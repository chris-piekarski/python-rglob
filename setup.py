#!/usr/bin/env python

from setuptools import setup, Extension

setup(name='rglob',
      version='1.7',
      description='Python Recursive Glob',
      author='Christopher Piekarski',
      author_email='chris@cpiekarski.com',
      maintainer='Christopher Piekarski',
      maintainer_email='chris@cpiekarski.com',
      keywords=['glob','rglob','recursive','line counter'],
      python_requires='>=3.5',
      classifiers=[
                   'Intended Audience :: Developers',
                   'License :: OSI Approved :: Apache Software License',
                   'Programming Language :: Python :: 3.5',
                   'Operating System :: OS Independent',
                   ],
      url='http://cpiekarski.com/2011/09/23/python-recursive-glob/',
      packages=['rglob'],
      provides=['rglob'],
      license='OSI Approved Apache Software License',
     )
