"""Contraste AA de los dos temas (REQ-133; plan 017, «Criterio de aceptación numérico»).

Calcula la razón de cada par declarado desde `evaluon/static/diseno/tokens.css`: texto 4,5:1;
íconos, marcas y gráficos 3:1 (WCAG 1.4.3 y 1.4.11). Los dos temas se resuelven igual que el
navegador: `:root` es el tema gris y blanco y `[data-theme="negro"]` lo pisa.
"""

import re
from pathlib import Path

import pytest

TOKENS = Path(__file__).resolve().parents[2] / "evaluon" / "static" / "diseno" / "tokens.css"
TEMAS = ("claro", "negro")
TEXTO, GRAFICO = 4.5, 3.0

# --- Lectura de tokens.css ----------------------------------------------------------------


def _bloques(css: str) -> list[tuple[list[str], dict[str, str]]]:
    """Devuelve [(selectores, {--nombre: valor})] en el orden del archivo, sin los @font-face."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    salida = []
    for selector, cuerpo in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        selector = selector.strip()
        if selector.startswith("@"):
            continue
        declaraciones = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", cuerpo))
        salida.append(([s.strip() for s in selector.split(",")], {k: v.strip() for k, v in declaraciones.items()}))
    return salida


def variables(css: str, tema: str) -> dict[str, str]:
    """Variables vigentes en el tema: `:root` y, para el negro, además `[data-theme="negro"]`."""
    valores: dict[str, str] = {}
    for selectores, declaraciones in _bloques(css):
        if ":root" in selectores or (tema == "negro" and '[data-theme="negro"]' in selectores):
            valores.update(declaraciones)
    return valores


def _partes(texto: str) -> list[str]:
    """Separa argumentos por comas del nivel de arriba."""
    partes, nivel, actual = [], 0, ""
    for c in texto:
        nivel += c == "("
        nivel -= c == ")"
        if c == "," and nivel == 0:
            partes.append(actual.strip())
            actual = ""
        else:
            actual += c
    partes.append(actual.strip())
    return partes


def color(expresion: str, vars_: dict[str, str], _prof: int = 0) -> tuple[float, float, float]:
    """Resuelve `#hex`, `var(--x)`, `--x` y `color-mix(in srgb, A p%, B)` a (r, g, b) de 0 a 255."""
    assert _prof < 12, f"referencia circular en {expresion}"
    e = expresion.strip()
    if e.startswith("--"):
        return color(vars_[e], vars_, _prof + 1)
    if e.startswith("var("):
        nombre = _partes(e[4:-1])[0]
        return color(vars_[nombre], vars_, _prof + 1)
    if e.startswith("color-mix("):
        _, a, b = _partes(e[len("color-mix("):-1])
        m = re.match(r"(.+?)\s+(\d+(?:\.\d+)?)%$", a)
        ca, pa = color(m.group(1), vars_, _prof + 1), float(m.group(2)) / 100
        cb = color(b, vars_, _prof + 1)
        return tuple(pa * x + (1 - pa) * y for x, y in zip(ca, cb))
    m = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", e)
    assert m, f"color no soportado por el test: {expresion!r}"
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(float(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def luminancia(rgb: tuple[float, float, float]) -> float:
    def lin(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def razon(fg: str, bg: str, vars_: dict[str, str]) -> float:
    a, b = luminancia(color(fg, vars_)), luminancia(color(bg, vars_))
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


# --- Pares declarados ---------------------------------------------------------------------
# (nombre, primer plano, fondo, mínimo). Se evalúan en los dos temas.

SUPERFICIES = ("--bg", "--tile", "--tile-h")
ESTADOS = ("ok", "no", "nd", "pe", "ext")


def _pares() -> list[tuple[str, str, str, float]]:
    p: list[tuple[str, str, str, float]] = []

    def add(nombre, fg, bg, minimo):
        p.append((nombre, fg, bg, minimo))

    # Texto sobre las superficies. --ink-3 (marcas y números tenues) no va sobre --tile-h.
    for s in SUPERFICIES:
        add(f"texto --ink / {s}", "--ink", s, TEXTO)
        add(f"texto --ink-2 / {s}", "--ink-2", s, TEXTO)
    for s in ("--bg", "--tile"):
        add(f"texto --ink-3 / {s}", "--ink-3", s, TEXTO)
    # Acciones, pestañas y mosaico oscuro.
    add("texto sobre lima", "--on-lime", "--lime", TEXTO)
    add("botón", "--on-btn", "--btn", TEXTO)
    add("botón (hover)", "--on-btn", "--btn-h", TEXTO)
    add("pestaña inactiva", "--nav-ink", "--nav-track", TEXTO)
    add("pestaña inactiva (hover)", "--ink", "--nav-track", TEXTO)
    add("pestaña activa", "--nav-on-ink", "--nav-on", TEXTO)
    add("contador de pestaña activa", "--nav-on", "--nav-on-ink", TEXTO)
    add("mosaico oscuro", "--dark-tile-ink", "--dark-tile", TEXTO)
    add("mosaico oscuro, texto secundario", "--dark-tile-2", "--dark-tile", TEXTO)
    add("avatar, aviso emergente, filtro activo", "--bg", "--ink", TEXTO)
    # Estados: texto sobre su tinta, y el texto de estado sobre las superficies.
    for e in ESTADOS:
        add(f"etiqueta {e}", f"--{e}-ink", f"--{e}-bg", TEXTO)
    for e in ESTADOS:
        for s in ("--bg", "--tile"):
            add(f"texto de estado {e} / {s}", f"--{e}-ink", s, TEXTO)
    add("botón de acento", "#FFFFFF", "--accent", TEXTO)
    add("botón de acento (hover)", "#FFFFFF", "--accent-h", TEXTO)

    # Íconos, marcas y gráficos sobre las tres superficies.
    for e in ESTADOS:
        for s in SUPERFICIES:
            add(f"ícono/gráfico {e} / {s}", f"--{e}", s, GRAFICO)
        add(f"símbolo blanco sobre el círculo {e}", "--ev-icono-simbolo", f"--{e}", GRAFICO)
    for s in SUPERFICIES:
        add(f"gráfico --s2 / {s}", "--s2", s, GRAFICO)
        add(f"gráfico --s3 / {s}", "--s3", s, GRAFICO)
        add(f"anillo de foco / {s}", "--focus", s, GRAFICO)
    for s in ("--bg", "--tile"):
        add(f"marca futura y borde de campo --ink-3 / {s}", "--ink-3", s, GRAFICO)

    # Alias de los tokens viejos: las páginas sin migrar se leen bien en los dos temas.
    fondos_viejos = ("--ev-fondo", "--ev-superficie", "--ev-superficie-2", "--ev-tabla-cabecera",
                     "--ev-tabla-cebra", "--ev-azul-50", "--ev-beige-100", "--ev-beige-50",
                     "--ev-beige-300", "--ev-azul-100")
    for f in fondos_viejos:
        for t in ("--ev-texto", "--ev-texto-suave", "--ev-enlace"):
            add(f"alias {t} / {f}", t, f, TEXTO)
    add("alias encabezado", "--ev-encabezado-texto", "--ev-encabezado-fondo", TEXTO)
    add("alias encabezado, texto tenue", "--ev-azul-200", "--ev-encabezado-fondo", TEXTO)
    add("alias botón", "--ev-boton-texto", "--ev-boton-fondo", TEXTO)
    add("alias botón (hover)", "--ev-boton-texto", "--ev-boton-hover", TEXTO)
    add("alias aviso emergente", "--ev-tooltip-texto", "--ev-tooltip-fondo", TEXTO)
    add("alias acento", "#FFFFFF", "--ev-rojo", TEXTO)
    add("alias acento (hover)", "#FFFFFF", "--ev-rojo-hover", TEXTO)
    for nombre, t, f in (("cumple", "--ev-cumple", "--ev-cumple-fondo"),
                         ("no cumple", "--ev-nocumple", "--ev-nocumple-fondo"),
                         ("no determinado", "--ev-nodeterminado", "--ev-nodeterminado-fondo"),
                         ("pendiente", "--ev-pendiente", "--ev-pendiente-fondo"),
                         ("externo", "--ev-externo", "--ev-externo-fondo")):
        add(f"alias estado {nombre}", t, f, TEXTO)
    for s in ("--ev-fondo", "--ev-superficie"):
        add(f"alias borde de campo / {s}", "--ev-borde-campo", s, GRAFICO)
        add(f"alias ícono cumple / {s}", "--ev-icono-cumple", s, GRAFICO)
        add(f"alias ícono no cumple / {s}", "--ev-icono-nocumple", s, GRAFICO)
        add(f"alias ícono no determinado / {s}", "--ev-icono-nodeterminado", s, GRAFICO)
        add(f"alias ícono pendiente / {s}", "--ev-icono-pendiente", s, GRAFICO)
        add(f"alias marca externa / {s}", "--ev-externo-marca", s, GRAFICO)
        add(f"alias foco / {s}", "--ev-foco", s, GRAFICO)
    return p


PARES = _pares()

# Pares que dependen del tema. El lima solo resalta y nunca va solo: en el tema gris y blanco
# (donde el lima casi no se distingue del fondo) toda marca lima lleva contorno --ink; en el
# negro el lima se distingue por sí mismo de las tres superficies.
PARES_POR_TEMA: dict[str, list[tuple[str, str, str, float]]] = {
    "claro": [("contorno --ink de una marca lima / lima", "--ink", "--lime", GRAFICO)]
             + [(f"contorno --ink de una marca lima / {s}", "--ink", s, GRAFICO) for s in SUPERFICIES],
    "negro": [(f"marca lima / {s}", "--lime", s, GRAFICO) for s in SUPERFICIES],
}

# Lugar para el texto sobre la foto del primer panel (lo agrega T-321, REQ-135): mismo formato
# (nombre, primer plano, fondo, mínimo), con el peor píxel de la foto de la casa a máxima
# opacidad como fondo literal (#RRGGBB) o una mezcla `color-mix(...)`.
PARES_FOTO: list[tuple[str, str, str, float]] = []

# Tokens de color que no llevan par propio, con la razón. Todo lo demás tiene que figurar en un par.
EXENTOS = {
    "--line": "separadores y bordes de adorno; nada depende de verlos",
    "--trk": "pista detrás de una barra: la barra y la cifra dan el dato",
}


def _css() -> str:
    return TOKENS.read_text(encoding="utf-8")


def _fallos(css: str) -> list[str]:
    fallos = []
    for tema in TEMAS:
        v = variables(css, tema)
        for nombre, fg, bg, minimo in PARES + PARES_POR_TEMA[tema] + PARES_FOTO:
            r = razon(fg, bg, v)
            if r < minimo:
                fallos.append(f"[{tema}] {nombre}: {r:.2f}:1 < {minimo}:1")
    return fallos


_CASOS = [(t, par) for t in TEMAS for par in PARES + PARES_POR_TEMA[t] + PARES_FOTO]


@pytest.mark.parametrize("tema,par", _CASOS, ids=lambda x: x if isinstance(x, str) else x[0])
def test_cada_par_declarado_llega_al_minimo(tema, par):
    """REQ-133: cada par texto/fondo, ícono/fondo o gráfico/fondo cumple AA en el tema."""
    nombre, fg, bg, minimo = par
    v = variables(_css(), tema)
    assert razon(fg, bg, v) >= minimo, f"{nombre} en {tema}"


def test_cien_por_ciento_de_los_pares_en_los_dos_temas():
    """REQ-133 (criterio numérico): 100 % de los pares declarados cumplen AA en ambos temas."""
    assert len(PARES) + len(PARES_POR_TEMA["claro"]) >= 100
    assert _fallos(_css()) == []


def test_los_dos_temas_definen_los_mismos_colores():
    """REQ-133: todo token de color del tema claro está redefinido en el negro (salvo los comunes)."""
    claro = variables(_css(), "claro")
    bloques = _bloques(_css())
    base = next(d for s, d in bloques if s == [":root"] and "--bg" in d)
    negro = next(d for s, d in bloques if s == ['[data-theme="negro"]'])
    comunes = {"--lime", "--on-lime"}
    faltan = [k for k, v in base.items() if v.startswith("#") and k not in negro and k not in comunes]
    assert faltan == [], f"definidos en el claro y no en el negro: {faltan}"
    assert claro["--bg"] != variables(_css(), "negro")["--bg"]


def test_todo_token_de_color_tiene_par_o_exencion():
    """REQ-133: un color nuevo en tokens.css no entra sin declarar su contraste."""
    mencionados = set()
    for _, fg, bg, _ in PARES + PARES_POR_TEMA["claro"] + PARES_POR_TEMA["negro"]:
        mencionados.update(re.findall(r"--[\w-]+", f"{fg} {bg}"))
    colores = {k for s, d in _bloques(_css()) for k, v in d.items()
               if (v.startswith("#") or v.startswith("color-mix(")) and not k.startswith("--ev-")}
    sin_par = sorted(colores - mencionados - set(EXENTOS))
    assert sin_par == [], f"tokens de color sin par declarado ni exención: {sin_par}"


def test_bajar_ink_3_a_un_gris_mas_claro_hace_fallar_el_test():
    """REQ-133 (prueba de alteración): el valor de la maqueta, #8E8E8E, no pasa."""
    css = _css()
    alterado = re.sub(r"(:root\s*\{[^}]*--ink-3:\s*)#[0-9A-Fa-f]{6}", r"\1#8E8E8E", css, count=1)
    assert alterado != css
    fallos = _fallos(alterado)
    assert any("--ink-3" in f for f in fallos)


def test_un_amarillo_claro_en_el_icono_no_determinado_hace_fallar_el_test():
    """REQ-133 (prueba de alteración): el --nd de la maqueta, #C29A4F, no pasa sobre el mosaico gris."""
    css = _css()
    alterado = re.sub(r"(--nd:\s*)#[0-9A-Fa-f]{6}", r"\1#C29A4F", css, count=1)
    assert alterado != css
    assert any("nd" in f for f in _fallos(alterado))


def test_el_lugar_para_el_texto_sobre_la_foto_existe():
    """REQ-135 (lo llena T-321): cada entrada trae nombre, primer plano, fondo y mínimo."""
    assert isinstance(PARES_FOTO, list)
    for entrada in PARES_FOTO:
        assert len(entrada) == 4 and entrada[3] >= TEXTO
