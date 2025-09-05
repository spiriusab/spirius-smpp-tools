# SMPPTools

A collection of tools for testing the SMPP (Short Message Peer-to-Peer) protocol towards Spirius SMSCs.

This project is provided by Spirius to showcase the SMPP protocol integration as a means to get started and to help with integration testing. It is not intended for production use. 

## Tools included

- smpp_sender: A command-line tool for sending SMS messages using the SMPP protocol.
- smpp_receiver: A command-line tool for receiving SMS messages using the SMPP protocol.
- sms_encoder: A command-line tool for encoding SMS messages using the SMPP protocol.
- sms_decoder: A command-line tool for decoding SMS messages using the SMPP protocol.

## Prerequisites

- Python 3.12 or higher
- Poetry 1.8.0 or higher
- Credentials from Spirius, contact your Spirius account manager for access

## Installation

This project uses [Poetry](https://python-poetry.org/) for dependency management. To set up the project:

   ```bash
   # Install Poetry
   curl -sSL https://install.python-poetry.org | python3 -

   # Clone repository
   git clone <repository-url>
   cd spirius-smpp-tools

   # Install dependencies
   poetry install

   # Activate virtual environment
   poetry shell
   ```

# Tools

## smpp_sender

A command-line tool for sending SMS messages using the SMPP protocol. Supports both plain TCP and SSL/TLS connections with interactive and non-interactive modes.

### Configuration

The tool uses environment variables for configuration. 
- Copy `.env.common.example` to `.env.common` and configure the variables.
- Copy `.env.sender.example` to `.env.sender` and configure the variables.

### Usage

```bash
# Plain TCP
./smpp_sender.py

# SSL/TLS
./smpp_sender.py -s

# Override destination and text with command line argument
./smpp_sender.py -d 46123456789 -t "Custom message"
```

## smpp_receiver

A command-line tool for receiving SMS messages using the SMPP protocol. Supports both plain TCP and SSL/TLS connections with interactive and non-interactive modes. Has a send-receive mode to test end-to-end MO SMS functionality.

### Configuration

The tool uses environment variables for configuration. 
- Copy `.env.common.example` to `.env.common` and configure the variables.
- Copy `.env.receiver.example` to `.env.receiver` and configure the variables.

### Usage

```bash
# Send-receive mode (default - tests end-to-end MO functionality)
./smpp_receiver.py                  # Defaults to 'send-receive' mode

# Receive-only mode (listen for MO messages and DLRs)
./smpp_receiver.py -m receive-only  # Only listen, no test message sent

# Verbose logging
./smpp_receiver.py -v
```

## sms_encoder

A command-line tool for encoding text messages to hexadecimal format using various SMPP encodings. Automatically selects the most efficient encoding and displays the corresponding SMPP data_coding value.

### Usage

```bash
./sms_encoder.py "Hello World"
./sms_encoder.py "Hello World" --encoding gsm
```

## sms_decoder

A command-line tool for decoding hexadecimal SMS message content captured from Wireshark or network analysis tools. Supports auto-detection and manual encoding specification.

### Usage

```bash
./sms_decoder.py "48656C6C6F20576F726C64"
./sms_decoder.py "48656C6C6F20576F726C64" --encoding gsm
./sms_decoder.py "48656C6C6F20576F726C64" --data-coding 0x00
./sms_decoder.py "48656C6C6F20576F726C64" --all
```
