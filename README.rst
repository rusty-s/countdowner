Countdowner
************
.. image:: https://travis-ci.org/araichev/countdowner.svg?branch=master
    :target: https://travis-ci.org/araichev/countdowner

A Python 3.4+ package to check for sales at Countdown grocery stores throughout New Zealand.
Pretty rough, but gets the job done.


Installation
=============
``pip install -U git+https://github.com/araichev/countdowner``


Usage
======
Here is a common workflow.

#. Get the stock codes of the products you want to watch by searching `the Countdown site <https://shop.countdown.co.nz/>`_.  The stock code of a product is listed in the URL of its details page. For example, the stock code for the product at ``https://shop.countdown.co.nz/Shop/ProductDetails?stockcode=214684&name=colgate-360-toothbrush-medium-whole-mouth-clean`` is ``214684``.

#. Put your stock codes into a YAML watchlist along with your email address and a name for the watchlist.  The watchlist ---call it ``watchlist.yaml``--- should have the form::

	name: my_favorites
	email_addresses:
      - brainbummer@mailinator.com
      - rhymedude@mailinator.com
	products: |
	  description,stock_code
	  organic cheese,281739
	  GB chocolate,260803
	  Lupi olive oil,701829
	  Earthcare double toilet paper,381895
	  Dijon mustard,700630

#. Use the ``countdowner`` library functions as in the IPython notebook at ``ipynb/examples.ipynb`` or run ``countdownit --help`` from the command line for information on the command line tool.  To use the emailing functionality of ``countdowner``, you'll need a (free) `Mailgun account <https://mailgun.com>`_.


Authors
========
- Alex Raichev (2017-05)


Notes
======
- Development status is Alpha
- This project uses semantic versioning
- I might extend this to New World stores once they roll out `more online shopping <http://www.newworld.co.nz/online-shopping/>`_
- Will replace ``grequests`` with a faster asynchronous HTTP requester as soon as someone makes one for ``trio``


History
========

0.2.0, 2017-06-18
-------------------
- Allowed for multiple email addresses in watchlist
- In tests, replaced actual HTTP requests with mock ones


0.1.0, 2017-06-04
-------------------
- Replaced ``curio`` and ``curio-http`` with ``grequests`` for asynchronous requests. The latter is slower but easier to use.
- Handled invalid stock codes
- Added some automated tests


0.0.1, 2017-05-30
------------------
- First draft