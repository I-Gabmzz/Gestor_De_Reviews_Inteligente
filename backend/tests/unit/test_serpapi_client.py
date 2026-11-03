from concurrent.futures import ThreadPoolExecutor
import json
import logging
import ssl
import traceback

import httpx
import pytest

from app.core.serpapi_config import SerpApiSettings
from app.services.serpapi_client import SERPAPI_ENDPOINT, SerpApiClient, SerpApiError, _tls_context


TEST_MARKER = "test-only-not-a-credential"
DATA_ID = "0x123:0x456"
PRIVATE_MARKER = "synthetic-private-response"
TOKEN = "synthetic-pagination-token"
LOGGERS = ("httpx", "httpcore", "httpcore.connection", "httpcore.http11", "httpcore.http2", "httpcore.proxy", "httpcore.socks")


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch):
    for name in ("SERPAPI_API_KEY", "SERPAPI_PAGE_SIZE", "SERPAPI_MAX_PAGES", "SERPAPI_TIMEOUT_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setitem(SerpApiSettings.model_config, "env_file", None)


def config(**changes):
    return SerpApiSettings(_env_file=None, serpapi_api_key=TEST_MARKER, **changes)


def body(*, token=None, reviews=None, **extra):
    response = {
        "search_metadata": {"status": "Success", "id": "synthetic-search", "json_endpoint": PRIVATE_MARKER},
        "place_info": {"title": "Establecimiento sintético"},
        "reviews": [{"review_id": "synthetic-review", "rating": 4}] if reviews is None else reviews,
    }
    if token is not None:
        response["serpapi_pagination"] = {"next_page_token": token, "next": "https://untrusted.invalid/"}
    response.update(extra)
    return response


def execute(responses, *, settings=None, **kwargs):
    calls = []

    def handler(request):
        calls.append(request)
        response = responses[len(calls) - 1]
        if isinstance(response, Exception):
            raise response
        return response

    with SerpApiClient(settings or config(), transport=httpx.MockTransport(handler)) as client:
        result = client.fetch_reviews(DATA_ID, **kwargs)
    return result, calls


def test_single_page_contract_native_textless_review_and_safe_repr():
    payload = body(reviews=[{"review_id": "synthetic-review", "user": {"name": PRIVATE_MARKER}, "rating": 5}])
    result, calls = execute([httpx.Response(200, json=payload)])
    assert len(calls) == result.request_count == result.record_count == len(result.pages) == 1
    assert result.stop_reason == "no_next_token"
    assert not result.incomplete and not result.limited
    assert result.place_info == payload["place_info"]
    assert result.first_page_metadata == {"status": "Success", "id": "synthetic-search"}
    assert result.reviews[0].data == payload["reviews"][0]
    assert "snippet" not in result.reviews[0].data
    assert result.pages[0].http_status == 200
    assert result.pages[0].search_status == "Success"
    for value in (result, result.pages[0], result.reviews[0]):
        assert PRIVATE_MARKER not in repr(value)


def test_pagination_keeps_fixed_params_metadata_and_timeouts():
    later = body()
    later.pop("place_info")
    later["search_metadata"]["id"] = "later-search"
    result, calls = execute([
        httpx.Response(200, json=body(token=TOKEN)), httpx.Response(200, json=later),
    ], page_size=2, max_pages=2)
    assert result.request_count == len(calls) == 2
    assert result.record_count == 2 and result.stop_reason == "no_next_token"
    assert result.place_info == {"title": "Establecimiento sintético"}
    assert result.first_page_metadata["id"] == "synthetic-search"
    expected = {
        "engine": "google_maps_reviews", "data_id": DATA_ID, "num": "2", "sort_by": "newestFirst",
        "hl": "es", "output": "json", "async": "false", "no_cache": "false", "api_key": TEST_MARKER,
    }
    for index, request in enumerate(calls):
        assert request.method == "GET"
        assert str(request.url.copy_with(query=None)) == SERPAPI_ENDPOINT
        assert dict(request.url.params) == {**expected, **({"next_page_token": TOKEN} if index else {})}
        assert request.extensions["timeout"] == {"connect": 5, "read": 30, "write": 5, "pool": 5}


@pytest.mark.parametrize("responses,reason,count,incomplete,limited", [
    ([body(reviews=[])], "no_next_token", 1, False, False),
    ([body(reviews=[], token=TOKEN)], "empty_with_token", 1, True, False),
    ([body(token=TOKEN), body(token=TOKEN)], "repeated_token", 2, True, False),
    ([body(token="a"), body(token="b"), body(token="a")], "repeated_token", 3, True, False),
    ([body(token="a"), body(token="b"), body(token="c")], "max_pages", 3, True, True),
])
def test_stops_without_extra_requests(responses, reason, count, incomplete, limited):
    result, calls = execute([httpx.Response(200, json=item) for item in responses])
    assert result.request_count == len(calls) == count
    assert result.stop_reason == reason
    assert result.incomplete is incomplete and result.limited is limited
    assert TOKEN not in repr(result)
    assert all(TOKEN not in repr(page) for page in result.pages)


def test_operation_can_only_reduce_configured_limits_and_does_not_follow_next_url():
    result, calls = execute([httpx.Response(200, json=body(token=TOKEN))], max_pages=1, page_size=1)
    assert len(calls) == 1 and result.limited
    assert result.stop_reason == "max_pages"


@pytest.mark.parametrize("data_id,limits", [
    ("", {}), (None, {}), ("https://untrusted.invalid/", {}), ("0x1:0x2&api_key=other", {}),
    ("0x1:0x2\n", {}), (DATA_ID, {"page_size": 6}), (DATA_ID, {"max_pages": 4}),
    (DATA_ID, {"max_pages": 0}), (DATA_ID, {"page_size": 0}),
    (DATA_ID, {"max_pages": True}), (DATA_ID, {"page_size": 1.0}), (DATA_ID, {"page_size": "1"}),
])
def test_invalid_input_is_rejected_before_network(data_id, limits):
    calls = []
    with SerpApiClient(config(), transport=httpx.MockTransport(lambda request: calls.append(request))) as client:
        with pytest.raises(SerpApiError) as error:
            client.fetch_reviews(data_id, **limits)
    assert error.value.code == "input" and not calls


@pytest.mark.parametrize("status,code", [
    (400, "request"), (401, "credentials"), (403, "forbidden"), (429, "quota"),
    (500, "unavailable"), (503, "unavailable"), (301, "redirect"), (307, "redirect"),
    (302, "redirect"), (404, "request"), (201, "request"),
])
def test_http_errors_are_sanitized_without_retry_or_redirect(status, code):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": TEST_MARKER + PRIVATE_MARKER}, headers={"Location": "https://untrusted.invalid/"})

    with SerpApiClient(config(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SerpApiError) as error:
            client.fetch_reviews(DATA_ID)
    assert error.value.code == code and error.value.http_status == status
    assert error.value.partial_result.request_count == len(calls) == 1
    assert error.value.partial_result.record_count == 0
    assert error.value.partial_result.incomplete
    assert_safe_error(error.value)


def assert_safe_error(error):
    rendered = "".join(traceback.format_exception(error)) + repr(error) + repr(error.partial_result)
    for marker in (TEST_MARKER, PRIVATE_MARKER, TOKEN, "api_key=", "untrusted.invalid"):
        assert marker not in rendered


@pytest.mark.parametrize("exception,code", [
    (httpx.ConnectTimeout, "timeout"), (httpx.ReadTimeout, "timeout"),
    (httpx.WriteTimeout, "timeout"), (httpx.PoolTimeout, "timeout"),
    (httpx.ConnectError, "network"), (httpx.ReadError, "network"),
    (httpx.RemoteProtocolError, "network"),
])
def test_transport_failures_are_sanitized_and_never_retried(exception, code):
    calls = []

    def handler(request):
        calls.append(request)
        raise exception(str(request.url) + PRIVATE_MARKER, request=request)

    with SerpApiClient(config(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SerpApiError) as error:
            client.fetch_reviews(DATA_ID)
    assert error.value.code == code
    assert error.value.partial_result.request_count == len(calls) == 1
    assert_safe_error(error.value)


@pytest.mark.parametrize("payload,code", [
    (None, "invalid_response"), ([], "invalid_response"), ({}, "invalid_response"),
    ({"search_metadata": []}, "invalid_response"),
    ({"error": PRIVATE_MARKER}, "provider_error"),
    (body(search_metadata={"status": "Error"}, error=TEST_MARKER), "provider_error"),
    (body(error=PRIVATE_MARKER), "provider_error"),
    (body(search_metadata={"status": "Processing"}), "pending"),
    (body(search_metadata={"status": "Queued"}), "pending"),
    (body(search_metadata={"status": "Pending"}), "pending"),
    (body(search_metadata={"status": "Unknown"}), "invalid_response"),
    (body(search_metadata={"status": []}), "invalid_response"),
    (body(reviews="wrong"), "invalid_response"),
    (body(reviews=[None]), "invalid_response"),
    (body(reviews=[{}] * 6), "invalid_response"),
    (body(place_info=[]), "invalid_response"),
    (body(serpapi_pagination=[]), "invalid_response"),
    (body(token=3), "invalid_response"), (body(token=" "), "invalid_response"),
    ({"search_metadata": {"status": "Success"}}, "invalid_response"),
])
def test_invalid_or_non_success_json_is_not_a_completed_result(payload, code):
    with SerpApiClient(config(), transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))) as client:
        with pytest.raises(SerpApiError) as error:
            client.fetch_reviews(DATA_ID)
    assert error.value.code == code
    assert error.value.partial_result.request_count == 1
    assert_safe_error(error.value)


def test_invalid_json_is_sanitized():
    with SerpApiClient(config(), transport=httpx.MockTransport(lambda _: httpx.Response(200, text=TEST_MARKER))) as client:
        with pytest.raises(SerpApiError) as error:
            client.fetch_reviews(DATA_ID)
    assert error.value.code == "invalid_response"
    assert_safe_error(error.value)


@pytest.mark.parametrize("failure", [
    httpx.Response(503, text=PRIVATE_MARKER),
    httpx.ReadTimeout(TEST_MARKER),
    httpx.Response(200, json=body(search_metadata={"status": "Error"})),
    httpx.Response(200, text="not-json"),
])
def test_failure_after_valid_page_preserves_partial_data(failure):
    calls = []
    responses = [httpx.Response(200, json=body(token=TOKEN)), failure]

    def handler(request):
        calls.append(request)
        response = responses[len(calls) - 1]
        if isinstance(response, Exception):
            raise response
        return response

    with SerpApiClient(config(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SerpApiError) as error:
            client.fetch_reviews(DATA_ID)
    partial = error.value.partial_result
    assert partial.request_count == len(calls) == 2
    assert partial.record_count == len(partial.pages) == 1
    assert partial.incomplete and not partial.limited and partial.stop_reason == "error"
    assert partial.place_info == {"title": "Establecimiento sintético"}
    assert partial.reviews[0].data["rating"] == 4
    assert_safe_error(error.value)


@pytest.mark.parametrize("fail", [False, True])
def test_httpx_and_httpcore_logs_never_expose_transport_data(caplog, fail):
    caplog.set_level(logging.DEBUG)
    levels = {name: logging.getLogger(name).level for name in LOGGERS}

    def handler(request):
        for name in LOGGERS:
            logger = logging.getLogger(name)
            logger.debug("request=%s body=%s token=%s", request.url, PRIVATE_MARKER, TOKEN)
            logger.info("request=%s", request.url)
            try:
                raise ValueError(str(request.url) + PRIVATE_MARKER)
            except ValueError:
                logger.debug("transport exception", exc_info=True)
        # Otro hilo no pierde sus logs por la consulta actual.
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(logging.getLogger("httpx").info, "unrelated-request").result()
        if fail:
            raise httpx.ConnectError(str(request.url), request=request)
        return httpx.Response(200, json=body())

    with SerpApiClient(config(), transport=httpx.MockTransport(handler)) as client:
        assert TEST_MARKER not in repr(client)
        if fail:
            with pytest.raises(SerpApiError) as error:
                client.fetch_reviews(DATA_ID)
            assert_safe_error(error.value)
        else:
            client.fetch_reviews(DATA_ID)
    assert "unrelated-request" in caplog.text
    for name in LOGGERS:
        assert logging.getLogger(name).level == levels[name]
    logging.getLogger("httpx").info("after-request")
    assert "after-request" in caplog.text
    for marker in (TEST_MARKER, PRIVATE_MARKER, TOKEN, "api_key="):
        assert marker not in caplog.text
        assert all(marker not in repr(record.__dict__) for record in caplog.records)


def test_close_and_context_manager_release_transport_on_error():
    class TrackingTransport(httpx.MockTransport):
        closed = False

        def close(self):
            self.closed = True

    transport = TrackingTransport(lambda _: httpx.Response(500))
    with pytest.raises(SerpApiError):
        with SerpApiClient(config(), transport=transport) as client:
            client.fetch_reviews(DATA_ID)
    assert transport.closed
    client.close()
    with pytest.raises(SerpApiError) as error:
        client.fetch_reviews(DATA_ID)
    assert error.value.code == "closed"


def test_explicit_tls_context_ignores_inherited_keylog(monkeypatch, tmp_path):
    keylog = tmp_path / "must-not-exist.keys"
    monkeypatch.setenv("SSLKEYLOGFILE", str(keylog))
    context = _tls_context()
    assert context.keylog_filename is None
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    assert not keylog.exists()


def test_default_transport_uses_zero_retries_and_no_environment_proxies(monkeypatch):
    captured = {}

    def transport(**kwargs):
        captured.update(kwargs)
        return httpx.MockTransport(lambda _: httpx.Response(200, json=body()))

    monkeypatch.setattr(httpx, "HTTPTransport", transport)
    with SerpApiClient(config()) as client:
        assert client.fetch_reviews(DATA_ID).request_count == 1
    assert captured["retries"] == 0 and captured["trust_env"] is False
    assert captured["verify"].keylog_filename is None


def test_configured_absolute_limits_allow_five_pages_of_twenty_records():
    responses = [httpx.Response(200, json=body(reviews=[{}] * 20, token=f"synthetic-{index}")) for index in range(5)]
    result, calls = execute(responses, settings=config(serpapi_page_size=20, serpapi_max_pages=5))
    assert result.request_count == len(calls) == 5
    assert result.record_count == 100 and result.limited
    assert all(request.url.params["num"] == "20" for request in calls)


def test_separate_operations_start_without_previous_token():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=body(token=TOKEN))

    with SerpApiClient(config(), transport=httpx.MockTransport(handler)) as client:
        first = client.fetch_reviews(DATA_ID, max_pages=1)
        second = client.fetch_reviews(DATA_ID, max_pages=1)
    assert first.request_count == second.request_count == 1
    assert len(calls) == 2
    assert all("next_page_token" not in request.url.params for request in calls)


@pytest.mark.parametrize("invalid_page", [1, 2], ids=["first-page", "second-page"])
@pytest.mark.parametrize("invalid_char", ["\ud800", "\udfff"], ids=["high-surrogate", "low-surrogate"])
def test_unencodable_pagination_token_preserves_only_validated_pages_and_is_private(
    caplog, invalid_page, invalid_char
):
    caplog.set_level(logging.DEBUG)
    invalid_token = f"{TEST_MARKER}:{PRIVATE_MARKER}:{TOKEN}:{invalid_char}"
    first = body(token=TOKEN, reviews=[{"review_id": "validated-review", "rating": 5}])
    rejected = body(
        token=invalid_token, reviews=[{"review_id": PRIVATE_MARKER}],
        place_info={"title": PRIVATE_MARKER},
        search_metadata={"status": "Success", "id": PRIVATE_MARKER},
    )
    calls = []

    def handler(request):
        calls.append(request)
        assert len(calls) <= invalid_page  # Ninguna continuación ni reintento tras el rechazo.
        if len(calls) < invalid_page:
            return httpx.Response(200, json=first)
        for name in LOGGERS:
            logging.getLogger(name).info("request=%s", request.url)
            logging.getLogger(name).debug("continuation=%s", invalid_token)
        # JSON recibido puede contener un sustituto escapado aunque no sea UTF-8 codificable.
        return httpx.Response(200, content=json.dumps(rejected, ensure_ascii=True).encode("ascii"))

    with SerpApiClient(config(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SerpApiError) as error:
            client.fetch_reviews(DATA_ID)

    assert error.value.code == "invalid_response" and error.value.http_status == 200
    partial = error.value.partial_result
    assert partial is not None
    assert partial.request_count == len(calls) == invalid_page
    assert len(partial.pages) == partial.record_count == invalid_page - 1
    assert partial.incomplete and not partial.limited and partial.stop_reason == "error"
    assert [review.data for review in partial.reviews] == (first["reviews"] if invalid_page == 2 else [])
    assert partial.place_info == (first["place_info"] if invalid_page == 2 else None)
    assert partial.first_page_metadata == (
        {"status": "Success", "id": "synthetic-search"} if invalid_page == 2 else None
    )
    assert all("next_page_token" not in request.url.params for request in calls[:1])
    if invalid_page == 2:
        assert calls[1].url.params["next_page_token"] == TOKEN
    assert_safe_error(error.value)
    representations = [str(error.value), repr(error.value), str(partial), repr(partial)]
    representations.extend(repr(page) for page in partial.pages)
    representations.append("".join(traceback.format_exception(error.value)))
    for marker in (invalid_token, TEST_MARKER, PRIVATE_MARKER, TOKEN, "api_key="):
        assert all(marker not in value for value in representations)
        assert marker not in caplog.text
        assert all(marker not in repr(record.__dict__) for record in caplog.records)


@pytest.mark.parametrize("token", ["página-次-☕", "continuación-😀"])
def test_utf8_pagination_token_round_trips_without_changing_parameters(token):
    result, calls = execute([
        httpx.Response(200, json=body(token=token)), httpx.Response(200, json=body()),
    ])
    assert result.request_count == len(calls) == 2
    assert result.record_count == len(result.pages) == 2
    assert result.stop_reason == "no_next_token" and not result.incomplete and not result.limited
    assert calls[1].url.params["next_page_token"] == token
    assert dict(calls[1].url.params) == {**dict(calls[0].url.params), "next_page_token": token}
    assert all(str(request.url.copy_with(query=None)) == SERPAPI_ENDPOINT for request in calls)
