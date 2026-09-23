"""
Texto plano del correo de Nota de Venta Directa (venta mostrador).

EXPLICACIÓN PARA PRINCIPIANTES:
================================
El HTML muestra el PDF y los datos de la orden. El text/plain debe
decir lo mismo por si la bandeja bloquea el HTML: qué documento va
adjunto, datos del equipo y a quién contactar. No envía correo.
"""

from __future__ import annotations

from django.template.defaultfilters import date as date_filter


def nombre_para_saludo(formato, detalle) -> str:
    """
    Elige el nombre que va en el saludo del correo.

    Objetivo de negocio:
        Si hay persona de contacto en el formato, se saluda por ese
        nombre. Si no, se usa el nombre del cliente de la orden.
        Vacío significa que el correo dirá “usuario”.

    Args:
        formato: FormatoServicioVentaMostrador (o un objeto con
            persona_contacto).
        detalle: DetalleEquipo (o un objeto con nombre_cliente). Puede
            ser None.

    Returns:
        str: Nombre limpio, o cadena vacía si no hay ninguno.

    Efectos secundarios:
        Ninguno.
    """
    # La persona del formato manda: es quien recibe la nota.
    contacto = (getattr(formato, 'persona_contacto', '') or '').strip()
    if contacto:
        return contacto
    return (getattr(detalle, 'nombre_cliente', '') or '').strip()


def nombre_saludo(context: dict) -> str:
    """
    Nombre ya resuelto para el saludo, o “usuario” si no hay.

    Args:
        context: Diccionario del correo. Usa la clave nombre_cliente.

    Returns:
        str: Nombre o la palabra usuario.

    Efectos secundarios:
        Ninguno.
    """
    return (context.get('nombre_cliente') or '').strip() or 'usuario'


def construir_texto_plano_formato_venta_mostrador(context: dict) -> str:
    """
    Arma el cuerpo text/plain del correo de Nota de Venta Directa.

    Objetivo de negocio:
        El cliente sabe que el PDF va adjunto aunque su bandeja bloquee HTML.

    Args:
        context: El mismo diccionario que
            `formato_venta_mostrador_cliente.html`.

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
        'Nota de venta directa',
        f'Orden: {orden_sicser}',
        '',
        f"Buen día estimado/a {nombre_saludo(context)}",
        '',
        (
            f"Me dirijo de {context.get('empresa_nombre') or ''} para enviarle la "
            'Nota de Venta Directa correspondiente a los servicios y/o piezas '
            'adquiridos. El documento se encuentra adjunto en este correo.'
        ),
        '',
        'Agradecemos su preferencia y nos ponemos a sus órdenes para esta y futuras ocasiones.',
        '',
        'INFORMACIÓN DE SU EQUIPO',
        f'Número de Orden: {orden_sicser}',
        f'Equipo: {equipo}',
        f'Service Tag: {numero_serie}',
        f'Fecha de Ingreso: {fecha_ingreso_texto}',
        '',
        'ARCHIVOS ADJUNTOS',
        '1 archivo adjunto a este correo',
        '1 PDF — Nota de Venta Directa',
        '',
        'INFORMACIÓN IMPORTANTE',
        'El documento PDF adjunto es la nota de venta de los servicios adquiridos.',
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
