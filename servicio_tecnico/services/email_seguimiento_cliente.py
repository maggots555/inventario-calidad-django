"""
Texto plano del correo de enlace de seguimiento público.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
El HTML se ve bonito; el text/plain es el respaldo si el cliente bloquea
imágenes o HTML. Debe decir lo mismo: folio, equipo, URL y responsable.
"""

from __future__ import annotations


def construir_texto_plano_seguimiento_cliente(context: dict) -> str:
    """
    Arma el cuerpo text/plain del correo de seguimiento.

    Objetivo de negocio:
        El cliente debe poder abrir el enlace aunque no se pinte el HTML.

    Args:
        context: Mismo diccionario que `seguimiento_cliente.html`.
            Claves: folio, tipo_equipo, marca_equipo, modelo_equipo,
            seguimiento_url, nombre_responsable, email_responsable,
            fecha_envio.

    Returns:
        str: Cuerpo en texto plano.

    Efectos secundarios:
        Ninguno.
    """
    tipo = (context.get('tipo_equipo') or '').strip()
    marca = (context.get('marca_equipo') or '').strip()
    modelo = (context.get('modelo_equipo') or '').strip()
    # EXPLICACIÓN: el HTML pone "Laptop — Dell XPS"; aquí igual, sin HTML.
    equipo = ' '.join(parte for parte in (marca, modelo) if parte).strip()
    if tipo:
        equipo = f'{tipo} — {equipo}' if equipo else tipo

    folio = context.get('folio') or ''
    url = context.get('seguimiento_url') or ''

    lineas = [
        'Seguimiento de tu equipo',
        'Consulta el estado de tu orden en cualquier momento.',
        '',
        'TU EQUIPO EN SERVICIO',
        equipo,
        f'Folio: {folio}',
        '',
        'Sigue de cerca tu reparación',
        (
            'Hemos creado un enlace personalizado para que puedas consultar el '
            'estado actual de tu equipo en cualquier momento. '
            'Verás cada paso del proceso de reparación conforme avance.'
        ),
        '',
        'Ver estado de mi equipo:',
        url,
        '',
        'SOBRE ESTE ENLACE',
        'No requiere crear cuenta ni iniciar sesión.',
        'El enlace es personal y seguro.',
        'Puedes consultarlo las veces que necesites.',
        'Se actualiza automáticamente con cada cambio de estado.',
        '',
        'TU RESPONSABLE DE SEGUIMIENTO',
    ]

    nombre = (context.get('nombre_responsable') or '').strip()
    if nombre:
        lineas.append(nombre)
        email = (context.get('email_responsable') or '').strip()
        if email:
            lineas.append(email)
    else:
        # EXPLICACIÓN: coincide con el {% else %} de la plantilla HTML.
        lineas.append('Pendiente de asignar')
        lineas.append('Se te notificará cuando se asigne a tu responsable.')

    lineas.extend(
        [
            '',
            'Sitio web: https://sicfix.mx',
            'Instagram: https://instagram.com/sicfix.mx',
            'Facebook: https://facebook.com/sicfix.mx',
            'WhatsApp: https://wa.me/523318189988',
            '',
            'SIC - Comercialización y Servicios',
            'https://sicfix.mx',
            f"Este correo fue enviado el {context.get('fecha_envio') or ''}",
        ]
    )

    return '\n'.join(lineas)
