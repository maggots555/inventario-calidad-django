"""
Texto plano del correo de fotografías de egreso.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Igual que en ingreso: HTML + text/plain. El mensaje clave (el equipo
aún NO se puede recoger) debe ir también en texto, por si la bandeja
bloquea el HTML.
"""

from __future__ import annotations

from django.template.defaultfilters import date as date_filter


def construir_texto_plano_imagenes_egreso(context: dict) -> str:
    """
    Arma el cuerpo text/plain del correo de fotos de egreso.

    Objetivo de negocio:
        El cliente lee que el servicio concluyó, que hay fotos adjuntas
        y que AÚN no puede recoger el equipo, aunque Gmail bloquee HTML.

    Args:
        context: El mismo diccionario que `imagenes_egreso_cliente.html`.
            Claves: orden, detalle, mensaje_personalizado, cantidad_imagenes,
            empresa_nombre, pais_nombre, fecha_envio_texto, hora_envio_texto,
            seguimiento_url, whatsapp_empleado.

    Returns:
        str: Cuerpo en texto plano.

    Efectos secundarios:
        Ninguno.
    """
    detalle = context.get('detalle')
    orden = context.get('orden')

    orden_cliente = getattr(detalle, 'orden_cliente', '') or ''
    numero_orden = orden_cliente or getattr(orden, 'numero_orden_interno', '')

    tipo = getattr(detalle, 'tipo_equipo', '') or ''
    marca = getattr(detalle, 'marca', '') or ''
    modelo = getattr(detalle, 'modelo', '') or ''
    equipo = ' '.join(parte for parte in (tipo, marca, modelo) if parte).strip()
    numero_serie = getattr(detalle, 'numero_serie', '') or ''

    fecha_ingreso = getattr(orden, 'fecha_ingreso', None)
    fecha_ingreso_texto = date_filter(fecha_ingreso, 'd/m/Y H:i') if fecha_ingreso else ''
    fecha_fin = getattr(orden, 'fecha_finalizacion', None)
    fecha_fin_texto = date_filter(fecha_fin, 'd/m/Y H:i') if fecha_fin else ''

    # EXPLICACIÓN: coincide con el {% if detalle.tiene_cargador %} del HTML.
    if getattr(detalle, 'tiene_cargador', False):
        sn = (getattr(detalle, 'numero_serie_cargador', '') or '').strip()
        cargador = f'Incluido (S/N: {sn})' if sn else 'Incluido'
    else:
        cargador = 'No incluido'

    cantidad = context.get('cantidad_imagenes') or 0
    plural = 's' if cantidad != 1 else ''

    lineas = [
        'Fotografías de egreso',
        'Registro de estado final del equipo',
        '',
        'Estimado/a cliente,',
        '',
        (
            'Le informamos que el proceso de servicio técnico de su equipo ha concluido '
            'y adjuntamos a este correo las fotografías del estado final (egreso) del equipo. '
            'Estas imágenes documentan las condiciones en las que se encuentra su dispositivo '
            'al término del servicio.'
        ),
        '',
        'IMPORTANTE — Su equipo aún no está listo para ser recolectado',
        'Este correo NO es una confirmación de que puede acudir a recoger su equipo.',
        (
            'Para recoger su dispositivo, deberá esperar la notificación adicional '
            'que le informará cuando su equipo esté disponible y listo para ser entregado.'
        ),
        'Le pedimos paciencia y le agradecemos su comprensión.',
        '',
        'INFORMACIÓN DE SU EQUIPO',
        f'Número de orden: {numero_orden}',
        f'Equipo: {equipo}',
        f'Número de serie: {numero_serie}',
        f'Fecha de ingreso: {fecha_ingreso_texto}',
    ]
    if fecha_fin_texto:
        lineas.append(f'Fecha de finalización: {fecha_fin_texto}')
    lineas.extend([f'Cargador: {cargador}', ''])

    mensaje = (context.get('mensaje_personalizado') or '').strip()
    if mensaje:
        lineas.extend(['MENSAJE ADICIONAL', mensaje, ''])

    lineas.extend(
        [
            'IMÁGENES ADJUNTAS',
            f'{cantidad} fotografía{plural} adjunta{plural} a este correo',
            '',
            'INFORMACIÓN IMPORTANTE',
            'Las fotografías adjuntas muestran el estado final en el que se encuentra su equipo.',
            'Estas imágenes forman parte del registro de egreso para su tranquilidad y seguridad.',
            'Si tiene alguna pregunta sobre el servicio realizado, no dude en contactarnos.',
            'Recuerde esperar la notificación de disponibilidad antes de acudir por su equipo.',
            '',
            'Gracias por confiar en nuestros servicios.',
            '',
        ]
    )

    seguimiento_url = (context.get('seguimiento_url') or '').strip()
    if seguimiento_url:
        # EXPLICACIÓN: el HTML de egreso usa “tú” en este CTA; el plano igual.
        lineas.extend(
            [
                'Consulta el estado de tu equipo en cualquier momento:',
                seguimiento_url,
                '',
            ]
        )

    lineas.extend(
        [
            'Sistema de Servicio Técnico',
            'IMPORTANTE: Este es un correo automático no supervisado.',
            'Por favor, NO RESPONDA a este correo.',
            'Para seguimiento de su orden, contacte directamente a su responsable de seguimiento.',
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
