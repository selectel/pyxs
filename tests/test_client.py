# -*- coding: utf-8 -*-

import errno
from threading import Timer

import pytest

from pyxs.client import Client
from pyxs.connection import UnixSocketConnection, XenBusConnection
from pyxs.exceptions import InvalidPayload, InvalidPermission, \
    UnexpectedPacket, PyXSError
from pyxs._internal import Op, Packet


def setup_function(f):
    try:
        with Client() as c:
            c.rm("/foo")
    except PyXSError:
        pass


def test_client_init():
    # a) UnixSocketConnection
    c = Client()
    assert c.tx_id is 0
    assert not c.events
    assert isinstance(c.connection, UnixSocketConnection)
    assert c.connection.fd is None

    c = Client(unix_socket_path="/var/run/xenstored/socket")
    assert isinstance(c.connection, UnixSocketConnection)
    assert c.connection.fd is None

    # b) XenBusConnection
    c = Client(xen_bus_path="/proc/xen/xenbus")
    assert isinstance(c.connection, XenBusConnection)
    assert c.connection.fd is None


virtualized = pytest.mark.skipif(
    "not os.path.exists('/proc/xen') or not Client.SU")


@virtualized
def test_client_transaction():
    # Making sure ``tx_id`` is acquired if transaction argument is not
    # ``False``.
    c = Client(transaction=True)
    assert c.connection.fd
    assert c.tx_id is not 0


@virtualized
def test_client_context_manager():
    # a) no transaction is running
    c = Client()
    assert c.connection.fd is None

    with c:
        assert c.connection.fd

    assert c.connection.fd is None

    # b) transaction in progress -- expecting it to be commited on
    #    context manager exit.
    c = Client(transaction=True)

    with c:
        assert c.tx_id is not 0

    assert c.tx_id is 0


@virtualized
def test_client_execute_command():
    c = Client()
    c.execute_command(Op.WRITE, "/foo/bar", "baz")

    # a) arguments contain invalid characters.
    with pytest.raises(ValueError):
        c.execute_command(Op.DEBUG, "\x07foo")

    # b) command validator fails.
    c.COMMAND_VALIDATORS[Op.DEBUG] = lambda *args: False
    with pytest.raises(ValueError):
        c.execute_command(Op.DEBUG, "foo")
    c.COMMAND_VALIDATORS.pop(Op.DEBUG)

    # c) ``Packet`` constructor fails.
    with pytest.raises(InvalidPayload):
        c.execute_command(Op.WRITE, "/foo/bar", "baz" * 4096)

    # d) XenStore returned an error code.
    with pytest.raises(PyXSError):
        c.execute_command(Op.READ, "/path/to/something")

    _old_recv = c.connection.recv
    # e) XenStore returns a packet with invalid operation in the header.
    c.connection.recv = lambda *args: Packet(Op.DEBUG, "boo")
    with pytest.raises(UnexpectedPacket):
        c.execute_command(Op.READ, "/foo/bar")
    c.connection.recv = _old_recv

    # d) XenStore returns a packet with invalid transaction id in the
    #    header.
    c.connection.recv = lambda *args: Packet(Op.READ, "boo", tx_id=42)
    with pytest.raises(UnexpectedPacket):
        c.execute_command(Op.READ, "/foo/bar")
    c.connection.recv = _old_recv

    # e) ... and a hack for ``XenBusConnection``
    c = Client(connection=XenBusConnection())
    c.connection.recv = lambda *args: Packet(Op.READ, "boo", tx_id=42)
    try:
        c.execute_command(Op.READ, "/foo/bar")
    except UnexpectedPacket as e:
        pytest.fail("No error should've been raised, got: {0}"
                    .format(e))
    c.connection.recv = _old_recv

    # f) Got a WATCH_EVENT instead of an expected packet type, making
    #    sure it's queued properly.
    def recv(*args):
        if hasattr(recv, "called"):
            return Packet(Op.READ, "boo")
        else:
            recv.called = True
            return Packet(Op.WATCH_EVENT, "boo")
    c.connection.recv = recv

    try:
        c.execute_command(Op.READ, "/foo/bar")
    except UnexpectedPacket as e:
        pytest.fail("No error should've been raised, got: {0}"
                    .format(e))
    else:
        assert len(c.events) is 1
        assert c.events[0] == Packet(Op.WATCH_EVENT, "boo")

    c.connection.recv = _old_recv

    # Cleaning up.
    with Client() as c:
        c.execute_command(Op.RM, "/foo/bar")


@virtualized
def test_client_ack():
    c = Client()

    # a) OK-case.
    c.connection.recv = lambda *args: Packet(Op.WRITE, "OK\x00")

    try:
        c.ack(Op.WRITE, "/foo", "bar")
    except PyXSError as e:
        pytest.fail("No error should've been raised, got: {0}"
                    .format(e))

    # b) ... something went wrong.
    c.connection.recv = lambda *args: Packet(Op.WRITE, "boo")

    with pytest.raises(PyXSError):
        c.ack(Op.WRITE, "/foo", "bar")


