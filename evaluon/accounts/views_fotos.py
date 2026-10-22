"""«Mis fotos» del perfil y servido privado de cada foto (REQ-136; ADR-0073; P4).

Cada usuario sube, ve y quita hasta 10 fotos. Subir y quitar las propias no es una acción de
decisión de la Comisión ni interviene la IA, así que también lo puede hacer el usuario de lectura
y no deja registro de auditoría (P6 pide registrar los pasos en que interviene la IA).

La foto se busca siempre con `user=request.user`: la de otro usuario da 404, igual que una que no
existe, así que no se puede saber si existe. La exigencia de sesión la pone el middleware de ingreso.
"""

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.cache import get_conditional_response
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from evaluon.accounts import photos
from evaluon.accounts.models import PHOTO_SLOTS, Photo

# Avisos de éxito que viajan en la consulta: es una lista cerrada, nunca texto libre.
NOTICES = {"subida": "Foto subida.", "quitada": "Foto quitada."}
NO_FILE = "Elija una foto para subir."


def _page(request, *, error=None, status=200):
    mine = list(Photo.objects.filter(user=request.user).only(
        "pk", "slot", "width", "height").order_by("slot"))
    free = PHOTO_SLOTS - len(mine)
    context = {
        "photos": mine,
        "count": len(mine),
        "free": free,
        "can_add": free > 0,
        "empty_slots": range(max(free - 1, 0)),
        "max_photos": PHOTO_SLOTS,
        "error": error,
        "notice": NOTICES.get(request.GET.get("aviso", "")),
    }
    return render(request, "accounts/fotos.html", context, status=status)


@require_http_methods(["GET", "POST"])
def fotos(request):
    """GET: la pantalla. POST: sube la foto del campo `foto`."""
    if request.method == "GET":
        return _page(request)
    file = request.FILES.get("foto")
    if file is None:
        return _page(request, error=NO_FILE)
    try:
        photos.upload(request.user, file)
    except photos.PhotoRejected as rejected:
        return _page(request, error=str(rejected))
    return redirect(f"{reverse('accounts:fotos')}?aviso=subida")


@require_safe
def foto(request, pk):
    """Sirve la foto propia. Sin ser el dueño, 404. Caché privada y ETag con la huella."""
    photo = get_object_or_404(Photo, pk=pk, user=request.user)
    etag = f'"{photo.sha256}"'
    response = get_conditional_response(request, etag=etag)
    if response is None:
        response = HttpResponse(bytes(photo.content), content_type="image/jpeg")
    response["ETag"] = etag
    response["Cache-Control"] = "private, no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_POST
def foto_quitar(request, pk):
    """Quita una foto propia y deja libre su ranura. Si no es del usuario o no existe, 404."""
    if not photos.remove(request.user, pk):
        raise Http404("No existe esa foto.")
    return redirect(f"{reverse('accounts:fotos')}?aviso=quitada")
