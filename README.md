# SMPPTools

A collection of tools for testing the SMPP (Short Message Peer-to-Peer) protocol towards Spirius SMSCs.

This project is provided by Spirius to showcase the SMPP protocol integration as a means to get started and to help with integration testing. It is not intended for production use. 

## Tools included

- smpp_sender: A command-line tool for sending SMS messages using the SMPP protocol.
- smpp_receiver: A command-line tool for receiving SMS messages using the SMPP protocol.

## Prerequisites

- Python 3.12 or higher
- Poetry 1.8.0 or higher
- Credentials from Spirus, contact your Spirius representative for access

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

### Usage

```bash
python tools/smpp_sender.py [OPTIONS]
```

### Options

- `-s, --ssl`: Use SSL/TLS connection (default: plain TCP)
- `-i, --interactive`: Interactive mode - prompt for username, password, and destination
- `-h, --help`: Show help message

### Configuration

The tool uses environment variables for configuration. Copy `.env.example` to `.env` and configure the variables.

### Examples

**Interactive mode (prompts for credentials):**
```bash
python tools/smpp_sender.py -i     # plain TCP
python tools/smpp_sender.py -i -s  # with SSL/TLS
```

**Non-interactive mode (uses .env values):**
```bash
python tools/smpp_sender.py        # plain TCP
python tools/smpp_sender.py -s     # with SSL/TLS
```

## smpp_receiver

A command-line tool for receiving SMS messages using the SMPP protocol. Supports both plain TCP and SSL/TLS connections with interactive and non-interactive modes. Has a send-receive mode to test end-to-end MO SMS functionality.

### Usage

```bash
python tools/smpp_receiver.py [OPTIONS]
```

### Options

- `-s, --ssl`: Use SSL/TLS connection (default: plain TCP)
- `-i, --interactive`: Interactive mode - prompt for username, password, and destination
- `-m, --mode`: Operation mode (default: send-receive)
  - `send-receive`: Send a test message and wait for MO messages and delivery reports
  - `receive-only`: Only listen for incoming MO messages (no test message sent)
- `-t, --text`: Custom message text for test message (default: auto-generated)
- `-d, --debug`: Enable debug logging with detailed sequence information
- `-h, --help`: Show help message

### Configuration

The tool uses environment variables for configuration. Copy `.env.example` to `.env` and configure the variables.

### Examples

**Send-receive mode (default - tests end-to-end MO functionality):**
```bash
python tools/smpp_receiver.py -m send-receive  # Send test message and wait for MO/DLR
python tools/smpp_receiver.py                  # Same as above (default mode)
```

**Receive-only mode (listen for real MO messages):**
```bash
python tools/smpp_receiver.py -m receive-only  # Only listen, no test message sent
```

**Custom test message:**
```bash
python tools/smpp_receiver.py -t "Custom test message"
```

**Debug mode (shows sequence numbers and detailed info):**
```bash
python tools/smpp_receiver.py -d
```
