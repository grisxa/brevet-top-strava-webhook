# noqa: D100, pylint: disable=missing-function-docstring,missing-module-docstring
from unittest.mock import patch

from main import init_logger


@patch("google.cloud.logging.Client")
def test_logger(mock_logger):  # noqa: D103
    # given
    mock_logger.return_value.get_default_handler.return_value = None
    mock_logger.return_value.setup_logging.return_value = None

    # when
    init_logger()

    # then
    mock_logger.return_value.get_default_handler.assert_called_once()
    mock_logger.return_value.setup_logging.assert_called_once()
