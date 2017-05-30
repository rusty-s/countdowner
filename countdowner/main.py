import datetime as dt
from collections import OrderedDict
from pathlib import Path
import os
import json
import io 
import re 

import yaml
import requests
import pandas as pd
import numpy as np
import curio
import curio_http
from bs4 import BeautifulSoup


ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WATCHLIST_FIELDS = [
  'name',
  'email_address',
  'products',
]
EMAIL_PATTERN = re.compile(r'[^@]+@[^@]+\.[^@]+')

#---------------------
# Watchlist functions
#--------------------- 
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
    Return ``True`` if ``x`` is a valid email address; otherwise return ``False``.
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
        raise ValueError('Products must have "description" and "stock_code" fields')
   
def read_watchlist(path):
    """
    Read a YAML file of watchlist data at the given path, parse the file,
    check it, and return the resulting watchlist dictionary.
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

#-------------------------
# Countdown API functions
#-------------------------
def get_product(stock_code):
    """
    Issue a GET request to Countdown at https://shop.countdown.co.nz/Shop/ProductDetails with the given stock code (string).
    Return the text respones containing the details of the product with that stock code.
    Raise an error if the GET request fails.
    """
    url = 'https://shop.countdown.co.nz/Shop/ProductDetails'
    r = requests.get(url, params={'stockcode': stock_code})
    r.raise_for_status()
    return r.text

def price_to_float(price_string):
    """
    Convert a price string to a float.
    """
    return float(price_string.replace('$', ''))
              
def parse_product(html):
    """
    Given a response from the Countdown API, parse it, and return in as a dictionary with the keys and values:

    - ``'stock_code'``
    - ``'name'``
    - ``'description'``
    - ``'size'``
    - ``'on_sale'``
    - ``'sale_price'``
    - ``'price'``
    - ``'unit_price'``
    - ``'datetime'``
    """
    # Parse response
    d = OrderedDict()
    
    soup = BeautifulSoup(html, 'lxml')
    
    d['stock_code'] = soup.find('input', id='stockcode')['value']
    d['name'] = soup.find('div', class_='product-title').h1.text.strip()
    d['description']= soup.find('p', class_='product-description-text').text.strip() or None
    d['size'] = soup.find('span', class_='volume-size').text.strip() or None

    s1 = soup.find('span', class_='special-price')
    s2 = soup.find('span', class_='club-price-wrapper')
    s3 = soup.find('span', class_='price')
    if s1:
        d['on_sale'] = True
        d['sale_price'] = price_to_float(list(s1.stripped_strings)[0])
        t = soup.find('span', class_='was-price')
        d['price'] = price_to_float(list(t.stripped_strings)[0].replace('was', ''))
    elif s2:
        d['on_sale'] = True
        d['sale_price'] = price_to_float(list(s2.stripped_strings)[0])
        t = soup.find('span', class_='grid-non-club-price')
        d['price'] = price_to_float(list(t.stripped_strings)[0].replace('non club price', ''))
    elif s3:
        d['on_sale'] = False
        d['sale_price'] = None    
        d['price'] = price_to_float(list(s3.stripped_strings)[0])

    if d['on_sale']:
        d['discount_percentage'] = 100*(1 - d['sale_price']/d['price'])
    else:
        d['discount_percentage'] = None 

    d['unit_price'] = soup.find('div', class_='cup-price').string.strip() or None        
    d['datetime'] = dt.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

    return d

def collect_products(stock_codes, as_df=True):
    """
    For each item in the given list of stock codes (list of strings), call :func:`get_product`, parse the responses, and return the results as a list of dictionaries.
    If ``as_df``, then return the result as a DataFrame with columns equal to the keys listed in :func:`parse_product`.
    """
    results = []
    for code in stock_codes:
        try:
            html = get_product(code)
            info = parse_product(html)
            results.append(info)
        except:
            # Skip failures
            continue
        
    if as_df:
        results = pd.DataFrame(results)
        if not results.empty:
            results['datetime'] = pd.to_datetime(results['datetime'])
        
    return results

MAX_CONNECTIONS_PER_HOST = 100
sema = curio.BoundedSemaphore(MAX_CONNECTIONS_PER_HOST)

async def get_product_a(stock_code):
    """
    Asynchronous version of :func:`get_product`.
    """
    url = 'https://shop.countdown.co.nz/Shop/ProductDetails'
    async with sema, curio_http.ClientSession() as session:
         response = await session.get(url, params={'stockcode': stock_code})
         content = await response.text()
         return response, content
        
async def collect_products_a_base(stock_codes, as_df):    
    """
    Asynchronous version of :func:`collect_products`.
    Must be called with ``curio.run(collect_products_a(*))``.
    """
    tasks = []
    for code in stock_codes:
        task = await curio.spawn(get_product_a(code))
        tasks.append(task)

    results = []
    for task in tasks:
        response, content = await task.join()
        if response.status_code == 200:
            results.append(parse_product(content))
    
    if as_df:
        results = pd.DataFrame(results)
        results['datetime'] = pd.to_datetime(results['datetime'])
    
    return results.sort_values('name')

def collect_products_a(stock_codes, as_df=True):
    """
    Asynchronous version of :func:`collect_products`.
    Wraps :func:`collects_products_a_base`.
    """
    return curio.run(collect_products_a_base(stock_codes, as_df=as_df))

#-------------------------
# Data pipeline functions
#-------------------------
def filter_sales(products):
    """
    Given a DataFrame of products of the form returned by :func:`collect_products`, keep only the items on sale and the columns ``['name', 'sale_price', 'price', 'discount']``.
    """
    cols = ['name', 'sale_price', 'price', 'discount_percentage']
    f = products.loc[products['on_sale'], cols].copy()
    return f

def get_secret(key, secrets_path=ROOT/'secrets.json'):
    """
    Open the JSON file at ``secrets_path``, and return the value corresponding to the given key. 
    """
    secrets_path = Path(secrets_path)
    with secrets_path.open() as src:
        secrets = json.load(src)
    return secrets[key]

def email(products, email_address, mailgun_domain, mailgun_key, as_html=True):
    """
    Email the given product DataFrame to the given email address using Mailgun with the given domain and API key.
    If ``as_html``, then write the email body as HTML; otherwise, write it as text.
    """

    url = 'https://api.mailgun.net/v3/{!s}/messages'.format(mailgun_domain)
    auth = ('api', mailgun_key)
    data = {
        'from': 'Countdowner <hello@countdowner.io>',
        'to': email_address,
        'subject': 'Countdown sale on your watchlist items',
    }
    if as_html:
        data['html'] = products.to_html(index=False, float_format='%.2f')
    else:
        data['text'] = products.to_string(index=False, float_format='%.2f')

    return requests.post(url, auth=auth, data=data)

def run_pipeline(watchlist_path, out_dir, mailgun_domain=None, 
  mailgun_key=None, as_html=True):
    """
    Read a YAML watchlist located at ``watchlist_path`` (string or Path object), one that :func:`read_watchlist` can read, collect all the product information from Countdown, and write the result to a CSV located in the directory ``out_dir`` (string or Path object), creating the directory if it does not exist.
    If ``mailgun_domain`` (string) and ``mailgun_key`` are given, then email the products that are on sale (if there are any) using :func:`email`.
    """
    # Read products
    watchlist_path = Path(watchlist_path)
    w = read_watchlist(watchlist_path)
    
    # Collect updates
    codes = w['products']['stock_code']
    f = collect_products_a(codes)
    
    # Write product updates
    out_dir = Path(out_dir)
    if not out_dir.exists():
        out_dir.mkdir(parents=True)

    t = dt.datetime.now()
    path = out_dir/'{!s}_prices_{:%Y-%m-%dT%H:%M}'.format(w['name'], t)
    f.to_csv(str(path), index=False)
    
    # Filter sale items
    g = filter_sales(f)
    if not g.empty and mailgun_domain is not None and mailgun_key is not None:
        # Email
        email(g, w['email_address'], mailgun_domain, mailgun_key, 
          as_html=as_html)
