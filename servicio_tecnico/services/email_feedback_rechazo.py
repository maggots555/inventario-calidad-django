"""
Texto plano del correo de feedback por rechazo de cotización.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
El HTML lleva un botón. Si la bandeja bloquea el HTML, el cliente igual
debe leer el aviso y poder copiar el enlace personal. Esta función copia
el texto de `emails/feedback_rechazo.html`. No envía correo.
"""

from __future__ import annotations


def construir_texto_plano_feedback_rechazo(context: dict) -> str:
    """
    Arma el cuerpo text/plain del correo de feedback de rechazo.

    Objetivo de negocio:
        El cliente puede abrir o copiar su enlace de comentario aunque
        su bandeja no muestre el HTML.

    Args:
        context: El mismo diccionario que `feedback_rechazo.html`.
            Claves: nombre_cliente, folio, tipo_equipo, marca_equipo,
            modelo_equipo, motivo_rechazo, piezas, monto_total,
            feedback_url, dias_vigencia, fecha_envio.

    Returns:
        str: Cuerpo en texto plano, con saltos de línea.

    Efectos secundarios:
        Ninguno. No toca BD ni envía correo.
    """
    nombre = context.get('nombre_cliente') or ''
    tipo = context.get('tipo_equipo') or ''
    marca = context.get('marca_equipo') or ''
    modelo = context.get('modelo_equipo') or ''
    equipo = ' '.join(parte for parte in (tipo, marca, modelo) if parte).strip()
    url = (context.get('feedback_url') or '').strip()

    lineas = [
        'Tu opinión nos importa',
        'Nos gustaría conocer tu experiencia',
        '',
        f'Estimado/a {nombre},',
        '',
        (
            'Notamos que decidiste no continuar con la cotización de tu equipo. '
            'Nos gustaría mucho conocer tu opinión para poder mejorar nuestro servicio. '
            'Tu comentario es completamente confidencial.'
        ),
        '',
        'INFORMACIÓN DE TU EQUIPO',
        f"Folio: {context.get('folio') or ''}",
        f'Equipo: {equipo}',
        f"Motivo registrado: {context.get('motivo_rechazo') or ''}",
        '',
    ]

    # EXPLICACIÓN: la tabla solo sale si hay piezas rechazadas, igual que el HTML.
    piezas = context.get('piezas') or []
    if piezas:
        lineas.extend(_lineas_de_cotizacion(piezas, context))

    lineas.extend(
        [
            'Tomará menos de 1 minuto. Solo queremos saber qué podemos hacer mejor.',
            'Dejar mi comentario:',
            url,
            f"Este enlace es personal y expira en {context.get('dias_vigencia') or ''} días.",
            '',
            'INFORMACIÓN',
            'Tu respuesta es anónima y confidencial.',
            'No necesitas crear cuenta ni iniciar sesión.',
            'El enlace solo puede usarse una vez.',
            'Si el enlace no funciona, copia y pega esta dirección en tu navegador:',
            url,
            '',
            'Gracias por tu tiempo y confianza.',
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
    )
    return '\n'.join(lineas)


def _lineas_de_cotizacion(piezas: list, context: dict) -> list[str]:
    """
    Arma el detalle de piezas para el texto plano.

    Objetivo de negocio:
        El cliente ve las mismas piezas y el total de piezas, aunque no
        pueda ver la tabla HTML. La mano de obra no se incluye.

    Args:
        piezas: Lista de dicts con nombre_pieza, cantidad y costo_unitario.
        context: Contexto del correo; usa monto_total.

    Returns:
        list[str]: Líneas del bloque, incluida una línea en blanco final.

    Efectos secundarios:
        Ninguno.
    """
    lineas = [
        'DETALLE DE LA COTIZACIÓN',
        'Pieza / Componente | Cant. | Subtotal',
    ]
    # El HTML muestra el costo unitario en la columna Subtotal: se respeta.
    for pieza in piezas:
        nombre = pieza.get('nombre_pieza') or ''
        cantidad = pieza.get('cantidad')
        costo = _dinero(pieza.get('costo_unitario'))
        lineas.append(f'{nombre} | {cantidad} | ${costo}')

    lineas.extend(
        [
            f"Total cotizado: ${_dinero(context.get('monto_total'))}",
            '',
        ]
    )
    return lineas


def _dinero(valor) -> str:
    """
    Formatea un monto con dos decimales, como floatformat:2 del HTML.

    Args:
        valor: Número, Decimal o None.

    Returns:
        str: Monto con dos decimales, o el texto original si no es número.

    Efectos secundarios:
        Ninguno.
    """
    if valor is None:
        return '0.00'
    try:
        return f'{float(valor):.2f}'
    except (TypeError, ValueError):
        return str(valor)
