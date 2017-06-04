import tempfile

import requests
import grequests
import pandas as pd
import pytest

from .context import countdowner, DATA_DIR, is_connected
from countdowner import *


def build_mock_request(stock_code):
    r = requests.models.Response()
    setattr(r, 'url', 'https://shop.countdown.co.nz/Shop/ProductDetails?stockcode=' + stock_code)
    return r

def test_read_watchlist():
    w = read_watchlist(DATA_DIR/'watchlist.yaml')
    assert isinstance(w, dict)
    assert isinstance(w['products'], pd.DataFrame)

@pytest.mark.skipif(not is_connected(), reason="Requires an internet connection")
def test_get_product():
    r = get_product('hello')
    assert isinstance(r, requests.models.Response)

    r = get_product('hello', async=True)
    assert isinstance(r, grequests.AsyncRequest)

def test_parse_product():
    r = build_mock_request('bingo')
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

@pytest.mark.skipif(not is_connected(), reason="Requires an internet connection")
def test_collect_products():
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

@pytest.mark.skipif(not is_connected(), reason="Requires an internet connection")
def test_email():
    products = pd.DataFrame([['a', 2, 3, 20.1]],     
      columns=['name', 'sale_price', 'price', 'discount_percentage'])
    r = email(products, 'a@b.com', 'fake', 'fake')
    print(r)
    assert r.status_code == 401  # unauthorized error

@pytest.mark.skipif(not is_connected(), reason="Requires an internet connection")
def test_run_pipeline():
    w_path = DATA_DIR/'watchlist.yaml'
    with tempfile.TemporaryDirectory() as tmp:
        run_pipeline(w_path, tmp)
        # Should write a file
        file_list = list(Path(tmp).iterdir()) 
        assert len(file_list) == 1
        # File should be a CSV
        f = pd.read_csv(file_list[0])
        assert isinstance(f, pd.DataFrame)
        # File should contain all the products in the watchlist
        w = read_watchlist(w_path)
        assert set(w['products']['stock_code'].values) == set(f['stock_code'].values)