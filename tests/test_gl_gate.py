"""Tests for the CI gate that forbids silently skipping the render tests.

The gate exists so a rendering regression cannot hide behind a skip. If the
gate itself broke, it would also fail silently -- so it gets its own tests.
"""

import pytest

from tests.conftest import REQUIRE_GL_ENV, gl_is_required, resolve_gl_available


def test_gl_is_required_recognizes_truthy_values():
    for value in ("1", "true", "TRUE", "yes", " 1 "):
        assert gl_is_required({REQUIRE_GL_ENV: value}) is True, value


def test_gl_is_required_recognizes_falsy_and_absent():
    for value in ("", "0", "false", "no", "off"):
        assert gl_is_required({REQUIRE_GL_ENV: value}) is False, value
    assert gl_is_required({}) is False


def test_missing_gl_is_a_skip_when_not_required():
    """Default behavior: no backend simply reports False, tests skip."""
    assert resolve_gl_available(probe=lambda: (False, "boom"), environ={}) is False


def test_missing_gl_fails_the_run_when_required():
    """The whole point of the gate.

    pytest.fail raises Failed, which derives from BaseException rather than
    Exception, so catch BaseException here.
    """
    with pytest.raises(BaseException) as exc_info:
        resolve_gl_available(
            probe=lambda: (False, "no GL context"),
            environ={REQUIRE_GL_ENV: "1"},
        )
    assert type(exc_info.value).__name__ == "Failed"
    message = str(exc_info.value)
    assert REQUIRE_GL_ENV in message
    assert "no GL context" in message, "the underlying reason must be surfaced"


def test_working_gl_passes_when_required():
    assert resolve_gl_available(
        probe=lambda: (True, ""), environ={REQUIRE_GL_ENV: "1"}
    ) is True
