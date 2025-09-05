#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Common SMPP functionality shared between sender and receiver tools.
"""

import os
import ssl
import socket
import sys
from dotenv import load_dotenv
from colorama import Fore, Style, init
import smpplib.gsm
import re

# Initialize colorama for cross-platform colored output
init(autoreset=True)

# SMPP credential validation constants
SMPP_USERNAME_MIN_LENGTH = 1
SMPP_USERNAME_MAX_LENGTH = 16
SMPP_PASSWORD_MIN_LENGTH = 1
SMPP_PASSWORD_MAX_LENGTH = 9


def find_project_root():
    """Find the project root directory by looking for pyproject.toml."""
    current_dir = os.path.abspath(os.path.dirname(__file__))
    
    # Walk up the directory tree looking for pyproject.toml
    while current_dir != os.path.dirname(current_dir):  # Stop at filesystem root
        if os.path.exists(os.path.join(current_dir, 'pyproject.toml')):
            return current_dir
        current_dir = os.path.dirname(current_dir)
    
    # If not found, use the parent of the common directory as fallback
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env_file(env_file_name):
    """Load environment variables from common file and specified file in project root."""
    project_root = find_project_root()
    
    # First load common environment variables (required)
    common_env_path = os.path.join(project_root, '.env.common')
    if not os.path.exists(common_env_path):
        print(f"{Fore.RED}❌ Error: Common configuration file '.env.common' not found{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}💡 Please copy '.env.common.example' to '.env.common' and configure your settings{Style.RESET_ALL}")
        sys.exit(1)
    
    load_dotenv(common_env_path)
    
    # Then load specific environment variables (these can override common ones)
    env_file_path = os.path.join(project_root, env_file_name)
    if not os.path.exists(env_file_path):
        print(f"{Fore.RED}❌ Error: Configuration file '{env_file_name}' not found{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}💡 Please copy '{env_file_name}.example' to '{env_file_name}' and configure your settings{Style.RESET_ALL}")
        sys.exit(1)
    
    load_dotenv(env_file_path)
    return True


def get_smsc_servers():
    """Get SMSC server configuration from environment."""
    return {
        'SMSC_1': os.getenv('SMSC_1'),
        'SMSC_2': os.getenv('SMSC_2')
    }


def get_connection_config():
    """Get connection configuration from environment."""
    plain_port = os.getenv('SMPP_PLAIN_PORT')
    ssl_port = os.getenv('SMPP_SSL_PORT')
    
    if not plain_port:
        print(f"{Fore.RED}❌ Error: SMPP_PLAIN_PORT not set in environment{Style.RESET_ALL}")
        sys.exit(1)
    if not ssl_port:
        print(f"{Fore.RED}❌ Error: SMPP_SSL_PORT not set in environment{Style.RESET_ALL}")
        sys.exit(1)
        
    return {
        'plain_port': int(plain_port),
        'ssl_port': int(ssl_port)
    }


def validate_smpp_username(username):
    """Validate SMPP username with length and format checks."""
    if not username:
        raise ValueError("SMPP username cannot be empty")
    
    # Length validation
    if len(username) < SMPP_USERNAME_MIN_LENGTH:
        raise ValueError(f"SMPP username must be at least {SMPP_USERNAME_MIN_LENGTH} character(s) long")
    if len(username) > SMPP_USERNAME_MAX_LENGTH:
        raise ValueError(f"SMPP username cannot exceed {SMPP_USERNAME_MAX_LENGTH} characters")
    
    # Format validation - printable ASCII characters only (no control characters)
    if not re.match(r'^[\x21-\x7E]+$', username):
        raise ValueError("SMPP username must contain only printable ASCII characters (no spaces or control characters)")


def validate_smpp_password(password):
    """Validate SMPP password with length and format checks."""
    if not password:
        raise ValueError("SMPP password cannot be empty")
    
    # Length validation
    if len(password) < SMPP_PASSWORD_MIN_LENGTH:
        raise ValueError(f"SMPP password must be at least {SMPP_PASSWORD_MIN_LENGTH} character(s) long")
    if len(password) > SMPP_PASSWORD_MAX_LENGTH:
        raise ValueError(f"SMPP password cannot exceed {SMPP_PASSWORD_MAX_LENGTH} characters")
    
    # Format validation - printable ASCII characters only (no control characters)
    if not re.match(r'^[\x21-\x7E]+$', password):
        raise ValueError("SMPP password must contain only printable ASCII characters (no spaces or control characters)")


def get_smpp_params():
    """Get SMPP parameters from environment with validation and auto-derived TON/NPI."""
    # Get values from environment
    source_address = os.getenv('SOURCE_ADDRESS')
    username = os.getenv('SMPP_USERNAME')
    password = os.getenv('SMPP_PASSWORD')
    dest_address = os.getenv('DEST_ADDRESS')
    
    # Validate required SMPP credentials
    if not username:
        raise ValueError("SMPP_USERNAME is required in environment")
    if not password:
        raise ValueError("SMPP_PASSWORD is required in environment")
    
    # Validate SMPP credentials format and length
    validate_smpp_username(username)
    validate_smpp_password(password)
    
    # Validate and auto-derive SOURCE_TON/NPI from address format
    source_ton, source_npi = None, None
    if source_address:
        # Validate source address format
        validate_source_address(source_address)
        # Auto-derive TON/NPI values
        source_ton, source_npi = get_source_ton_npi(source_address)
    
    # Validate destination address if present
    if dest_address:
        validate_e164_address(dest_address)
    
    return {
        'source_ton': source_ton,
        'source_npi': source_npi,
        'source_address': source_address,
        'username': username,
        'password': password,
        'dest_address': dest_address
    }


def validate_e164_address(address):
    """Validate that address is in E.164 format without + prefix. Throws ValueError if invalid."""
    if not address:
        raise ValueError("Address cannot be empty")
    
    # E.164 format: digits only, 7-15 characters, no + prefix
    if not re.match(r'^[1-9]\d{6,14}$', address):
        raise ValueError("Address must be in E.164 format (7-15 digits, no + prefix, cannot start with 0)")


def is_valid_e164_address(address):
    """Check if address is in valid E.164 format without + prefix."""
    if not address:
        return False
    
    # E.164 format: digits only, 7-15 characters, no + prefix, cannot start with 0
    return bool(re.match(r'^[1-9]\d{6,14}$', address))


def is_valid_alphanumeric_address(address):
    """
    Check if a string contains only alphanumeric characters including Nordic/Scandinavian letters.
    Allows: a-z, A-Z, 0-9, åäöÅÄÖ, æøåÆØÅ and other accented characters used in Nordic languages.
    """
    if not address:
        return False
    
    # Check length (typically 1-11 characters for alphanumeric sender IDs)
    if len(address) > 11:
        return False
    
    # Define pattern for allowed characters
    allowed_pattern = r'^[a-zA-Z0-9åäöÅÄÖæøÆØ ._&-]+$'
    if not re.match(allowed_pattern, address):
        return False
    
    # Disallow leading/trailing spaces
    if address != address.strip():
        return False
    
    return True


def validate_source_address(address):
    """
    Validate source address - supports both E.164 international and alphanumeric formats.
    Throws ValueError if invalid, returns silently if valid.
    """
    if not address:
        raise ValueError("Source address cannot be empty")
    
    # Try E.164 format first
    if is_valid_e164_address(address):
        return
    
    # Try alphanumeric format
    if is_valid_alphanumeric_address(address):
        return
    
    # Neither format is valid
    raise ValueError("Source address must be either E.164 international format (7-15 digits, no + prefix, cannot start with 0) or alphanumeric format (max 11 chars, letters/numbers/Nordic chars/space/._&-)")


def get_source_address_format(address):
    """Determine the format of a source address."""
    if is_valid_e164_address(address):
        return "e164"
    elif is_valid_alphanumeric_address(address):
        return "alphanumeric"
    else:
        raise ValueError("Invalid source address format")


def get_source_ton_npi(address):
    """
    Auto-derive SOURCE_TON and SOURCE_NPI values based on address format.
    Returns (ton, npi) tuple.
    """
    validate_source_address(address)  # Throws if invalid
    
    format_type = get_source_address_format(address)
    
    if format_type == "e164":
        return 0x01, 0x01  # International, ISDN/E.164
    elif format_type == "alphanumeric":
        return 0x05, 0x00  # Alphanumeric, Unknown numbering plan
    else:
        raise ValueError(f"Unknown address format: {format_type}")


def test_ssl_connection(host, port):
    """Test SSL/TLS connection to SMSC."""
    try:
        print(f"{Fore.WHITE}🔐 Testing SSL/TLS connection...{Style.RESET_ALL}")
        
        # Create SSL context for SSL/TLS connection
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Test SSL/TLS handshake
        test_sock = socket.create_connection((host, port), timeout=10)
        ssl_test_sock = ssl_context.wrap_socket(test_sock, server_hostname=host)
        ssl_test_sock.close()
        print(f"{Fore.GREEN}✅ SSL/TLS connection successful{Style.RESET_ALL}")
        return ssl_context
        
    except ssl.SSLError as e:
        print(f"{Fore.RED}❌ SSL/TLS connection failed: {e}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}💡 Use plain TCP connection (without -s/--ssl flag) if SSL/TLS is not supported.{Style.RESET_ALL}")
        sys.exit(1)
        
    except Exception as e:
        print(f"{Fore.RED}❌ Connection test failed: {e}{Style.RESET_ALL}")
        raise


def validate_required_params(params, required_fields):
    """Validate that required parameters are set."""
    missing = []
    for field in required_fields:
        if not params.get(field):
            missing.append(field)
    
    if missing:
        for field in missing:
            print(f"{Fore.RED}❌ Error: {field.upper()} not set in environment{Style.RESET_ALL}")
        sys.exit(1)


def print_connection_info(server_choice, host, port, use_ssl):
    """Print connection information."""
    connection_type = 'SSL/TLS' if use_ssl else 'plain TCP'
    print(f"{Fore.WHITE}🔌 Connecting to {server_choice} ({host}:{port}) with {connection_type}{Style.RESET_ALL}")


def print_using_params(username, dest_addr):
    """Print parameters being used in non-interactive mode."""
    print(f"{Fore.CYAN}👤 Using username: {username}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}📱 Using destination: {dest_addr}{Style.RESET_ALL}")


def create_test_message(server_choice, username, use_ssl, custom_text=None):
    """Create a test message with connection details."""
    import time
    
    if custom_text:
        return custom_text
    
    return f"Testing SMPP\nServer: {server_choice}\nAccount: {username}\nSSL/TLS: {'YES' if use_ssl else 'NO'}\nTime: {time.strftime('%Y-%m-%d %H:%M:%S')}"


def encode_sms_message(message_text, data_coding=0x00):
    """Encode SMS message according to specified data_coding."""
    if data_coding == 0x00 or data_coding & 0xF0 == 0xF0:  # GSM 7-bit
        return smpplib.gsm.gsm_encode(message_text)
    elif data_coding == 0x01:  # ASCII
        return message_text.encode('ascii', errors='replace')
    elif data_coding == 0x02:  # 8-bit binary (UTF-8)
        return message_text.encode('utf-8')
    elif data_coding == 0x03:  # Latin-1
        return message_text.encode('iso-8859-1', errors='replace')
    elif data_coding == 0x08:  # UCS2 (UTF-16BE)
        return message_text.encode('utf-16be')
    else:
        # Default to GSM 7-bit for unknown encodings
        return smpplib.gsm.gsm_encode(message_text)


def gsm_decode(encoded_bytes):
    """Decode GSM 7-bit encoded bytes using the GSM character table.
    
    This function implements the missing GSM 7-bit decoding functionality
    that is not provided by smpplib.
    """
    if not isinstance(encoded_bytes, bytes):
        return str(encoded_bytes)
    
    result = []
    i = 0
    while i < len(encoded_bytes):
        byte_val = encoded_bytes[i]
        
        # Handle escape character for extended GSM character set
        if byte_val == 0x1B and i + 1 < len(encoded_bytes):
            # Extended character - add 0x80 to the next byte's index
            next_byte = encoded_bytes[i + 1]
            char_index = next_byte + 0x80
            i += 2  # Skip both bytes
        else:
            char_index = byte_val
            i += 1
        
        # Map byte value to GSM character
        if char_index < len(smpplib.gsm.GSM_CHARACTER_TABLE):
            result.append(smpplib.gsm.GSM_CHARACTER_TABLE[char_index])
        else:
            # Unknown character - use replacement
            result.append('?')
    
    return ''.join(result)


def decode_sms_message(raw_bytes, data_coding=0x00):
    """Decode SMS message using proper data_coding field from SMPP PDU."""
    if not isinstance(raw_bytes, bytes):
        return str(raw_bytes)
    
    try:
        if data_coding == 0x00:  # GSM 7-bit default alphabet
            return gsm_decode(raw_bytes)
        elif data_coding == 0x01:  # ASCII
            return raw_bytes.decode('ascii', errors='replace')
        elif data_coding == 0x02:  # 8-bit binary
            return raw_bytes.decode('utf-8', errors='replace')
        elif data_coding == 0x03:  # Latin-1 (ISO-8859-1)
            return raw_bytes.decode('iso-8859-1', errors='replace')
        elif data_coding == 0x08:  # UCS2 (Unicode)
            return raw_bytes.decode('utf-16be', errors='replace')
        elif data_coding & 0xF0 == 0xF0:  # Message class indicators with GSM 7-bit
            return gsm_decode(raw_bytes)
        else:
            # Unknown data_coding - fallback to GSM 7-bit
            return gsm_decode(raw_bytes)
    except Exception:
        # Final fallback - UTF-8 with error handling
        return raw_bytes.decode('utf-8', errors='replace')
