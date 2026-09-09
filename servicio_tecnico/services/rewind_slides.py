"""
Pinta las diapositivas del video rewind (intro, tarjetas de sección y cierre).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
FFmpeg es excelente para unir fotos y hacer fades, pero su filtro
``drawtext`` solo puede poner una línea de texto sobre un color plano.
Por eso este servicio dibuja las tarjetas ANTES, con Pillow (como si
fueran carteles de 1280×720), y FFmpeg las muestra como imágenes fijas.

Objetivo de negocio:
    Darle al rewind un look cinematográfico oscuro (navy + acento SIC)
    sin cambiar el orden del video ni el envío al cliente.

Efectos secundarios:
    Escribe archivos PNG en el directorio temporal que reciba.
    No toca la base de datos.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import TypedDict

from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger('servicio_tecnico')

# ---------------------------------------------------------------------------
# Lienzo y paleta (cinematográfico oscuro, acento de marca SIC)
# ---------------------------------------------------------------------------
ANCHO = 1280
ALTO = 720

# Navy profundo (cercano al dark mode de SIGMA) y azul de marca.
COLOR_FONDO_ARRIBA = (18, 38, 58)       # #12263A
COLOR_FONDO_ABAJO = (11, 28, 44)        # #0B1C2C
COLOR_ACENTO = (31, 99, 145)            # #1F6391
COLOR_BLANCO = (255, 255, 255)
COLOR_MUTED = (186, 201, 214)           # gris-azulado, subtítulos

# Copy de las tarjetas de sección (diagnóstico = 4 pasos).
TEXTO_SECCIONES = {
    'ingreso': 'Así ingresó tu equipo',
    'diagnostico': 'Diagnóstico minucioso',
    'reparacion': 'Así se reparó',
    'egreso': 'Tu equipo ahora',
}

# Copy de venta mostrador (3 pasos, sin diagnóstico).
TEXTO_SECCIONES_VM = {
    'ingreso': 'Así llegó tu equipo',
    'reparacion': 'Así se realizó el servicio',
    'egreso': 'Tu equipo ahora',
}

# Etiqueta corta del kicker (el número de paso se arma al pintar).
KICKER_SECCIONES = {
    'ingreso': 'INGRESO',
    'diagnostico': 'DIAGNÓSTICO',
    'reparacion': 'REPARACIÓN',
    'egreso': 'EGRESO',
}
KICKER_SECCIONES_VM = {
    'ingreso': 'INGRESO',
    'reparacion': 'SERVICIO',
    'egreso': 'EGRESO',
}

# Cierre: confianza + siguiente paso (el cliente espera confirmación de entrega).
TEXTO_CIERRE_KICKER = 'Gracias por tu confianza'
TEXTO_CIERRE_TITULO = 'Tu equipo está listo'
TEXTO_CIERRE_SUBTITULO = 'Te contactaremos para coordinar la entrega'

# Candidatos de fuente: Ubuntu/Debian (DejaVu) primero; Arch (Noto) después.
_FONT_BOLD = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    '/usr/share/fonts/noto/NotoSans-Bold.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
]
_FONT_REGULAR = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
    '/usr/share/fonts/noto/NotoSans-Regular.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
]


class SlidesRewind(TypedDict):
    """Rutas de los PNG generados. intro/secciones van vacíos en modo simple."""

    intro: str | None
    secciones: dict[str, str]
    cierre: str


def lineas_cierre() -> tuple[str, str, str]:
    """
    Devuelve las 3 líneas del slide final (kicker, título, subtítulo).

    Args:
        Ninguno.

    Returns:
        Tupla de 3 strings. La tarea FFmpeg no las dibuja: ya van pintadas
        en el PNG de cierre.

    Efectos secundarios:
        Ninguno.
    """
    return (
        TEXTO_CIERRE_KICKER,
        TEXTO_CIERRE_TITULO,
        TEXTO_CIERRE_SUBTITULO,
    )


def generar_slides_rewind(
    dest_dir: str,
    *,
    folio: str,
    equipo: str,
    tipos_activos: list[str],
    es_venta_mostrador: bool = False,
    incluir_intro_y_secciones: bool = True,
) -> SlidesRewind:
    """
    Genera los PNG del rewind en ``dest_dir``.

    Args:
        dest_dir: carpeta temporal (la tarea Celery ya la creó).
        folio: número de orden que se ve en la intro (orden_cliente o interno).
        equipo: texto «tipo marca modelo» de la intro.
        tipos_activos: lista ordenada de tipos de foto (3 o 4).
        es_venta_mostrador: True usa copy de 3 pasos.
        incluir_intro_y_secciones: False = solo cierre (modo simple, fotos incompletas).

    Returns:
        Diccionario con rutas: intro (o None), secciones {tipo: ruta}, cierre.

    Efectos secundarios:
        Escribe PNG en disco. Si falta el logo, las tarjetas se pintan igual.
    """
    os.makedirs(dest_dir, exist_ok=True)
    logo = _cargar_logo_blanco(dest_dir)

    resultado: SlidesRewind = {
        'intro': None,
        'secciones': {},
        'cierre': '',
    }

    if incluir_intro_y_secciones:
        ruta_intro = os.path.join(dest_dir, 'slide_intro.png')
        _pintar_intro(ruta_intro, folio=folio or '', equipo=equipo or '', logo=logo)
        resultado['intro'] = ruta_intro

        textos = TEXTO_SECCIONES_VM if es_venta_mostrador else TEXTO_SECCIONES
        kickers = KICKER_SECCIONES_VM if es_venta_mostrador else KICKER_SECCIONES
        for indice, tipo in enumerate(tipos_activos, start=1):
            ruta_sec = os.path.join(dest_dir, f'slide_sec_{tipo}.png')
            kicker = f'{indice:02d}  ·  {kickers.get(tipo, tipo.upper())}'
            titulo = textos.get(tipo, tipo)
            _pintar_seccion(ruta_sec, kicker=kicker, titulo=titulo, logo=logo)
            resultado['secciones'][tipo] = ruta_sec

    ruta_cierre = os.path.join(dest_dir, 'slide_cierre.png')
    _pintar_cierre(ruta_cierre, logo=logo)
    resultado['cierre'] = ruta_cierre
    return resultado


# ===========================================================================
# FONDO Y TIPOGRAFÍA
# ===========================================================================

def _fondo_cinematico() -> Image.Image:
    """
    Lienzo navy con degradado vertical, viñeta suave y barras de acento.

    Returns:
        Imagen RGB 1280×720 lista para dibujar texto encima.
    """
    # Degradado de 1 px de ancho y se estira: más rápido que pintar píxel a píxel.
    franja = Image.new('RGB', (1, ALTO))
    draw_franja = ImageDraw.Draw(franja)
    for y in range(ALTO):
        t = y / (ALTO - 1)
        color = _mezclar(COLOR_FONDO_ARRIBA, COLOR_FONDO_ABAJO, t)
        draw_franja.point((0, y), fill=color)
    fondo = franja.resize((ANCHO, ALTO), Image.Resampling.BILINEAR)

    # Halo azul suave al centro-arriba: da profundidad sin parecer un PowerPoint.
    halo = Image.new('L', (ANCHO, ALTO), 0)
    draw_halo = ImageDraw.Draw(halo)
    draw_halo.ellipse((ANCHO // 2 - 420, -180, ANCHO // 2 + 420, 380), fill=70)
    halo = halo.filter(ImageFilter.GaussianBlur(radius=80))
    capa_acento = Image.new('RGB', (ANCHO, ALTO), COLOR_ACENTO)
    fondo = Image.composite(capa_acento, fondo, halo)

    # Viñeta: oscurece bordes para que el texto del centro “flote”.
    vineta = Image.new('L', (ANCHO, ALTO), 0)
    draw_v = ImageDraw.Draw(vineta)
    draw_v.rectangle((80, 50, ANCHO - 80, ALTO - 50), fill=255)
    vineta = vineta.filter(ImageFilter.GaussianBlur(radius=70))
    oscuro = Image.new('RGB', (ANCHO, ALTO), (6, 14, 22))
    fondo = Image.composite(fondo, oscuro, vineta)

    # Barras de acento arriba y abajo: marco tipo ident de marca.
    draw = ImageDraw.Draw(fondo)
    draw.rectangle((0, 0, ANCHO, 4), fill=COLOR_ACENTO)
    draw.rectangle((0, ALTO - 4, ANCHO, ALTO), fill=COLOR_ACENTO)
    return fondo


def _fuente(bold: bool, tamanio: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Carga TTF del sistema. Si no hay Bold, cae a Regular; si no hay nada, default.

    Args:
        bold: True para títulos.
        tamanio: tamaño en píxeles.

    Returns:
        Fuente Pillow lista para ``draw.text``.
    """
    candidatos = _FONT_BOLD if bold else _FONT_REGULAR
    # Si pidieron Bold y no existe, el Regular sigue viéndose profesional.
    if bold:
        candidatos = list(_FONT_BOLD) + list(_FONT_REGULAR)
    for ruta in candidatos:
        if os.path.isfile(ruta):
            try:
                return ImageFont.truetype(ruta, tamanio)
            except OSError:
                continue
    logger.warning('[REWIND-SLIDES] Ninguna TTF del sistema; se usa fuente default')
    return ImageFont.load_default()


