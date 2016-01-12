import string

import pytest

from pyxs.exceptions import InvalidPath, InvalidPermission
from pyxs.helpers import validate_path, validate_watch_path, validate_perms


def test_validate_path():
    # a) max length is bounded by 3072 for absolute path and 2048 for
    #    relative ones.
    with pytest.raises(InvalidPath):
        validate_path("/foo/bar" * 3072)

    with pytest.raises(InvalidPath):
        validate_path("foo/bar" * 2048)

    # b) ASCII alphanumerics and -/_@ only!
    for char in string.punctuation:
        if char in "-/_@":
            continue

        with pytest.raises(InvalidPath):
            validate_path("/foo" + char)

    # c) no trailing / -- except for root path.
    with pytest.raises(InvalidPath):
        validate_path("/foo/")

    # d) no //'s!.
    with pytest.raises(InvalidPath):
        validate_path("/foo//bar")

    try:
        validate_path("/")
    except InvalidPath as p:
        pytest.fail("{0} is prefectly valid, baby :)".format(p.args))


def test_validate_watch_path():
    # a) ordinary path should be checked with `validate_path()`
    with pytest.raises(InvalidPath):
        validate_watch_path("/foo/")

    with pytest.raises(InvalidPath):
        validate_watch_path("/fo\x07o")

    with pytest.raises(InvalidPath):
        validate_watch_path("/$/foo")

    # b) special path options are limited to `@introduceDomain` and
    #    `@releaseDomain`.
    with pytest.raises(InvalidPath):
        validate_watch_path("@foo")

    try:
        validate_watch_path("@introduceDomain")
        validate_watch_path("@releaseDomain")
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
        validate_perms("w0 r0 b0 n0".split())
        validate_perms(["w999999"])  # valid, even though it overflows int32.
    except InvalidPermission as p:
        pytest.fail("{0} is prefectly valid, baby :)".format(p.args))
