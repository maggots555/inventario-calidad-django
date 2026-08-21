"""
Vistas de daños estéticos compartidas por los formatos OOW y Garantía Dell.

EXPLICACIÓN PARA PRINCIPIANTES:
------------------------------------------------
Cada tipo de equipo (laptop, escritorio, AIO) tiene una lista fija de
ángulos que hay que fotografiar/anotar. Este helper dice cuáles faltan
para no poder finalizar el PDF a medias.
"""

from __future__ import annotations

from config.constants import catalogo_vistas_dano_estetico


def etiquetas_vistas_dano_faltantes(formato) -> list[str]:
    """
    Etiquetas humanas de las vistas del tipo actual sin imagen guardada.

    Args:
        formato: FormatoServicioOOW o FormatoServicioGarantia (tiene
            ``tipo_diagrama`` y related ``vistas_dano``).

    Returns:
        Lista de etiquetas faltantes (ej. ``['Top Cover', 'Palm / Teclado']``).
        Vacía = el operador ya guardó todas las vistas requeridas.
    """
    tipo = getattr(formato, 'tipo_diagrama', '') or 'laptop'
    catalogo = catalogo_vistas_dano_estetico(tipo)
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Una vista “cuenta” solo si ya tiene PNG. El renglón vacío no sirve
    # para el PDF ni para demostrar que se revisó ese lado del equipo.
    qs = (
        formato.vistas_dano
        .exclude(imagen_anotada='')
        .exclude(imagen_anotada=None)
    )
    guardadas = set(qs.values_list('clave_vista', flat=True))
    return [
        etiqueta
        for clave, etiqueta in catalogo
        if clave not in guardadas
    ]
