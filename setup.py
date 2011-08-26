#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import sys

try:
    from setuptools import setup, Command
except ImportError:
    from distutils.core import setup, Command


here = os.path.abspath(os.path.dirname(__file__))

DESCRIPTION = "Pure Python bindings to XenStore."

try:
    LONG_DESCRIPTION = open(os.path.join(here, "README")).read()
except IOError:
    LONG_DESCRIPTION = ""


CLASSIFIERS = (
    "Development Status :: 2 - Pre-Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 2.6",
)


class PyTest(Command):
    """Unfortunately :mod:`setuptools` support only :mod:`unittest`
    based tests, thus, we have to overider build-in ``test`` command
    to run :mod:`pytest`.

    .. note::

       Please pack your tests, using ``py.test --genscript=runtests.py``
       before commiting, this will eliminate `pytest` dependency.
    """
    user_options = []
    initialize_options = finalize_options = lambda self: None

    def run(self):
        errno = subprocess.call([sys.executable, "runtests.py", "tests.py"])
        raise SystemExit(errno)


setup(name="pyxs",
      version="0.3",
      packages=["pyxs"],
      cmdclass={"test": PyTest},
      platforms=["any"],

      author="Sergei Lebedev",
      author_email="lebedev@selectel.ru",
      description=DESCRIPTION,
      long_description=LONG_DESCRIPTION,
      classifiers=CLASSIFIERS,
      keywords=["xen", "xenstore", "virtualization"],
)
