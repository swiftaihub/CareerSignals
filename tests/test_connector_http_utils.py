from __future__ import annotations

import logging

import requests

from src.connectors.http_utils import safe_get_json


class FailingSession:
    def get(self, *_args, **_kwargs):
        raise requests.HTTPError(
            "401 for https://connector.example/search?api_key=exception-secret"
        )


class InvalidJsonResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self):
        raise ValueError("response contained payload-secret")


class InvalidJsonSession:
    def get(self, *_args, **_kwargs):
        return InvalidJsonResponse()


def test_request_exception_log_omits_query_credentials_and_exception_message(caplog) -> None:
    caplog.set_level(logging.WARNING, logger="src.connectors.http_utils")

    result = safe_get_json(
        FailingSession(),  # type: ignore[arg-type]
        "https://user:url-secret@connector.example/search?api_key=url-secret#fragment",
        params={"api_key": "params-secret"},
        headers={"Authorization": "Bearer header-secret"},
        source_name="test-source",
    )

    assert result is None
    message = caplog.text
    assert "test-source request failed for https://connector.example (HTTPError)" in message
    for secret in (
        "exception-secret",
        "url-secret",
        "params-secret",
        "header-secret",
        "api_key",
        "fragment",
    ):
        assert secret not in message


def test_invalid_json_log_omits_url_query_and_decoder_message(caplog) -> None:
    caplog.set_level(logging.WARNING, logger="src.connectors.http_utils")

    result = safe_get_json(
        InvalidJsonSession(),  # type: ignore[arg-type]
        "https://connector.example/search?token=url-secret",
        source_name="test-source",
    )

    assert result is None
    assert "test-source returned invalid JSON for https://connector.example (ValueError)" in caplog.text
    assert "payload-secret" not in caplog.text
    assert "url-secret" not in caplog.text
