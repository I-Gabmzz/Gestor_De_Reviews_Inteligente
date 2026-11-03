"""Cliente síncrono acotado, sin persistencia, endpoints ni procesamiento de IA."""

from contextvars import ContextVar
import logging
import re
import ssl
from threading import Lock
from types import TracebackType
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.serpapi_config import SerpApiSettings
from app.schemas.serpapi import SerpApiPage, SerpApiResult, SerpApiReview, StopReason


SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
_IN_SERPAPI_REQUEST: ContextVar[bool] = ContextVar("serpapi_transport_private", default=False)
_LOG_FILTER_LOCK = Lock()


class _TransportPrivacyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # No se formatea el registro: podría contener URL, cuerpo o excepción.
        return not _IN_SERPAPI_REQUEST.get()


_PRIVACY_FILTER = _TransportPrivacyFilter()


def _protect_transport_logs() -> None:
    """Filtro permanente, limitado al contexto actual; no cambia niveles globales.

    Los filtros del logger padre no se heredan. Se instalan en los emisores de
    HTTPX 0.28 / HTTPCore 1.x, además de los descendientes ya registrados.
    """
    with _LOG_FILTER_LOCK:
        names = {
            "httpx", "httpcore", "httpcore.connection", "httpcore.http11",
            "httpcore.http2", "httpcore.proxy", "httpcore.socks",
        }
        names.update(
            name for name in logging.Logger.manager.loggerDict.copy()
            if name.startswith(("httpx.", "httpcore."))
        )
        for name in names:
            logger = logging.getLogger(name)
            if _PRIVACY_FILTER not in logger.filters:
                logger.addFilter(_PRIVACY_FILTER)


_MESSAGES = {
    "configuration": "La configuración de SerpApi no está disponible o no es válida",
    "input": "El identificador o los límites de consulta no son válidos",
    "closed": "El cliente de SerpApi está cerrado",
    "request": "SerpApi rechazó la solicitud",
    "credentials": "SerpApi rechazó la credencial",
    "forbidden": "SerpApi no autorizó el acceso",
    "quota": "SerpApi informó un límite de cuota",
    "unavailable": "SerpApi no está disponible temporalmente",
    "redirect": "SerpApi devolvió una redirección no permitida",
    "timeout": "SerpApi excedió el tiempo de espera",
    "network": "No fue posible completar la conexión con SerpApi",
    "invalid_response": "SerpApi devolvió una respuesta no válida",
    "provider_error": "SerpApi informó un error de búsqueda",
    "pending": "La búsqueda de SerpApi continúa pendiente; no se realizará sondeo",
}


class SerpApiError(Exception):
    """Sólo mensaje fijo, código estable y parcial interno; sin request/response."""

    def __init__(self, code: str, *, http_status: int | None = None) -> None:
        self.code = code
        self.http_status = http_status
        self.partial_result: SerpApiResult | None = None
        super().__init__(_MESSAGES[code])


def _tls_context() -> ssl.SSLContext:
    # create_default_context() habilita key logging si hereda SSLKEYLOGFILE.
    # La construcción explícita conserva verificación TLS sin leer esa variable.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_default_certs()
    return context


