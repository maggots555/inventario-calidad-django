"""
Reglas de la encuesta de satisfacción (NPS y detalle por estrellas).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El cliente ya no ve la pregunta de pulgares («¿Recomendarías…?»).
Esa respuesta se calcula aquí a partir del NPS 0–10, que sí contesta
en el formulario. Así el dashboard, el perfil y el PDF siguen teniendo
un sí/no sin preguntar lo mismo dos veces.

También decide si pedir Atención y Tiempo: solo cuando la nota general
es 1–3 (la visita no fue buena). Con 4 o 5 el formulario se queda corto.

Estándar NPS (Bain / Reichheld):
    0–6  detractores
    7–8  pasivos
    9–10 promotores
"""

from __future__ import annotations


# A partir de 7 el cliente no es detractor: cuenta como «sí recomienda».
# 7 y 8 son pasivos (dirían que sí, pero no son promotores).
UMBRAL_RECOMIENDA_NPS = 7

# Atención y Tiempo solo se piden si la experiencia general fue 1, 2 o 3.
MAX_ESTRELLAS_DETALLE = 3


def derivar_recomienda_desde_nps(nps: int | None) -> bool | None:
    """
    Convierte el NPS (0–10) en el booleano `recomienda` de FeedbackCliente.

    Objetivo de negocio:
        Guardar sí/no para perfil, directorio y tasa de recomendación
        sin pedir otra pregunta al cliente.

    Args:
        nps: Entero 0–10, o None si aún no hay respuesta.

    Returns:
        True si nps >= 7, False si nps está entre 0 y 6, None si falta
        o el valor está fuera de rango (no inventamos un sí/no).

    Efectos secundarios:
        Ninguno. No toca base de datos ni archivos.
    """
    # Sin NPS no hay forma honesta de decidir el pulgar.
    if nps is None:
        return None
    # El formulario ya valida 0–10; esto cubre llamadas sueltas al helper.
    if not 0 <= nps <= 10:
        return None
    return nps >= UMBRAL_RECOMIENDA_NPS


def debe_pedir_detalle_calificacion(estrellas: int | None) -> bool:
    """
    ¿Hay que mostrar Atención y Tiempo de reparación?

    Objetivo de negocio:
        Si la visita fue buena (4 o 5 estrellas), no alargar la encuesta.
        Si fue regular o mala (1–3), sí preguntar en qué falló.

    Args:
        estrellas: Calificación general 1–5, o None si aún no eligió.

    Returns:
        True solo para 1, 2 o 3. False si falta, está fuera de rango,
        o es 4 / 5.

    Efectos secundarios:
        Ninguno. El formulario y el JS usan esta misma regla.
    """
    if estrellas is None:
        return False
    return 1 <= estrellas <= MAX_ESTRELLAS_DETALLE
