from setuptools import setup, find_packages


with open('README.rst') as f:
    readme = f.read()

with open('LICENSE.txt') as f:
    license = f.read()

setup(
    name='countdowner',
    version='0.2.0',
    author='Alex Raichev',
    url='https://github.com/araichev/countdowner',
    description='A Python 3.5+ package to check for sales at Countdown'
        'grocery stores throughout New Zealand',
    long_description=readme,
    license=license,
    install_requires=[
        'PyYAML>=3.12',
        'requests>=2.14.2',
        'grequests>=0.3.0',
        'beautifulsoup4>=4.6.0',
        'lxml>=3.7.3',
        'pandas>=0.19.0',
        'click>=6.7',
    ],
    entry_points={
        'console_scripts': ['countdownit=countdowner.cli:countdownit'],
    },
    packages=find_packages(exclude=('tests', 'docs')),
)
