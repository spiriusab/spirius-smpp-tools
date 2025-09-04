#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Connect to a SMPP v3.4 interface, send an SMS to a specified number
and wait for delivery report using modern smpplib.
"""
import argparse
import io
import os
import socket
import ssl
import sys
import time
from contextlib import redirect_stderr
from threading import Thread, Event

import questionary
import smpplib.client
import smpplib.consts
import smpplib.gsm
from dotenv import load_dotenv
from colorama import Fore, Style, init

# Initialize colorama for cross-platform colored output
init(autoreset=True)


# Load environment variables
load_dotenv()

# Configuration constants loaded from environment
SMSC_SERVERS = {
    'SMSC_1': os.getenv('SMSC_1', 'localhost'),
    'SMSC_2': os.getenv('SMSC_2', 'localhost')
}

# Default values from environment or fallbacks
SMPP_PLAIN_PORT = int(os.getenv('SMPP_PLAIN_PORT'))
SMPP_SSL_PORT = int(os.getenv('SMPP_SSL_PORT'))
SOURCE_TON = os.getenv('SOURCE_TON')
SOURCE_NPI = os.getenv('SOURCE_NPI')
SOURCE_ADDRESS = os.getenv('SOURCE_ADDRESS')
DEST_TON = os.getenv('DEST_TON')
DEST_NPI = os.getenv('DEST_NPI')
SMPP_USERNAME = os.getenv('SMPP_USERNAME')
SMPP_PASSWORD = os.getenv('SMPP_PASSWORD')
DEST_ADDRESS = os.getenv('DEST_ADDRESS')


def parse_arguments():
    parser = argparse.ArgumentParser(description='SMPP Sender - Connect to SMPP v3.4 interface and send SMS')
    parser.add_argument('-s', '--ssl', action='store_true', help='Use SSL/TLS connection')
    parser.add_argument('-i', '--interactive', action='store_true', help='Interactive mode - prompt for username, password, and destination')
    return parser.parse_args()


def message_sent_handler(pdu):
    print(f"{Fore.GREEN}📤 Message sent - Sequence: {pdu.sequence}, Message ID: {pdu.message_id}{Style.RESET_ALL}")


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
                print(f"{Fore.YELLOW}📋 Delivery report: Status = {status}{Style.RESET_ALL}")
                delivery_received_event.set()
            else:
                print(f"{Fore.BLUE}📨 Message received: {msg}{Style.RESET_ALL}")
        else:
            print(f"{Fore.MAGENTA}📡 Received PDU: {pdu.command} (sequence: {pdu.sequence}){Style.RESET_ALL}")
    return message_received_handler


def main():
    args = parse_arguments()
    use_ssl = args.ssl
    interactive = args.interactive

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
    port = SMPP_SSL_PORT if use_ssl else SMPP_PLAIN_PORT
    message_count = 1
    source_ton = int(SOURCE_TON, 0)
    source_npi = int(SOURCE_NPI, 0)
    source_addr = SOURCE_ADDRESS
    dest_ton = int(DEST_TON, 0)
    dest_npi = int(DEST_NPI, 0)

    # Get user inputs based on interactive mode
    if interactive:
        username = input(f"Enter username [{SMPP_USERNAME}]: ").strip() or SMPP_USERNAME
        
        password = input("Enter password: ").strip()
        if not password:
            print("Password is required")
            sys.exit(1)

        dest_addr = input(f"Enter destination address [{DEST_ADDRESS}]: ").strip()
        if not dest_addr:
            dest_addr = DEST_ADDRESS
    else:
        # Use values from environment
        username = SMPP_USERNAME
        password = SMPP_PASSWORD
        dest_addr = DEST_ADDRESS
        
        if not username:
            print(f"{Fore.RED}❌ Error: SMPP_USERNAME not set in environment{Style.RESET_ALL}")
            sys.exit(1)
        if not password:
            print(f"{Fore.RED}❌ Error: SMPP_PASSWORD not set in environment{Style.RESET_ALL}")
            sys.exit(1)
        if not dest_addr:
            print(f"{Fore.RED}❌ Error: DEST_ADDRESS not set in environment{Style.RESET_ALL}")
            sys.exit(1)
            
        print(f"{Fore.CYAN}👤 Using username: {username}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📱 Using destination: {dest_addr}{Style.RESET_ALL}")

    message = f"Testing SMPP\nServer: {server_choice}\nAccount: {username}\nSSL/TLS: {'YES' if use_ssl else 'NO'}\nTime: {time.strftime('%Y-%m-%d %H:%M:%S')}"

    # Create client
    try:
        print(f"{Fore.WHITE}🔌 Connecting to {server_choice} ({host}:{port}) with {'SSL/TLS' if use_ssl else 'plain TCP'}{Style.RESET_ALL}")
        
        if use_ssl:
            # Test SSL/TLS connection first
            print(f"{Fore.WHITE}🔐 Testing SSL/TLS connection...{Style.RESET_ALL}")
            try:
                # Create SSL context for SSL/TLS connection
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                # Test SSL/TLS handshake
                test_sock = socket.create_connection((host, port), timeout=10)
                ssl_test_sock = ssl_context.wrap_socket(test_sock, server_hostname=host)
                ssl_test_sock.close()
                print(f"{Fore.GREEN}✅ SSL/TLS connection successful{Style.RESET_ALL}")
                
                # Create SMPP client using SSL context (client.connect() will wrap the socket)
                client = smpplib.client.Client(host, port, ssl_context=ssl_context)
                
            except ssl.SSLError as e:
                print(f"{Fore.RED}❌ SSL/TLS connection failed: {e}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}💡 Use plain TCP connection (without -s/--ssl flag) if SSL/TLS is not supported.{Style.RESET_ALL}")
                sys.exit(1)
                
            except Exception as e:
                print(f"{Fore.RED}❌ Connection test failed: {e}{Style.RESET_ALL}")
                raise
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
            print(f"{Fore.WHITE}⏰ Timeout reached, no delivery report received{Style.RESET_ALL}")
        
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
