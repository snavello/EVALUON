"""Tipos de las cinco secciones y cómo se arma cada una (plan 014, «Cómo se calcula el estado y
las cuentas de cada sección»).

Una sección suma dos cosas: las etapas de la 013 que ya calcula `journey/stages/` (su insumo)
y el `status()` de cada uno de sus temas. Las secciones no tienen orden: se entra a cualquiera
en cualquier momento (REQ-075). Solo lee; no decide nada (P3).

Estado de la sección, con las reglas comunes de la 013 adaptadas a secciones sin orden, en este
orden: un pedido activo la deja en curso; la última falla sin un resultado posterior, con error;
si algo espera una decisión (cuenta o etapa a decidir), a decidir; si todo está listo, lista; si
no, pendiente. Una sección sin etapa de la 013 (Normativas) sale de sus temas y, sin
cuentas, queda pendiente. Una etapa opcional pendiente (el Portal en un procedimiento cargado a mano) no
cuenta como falta.
"""

from dataclasses import dataclass, field

from django.urls import reverse

from evaluon.journey.stages import base as stage_base
from evaluon.journey.window import plain_reason

# Estado -> símbolo del ícono de la guía visual (círculo de color con símbolo blanco).
ICONS = {
    stage_base.PENDIENTE: "pend",
    stage_base.EN_CURSO: "pend",
    stage_base.A_DECIDIR: "nodet",
    stage_base.LISTA: "cumple",
    stage_base.CON_ERROR: "nocumple",
}


@dataclass(frozen=True)
class Missing:
    """Algo que falta, con su acción directa (si la hay)."""

    text: str
    url: str | None = None
    action: str = ""


@dataclass(frozen=True)
class Item:
    """Un renglón de la lista de pendientes o de sugerencias, con su enlace."""

    text: str
    url: str | None = None
    count: int = 0
    action: str = "Ver"


@dataclass(frozen=True)
class TemaStatus:
    """Lo que aporta un tema a su sección: cuentas, lo que falta y de dónde vino lo que hay."""

    pending: int = 0
    suggestions: int = 0
    missing: tuple = ()
    sources: tuple = ()
    pending_items: tuple = ()
    suggestion_items: tuple = ()
    detailed_stages: tuple = ()  # etapas cuyo renglón genérico reemplazan los renglones del tema


@dataclass(frozen=True)
class Section:
    key: str
    label: str
    slug: str
    url: str
    state: str
    pending: int
    suggestions: int
    summary: tuple = ()  # (etapa, detalle) de cada etapa de la sección
    missing: tuple = ()
    sources: tuple = ()
    pending_items: tuple = ()
    suggestion_items: tuple = ()
    error: str = ""
    tema_missing: tuple = ()  # lo que faltan los temas, con su acción directa (sin la de las etapas)
    legacy_links: tuple = ()  # (nombre, dirección) de las pantallas actuales que aún se usan
    upload_url: str | None = None
    css: str = ""
    temas: tuple = field(default=(), repr=False)

    @property
    def state_label(self):
        return stage_base.LABELS[self.state]

    @property
    def icon(self):
        return ICONS[self.state]


def combine(stages, pending):
    """El estado de una sección a partir de sus etapas (reglas en el docstring del módulo)."""
    states = [s.state for s in stages if not (s.optional and s.state == stage_base.PENDIENTE)]
    if not stages:
        # Sin etapa de la 013 y sin cuentas, todavía no hay con qué calcularla: pendiente.
        return stage_base.A_DECIDIR if pending else stage_base.PENDIENTE
    if stage_base.EN_CURSO in states:
        return stage_base.EN_CURSO
    if stage_base.CON_ERROR in states:
        return stage_base.CON_ERROR
    if pending or stage_base.A_DECIDIR in states:
        return stage_base.A_DECIDIR
    if all(state == stage_base.LISTA for state in states):
        return stage_base.LISTA
    return stage_base.PENDIENTE


def build_section(module, user, procedure, stages_by_key):
    """Arma la sección que describe `module` (KEY, LABEL, SLUG, STAGE_KEYS, TEMA_KEYS,
    `legacy_links(procedure)`)."""
    from evaluon.journey import temas

    stages = [stages_by_key[key] for key in module.STAGE_KEYS]
    tema_modules = [temas.by_key(key) for key in module.TEMA_KEYS]
    statuses = [tema.status(user, procedure) for tema in tema_modules]

    pending = sum(s.pending for s in stages) + sum(t.pending for t in statuses)
    suggestions = sum(s.suggestions for s in stages) + sum(t.suggestions for t in statuses)

    detailed = {key for status in statuses for key in status.detailed_stages}
    pending_items = [Item(f"{s.label}: {s.pending} por decidir", s.decide_url or s.view_url,
                          s.pending) for s in stages if s.pending and s.key not in detailed]
    suggestion_items = [Item(f"{s.label}: {s.suggestions} del sistema", s.view_url,
                             s.suggestions) for s in stages
                        if s.suggestions and s.key not in detailed]
    missing = [Missing(s.detail, s.view_url, "Ir") for s in stages
               if s.state == stage_base.PENDIENTE and not s.optional]
    tema_missing = []
    for status in statuses:
        pending_items += status.pending_items
        suggestion_items += status.suggestion_items
        missing += status.missing
        tema_missing += status.missing

    failed = next((s for s in stages if s.state == stage_base.CON_ERROR), None)
    return Section(
        key=module.KEY, label=module.LABEL, slug=module.SLUG,
        url=reverse(f"expedientes:{module.KEY}", args=[procedure.pk]),
        state=combine(stages, pending), pending=pending, suggestions=suggestions,
        summary=(module.summary(user, procedure, stages) if hasattr(module, "summary")
                 else tuple((s.label, s.detail) for s in stages if s.detail)),
        missing=tuple(missing), tema_missing=tuple(tema_missing),
        sources=tuple(source for status in statuses for source in status.sources),
        pending_items=tuple(pending_items), suggestion_items=tuple(suggestion_items),
        error=plain_reason(failed.error) if failed else "",
        legacy_links=tuple(module.legacy_links(procedure)),
        upload_url=module.upload_url(procedure),
        css=f"journey/{module.__name__.rsplit('.', 1)[-1]}.css", temas=tuple(tema_modules))
