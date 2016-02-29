# -*- coding: utf-8 -*-

from __future__ import absolute_import

import pytest

from pyxs._compat import xs, Error

from . import virtualized


@virtualized
def setup_function(f):
    try:
        handle = xs()
    except Error:
        return  # Failed to connect.

    try:
        handle.rm(0, b"/foo")
    except Error:
        pass
    finally:
        handle.close()


@pytest.yield_fixture
def handle():
    handle = xs()
    try:
        yield handle
    finally:
        handle.close()


def test_api_completeness():
    try:
        from xen.lowlevel.xs import xs as cxs
    except ImportError:
        pytest.skip("xen.lowlevel.xs not available")

    def public_methods(target):
        return set(attr for attr in dir(target)
                   if not attr.startswith("_"))

    assert public_methods(cxs).issubset(public_methods(xs))


@virtualized
def test_ls(handle):
    assert handle.ls(0, b"/missing/path") is None


@virtualized
def test_transaction_start(handle):
    assert isinstance(handle.transaction_start(), bytes)


@virtualized
def test_transaction_end_rollback(handle):
    assert handle.ls(0, b"/foo") is None
    tx_id = handle.transaction_start()
    handle.write(tx_id, b"/foo/bar", b"boo")
    handle.transaction_end(tx_id, abort=1)
    assert handle.ls(0, b"/foo") is None


@virtualized
def test_transaction_end_commit(handle):
    assert handle.ls(0, b"/foo") is None
    tx_id = handle.transaction_start()
    handle.write(tx_id, b"/foo/bar", b"boo")
    handle.transaction_end(tx_id, abort=0)
    assert handle.ls(0, b"/foo") == [b"bar"]


@virtualized
def test_watch_unwatch(handle):
    token = object()
    handle.watch(b"/foo/bar", token)
    assert handle.read_watch() == (b"/foo/bar", token)
    handle.unwatch(b"/foo/bar", token)
