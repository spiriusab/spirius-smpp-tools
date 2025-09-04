#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SMPP Receiver - Receive MO SMS messages and optionally send test messages
for end-to-end MO SMS testing using bind_transceiver mode.
"""

import argparse
import io
import os
import sys
import time
from contextlib import redirect_stderr
from threading import Thread, Event
import re

import questionary
import smpplib.client
import smpplib.consts
import smpplib.gsm
from colorama import Fore, Style

# Import common SMPP functionality
sys.path.append('..')
from common.smpp_common import (
    load_env_file, get_smsc_servers, get_connection_config, get_smpp_params,
    test_ssl_connection, validate_required_params, print_connection_info,
    print_using_params, create_test_message
)

# Load receiver-specific environment variables
load_env_file('.env.receiver')

# Configuration from environment
SMSC_SERVERS = get_smsc_servers()
CONNECTION_CONFIG = get_connection_config()
SMPP_PARAMS = get_smpp_params()

# MO-specific configuration
RECEIVER_TIMEOUT = int(os.getenv('RECEIVER_TIMEOUT', '30'))

# Message correlation tracking
sent_messages = {}
received_messages = []


def parse_arguments():
    parser = argparse.ArgumentParser(description='SMPP Receiver - Receive MO SMS and test end-to-end MO functionality')
    parser.add_argument('-s', '--ssl', action='store_true', help='Use SSL/TLS connection')
    parser.add_argument('-i', '--interactive', action='store_true', help='Interactive mode - prompt for username, password, and destination')
    parser.add_argument('-m', '--mode', choices=['receive', 'send', 'test'], default='test', help='Operation mode (default: test)')
    parser.add_argument('-c', '--count', type=int, default=1, help='Number of test messages to send (default: 1)')
    parser.add_argument('-w', '--wait', type=int, default=30, help='Wait time for receiving messages in seconds (default: 30)')
    parser.add_argument('-t', '--text', help='Custom message text (default: auto-generated)')
    return parser.parse_args()


def message_sent_handler(pdu):
    """Handle sent message confirmations."""
    print(f"{Fore.GREEN}📤 Message sent - Sequence: {pdu.sequence}, Message ID: {pdu.message_id}{Style.RESET_ALL}")
    
    # Store sent message for correlation
    if hasattr(pdu, 'sequence'):
        sent_messages[pdu.sequence] = {
            'message_id': pdu.message_id,
            'timestamp': time.time()
        }


def create_mo_message_handler(mo_received_event):
    """Create handler for incoming MO messages (deliver_sm PDUs)."""
    def mo_message_handler(pdu):
        global received_messages
        
        # Handle MO messages (deliver_sm PDUs)
        if hasattr(pdu, 'command') and pdu.command == 'deliver_sm':
            # Extract MO message details
            source_addr = getattr(pdu, 'source_addr', 'Unknown')
            destination_addr = getattr(pdu, 'destination_addr', 'Unknown')
            short_message = getattr(pdu, 'short_message', b'')
            
            # Decode message content
            if isinstance(short_message, bytes):
                try:
                    # Try GSM 7-bit decoding first
                    message_text = smpplib.gsm.gsm_decode(short_message)
                except (UnicodeDecodeError, ValueError):
                    # Fallback to UTF-8
                    message_text = short_message.decode('utf-8', errors='ignore')
            else:
                message_text = str(short_message)
            
            # Store received message
            mo_message = {
                'source': source_addr,
                'destination': destination_addr,
                'text': message_text,
                'timestamp': time.time(),
                'sequence': getattr(pdu, 'sequence', None)
            }
            received_messages.append(mo_message)
            
            # Display MO message
            print(f"{Fore.BLUE}📨 MO Message received:{Style.RESET_ALL}")
            print(f"  {Fore.CYAN}From: {source_addr}{Style.RESET_ALL}")
            print(f"  {Fore.CYAN}To: {destination_addr}{Style.RESET_ALL}")
            print(f"  {Fore.WHITE}Text: {message_text}{Style.RESET_ALL}")
            
            # Check for message correlation
            check_message_correlation(mo_message)
            mo_received_event.set()
            
        # Handle delivery reports
        elif hasattr(pdu, 'receipted_message_id') and pdu.receipted_message_id:
            print(f"{Fore.CYAN}📥 Delivery report received - Message ID: {pdu.receipted_message_id}{Style.RESET_ALL}")
            
        # Handle other delivery report formats
        elif hasattr(pdu, 'short_message') and pdu.short_message:
            msg = pdu.short_message.decode('utf-8', errors='ignore') if isinstance(pdu.short_message, bytes) else str(pdu.short_message)
            if 'stat:DELIVRD' in msg:
                print(f"{Fore.GREEN}✅ Delivery report: Message delivered successfully{Style.RESET_ALL}")
            elif 'stat:' in msg:
                status_match = re.search(r'stat:([A-Z]+)', msg)
                status = status_match.group(1) if status_match else 'UNKNOWN'
                print(f"{Fore.YELLOW}📋 Delivery report: Status = {status}{Style.RESET_ALL}")
            else:
                print(f"{Fore.BLUE}📨 Message received: {msg}{Style.RESET_ALL}")
        else:
            print(f"{Fore.MAGENTA}📡 Received PDU: {pdu.command} (sequence: {pdu.sequence}){Style.RESET_ALL}")
    
    return mo_message_handler


def check_message_correlation(mo_message):
    """Check if received MO message correlates with sent test message."""
    text = mo_message['text']
    
    # Look for correlation by message content
    # Check if this looks like our test message
    if 'Testing SMPP' in text:
        print(f"{Fore.GREEN}🔗 Message correlation found!{Style.RESET_ALL}")
        print(f"  {Fore.GREEN}✅ Test message successfully received as MO SMS{Style.RESET_ALL}")
        return True
    
    return False


def send_test_messages(client, count, custom_text, server_choice, username, use_ssl, smpp_params):
    """Send test messages that will be received as MO messages."""
    print(f"{Fore.CYAN}📤 Sending {count} test message(s)...{Style.RESET_ALL}")
    
    for i in range(count):
        message = custom_text or create_test_message(server_choice, username, use_ssl)
        
        print(f"{Fore.CYAN}📤 Sending message {i+1}/{count}{Style.RESET_ALL}")
        
        pdu = client.send_message(
            source_addr_ton=smpp_params['source_ton'],
            source_addr_npi=smpp_params['source_npi'],
            source_addr=smpp_params['source_address'],
            dest_addr_ton=smpp_params['dest_ton'],
            dest_addr_npi=smpp_params['dest_npi'],
            destination_addr=smpp_params['dest_address'],
            short_message=smpplib.gsm.gsm_encode(message),
            data_coding=0x00,  # GSM 7-bit encoding
            registered_delivery=True
        )
        print(f"{Fore.GREEN}✅ Message queued with sequence: {pdu.sequence}{Style.RESET_ALL}")
        
        if i < count - 1:
            time.sleep(1)  # Wait 1 second between messages


def main():
    args = parse_arguments()
    use_ssl = args.ssl
    interactive = args.interactive
    mode = args.mode
    message_count = args.count
    wait_time = args.wait
    custom_text = args.text

    print(f"{Fore.CYAN}{Style.BRIGHT}SMPP Receiver{Style.RESET_ALL}")
    print(f"Mode: {mode.upper()}")
    if use_ssl:
        print(f"{Fore.GREEN}🔒 Using SSL/TLS connection{Style.RESET_ALL}")
    else:
        print(f"{Fore.WHITE}🔓 Using plain TCP connection{Style.RESET_ALL}")
    print()

    # Server selection with questionary
    server_choice = questionary.select(
        "Select SMPP server:",
        choices=[
            questionary.Choice(f"{name} ({ip})", value=name) 
            for name, ip in SMSC_SERVERS.items()
        ]
    ).ask()
    
    if not server_choice:
        print(f"{Fore.RED}❌ Server selection is required{Style.RESET_ALL}")
        sys.exit(1)
    
    host = SMSC_SERVERS[server_choice]
    port = CONNECTION_CONFIG['ssl_port'] if use_ssl else CONNECTION_CONFIG['plain_port']

    # Get user inputs based on interactive mode
    if interactive:
        username = input(f"Enter username [{SMPP_PARAMS['username']}]: ").strip() or SMPP_PARAMS['username']
        
        password = input("Enter password: ").strip()
        if not password:
            print("Password is required")
            sys.exit(1)

        if mode in ['send', 'test']:
            dest_addr = input(f"Enter destination address [{SMPP_PARAMS['dest_address']}]: ").strip()
            if not dest_addr:
                dest_addr = SMPP_PARAMS['dest_address']
            SMPP_PARAMS['dest_address'] = dest_addr
    else:
        # Use values from environment
        username = SMPP_PARAMS['username']
        password = SMPP_PARAMS['password']
        
        validate_required_params(SMPP_PARAMS, ['username', 'password'])
        print_using_params(username, SMPP_PARAMS.get('dest_address', 'N/A'))

    # Create client
    try:
        print_connection_info(server_choice, host, port, use_ssl)
        
        if use_ssl:
            ssl_context = test_ssl_connection(host, port)
            client = smpplib.client.Client(host, port, ssl_context=ssl_context)
        else:
            client = smpplib.client.Client(host, port)

        # Create event to signal when MO message is received
        mo_received = Event()
        
        # Set handlers
        client.set_message_sent_handler(message_sent_handler)
        client.set_message_received_handler(create_mo_message_handler(mo_received))

        # Connect and bind as transceiver
        client.connect()
        print(f"{Fore.GREEN}✅ Connected{Style.RESET_ALL}")
        
        print(f"{Fore.WHITE}🔗 Binding in TRX mode (for MO reception){Style.RESET_ALL}")
        client.bind_transceiver(system_id=username, password=password)
        print(f"{Fore.GREEN}✅ Bound successfully{Style.RESET_ALL}")

        # Start listening thread
        def listen_thread():
            try:
                client.listen()
            except Exception:
                pass
        
        listener = Thread(target=listen_thread, daemon=True)
        listener.start()

        # Execute based on mode
        if mode == 'receive':
            print(f"{Fore.WHITE}👂 Listening for MO messages for {wait_time} seconds...{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}💡 (Press Ctrl+C to stop early){Style.RESET_ALL}")
            
            if mo_received.wait(timeout=wait_time):
                print(f"{Fore.GREEN}✅ Received {len(received_messages)} MO message(s){Style.RESET_ALL}")
            else:
                print(f"{Fore.WHITE}⏰ Timeout reached, received {len(received_messages)} MO message(s){Style.RESET_ALL}")
                
        elif mode == 'send':
            send_test_messages(client, message_count, custom_text, server_choice, username, use_ssl, SMPP_PARAMS)
            
        elif mode == 'test':
            print(f"{Fore.YELLOW}🧪 Starting end-to-end MO SMS test{Style.RESET_ALL}")
            
            # Send test message(s)
            send_test_messages(client, message_count, custom_text, server_choice, username, use_ssl, SMPP_PARAMS)
            
            # Wait for MO messages
            print(f"{Fore.WHITE}👂 Waiting for MO messages for {wait_time} seconds...{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}💡 (Press Ctrl+C to stop early){Style.RESET_ALL}")
            
            if mo_received.wait(timeout=wait_time):
                print(f"{Fore.GREEN}✅ Test completed - received {len(received_messages)} MO message(s){Style.RESET_ALL}")
            else:
                print(f"{Fore.WHITE}⏰ Timeout reached - received {len(received_messages)} MO message(s){Style.RESET_ALL}")

        # Graceful shutdown
        print(f"{Fore.WHITE}🔄 Shutting down...{Style.RESET_ALL}")
        
        try:
            with redirect_stderr(io.StringIO()):
                client.disconnect()
            print(f"{Fore.GREEN}✅ Disconnected{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}❌ Disconnect error: {e}{Style.RESET_ALL}")

    except KeyboardInterrupt:
        print(f"{Fore.WHITE}\n⏹️  Stopped by user{Style.RESET_ALL}")
        try:
            client.unbind()
            client.disconnect()
        except Exception:
            pass
    except Exception as e:
        print(f"{Fore.RED}❌ Error: {e}{Style.RESET_ALL}")
        try:
            client.disconnect()
        except Exception:
            pass
        sys.exit(1)

    print(f"{Fore.GREEN}{Style.BRIGHT}✅ Done{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
