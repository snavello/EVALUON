"""Cookies seguras en los pedidos cifrados (plan 007, T-269; REQ-110).

Desde otra computadora se entra por Caddy, que corre en este mismo equipo, recibe la conexión
cifrada y reenvía el pedido a 127.0.0.1 con `X-Forwarded-Proto: https`. Con
`SECURE_PROXY_SSL_HEADER` (settings.py), Django toma ese pedido como cifrado (`request.is_secure()`).
En esos pedidos, este middleware marca `Secure` las cookies de sesión y de CSRF de la respuesta,
para que el navegador no las mande nunca por una conexión sin cifrar.

El uso local por http://127.0.0.1:8000 (agentes y responsable) no cambia: ahí las cookies salen
como siempre, porque una cookie `Secure` no vuelve por http y la sesión no andaría. Por eso no se
usan SESSION_COOKIE_SECURE ni CSRF_COOKIE_SECURE, que valen para todos los pedidos.

Va en MIDDLEWARE antes de SessionMiddleware: Django procesa las respuestas en el orden inverso, así
que este middleware actúa después de que la sesión y el CSRF escribieron sus cookies.
"""

from django.conf import settings


class SecureCookiesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.is_secure():
            for name in (settings.SESSION_COOKIE_NAME, settings.CSRF_COOKIE_NAME):
                if name in response.cookies:
                    response.cookies[name]["secure"] = True
        return response
