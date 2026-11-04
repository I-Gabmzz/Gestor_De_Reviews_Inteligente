import logging
import httpx
import pytest
from app.services.google_maps_link_service import GoogleMapsLinkError, GoogleMapsLinkResolver

BUSINESS = "0xabc:0x123"
FULL = f"https://www.google.com/maps/place/Synthetic/data=!4m2!1s{BUSINESS}!1b1"


def resolver(handler):
    return GoogleMapsLinkResolver(transport=httpx.MockTransport(handler))


def test_complete_link_never_sends_http():
    def forbidden(_): raise AssertionError("Unneeded HTTP")
    assert resolver(forbidden).resolve(FULL) == BUSINESS
    assert resolver(forbidden).resolve(f"https://www.google.com/maps?ftid={BUSINESS}") == BUSINESS


@pytest.mark.parametrize("value", [
    "http://www.google.com/maps", "https://localhost/maps", "https://127.0.0.1/maps",
    "https://www.google.com.evil.invalid/maps", "https://private@www.google.com/maps",
    "https://www.google.com:8000/maps", "https://www.google.com/search?q=maps",
    "file:///private/maps", "https://maps.app.goo.gl/a\\b", "https://maps.app.goo.gl/a\nb",
])
def test_invalid_or_untrusted_input_is_not_requested(value):
    calls = []
    def handle(request): calls.append(request); return httpx.Response(200)
    with pytest.raises(GoogleMapsLinkError):
        resolver(handle).resolve(value)
    assert not calls


def test_short_link_uses_fixed_google_destinations_without_following_external_redirect():
    calls = []
    def valid(request):
        calls.append(request)
        return httpx.Response(302, headers={"Location": FULL})
    assert resolver(valid).resolve("https://maps.app.goo.gl/Synthetic") == BUSINESS
    assert len(calls) == 1
    calls.clear()
    def unsafe(request):
        calls.append(request)
        return httpx.Response(302, headers={"Location": "https://127.0.0.1/private"})
    with pytest.raises(GoogleMapsLinkError):
        resolver(unsafe).resolve("https://maps.app.goo.gl/Synthetic")
    assert len(calls) == 1


def test_redirect_loop_and_unsupported_result_are_bounded():
    calls = []
    def loop(request):
        calls.append(request)
        return httpx.Response(302, headers={"Location": f"https://maps.app.goo.gl/next{len(calls)}"})
    with pytest.raises(GoogleMapsLinkError):
        resolver(loop).resolve("https://maps.app.goo.gl/Synthetic")
    assert len(calls) == 4


def test_transport_errors_and_debug_logs_do_not_expose_request_url(caplog):
    marker = "synthetic-private-link-marker"
    url = f"https://maps.app.goo.gl/{marker}"
    caplog.set_level(logging.DEBUG)
    def timeout(request): raise httpx.ReadTimeout(marker, request=request)
    with pytest.raises(GoogleMapsLinkError) as error:
        resolver(timeout).resolve(url)
    assert marker not in str(error.value) and marker not in caplog.text


def test_ambiguous_native_identity_is_rejected():
    with pytest.raises(GoogleMapsLinkError):
        resolver(lambda _: httpx.Response(200)).resolve(FULL + "!1s0xabc:0x456!1b1")
