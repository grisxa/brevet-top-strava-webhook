# noqa: D100, pylint: disable=missing-function-docstring,missing-module-docstring
from unittest.mock import patch

import pytest
from werkzeug.exceptions import Forbidden

from main import enqueue


@pytest.fixture(autouse=True)
def env(monkeypatch):  # noqa: D103
    monkeypatch.setenv("STRAVA", '{"subscription_id": "12345"}')
    monkeypatch.setenv("GCLOUD_PROJECT", "project")
    monkeypatch.setenv("PUBSUB_TOPIC", "topic")


def test_no_secret_exception(monkeypatch):  # noqa: D103
    # given
    monkeypatch.delenv("STRAVA", raising=False)

    # when
    with pytest.raises(TypeError) as error:
        enqueue(None)

    # then
    assert "JSON object" in str(error)


def test_verify_none_exception():  # noqa: D103
    # when
    with pytest.raises(TypeError) as error:
        enqueue(None)

    # then
    assert "not subscriptable" in str(error)


def test_verify_empty_exception():  # noqa: D103
    # given
    data = {}

    # when
    with pytest.raises(KeyError) as error:
        enqueue(data)

    # then
    assert "subscription_id" in str(error)


def test_verify_unknown_exception():  # noqa: D103
    # given
    data = {"any": "value"}

    # when
    with pytest.raises(KeyError) as error:
        enqueue(data)

    # then
    assert "subscription_id" in str(error)


def test_wrong_subscription_exception():  # noqa: D103
    # given
    data = {"subscription_id": "67890"}

    # when
    with pytest.raises(Forbidden) as error:
        enqueue(data)

    # then
    assert "Forbidden" in str(error)


def test_verify_wrong_action(caplog):  # noqa: D103
    # given
    data = {"subscription_id": "12345", "aspect_type": "test"}

    # then
    assert enqueue(data) == "OK"
    assert "Ignoring action test" in caplog.messages


@patch("json.dumps", return_value="data json")
@patch("google.cloud.pubsub.PublisherClient")
def test_verify_create(mock_publisher, mock_json, caplog):  # noqa: D103
    # given
    caplog.set_level("DEBUG")
    data = {
        "subscription_id": "12345",
        "aspect_type": "create",
        "owner_id": "123",
        "object_id": "456",
    }
    mock_publisher.return_value.topic_path.return_value = "test/topic"

    # then
    assert enqueue(data) == "OK"
    assert "Athlete 123 creates 456" in caplog.messages
    mock_publisher.return_value.topic_path.assert_called_once_with("project", "topic")
    mock_publisher.return_value.publish.assert_called_once_with(
        "test/topic", b"data json"
    )
    mock_json.assert_called_once()


@patch("json.dumps", return_value="data json")
@patch("google.cloud.pubsub.PublisherClient")
def test_verify_update(mock_publisher, mock_json, caplog):  # noqa: D103
    # given
    mock_json.reset_mock()
    caplog.set_level("DEBUG")
    data = {
        "subscription_id": "12345",
        "aspect_type": "update",
        "owner_id": "123",
        "object_id": "456",
        "updates": {"type": "Ride"},
    }
    mock_publisher.return_value.topic_path.return_value = "test/topic"

    # then
    assert enqueue(data) == "OK"
    assert "Athlete 123 updates 456" in caplog.messages
    mock_publisher.return_value.topic_path.assert_called_once_with("project", "topic")
    mock_publisher.return_value.publish.assert_called_once_with(
        "test/topic", b"data json"
    )
    mock_json.assert_called_once()


def test_verify_not_ride(caplog):  # noqa: D103
    # given
    data = {
        "subscription_id": "12345",
        "aspect_type": "update",
        "updates": {"type": "test"},
    }

    # then
    assert enqueue(data) == "OK"
    assert "Ignoring action update" in caplog.messages


def test_verify_title(caplog):  # noqa: D103
    # given
    data = {
        "subscription_id": "12345",
        "aspect_type": "update",
        "updates": {"title": "test"},
    }

    # then
    assert enqueue(data) == "OK"
    assert "Ignoring action update" in caplog.messages
