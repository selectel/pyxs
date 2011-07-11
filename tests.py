# -*- coding: utf-8 -*-

import pytest

from pyxs import Packet


def test_packet():
    # a) invalid packet type.
    with pytest.raises(ValueError):
        Packet(-1, 0, 0, 0)


def test_packet_from_string():
    d = "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00OK\x00"
    p = Packet.from_string(d)

    assert p.type == 0
    assert p.req_id == 0
    assert p.tx_id == 0
    assert p.len == 3
    assert p.payload == "OK\x00"
    assert len(p.payload) == p.len
    assert str(p) == d
