# -*- coding: utf-8 -*-

import errno
from threading import Timer

import pytest

from pyxs.client import Router, Client
from pyxs.connection import UnixSocketConnection, XenBusConnection
from pyxs.exceptions import InvalidPayload, InvalidPermission, \
    UnexpectedPacket, PyXSError
from pyxs._internal import NUL, Op, Packet


def setup_function(f):
    try:
        with Client() as c:
            c.rm(b"/foo")
    except PyXSError:
        pass


def test_client_init():
    # a) UnixSocketConnection
    c = Client()
    assert c.tx_id == 0
    assert isinstance(c.router.connection, UnixSocketConnection)
    assert not c.router_thread.is_alive()

    c = Client(unix_socket_path="/var/run/xenstored/socket")
    assert isinstance(c.router.connection, UnixSocketConnection)
    assert not c.router_thread.is_alive()

    # b) XenBusConnection
    c = Client(xen_bus_path="/proc/xen/xenbus")
    assert isinstance(c.router.connection, XenBusConnection)
    assert not c.router_thread.is_alive()


virtualized = pytest.mark.skipif(
    "not os.path.exists('/proc/xen') or not Client.SU")


@virtualized
def test_client_context_manager():
    # a) no transaction is running
    c = Client()
    assert not c.router_thread.is_alive()

    with c:
        assert c.router_thread.is_alive()

    assert not c.router_thread.is_alive()


# @virtualized
# def test_transaction_context_manager():
#     # b) transaction in progress -- expecting it to be commited on
#     #    context manager exit.
#     c = Client()
#     with c.transaction():
#         assert c.tx_id != 0

#     assert c.tx_id == 0


# @virtualized
# def test_execute_command_invalid_characters():
#     with Client() as c:
#         c.execute_command(Op.WRITE, b"/foo/bar" + NUL, b"baz")

#         with pytest.raises(ValueError):
#             c.execute_command(Op.DEBUG, b"\x07foo" + NUL)


# @virtualized
# def test_execute_command_validator_fails():
#     with Client() as c:
#         COMMAND_VALIDATORS[Op.DEBUG] = lambda *args: False
#         with pytest.raises(ValueError):
#             c.execute_command(Op.DEBUG, b"foo" + NUL)
#         COMMAND_VALIDATORS.pop(Op.DEBUG)


# @virtualized
# def test_execute_command():
#     # c) ``Packet`` constructor fails.
#     with pytest.raises(InvalidPayload):
#         c.execute_command(Op.WRITE, b"/foo/bar" + NUL, b"baz" * 4096)

#     # d) XenStore returned an error code.
#     with pytest.raises(PyXSError):
#         c.execute_command(Op.READ, b"/path/to/something" + NUL)

#     _old_recv = c.router.connection.recv
#     # e) XenStore returns a packet with invalid operation in the header.
#     c.router.connection.recv = lambda *args: Packet(Op.DEBUG, b"boo" + NUL)
#     with pytest.raises(UnexpectedPacket):
#         c.execute_command(Op.READ, b"/foo/bar" + NUL)
#     c.router.connection.recv = _old_recv

#     # d) XenStore returns a packet with invalid transaction id in the
#     #    header.
#     c.router.connection.recv = lambda *args: Packet(Op.READ, b"boo", tx_id=42)
#     with pytest.raises(UnexpectedPacket):
#         c.execute_command(Op.READ, b"/foo/bar")
#     c.router.connection.recv = _old_recv

#     # e) ... and a hack for ``XenBusConnection``
#     c = Client(connection=XenBusConnection())
#     c.router.connection.recv = lambda *args: Packet(Op.READ, b"boo", tx_id=42)
#     c.execute_command(Op.READ, b"/foo/bar")
#     c.router.connection.recv = _old_recv

#     # f) Got a WATCH_EVENT instead of an expected packet type, making
#     #    sure it's queued properly.
#     def recv(*args):
#         if hasattr(recv, "called"):
#             return Packet(Op.READ, b"boo")
#         else:
#             recv.called = True
#             return Packet(Op.WATCH_EVENT, b"boo")
#     c.router.connection.recv = recv
#     c.execute_command(Op.READ, "/foo/bar")
#     assert len(c.events) == 1
#     assert c.events[0] == Packet(Op.WATCH_EVENT, b"boo")

#     c.router.connection.recv = _old_recv

#     # Cleaning up.
#     with Client() as c:
#         c.execute_command(Op.RM, b"/foo/bar" + NUL)


@virtualized
def test_ack_ok():
    with Client() as c:
        c.router.connection.recv = lambda *args: Packet(Op.WRITE, b"OK\x00")
        c.ack(Op.WRITE, b"/foo", b"bar")


@virtualized
def test_ack_error():
    with Client() as c:
        c.router.connection.recv = lambda *args: Packet(Op.WRITE, b"boo")
        with pytest.raises(PyXSError):
            c.ack(Op.WRITE, b"/foo", b"bar")


