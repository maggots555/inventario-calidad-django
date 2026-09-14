"""
Texto plano de los tres correos de diagnóstico al cliente.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Hay UNA tarea Celery (`enviar_diagnostico_cliente_task`) y TRES plantillas HTML:

- estandar: diagnóstico + cotización en camino (1 a 6 días)
- nivel_componente: reparación de tarjeta madre, FAQ y galería
- validacion: equipo funcional, recolección o espera Drop Off

Este módulo arma el text/plain con el MISMO mensaje que el HTML, para que
Gmail/Outlook muestren algo útil si bloquean el HTML. No toca BD ni envía.
"""

from __future__ import annotations

from django.template.defaultfilters import date as date_filter


def construir_texto_plano_diagnostico(tipo_plantilla: str, context: dict) -> str:
    """
    Elige el texto plano según el radio del modal de diagnóstico.

    Objetivo de negocio:
        El cliente lee el diagnóstico (folio, equipo, PDF, seguimiento)
        aunque su bandeja no pinte HTML.

    Args:
        tipo_plantilla: 'estandar', 'nivel_componente' o 'validacion'.
            Cualquier otro valor cae a estándar (mismo criterio que la tarea).
        context: El mismo diccionario que se pasa a render_to_string.

    Returns:
        str: Cuerpo en texto plano, con saltos de línea.

    Efectos secundarios:
        Ninguno.
    """
    # EXPLICACIÓN: la tarea ya validó el radio; aquí repetimos el fallback
    # por si alguien llama al helper con un valor raro.
    if tipo_plantilla == 'nivel_componente':
        return _texto_nivel_componente(context)
    if tipo_plantilla == 'validacion':
        return _texto_validacion(context)
    return _texto_estandar(context)


def _lineas_equipo(context: dict) -> list[str]:
    """
    Bloque de folio / orden / equipo / serie / fecha (igual que el HTML).

    Args:
        context: Claves `folio`, `detalle`, `orden`.

    Returns:
        list[str]: Líneas del bloque, con título.
    """
    detalle = context.get('detalle')
    orden = context.get('orden')

    # EXPLICACIÓN: si no hay orden de cliente (FL-…), usamos el interno.
    orden_cliente = getattr(detalle, 'orden_cliente', '') or ''
    numero_orden = orden_cliente or getattr(orden, 'numero_orden_interno', '')

    tipo = getattr(detalle, 'tipo_equipo', '') or ''
    marca = getattr(detalle, 'marca', '') or ''
    modelo = getattr(detalle, 'modelo', '') or ''
    equipo = ' '.join(parte for parte in (tipo, marca, modelo) if parte).strip()
    numero_serie = getattr(detalle, 'numero_serie', '') or ''

    fecha_ingreso = getattr(orden, 'fecha_ingreso', None)
    fecha_ingreso_texto = date_filter(fecha_ingreso, 'd/m/Y H:i') if fecha_ingreso else ''

    lineas = [
        'INFORMACIÓN DE SU EQUIPO',
        f"Folio diagnóstico: {context.get('folio') or ''}",
        f'Número de orden: {numero_orden}',
        f'Equipo: {equipo}',
        f'Número de serie: {numero_serie}',
        f'Fecha de ingreso: {fecha_ingreso_texto}',
        '',
    ]

    mensaje = (context.get('mensaje_personalizado') or '').strip()
    if mensaje:
        lineas.extend(['MENSAJE ADICIONAL', mensaje, ''])

    return lineas


def _lineas_adjuntos(context: dict) -> list[str]:
    """
    Conteo de adjuntos: 1 PDF + N fotos de diagnóstico.

    Args:
        context: Clave `cantidad_imagenes` (solo las fotos, no el PDF).

    Returns:
        list[str]: Líneas del bloque.
    """
    cantidad_fotos = int(context.get('cantidad_imagenes') or 0)
    # EXPLICACIÓN: el HTML usa {{ cantidad_imagenes|add:1 }} (PDF + fotos).
    total = cantidad_fotos + 1
    plural = 's' if total != 1 else ''

    lineas = [
        'ARCHIVOS ADJUNTOS',
        f'{total} archivo{plural} adjunto{plural} a este correo',
        '1 PDF — Diagnóstico completo con observaciones técnicas',
    ]
    if cantidad_fotos > 0:
        plural_img = 'es' if cantidad_fotos != 1 else ''
        lineas.append(
            f'{cantidad_fotos} imagen{plural_img} — Fotografías del diagnóstico'
        )
    lineas.append('')
    return lineas


