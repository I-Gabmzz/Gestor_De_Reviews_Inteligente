"""Resolver enlaces públicos de Maps sin consultar SerpApi ni descargar páginas."""

import re
from urllib.parse import parse_qs, unquote, urljoin, urlsplit
import httpx
from app.services.serpapi_client import _IN_SERPAPI_REQUEST, _protect_transport_logs, _tls_context


class GoogleMapsLinkError(ValueError):
    pass


def _validated_url(value: str) -> str:
    try:
        if (not isinstance(value, str) or len(value) > 4096
                or any(ord(char) < 33 or ord(char) == 127 for char in value) or "\\" in value):
            raise ValueError
        url = urlsplit(value)
        value.encode("utf-8")
        if url.scheme != "https" or url.username is not None or url.password is not None or url.port not in (None, 443):
            raise ValueError
        host = url.hostname
        if host == "maps.app.goo.gl":
            valid_path = re.fullmatch(r"/[A-Za-z0-9_-]+/?", url.path) is not None
        elif host == "goo.gl":
            valid_path = re.fullmatch(r"/maps/[A-Za-z0-9_-]+/?", url.path) is not None
        elif host in {"www.google.com", "google.com", "maps.google.com"}:
            valid_path = url.path == "/maps" or url.path.startswith("/maps/")
        else:
            valid_path = False
        if not valid_path:
            raise ValueError
        return value
    except (ValueError, TypeError, UnicodeError):
        raise GoogleMapsLinkError("Pega un enlace HTTPS de Google Maps, usando Compartir y Copiar enlace.") from None


def _identifier(value: str) -> str | None:
    url = urlsplit(value)
    if url.hostname not in {"www.google.com", "google.com", "maps.google.com"}:
        return None
    query = parse_qs(url.query)
    candidates = [unquote(url.path), *query.get("data", [])]
    ids = set(re.findall(r"!1s(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)(?=!|/|$)", " ".join(candidates)))
    for item in query.get("ftid", []):
        if re.fullmatch(r"0x[0-9a-fA-F]+:0x[0-9a-fA-F]+", item):
            ids.add(item)
    if len(ids) > 1:
        raise GoogleMapsLinkError("El enlace identifica varias fichas. Copia el enlace de un solo establecimiento.")
    return next(iter(ids)) if ids else None


class GoogleMapsLinkResolver:
    def __init__(self, *, transport: httpx.BaseTransport | None = None):
        self.transport = transport

    def resolve(self, value: str) -> str:
        current = _validated_url(value.strip())
        identifier = _identifier(current)
        if identifier:
            return identifier
        _protect_transport_logs()
        private = _IN_SERPAPI_REQUEST.set(True)
        try:
            transport = self.transport or httpx.HTTPTransport(verify=_tls_context(), trust_env=False, retries=0)
            with httpx.Client(transport=transport, trust_env=False, follow_redirects=False,
                              timeout=httpx.Timeout(8, connect=5)) as client:
                seen = set()
                for _ in range(4):
                    if current in seen:
                        break
                    seen.add(current)
                    with client.stream("GET", current) as response:
                        if response.status_code not in (301, 302, 303, 307, 308):
                            break
                        location = response.headers.get("location")
                        if not location:
                            break
                        # Validar CADA destino antes de enviar la siguiente solicitud.
                        current = _validated_url(urljoin(current, location))
                    identifier = _identifier(current)
                    if identifier:
                        return identifier
        except (httpx.HTTPError, httpx.InvalidURL):
            raise GoogleMapsLinkError("No pudimos abrir el enlace de Google Maps. Revisa el enlace e inténtalo de nuevo.") from None
        finally:
            _IN_SERPAPI_REQUEST.reset(private)
        raise GoogleMapsLinkError("No pudimos identificar la ficha. Ábrela en Google Maps y copia su enlace completo.")
