import datetime as dt
from collections import OrderedDict
from pathlib import Path
import os
import json
import io
import re

import yaml
import requests
import grequests
from bs4 import BeautifulSoup
import pandas as pd


ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WATCHLIST_FIELDS = [
  'name',
  'email_address',
  'products',
]
EMAIL_PATTERN = re.compile(r'[^@]+@[^@]+\.[^@]+')

# ---------------------
# Watchlist functions
# ---------------------
def parse_df(csv_text, **kwargs):
    """
    Given a CSV text with a header, convert it to a data frame and
    return the result.
    """
    csv = io.StringIO(csv_text)
    return pd.read_table(csv, sep=',', **kwargs)

def parse_watchlist(watchlist_yaml):
    """
    Given a (decoded) YAML dictionary representing a fare structure
    convert the CSV text fields to data frames and return the resulting
    dictionary.
    If keys are missing from the dictionary, add them and set their values
    to ``None`` to aid format checking in :func:`check_fare_structure`.
    If the YAML dict comes from a file located at the path
    ``yaml_path``, then use that path to fill in the fare structure name
    (if missing) and make absolute the fare structure zones path (if given).
    """
    w = {}

    # Set all missing keys to None
    for key in WATCHLIST_FIELDS:
        if key in watchlist_yaml:
            w[key] = watchlist_yaml[key]
        else:
            w[key] = None

    if w['products'] is not None:
        w['products'] = parse_df(w['products'], dtype={'stock_code': str})

    return w

def valid_email(x):
    """
    Return ``True`` if ``x`` is a valid email address;
    otherwise return ``False``.
    """
    if isinstance(x, str) and re.match(EMAIL_PATTERN, x):
        return True
    else:
        return False

def check_watchlist(watchlist):
    """
    Raise an error if the given watchlist (dictionary) is invalid.
    """
    w = watchlist
    if not isinstance(w['name'], str) or not len(w['name']):
        raise ValueError('Name must be a nonempty string')

    if not valid_email(w['email_address']):
        raise ValueError('Invalid email address')

    p = w['products']
    if p is None:
        raise ValueError('Products must be given')
    if not set(['description', 'stock_code']) <= set(p.columns):
        raise ValueError(
          'Products must have "description" and "stock_code" fields')

def read_watchlist(path):
    """
    Read a YAML file of watchlist data at the given path,
    parse the file, check it, and return the resulting watchlist
    dictionary.
    The YAML file should have the following form::

        - name: Hello
        - email_address: a@b.com
        - products: |
            description,stock_code
            chips sis,267945
            bagels bro,285453

    """
    # Read
    path = Path(path)
    with path.open('r') as src:
        watchlist_yaml = yaml.load(src)

    # Parse
    watchlist = parse_watchlist(watchlist_yaml)

    # Check
    check_watchlist(watchlist)

    # Create
    return watchlist

# -------------------------
# Countdown API functions
# -------------------------
def get_product(stock_code, async=False):
    """
    Issue a GET request to Countdown at
    https://shop.countdown.co.nz/Shop/ProductDetails
    with the given stock code (string), and return the response.
    If ``async``, then return an unissued GET request for
    asynchronous queueing.
    """
    url = 'https://shop.countdown.co.nz/Shop/ProductDetails'
    if async:
        get = grequests.get
    else:
        get = requests.get
    return get(url, params={'stockcode': stock_code})

def price_to_float(price_string):
    """
    Convert a price string to a float.
    """
    return float(price_string.replace('$', ''))

def parse_product(response):
    """
    Given a response of the form output by :func:`get_product` or
    :func:`get_product_a`, parse it, and return the a dictionary
    with the following keys and their corresponding values.

    - ``'stock_code'``
    - ``'name'``
    - ``'description'``
    - ``'size'``
    - ``'sale_price'``
    - ``'price'``
    - ``'unit_price'``
    - ``'datetime'``: current datetime as a ``'%Y-%m-%dT%H:%M:%S'``
      string

    Use ``None`` values when the information is not found in the response.
    """
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
    d = OrderedDict([(key, None) for key in keys])

    # Get stock code from URL and set datetime
    d['stock_code'] = re.search(r'stockcode=(\w+)',
      response.url).group(1)
    d['datetime'] = dt.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

    # Handle bad product data
    if response.status_code != 200:
        return d

    soup = BeautifulSoup(response.text, 'lxml')

    if not soup.find('input', id='stockcode'):
        return d

    # Handle good product data
    d['name'] = soup.find('div', class_='product-title').h1.text.strip()
    d['description'] = soup.find('p', class_='product-description-text'
      ).text.strip() or None
    d['size'] = soup.find('span', class_='volume-size').text.strip() or None

    s1 = soup.find('span', class_='special-price')
    s2 = soup.find('span', class_='club-price-wrapper')
    s3 = soup.find('span', class_='price')
    if s1:
        d['sale_price'] = price_to_float(list(s1.stripped_strings)[0])
        t = soup.find('span', class_='was-price')
        d['price'] = price_to_float(list(t.stripped_strings)[0].replace(
          'was', ''))
    elif s2:
        d['sale_price'] = price_to_float(list(s2.stripped_strings)[0])
        t = soup.find('span', class_='grid-non-club-price')
        d['price'] = price_to_float(list(t.stripped_strings)[0].replace(
          'non club price', ''))
    elif s3:
        d['price'] = price_to_float(list(s3.stripped_strings)[0])

    if d['sale_price'] is not None:
        d['discount_percentage'] = 100*(1 - d['sale_price']/d['price'])
    else:
        d['discount_percentage'] = None

    d['unit_price'] = soup.find('div', class_='cup-price').string.strip(
      ) or None

    return d