def _lineas_seguimiento(context: dict) -> list[str]:
    """
    CTA de seguimiento público, solo si hay URL (órdenes OOW con enlace activo).

    Args:
        context: Clave `seguimiento_url`.

    Returns:
        list[str]: Vacío o el bloque con la misma URL que el botón HTML.
    """
    url = (context.get('seguimiento_url') or '').strip()
    if not url:
        return []
    return [
        'Consulte el estado de su equipo en cualquier momento:',
        url,
        '',
    ]


def _lineas_footer(context: dict, sitio_web: str) -> list[str]:
    """
    Pie: no responder, contacto del técnico, redes y fecha.

    Args:
        context: email_empleado, nombre_empleado, empresa, país, WhatsApp, fecha.
        sitio_web: URL del footer (sicfix.mx en estándar; sic.com.mx en las otras).

    Returns:
        list[str]: Líneas finales.
    """
    nombre = (context.get('nombre_empleado') or '').strip()
    email = (context.get('email_empleado') or '').strip()
    if nombre:
        contacto = nombre
        if email:
            contacto = f'{nombre} ({email})'
    else:
        contacto = 'su responsable de seguimiento'

    lineas = [
        'Sistema de Servicio Técnico',
        'IMPORTANTE: Este es un correo automático no supervisado.',
        'Por favor, NO RESPONDA a este correo.',
        f'Para seguimiento de su orden, contacte directamente a {contacto}.',
        '',
        str(context.get('empresa_nombre') or ''),
        str(context.get('pais_nombre') or ''),
        '',
        'Visítenos y síganos en nuestras redes sociales',
        f'Sitio web: {sitio_web}',
        'Instagram: https://www.instagram.com/sic_mexico/?hl=es',
        'Facebook: https://www.facebook.com/LatAmSic',
    ]

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
    return lineas


def _texto_estandar(context: dict) -> str:
    """
    Cuerpo plano de diagnostico_cliente.html.

    Args:
        context: Contexto de la plantilla estándar.

    Returns:
        str: Texto plano.
    """
    empresa = context.get('empresa_nombre') or ''
    lineas = [
        'Diagnóstico de equipo',
        f"Folio: {context.get('folio') or ''}",
        '',
        'Buen día estimado usuario',
        '',
        (
            f'Me dirijo de {empresa}, para hacer de su conocimiento el diagnóstico '
            'realizado por nuestro Ingeniero a su equipo de cómputo (documento adjunto); '
            'así mismo, notificando que su cotización está en proceso y se la haremos '
            'llegar a la brevedad.'
        ),
        '',
        (
            'Le recordamos que no contamos localmente con un stock de piezas, revisaremos '
            'existencia, tiempo de entrega y costo con nuestros proveedores logísticos; '
            'en cuanto tengamos esta información se la proporcionaremos a usted por este '
            'mismo medio (de 1 a 6 días hábiles después de la recepción de este correo).'
        ),
        '',
        'Agradecemos su preferencia y nos ponemos a sus órdenes para esta y futuras ocasiones.',
        '',
    ]
    # EXPLICACIÓN: mismo orden que el HTML: equipo → adjuntos → nota de cotización.
    lineas.extend(_lineas_equipo(context))
    lineas.extend(_lineas_adjuntos(context))
    lineas.extend(
        [
            'INFORMACIÓN IMPORTANTE',
            'El documento PDF adjunto contiene el diagnóstico detallado de su equipo.',
            'La cotización de las piezas necesarias será enviada a la brevedad por este mismo medio.',
            'El tiempo estimado de respuesta con cotización es de 1 a 6 días hábiles.',
            'Si tiene alguna pregunta, no dude en contactarnos.',
            '',
            'Gracias por confiar en nuestros servicios.',
            '',
        ]
    )
    lineas.extend(_lineas_seguimiento(context))
    lineas.extend(_lineas_footer(context, 'https://sicfix.mx/'))
    return '\n'.join(lineas)


