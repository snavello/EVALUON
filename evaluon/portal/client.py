"""Cliente HTTP del Portal de Compras (plan 012, "Red y conexión"; ADR-0031 y ADR-0032).

Es el único código de EVALUON que abre una conexión a internet, y solo lo corre el servicio
`portal_worker`. Limita lo que puede hacer, y lo hace antes de conectar:

- solo HTTPS, solo el puerto 443 y solo los hosts de `PORTAL_ALLOWED_HOSTS`; un destino
  fuera de la lista, HTTP, otro puerto o una dirección con usuario se rechazan con
  `DestinationNotAllowed` sin abrir ninguna conexión;
- las redirecciones no se siguen solas: cada una se verifica con la misma regla antes de
  pedirla, y son pocas;
- tope de tamaño de cada respuesta (`PORTAL_MAX_BYTES`) y de espera (`PORTAL_TIMEOUT_SECONDS`);
- pausa entre solicitudes (`PORTAL_PAUSE_SECONDS`) y `User-Agent` identificado;
- una sola sesión de cookies por cliente, como pide un sitio de ASP.NET.

El transporte (quien abre la conexión, una función de `Request` a `Response`) se recibe por
parámetro: las pruebas pasan uno que responde con contenido inventado y nunca tocan la red.
El que se usa por omisión es `https_transport`, de `http.client`.

Solo lee: GET, y el envío de un formulario de ASP.NET (POST) con los campos ocultos de la
página (`__VIEWSTATE` y compañía), que es como el Portal entrega sus documentos. No escribe
nada en el Portal.
"""

import http.client
import ssl
import time
from dataclasses import dataclass, field
from functools import partial
from html.parser import HTMLParser
from http.cookies import SimpleCookie
from urllib.parse import urlencode, urljoin, urlsplit

from django.conf import settings

HTTPS_PORT = 443
MAX_REDIRECTS = 5
REDIRECT_STATUSES = (301, 302, 303, 307, 308)
FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"


class PortalError(Exception):
    """Falla al hablar con el Portal."""


class DestinationNotAllowed(PortalError):
    """El destino no está permitido; no se conectó."""


class ResponseTooLarge(PortalError):
    """La respuesta pasó el tope de tamaño."""


class PortalHTTPError(PortalError):
    """El Portal respondió con un error."""

    def __init__(self, status, url):
        super().__init__(f"El Portal respondió {status} en {url}")
        self.status = status
        self.url = url


class TooManyRedirects(PortalError):
    """Más redirecciones que las permitidas."""


@dataclass(frozen=True)
class Request:
    method: str
    url: str
    headers: dict
    body: bytes = b""


@dataclass(frozen=True)
class Response:
    url: str
    status: int
    headers: dict  # nombres en minúscula
    body: bytes


def validate_url(url, allowed_hosts=None):
    """Comprueba que `url` sea HTTPS, del puerto 443 y de un host permitido. Devuelve el
    host. Si no, levanta `DestinationNotAllowed` con la razón. Sirve también para validar
    el enlace que registra una persona (REQ-045)."""
    allowed = settings.PORTAL_ALLOWED_HOSTS if allowed_hosts is None else allowed_hosts
    allowed = {host.lower() for host in allowed}
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise DestinationNotAllowed("la dirección no es válida") from None
    if parts.scheme.lower() != "https":
        raise DestinationNotAllowed("solo se admite HTTPS")
    if parts.username is not None or parts.password is not None:
        raise DestinationNotAllowed("la dirección no puede llevar usuario ni clave")
    host = (parts.hostname or "").lower()
    if not host:
        raise DestinationNotAllowed("la dirección no tiene host")
    if port not in (None, HTTPS_PORT):
        raise DestinationNotAllowed(f"solo se admite el puerto {HTTPS_PORT}")
    if host not in allowed:
        raise DestinationNotAllowed(f"el host {host} no está en la lista de destinos permitidos")
    return host


def https_transport(request, *, timeout, max_bytes):
    """Transporte real: una conexión HTTPS al puerto 443, sin seguir redirecciones. Solo lo
    llama el cliente, después de validar el destino."""
    parts = urlsplit(request.url)
    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"
    connection = http.client.HTTPSConnection(
        parts.hostname, HTTPS_PORT, timeout=timeout, context=ssl.create_default_context()
    )
    try:
        connection.request(request.method, path, body=request.body or None,
                           headers=request.headers)
        raw = connection.getresponse()
        declared = raw.getheader("Content-Length")
        if declared and declared.isdigit() and int(declared) > max_bytes:
            raise ResponseTooLarge(f"la respuesta declara {declared} bytes, el tope es {max_bytes}")
        body = raw.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ResponseTooLarge(f"la respuesta pasa el tope de {max_bytes} bytes")
        headers = {}
        for name, value in raw.getheaders():
            name = name.lower()
            # Varios Set-Cookie se juntan con un salto de línea.
            headers[name] = f"{headers[name]}\n{value}" if name in headers else value
        return Response(request.url, raw.status, headers, body)
    except (OSError, http.client.HTTPException) as error:
        raise PortalError(f"no se pudo conectar con el Portal: {error}") from error
    finally:
        connection.close()


