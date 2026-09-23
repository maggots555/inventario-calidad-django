"""
Texto plano del correo de encuesta de satisfacción.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
El HTML lleva cinco estrellas. Si la bandeja bloquea el HTML, el cliente
igual debe poder abrir cada calificación (?estrellas=1 … 5) y el botón
de respaldo. Esta función copia el texto de
`emails/feedback_satisfaccion.html`. No envía correo.
"""

from __future__ import annotations


_ETIQUETAS_ESTRELLAS = (
    (1, 'Muy malo'),
    (2, 'Malo'),
    (3, 'Regular'),
    (4, 'Bueno'),
    (5, 'Excelente'),
)


def construir_texto_plano_feedback_satisfaccion(context: dict) -> str:
    """
    Arma el cuerpo text/plain de la encuesta de satisfacción.

    Objetivo de negocio:
        El cliente puede calificar o abrir la encuesta aunque su bandeja
        no muestre las estrellas del HTML.

    Args:
        context: El mismo diccionario que `feedback_satisfaccion.html`.
            Claves: folio, tipo_equipo, marca_equipo, modelo_equipo,
            fecha_entrega, feedback_url, dias_vigencia, fecha_envio.

    Returns:
        str: Cuerpo en texto plano, con saltos de línea.

    Efectos secundarios:
        Ninguno. No toca BD ni envía correo.
    """
    tipo = (context.get('tipo_equipo') or '').strip()
    marca = (context.get('marca_equipo') or '').strip()
    modelo = (context.get('modelo_equipo') or '').strip()
    # EXPLICACIÓN: el HTML pone un guion largo solo si hay tipo de equipo.
    if tipo:
        equipo = f"{tipo} — {marca} {modelo}".strip()
    else:
        equipo = f'{marca} {modelo}'.strip()

    url = (context.get('feedback_url') or '').strip()
    lineas = [
        '¡Tu equipo fue entregado!',
        'Nos gustaría conocer cómo fue tu experiencia con nosotros.',
        '',
        'EQUIPO REPARADO',
        equipo,
        f"Folio: {context.get('folio') or ''}",
    ]

    fecha_entrega = (context.get('fecha_entrega') or '').strip()
    if fecha_entrega:
        lineas.append(f'Entregado el {fecha_entrega}')

    lineas.extend(
        [
            '',
            '¿Cómo te tratamos?',
            (
                'Tu opinión es muy importante para nosotros. Toca una estrella para '
                'empezar: te abre el formulario con esa calificación ya marcada. '
                'Completarlo toma unos 2 minutos.'
            ),
            '',
            'Toca una estrella para calificar:',
        ]
    )
    # Cada número conserva la misma URL que el enlace de la estrella HTML.
    for numero, etiqueta in _ETIQUETAS_ESTRELLAS:
        lineas.append(f'{numero} {etiqueta}: {url}?estrellas={numero}')

    lineas.extend(
        [
            '',
            '¿No se ven las estrellas? Usa este botón:',
            'O completa la encuesta aquí:',
            url,
            '',
            (
                'Este enlace es personal y de uso único. '
                f"Válido durante {context.get('dias_vigencia') or ''} días "
                'desde la fecha de entrega.'
            ),
            '',
            'SOBRE LA ENCUESTA:',
            'Toca una estrella para abrir el formulario ya calificado',
            'No requiere crear cuenta ni iniciar sesión',
            'El enlace es seguro y solo funciona una vez',
            'Tus respuestas son confidenciales',
            '',
            'SIC - Comercialización y Servicios',
            'sicfix.mx: https://sicfix.mx',
            '',
            'Visítanos y síguenos en nuestras redes sociales',
            'Sitio Web: https://sicfix.mx',
            'Instagram: https://instagram.com/sicfix.mx',
            'Facebook: https://facebook.com/sicfix.mx',
            'WhatsApp: https://wa.me/523318189988',
            '',
            f"Este correo fue enviado el {context.get('fecha_envio') or ''}",
        ]
    )
    return '\n'.join(lineas)
