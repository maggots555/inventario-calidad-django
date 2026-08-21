"""
Vistas de daños estéticos compartidas por los formatos OOW y Garantía Dell.

EXPLICACIÓN PARA PRINCIPIANTES:
------------------------------------------------
Cada tipo de equipo (laptop, escritorio, AIO) tiene una lista fija de
ángulos que hay que fotografiar/anotar. Este helper dice cuáles faltan
para no poder finalizar el PDF a medias, y cuáles deben ir al documento.
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


def vistas_dano_para_pdf(formato) -> list:
    """
    Vistas con imagen del tipo actual, en el orden del catálogo.

    Objetivo de negocio:
        Si el técnico guardó caras de laptop y luego cambió a escritorio
        o AIO, esas caras viejas NO deben salir en el PDF.

    Args:
        formato: FormatoServicioOOW o FormatoServicioGarantia.

    Returns:
        Lista de objetos vista (related ``vistas_dano``) ya filtrada y ordenada.
    """
    tipo = getattr(formato, 'tipo_diagrama', '') or 'laptop'
    catalogo = catalogo_vistas_dano_estetico(tipo)
    # clave → posición (0, 1, 2…) para ordenar Pantalla, Top Cover, etc.
    orden_claves = {clave: idx for idx, (clave, _etiqueta) in enumerate(catalogo)}
    claves_del_tipo = set(orden_claves)

    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Traemos todas las que tienen PNG y nos quedamos solo con las del
    # tipo elegido. Las demás (otro diagrama) se ignoran en el documento.
    vistas = [
        vista
        for vista in formato.vistas_dano.exclude(
            imagen_anotada='',
        ).exclude(imagen_anotada=None)
        if vista.clave_vista in claves_del_tipo
    ]
    vistas.sort(
        key=lambda vista: (
            orden_claves.get(vista.clave_vista, 999),
            vista.clave_vista or '',
        )
    )
    return vistas


def claves_vistas_del_tipo(tipo_diagrama: str) -> set[str]:
    """
    Conjunto de claves (pantalla, frente, aio_base…) del tipo de equipo.

    Args:
        tipo_diagrama: ``laptop``, ``escritorio`` o ``aio``.

    Returns:
        set de claves válidas para ese diagrama.
    """
    return {clave for clave, _etiqueta in catalogo_vistas_dano_estetico(tipo_diagrama)}


def eliminar_vistas_dano_fuera_de_tipo(formato) -> int:
    """
    Borra de BD las vistas que no pertenecen al tipo actual del formato.

    Objetivo de negocio:
        Al cambiar laptop → escritorio, las miniaturas viejas no deben
        reaparecer al recargar ni mezclarse con el PDF.

    Args:
        formato: FormatoServicioOOW o FormatoServicioGarantia (ya con
            ``tipo_diagrama`` actualizado).

    Returns:
        int: cuántas filas se eliminaron.

    Efectos secundarios:
        DELETE de vistas_dano ajenas al tipo; intenta borrar el PNG del disco.
    """
    tipo = getattr(formato, 'tipo_diagrama', '') or 'laptop'
    claves_ok = claves_vistas_del_tipo(tipo)
    ajenas = formato.vistas_dano.exclude(clave_vista__in=claves_ok)
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # .delete() en el QuerySet no siempre quita el archivo de media.
    # Recorremos cada fila para borrar PNG + registro.
    borradas = 0
    for vista in ajenas:
        if vista.imagen_anotada:
            vista.imagen_anotada.delete(save=False)
        vista.delete()
        borradas += 1
    return borradas

