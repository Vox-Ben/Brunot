"""Tests for HTTP client (mocked; no real network)."""

from unittest.mock import MagicMock, patch

from brunot.http_client import send_request


@patch("brunot.http_client.httpx.Client")
def test_send_request_returns_normalized_response(mock_client_class: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.reason_phrase = "Created"
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.text = '{"id":1}'
    mock_resp.elapsed.total_seconds = MagicMock(return_value=0.05)

    mock_instance = MagicMock()
    mock_instance.request.return_value = mock_resp
    mock_client_class.return_value.__enter__.return_value = mock_instance
    mock_client_class.return_value.__exit__.return_value = None

    out = send_request(
        "post",
        "https://api.example.com/items",
        headers={"X-Test": "1"},
        params={"page": "2"},
        body='{"a":true}',
    )

    assert out.status_code == 201
    assert out.reason_phrase == "Created"
    assert out.headers["content-type"] == "application/json"
    assert out.body == '{"id":1}'
    assert abs(out.elapsed_ms - 50.0) < 0.01

    mock_client_class.assert_called_once()
    assert mock_client_class.call_args.kwargs.get("trust_env") is False

    mock_instance.request.assert_called_once()
    call_kw = mock_instance.request.call_args.kwargs
    assert call_kw["method"] == "POST"
    assert call_kw["url"] == "https://api.example.com/items"
    assert call_kw["headers"] == {"X-Test": "1"}
    assert call_kw["params"] == {"page": "2"}
    assert call_kw["content"] == '{"a":true}'
