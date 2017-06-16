import tempfile

from click.testing import CliRunner

from .context import countdowner, DATA_DIR, is_connected
from countdowner import *
from countdowner.cli import *


runner = CliRunner()

def test_countdownit():
    w_path = DATA_DIR/'watchlist.yaml'
    with tempfile.TemporaryDirectory() as tmp:
        result = runner.invoke(countdownit, [str(w_path), tmp])
        assert result.exit_code == 0
