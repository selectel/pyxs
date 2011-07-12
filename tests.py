# -*- coding: utf-8 -*-

import pytest

from pyxs import Op, Packet, InvalidOperation, InvalidPayload


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
    assert p.req_id == 0
    assert p.tx_id == 0
    assert p.len == 3
    assert p.payload == b"OK\x00"
    assert len(p.payload) == p.len
    assert str(p) == d