def _mezclar(
    color_a: tuple[int, int, int],
    color_b: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    """Interpola dos RGB. t=0 → color_a, t=1 → color_b."""
    return tuple(int(a + (b - a) * t) for a, b in zip(color_a, color_b))


def _ancho_texto(texto: str, fuente: ImageFont.ImageFont) -> int:
    """Ancho en píxeles de una línea (bbox de Pillow)."""
    dummy = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    caja = dummy.textbbox((0, 0), texto, font=fuente)
    return caja[2] - caja[0]


def _envolver(texto: str, fuente: ImageFont.ImageFont, max_ancho: int) -> list[str]:
    """
    Parte un título en 1 o 2 líneas si no cabe.

    Args:
        texto: frase completa.
        fuente: la misma que se usará al pintar.
        max_ancho: límite horizontal (deja márgenes).

    Returns:
        Lista de líneas (nunca vacía).
    """
    if _ancho_texto(texto, fuente) <= max_ancho:
        return [texto]
    palabras = texto.split()
    lineas: list[str] = []
    actual = ''
    for palabra in palabras:
        prueba = f'{actual} {palabra}'.strip()
        if _ancho_texto(prueba, fuente) <= max_ancho:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas or [texto]


def _barra_acento(draw: ImageDraw.ImageDraw, centro_x: int, y: int, ancho: int = 88) -> None:
    """Línea corta de acento bajo un título (grosor 3 px)."""
    draw.rectangle(
        (centro_x - ancho // 2, y, centro_x + ancho // 2, y + 3),
        fill=COLOR_ACENTO,
    )


def _pegar_logo(
    canvas: Image.Image,
    logo: Image.Image | None,
    *,
    centro_x: int | None = None,
    x: int | None = None,
    y: int,
    ancho_max: int,
) -> None:
    """
    Pega el logo SIC con transparencia. Si no hay logo, no hace nada.

    Args:
        canvas: imagen RGB de destino.
        logo: RGBA o None.
        centro_x: si se pasa, centra horizontalmente.
        x: esquina izquierda (se ignora si hay centro_x).
        y: esquina superior.
        ancho_max: escala el logo a este ancho máximo.
    """
    if logo is None:
        return
    rgba = logo.convert('RGBA')
    w, h = rgba.size
    if w <= 0 or h <= 0:
        return
    escala = min(ancho_max / w, 1.0)
    nuevo = (max(1, int(w * escala)), max(1, int(h * escala)))
    rgba = rgba.resize(nuevo, Image.Resampling.LANCZOS)
    if centro_x is not None:
        x = centro_x - rgba.size[0] // 2
    if x is None:
        x = 0
    canvas.paste(rgba, (int(x), int(y)), rgba)


def _guardar_png(img: Image.Image, ruta: str) -> None:
    """Guarda RGB (sin alpha) para que FFmpeg no pelee con transparencia."""
    img.convert('RGB').save(ruta, format='PNG', optimize=True)
    logger.info('[REWIND-SLIDES] PNG listo: %s (%s bytes)', ruta, os.path.getsize(ruta))


# ===========================================================================
# COMPOSICIÓN DE CADA SLIDE
# ===========================================================================

def _pintar_intro(ruta: str, *, folio: str, equipo: str, logo: Image.Image | None) -> None:
    """
    Intro: logo + folio grande + equipo. El cliente reconoce de inmediato su orden.

    Args:
        ruta: PNG de salida.
        folio: texto del folio.
        equipo: tipo/marca/modelo (puede ir vacío).
        logo: logo blanco o None.
    """
    img = _fondo_cinematico()
    draw = ImageDraw.Draw(img)
    fuente_folio = _fuente(True, 52)
    fuente_equipo = _fuente(False, 26)

    # Logo un poco arriba del centro óptico (no geométrico) para dejar aire al texto.
    _pegar_logo(img, logo, centro_x=ANCHO // 2, y=128, ancho_max=420)

    y_folio = 330
    draw.text(
        (ANCHO // 2, y_folio),
        folio,
        font=fuente_folio,
        fill=COLOR_BLANCO,
        anchor='mt',
    )
    _barra_acento(draw, ANCHO // 2, y_folio + 70, ancho=96)

    if equipo.strip():
        draw.text(
            (ANCHO // 2, y_folio + 100),
            equipo.strip(),
            font=fuente_equipo,
            fill=COLOR_MUTED,
            anchor='mt',
        )
    _guardar_png(img, ruta)


def _pintar_seccion(
    ruta: str,
    *,
    kicker: str,
    titulo: str,
    logo: Image.Image | None,
) -> None:
    """
    Tarjeta de capítulo: número de paso + título grande + logo chico.

    Args:
        ruta: PNG de salida.
        kicker: ej. «01  ·  INGRESO».
        titulo: frase que ya conocen («Así se reparó»).
        logo: logo blanco o None.
    """
    img = _fondo_cinematico()
    draw = ImageDraw.Draw(img)
    fuente_kicker = _fuente(True, 22)
    fuente_titulo = _fuente(True, 56)

    lineas = _envolver(titulo, fuente_titulo, max_ancho=1040)
    # Bloque vertical centrado: kicker + título (1 o 2 líneas) + barra.
    alto_titulo = 68 * len(lineas)
    y_kicker = (ALTO // 2) - 70 - (alto_titulo // 4)

    draw.text(
        (ANCHO // 2, y_kicker),
        kicker,
        font=fuente_kicker,
        fill=COLOR_ACENTO,
        anchor='mt',
    )
    y_titulo = y_kicker + 48
    for linea in lineas:
        draw.text(
            (ANCHO // 2, y_titulo),
            linea,
            font=fuente_titulo,
            fill=COLOR_BLANCO,
            anchor='mt',
        )
        y_titulo += 68
    _barra_acento(draw, ANCHO // 2, y_titulo + 8, ancho=110)

    # Logo chico abajo a la izquierda: ancla de marca sin competir con el título.
    _pegar_logo(img, logo, x=56, y=ALTO - 92, ancho_max=150)
    _guardar_png(img, ruta)


def _pintar_cierre(ruta: str, *, logo: Image.Image | None) -> None:
    """
    Cierre: confianza + «está listo» + siguiente paso (coordinar entrega).

    Args:
        ruta: PNG de salida.
        logo: logo blanco o None.
    """
    img = _fondo_cinematico()
    draw = ImageDraw.Draw(img)
    kicker, titulo, subtitulo = lineas_cierre()
    fuente_kicker = _fuente(False, 22)
    fuente_titulo = _fuente(True, 54)
    fuente_sub = _fuente(False, 26)

    y_kicker = 210
    draw.text(
        (ANCHO // 2, y_kicker),
        kicker,
        font=fuente_kicker,
        fill=COLOR_MUTED,
        anchor='mt',
    )
    y_titulo = y_kicker + 52
    draw.text(
        (ANCHO // 2, y_titulo),
        titulo,
        font=fuente_titulo,
        fill=COLOR_BLANCO,
        anchor='mt',
    )
    _barra_acento(draw, ANCHO // 2, y_titulo + 72, ancho=100)

    # El subtítulo es el “qué sigue”: no dejamos al cliente colgado.
    draw.text(
        (ANCHO // 2, y_titulo + 102),
        subtitulo,
        font=fuente_sub,
        fill=COLOR_MUTED,
        anchor='mt',
    )
    _pegar_logo(img, logo, centro_x=ANCHO // 2, y=ALTO - 130, ancho_max=180)
    _guardar_png(img, ruta)


# ===========================================================================
# LOGO (PNG estático, SVG + rsvg-convert, o None)
# ===========================================================================

def _cargar_logo_blanco(tmp_dir: str) -> Image.Image | None:
    """
    Busca el logo blanco SIC. Pillow no lee SVG: si solo hay SVG, se rasteriza.

    Args:
        tmp_dir: carpeta temporal para el PNG rasterizado del SVG.

    Returns:
        Imagen RGBA o None si no hay logo (las tarjetas se pintan igual).

    Efectos secundarios:
        Puede crear un PNG temporal con rsvg-convert.
    """
    ruta_png = _buscar_static('images/logos/logo_sic_white.png')
    if ruta_png:
        try:
            return Image.open(ruta_png).convert('RGBA')
        except OSError as exc:
            logger.warning('[REWIND-SLIDES] No se pudo abrir logo PNG: %s', exc)

    ruta_svg = _buscar_static('images/logos/logo_sic_white.svg')
    if ruta_svg:
        rsvg = shutil.which('rsvg-convert')
        if rsvg:
            tmp_png = os.path.join(tmp_dir, 'logo_intro_raster.png')
            try:
                res = subprocess.run(
                    [rsvg, '-w', '480', ruta_svg, '-o', tmp_png],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                if res.returncode == 0 and os.path.isfile(tmp_png):
                    return Image.open(tmp_png).convert('RGBA')
                logger.warning('[REWIND-SLIDES] rsvg-convert falló: %s', (res.stderr or '')[:200])
            except (OSError, subprocess.TimeoutExpired) as exc:
                logger.warning('[REWIND-SLIDES] rsvg-convert no disponible: %s', exc)

    logger.info('[REWIND-SLIDES] Sin logo — las tarjetas se pintan solo con texto')
    return None


def _buscar_static(relativo: str) -> str | None:
    """
    Resuelve un archivo de static/ (finders de Django, luego ruta del repo).

    Args:
        relativo: ruta bajo static/, ej. ``images/logos/logo_sic_white.png``.

    Returns:
        Ruta absoluta si el archivo existe; None si no.
    """
    try:
        from django.contrib.staticfiles import finders
        encontrado = finders.find(relativo)
        if encontrado and os.path.isfile(encontrado):
            return encontrado
    except Exception:
        # Fuera de Django (tests aislados) caemos al fallback del repo.
        pass

    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    fallback = os.path.join(raiz, 'static', relativo)
    if os.path.isfile(fallback):
        return fallback
    return None
