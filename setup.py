#!/usr/bin/env python

from distutils.core import setup

setup(name='rglob',
      version='1.4',
      description='Python Recursive Glob',
      author='Christopher Piekarski',
      author_email='chris@cpiekarski.com',
      maintainer='Christopher Piekarski',
      maintainer_email='chris@cpiekarski.com',
      keywords=['glob','rglob','recursive','line counter'],
      classifiers=[
                   'Intended Audience :: Developers',
                   'License :: OSI Approved :: Apache Software License',
                   'Programming Language :: Python :: 2.7',
                   'Operating System :: OS Independent',
                   ],
      url='http://cpiekarski.com/2011/09/23/python-recursive-glob/',
      packages=['rglob'],
      provides=['rglob'],
      license='OSI Approved Apache Software License',
     )
