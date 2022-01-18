# noqa: D100, pylint: disable=missing-function-docstring,missing-module-docstring
import pytest
from werkzeug.exceptions import Unauthorized, BadRequest

from main import verify


@pytest.fixture(autouse=True)
def env(monkeypatch):  # noqa: D103
    monkeypatch.setenv("STRAVA", '{"verify_token": "SECRET"}')


def test_no_secret_exception(monkeypatch):  # noqa: D103
    # given
    monkeypatch.delenv("STRAVA", raising=False)

    # when
    with pytest.raises(TypeError) as error:
        verify(None)

    # then
    assert "JSON object" in str(error)


def test_verify_none_exception():  # noqa: D103
    # when
    with pytest.raises(TypeError) as error:
        verify(None)

    # then
    assert "not iterable" in str(error)


def test_verify_empty():  # noqa: D103
    # given
    data = {}

    # when
    with pytest.raises(BadRequest) as error:
        verify(data)

    # then
    assert "BadRequest" in str(error)


def test_verify_unknown():  # noqa: D103
    # given
    data = {"any": "value"}

    # when
    with pytest.raises(BadRequest) as error:
        verify(data)

    # then
    assert "BadRequest" in str(error)


def test_verify_wrong_mode_exception():  # noqa: D103
    # given
    data = {"hub.mode": "test"}

    # when
    with pytest.raises(Unauthorized) as error:
        verify(data)

    # then
    assert "Unauthorized" in str(error)


def test_verify_wrong_token_exception():  # noqa: D103
    # given
    data = {"hub.mode": "subscribe", "hub.verify_token": "wrong"}

    # when
    with pytest.raises(Unauthorized) as error:
        verify(data)

    # then
    assert "Unauthorized" in str(error)


def test_verify_no_challenge_exception():  # noqa: D103
    # given
    data = {"hub.mode": "subscribe", "hub.verify_token": "SECRET"}

    # when
    with pytest.raises(KeyError) as error:
        verify(data)

    # then
    assert "hub.challenge" in str(error)


def test_verify_challenge_ok():  # noqa: D103
    # given
    data = {
        "hub.mode": "subscribe",
        "hub.verify_token": "SECRET",
        "hub.challenge": "ok",
    }

    # then
    assert verify(data) == {"hub.challenge": "ok"}
