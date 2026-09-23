"""
Texto plano del correo interno de Diagnóstico SIC listo.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Hay dos audiencias. Si la bandeja bloquea el HTML, el responsable y
Compras igual deben leer su aviso y abrir la misma orden. No envía.
"""

from __future__ import annotations

from django.template.defaultfilters import date as date_filter


def construir_texto_plano_diagnostico_sic_listo(context: dict) -> str:
    """
    Arma el cuerpo text/plain del aviso de Diagnóstico SIC listo.

    Objetivo de negocio:
        Responsable y Compras pueden abrir la orden aunque no vean el HTML.

    Args:
        context: El mismo diccionario que
            `diagnostico_sic_listo_staff.html`, incluida audiencia.

    Returns:
        str: Cuerpo en texto plano.

    Efectos secundarios:
        Ninguno.
    """
    audiencia = context.get('audiencia') or ''
    titulo, cuerpo, boton = _textos_de_audiencia(audiencia)
    referencia = context.get('referencia_orden') or ''
    url = (context.get('url_detalle') or '').strip()

    lineas = [
        titulo,
        f'Orden {referencia}',
        '',
        cuerpo,
        '',
        'DATOS DE LA ORDEN',
    ]

    # EXPLICACIÓN: folio, Service Tag y cliente solo salen si vienen.
    folio_cliente = (context.get('folio_cliente') or '').strip()
    if folio_cliente:
        lineas.append(f'Folio cliente: {folio_cliente}')
    service_tag = (context.get('service_tag') or '').strip()
    if service_tag:
        lineas.append(f'Service Tag: {service_tag}')
    lineas.append(f"Folio interno: {context.get('folio_interno') or ''}")
    nombre = (context.get('nombre_cliente') or '').strip()
    if nombre:
        lineas.append(f'Cliente: {nombre}')

    extracto = (context.get('extracto_sic') or '').strip()
    if extracto:
        lineas.extend(['', 'Extracto del Diagnóstico SIC:', extracto])

    lineas.extend(['', f'{boton}:', url, '', 'Aviso interno de SIGMA — Servicio Técnico'])
    ahora = context.get('ahora_local')
    if ahora:
        lineas.append(date_filter(ahora, 'd/m/Y H:i'))
    return '\n'.join(lineas)


def _textos_de_audiencia(audiencia: str) -> tuple[str, str, str]:
    """
    Devuelve título, párrafo y botón según quién recibe el correo.

    Args:
        audiencia: 'compras' o 'responsable'.

    Returns:
        tuple: (título, cuerpo, texto del botón).

    Efectos secundarios:
        Ninguno.
    """
    if audiencia == 'compras':
        return (
            'Diagnóstico SIC disponible — cotizar piezas',
            (
                'El técnico guardó el Diagnóstico SIC. Revisa los componentes '
                'identificados y comienza la búsqueda o cotización de piezas.'
            ),
            'Revisar piezas a cotizar',
        )
    return (
        'Diagnóstico listo para compartir',
        (
            'La orden ya tiene Diagnóstico SIC. Entra al detalle y usa '
            '«Enviar diagnóstico» para compartirlo con el cliente.'
        ),
        'Abrir orden y enviar al cliente',
    )
