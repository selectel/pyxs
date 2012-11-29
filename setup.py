#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import sys

from setuptools import setup
from setuptools.command.test import test as TestCommand


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
    "Programming Language :: Python :: 2.7",
    "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
)


class PyTest(TestCommand):
    """Unfortunately :mod:`setuptools` support only :mod:`unittest`
    based tests, thus, we have to overider build-in ``test`` command
    to run :mod:`pytest`.
    """
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest
        sys.exit(pytest.main(self.test_args + ["tests.py"]))


setup(name="pyxs",
      version="0.3",
      packages=["pyxs"],
      cmdclass={"test": PyTest},
      tests_require=["pytest"],
      platforms=["any"],

      author="Sergei Lebedev",
      author_email="superbobry@gmail.com",
      description=DESCRIPTION,
      long_description=LONG_DESCRIPTION,
      classifiers=CLASSIFIERS,
      keywords=["xen", "xenstore", "virtualization"],
)
