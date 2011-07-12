# -*- coding: utf-8 -*-
"""
    pyxs.exceptions
    ~~~~~~~~~~~~~~~

    This module implements a number of Python exceptions used by
    :mod:`pyxs` classes.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""

__all__ = frozenset([
    "InvalidOperation", "InvalidPayload", "InvalidPath", "InvalidSyntax"
])


class InvalidOperation(ValueError):
    """Exception raised when :class:`~pyxs.Packet` is passed an
    operation, which isn't listed in :data:`~pyxs.Op`.

    :param int operation: invalid operation value.
    """


class InvalidPayload(ValueError):
    """Exception raised when :class:`~pyxs.Packet` is initialized
    with payload, which exceeds 4096 bytes restriction or contains
    characters outsied the ``[0x20;0x7f]`` range

    :param bytes operation: invalid payload value.
    """


class InvalidPath(ValueError):
    """Exception raised when a path proccessed by a comand doesn't
    match the following constraints:

    * its length should not exceed 3072 or 2048 for absolute and relative
      path respectively.
    * it should only consist of ASCII alphanumerics and the four
      punctuation characters ``-/_@`` -- `hyphen`, `slash`, `underscore`
      and `atsign`.
    * it shouldn't have a trailing ``/``, except for the root path.

    :param bytes path: invalid path value.
"""


class InvalidSyntax(ValueError):
    """Exception raised by :func:`~pyxs.helpers.compile` when a given
    syntax is invalid, i. e. doesn't match any of the recognized forms.
    """
