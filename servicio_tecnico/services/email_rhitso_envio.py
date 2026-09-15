"""
Texto plano del correo de envío de equipo a RHITSO.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Los clientes de correo suelen pedir DOS versiones del mismo mensaje:

1. HTML (bonito, con tablas y colores)
2. text/plain (solo texto: se usa si el HTML está bloqueado o el lector
   es de accesibilidad)

Este módulo arma la versión de texto con el MISMO contenido que la
plantilla HTML `emails/rhitso_envio.html` (orden, serie, falla, contacto
SIC, lista de adjuntos). La tarea Celery solo llama a esta función y
la adjunta.

Este correo va al LABORATORIO, no al cliente: no incluye "NO RESPONDA".
"""

from __future__ import annotations


def _texto_o_vacio(valor) -> str:
    """
    Convierte un valor de plantilla a texto limpio.

    Args:
        valor: Atributo de orden/detalle (puede ser None).

    Returns:
        str: Texto sin espacios de más, o cadena vacía.
    """
    if valor is None:
        return ''
    return str(valor).strip()


def construir_texto_plano_rhitso_envio(context: dict) -> str:
    """
    Arma el cuerpo text/plain del correo de envío a RHITSO.

    Objetivo de negocio:
        El laboratorio debe poder leer orden, serie, falla y contacto
        aunque su bandeja bloquee HTML.

    Args:
        context: El mismo diccionario que se pasa a render_to_string
            de `rhitso_envio.html`. Claves esperadas: orden,
            empresa_nombre, pais_nombre, fecha_envio_texto,
            hora_envio_texto.

    Returns:
        str: Cuerpo en texto plano, con saltos de línea.

    Efectos secundarios:
        Ninguno. No toca BD ni envía correo.
    """
    orden = context.get('orden')
    # EXPLICACIÓN: en Django templates, orden.detalle_equipo vacío
    # no truena; aquí replicamos ese fallback a mano.
    detalle = getattr(orden, 'detalle_equipo', None) if orden else None

    orden_cliente = _texto_o_vacio(getattr(detalle, 'orden_cliente', ''))
    numero_interno = _texto_o_vacio(getattr(orden, 'numero_orden_interno', ''))
    numero_orden = orden_cliente or numero_interno

    numero_serie = _texto_o_vacio(getattr(detalle, 'numero_serie', '')) or 'N/A'

    # EXPLICACIÓN: si no hay detalle, el HTML pinta "N/A"; si hay, marca + modelo.
    if detalle:
        marca = _texto_o_vacio(getattr(detalle, 'marca', ''))
        modelo = _texto_o_vacio(getattr(detalle, 'modelo', ''))
        modelo_texto = ' '.join(parte for parte in (marca, modelo) if parte).strip() or 'N/A'
    else:
        modelo_texto = 'N/A'

    serie_cargador = _texto_o_vacio(getattr(detalle, 'numero_serie_cargador', ''))
    cargador = serie_cargador or 'SIN CARGADOR'

    descripcion = _texto_o_vacio(getattr(orden, 'descripcion_rhitso', ''))
    falla = descripcion or 'No especificado'

    lineas = [
        'Buen día Team RHITSO',
        '',
        (
            'Enviamos equipo para revisión especializada. '
            'A continuación encontrarán toda la información técnica del equipo, '
            'así como las imágenes correspondientes adjuntas a este correo.'
        ),
        '',
        'INFORMACIÓN DEL EQUIPO',
        f'Orden: {numero_orden}',
        f'Número de serie: {numero_serie}',
        f'Modelo: {modelo_texto}',
        f'Cargador: {cargador}',
        f'Descripción de la falla: {falla}',
        '',
        'INFORMACIÓN DE CONTACTO',
        'Agente: Alejandro García',
        'Celular: 55-35-45-81-92',
        'Correo: cis_mex@sic.com.mx',
        '',
        'ARCHIVOS ADJUNTOS',
        'Formato RHITSO (PDF)',
        'Imágenes de evidencia',
        'Imágenes de autorización/pass (incluidas en PDF)',
        '',
        'Saludos cordiales,',
        'Equipo de Soporte Técnico',
        '',
        str(context.get('empresa_nombre') or ''),
        str(context.get('pais_nombre') or ''),
        '',
        'Sitio web: https://sicfix.mx/',
        'Instagram: https://www.instagram.com/sic_mexico/?hl=es',
        'Facebook: https://www.facebook.com/LatAmSic',
        '',
        (
            f"Enviado el {context.get('fecha_envio_texto') or ''} "
            f"a las {context.get('hora_envio_texto') or ''}"
        ),
    ]

    return '\n'.join(lineas)
