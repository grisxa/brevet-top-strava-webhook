# noqa: D100, pylint: disable=missing-function-docstring,missing-module-docstring
from unittest.mock import patch

import pytest
from flask import Request, Flask
from werkzeug.datastructures import ImmutableMultiDict
from werkzeug.exceptions import BadRequest, MethodNotAllowed

from main import strava_webhook


@pytest.fixture(autouse=True)
def mock_logger():  # noqa: D103
    with patch("main.init_logger", return_value=None) as logger:
        yield logger


@pytest.fixture(autouse=True)
def mock_flask():  # noqa: D103
    app = Flask(__name__)
    with app.test_client() as client:
        yield client


@pytest.fixture
def environ_get():  # noqa: D103
    return {"REQUEST_METHOD": "GET", "QUERY_STRING": "key=value"}


@pytest.fixture
def environ_post():  # noqa: D103
    return {"REQUEST_METHOD": "POST"}


@pytest.fixture
def environ_put():  # noqa: D103
    return {"REQUEST_METHOD": "PUT"}


@patch("main.verify", return_value="get ok")
def test_main_get(  # noqa: D103
    mock_verify, environ_get: dict  # pylint: disable=redefined-outer-name
):
    # given
    req = Request(environ_get)
    expected = ImmutableMultiDict([("key", "value")])

    # when
    res = strava_webhook(req)

    # then
    assert res == "get ok"
    mock_verify.assert_called_once_with(expected)


@patch("main.verify", side_effect=KeyError("missing"))
def test_main_get_exception(  # noqa: D103
    mock_verify,  # pylint: disable=unused-argument
    caplog,
    environ_get: dict,  # pylint: disable=redefined-outer-name
):
    # given
    req = Request(environ_get)

    # when
    with pytest.raises(BadRequest) as error:
        strava_webhook(req)

    # then
    assert "BadRequest" in str(error)
    assert "missing" in caplog.text


@patch("flask.Request.get_json")
@patch("main.enqueue", return_value="post ok")
def test_main_post(  # noqa: D103
    mock_enqueue, mock_json, environ_post: dict  # pylint: disable=redefined-outer-name
):
    # given
    req = Request(environ_post)
    data = {"key": "value"}
    mock_json.return_value = data

    # when
    res = strava_webhook(req)

    # then
    assert res == "post ok"
    mock_enqueue.assert_called_once_with(data)
    mock_json.assert_called()


def test_main_put(
    environ_put: dict,
):  # noqa: D103, pylint: disable=redefined-outer-name
    # given
    req = Request(environ_put)

    # when
    with pytest.raises(MethodNotAllowed) as error:
        strava_webhook(req)

    # then
    assert "MethodNotAllowed" in str(error)
