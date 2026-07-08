"""
chat_seguimiento_helpers.py — Utilidades del chat IA en seguimiento del cliente.

EXPLICACIÓN PARA PRINCIPIANTES:
Funciones auxiliares del chatbot público y del timeline de la página de
seguimiento, separadas de views.py para que ambas vistas usen la misma lógica.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from django.utils import timezone

from config.constants import ESTADO_ORDEN_CHOICES


# Nombres amigables para el cliente (vista pública y chat IA)
NOMBRES_PUBLICOS_ESTADO: dict[str, str] = {
  # Fase cotización — nombres que evitan confundir proveedor vs. cliente
    'cotizacion_enviada_proveedor': (
        'Consultando costos de piezas con proveedores'
    ),
    'cotizacion_recibida_proveedor': (
        'Preparando tu cotización (precios recibidos de proveedores)'
    ),
    'cotizacion': 'Esperando aprobación del cliente',
    'control_calidad': 'Equipo reparado, en control de calidad',
    'finalizado': (
        'Finalizado — pendiente de confirmación de entrega por el responsable de seguimiento'
    ),
}

# Estados de la fase de cotización (para inyectar guía contextual al chat IA)
ESTADOS_FASE_COTIZACION: frozenset[str] = frozenset({
    'diagnostico_enviado_cliente',
    'cotizacion_enviada_proveedor',
    'cotizacion_recibida_proveedor',
    'cotizacion',
    'cliente_acepta_cotizacion',
    'rechazada',
})

# Aclaraciones de negocio — evitan que la IA confunda cotización a proveedor vs. al cliente
ACLARACIONES_ESTADO_CHAT: dict[str, str] = {
    'diagnostico_enviado_cliente': (
        'El diagnóstico técnico ya fue enviado al cliente. '
        'El taller aún NO ha enviado la cotización formal de reparación.'
    ),
    'cotizacion_enviada_proveedor': (
        'El taller está consultando con proveedores los costos de las piezas necesarias '
        'para la reparación. Esto NO significa que la cotización ya se haya enviado al cliente.'
    ),
    'cotizacion_recibida_proveedor': (
        'Ya se recibieron precios de proveedores; el equipo está armando la cotización '
        'formal para el cliente. Aún NO está lista para tu aprobación.'
    ),
    'cotizacion': (
        'La cotización formal de reparación YA fue enviada al cliente. '
        'Se espera tu aprobación o respuesta sobre las piezas ofrecidas.'
    ),
    'cliente_acepta_cotizacion': (
        'El cliente ya aprobó la cotización; el taller gestiona el pedido de piezas.'
    ),
    'rechazada': (
        'El cliente rechazó la cotización; el equipo espera indicaciones sobre cómo proceder.'
    ),
}

# Estados que ya ocurrieron como hito (no son procesos “en curso” en el timeline visual)
ESTADOS_HITO_SEGUIMIENTO: frozenset[str] = frozenset({
    'equipo_diagnosticado',
    'diagnostico_enviado_cliente',
    'cotizacion_enviada_proveedor',
    'cotizacion_recibida_proveedor',
    'cliente_acepta_cotizacion',
    'rechazada',
    'partes_solicitadas_proveedor',
    'piezas_recibidas',
    'wpb_pieza_incorrecta',
    'doa_pieza_danada',
    'pnc_parte_no_disponible',
    'finalizado',
    'entregado',
})

# Texto «próximo paso» visible en el timeline público (copy breve para el cliente)
SIGUIENTE_PASO_SEGUIMIENTO: dict[str, str] = {
    'equipo_diagnosticado': 'El diagnóstico será enviado para tu revisión',
    'diagnostico_enviado_cliente': 'Consulta de costos de piezas con proveedores',
    'cotizacion_enviada_proveedor': (
        'En espera de respuesta de proveedores sobre costos de piezas'
    ),
    'cotizacion_recibida_proveedor': (
        'Preparación de la cotización formal para enviártela'
    ),
    'cliente_acepta_cotizacion': 'Gestionando las piezas necesarias para tu equipo',
    'rechazada': 'En espera de indicaciones',
    'partes_solicitadas_proveedor': 'En espera de llegada de piezas',
    'piezas_recibidas': 'Tu equipo entrará a reparación próximamente',
    'wpb_pieza_incorrecta': 'Gestionando reemplazo de pieza',
    'doa_pieza_danada': 'Gestionando reemplazo de pieza dañada',
    'pnc_parte_no_disponible': 'Buscando alternativas de disponibilidad',
}


def resolver_nombre_estado_publico(
    codigo: str,
    estado_dict: dict[str, str] | None = None,
) -> str:
    """
    Traduce un código interno de estado a texto legible para el cliente.

    Args:
        codigo: Código del estado (ej. 'reparacion')
        estado_dict: Mapa opcional de ESTADO_ORDEN_CHOICES

    Returns:
        str: Nombre público del estado
    """
    if not codigo:
        return ''
    if estado_dict is None:
        estado_dict = dict(ESTADO_ORDEN_CHOICES)
    return NOMBRES_PUBLICOS_ESTADO.get(
        codigo,
        estado_dict.get(codigo, codigo.replace('_', ' ').title()),
    )


def calcular_hace_relativo(fecha: datetime, ahora: datetime | None = None) -> str:
    """
    Calcula el texto relativo «Hace X días/horas» igual que en la página pública.

    Args:
        fecha: Momento del evento en la línea de tiempo
        ahora: Referencia temporal (por defecto timezone.now())

    Returns:
        str: Texto relativo en español
    """
    if ahora is None:
        ahora = timezone.now()
    delta = ahora - fecha
    if delta.days > 0:
        return f"Hace {delta.days} día{'s' if delta.days != 1 else ''}"
    if delta.seconds >= 3600:
        horas = delta.seconds // 3600
        return f"Hace {horas} hora{'s' if horas != 1 else ''}"
    return 'Hace unos minutos'


def formatear_aclaraciones_cotizacion_para_chat(estado_orden: str) -> str:
    """
    Genera el bloque de aclaraciones sobre la fase de cotización para el prompt del chat.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Los nombres internos de algunos estados pueden confundir al cliente (y a la IA):
    «Envío de Cotización al Proveedor» NO es lo mismo que «Esperando aprobación del cliente».
    Este bloque deja esa distinción explícita en el contexto del modelo.

    Args:
        estado_orden: Código del estado actual de la orden

    Returns:
        str: Texto para inyectar en el system prompt, o cadena vacía si no aplica
    """
    if estado_orden not in ESTADOS_FASE_COTIZACION:
        return ''

    lineas: list[str] = [
        'GUÍA DE ESTADOS DE COTIZACIÓN (distinción obligatoria para el cliente):',
        (
            '  • «Consultando costos con proveedores» / Envío de Cotización al Proveedor: '
            'el taller pide precios de piezas a proveedores. '
            'La cotización formal AÚN NO se ha enviado al cliente.'
        ),
        (
            '  • «Esperando aprobación del cliente»: la cotización formal SÍ fue enviada '
            'al cliente y se espera su respuesta o aprobación.'
        ),
    ]

    aclaracion_actual = ACLARACIONES_ESTADO_CHAT.get(estado_orden)
    if aclaracion_actual:
        nombre_publico = resolver_nombre_estado_publico(estado_orden)
        lineas.append(f'  • Estado actual («{nombre_publico}»): {aclaracion_actual}')

    return '\n'.join(lineas)


def construir_timeline_seguimiento_cliente(
    historial_estados: Iterable[dict[str, Any]],
    estado_orden: str,
    *,
    ahora: datetime | None = None,
) -> dict[str, Any]:
    """
    Construye el timeline de estados compartido entre la página pública y el chat IA.

    Aplica las mismas reglas que la vista de seguimiento:
    - Elimina estados duplicados consecutivos
    - Marca nodos completados vs. estado actual en progreso
    - Calcula «Hace X tiempo» por cada paso
    - Determina el texto de «próximo paso» cuando el estado es un hito

    Args:
        historial_estados: Iterable de dicts con estado_nuevo y fecha_evento
        estado_orden: Código del estado actual de la orden
        ahora: Referencia temporal para «hace» relativo

    Returns:
        dict con timeline, siguiente_paso_texto, estado_es_hito,
        estado_actual_texto, timeline_texto y aclaraciones_cotizacion_texto
    """
    if ahora is None:
        ahora = timezone.now()

    estado_dict = dict(ESTADO_ORDEN_CHOICES)

    # ── Paso 1: armar lista cruda con nombre público y tiempo relativo ──
    timeline_raw: list[dict[str, Any]] = []
    for evento in historial_estados:
        codigo = evento.get('estado_nuevo') or ''
        fecha = evento.get('fecha_evento')
        if not codigo or not fecha:
            continue
        timeline_raw.append({
            'codigo': codigo,
            'nombre': resolver_nombre_estado_publico(codigo, estado_dict),
            'fecha': fecha,
            'hace': calcular_hace_relativo(fecha, ahora),
        })

    # ── Paso 2: quitar duplicados consecutivos (misma lógica que la página) ──
    timeline: list[dict[str, Any]] = []
    for paso in timeline_raw:
        if timeline and timeline[-1]['codigo'] == paso['codigo']:
            continue
        timeline.append(paso)

    # ── Paso 3: hito vs. proceso activo y texto de siguiente paso ──
    estado_es_hito = estado_orden in ESTADOS_HITO_SEGUIMIENTO
    siguiente_paso_texto = (
        SIGUIENTE_PASO_SEGUIMIENTO.get(estado_orden) if estado_es_hito else None
    )

    # ── Paso 4: marcar completado / actual en cada nodo del timeline ──
    for indice, paso in enumerate(timeline):
        es_ultimo = indice == len(timeline) - 1
        if estado_es_hito:
            paso['completado'] = True
            paso['es_actual'] = False
        else:
            paso['completado'] = not es_ultimo
            paso['es_actual'] = es_ultimo

    estado_actual_texto = resolver_nombre_estado_publico(estado_orden, estado_dict)
    timeline_texto = formatear_timeline_texto_para_chat(
        timeline,
        siguiente_paso_texto=siguiente_paso_texto,
        estado_es_hito=estado_es_hito,
    )
    aclaraciones_cotizacion_texto = formatear_aclaraciones_cotizacion_para_chat(estado_orden)

    return {
        'timeline': timeline,
        'siguiente_paso_texto': siguiente_paso_texto,
        'estado_es_hito': estado_es_hito,
        'estado_actual_texto': estado_actual_texto,
        'timeline_texto': timeline_texto,
        'aclaraciones_cotizacion_texto': aclaraciones_cotizacion_texto,
    }


def formatear_timeline_texto_para_chat(
    timeline: list[dict[str, Any]],
    *,
    siguiente_paso_texto: str | None = None,
    estado_es_hito: bool = False,
) -> str:
    """
    Formatea el timeline deduplicado como texto para el system prompt del chat.

    Incluye fecha absoluta, tiempo relativo («Hace X días») y, si aplica,
    la indicación de próximo paso que ve el cliente en la página pública.

    Args:
        timeline: Lista procesada por construir_timeline_seguimiento_cliente
        siguiente_paso_texto: Texto de qué sigue cuando el estado es un hito
        estado_es_hito: Si el estado actual ya se completó como hito

    Returns:
        str: Bloque de texto con viñetas para el prompt
    """
    if not timeline:
        return '  Sin registros aún'

    lineas: list[str] = []
    for paso in timeline:
        fecha = paso.get('fecha')
        fecha_str = fecha.strftime('%d/%m/%Y %H:%M') if fecha else '?'
        hace = paso.get('hace', '')
        nombre = paso.get('nombre', '')
        # Indicar si el paso es el estado en curso o ya completado
        if paso.get('es_actual'):
            etiqueta_progreso = ' — estado en curso'
        elif paso.get('completado'):
            etiqueta_progreso = ' — completado'
        else:
            etiqueta_progreso = ''
        lineas.append(f"  • {nombre} ({fecha_str}, {hace}){etiqueta_progreso}")

    if siguiente_paso_texto:
        lineas.append(
            f"  → Próximo paso esperado en el proceso: {siguiente_paso_texto}"
        )
    elif not estado_es_hito and timeline:
        ultimo = timeline[-1]
        if ultimo.get('es_actual'):
            lineas.append(
                f"  → El equipo está actualmente en: {ultimo.get('nombre', 'proceso activo')}"
            )

    return '\n'.join(lineas)


def obtener_chips_chat_seguimiento(
    estado_orden: str,
    *,
    tiene_pdf_diagnostico: bool = False,
    tiene_seguimientos_piezas: bool = False,
) -> list[str]:
    """
    Devuelve chips de sugerencias rápidas según el estado real de la orden.

    Args:
        estado_orden: Código del estado (ej. 'reparacion', 'cotizacion')
        tiene_pdf_diagnostico: Si el cliente puede ver el PDF en la página
        tiene_seguimientos_piezas: Si hay piezas en tránsito visibles

    Returns:
        list[str]: Hasta 5 preguntas sugeridas para el panel del chat
    """
    # Preguntas por fase del workflow — máximo 5 por estado
    chips_por_estado: dict[str, list[str]] = {
        'espera': [
            '¿Cuándo empezarán a revisar mi equipo?',
            '¿En qué sucursal está mi equipo?',
            '¿Cuáles son sus sucursales?',
        ],
        'recepcion': [
            '¿Ya recibieron mi equipo?',
            '¿En qué sucursal está?',
            '¿Cuáles son sus sucursales?',
        ],
        'diagnostico': [
            '¿Qué le están revisando?',
            '¿Cuándo tendré el diagnóstico?',
            '¿En qué sucursal está mi equipo?',
        ],
        'equipo_diagnosticado': [
            '¿Qué le encontraron a mi equipo?',
            '¿Cuándo recibiré la cotización?',
            '¿Dónde está mi equipo?',
        ],
        'diagnostico_enviado_cliente': [
            '¿Qué le encontraron a mi equipo?',
            '¿Cuándo recibiré la cotización?',
            '¿En qué sucursal está mi equipo?',
        ],
        'cotizacion_enviada_proveedor': [
            '¿Ya tienen los precios de las piezas?',
            '¿Cuándo me enviarán la cotización?',
            '¿Dónde está mi equipo?',
        ],
        'cotizacion_recibida_proveedor': [
            '¿Cuándo me enviarán la cotización?',
            '¿En qué va el proceso?',
            '¿En qué sucursal está mi equipo?',
        ],
        'cotizacion': [
            '¿Qué incluye la cotización?',
            '¿Qué piezas debo aprobar?',
            '¿En qué sucursal está mi equipo?',
        ],
        'cliente_acepta_cotizacion': [
            '¿Cuándo llegan las piezas?',
            '¿En qué va mi reparación?',
            '¿Dónde está mi equipo?',
        ],
        'rechazada': [
            '¿Qué opciones tengo ahora?',
            '¿Puedo hablar con mi responsable?',
            '¿En qué sucursal está mi equipo?',
        ],
        'partes_solicitadas_proveedor': [
            '¿Ya pidieron las piezas?',
            '¿Cuándo llegan?',
            '¿Dónde está mi equipo?',
        ],
        'esperando_piezas': [
            '¿Hay piezas pendientes?',
            '¿Cuándo llegan las piezas?',
            '¿En qué va mi reparación?',
        ],
        'piezas_recibidas': [
            '¿Ya comenzaron la reparación?',
            '¿Cuándo estará listo?',
            '¿Dónde está mi equipo?',
        ],
        'reparacion': [
            '¿Cuándo estará listo?',
            '¿Qué le encontraron?',
            '¿Hay piezas pendientes?',
        ],
        'control_calidad': [
            '¿Cuándo estará listo?',
            '¿En qué sucursal está mi equipo?',
            '¿Cuáles son sus sucursales?',
        ],
        'finalizado': [
            '¿Dónde recojo mi equipo?',
            '¿Cuáles son los horarios de la sucursal?',
            '¿Cuáles son sus sucursales?',
        ],
        'entregado': [
            '¿Cuándo fue entregado mi equipo?',
            '¿Cuáles son sus sucursales?',
            '¿Tienen otras ubicaciones?',
        ],
        'almacen': [
            '¿Cuál es el estado de mi orden?',
            '¿En qué sucursal está mi equipo?',
            '¿Cuáles son sus sucursales?',
        ],
    }

    fallback = [
        '¿Cuál es el estado de mi orden?',
        '¿Dónde está mi equipo?',
        '¿Cuáles son sus sucursales?',
    ]

    chips = list(chips_por_estado.get(estado_orden, fallback))

    # Ajustes según datos disponibles en la página del cliente
    if tiene_pdf_diagnostico and '¿Puedo ver mi diagnóstico?' not in chips:
        chips.insert(1, '¿Puedo ver mi diagnóstico?')

    if tiene_seguimientos_piezas and '¿Hay piezas pendientes?' not in chips:
        chips.insert(0, '¿Hay piezas pendientes?')

    # Máximo 5 chips para no saturar móvil
    return chips[:5]
