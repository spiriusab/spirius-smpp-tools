#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Connect to a SMPP v3.4 interface, send an SMS to a specified number
and wait for delivery report using modern smpplib.
"""
import argparse
import io
import sys
import time
from contextlib import redirect_stderr
from threading import Thread, Event

import questionary
import smpplib.client
import smpplib.consts
import smpplib.gsm
from colorama import Fore, Style

# Import common SMPP functionality
sys.path.append('..')
from common.smpp_common import (
    load_env_file, get_smsc_servers, get_connection_config, get_smpp_params,
    test_ssl_connection, print_connection_info, print_using_params, 
    validate_required_params, validate_e164_address, create_test_message
)

# Load sender-specific environment variables
load_env_file('.env.sender')

# Configuration from environment
SMSC_SERVERS = get_smsc_servers()
CONNECTION_CONFIG = get_connection_config()
SMPP_PARAMS = get_smpp_params()

# Global debug mode flag
debug_mode = False


def parse_arguments():
    parser = argparse.ArgumentParser(description='SMPP Sender - Connect to SMPP v3.4 interface and send SMS')
    parser.add_argument('-s', '--ssl', action='store_true', help='Use SSL/TLS connection')
    parser.add_argument('-i', '--interactive', action='store_true', help='Interactive mode - prompt for username, password, and destination')
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('-t', '--text', help='Custom message text (default: auto-generated)')
    return parser.parse_args()


def message_sent_handler(pdu):
    # Convert message ID to string for display
    message_id_str = pdu.message_id.decode('utf-8', errors='ignore') if isinstance(pdu.message_id, bytes) else str(pdu.message_id)
    
    if debug_mode:
        print(f"{Fore.GREEN}📤 Message sent - Sequence: {pdu.sequence}, Message ID: {message_id_str}{Style.RESET_ALL}")
    else:
        print(f"{Fore.GREEN}📤 Message sent - Message ID: {message_id_str}{Style.RESET_ALL}")


def create_message_received_handler(delivery_received_event):
    def message_received_handler(pdu):
        # Handle delivery reports and other incoming messages
        if hasattr(pdu, 'receipted_message_id') and pdu.receipted_message_id:
            print(f"{Fore.CYAN}📥 Delivery report received - Message ID: {pdu.receipted_message_id}{Style.RESET_ALL}")
            delivery_received_event.set()
        elif hasattr(pdu, 'short_message') and pdu.short_message:
            # Parse delivery report from short_message
            msg = pdu.short_message.decode('utf-8', errors='ignore') if isinstance(pdu.short_message, bytes) else str(pdu.short_message)
            if 'stat:DELIVRD' in msg:
                print(f"{Fore.GREEN}✅ Delivery report: Message delivered successfully{Style.RESET_ALL}")
                delivery_received_event.set()
            elif 'stat:' in msg:
                # Extract status from delivery report
                import re
                status_match = re.search(r'stat:([A-Z]+)', msg)
                status = status_match.group(1) if status_match else 'UNKNOWN'
                # Color failed statuses in red
                if status in ['UNDELIV', 'REJECTD', 'EXPIRED', 'UNKNOWN']:
                    print(f"{Fore.RED}📋 Delivery report: Status = {status}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}📋 Delivery report: Status = {status}{Style.RESET_ALL}")
                delivery_received_event.set()
            else:
                print(f"{Fore.BLUE}📨 Message received: {msg}{Style.RESET_ALL}")
        else:
            print(f"{Fore.MAGENTA}📡 Received PDU: {pdu.command} (sequence: {pdu.sequence}){Style.RESET_ALL}")
    return message_received_handler


def main():
    global debug_mode
    args = parse_arguments()
    debug_mode = args.debug
    use_ssl = args.ssl
    interactive = args.interactive
    custom_text = args.text

    print(f"{Fore.CYAN}{Style.BRIGHT}SMPP Sender{Style.RESET_ALL}")
    print("Attempts to send an SMS over SMPP")
    if use_ssl:
        print(f"{Fore.WHITE}🔒 Using SSL/TLS connection{Style.RESET_ALL}")
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
    message_count = 1
    source_ton = SMPP_PARAMS['source_ton']
    source_npi = SMPP_PARAMS['source_npi']
    source_addr = SMPP_PARAMS['source_address']
    dest_ton = 0x01  # International E.164
    dest_npi = 0x01  # ISDN numbering plan

    # Get user inputs based on interactive mode
    if interactive:
        username = input(f"Enter username [{SMPP_PARAMS['username']}]: ").strip() or SMPP_PARAMS['username']
        
        password = input("Enter password: ").strip()
        if not password:
            print("Password is required")
            sys.exit(1)

        dest_addr = input(f"Enter destination address [{SMPP_PARAMS['dest_address']}]: ").strip()
        if not dest_addr:
            dest_addr = SMPP_PARAMS['dest_address']
        
        # Validate E.164 format
        is_valid, error_msg = validate_e164_address(dest_addr)
        if not is_valid:
            print(f"{Fore.RED}❌ Invalid destination address: {error_msg}{Style.RESET_ALL}")
            sys.exit(1)
    else:
        # Use values from environment
        username = SMPP_PARAMS['username']
        password = SMPP_PARAMS['password']
        dest_addr = SMPP_PARAMS['dest_address']
        
        validate_required_params(SMPP_PARAMS, ['username', 'password', 'dest_address'])
        
        # Validate E.164 format
        is_valid, error_msg = validate_e164_address(dest_addr)
        if not is_valid:
            print(f"{Fore.RED}❌ Invalid destination address: {error_msg}{Style.RESET_ALL}")
            sys.exit(1)
        print_using_params(username, dest_addr)

    message = custom_text or create_test_message(server_choice, username, use_ssl)

    # Create client
    try:
        print_connection_info(server_choice, host, port, use_ssl)
        
        if use_ssl:
            ssl_context = test_ssl_connection(host, port)
            client = smpplib.client.Client(host, port, ssl_context=ssl_context)
        else:
            client = smpplib.client.Client(host, port)

        # Create event to signal when delivery report is received
        delivery_received = Event()
        
        # Set handlers
        client.set_message_sent_handler(message_sent_handler)
        client.set_message_received_handler(create_message_received_handler(delivery_received))

        # Connect and bind
        client.connect()
        print(f"{Fore.GREEN}✅ Connected{Style.RESET_ALL}")
        
        print(f"{Fore.WHITE}🔗 Binding in TRX mode{Style.RESET_ALL}")
        client.bind_transceiver(system_id=username, password=password)
        print(f"{Fore.GREEN}✅ Bound successfully{Style.RESET_ALL}")

        # Send messages
        if message_count > 0:
            for i in range(message_count):
                print(f"{Fore.CYAN}📤 Sending message {i+1}/{message_count}{Style.RESET_ALL}")
                
                pdu = client.send_message(
                    source_addr_ton=source_ton,
                    source_addr_npi=source_npi,
                    source_addr=source_addr,
                    dest_addr_ton=dest_ton,
                    dest_addr_npi=dest_npi,
                    destination_addr=dest_addr,
                    short_message=smpplib.gsm.gsm_encode(message),
                    data_coding=0x00,  # GSM 7-bit encoding
                    registered_delivery=True
                )
                print(f"{Fore.GREEN}✅ Message queued with sequence: {pdu.sequence}{Style.RESET_ALL}")
                
                if i < message_count - 1:
                    time.sleep(1)  # Wait 1 second between messages

        # Listen for responses
        print(f"{Fore.WHITE}⏳ Waiting up to 30 seconds for delivery reports...{Style.RESET_ALL}")
        print(f"{Fore.MAGENTA}💡 (Press Ctrl+C to stop early){Style.RESET_ALL}")
        
        def listen_thread():
            try:
                client.listen()
            except Exception:
                # Silently handle all listen thread errors during shutdown
                pass
        
        listener = Thread(target=listen_thread, daemon=True)
        listener.start()
        
        # Wait for delivery report or timeout
        if delivery_received.wait(timeout=30):
            time.sleep(0.1)  # Brief pause to ensure all responses are processed
        else:
            print(f"{Fore.RED}⏰ Timeout reached, no delivery report received{Style.RESET_ALL}")
        
        # Graceful shutdown sequence
        print(f"{Fore.WHITE}🔄 Shutting down...{Style.RESET_ALL}")
        
        # Skip unbind due to smpplib issues - just disconnect
        # For short-lived connections, the SMSC will handle cleanup
        try:
            # Suppress the "disconnecting in bound state" message
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
