# -*- coding: utf-8 -*-

import string
from cStringIO import StringIO

import pytest

from pyxs._internal import Op, Packet
from pyxs.exceptions import InvalidOperation, InvalidPayload, InvalidPath, \
    InvalidTerm, InvalidPermission
from pyxs.helpers import compile, spec, validate_path, validate_wpath, \
    validate_perms


def test_packet():
    # a) invalid operation.
    with pytest.raises(InvalidOperation):
        Packet(-1, "", 0)

    # b) invalid payload -- maximum size exceeded.
    with pytest.raises(InvalidPayload):
        Packet(Op.DEBUG, "hello" * 4096, 0)


def test_packet_from_string():
    d = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00OK\x00"
    p = Packet.from_string(d)

    assert p.op == Op.DEBUG
    assert p.rq_id == 0
    assert p.tx_id == 0
    assert p.len == 3
    assert p.payload == b"OK\x00"
    assert len(p.payload) == p.len
    assert str(p) == d


def test_packet_from_file():
    d = StringIO(b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03"
                 b"\x00\x00\x00OK\x00")
    p = Packet.from_file(d)
    d.seek(0)

    assert p.op == Op.DEBUG
    assert p.rq_id == 0
    assert p.tx_id == 0
    assert p.len == 3
    assert p.payload == b"OK\x00"
    assert len(p.payload) == p.len
    assert str(p) == d.read()


# Helpers.

def test_compile():
    # a) <foo> -- non-empty string with no NULL bytes.
    v = compile("<foo>")
    assert v("foo")
    assert not v("foo\x07")
    assert not v("foo\x00")
    assert not v("f\x00oo")
    assert not v("")

    # b) <foo|> -- non-empty string with zero or more NULL bytes.
    v = compile("<foo|>")
    assert v("foo")
    assert v("foo\x00")
    assert v("f\x00\x00oo")
    assert not v("foo\x07")
    assert not v("")

    # c) <foo>| -- non-empty string with no NULL bytes, followed by a
    #    trailing NULL.
    v = compile("<foo>|")
    assert v("foo\x00")
    assert not v("\x00")
    assert not v("f\x00oo\x00")
    assert not v("")

    # d) <foo>|* -- zero or more non-empty strings with no NULL bytes,
    #    followed by a trailing NULL.
    v = compile("<foo>|*")
    assert v([])
    assert v(["foo\x00"])
    assert v(["foo\x00", "bar\x00"])
    assert not v(["foo\x00", "bar\x00", "\x00"])
    assert not v(["\x00"])

    # e) <foo>|+ -- one or more non-empty strings with no NULL bytes,
    #    followed by a trailing NULL.
    v = compile("<foo>|+")
    assert v(["foo\x00"])
    assert v(["foo\x00", "bar\x00"])
    assert not v(["foo\x00", "bar\x00", "\x00"])
    assert not v(["\x00"])
    assert not v([])

    # f) invalid term syntax.
    for term in ["<foo", "<foo><bar>", "<foo >"]:
        with pytest.raises(InvalidTerm):
            compile(term)


def test_validate_path():
    # a) max length is bounded by 3072 for absolute path and 2048 for
    #    relative ones.
    with pytest.raises(InvalidPath):
        validate_path("/foo/bar" * 3072)

    with pytest.raises(InvalidPath):
        validate_path("foo/bar" * 2048)

    # b) ASCII alphanumerics and -/_@ only!
    for char in string.punctuation:
        if char in "-/_@": continue

        with pytest.raises(InvalidPath):
            validate_path("/foo" + char)

    # c) no trailing / -- except for root path.
    with pytest.raises(InvalidPath):
        validate_path("/foo/")

    try:
        validate_path("/")
    except InvalidPath as p:
        pytest.fail("{0} is prefectly valid, baby :)".format(p.args))


def test_validate_wpath():
    # a) ordinary path should be checked with `validate_path()`
    with pytest.raises(InvalidPath):
        validate_wpath("/foo/")

    with pytest.raises(InvalidPath):
        validate_wpath("/fo\x07o")

    with pytest.raises(InvalidPath):
        validate_wpath("/$/foo")

    # b) special path options are limited to `@introduceDomain` and
    #    `@releaseDomain`.
    with pytest.raises(InvalidPath):
        validate_wpath("@foo")

    try:
        validate_wpath("@introduceDomain")
        validate_wpath("@releaseDomain")
    except InvalidPath as p:
        pytest.fail("{0} is prefectly valid, baby :)".format(p.args))


def test_validate_perms():
    # a valid permission has a form `[wrbn]:digits:`.
    with pytest.raises(InvalidPermission):
        validate_perms(["foo"])

    with pytest.raises(InvalidPermission):
        validate_perms(["f20"])

    with pytest.raises(InvalidPermission):
        validate_perms(["r-20"])

    try:
        validate_perms(["w0", "r0", "b0", "n0"])
        validate_perms(["w999999"])  # valid, even though it overflows int32.
    except InvalidPermission as p:
        pytest.fail("{0} is prefectly valid, baby :)".format(p.args))


def test_spec():
    @spec("<a|>", "<b>|+", "<c>")
    def foo(self, a, b, c):
        return True

    # a) checking that ``__spec__`` atribute is updated.
    assert hasattr(foo, "__spec__")
    assert len(foo.__spec__) == 3
    a, b, c = foo.__spec__

    assert a.null_ending == False
    assert b.null_ending == True
    assert c.null_ending == False

    # b) checking valid argument cases.
    for args in [("foo\x00", ["bar\x00"], "baz"),
                 ("foo\x00", ["bar\x00", "baz\x00"], "baz")]:
        try:
            assert foo(None, *args)
        except ValueError:
            pytest.fail("No error should've been raised for {0}"
                        .format(args))

    # c) time for some errors.
    for args in [("fo\x07o", ["bar\x00"], "baz"),
                 ("foo\x00", [], "baz"),
                 ("foo\x00", [], "\x00")]:
        with pytest.raises(ValueError):
            foo(None, *args)
