"""
Imagen QR para PDFs ReportLab (seguimiento cliente, etc.).

EXPLICACIÓN PARA PRINCIPIANTES:
------------------------------------------------
`qrcode` dibuja un PNG en memoria; ReportLab lo pega como `Image`.
Si la librería no está o falla, devolvemos None: el PDF debe salir igual
(el de garantía ya usa este fail-safe).
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
from typing import Optional

from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage

logger = logging.getLogger('servicio_tecnico')


class ImagenQRClicable(RLImage):
    """
    Imagen ReportLab que, al hacer clic en el PDF digital, abre `url`.

    Args:
        filename: BytesIO o ruta PNG.
        url: URL absoluta del portal de seguimiento.
        width / height: tamaño en puntos (los pasa `imagen_qr_para_pdf`).
    """

    def __init__(self, filename, url: str = '', **kwargs):
        """
        Args:
            filename: buffer o ruta del PNG.
            url: enlace que se abre al tocar el QR.
            **kwargs: width, height, kind, etc. de RLImage.
        """
        super().__init__(filename, **kwargs)
        self._url_enlace = url or ''

    def draw(self) -> None:
        """Dibuja el PNG y registra un linkURL del tamaño del QR."""
        super().draw()
        if not self._url_enlace:
            return
        # relative=1: el rectángulo está en coords del flowable (0,0 → ancho,alto).
        self.canv.linkURL(
            self._url_enlace,
            (0, 0, self.drawWidth, self.drawHeight),
            relative=1,
        )


def _importar_qrcode():
    """
    Importa qrcode (se aísla para poder mockear ImportError en tests).

    Returns:
        módulo qrcode

    Raises:
        ImportError: si el paquete no está instalado.
    """
    import qrcode
    return qrcode


def imagen_qr_para_pdf(url: str, lado_mm: float = 28) -> Optional[RLImage]:
    """
    Genera un QR cuadrado listo para Platypus.

    Args:
        url: URL absoluta a codificar (portal de seguimiento).
        lado_mm: lado del cuadrado en milímetros (28 mm escanea bien en papel).

    Returns:
        ImagenQRClicable o None si qrcode no está / falla.

    Efectos secundarios:
        Ninguno sobre BD. Puede crear un PNG temporal si BytesIO no le gusta
        a ReportLab (se conserva en el propio flowable hasta doc.build()).
    """
    destino = (url or '').strip()
    if not destino:
        return None

    try:
        qrcode = _importar_qrcode()
    except ImportError:
        logger.warning('[QR_PDF] qrcode no disponible; se omite el código QR')
        return None

    try:
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # El token del enlace es largo; no forzamos version=1 (eso es para
        # URLs cortas tipo wa.me). fit=True elige la versión que quepa.
        # ERROR_CORRECT_M aguanta un poco de tinta corrida al imprimir.
        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=1,
        )
        qr.add_data(destino)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)

        lado = lado_mm * mm
        try:
            flowable = ImagenQRClicable(
                buf,
                url=destino,
                width=lado,
                height=lado,
            )
            # Evita que el GC cierre el buffer antes de build().
            flowable._qr_buffer = buf
            return flowable
        except Exception:
            # Algunas versiones de ReportLab exigen una ruta de archivo.
            fd, ruta = tempfile.mkstemp(suffix='.png')
            os.close(fd)
            with open(ruta, 'wb') as fh:
                fh.write(buf.getvalue())
            flowable = ImagenQRClicable(
                ruta,
                url=destino,
                width=lado,
                height=lado,
            )
            flowable._qr_temp_path = ruta
            return flowable
    except Exception as exc:
        logger.warning('[QR_PDF] No se pudo generar QR: %s', exc)
        return None
