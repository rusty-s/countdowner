import os
import sys
from pathlib import Path
import socket

sys.path.insert(0, os.path.abspath('..'))

import countdowner


DATA_DIR = Path('tests/data')

# Check if we have a network connection
def is_connected():
    try:
        socket.create_connection(("www.google.com", 80))
        return True
    except OSError:
        return False
