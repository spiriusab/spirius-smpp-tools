#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SMS Decoder - Decode hexadecimal SMS message content using various encodings.
Useful for analyzing SMS messages captured in Wireshark or other network tools.
"""

import argparse
import sys
from colorama import Fore, Style, init

# Import common SMPP functionality
sys.path.append('..')
from common.smpp_common import decode_sms_message

# Initialize colorama for cross-platform colored output
init(autoreset=True)

# Data coding constants for reference
DATA_CODING_MAP = {
    0x00: "GSM 7-bit default alphabet",
    0x01: "ASCII",
    0x02: "8-bit binary (UTF-8)",
    0x03: "Latin-1 (ISO-8859-1)",
    0x08: "UCS2 (UTF-16BE)",
}


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='SMS Decoder - Decode hexadecimal SMS message content using various encodings. Useful for analyzing SMS messages captured in Wireshark or other network tools.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "4A54455F54455354"                    # Auto-detect encoding
  %(prog)s "4A54455F54455354" --encoding gsm     # Use GSM 7-bit decoding
  %(prog)s "4A54455F54455354" --data-coding 0x00 # Use SMPP data_coding value
  %(prog)s "4A54455F54455354" --all              # Try all encodings

Supported Encodings:
  gsm      (0x00) - GSM 7-bit default alphabet
  ascii    (0x01) - ASCII
  utf8     (0x02) - 8-bit binary (UTF-8)
  latin1   (0x03) - Latin-1 (ISO-8859-1)
  ucs2     (0x08) - UCS2 (UTF-16BE)

SMPP Data Coding:
  The data_coding field in SMPP PDUs specifies how message content is encoded.

Note: The encoding information is stored in the SMPP PDU header, not in the
message content itself.
        """
    )
    
    parser.add_argument('hexstring', nargs='?', help='Hexadecimal string to decode (e.g., "48656C6C6F20576F726C64")')
    parser.add_argument('-e', '--encoding', choices=['gsm', 'ascii', 'utf8', 'latin1', 'ucs2'], 
                       help='Force specific encoding (default: auto-detect)')
    parser.add_argument('-d', '--data-coding', type=lambda x: int(x, 0), 
                       choices=[0x00, 0x01, 0x02, 0x03, 0x08],
                       help='SMPP data_coding value (0x00=GSM, 0x01=ASCII, 0x02=UTF-8, 0x03=Latin-1, 0x08=UCS2)')
    parser.add_argument('-a', '--all', action='store_true',
                       help='Try all encodings and show results for each')
    parser.add_argument('-l', '--list-encodings', action='store_true', 
                       help='List supported encodings and exit')
    
    return parser.parse_args()


def hex_to_bytes(hex_string):
    """Convert hexadecimal string to bytes."""
    # Remove spaces, colons, and other separators
    clean_hex = ''.join(c for c in hex_string if c.isalnum())
    
    # Ensure even length
    if len(clean_hex) % 2 != 0:
        raise ValueError("Hexadecimal string must have even length")
    
    try:
        return bytes.fromhex(clean_hex)
    except ValueError as e:
        raise ValueError(f"Invalid hexadecimal string: {e}") from e


def encoding_to_data_coding(encoding):
    """Map encoding name to SMPP data_coding value."""
    mapping = {
        'gsm': 0x00,
        'ascii': 0x01,
        'utf8': 0x02,
        'latin1': 0x03,
        'ucs2': 0x08
    }
    return mapping.get(encoding, 0x00)


def try_decode_with_encoding(raw_bytes, encoding_name):
    """Try to decode bytes with specific encoding."""
    data_coding = encoding_to_data_coding(encoding_name)
    
    
    try:
        result = decode_sms_message(raw_bytes, data_coding)
        return result, True
    except Exception:
        return None, False


def auto_detect_encoding(raw_bytes):
    """Try to auto-detect the best encoding for the message."""
    
    # Try encodings in order of likelihood
    encodings_to_try = ['gsm', 'utf8', 'ascii', 'latin1', 'ucs2']
    
    results = []
    for encoding in encodings_to_try:
        result, success = try_decode_with_encoding(raw_bytes, encoding)
        if success and result:
            results.append((encoding, result))
    
    if not results:
        return None, None
    
    # Return the first successful decode (GSM 7-bit preferred)
    return results[0]


def try_all_encodings(raw_bytes):
    """Try all encodings and return results for each."""
    
    encodings_to_try = ['gsm', 'ascii', 'utf8', 'latin1', 'ucs2']
    results = []
    
    for encoding in encodings_to_try:
        result, success = try_decode_with_encoding(raw_bytes, encoding)
        if success and result:
            results.append((encoding, result))
        else:
            results.append((encoding, None))
    
    return results


def display_results(hex_input, raw_bytes, encoding_used, decoded_text):
    """Display decoding results in a formatted way."""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}SMS Decoder Results{Style.RESET_ALL}")
    print("=" * 50)
    
    print(f"{Fore.WHITE}Input (hex):{Style.RESET_ALL} {hex_input}")
    print(f"{Fore.WHITE}Raw bytes:{Style.RESET_ALL} {raw_bytes}")
    print(f"{Fore.WHITE}Length:{Style.RESET_ALL} {len(raw_bytes)} bytes")
    
    if encoding_used:
        data_coding = encoding_to_data_coding(encoding_used)
        encoding_desc = DATA_CODING_MAP.get(data_coding, f"Unknown (0x{data_coding:02X})")
        print(f"{Fore.WHITE}Encoding:{Style.RESET_ALL} {encoding_used.upper()} (data_coding=0x{data_coding:02X})")
        print(f"{Fore.WHITE}Description:{Style.RESET_ALL} {encoding_desc}")
    
    print(f"\n{Fore.GREEN}{Style.BRIGHT}Decoded text (raw):{Style.RESET_ALL} {repr(decoded_text)}")
    print(f"{Fore.GREEN}{Style.BRIGHT}Decoded text (display):{Style.RESET_ALL} {decoded_text}")
    
    
    print("=" * 50)


