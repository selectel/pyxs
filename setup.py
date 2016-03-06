#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os

from setuptools import setup


here = os.path.abspath(os.path.dirname(__file__))

DESCRIPTION = "Pure Python bindings to XenStore."

try:
    LONG_DESCRIPTION = open(os.path.join(here, "README")).read()
except IOError:
    LONG_DESCRIPTION = ""


CLASSIFIERS = (
    "Development Status :: 2 - Pre-Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 2",
    "Programming Language :: Python :: 2.6",
    "Programming Language :: Python :: 2.7",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.4",
    "Programming Language :: Python :: 3.5",
    "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
)

setup(name="pyxs",
      version="0.4.1",
      packages=["pyxs"],
      setup_requires=["pytest-runner"],
      tests_require=["pytest"],
      platforms=["any"],

      author="Sergei Lebedev",
      author_email="superbobry@gmail.com",
      description=DESCRIPTION,
      long_description=LONG_DESCRIPTION,
      classifiers=CLASSIFIERS,
      keywords=["xen", "xenstore", "virtualization"],
      url="https://github.com/selectel/pyxs")
