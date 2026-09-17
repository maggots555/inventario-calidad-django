"""
Campañas publicitarias para la hoja extra del PDF OOW.

EXPLICACIÓN PARA PRINCIPIANTES:
------------------------------------------------
Los banners del seguimiento (BannerPromocional) son para la WEB: se recortan
a un slot (header, footer, rascacielos). Este módulo es el hermano para
PAPEL/PDF: se queda con la proporción original y solo baja de tamaño si
la foto es enorme, para que el PDF no pese de más.

No vive en models.py (regla fat models): vigencia + Pillow son cerebro,
no tabla.
"""

from __future__ import annotations

import logging
import os
from io import BytesIO
from typing import List

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils import timezone
from PIL import Image as PILImage, ImageOps

logger = logging.getLogger('servicio_tecnico')

# Tope de píxeles: una hoja carta a ~150 dpi cabe holgada; no recortamos.
ANCHO_MAX_PX = 1800
ALTO_MAX_PX = 1800
JPEG_QUALITY = 85


def obtener_campanias_vigentes() -> List:
    """
    Campañas activas cuyo calendario cubre el momento actual.

    Returns:
        Lista de CampaniaPdfOow ordenada (menor ``orden_display`` primero).

    Efectos secundarios:
        Ninguno (solo SELECT).
    """
    from servicio_tecnico.models import CampaniaPdfOow

    ahora = timezone.now()
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # activo=True es el interruptor manual. Las fechas hacen el resto:
    # si hoy está entre inicio y fin, la campaña entra al PDF.
    return list(
        CampaniaPdfOow.objects.filter(
            activo=True,
            fecha_inicio__lte=ahora,
            fecha_fin__gte=ahora,
        ).order_by('orden_display', '-fecha_creacion')
    )


def optimizar_imagen_si_cambio(campania) -> None:
    """
    Si la imagen es nueva o cambió, baja de tamaño sin recortar.

    Args:
        campania: instancia CampaniaPdfOow (puede no estar guardada aún).

    Efectos secundarios:
        Reemplaza ``campania.imagen`` en memoria (save=False). El save()
        del modelo es quien persiste el archivo.
    """
    if not _imagen_acaba_de_cambiar(campania):
        return

    try:
        _redimensionar_proporcional(campania)
    except Exception as exc:
        # Si Pillow falla, no bloqueamos a marketing: se guarda el original.
        logger.warning(
            '[CAMPANIA_PDF_OOW] No se pudo optimizar "%s": %s',
            getattr(campania, 'titulo', '?'),
            exc,
        )


def _imagen_acaba_de_cambiar(campania) -> bool:
    """
    True si hay archivo y es distinto al que ya estaba en BD.

    Args:
        campania: CampaniaPdfOow en save().

    Returns:
        bool
    """
    from servicio_tecnico.models import CampaniaPdfOow

    if not campania.imagen or not hasattr(campania.imagen, 'file'):
        return False
    if not campania.pk:
        return True
    try:
        original = CampaniaPdfOow.objects.get(pk=campania.pk)
    except CampaniaPdfOow.DoesNotExist:
        return True
    return original.imagen.name != campania.imagen.name


def _redimensionar_proporcional(campania) -> None:
    """
    Escala la foto si pasa de 1800 px; mantiene PNG con transparencia.

    Args:
        campania: CampaniaPdfOow con imagen recién subida.

    Efectos secundarios:
        ``campania.imagen.save(..., save=False)`` con el buffer nuevo.
    """
    archivo = campania.imagen
    if hasattr(archivo, 'seek'):
        archivo.seek(0)
    img = PILImage.open(archivo)
    img = ImageOps.exif_transpose(img)

    # Ya cabe: no re-encodeamos (evita perder calidad al re-guardar).
    if img.width <= ANCHO_MAX_PX and img.height <= ALTO_MAX_PX:
        return

    # thumbnail respeta el ratio: 2400×1200 → 1800×900, no recorta.
    img.thumbnail((ANCHO_MAX_PX, ALTO_MAX_PX), resample=PILImage.LANCZOS)

    tiene_alpha = img.mode in ('RGBA', 'LA', 'PA')
    if tiene_alpha:
        formato, content_type, extension = 'PNG', 'image/png', '.png'
    else:
        if img.mode != 'RGB':
            img = img.convert('RGB')
        formato, content_type, extension = 'JPEG', 'image/jpeg', '.jpg'

    buffer = BytesIO()
    if formato == 'JPEG':
        img.save(buffer, format='JPEG', quality=JPEG_QUALITY, optimize=True)
    else:
        img.save(buffer, format='PNG', optimize=True)
    buffer.seek(0)

    nombre_base = os.path.splitext(os.path.basename(campania.imagen.name))[0]
    nuevo_nombre = f'{nombre_base}_oow{extension}'
    campania.imagen.save(
        nuevo_nombre,
        InMemoryUploadedFile(
            file=buffer,
            field_name='imagen',
            name=nuevo_nombre,
            content_type=content_type,
            size=buffer.getbuffer().nbytes,
            charset=None,
        ),
        save=False,
    )
    logger.info(
        '[CAMPANIA_PDF_OOW] "%s" escalada a %sx%s (%s)',
        campania.titulo,
        img.width,
        img.height,
        formato,
    )
