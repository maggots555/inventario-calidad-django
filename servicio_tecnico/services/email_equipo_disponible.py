"""
Texto plano del correo de equipo disponible para recolección.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Este es el aviso de “ya puede pasar a recoger”. El text/plain debe decir
lo mismo que el HTML: sucursal, horarios y, si es OOW, la cláusula 6.
"""

from __future__ import annotations


def construir_texto_plano_equipo_disponible(context: dict) -> str:
    """
    Arma el cuerpo text/plain del correo de equipo disponible.

    Objetivo de negocio:
        El cliente puede recoger aunque su bandeja bloquee HTML.

    Args:
        context: El mismo diccionario que `equipo_disponible_cliente.html`.

    Returns:
        str: Cuerpo en texto plano.

    Efectos secundarios:
        Ninguno.
    """
    tipo = (context.get('tipo_equipo') or '').strip()
    marca = (context.get('marca_equipo') or '').strip()
    modelo = (context.get('modelo_equipo') or '').strip()
    equipo = ' '.join(parte for parte in (marca, modelo) if parte).strip()
    if tipo:
        equipo = f'{tipo} — {equipo}' if equipo else tipo

    folio = context.get('folio') or ''
    nombre = (context.get('nombre_cliente') or '').strip() or 'cliente'

    lineas = [
        'Equipo listo para recolección',
        'SIC México — Centro de servicio',
        '',
        f'Buen día estimado {nombre}:',
        '',
        (
            'Me dirijo de SIC MÉXICO; nos es grato informarle que su equipo de cómputo '
            'se encuentra listo para que pase a recolectar al centro de servicio donde '
            'fue ingresado. Es necesario presentar la hoja (formato de servicio) que le '
            'fue entregada al momento de ingresar el equipo así como una identificación oficial. '
            'En caso de no contar con el formato físico, puede presentar el formato digital.'
        ),
        '',
        'EQUIPO / FOLIO',
        equipo,
        f'Folio: {folio}',
    ]

    service_tag = (context.get('service_tag') or '').strip()
    if service_tag:
        lineas.append(f'Service Tag: {service_tag}')

    lineas.extend(
        [
            '',
            (
                'En caso de que sea alguna otra persona quien vaya a recoger el equipo '
                'necesitamos de igual manera el Formato de Servicio, identificación oficial '
                'de la persona que recogerá y copia de la identificación oficial de la '
                'persona que lo ingresó o del titular del servicio. '
                '(COPIAS DE AMBAS CREDENCIALES POR LOS 2 LADOS).'
            ),
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
    horario_extra = (context.get('sucursal_horario_extra') or '').strip()
    if horario_extra:
        lineas.append(f'Horario de la sucursal: {horario_extra}')

    # EXPLICACIÓN: misma condición que el HTML: solo OOW/FL ve la cláusula 6.
    if context.get('es_fuera_garantia'):
        lineas.extend(
            [
                '',
                'Nota importante',
                (
                    'ES SUMAMENTE IMPORTANTE LO RETIREN A LA BREVEDAD YA QUE SE GENERA CARGO '
                    'DE ALMACENAJE O DESTRUCCIÓN DEL EQUIPO (CLÁUSULA 6 DEL FORMATO QUE FIRMA '
                    'AL INGRESO DEL EQUIPO).'
                ),
            ]
        )

    lineas.extend(
        [
            '',
            (
                'Agradecemos su preferencia y nos ponemos a sus órdenes para esta y futuras '
                'ocasiones, saludos cordiales.'
            ),
            '',
            'SIC México — Servicio Técnico',
            'Sitio web: https://sicfix.mx',
            'Instagram: https://instagram.com/sic.com.mx',
            'Facebook: https://facebook.com/sic.com.mx',
            'WhatsApp: https://wa.me/523318189988',
            '',
            'Este correo se generó automáticamente desde SIGMA.',
        ]
    )

    return '\n'.join(lineas)
