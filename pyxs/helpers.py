# -*- coding: utf-8 -*-
"""
    pyxs.helpers
    ~~~~~~~~~~~~

    Implements various helpers.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""

from __future__ import unicode_literals

__all__ = ["spec"]

import inspect
import re
import posixpath
from itertools import chain
from functools import wraps
from future_builtins import zip, map

from .exceptions import InvalidSyntax, InvalidPath


def compile(*terms):
    """Compiles a given list of terms to a mapping of argument names
    to validation regexes.

    .. note:: `reserved` values aren't compiled, since there aren't
              used anywhere but in the DEBUG operation, which is not
              a priority.
    """
    def inner(term):
        if term.startswith("<"):
            end = term.endswith

            # <foo|>
            if end("|>"):
                return term[1:-2], "[\x20-\x7f\x00]+"
            # <foo>|*
            elif end(b">|*"):
                _, regex = inner(term[:-1])
                return term[1:-3], "(?:{0})*".format(regex)
            # <foo>|+
            elif end(b">|+"):
                _, regex = inner(term[:-1])
                return term[1:-3], "(?:{0})+".format(regex)
            # <foo>|
            elif end(b">|"):
                _, regex = inner(term[:-1])
                return term[1:-2], "{0}\x00".format(regex)
            # <foo>
            elif end(b">"):
                return term[1:-1], "[\x20-\x7f]+"

        raise InvalidSyntax(term)

    # .. note:: regex pattern is converted to `bytes`, since all XenStore
    #           values are expected to by bytestrings.
    return dict((name, re.compile("^{0}$".format(t).encode("utf-8")))
                for name, t in map(inner, terms))


def spec(*terms):
    """Decorator, which links a given syntax definition to the wrapped
    function, by updating its ``__doc__`` attribute. The following
    conventions are used:

    =======  ============================================================
    Symbol   Description
    =======  ============================================================
    ``|``    A ``NULL`` (zero) byte.
    <foo>    A string guaranteed not to contain any ``NULL`` bytes.
    <foo|>   Binary data (which may contain zero or more ``NULL`` bytes).
    <foo>|*  Zero or more strings each followed by a trailing ``NULL``.
    <foo>|+  One or more strings each followed by a trailing ``NULL``.
    ?        Reserved value (may not contain ``NULL`` bytes).
    ??       Reserved value (may contain ``NULL`` bytes).
    =======  ============================================================

    .. note::

       According to ``docs/misc/xenstore.txt`` in the current
       implementation reserved values are just empty strings. So for
       example ``"\\x00\\x00\\x00"`` is a valid ``??`` symbol.

    .. todo:: Add validators based on the syntax definition and wrapped
              function signature.
    """
    def decorator(func):
        func.__doc__ += "\n**Syntax**: ``{0}``".format("".join(terms))

        patterns = compile(*terms)
        argspec  = inspect.getargspec(func)
        defaults = zip(reversed(argspec.args),
                       reversed(argspec.defaults or ()))

        @wraps(func)
        def inner(*values):
            for arg, value in chain(zip(argspec.args, values), defaults):
                if arg == "path":
                    validate_path(value)
                elif arg in patterns:
                    validate_spec(patterns[arg], value)

            return func(*values)
        return inner
    return decorator


# Custom validators.


def validate_spec(spec, value):
    """Checks if a given value matches the spec, see :func:`spec` for
    details.

    :param spec: a regular expression to match the value against.
    :param bytes value: a value to check.
    :raises ValueError: when value fails to validate.
    """
    if not spec.match(value):
        raise ValueError(value)


def validate_path(path):
    """Checks if a given path is valid, see :exc:`InvalidPath` for
    details.

    :param bytes path: path to check.
    :raises pyxs.exceptions.InvalidPath: when path fails to validate.
    """
    # Paths longer than 3072 bytes are forbidden; clients specifying
    # relative paths should keep them to within 2048 bytes.
    max_len = 3072 if posixpath.abspath(path) else 2048

    if not (re.match(r"^[a-zA-Z0-9-/_@]+$", path) and
            len(path) <= max_len):
        raise InvalidPath(path)

    # A path is not allowed to have a trailing /, except for the
    # root path.
    if len(path) > 1 and path[-1] == b"/":
        raise InvalidPath(path)