with_backend = pytest.mark.parametrize("backend", [
    UnixSocketConnection, XenBusConnection
])


@virtualized
@with_backend
def test_client_read(backend):
    c = Client(connection=backend())

    # a) non-existant path.
    try:
        c.read("/foo/bar")
    except PyXSError as e:
        assert e.args[0] == errno.ENOENT

    # b) OK-case (`/local` is allways in place).
    assert c.read("/local") == ""
    assert c["/local"] == ""

    # c) No read permissions (should be ran in DomU)?


@virtualized
@with_backend
def test_write(backend):
    c = Client(connection=backend())

    c.write("/foo/bar", "baz")
    assert c.read("/foo/bar") == "baz"

    c["/foo/bar"] = "boo"
    assert c["/foo/bar"] == "boo"

    # b) No write permissions (should be ran in DomU)?


@virtualized
@with_backend
def test_mkdir(backend):
    c = Client(connection=backend())

    c.mkdir("/foo/bar")
    assert c.ls("/foo") == ["bar"]
    assert c.read("/foo/bar") == ""


@virtualized
@with_backend
def test_rm(backend):
    c = Client(connection=backend())
    c.mkdir("/foo/bar")

    try:
        c.rm("/foo/bar")
    except PyXSError as e:
        pytest.fail("No error should've been raised, got: {0}"
                    .format(e))

    with pytest.raises(PyXSError):
        c.read("/foo/bar")

    try:
        c.read("/foo/bar", "baz") == "baz"  # using a default option.
    except PyXSError:
        pytest.fail("No error should've been raised, got: {0}"
                    .format(e))

    assert c.read("/foo") == ""


@virtualized
def test_ls():
    for backend in [UnixSocketConnection, XenBusConnection]:
        c = Client(connection=backend())
        c.mkdir("/foo/bar")

        # a) OK-case.
        assert c.ls("/foo") == ["bar"]
        assert c.ls("/foo/bar") == []

        # b) directory doesn't exist.
        try:
            c.ls("/path/to/something")
        except PyXSError as e:
            assert e.args[0] == errno.ENOENT

        # c) No list permissions (should be ran in DomU)?


@virtualized
@with_backend
def test_permissions(backend):
    c = Client(connection=backend())
    c.rm("/foo")
    c.mkdir("/foo/bar")

    # a) checking default permissions -- full access.
    assert c.get_permissions("/foo/bar") == ["n0"]

    # b) setting new permissions, and making sure it worked.
    c.set_permissions("/foo/bar", ["b0"])
    assert c.get_permissions("/foo/bar") == ["b0"]

    # c) conflicting permissions -- XenStore doesn't care.
    c.set_permissions("/foo/bar", ["b0", "n0", "r0"])
    assert c.get_permissions("/foo/bar") == ["b0", "n0", "r0"]

    # d) invalid permission format.
    with pytest.raises(InvalidPermission):
        c.set_permissions("/foo/bar", ["x0"])


@virtualized
@with_backend
def test_get_domain_path(backend):
    c = Client(connection=backend())

    # a) invalid domid.
    with pytest.raises(ValueError):
        c.get_domain_path("foo")

    # b) OK-case (note, that XenStored doesn't care if a domain
    #    actually exists, but according to the spec we shouldn't
    #    really count on a *valid* reply in that case).
    assert c.get_domain_path(0) == "/local/domain/0"
    assert c.get_domain_path(999) == "/local/domain/999"


@virtualized
@with_backend
def test_is_domain_introduced(backend):
    c = Client(connection=backend())

    for domid in map(int, c.ls("/local/domain")):
        assert c.is_domain_introduced(domid)

    assert not c.is_domain_introduced(999)


@virtualized
@with_backend
def test_watches(backend):
    c = Client(connection=backend())
    c.write("/foo/bar", "baz")
    m = c.monitor()
    m.watch("/foo/bar", "boo")

    # a) we receive the first event immediately, so `wait()` doesn't
    #    block.
    assert m.wait() == ("/foo/bar", "boo")

    # b) before the second call we have to make sure someone
    #    will change the path being watched.
    Timer(.5, lambda: c.write("/foo/bar", "baz")).run()
    assert m.wait() == ("/foo/bar", "boo")

    # c) changing a children of the watched path triggers watch
    #    event as well.
    Timer(.5, lambda: c.write("/foo/bar/baz", "???")).run()
    assert m.wait() == ("/foo/bar/baz", "boo")


@virtualized
@with_backend
def test_header_decode_error(backend):
    c = Client(connection=backend())

    # a) The following packet's header cannot be decoded to UTF-8, but
    #    we still need to handle it somehow.
    p = Packet(11, "/foo", rq_id=0, tx_id=128)

    try:
        c.connection.send(p)
    except UnicodeDecodeError as e:
        pytest.fail("No error should've been raised, got: {0}"
                    .format(e))
