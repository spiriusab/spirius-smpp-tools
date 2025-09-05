#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SMS Encoder - Encode text messages to hexadecimal format using various encodings.
Shows the resulting hexstring and SMPP data_coding value for use in SMPP PDUs.
"""

import argparse
import sys
from colorama import Fore, Style, init

# Import common SMPP functionality
sys.path.append('..')
from common.smpp_common import encode_sms_message

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

ENCODING_TO_DATA_CODING = {
    'gsm': 0x00,
    'ascii': 0x01,
    'utf8': 0x02,
    'latin1': 0x03,
    'ucs2': 0x08
}


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='SMS Encoder - Encode text messages to hexadecimal format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "Hello World"                         # Auto-select encoding (GSM 7-bit preferred)
  %(prog)s "Hello World" --encoding gsm          # Force GSM 7-bit encoding
  %(prog)s "Hello 世界" --encoding utf8          # Force UTF-8 for Unicode
  %(prog)s "Hello World" --encoding ucs2         # Force UCS2/UTF-16BE
  %(prog)s --list-encodings                      # Show supported encodings

Supported encodings:
  gsm, ascii, utf8, latin1, ucs2
  
The tool will show:
  - Encoded hexstring
  - SMPP data_coding value for PDU
  - Encoding method used
  - Message length information
        """
    )
    
    parser.add_argument('text', nargs='?', help='Text message to encode')
    parser.add_argument('-e', '--encoding', choices=['gsm', 'ascii', 'utf8', 'latin1', 'ucs2'], 
                       help='Encoding method (default: auto-select)')
    parser.add_argument('-l', '--list-encodings', action='store_true', 
                       help='List supported encodings and exit')
    parser.add_argument('-v', '--verbose', action='store_true', 
                       help='Show detailed encoding information')
    
    return parser.parse_args()


def try_encode_with_encoding(text, encoding_name, verbose=False):
    """Try to encode text with specific encoding."""
    data_coding = ENCODING_TO_DATA_CODING[encoding_name]
    
    if verbose:
        print(f"{Fore.YELLOW}🔍 Trying {encoding_name.upper()} (data_coding=0x{data_coding:02X}){Style.RESET_ALL}")
    
    try:
        encoded_bytes = encode_sms_message(text, data_coding)
        if verbose:
            print(f"{Fore.GREEN}✅ Success with {encoding_name.upper()}{Style.RESET_ALL}")
        return encoded_bytes, True
    except Exception as e:
        if verbose:
            print(f"{Fore.RED}❌ Failed with {encoding_name.upper()}: {e}{Style.RESET_ALL}")
        return None, False


def auto_select_encoding(text, verbose=False):
    """Auto-select the best encoding for the text."""
    if verbose:
        print(f"{Fore.CYAN}🔍 Auto-selecting encoding...{Style.RESET_ALL}")
    
    # Try encodings in order of preference (most compact first)
    encodings_to_try = ['gsm', 'ascii', 'latin1', 'utf8', 'ucs2']
    
    for encoding in encodings_to_try:
        encoded_bytes, success = try_encode_with_encoding(text, encoding, verbose)
        if success:
            return encoding, encoded_bytes
    
    # Fallback to UTF-8 if nothing else works
    return 'utf8', text.encode('utf-8')


def get_message_limits(encoding_name):
    """Get SMS message length limits for encoding."""
    limits = {
        'gsm': {'single': 160, 'concat': 153},
        'ascii': {'single': 160, 'concat': 153}, 
        'utf8': {'single': 140, 'concat': 134},
        'latin1': {'single': 140, 'concat': 134},
        'ucs2': {'single': 70, 'concat': 67}
    }
    return limits.get(encoding_name, {'single': 140, 'concat': 134})


