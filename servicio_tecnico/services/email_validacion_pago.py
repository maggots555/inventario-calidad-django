"""
Texto plano del correo interno de validación de pago.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
El HTML tiene un botón. Si la bandeja bloquea el HTML, Facturación
o Recepción igual deben leer el aviso y abrir la misma URL.
No envía correo.
"""

from __future__ import annotations

from django.template.defaultfilters import date as date_filter


def construir_texto_plano_validacion_pago(context: dict) -> str:
    """
    Arma el cuerpo text/plain del aviso de validación de pago.

    Objetivo de negocio:
        Quien recibe puede abrir la bandeja o los cobros aunque no vea
        el HTML, y lee el mismo monto y la misma nota.

    Args:
        context: El mismo diccionario que `validacion_pago.html`.
            Claves: pago, tipo_evento, url_pagos, referencia_orden,
            folio_cliente, service_tag, folio_interno, ahora_local.

    Returns:
        str: Cuerpo en texto plano.

    Efectos secundarios:
        Ninguno.
    """
    tipo = context.get('tipo_evento') or ''
    pago = context.get('pago')
    titulo, cuerpo, boton = _textos_del_evento(tipo)
    referencia = context.get('referencia_orden') or ''
    url = (context.get('url_pagos') or '').strip()

    lineas = [
        titulo,
        f'Orden {referencia}',
        '',
        cuerpo,
        '',
        'DATOS DEL PAGO',
        f"Monto: ${_dinero(getattr(pago, 'monto', None))}",
        f"Método: {_display(pago, 'get_metodo_display')}",
        f"Tipo: {_display(pago, 'get_tipo_display')}",
    ]

    # EXPLICACIÓN: folio y Service Tag solo salen si el helper los trae.
    folio_cliente = (context.get('folio_cliente') or '').strip()
    if folio_cliente:
        lineas.append(f'Folio cliente: {folio_cliente}')
    service_tag = (context.get('service_tag') or '').strip()
    if service_tag:
        lineas.append(f'Service Tag: {service_tag}')

    lineas.append(f"Folio interno: {context.get('folio_interno') or ''}")
    registrado = getattr(getattr(pago, 'registrado_por', None), 'nombre_completo', '') or ''
    lineas.append(f'Registró: {registrado}')

    notas = (getattr(pago, 'notas', '') or '').strip()
    if notas:
        lineas.append(f'Notas del cobro: {notas}')
    nota_validacion = (getattr(pago, 'nota_validacion', '') or '').strip()
    if nota_validacion:
        lineas.append(f'Nota de Facturación: {nota_validacion}')

    lineas.extend(['', f'{boton}:', url, '', 'Aviso interno de SIGMA'])
    ahora = context.get('ahora_local')
    if ahora:
        lineas.append(date_filter(ahora, 'd/m/Y H:i'))
    return '\n'.join(lineas)


def _textos_del_evento(tipo: str) -> tuple[str, str, str]:
    """
    Devuelve título, párrafo y etiqueta del botón según el evento.

    Args:
        tipo: 'pendiente', 'validado' o 'no_aparece'.

    Returns:
        tuple: (título, cuerpo, texto del botón).

    Efectos secundarios:
        Ninguno.
    """
    if tipo == 'validado':
        return (
            'Pago validado en la cuenta',
            (
                'Facturación confirmó que este pago ya aparece en la cuenta '
                'de la empresa.'
            ),
            'Abrir cobros de la orden',
        )
    if tipo == 'no_aparece':
        return (
            'El pago aún no aparece en la cuenta',
            (
                'Facturación no encontró este pago en la cuenta. Revisa el '
                'comprobante, el monto o la referencia y corrígelo si hace falta.'
            ),
            'Abrir cobros de la orden',
        )
    return (
        'Pago pendiente de validar',
        (
            'Recepción registró un abono. Revisa si ya se refleja en la '
            'cuenta de la empresa y confírmalo en la bandeja de pagos.'
        ),
        'Abrir bandeja de pagos',
    )


def _display(pago, metodo: str) -> str:
    """
    Llama get_metodo_display / get_tipo_display si existen.

    Args:
        pago: PagoOrden o un objeto de mentira del test.
        metodo: Nombre del método de display.

    Returns:
        str: Texto visible, o vacío.

    Efectos secundarios:
        Ninguno.
    """
    fn = getattr(pago, metodo, None)
    if callable(fn):
        return str(fn() or '')
    return ''


def _dinero(valor) -> str:
    """
    Formatea el monto con dos decimales, como floatformat:2.

    Args:
        valor: Número, Decimal o None.

    Returns:
        str: Monto con dos decimales.

    Efectos secundarios:
        Ninguno.
    """
    if valor is None:
        return '0.00'
    try:
        return f'{float(valor):.2f}'
    except (TypeError, ValueError):
        return str(valor)