class _HiddenFields(HTMLParser):
    """Reúne los `<input type="hidden">` de una página, en orden."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        if tag != "input":
            return
        attrs = dict(attrs)
        if (attrs.get("type") or "").lower() == "hidden" and attrs.get("name"):
            self.fields[attrs["name"]] = attrs.get("value") or ""


def hidden_fields(page):
    """Campos ocultos de una página (`bytes` o texto), como los espera un envío de
    formulario de ASP.NET: `__VIEWSTATE`, `__EVENTVALIDATION` y los demás."""
    text = page.decode("utf-8", errors="replace") if isinstance(page, bytes) else page
    parser = _HiddenFields()
    parser.feed(text)
    parser.close()
    return parser.fields


@dataclass
class PortalClient:
    """Sesión con el Portal. Recordar: un cliente es una sesión de cookies."""

    transport: object = None
    allowed_hosts: list = None
    timeout: float = None
    max_bytes: int = None
    pause: float = None
    user_agent: str = None
    sleep: object = time.sleep
    clock: object = time.monotonic
    cookies: dict = field(default_factory=dict)
    _last_request_at: float = field(default=None, init=False, repr=False)

    def __post_init__(self):
        if self.allowed_hosts is None:
            self.allowed_hosts = list(settings.PORTAL_ALLOWED_HOSTS)
        if self.timeout is None:
            self.timeout = settings.PORTAL_TIMEOUT_SECONDS
        if self.max_bytes is None:
            self.max_bytes = settings.PORTAL_MAX_BYTES
        if self.pause is None:
            self.pause = settings.PORTAL_PAUSE_SECONDS
        if self.user_agent is None:
            self.user_agent = settings.PORTAL_USER_AGENT
        if self.transport is None:
            self.transport = partial(
                https_transport, timeout=self.timeout, max_bytes=self.max_bytes
            )

    # --- Solicitudes -------------------------------------------------------------------

    def get(self, url):
        """GET de `url`; devuelve la `Response` final, tras verificar cada redirección."""
        return self._send("GET", url, b"", {})

    def submit_form(self, url, page, fields=None):
        """Envío de formulario de ASP.NET: POST a `url` con los campos ocultos de `page`
        (los bytes de la página que trae el formulario) más `fields`, que pisan a los
        ocultos del mismo nombre. Usa las cookies de esta sesión."""
        data = hidden_fields(page)
        data.update(fields or {})
        body = urlencode(data).encode("ascii")
        return self._send("POST", url, body, {"Content-Type": FORM_CONTENT_TYPE})

    def _send(self, method, url, body, extra_headers):
        for _ in range(MAX_REDIRECTS + 1):
            validate_url(url, self.allowed_hosts)  # antes de conectar, en cada solicitud
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "*/*",
                "Connection": "close",
                **extra_headers,
            }
            cookie = self._cookie_header()
            if cookie:
                headers["Cookie"] = cookie
            if body:
                headers["Content-Length"] = str(len(body))
            self._wait_turn()
            response = self.transport(Request(method, url, headers, body))
            if len(response.body) > self.max_bytes:
                raise ResponseTooLarge(f"la respuesta pasa el tope de {self.max_bytes} bytes")
            self._store_cookies(response.headers.get("set-cookie", ""))
            if response.status in REDIRECT_STATUSES and response.headers.get("location"):
                url = urljoin(url, response.headers["location"])
                if response.status in (301, 302, 303):
                    method, body, extra_headers = "GET", b"", {}
                continue
            if response.status >= 400:
                raise PortalHTTPError(response.status, url)
            return response
        raise TooManyRedirects(f"más de {MAX_REDIRECTS} redirecciones")

    # --- Pausa y cookies ---------------------------------------------------------------

    def _wait_turn(self):
        now = self.clock()
        if self._last_request_at is not None:
            remaining = self.pause - (now - self._last_request_at)
            if remaining > 0:
                self.sleep(remaining)
                now = self.clock()
        self._last_request_at = now

    def _cookie_header(self):
        return "; ".join(f"{name}={value}" for name, value in self.cookies.items())

    def _store_cookies(self, set_cookie):
        if not set_cookie:
            return
        jar = SimpleCookie()
        for line in set_cookie.split("\n"):
            try:
                jar.load(line)
            except Exception:  # noqa: BLE001 - una cookie ilegible no frena la lectura
                continue
        for name, morsel in jar.items():
            self.cookies[name] = morsel.value