def display_results(text, encoding_used, encoded_bytes, verbose=False):
    """Display encoding results in a formatted way."""
    data_coding = ENCODING_TO_DATA_CODING[encoding_used]
    encoding_desc = DATA_CODING_MAP.get(data_coding, f"Unknown (0x{data_coding:02X})")
    hex_string = encoded_bytes.hex().upper()
    limits = get_message_limits(encoding_used)
    
    print(f"{Fore.CYAN}{Style.BRIGHT}SMS Encoder Results{Style.RESET_ALL}")
    print("=" * 50)
    
    print(f"{Fore.WHITE}Input text:{Style.RESET_ALL} {repr(text)}")
    print(f"{Fore.WHITE}Display:{Style.RESET_ALL} {text}")
    print(f"{Fore.WHITE}Length:{Style.RESET_ALL} {len(text)} characters")
    
    print(f"\n{Fore.GREEN}Encoding:{Style.RESET_ALL} {encoding_used.upper()}")
    print(f"{Fore.WHITE}Description:{Style.RESET_ALL} {encoding_desc}")
    print(f"{Fore.WHITE}SMPP data_coding:{Style.RESET_ALL} 0x{data_coding:02X} ({data_coding})")
    
    print(f"\n{Fore.WHITE}Encoded bytes:{Style.RESET_ALL} {encoded_bytes}")
    print(f"{Fore.GREEN}{Style.BRIGHT}Hexstring:{Style.RESET_ALL} {Style.BRIGHT}{hex_string}{Style.RESET_ALL}")

    # SMS length analysis
    print("")
    char_count = len(text)
    if char_count <= limits['single']:
        print(f"{Fore.WHITE}SMS type:{Style.RESET_ALL} Single SMS (fits in one message)")
    else:
        parts_needed = (char_count + limits['concat'] - 1) // limits['concat']
        print(f"{Fore.YELLOW}SMS type:{Style.RESET_ALL} Concatenated SMS ({parts_needed} parts needed)")
    
    print(f"{Fore.WHITE}Limits:{Style.RESET_ALL} {limits['single']} chars (single), {limits['concat']} chars (concat)")
    print("=" * 50)
    
    if verbose and len(encoded_bytes) <= 50:
        print(f"\n{Fore.YELLOW}Byte-by-byte breakdown:{Style.RESET_ALL}")
        for i, byte_val in enumerate(encoded_bytes):
            char = text[i] if i < len(text) else '?'
            print(f"  {i:2d}: 0x{byte_val:02X} ({byte_val:3d}) <- '{char}'")


def list_encodings():
    """Display supported encodings and their SMPP data_coding values."""
    print(f"{Fore.CYAN}{Style.BRIGHT}Supported Encodings{Style.RESET_ALL}")
    print("=" * 50)
    
    for encoding, data_coding in ENCODING_TO_DATA_CODING.items():
        description = DATA_CODING_MAP.get(data_coding, "Unknown")
        limits = get_message_limits(encoding)
        print(f"{Fore.WHITE}{encoding.upper():8s}{Style.RESET_ALL} (0x{data_coding:02X}) - {description}")
        print(f"         Limits: {limits['single']} chars (single), {limits['concat']} chars (concat)")
        print()
    
    print(f"{Fore.YELLOW}Usage examples:{Style.RESET_ALL}")
    print('  sms_encoder.py "Hello World" --encoding gsm')
    print('  sms_encoder.py "Hello 世界" --encoding utf8')
    print('  sms_encoder.py "Test message"  # Auto-select encoding')


def main():
    args = parse_arguments()
    
    if args.list_encodings:
        list_encodings()
        return
    
    if not args.text:
        print(f"{Fore.RED}❌ Error: Text message is required{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}💡 Use --help for usage information{Style.RESET_ALL}")
        sys.exit(1)
    
    try:
        if args.verbose:
            print(f"{Fore.CYAN}Input processing:{Style.RESET_ALL}")
            print(f"  Text: {repr(args.text)}")
            print(f"  Length: {len(args.text)} characters")
            print()
        
        # Determine encoding method
        if args.encoding:
            # Use specific encoding
            encoded_bytes, success = try_encode_with_encoding(args.text, args.encoding, args.verbose)
            if not success:
                print(f"{Fore.RED}❌ Failed to encode with {args.encoding.upper()} encoding{Style.RESET_ALL}")
                sys.exit(1)
            encoding_used = args.encoding
        else:
            # Auto-select encoding
            encoding_used, encoded_bytes = auto_select_encoding(args.text, args.verbose)
        
        # Display results
        display_results(args.text, encoding_used, encoded_bytes, args.verbose)
        
    except Exception as e:
        print(f"{Fore.RED}❌ Unexpected error: {e}{Style.RESET_ALL}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
