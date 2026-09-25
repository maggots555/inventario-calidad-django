"""
Adjunta el logo SIC blanco (CID) a correos transaccionales de cliente.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Un correo HTML no “baja” imágenes de static/ como una página web.
La imagen se PEGA al mensaje con un Content-ID (CID). El HTML dice
``src="cid:logo_sic_white"`` y el cliente de correo busca ese adjunto.

Outlook no pinta SVG: por eso usamos PNG
(``static/images/logos/logo_sic_white.png``).

El PNG azul (``logo_sic.png``) sigue en static/ para PDF y favicon.
Los correos ya no lo adjuntan: la barra solo pide este blanco.
"""

from __future__ import annotations

import logging
from email.mime.image import MIMEImage

from django.contrib.staticfiles import finders

logger = logging.getLogger(__name__)

# Ruta bajo static/ y nombre CID que usa _email_brand_bar.html.
RUTA_LOGO_BLANCO = 'images/logos/logo_sic_white.png'
CID_LOGO_BLANCO = 'logo_sic_white'


def adjuntar_logo_blanco_email(email_msg, log_prefix: str = '[EMAIL]') -> bool:
    """
    Pega el PNG del logo SIC blanco como imagen inline (CID).

    Objetivo de negocio:
        La barra de marca de los correos de cliente muestra el logo
        blanco sobre fondo #1e293b. Sin este adjunto, el cliente ve
        el hueco roto o, si bloquea imágenes, el texto alt="SIC".

    Args:
        email_msg: EmailMessage o EmailMultiAlternatives ya creado.
        log_prefix: Prefijo de log de la tarea (ej. ``[DIAGNOSTICO]``).

    Returns:
        bool: True si se adjuntó; False si no había archivo o falló I/O.

    Efectos secundarios:
        Mutates ``email_msg`` (añade un MIMEImage). No toca BD ni envía.
    """
    try:
        # 1) Django busca el PNG en static/ (runserver y collectstatic).
        logo_path = finders.find(RUTA_LOGO_BLANCO)
        if not logo_path:
            logger.warning(
                '%s Logo blanco CID no encontrado: %s',
                log_prefix,
                RUTA_LOGO_BLANCO,
            )
            return False

        # 2) Bytes + Content-ID: el HTML usa src="cid:logo_sic_white".
        with open(logo_path, 'rb') as archivo_logo:
            logo_mime = MIMEImage(archivo_logo.read(), _subtype='png')
        logo_mime.add_header('Content-ID', f'<{CID_LOGO_BLANCO}>')
        logo_mime.add_header(
            'Content-Disposition',
            'inline',
            filename='logo_sic_white.png',
        )

        # 3) Se pega al mensaje; no se envía todavía (eso lo hace la tarea).
        email_msg.attach(logo_mime)
        return True
    except OSError as exc:
        logger.warning('%s Error al adjuntar logo blanco: %s', log_prefix, exc)
        return False
