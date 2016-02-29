import pytest

from pyxs.exceptions import InvalidOperation, InvalidPayload
from pyxs._internal import Op, Packet


def test_packet():
    # a) invalid operation.
    with pytest.raises(InvalidOperation):
        Packet(-1, b"", 0)

    # b) invalid payload -- maximum size exceeded.
    with pytest.raises(InvalidPayload):
        Packet(Op.DEBUG, b"hello" * 4096, 0)
