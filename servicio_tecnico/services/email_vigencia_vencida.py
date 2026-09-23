"""
Texto plano del correo de cotización vencida por falta de respuesta.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Este aviso no tiene botón. Si la bandeja bloquea el HTML, el cliente
igual debe leer que la cotización ya no está vigente y qué puede hacer.
Esta función copia el texto de `emails/vigencia_vencida.html`. No envía.
"""

from __future__ import annotations


def construir_texto_plano_vigencia_vencida(context: dict) -> str:
    """
    Arma el cuerpo text/plain del aviso de cotización vencida.

    Objetivo de negocio:
        El cliente entiende que la cotización ya no está vigente aunque
        su bandeja no muestre el HTML.

    Args:
        context: El mismo diccionario que `vigencia_vencida.html`.
            Claves: nombre_cliente, folio, marca_equipo, modelo_equipo,
            fecha_envio.

    Returns:
        str: Cuerpo en texto plano, con saltos de línea.

    Efectos secundarios:
        Ninguno. No toca BD ni envía correo.
    """
    marca = (context.get('marca_equipo') or '').strip()
    modelo = (context.get('modelo_equipo') or '').strip()
    equipo = ' '.join(parte for parte in (marca, modelo) if parte).strip()

    lineas = [
        'Aviso de cotización vencida',
        f"Folio {context.get('folio') or ''}",
        '',
        f"Estimado/a {context.get('nombre_cliente') or ''},",
        '',
        (
            'Le informamos que la cotización de su equipo ha vencido '
            'por falta de respuesta dentro del plazo establecido.'
        ),
        '',
        'INFORMACIÓN DE SU EQUIPO',
        f"Folio: {context.get('folio') or ''}",
        f'Equipo: {equipo}',
        '',
        'IMPORTANTE',
        'La cotización que le fue enviada previamente ya no se encuentra vigente.',
        (
            'Si desea retomar el servicio o solicitar una nueva cotización, '
            'por favor comuníquese con nosotros a la brevedad.'
        ),
        '',
        'PRÓXIMOS PASOS',
        'Si desea una nueva cotización, contáctenos directamente.',
        'Los precios y disponibilidad de piezas pueden variar respecto a la cotización original.',
        'Recuerde que su equipo sigue en nuestras instalaciones hasta nuevo aviso.',
        '',
        'Gracias por confiar en nuestros servicios.',
        '',
        'Sistema de Servicio Técnico',
        'Este es un correo automático no supervisado.',
        'Por favor, NO RESPONDA a este correo.',
        'Para seguimiento de su orden, contacte directamente a su responsable.',
        '',
        'Visítanos y síguenos en nuestras redes sociales',
        'Sitio Web: https://sicfix.mx/',
        'Instagram: https://www.instagram.com/sic_mexico/?hl=es',
        'Facebook: https://www.facebook.com/LatAmSic',
        'WhatsApp: https://wa.me/',
        '',
        f"Enviado el {context.get('fecha_envio') or ''}",
    ]
    return '\n'.join(lineas)