def _texto_nivel_componente(context: dict) -> str:
    """
    Cuerpo plano de diagnostico_cliente_nivel_componente.html.

    Args:
        context: Contexto de la plantilla de nivel componente.

    Returns:
        str: Texto plano (incluye FAQ; las fotos de proceso solo existen en HTML).
    """
    empresa = context.get('empresa_nombre') or ''
    lineas = [
        'Diagnóstico — Reparación a nivel componente',
        f"Folio: {context.get('folio') or ''}",
        '',
        'Buen día estimado usuario',
        '',
        (
            f'Me dirijo de {empresa}, para hacer de su conocimiento el diagnóstico '
            'realizado por nuestro Ingeniero a su equipo de cómputo (documento adjunto).'
        ),
        '',
        (
            'Al identificar en el diagnóstico que el daño es en una de las partes '
            'principales del equipo, la Tarjeta Madre la cual es una de las partes más '
            'importantes y caras de un equipo (representa aprox el 55% del costo del equipo) '
            'y por ello es que queremos explicarle acerca del proceso de reparación a nivel '
            'componente con el cual contamos y que implicaría una inversión menor y un ahorro '
            'sustancial en costo y tiempo VS el reemplazo completo de esta parte.'
        ),
        '',
        (
            'En caso de aceptar este proceso, se deben ir reemplazando los componentes dañados '
            '(por ejemplo fuentes de alimentación) para dejarlo funcional y hay un alto porcentaje '
            'de éxito (90%); el costo como ya mencionamos es mucho menor VS el costo de la parte '
            'de Stock y el tiempo de entrega de igual forma es mucho más rápido '
            '((2 a 6 días hábiles después de su OK para este proceso aproximadamente), '
            'también contará con los 30 días naturales de garantía que ofrecemos, y recibirá '
            'además evidencia fotográfica del(os) microcomponente(s) dañado(s) y del funcionamiento '
            'de su equipo después del reemplazo de estos.'
        ),
        '',
    ]
    lineas.extend(_lineas_equipo(context))
    lineas.extend(
        [
            'PREGUNTAS FRECUENTES',
            '',
            '¿Todos los equipos bajo este escenario de daño en Tarjeta Madre pasan en automático '
            'a esta reparación por componente?',
            'NO, requerimos su aprobación escrita vía email en respuesta al diagnóstico enviado.',
            '',
            '¿Qué pasa si en este proceso se determina que la Tarjeta madre es IRREPARABLE?',
            'Como todo hay un rango de fallo por lo que si su Tarjeta madre tiene un daño muy profundo '
            'y no es candidata a reparación, esto no representará ningún costo adicional para usted '
            'y se lo informaremos a la brevedad.',
            '',
            '¿Si no es reparable entonces qué puedo esperar?',
            'Recibirá un email informando esto y en paralelo una cotización por la parte completa '
            'y tiempo de entrega, ya que estas partes vienen de diferentes Stocks que tenemos en '
            'USA o China (siempre seleccionamos el de mejor disponibilidad, tiempo de espera y costo '
            'de arancel) y en base a ello usted pueda tomar la decisión de reemplazar la parte y '
            'esperar o no.',
            '',
            '¿Cuanto cuesta la reparación a nivel componente?',
            'El costo de la reparación depende del nivel de daño que se encuentre; cuando le enviemos '
            'la propuesta económica se le detallará el mismo.',
            '',
            '¿En caso de que no se pueda reparar la Tarjeta Madre, es posible recuperar '
            'la información del equipo?',
            'Sí, dado que el almacenamiento es independiente en algunos modelos, es posible recuperar '
            'su información si es que así lo requiere (solo en caso de SSD formateados es imposible '
            'recuperar datos).',
            '',
            'Proceso de reparación a nivel componente',
            'Reballing, recuperación de pistas, baño en tina ultrasonica, revisión de cada '
            'componente, recuperación de información y verificación de integridad.',
            'Más información: https://sicfix.mx/reparacion-tarjeta-madre/',
            '',
            'Para contactarnos puede dar clic en el siguiente botón y con gusto le atenderemos',
        ]
    )
    whatsapp = (context.get('whatsapp_empleado') or '').strip()
    if whatsapp:
        lineas.append(f'WhatsApp: https://wa.me/{whatsapp}')
    lineas.append('')
    lineas.extend(_lineas_adjuntos(context))
    lineas.extend(
        [
            'INFORMACIÓN IMPORTANTE',
            'El documento PDF adjunto contiene el diagnóstico detallado de su equipo.',
            'La reparación a nivel componente requiere su aprobación escrita por email.',
            'El tiempo estimado tras su OK es de 2 a 6 días hábiles aproximadamente.',
            'Si tiene alguna pregunta, no dude en contactarnos.',
            '',
            'Gracias por confiar en nuestros servicios.',
            '',
        ]
    )
    lineas.extend(_lineas_seguimiento(context))
    # EXPLICACIÓN: esta plantilla (y validación) usan sic.com.mx en el pie, no sicfix.mx.
    lineas.extend(_lineas_footer(context, 'https://sic.com.mx/'))
    return '\n'.join(lineas)


