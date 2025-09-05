#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SMPP Receiver - Receive MO SMS messages and optionally send test messages
for end-to-end MO SMS testing using bind_transceiver mode.
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
    test_ssl_connection, print_connection_info, 
    print_using_params, create_test_message, decode_sms_message
)

# Load receiver-specific environment variables
load_env_file('.env.receiver')

# Configuration from environment
SMSC_SERVERS = get_smsc_servers()
CONNECTION_CONFIG = get_connection_config()

# Get SMPP parameters with error handling
try:
    SMPP_PARAMS = get_smpp_params()
except ValueError as e:
    print(f"{Fore.RED}❌ Configuration error: {e}{Style.RESET_ALL}")
    sys.exit(1)
except Exception as e:
    print(f"{Fore.RED}❌ Unexpected error while reading configuration: {e}{Style.RESET_ALL}")
    sys.exit(1)


# MO-specific configuration
RECEIVER_TIMEOUT = 30  # Timeout in seconds

# Message correlation tracking
sent_messages = {}
received_messages = []
delivery_reports_received = []

# Global verbose mode flag
verbose_mode = False


def parse_arguments():
    parser = argparse.ArgumentParser(description='SMPP Receiver - Receive MO SMS and test end-to-end MO functionality')
    parser.add_argument('-s', '--ssl', action='store_true', help='Use SSL/TLS connection')
    parser.add_argument('-m', '--mode', choices=['send-receive', 'receive-only'], default='send-receive', help='Operation mode (default: send-receive)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    return parser.parse_args()


def message_sent_handler(pdu):
    """Handle sent message confirmations."""
    # Convert message ID to string for display
    message_id_str = pdu.message_id.decode('utf-8', errors='ignore') if isinstance(pdu.message_id, bytes) else str(pdu.message_id)
    
    print(f"{Fore.GREEN}📤 Message sent - Message ID: {message_id_str}{Style.RESET_ALL}")
    
    # Store sent message for correlation
    if hasattr(pdu, 'sequence'):
        sent_messages[pdu.sequence] = {
            'message_id': pdu.message_id,
            'timestamp': time.time()
        }


def decode_sms_message_with_verbose_logging(raw_bytes, data_coding):
    """
    Wrapper for decode_sms_message with verbose output.
    """
    print(f"{Fore.YELLOW}🔍 Decoding with data_coding=0x{data_coding:02X}{Style.RESET_ALL}")
    
    # Map data_coding to description for verbose output
    coding_descriptions = {
        0x00: "GSM 7-bit default alphabet",
        0x01: "ASCII",
        0x02: "8-bit binary (UTF-8)",
        0x03: "Latin-1 (ISO-8859-1)",
        0x08: "UCS2 (UTF-16BE)"
    }
    
    if data_coding in coding_descriptions:
        print(f"{Fore.YELLOW}🔍 Using {coding_descriptions[data_coding]}{Style.RESET_ALL}")
    elif data_coding & 0xF0 == 0xF0:
        print(f"{Fore.YELLOW}🔍 GSM 7-bit with message class{Style.RESET_ALL}")
    else:
        print(f"{Fore.YELLOW}🔍 Unknown data_coding, falling back to GSM 7-bit{Style.RESET_ALL}")

    result = decode_sms_message(raw_bytes, data_coding)
    print(f"{Fore.GREEN}🔍 Successfully decoded message{Style.RESET_ALL}")
    return result

def create_mo_message_handler(mo_received_event, verbose_mode=False):
    """Create handler for incoming MO messages (deliver_sm PDUs)."""
    def mo_message_handler(pdu):
        global received_messages
        
        # Print all incoming PDUs with details
        if verbose_mode:
            pdu_details = f"command={pdu.command}, sequence={pdu.sequence}"
            if hasattr(pdu, 'source_addr'):
                pdu_details += f", source={pdu.source_addr}"
            if hasattr(pdu, 'destination_addr'):
                pdu_details += f", dest={pdu.destination_addr}"
            if hasattr(pdu, 'short_message'):
                pdu_details += f", message_len={len(pdu.short_message) if pdu.short_message else 0}"
            print(f"{Fore.MAGENTA}🔍 Received PDU: {pdu_details}{Style.RESET_ALL}")
        
        # Handle MO messages (deliver_sm PDUs)
        if hasattr(pdu, 'command') and pdu.command == 'deliver_sm':
            if verbose_mode:
                print(f"{Fore.YELLOW}🔍 Processing deliver_sm PDU{Style.RESET_ALL}")
            # Extract MO message details
            source_addr = getattr(pdu, 'source_addr', 'Unknown')
            destination_addr = getattr(pdu, 'destination_addr', 'Unknown')
            short_message = getattr(pdu, 'short_message', b'')
            data_coding = getattr(pdu, 'data_coding', 0x00)  # Default to GSM 7-bit if not present
            
            if verbose_mode:
                print(f"{Fore.YELLOW}🔍 Extracted - source={source_addr}, dest={destination_addr}, msg_len={len(short_message) if short_message else 0}, data_coding=0x{data_coding:02X}{Style.RESET_ALL}")
            
            # Decode message content using proper data_coding field
            if verbose_mode:
                print(f"{Fore.YELLOW}🔍 Decoding message, type={type(short_message)}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}🔍 Raw bytes (first 50): {short_message[:50]}{Style.RESET_ALL}")
            
            # Use proper SMPP data_coding field for decoding
            if verbose_mode:
                message_text = decode_sms_message_with_verbose_logging(short_message, data_coding)
            else:
                message_text = decode_sms_message(short_message, data_coding)
            
            # Decode addresses properly
            source_str = source_addr.decode('utf-8') if isinstance(source_addr, bytes) else str(source_addr)
            dest_str = destination_addr.decode('utf-8') if isinstance(destination_addr, bytes) else str(destination_addr)
            
            # Check if this is a delivery report
            is_delivery_report = ('id:' in message_text and 'stat:' in message_text) or message_text.startswith("b'id:")
            
            # Store received message
            mo_message = {
                'source': source_str,
                'destination': dest_str,
                'text': message_text,
                'timestamp': time.time(),
                'is_delivery_report': is_delivery_report,
                'sequence': getattr(pdu, 'sequence', None)
            }
            received_messages.append(mo_message)
            
            # Track delivery reports separately
            if is_delivery_report:
                delivery_reports_received.append(mo_message)
            
            # Only trigger MO received event for actual MO messages, not delivery reports
            should_trigger_event = not is_delivery_report
            
            # Display MO message
            if is_delivery_report:
                print(f"{Fore.BLUE}📋 Delivery Report received:{Style.RESET_ALL}")
                print(f"  From: {source_str}")
                print(f"  To: {dest_str}")
                # Extract status from delivery report
                if 'stat:DELIVRD' in message_text:
                    print(f"  Status: {Fore.GREEN}DELIVERED{Style.RESET_ALL}")
                elif 'stat:' in message_text:
                    import re
                    status_match = re.search(r'stat:([A-Z]+)', message_text)
                    status = status_match.group(1) if status_match else 'UNKNOWN'
                    # Color failed statuses in red
                    if status in ['UNDELIV', 'REJECTD', 'EXPIRED', 'UNKNOWN']:
                        print(f"  Status: {Fore.RED}{status}{Style.RESET_ALL}")
                    else:
                        print(f"  Status: {status}")
                else:
                    print(f"  Raw: {message_text}")
            else:
                print(f"{Fore.GREEN}📨 MO Message received:{Style.RESET_ALL}")
                print(f"  From: {source_str}")
                print(f"  To: {dest_str}")
                print(f"  Text: {message_text}")
            
            # Check for message correlation
            if verbose_mode:
                print(f"{Fore.YELLOW}🔍 Checking message correlation{Style.RESET_ALL}")
            check_message_correlation(mo_message)
            
            # Only set event for actual MO messages, not delivery reports
            if should_trigger_event:
                if verbose_mode:
                    print(f"{Fore.YELLOW}🔍 Setting mo_received event for MO message{Style.RESET_ALL}")
                mo_received_event.set()
            elif verbose_mode:
                print(f"{Fore.YELLOW}🔍 Skipping event for delivery report{Style.RESET_ALL}")
            
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
    # First try correlation by delivery report message ID
    if mo_message.get('is_delivery_report', False):
        text = mo_message['text']
        # Extract message ID from delivery report
        import re
        id_match = re.search(r'id:(\d+)', text)
        if id_match:
            dlr_message_id = id_match.group(1)
            # Check if this message ID matches any sent message
            for seq, sent_info in sent_messages.items():
                sent_id = sent_info['message_id']
                # Handle both string and bytes message IDs
                if isinstance(sent_id, bytes):
                    sent_id = sent_id.decode('utf-8', errors='ignore')
                if str(sent_id) == dlr_message_id:
                    print(f"{Fore.GREEN}🔗 Delivery report correlation found!{Style.RESET_ALL}")
                    print(f"  {Fore.GREEN}✅ Message ID {dlr_message_id} matches sent message (seq: {seq}){Style.RESET_ALL}")
                    # Mark this sent message as having received its delivery report
                    sent_messages[seq]['dlr_received'] = True
                    
                    # Extract and store delivery status for early termination logic
                    status_match = re.search(r'stat:([A-Z]+)', text)
                    if status_match:
                        sent_messages[seq]['dlr_status'] = status_match.group(1)
                    
                    return True
    
    return False


def has_received_all_confirmations():
    """Check if we have received both MO message and delivery report for sent messages."""
    if not sent_messages:
        return False
    
    # Check if we have at least one MO message (actual SMS content)
    mo_messages = [msg for msg in received_messages if not msg.get('is_delivery_report', False)]
    has_mo_message = len(mo_messages) > 0
    
    # Check if all sent messages have received their delivery reports
    all_dlrs_received = all(sent_info.get('dlr_received', False) for sent_info in sent_messages.values())
    
    # If we received a failed delivery report (UNDELIV, etc.), we can stop early
    # since we know the message won't arrive as MO
    has_failed_delivery = any(sent_info.get('dlr_received', False) and 
                             sent_info.get('dlr_status') in ['UNDELIV', 'REJECTD', 'EXPIRED', 'UNKNOWN'] 
                             for sent_info in sent_messages.values())
    
    return (has_mo_message and all_dlrs_received) or has_failed_delivery


def send_test_message(client, server_choice, username, use_ssl, smpp_params):
    """Send a test message that will be received as MO message."""
    print(f"{Fore.CYAN}📤 Sending test message...{Style.RESET_ALL}")
    
    message = create_test_message(server_choice, username, use_ssl)
    
    pdu = client.send_message(
        source_addr_ton=smpp_params['source_ton'],
        source_addr_npi=smpp_params['source_npi'],
        source_addr=smpp_params['source_address'],
        dest_addr_ton=0x01,  # International E.164
        dest_addr_npi=0x01,  # ISDN numbering plan,
        destination_addr=smpp_params['dest_address'],
        short_message=smpplib.gsm.gsm_encode(message),
        data_coding=0x00,  # GSM 7-bit encoding
        registered_delivery=True
    )
    print(f"{Fore.GREEN}✅ Message queued with sequence: {pdu.sequence}{Style.RESET_ALL}")


def main():
    global verbose_mode
    args = parse_arguments()
    verbose_mode = args.verbose
    use_ssl = args.ssl
    mode = args.mode

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

    # Always use values from environment
    username = SMPP_PARAMS['username']
    password = SMPP_PARAMS['password']
    
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
        
        # Set up message handlers
        client.set_message_received_handler(create_mo_message_handler(mo_received, verbose_mode))
        client.set_message_sent_handler(message_sent_handler)
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
        if mode == 'receive-only':
            print(f"{Fore.WHITE}👂 Listening for MO messages indefinitely...{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}💡 Press Ctrl+C to stop{Style.RESET_ALL}")
            
            try:
                # Wait indefinitely for messages
                while True:
                    if mo_received.wait(timeout=1):
                        # Reset the event to continue listening
                        mo_received.clear()
                    # Continue the loop - this keeps the connection alive
            except KeyboardInterrupt:
                print(f"{Fore.WHITE}\n⏹️  Stopped by user{Style.RESET_ALL}")
                actual_mo_count = len([msg for msg in received_messages if not msg.get('is_delivery_report', False)])
                print(f"{Fore.GREEN}✅ Received {actual_mo_count} MO message(s) total{Style.RESET_ALL}")
                
        elif mode == 'send-receive':
            print(f"{Fore.YELLOW}🧪 Starting end-to-end MO SMS test{Style.RESET_ALL}")
            
            # Send test message
            send_test_message(client, server_choice, username, use_ssl, SMPP_PARAMS)
            
            # Wait for both MO message and delivery report
            print(f"{Fore.WHITE}👂 Waiting for MO message and delivery report for 30 seconds...{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}💡 (Press Ctrl+C to stop early){Style.RESET_ALL}")
            
            # Wait for MO message first
            if mo_received.wait(timeout=30):
                # Continue waiting for delivery report
                print(f"{Fore.YELLOW}📨 MO message received, waiting for delivery report...{Style.RESET_ALL}")
                
                # Wait additional time for delivery report
                start_time = time.time()
                while time.time() - start_time < 15:  # Wait up to 15 more seconds for DLR
                    if has_received_all_confirmations():
                        actual_mo_count = len([msg for msg in received_messages if not msg.get('is_delivery_report', False)])
                        dlr_count = len(delivery_reports_received)
                        print(f"{Fore.GREEN}✅ Test completed - received {actual_mo_count} MO message(s) and {dlr_count} delivery report(s){Style.RESET_ALL}")
                        break
                    time.sleep(0.5)
                else:
                    # Timeout waiting for delivery report
                    actual_mo_count = len([msg for msg in received_messages if not msg.get('is_delivery_report', False)])
                    dlr_count = len(delivery_reports_received)
                    print(f"{Fore.YELLOW}⏰ Delivery report timeout - received {actual_mo_count} MO message(s) and {dlr_count} delivery report(s){Style.RESET_ALL}")
            else:
                actual_mo_count = len([msg for msg in received_messages if not msg.get('is_delivery_report', False)])
                dlr_count = len(delivery_reports_received)
                color = Fore.RED if actual_mo_count == 0 else Fore.WHITE
                print(f"{color}⏰ Timeout reached - received {actual_mo_count} MO message(s) and {dlr_count} delivery report(s){Style.RESET_ALL}")

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
