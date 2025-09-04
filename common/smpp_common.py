#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Common SMPP functionality shared between sender and receiver tools.
"""

import os
import socket
import ssl
import sys
from dotenv import load_dotenv
from colorama import Fore, Style, init

# Initialize colorama for cross-platform colored output
init(autoreset=True)


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


def get_smpp_params():
    """Get SMPP parameters from environment."""
    source_ton = os.getenv('SOURCE_TON')
    source_npi = os.getenv('SOURCE_NPI')
    dest_ton = os.getenv('DEST_TON')
    dest_npi = os.getenv('DEST_NPI')
    
    return {
        'source_ton': int(source_ton, 0) if source_ton else None,
        'source_npi': int(source_npi, 0) if source_npi else None,
        'source_address': os.getenv('SOURCE_ADDRESS'),
        'dest_ton': int(dest_ton, 0) if dest_ton else None,
        'dest_npi': int(dest_npi, 0) if dest_npi else None,
        'username': os.getenv('SMPP_USERNAME'),
        'password': os.getenv('SMPP_PASSWORD'),
        'dest_address': os.getenv('DEST_ADDRESS')
    }


def get_receiver_params():
    """Get SMPP parameters for receiver (MO SMS) from environment."""
    source_ton = os.getenv('SOURCE_TON')
    source_npi = os.getenv('SOURCE_NPI')
    dest_ton = os.getenv('DEST_TON')
    dest_npi = os.getenv('DEST_NPI')
    
    return {
        'source_ton': int(source_ton, 0) if source_ton else None,
        'source_npi': int(source_npi, 0) if source_npi else None,
        'originating_phone_number': os.getenv('ORIGINATING_PHONE_NUMBER'),  # MO: phone sending SMS
        'dest_ton': int(dest_ton, 0) if dest_ton else None,
        'dest_npi': int(dest_npi, 0) if dest_npi else None,
        'username': os.getenv('SMPP_USERNAME'),
        'password': os.getenv('SMPP_PASSWORD'),
        'receiving_phone_number': os.getenv('RECEIVING_PHONE_NUMBER')  # MO: virtual number receiving SMS
    }


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
