# -*- coding: utf-8 -*-
"""
    pyxs.exceptions
    ~~~~~~~~~~~~~~~

    This module implements a number of Python exceptions used by
    :mod:`pyxs` classes.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""

__all__ = [
    "InvalidOperation", "InvalidPayload", "InvalidPath", "InvalidTerm"
]


class InvalidOperation(ValueError):
    """Exception raised when :class:`~pyxs._internal.Packet` is passed
    an operation, which isn't listed in :data:`~pyxs._internal.Op`.

    :param int operation: invalid operation value.
    """


class InvalidPayload(ValueError):
    """Exception raised when :class:`~pyxs.Packet` is initialized with
    payload, which exceeds 4096 bytes restriction or contains a
    trailing ``NULL``.

    :param bytes operation: invalid payload value.
    """


class InvalidPath(ValueError):
    """Exception raised when a path proccessed by a comand doesn't
    match the following constraints:

    * its length should not exceed 3072 or 2048 for absolute and
      relative path respectively.
    * it should only consist of ASCII alphanumerics and the four
      punctuation characters ``-/_@`` -- `hyphen`, `slash`, `underscore`
      and `atsign`.
    * it shouldn't have a trailing ``/``, except for the root path.

    :param bytes path: invalid path value.
"""


class InvalidTerm(SyntaxError):
    """Exception raised by :func:`~pyxs.helpers.compile` when a given
    term is invalid, i. e. doesn't match any of the recognized forms.

    :param bytes term: invalid term value.
    """


class InvalidPermission(ValueError):
    """Exception raised for permission which don't match the following
    format::

        w<domid>	write only
        r<domid>	read only
        b<domid>	both read and write
        n<domid>	no access

    :param bytes perm: invalid permission value.
    """


class ConnectionError(Exception):
    """Exception raised for failures during socket operations.

    :param str path: detailed error message.
    """
