import tempfile

from click.testing import CliRunner
import responses

from .context import countdowner, DATA_DIR
from countdowner import *
from countdowner.cli import *


runner = CliRunner()

@responses.activate
def test_countdownit():
    # Create mock GET response
    responses.add(responses.GET,
      'https://shop.countdown.co.nz/Shop/ProductDetails',
      status=200, body='junk', content_type='text/xml')

    # Create mock POST response
    domain = 'fake'
    responses.add(responses.POST,
      'https://api.mailgun.net/v3/{!s}/messages'.format(domain),
      status=200, body='junk', content_type='application/json')

    w_path = DATA_DIR/'watchlist.yaml'
    with tempfile.TemporaryDirectory() as tmp:
        result = runner.invoke(countdownit,
          [str(w_path), tmp, '-d', domain, '-k', 'api'])
        assert result.exit_code == 0
