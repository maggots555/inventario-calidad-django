"""
Texto plano del correo de evidencia en video al cliente.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
El HTML lleva miniaturas y botones. Si la bandeja bloquea el HTML, el
cliente igual debe leer el mismo aviso y las mismas URLs de cada video.
Esta función copia el texto de `evidencia_video_cliente.html`. No envía.
"""

from __future__ import annotations

from django.template.defaultfilters import date as date_filter


def construir_texto_plano_evidencia_video(context: dict) -> str:
    """
    Arma el cuerpo text/plain del correo de evidencia en video.

    Objetivo de negocio:
        El cliente puede abrir cada video y el seguimiento aunque su
        bandeja no muestre el HTML.

    Args:
        context: El mismo diccionario que `evidencia_video_cliente.html`.
            Claves: orden, detalle, videos_data, cantidad_videos,
            analisis_ia_texto, analisis_ia_modelo, mensaje_personalizado,
            seguimiento_url, empresa_nombre, pais_nombre,
            whatsapp_empleado, fecha_envio_texto, hora_envio_texto.

    Returns:
        str: Cuerpo en texto plano, con saltos de línea.

    Efectos secundarios:
        Ninguno. No toca BD ni envía correo.
    """
    detalle = context.get('detalle')
    orden = context.get('orden')

    # EXPLICACIÓN: misma regla que el HTML: orden de cliente, si no, interna.
    orden_cliente = getattr(detalle, 'orden_cliente', '') or ''
    numero_orden = orden_cliente or getattr(orden, 'numero_orden_interno', '')

    tipo = getattr(detalle, 'tipo_equipo', '') or ''
    marca = getattr(detalle, 'marca', '') or ''
    modelo = getattr(detalle, 'modelo', '') or ''
    equipo = ' '.join(parte for parte in (tipo, marca, modelo) if parte).strip()
    numero_serie = getattr(detalle, 'numero_serie', '') or ''

    fecha_ingreso = getattr(orden, 'fecha_ingreso', None)
    fecha_ingreso_texto = date_filter(fecha_ingreso, 'd/m/Y H:i') if fecha_ingreso else ''

    cantidad = context.get('cantidad_videos') or 0
    lineas = [
        'Evidencia en video del servicio',
        'Registro Visual del Proceso de Reparación',
        '',
        'Estimado/a cliente,',
        '',
        (
            'Le compartimos la evidencia en video del servicio realizado a su equipo. '
            'Estos videos documentan el proceso de diagnóstico y reparación llevado a cabo '
            'por nuestro equipo técnico.'
        ),
        '',
        'INFORMACIÓN DE SU EQUIPO',
        f'Número de Orden: {numero_orden}',
        f'Equipo: {equipo}',
        f'Número de Serie: {numero_serie}',
        f'Fecha de Ingreso: {fecha_ingreso_texto}',
        '',
    ]

    # EXPLICACIÓN: la IA es opcional. Si falló, el plano tampoco la menciona.
    analisis = (context.get('analisis_ia_texto') or '').strip()
    if analisis:
        modelo_ia = context.get('analisis_ia_modelo') or ''
        lineas.extend(
            [
                'RESUMEN EJECUTIVO DEL SERVICIO',
                analisis,
                '',
                (
                    f'Resumen generado automáticamente por IA ({modelo_ia}) a partir de '
                    'los videos de evidencia. Este reporte describe las acciones '
                    'observables durante el proceso de servicio.'
                ),
                '',
            ]
        )

    lineas.append(f'VIDEOS DE EVIDENCIA ({cantidad})')
    lineas.append('')
    # Cada video lleva tipo, nota, duración y la misma URL del botón HTML.
    for video in context.get('videos_data') or []:
        lineas.extend(_lineas_de_un_video(video))

    mensaje = (context.get('mensaje_personalizado') or '').strip()
    if mensaje:
        lineas.extend(['Mensaje adicional del equipo:', mensaje, ''])

    lineas.extend(
        [
            'INFORMACIÓN IMPORTANTE',
            'Los videos adjuntos documentan el proceso de servicio de su equipo.',
            'Esta evidencia forma parte de nuestro registro de calidad y transparencia.',
            'Si tiene alguna pregunta sobre el servicio realizado, no dude en contactarnos.',
            'Le mantendremos informado sobre cualquier actualización de su equipo.',
            '',
            'Gracias por confiar en nuestros servicios.',
            '',
        ]
    )

    seguimiento_url = (context.get('seguimiento_url') or '').strip()
    if seguimiento_url:
        lineas.extend(
            [
                'Consulta el estado de tu equipo en cualquier momento:',
                'Ver seguimiento de mi equipo:',
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
            'Sitio Web: https://sicfix.mx/',
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


def _lineas_de_un_video(video: dict) -> list[str]:
    """
    Arma las líneas de un video para el texto plano.

    Objetivo de negocio:
        Cada video del correo HTML aparece en el plano con su tipo,
        descripción, duración y la URL para reproducirlo.

    Args:
        video: Un elemento de videos_data (tipo_display, descripcion,
            duracion, tamano, video_url).

    Returns:
        list[str]: Líneas listas para unir con saltos de línea.

    Efectos secundarios:
        Ninguno.
    """
    lineas = [str(video.get('tipo_display') or '')]

    descripcion = (video.get('descripcion') or '').strip()
    if descripcion:
        lineas.append(f'"{descripcion}"')

    # EXPLICACIÓN: duración y tamaño van en la misma línea, como en el HTML.
    duracion = (video.get('duracion') or '').strip()
    tamano = (video.get('tamano') or '').strip()
    meta = []
    if duracion:
        meta.append(duracion)
    if tamano:
        meta.append(f'{tamano} MB')
    if meta:
        lineas.append(' · '.join(meta))

    url = (video.get('video_url') or '').strip()
    if url:
        lineas.extend(['Reproducir video:', url])

    lineas.append('')
    return lineas