def display_all_results(hex_input, raw_bytes, all_results):
    """Display results for all encodings."""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}SMS Decoder - All Encodings{Style.RESET_ALL}")
    print("=" * 70)
    
    print(f"{Fore.WHITE}Input (hex):{Style.RESET_ALL} {hex_input}")
    print(f"{Fore.WHITE}Raw bytes:{Style.RESET_ALL} {raw_bytes}")
    print(f"{Fore.WHITE}Length:{Style.RESET_ALL} {len(raw_bytes)} bytes")
    
    for encoding, decoded_text in all_results:
        data_coding = encoding_to_data_coding(encoding)
        encoding_desc = DATA_CODING_MAP.get(data_coding, f"Unknown (0x{data_coding:02X})")
        
        print(f"\n{Fore.YELLOW}━━━ {encoding.upper()} (data_coding=0x{data_coding:02X}) ━━━{Style.RESET_ALL}")
        print(f"{Fore.WHITE}Description:{Style.RESET_ALL} {encoding_desc}")
        
        if decoded_text is not None:
            print(f"{Fore.GREEN}✅ Success:{Style.RESET_ALL} {repr(decoded_text)}")
            print(f"{Fore.GREEN}Display:{Style.RESET_ALL} {decoded_text}")
        else:
            print(f"{Fore.RED}❌ Failed to decode{Style.RESET_ALL}")
    
    print(f"\n{Fore.CYAN}{'=' * 70}{Style.RESET_ALL}")


def list_encodings():
    """Display supported encodings and their SMPP data_coding values."""
    print(f"{Fore.CYAN}{Style.BRIGHT}Supported Encodings{Style.RESET_ALL}")
    print("=" * 50)
    
    for encoding, data_coding in [('gsm', 0x00), ('ascii', 0x01), ('utf8', 0x02), ('latin1', 0x03), ('ucs2', 0x08)]:
        description = DATA_CODING_MAP.get(data_coding, "Unknown")
        print(f"{Fore.WHITE}{encoding.upper():8s}{Style.RESET_ALL} (0x{data_coding:02X}) - {description}")
    
    print(f"\n{Fore.YELLOW}Usage examples:{Style.RESET_ALL}")
    print('  sms_decoder.py "48656C6C6F" --encoding gsm')
    print('  sms_decoder.py "48656C6C6F" --data-coding 0x00')
    print('  sms_decoder.py "48656C6C6F"  # Auto-detect')


def main():
    args = parse_arguments()
    
    if args.list_encodings:
        list_encodings()
        return
    
    if not args.hexstring:
        print(f"{Fore.RED}❌ Error: Hexadecimal string is required{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}💡 Use --help for usage information{Style.RESET_ALL}")
        sys.exit(1)
    
    try:
        # Convert hex string to bytes
        raw_bytes = hex_to_bytes(args.hexstring)
        
        
        # Determine encoding method
        if args.all:
            # Try all encodings and display results for each
            all_results = try_all_encodings(raw_bytes)
            display_all_results(args.hexstring, raw_bytes, all_results)
            
        elif args.data_coding is not None:
            # Use specific SMPP data_coding value
            decoded_text = decode_sms_message(raw_bytes, args.data_coding)
            encoding_used = None  # Will be determined from data_coding for display
            
            # Map data_coding back to encoding name for display
            reverse_map = {0x00: 'gsm', 0x01: 'ascii', 0x02: 'utf8', 0x03: 'latin1', 0x08: 'ucs2'}
            encoding_used = reverse_map.get(args.data_coding, f'unknown_0x{args.data_coding:02X}')
            
            # Display results
            display_results(args.hexstring, raw_bytes, encoding_used, decoded_text)
            
        elif args.encoding:
            # Use specific encoding
            decoded_text, success = try_decode_with_encoding(raw_bytes, args.encoding)
            if not success:
                print(f"{Fore.RED}❌ Failed to decode with {args.encoding.upper()} encoding{Style.RESET_ALL}")
                sys.exit(1)
            encoding_used = args.encoding
            
            # Display results
            display_results(args.hexstring, raw_bytes, encoding_used, decoded_text)
            
        else:
            # Auto-detect encoding
            encoding_used, decoded_text = auto_detect_encoding(raw_bytes)
            if not encoding_used:
                print(f"{Fore.RED}❌ Could not decode message with any supported encoding{Style.RESET_ALL}")
                sys.exit(1)
            
            # Display results
            display_results(args.hexstring, raw_bytes, encoding_used, decoded_text)
        
    except ValueError as e:
        print(f"{Fore.RED}❌ Error: {e}{Style.RESET_ALL}")
        sys.exit(1)
    except Exception as e:
        print(f"{Fore.RED}❌ Unexpected error: {e}{Style.RESET_ALL}")
        sys.exit(1)


if __name__ == "__main__":
    main()
