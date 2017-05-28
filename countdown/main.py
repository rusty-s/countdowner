import datetime as dt
from collections import OrderedDict
from pathlib import Path
import os
import json

import requests
import pandas as pd
import numpy as np
import curio
import curio_http
from bs4 import BeautifulSoup


ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_secret(key, secrets_path=ROOT/'secrets.json'):
    """
    Open the JSON file at ``secrets_path``, and return the value corresponding to the given key. 
    """
    secrets_path = Path(secrets_path)
    with secrets_path.open() as src:
        secrets = json.load(src)
    return secrets[key]

def read_products(path):
    """
    Read the CSV file located at the given path (string or Path object), convert it to a DataFrame, and return the result.
    Raise a ``ValueError`` if the file does not contain a ``stock_code`` field.
    """
    path = Path(path)
    f = pd.read_csv(path, dtype={'stock_code': str})
    if 'stock_code' not in f.columns:
        raise ValueError('Product CSV must contain a stock_code field')
        
    return f

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
    Given a response from the Countdown API, parse it, and return in as a dictionary.
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
    
    d['unit_price'] = soup.find('div', class_='cup-price').string.strip() or None        
    d['datetime'] = dt.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

    return d

def collect_products(stock_codes, as_df=True):
    """
    For each item in the given list of stock codes (list of strings), call :func:`get_product`, parse the responses, and return the results as a list of dictionaries.
    If ``as_df``, then return the result as a DataFrame.
    """
    for code in stock_codes:
        try:
            r = get_product(code)
            info = parse_product(r.text)
            results.append(info)
        except:
            # Skip failures
            continue
        
    if as_df:
        results = pd.DataFrame(results)
        if not results.empty:
            results['datetime'] = pd.to_datetime(results['datetime'])
        
    return results

MAX_CONNECTIONS_PER_HOST = 10
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
        
async def collect_products_a(stock_codes, as_df=True):    
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

def email(products, subject, key, as_html=True):
    """
    """

    url = "https://api.mailgun.net/v3/sandbox6de202ffd7c148a99c36a01718d1c2d1.mailgun.org/messages"
    auth = ("api", "key-1b64688d5f489f42085d15eb83972555")
    data = {
        "from": "Mailgun Sandbox <postmaster@sandbox6de202ffd7c148a99c36a01718d1c2d1.mailgun.org>",
        "to": "ibatatas <ibatatas@runbox.com>",
        "subject": subject,
    }
    if as_html:
        data['html'] = products.to_html(index=False, float_format='%.2f')
    else:
        data['text'] = products.to_string(index=False, float_format='%.2f')

    return requests.post(url, auth=auth, data=data)

def filter_sales(products):
    """
    """
    cols = ['name', 'sale_price', 'price']
    f = products.loc[products['on_sale'], cols].copy()
    f['discount'] = 1 - f['sale_price']/f['price']
    return f

def run_pipeline(in_path, out_path, key=None, as_html=False):
    """
    Read a product CSV located at ``in_path`` (string or Path object), one that :func:`read_products` can read, collect all the product information from Countdown, and write the result to a CSV located at ``out_path`` (string or Path object).
    """
    # Read products
    in_path = Path(in_path)
    products = read_products(in_path)
    
    # Collect updates
    codes = products['stock_code']
    f = curio.run(collect_products_a(codes))
    
    # Write product updates
    f.to_csv(str(out_path), index=False)
    
    # Filter sale items
    g = filter_sales(f)
    if not g.empty and key is not None:
         # Email
         email(g, 'Countdown sales', key, as_html=as_html)