def _texto_validacion(context: dict) -> str:
    """
    Cuerpo plano de diagnostico_cliente_validacion.html.

    Args:
        context: Incluye horario, sucursal, Drop Off y cláusula 6.

    Returns:
        str: Texto plano.
    """
    empresa = context.get('empresa_nombre') or ''
    nombre_cliente = (context.get('nombre_cliente') or '').strip()
    saludo = 'Buen día:'
    if nombre_cliente:
        saludo = f'Buen día estimado {nombre_cliente}:'

    lineas = [
        'Diagnóstico de validación',
        f"Folio: {context.get('folio') or ''}",
        '',
        saludo,
        '',
        (
            f'Me dirijo de {empresa}, para hacer de su conocimiento el diagnóstico '
            'realizado por nuestro Ingeniero a su equipo de cómputo (documento adjunto); '
            'así mismo, le informamos que no será necesario cotizar ningún componente ya que '
            'su equipo ha quedado funcional y operativo durante el proceso de revisión.'
        ),
        '',
        'Nota: la garantía de validación es de 1 semana.',
        '',
    ]

    # EXPLICACIÓN: Drop Off pide esperar aviso; sucursal normal invita a recolectar.
    if context.get('es_sucursal_drop_off'):
        lineas.extend(
            [
                'Por favor espere la notificación de equipo disponible que le '
                'enviaremos por este mismo medio cuando el equipo ya se encuentre '
                'físicamente en la sucursal y pueda pasar a recolectarlo.',
                '',
            ]
        )
    else:
        lineas.extend(
            [
                'Nos es grato informarle que su equipo de cómputo se encuentra listo para que pase a '
                'recolectar al centro de servicio donde fue ingresado. Es necesario presentar la hoja '
                '(formato de servicio) que le fue entregada al momento de ingresar el equipo así como '
                'una identificación oficial.',
                '',
                'En caso de que sea alguna otra persona quien vaya a recoger el equipo necesitamos de '
                'igual manera el Formato de Servicio, identificación oficial de la persona que recogerá '
                'y copia de la identificación oficial de la persona que lo ingresó o del titular del '
                'servicio. (COPIAS DE AMBAS CREDENCIALES POR LOS 2 LADOS).',
                '',
                'Le recuerdo los horarios de atención:',
                str(context.get('horario_atencion') or ''),
                '',
                'Sucursal de recolección',
                str(context.get('sucursal_nombre') or ''),
            ]
        )
        direccion = (context.get('sucursal_direccion') or '').strip()
        if direccion:
            lineas.append(direccion)
        ciudad = (context.get('sucursal_ciudad_estado') or '').strip()
        if ciudad:
            lineas.append(ciudad)
        telefono = (context.get('sucursal_telefono') or '').strip()
        if telefono:
            lineas.append(f'Tel: {telefono}')
        lineas.append('')

        # EXPLICACIÓN: cláusula 6 solo OOW y solo si NO es Drop Off (igual que el HTML).
        if context.get('es_fuera_garantia'):
            lineas.extend(
                [
                    'Nota importante',
                    'ES SUMAMENTE IMPORTANTE LO RETIREN A LA BREVEDAD YA QUE SE GENERA CARGO '
                    'DE ALMACENAJE O DESTRUCCIÓN DEL EQUIPO (CLÁUSULA 6 DEL FORMATO QUE FIRMA '
                    'AL INGRESO DEL EQUIPO).',
                    '',
                ]
            )

    lineas.extend(_lineas_equipo(context))
    lineas.extend(_lineas_adjuntos(context))
    lineas.extend(
        [
            'Agradecemos su preferencia y nos ponemos a sus órdenes para esta y futuras ocasiones.',
            '',
        ]
    )
    lineas.extend(_lineas_seguimiento(context))
    lineas.extend(_lineas_footer(context, 'https://sic.com.mx/'))
    return '\n'.join(lineas)
