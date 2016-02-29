import pytest

from pyxs._compat import xs, Error

def setup_function(f):
    handle = xs()
    try:
        handle.rm(0, b"/foo")
    except PyXSError:
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


def test_ls(handle):
    assert handle.ls(0, b"/missing/path") is None


def test_transaction_start(handle):
    assert isinstance(handle.transaction_start(), bytes)


def test_transaction_end_rollback(handle):
    assert handle.ls(0, b"/foo") is None
    tx_id = handle.transaction_start()
    handle.write(tx_id, b"/foo/bar", b"boo")
    handle.transaction_end(tx_id, abort=1)
    assert handle.ls(0, b"/foo") is None


def test_transaction_end_commit(handle):
    assert handle.ls(0, b"/foo") is None
    tx_id = handle.transaction_start()
    handle.write(tx_id, b"/foo/bar", b"boo")
    handle.transaction_end(tx_id, abort=0)
    assert handle.ls(0, b"/foo") == [b"bar"]


def test_watch_unwatch(handle):
    token = object()
    handle.watch(b"/foo/bar", token)
    assert handle.read_watch() == (b"/foo/bar", token)
    handle.unwatch(b"/foo/bar", token)
