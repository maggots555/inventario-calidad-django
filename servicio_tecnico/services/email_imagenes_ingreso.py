"""
Texto plano del correo de fotografías de ingreso.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Los clientes de correo suelen pedir DOS versiones del mismo mensaje:

1. HTML (bonito, con tablas y colores)
2. text/plain (solo texto: se usa si el HTML está bloqueado o el lector
   es de accesibilidad)

Este módulo arma la versión de texto con el MISMO contenido que la
plantilla HTML `emails/imagenes_cliente.html` (orden, fotos, IA, enlace
de seguimiento). La tarea Celery solo llama a esta función y la adjunta.
"""

from __future__ import annotations

from django.template.defaultfilters import date as date_filter


def construir_texto_plano_imagenes_ingreso(context: dict) -> str:
    """
    Arma el cuerpo text/plain del correo de fotos de ingreso.

    Objetivo de negocio:
        El cliente debe poder leer el aviso (equipo recibido, fotos
        adjuntas, enlace de seguimiento) aunque su bandeja bloquee HTML.

    Args:
        context: El mismo diccionario que se pasa a render_to_string
            de `imagenes_cliente.html`. Claves esperadas: orden, detalle,
            mensaje_personalizado, cantidad_imagenes, empresa_nombre,
            pais_nombre, fecha_envio_texto, hora_envio_texto,
            seguimiento_url, analisis_ia_texto, analisis_ia_modelo,
            whatsapp_empleado.

    Returns:
        str: Cuerpo en texto plano, con saltos de línea.

    Efectos secundarios:
        Ninguno. No toca BD ni envía correo.
    """
    detalle = context.get('detalle')
    orden = context.get('orden')

    # EXPLICACIÓN: el nombre es opcional; si no está, el saludo genérico
    # coincide con la plantilla HTML.
    nombre_cliente = (getattr(detalle, 'nombre_cliente', '') or '').strip()
    saludo = f'Estimado/a {nombre_cliente},' if nombre_cliente else 'Estimado/a cliente,'

    orden_cliente = getattr(detalle, 'orden_cliente', '') or ''
    numero_orden = orden_cliente or getattr(orden, 'numero_orden_interno', '')

    tipo = getattr(detalle, 'tipo_equipo', '') or ''
    marca = getattr(detalle, 'marca', '') or ''
    modelo = getattr(detalle, 'modelo', '') or ''
    equipo = ' '.join(parte for parte in (tipo, marca, modelo) if parte).strip()
    numero_serie = getattr(detalle, 'numero_serie', '') or ''

    fecha_ingreso = getattr(orden, 'fecha_ingreso', None)
    fecha_ingreso_texto = date_filter(fecha_ingreso, 'd/m/Y H:i') if fecha_ingreso else ''

    cantidad = context.get('cantidad_imagenes') or 0
    plural = 's' if cantidad != 1 else ''

    lineas = [
        saludo,
        '',
        (
            'Le informamos que su equipo ha sido recibido en nuestras instalaciones '
            'y hemos registrado su estado de ingreso mediante las fotografías que '
            'adjuntamos a este correo.'
        ),
        '',
        'INFORMACIÓN DE SU EQUIPO',
        f'Número de orden: {numero_orden}',
        f'Equipo: {equipo}',
        f'Número de serie: {numero_serie}',
        f'Fecha de ingreso: {fecha_ingreso_texto}',
        '',
    ]

    mensaje = (context.get('mensaje_personalizado') or '').strip()
    if mensaje:
        lineas.extend(['MENSAJE ADICIONAL', mensaje, ''])

    lineas.extend(
        [
            'IMÁGENES ADJUNTAS',
            f'{cantidad} fotografía{plural} adjunta{plural} a este correo',
            '',
        ]
    )

    analisis = (context.get('analisis_ia_texto') or '').strip()
    if analisis:
        modelo_ia = context.get('analisis_ia_modelo') or ''
        lineas.extend(
            [
                'ANÁLISIS DE CONDICIÓN ESTÉTICA AL INGRESO',
                analisis,
                '',
                (
                    f'Análisis generado automáticamente por IA ({modelo_ia}) a partir '
                    'de las fotografías de ingreso. Este reporte documenta el estado '
                    'físico observable del equipo al momento de su recepción en el taller. '
                    'El técnico asignado podrá complementar o ajustar esta descripción '
                    'durante el proceso de diagnóstico.'
                ),
                '',
            ]
        )

    seguimiento_url = context.get('seguimiento_url') or ''
    if seguimiento_url:
        lineas.extend(
            [
                'Consulte el estado de su equipo en cualquier momento:',
                seguimiento_url,
                '',
            ]
        )

    lineas.extend(
        [
            'INFORMACIÓN IMPORTANTE',
            'Las fotografías adjuntas muestran el estado en el que recibimos su equipo.',
            'Estas imágenes forman parte del registro de ingreso para su tranquilidad.',
            'Si tiene alguna pregunta o requiere información adicional, no dude en contactarnos.',
            'Le mantendremos informado sobre el progreso de su equipo.',
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
