import click

import countdowner.main as m


@click.command(short_help="Get the current prices of your watchlist products")
@click.option('-k', '--key', default=None,
    help="Mailgun API key")
@click.option('-h', '--as_html', is_flag=True, default=True,
    help="Send the optional email as HTML if true; otherwise send it as text")
@click.argument('watchlist_path')
@click.argument('out_dir')
def countdownit(watchlist_path, out_dir, key=None, as_html=True):
    """
    Read a YAML watchlist located at ``--watchlist_path``, collect all the product information from Countdown, and write the result to a CSV located in the directory ``--out_dir``, creating the directory if it does not exist.
    If ``--key`` (Mailgun API key) is given, then email the products on sale (if there are any) to the email address listed in the watchlist.
    """
    m.run_pipeline(watchlist_path, out_dir, key=key, as_html=as_html)