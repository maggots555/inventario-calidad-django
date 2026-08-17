"""
Reglas de NPS para encuestas de satisfacción.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El cliente ya no ve la pregunta de pulgares («¿Recomendarías…?»).
Esa respuesta se calcula aquí a partir del NPS 0–10, que sí contesta
en el formulario. Así el dashboard, el perfil y el PDF siguen teniendo
un sí/no sin preguntar lo mismo dos veces.

Estándar NPS (Bain / Reichheld):
    0–6  detractores
    7–8  pasivos
    9–10 promotores
"""

from __future__ import annotations


# A partir de 7 el cliente no es detractor: cuenta como «sí recomienda».
# 7 y 8 son pasivos (dirían que sí, pero no son promotores).
UMBRAL_RECOMIENDA_NPS = 7


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