class SerpApiClient:
    def __init__(
        self, config: SerpApiSettings | None = None, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        try:
            self._config = config if config is not None else SerpApiSettings()
        except ValidationError:
            raise SerpApiError("configuration") from None
        _protect_transport_logs()
        # HTTPTransport(retries=0) explícito; MockTransport permite pruebas offline.
        actual_transport = transport if transport is not None else httpx.HTTPTransport(
            verify=_tls_context(), retries=0, trust_env=False
        )
        self._client = httpx.Client(
            transport=actual_transport,
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(self._config.serpapi_timeout_seconds, connect=5, write=5, pool=5),
        )

    def __enter__(self) -> "SerpApiClient":
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None,
        exc: BaseException | None, traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        private_context = _IN_SERPAPI_REQUEST.set(True)
        try:
            self._client.close()
        finally:
            _IN_SERPAPI_REQUEST.reset(private_context)

    def fetch_reviews(
        self, data_id: str, *, page_size: int | None = None, max_pages: int | None = None
    ) -> SerpApiResult:
        page_size = self._limit(page_size, self._config.serpapi_page_size)
        max_pages = self._limit(max_pages, self._config.serpapi_max_pages)
        if not isinstance(data_id, str) or re.fullmatch(r"0x[0-9a-fA-F]+:0x[0-9a-fA-F]+", data_id) is None:
            raise SerpApiError("input")
        if self._client.is_closed:
            raise SerpApiError("closed")
        params = {
            "engine": "google_maps_reviews", "data_id": data_id,
            "num": str(page_size), "sort_by": "newestFirst", "hl": "es",
            "output": "json", "async": "false", "no_cache": "false",
            "api_key": self._config.serpapi_api_key.get_secret_value(),
        }
        pages: list[SerpApiPage] = []
        place_info = metadata = None
        seen_tokens: set[str] = set()
        request_count = 0

        def result(reason: StopReason) -> SerpApiResult:
            return SerpApiResult(
                pages=tuple(pages), place_info=place_info, first_page_metadata=metadata,
                request_count=request_count, record_count=sum(len(page.reviews) for page in pages),
                stop_reason=reason, incomplete=reason != "no_next_token", limited=reason == "max_pages",
            )

        while len(pages) < max_pages:
            request_count += 1  # Intentos, incluidos fallos; no equivale a créditos facturados.
            try:
                body = self._request_page(params, page_size)
            except SerpApiError as error:
                error.partial_result = result("error")
                raise
            if not pages:
                place_info = body.get("place_info")
                # No conservar search_parameters, json_endpoint ni URLs de continuación.
                metadata = {
                    key: value for key, value in body["search_metadata"].items()
                    if key in {"id", "status", "created_at", "processed_at", "total_time_taken"}
                }
            token = (body.get("serpapi_pagination") or {}).get("next_page_token") or None
            reviews = tuple(SerpApiReview(data=review) for review in body["reviews"])
            pages.append(SerpApiPage(len(pages) + 1, 200, "Success", reviews, token))
            if not token:
                return result("no_next_token")
            if not reviews:
                return result("empty_with_token")
            if token in seen_tokens:
                return result("repeated_token")
            seen_tokens.add(token)
            params["next_page_token"] = token
        return result("max_pages")

    @staticmethod
    def _limit(value: int | None, configured: int) -> int:
        if value is None:
            return configured
        if type(value) is not int or not 1 <= value <= configured:
            raise SerpApiError("input")
        return value

    def _request_page(self, params: dict[str, str], page_size: int) -> dict[str, Any]:
        private_context = _IN_SERPAPI_REQUEST.set(True)
        try:
            try:
                response = self._client.get(SERPAPI_ENDPOINT, params=params)
            except httpx.TimeoutException:
                raise SerpApiError("timeout") from None
            except httpx.RequestError:
                raise SerpApiError("network") from None
            try:
                status = response.status_code
                if status != 200:
                    code = {400: "request", 401: "credentials", 403: "forbidden", 429: "quota"}.get(status)
                    if code is None:
                        code = "redirect" if 300 <= status < 400 else "unavailable" if status >= 500 else "request"
                    raise SerpApiError(code, http_status=status)
                try:
                    body = response.json()
                except (ValueError, UnicodeDecodeError):
                    raise SerpApiError("invalid_response", http_status=200) from None
                self._validate_body(body, page_size)
                return body
            finally:
                response.close()
        finally:
            _IN_SERPAPI_REQUEST.reset(private_context)

    @staticmethod
    def _validate_body(body: Any, page_size: int) -> None:
        if not isinstance(body, dict):
            raise SerpApiError("invalid_response", http_status=200)
        if body.get("error"):
            raise SerpApiError("provider_error", http_status=200)
        if not isinstance(body.get("search_metadata"), dict):
            raise SerpApiError("invalid_response", http_status=200)
        status = body["search_metadata"].get("status")
        if status == "Error":
            raise SerpApiError("provider_error", http_status=200)
        if status in ("Processing", "Queued", "Pending"):
            raise SerpApiError("pending", http_status=200)
        if status != "Success":
            raise SerpApiError("invalid_response", http_status=200)
        reviews = body.get("reviews")
        pagination = body.get("serpapi_pagination")
        place = body.get("place_info")
        if (
            not isinstance(reviews, list) or len(reviews) > page_size
            or any(not isinstance(review, dict) for review in reviews)
            or (place is not None and not isinstance(place, dict))
            or (pagination is not None and not isinstance(pagination, dict))
        ):
            raise SerpApiError("invalid_response", http_status=200)
        token = (pagination or {}).get("next_page_token")
        if token is not None and (not isinstance(token, str) or not token.strip()):
            raise SerpApiError("invalid_response", http_status=200)
        if token is not None:
            try:
                token.encode("utf-8")
            except UnicodeEncodeError:
                raise SerpApiError("invalid_response", http_status=200) from None
