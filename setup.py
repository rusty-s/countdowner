from setuptools import setup, find_packages


with open('README.rst') as f:
    readme = f.read()

with open('LICENSE.txt') as f:
    license = f.read()

setup(
    name='countdowner',
    version='0.0.0',
    author='Alex Raichev',
    url='',
    description='A Python 3.5+ package to check for sales at Countdown grocery stores throughout New Zealand',
    long_description=readme,
    license=license,
    install_requires=[
        'PyYAML>=3.12',
        'pandas>=0.20.0',
        'requests>=2.14.2',
        'curio>=0.7',
        'curio-http>=0.1.0',
        'click>=6.7',
    ],
    entry_points = {
        'console_scripts': ['countdownit=countdowner.cli:countdownit'],
    },
    packages=find_packages(exclude=('tests', 'docs')),   
)

