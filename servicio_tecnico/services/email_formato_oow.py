"""
Texto plano del correo de Formato de Servicio Fuera de Garantía (OOW).

EXPLICACIÓN PARA PRINCIPIANTES:
================================
El HTML muestra el PDF firmado y los datos de la orden SICSER. El
text/plain debe decir lo mismo por si Gmail/Outlook bloquean el HTML:
qué documento va adjunto, datos del equipo y a quién contactar.
"""

from __future__ import annotations

from django.template.defaultfilters import date as date_filter


def construir_texto_plano_formato_oow(context: dict) -> str:
    """
    Arma el cuerpo text/plain del correo de formato OOW.

    Objetivo de negocio:
        El cliente recibe el PDF firmado aunque su bandeja bloquee HTML.

    Args:
        context: El mismo diccionario que `formato_oow_cliente.html`.

    Returns:
        str: Cuerpo en texto plano.

    Efectos secundarios:
        Ninguno.
    """
    detalle = context.get('detalle')
    orden = context.get('orden')
    orden_sicser = context.get('orden_sicser') or ''

    # EXPLICACIÓN: el HTML junta tipo + marca + modelo; aquí igual, sin huecos.
    tipo = getattr(detalle, 'tipo_equipo', '') or ''
    marca = getattr(detalle, 'marca', '') or ''
    modelo = getattr(detalle, 'modelo', '') or ''
    equipo = ' '.join(parte for parte in (tipo, marca, modelo) if parte).strip()

    # EXPLICACIÓN: el template usa default:"—" si no hay Service Tag.
    numero_serie = (getattr(detalle, 'numero_serie', '') or '').strip() or '—'

    fecha_ingreso = getattr(orden, 'fecha_ingreso', None)
    fecha_ingreso_texto = (
        date_filter(fecha_ingreso, 'd/m/Y H:i') if fecha_ingreso else ''
    )

    nombre = (context.get('nombre_empleado') or '').strip()
    email = (context.get('email_empleado') or '').strip()
    if nombre:
        contacto = f'{nombre} ({email})' if email else nombre
    else:
        contacto = 'su responsable de seguimiento'

    lineas = [
        'Formato de servicio fuera de garantía',
        f'Orden: {orden_sicser}',
        '',
        'Buen día estimado usuario',
        '',
        (
            f"Me dirijo de {context.get('empresa_nombre') or ''} para enviarle el "
            'Formato de Servicio Fuera de Garantía (OOW) correspondiente a su '
            'equipo de cómputo. El documento firmado se encuentra adjunto en este correo.'
        ),
        '',
        'Agradecemos su preferencia y nos ponemos a sus órdenes para esta y futuras ocasiones.',
        '',
        'INFORMACIÓN DE SU EQUIPO',
        f'Número de orden: {orden_sicser}',
        f'Equipo: {equipo}',
        f'Service Tag: {numero_serie}',
        f'Fecha de ingreso: {fecha_ingreso_texto}',
        '',
        'ARCHIVOS ADJUNTOS',
        '1 archivo adjunto a este correo',
        '1 PDF — Formato de Servicio Fuera de Garantía firmado',
        '',
        'INFORMACIÓN IMPORTANTE',
        'El documento PDF adjunto es el formato oficial de servicio firmado.',
        'Conserve este archivo para su expediente y seguimiento.',
        'Si tiene alguna pregunta, contacte a su responsable de seguimiento.',
        '',
        'Gracias por confiar en nuestros servicios.',
        '',
        'Sistema de Servicio Técnico',
    ]

    # EXPLICACIÓN: el HTML solo pinta “Contacto:” si hay email del técnico.
    if email:
        lineas.append(f'Contacto: {email}')

    lineas.extend(
        [
            'IMPORTANTE: Este es un correo automático no supervisado.',
            'Por favor, NO RESPONDA a este correo.',
            f'Para seguimiento de su orden, contacte directamente a {contacto}.',
            '',
            str(context.get('empresa_nombre') or ''),
            str(context.get('pais_nombre') or ''),
            '',
            'Visítanos y síguenos en nuestras redes sociales',
            'Sitio web: https://sicfix.mx/',
            'Instagram: https://www.instagram.com/sic_mexico/?hl=es',
            'Facebook: https://www.facebook.com/LatAmSic',
        ]
    )

    whatsapp = (context.get('whatsapp_empleado') or '').strip()
    if whatsapp:
        lineas.append(f'WhatsApp: https://wa.me/{whatsapp}')

    lineas.extend(
        [
            '',
            (
                f"Enviado el {context.get('fecha_envio_texto') or ''} "
                f"a las {context.get('hora_envio_texto') or ''}"
            ),
        ]
    )

    return '\n'.join(lineas)
