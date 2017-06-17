import tempfile

import requests
import grequests
import responses
import pandas as pd

from .context import countdowner, DATA_DIR
from countdowner import *


def test_read_watchlist():
    w = read_watchlist(DATA_DIR/'watchlist.yaml')
    assert isinstance(w, dict)
    expect_keys = {'products', 'email_addresses', 'name'}
    assert set(w.keys()) == expect_keys
    assert isinstance(w['products'], pd.DataFrame)

@responses.activate
def test_get_product():
    # Create mock GET response
    responses.add(responses.GET,
      'https://shop.countdown.co.nz/Shop/ProductDetails',
      status=200, body='junk', content_type='text/xml')

    r = get_product('hello')
    assert isinstance(r, requests.models.Response)

    r = get_product('hello', async=True)
    assert isinstance(r, grequests.AsyncRequest)

def test_parse_product():
    r = requests.models.Response()
    setattr(r, 'url',
      'https://shop.countdown.co.nz/Shop/ProductDetails?stockcode=bingo')
    p = parse_product(r)
    assert isinstance(p, dict)
    keys = [
        'stock_code',
        'name',
        'description',
        'size',
        'sale_price',
        'price',
        'discount_percentage',
        'unit_price',
        'datetime',
    ]
    assert set(p.keys()) == set(keys)
    assert p['stock_code'] == 'bingo'

@responses.activate
def test_collect_products():
    # Create mock GET response
    responses.add(responses.GET,
      'https://shop.countdown.co.nz/Shop/ProductDetails',
      status=200, body='junk', content_type='text/xml')

    f = collect_products(['bingo', '260803'])
    assert isinstance(f, pd.DataFrame)
    assert f.shape == (2, 9)

def test_filter_sales():
    f = pd.DataFrame([['a', 2, 3, 20.1]],
      columns=['name', 'sale_price', 'price', 'discount_percentage'])
    g = filter_sales(f)
    assert isinstance(g, pd.DataFrame)
    assert g.to_dict() == f.to_dict()

    f = pd.DataFrame([['a', None, 3, 20.1]],
      columns=['name', 'sale_price', 'price', 'discount_percentage'])
    g = filter_sales(f)
    assert isinstance(g, pd.DataFrame)
    assert g.empty

@responses.activate
def test_email():
    # Create mock POST response
    domain = 'fake'
    responses.add(responses.POST,
      'https://api.mailgun.net/v3/{!s}/messages'.format(domain),
      status=200, body='junk', content_type='application/json')

    products = pd.DataFrame([['a', 2, 3, 20.1]],
      columns=['name', 'sale_price', 'price', 'discount_percentage'])
    r = email(products, ['a@b.com'], domain, 'fake')
    assert r.status_code == 200

@responses.activate
def test_run_pipeline():
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
        run_pipeline(w_path, tmp, domain, 'api_key')
        # Should write a file
        file_list = list(Path(tmp).iterdir())
        assert len(file_list) == 1
        # File should be a CSV
        f = pd.read_csv(file_list[0])
        assert isinstance(f, pd.DataFrame)
        # File should contain all the products in the watchlist
        w = read_watchlist(w_path)
        assert set(w['products']['stock_code'].values) ==\
          set(f['stock_code'].values)
