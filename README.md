# SMPPTools

A collection of tools for testing the SMPP (Short Message Peer-to-Peer) protocol towards Spirius SMSCs.

## Overview

This project provides utilities for working with SMS messages using the SMPP protocol. It is designed to help with debugging, testing, and developing applications that work with SMS messaging.

Currently, the following tools are available:

- **smpp_sender** - Command line utility to send SMS messages using the SMPP protocol

## Prerequisites

- Python 3.12 or higher
- Poetry 1.8.0 or higher
- Credentials from Spirus, contact your Spirius representative for access

## Installation

This project uses [Poetry](https://python-poetry.org/) for dependency management. To set up the project:

1. Make sure you have Poetry installed:
   ```
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. Clone this repository and navigate to the project directory:
   ```
   git clone <repository-url>
   cd spirius-smpp-tools
   ```

3. Install dependencies using Poetry:
   ```
   poetry install
   ```

4. Activate the Poetry virtual environment:
   ```
   poetry shell
   ```

## Tools

### smpp_sender

Send SMS messages using the SMPP protocol.

// TODO: Add documentation here

## License

This project is provided by Spirius to showcase the SMPP protocol integration as a means to get started. It is not intended for production use. 
The components derived from open-source projects maintain their original licenses.