def collect_products(stock_codes, async=True, as_df=True):
    """
    For each item in the given list of stock codes (list of strings),
    call :func:`get_product`, parse the responses,
    and return the results as a list of dictionaries.
    If ``async``, then issue the requests asynchronously.
    If ``as_df``, then return the result as a DataFrame
    with columns equal to the keys listed in :func:`parse_product`.
    """
    results = []
    responses = (get_product(code, async) for code in stock_codes)
    if async:
        responses = grequests.imap(responses)
    for response in responses:
        info = parse_product(response)
        results.append(info)

    if as_df:
        results = pd.DataFrame(results)
        if not results.empty:
            results['datetime'] = pd.to_datetime(results['datetime'])

    return results

# -------------------------
# Data pipeline functions
# -------------------------
def filter_sales(products):
    """
    Given a DataFrame of products of the form returned by
    :func:`collect_products`, keep only the items on sale and the
    columns ``['name', 'sale_price', 'price', 'discount']``.
    """
    cols = ['name', 'sale_price', 'price', 'discount_percentage']
    return products.loc[products['sale_price'].notnull(), cols].copy()

def get_secret(key, secrets_path=ROOT/'secrets.json'):
    """
    Open the JSON file at ``secrets_path``, and return the value
    corresponding to the given key.
    """
    secrets_path = Path(secrets_path)
    with secrets_path.open() as src:
        secrets = json.load(src)
    return secrets[key]

def email(products, email_address, mailgun_domain, mailgun_key, as_html=True):
    """
    Email the given product DataFrame to the given email address
    using Mailgun with the given domain and API key.
    If ``as_html``, then write the email body as HTML;
    otherwise, write it as text.
    """

    url = 'https://api.mailgun.net/v3/{!s}/messages'.format(mailgun_domain)
    auth = ('api', mailgun_key)
    subject = '{!s} sales on your Countdown watchlist'.format(
      products.shape[0])
    data = {
        'from': 'Countdowner <hello@countdowner.io>',
        'to': email_address,
        'subject': subject,
    }
    if as_html:
        data['html'] = products.to_html(index=False, float_format='%.2f')
    else:
        data['text'] = products.to_string(index=False, float_format='%.2f')

    return requests.post(url, auth=auth, data=data)

def run_pipeline(watchlist_path, out_dir, mailgun_domain=None,
  mailgun_key=None, as_html=True, async=True):
    """
    Read a YAML watchlist located at ``watchlist_path``
    (string or Path object), one that :func:`read_watchlist` can read,
    collect all the product information from Countdown
    (asynchronously if ``async``), and write the result to a CSV
    located in the directory ``out_dir`` (string or Path object),
    creating the directory if it does not exist.
    If ``mailgun_domain`` (string) and ``mailgun_key`` are given,
    then send an email with the possibly empty list of products
    on sale using :func:`email`.
    """
    # Read products
    watchlist_path = Path(watchlist_path)
    w = read_watchlist(watchlist_path)

    # Collect updates
    codes = w['products']['stock_code']
    f = collect_products(codes, async)

    # Write product updates
    out_dir = Path(out_dir)
    if not out_dir.exists():
        out_dir.mkdir(parents=True)

    t = dt.datetime.now()
    path = out_dir/'{!s}_prices_{:%Y-%m-%dT%H:%M}'.format(w['name'], t)
    f.to_csv(str(path), index=False)

    # Filter sale items
    g = filter_sales(f)
    if mailgun_domain is not None and mailgun_key is not None:
        email(g, w['email_address'], mailgun_domain, mailgun_key,
          as_html=as_html)
