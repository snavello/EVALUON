"""Las páginas de lectura anteriores a las cinco pestañas (T-219, REQ-075, REQ-100).

`to_section` envuelve una vista: el GET redirige a la pestaña que corresponde; el resto de los
métodos (las acciones) sigue en la vista. Sin pantallas duplicadas."""

from functools import wraps

from django.shortcuts import redirect
from django.urls import reverse


def section_url(key, procedure_id):
    return reverse(f"expedientes:{key}", args=[procedure_id])


def to_section(resolve):
    """`resolve(request, *args, **kwargs)` devuelve la URL de la pestaña (o lanza `Http404`)."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method in ("GET", "HEAD"):
                return redirect(resolve(request, *args, **kwargs))
            return view(request, *args, **kwargs)
        return wrapper
    return decorator

