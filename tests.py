# -*- coding: utf-8 -*-

from pyxs import Header, Packet


def test_header_from_string():
    d = "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00OK\x00"
    h = Header.from_string(d)
    assert h.type == 0
    assert h.req_id == 0
    assert h.tx_id == 0
    assert h.len == 3

    assert str(h) == d[:-h.len]


def test_packet_from_string():
    d = "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00OK\x00"
    p = Packet.from_string(d)

    assert p.payload == "OK\x00"
    assert len(p.payload) == p.header.len
    assert str(p) == d
