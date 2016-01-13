import string

import pytest

from pyxs.exceptions import InvalidPath, InvalidPermission
from pyxs.helpers import validate_path, validate_watch_path, validate_perms


def test_validate_path():
    # a) max length is bounded by 3072 for absolute path and 2048 for
    #    relative ones.
    with pytest.raises(InvalidPath):
        validate_path(b"/foo/bar" * 3072)

    with pytest.raises(InvalidPath):
        validate_path(b"foo/bar" * 2048)

    # b) ASCII alphanumerics and -/_@ only!
    for char in string.punctuation:
        if char in "-/_@":
            continue

        with pytest.raises(InvalidPath):
            validate_path(b"/foo" + char.encode())

    # c) no trailing / -- except for root path.
    with pytest.raises(InvalidPath):
        validate_path(b"/foo/")

    # d) no //'s!.
    with pytest.raises(InvalidPath):
        validate_path(b"/foo//bar")

    # e) OK-case.
    validate_path(b"/")


def test_validate_watch_path():
    # a) ordinary path should be checked with `validate_path()`
    with pytest.raises(InvalidPath):
        validate_watch_path(b"/foo/")

    with pytest.raises(InvalidPath):
        validate_watch_path(b"/fo\x07o")

    with pytest.raises(InvalidPath):
        validate_watch_path(b"/$/foo")

    # b) special path options are limited to `@introduceDomain` and
    #    `@releaseDomain`.
    with pytest.raises(InvalidPath):
        validate_watch_path(b"@foo")

    # c) OK-case.
    validate_watch_path(b"@introduceDomain")
    validate_watch_path(b"@releaseDomain")


def test_validate_perms():
    # A valid permission has a form `[wrbn]:digits:`.
    with pytest.raises(InvalidPermission):
        validate_perms([b"foo"])

    with pytest.raises(InvalidPermission):
        validate_perms([b"f20"])

    with pytest.raises(InvalidPermission):
        validate_perms([b"r-20"])

    # OK-case
    validate_perms(b"w0 r0 b0 n0".split())
    validate_perms([b"w999999"])  # valid, even though it overflows int32.
