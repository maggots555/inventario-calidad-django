"""
Texto plano del correo de video rewind de egreso.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
El HTML lleva un thumbnail del video. El text/plain debe decir lo mismo:
hay un resumen visual, la URL para verlo, y que AÚN no puede recoger.
"""

from __future__ import annotations

from django.template.defaultfilters import date as date_filter


def construir_texto_plano_rewind_egreso(context: dict) -> str:
    """
    Arma el cuerpo text/plain del correo de rewind de egreso.

    Objetivo de negocio:
        El cliente puede abrir el video y entiende que no recolecta aún,
        aunque su bandeja bloquee HTML e imágenes.

    Args:
        context: El mismo diccionario que `rewind_egreso_cliente.html`.

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

    if getattr(detalle, 'tiene_cargador', False):
        sn = (getattr(detalle, 'numero_serie_cargador', '') or '').strip()
        cargador = f'Incluido (S/N: {sn})' if sn else 'Incluido'
    else:
        cargador = 'No incluido'

    es_vm = bool(context.get('es_venta_mostrador'))
    if es_vm:
        intro_etapas = (
            'desde el estado de ingreso, la reparación, hasta el resultado final.'
        )
        video_etapas = (
            'El video reúne ingreso, reparación y egreso en una sola presentación.'
        )
    else:
        intro_etapas = (
            'desde el estado de ingreso, el diagnóstico, la reparación, hasta el resultado final.'
        )
        video_etapas = (
            'El video reúne ingreso, diagnóstico, reparación y egreso en una sola presentación.'
        )

    # EXPLICACIÓN: el HTML usa video_url|default:seguimiento_url para el play.
    url_video = (context.get('video_url') or context.get('seguimiento_url') or '').strip()
    url_seguimiento = (context.get('seguimiento_url') or '').strip()

    lineas = [
        'Resumen de tu servicio',
        'Todo el proceso de reparación, de inicio a fin',
        '',
        'Estimado/a cliente,',
        '',
        (
            'El servicio de su equipo ha concluido y queremos compartir '
            f'con usted un resumen visual completo de todo lo que se realizó: {intro_etapas}'
        ),
        '',
        'VIDEO RESUMEN DEL PROCESO',
        'Su equipo fue registrado fotográficamente en cada etapa del proceso.',
        video_etapas,
    ]
    if url_video:
        lineas.extend(['Toca aquí para reproducir el video:', url_video])
    if url_seguimiento:
        lineas.extend(['Ver el estado de mi equipo:', url_seguimiento])

    lineas.extend(
        [
            '',
            'INFORMACIÓN DE SU EQUIPO',
            f'Número de orden: {numero_orden}',
            f'Equipo: {equipo}',
            f'Número de serie: {numero_serie}',
            f'Fecha de ingreso: {fecha_ingreso_texto}',
        ]
    )
    if fecha_fin_texto:
        lineas.append(f'Fecha de finalización: {fecha_fin_texto}')
    lineas.extend(
        [
            f'Cargador: {cargador}',
            '',
            'IMPORTANTE — Confirme disponibilidad antes de recoger',
            (
                'Este correo le informa que el proceso técnico ha concluido '
                'y le muestra el resumen visual del trabajo realizado.'
            ),
            (
                'Sin embargo, para recoger su equipo deberá esperar la confirmación '
                'de disponibilidad por parte de su responsable de seguimiento. '
                'Le notificaremos cuando su dispositivo esté listo para ser entregado.'
            ),
            'Le pedimos paciencia y le agradecemos su confianza.',
            '',
            'INFORMACIÓN IMPORTANTE',
            'El video resumen documenta el estado del equipo en cada etapa del servicio.',
            'Si tiene alguna pregunta sobre el trabajo realizado, no dude en contactarnos.',
            'Recuerde esperar la notificación de disponibilidad antes de acudir por su equipo.',
            '',
            'Gracias por confiar en nuestros servicios.',
            '',
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
