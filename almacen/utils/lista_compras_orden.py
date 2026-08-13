"""
Orden por defecto de la lista de compras (Almacén).

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
La tabla de compras no ordena en SQL por “días que faltan”, porque ese
número no está guardado: se calcula en Python (property dias_para_llegada).

Este helper recibe las compras ya filtradas y las reordena en memoria:
1) Pendiente de llegada primero.
2) Entre esas, las más urgentes primero (retrasadas → llegan pronto).
3) El resto de estados, la más reciente primero.
"""


def _clave_orden_lista_compras(compra):
    """
    Arma la tupla que Python usa para comparar dos compras al ordenar.

    Objetivo de negocio: en la lista, lo urgente de llegar sale arriba.

    Args:
        compra: CompraProducto (o un objeto con los mismos atributos:
            estado, dias_para_llegada, fecha_registro).

    Returns:
        tuple: Valores de menor a mayor prioridad de sort.
            - Índice 0: 0 = pendiente_llegada, 1 = cualquier otro estado.
            - Índice 1: 0 = tiene ETA, 1 = no tiene ETA (van al final del bloque).
            - Índice 2: días relativos a la ETA (negativo = retrasada).
            - Índice 3: fecha_registro invertida (más reciente primero).

    Efectos secundarios:
        Ninguno. Solo lee atributos; no toca BD.
    """
    # Paso 1: las de "Pendiente de llegada" ganan (0 < 1).
    es_pendiente = 0 if compra.estado == 'pendiente_llegada' else 1

    # Paso 2: countdown. None = sin estimado → después de las que sí tienen fecha.
    dias = compra.dias_para_llegada
    if dias is None:
        grupo_eta = 1
        dias_val = 0
    else:
        # Negativo (retrasada) < 0 (hoy) < positivo (faltan días).
        grupo_eta = 0
        dias_val = dias

    # Paso 3: si empatan estado y días, la más reciente queda arriba.
    fecha = getattr(compra, 'fecha_registro', None)
    if fecha is not None and hasattr(fecha, 'timestamp'):
        ts_inverso = -fecha.timestamp()
    else:
        ts_inverso = 0

    return (es_pendiente, grupo_eta, dias_val, ts_inverso)


def ordenar_compras_para_lista(compras):
    """
    Ordena compras para pintar la lista (pestañas Cotizaciones y Directas).

    Objetivo de negocio: el personal de almacén ve primero lo que aún no
    llega y está más cerca (o ya retrasado) de la fecha estimada.

    Args:
        compras (iterable): QuerySet o lista de CompraProducto.

    Returns:
        list: Misma compras, en el orden de la lista.

    Efectos secundarios:
        Evalúa el iterable (si es QuerySet, ejecuta la consulta). No escribe BD.
    """
    # sorted no altera el original; el key reutiliza la property del modelo.
    return sorted(compras, key=_clave_orden_lista_compras)