with_backend = pytest.mark.parametrize("backend", [
    UnixSocketConnection, XenBusConnection
])


@virtualized
@with_backend
def test_client_read(backend):
    with Client(router=Router(backend())) as c:
        # a) non-existant path.
        try:
            c.read(b"/foo/bar")
        except PyXSError as e:
            assert e.args[0] == errno.ENOENT

        # b) OK-case (`/local` is allways in place).
        assert c.read("/local") == b""
        assert c["/local"] == b""

        # c) No read permissions (should be ran in DomU)?


@virtualized
@with_backend
def test_write(backend):
    with Client(router=Router(backend())) as c:
        c.write(b"/foo/bar", b"baz")
        assert c.read(b"/foo/bar") == b"baz"

        c[b"/foo/bar"] = b"boo"
        assert c[b"/foo/bar"] == b"boo"

        # b) No write permissions (should be ran in DomU)?


@virtualized
@with_backend
def test_mkdir(backend):
    with Client(router=Router(backend())) as c:
        c.mkdir(b"/foo/bar")
        assert c.ls(b"/foo") == [b"bar"]
        assert c.read(b"/foo/bar") == b""


@virtualized
@with_backend
def test_rm(backend):
    with Client(router=Router(backend())) as c:
        c.mkdir(b"/foo/bar")
        c.rm(b"/foo/bar")

        with pytest.raises(PyXSError):
            c.read(b"/foo/bar")

        c.read(b"/foo/bar", b"baz") == b"baz"  # using a default option.

        assert c.read(b"/foo") == b""


@virtualized
@with_backend
def test_ls(backend):
    with Client(router=Router(backend())) as c:
        c.mkdir(b"/foo/bar")

        # a) OK-case.
        assert c.ls(b"/foo") == [b"bar"]
        assert c.ls(b"/foo/bar") == []

        # b) directory doesn't exist.
        try:
            c.ls(b"/path/to/something")
        except PyXSError as e:
            assert e.args[0] == errno.ENOENT

        # c) No list permissions (should be ran in DomU)?


@virtualized
@with_backend
def test_permissions(backend):
    with Client(router=Router(backend())) as c:
        c.rm(b"/foo")
        c.mkdir(b"/foo/bar")

        # a) checking default permissions -- full access.
        assert c.get_permissions(b"/foo/bar") == [b"n0"]

        # b) setting new permissions, and making sure it worked.
        c.set_permissions(b"/foo/bar", [b"b0"])
        assert c.get_permissions(b"/foo/bar") == [b"b0"]

        # c) conflicting permissions -- XenStore doesn't care.
        c.set_permissions(b"/foo/bar", [b"b0", b"n0", b"r0"])
        assert c.get_permissions(b"/foo/bar") == [b"b0", b"n0", b"r0"]

        # d) invalid permission format.
        with pytest.raises(InvalidPermission):
            c.set_permissions(b"/foo/bar", [b"x0"])


@virtualized
@with_backend
def test_get_domain_path(backend):
    with Client(router=Router(backend())) as c:
        # Note, that XenStored doesn't care if a domain exists, but
        # according to the spec we shouldn't really count on a *valid*
        # reply in that case.
        assert c.get_domain_path(0) == b"/local/domain/0"
        assert c.get_domain_path(999) == b"/local/domain/999"


@virtualized
@with_backend
def test_is_domain_introduced(backend):
    with Client(router=Router(backend())) as c:
        for domid in map(int, c.ls("/local/domain")):
            assert c.is_domain_introduced(domid)

        assert not c.is_domain_introduced(999)


@virtualized
@with_backend
def test_watches(backend):
    with Client(router=Router(backend())) as c:
        c.write(b"/foo/bar", b"baz")
        m = c.monitor()
        m.watch(b"/foo/bar", b"boo")

        waiter = m.wait()
        # a) we receive the first event immediately, so `next` doesn't
        #    block.
        assert next(waiter) == (b"/foo/bar", b"boo")

        # b) before the second call we have to make sure someone
        #    will change the path being watched.
        Timer(.5, lambda: c.write(b"/foo/bar", b"baz")).run()
        assert next(waiter) == (b"/foo/bar", b"boo")

        # c) changing a children of the watched path triggers watch
        #    event as well.
        Timer(.5, lambda: c.write(b"/foo/bar/baz", b"???")).run()
        assert next(waiter) == (b"/foo/bar/baz", b"boo")


@virtualized
@with_backend
def test_header_decode_error(backend):
    with Client(router=Router(backend())) as c:
        # a) The following packet's header cannot be decoded to UTF-8, but
        #    we still need to handle it somehow.
        p = Packet(11, b"/foo", rq_id=0, tx_id=128)
        c.router.connection.send(p)
