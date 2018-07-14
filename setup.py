import sys
from setuptools import setup, find_packages

from starrypy import __version__


if sys.version_info < (3, 7, 0):
    raise RuntimeError("StarryPy requires Python 3.7.0+")


def get_requirements():
    with open("REQUIREMENTS.txt") as f:
        return f.read().splitlines()


setup(
    name='starrypy',
    version=__version__,
    description='StarryPy - A python wrapper for Starbound',
    url='http://www.starrypy.org',
    long_description='',
    packages=find_packages(),
    package_data={'starrypy': ['_example/*.yaml']},
    license='MIT',
    platforms='any',
    install_requires=get_requirements(),
    entry_points={
        'console_scripts': ['starrypy = starrypy.__init__:main']
    },
    zip_safe=False
)
