"""
Profit mínimo y efectivo por pieza (cotización de reparación).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Antes el margen era un solo % del perfil (Mostrador, Estándar, etc.) para
todas las piezas. Ahora cada pieza puede tener su propio %, pero nunca
debajo del mínimo según su costo unitario Y el tipo de cotización.

Los tramos de costo son fijos ($0–499, $500–999, $1000–1499, $1500+).
Los % mínimos por tramo viven en BD (ConfiguracionRangoProfitMinimo) y
se editan en el panel de parámetros; estas constantes son la SEMILLA /
fallback si aún no hay filas.

Semilla (todos los perfiles al sembrar):
  $0 – $499.99     → mínimo 45%
  $500 – $999.99   → mínimo 36%
  $1000 – $1499.99 → mínimo 30%
  $1500 en adelante → mínimo 28%

El perfil sigue siendo el punto de partida; el override del modal (si hay)
se compara contra ese mínimo y se toma el mayor.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Union, Tuple

NumberLike = Union[int, float, Decimal, str, None]

# ---------------------------------------------------------------------------
# Constantes semilla (tramos de costo fijos + % por defecto)
# El panel / BD pueden sobrescribir los % por perfil.
# ---------------------------------------------------------------------------
RANGOS_PROFIT_MINIMO: List[Dict[str, Any]] = [
    {'costo_min': 0, 'costo_max': 500, 'profit_minimo': 0.45},
    {'costo_min': 500, 'costo_max': 1000, 'profit_minimo': 0.36},
    {'costo_min': 1000, 'costo_max': 1500, 'profit_minimo': 0.30},
    {'costo_min': 1500, 'costo_max': None, 'profit_minimo': 0.28},
]


def _a_decimal(valor: NumberLike, default: str = '0') -> Decimal:
    """
    Convierte un número suelto a Decimal de forma segura.

    Args:
        valor   : Int, float, str, Decimal o None.
        default : Valor si valor es None o vacío.

    Returns:
        Decimal normalizado.
    """
    if valor is None or valor == '':
        return Decimal(default)
    return Decimal(str(valor))


def _resolver_lista_rangos(
    perfil: Optional[str] = None,
    rangos: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Elige la lista de tramos: argumento explícito → BD por perfil → semilla.

    Args:
        perfil : Clave del tipo de servicio (opcional).
        rangos : Lista ya resuelta (evita reconsultar BD en bucles).

    Returns:
        Lista de tramos {costo_min, costo_max, profit_minimo}.
    """
    if rangos is not None:
        return rangos
    if perfil:
        # Import diferido: evita ciclo parametros_cotizador ↔ profit_por_pieza
        from almacen.utils.parametros_cotizador import obtener_rangos_profit_minimo
        return obtener_rangos_profit_minimo(perfil)
    return [
        {
            'costo_min': r['costo_min'],
            'costo_max': r['costo_max'],
            'profit_minimo': r['profit_minimo'],
        }
        for r in RANGOS_PROFIT_MINIMO
    ]


def rangos_profit_minimo_para_frontend(
    perfil: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Serializa los rangos de UN perfil para COTIZACION_CLIENTE_CONFIG.

    Preferir ``rangos_profit_minimo_por_perfil_para_frontend`` en el modal
    para no recargar al cambiar de tipo de servicio.

    Args:
        perfil: Clave del perfil; None → semilla global.

    Returns:
        Lista de dicts con costo_min, costo_max y profit_minimo.
    """
    return _resolver_lista_rangos(perfil=perfil)


def rangos_profit_minimo_por_perfil_para_frontend() -> Dict[str, List[Dict[str, Any]]]:
    """
    Mapa completo perfil → rangos para inyectar al modal de una sola vez.

    Returns:
        dict: {'mostrador': [...], 'estandar': [...], ...}
    """
    from almacen.utils.parametros_cotizador import obtener_todos_rangos_profit_minimo

    return obtener_todos_rangos_profit_minimo()


def obtener_profit_minimo(
    costo_unitario: NumberLike,
    perfil: Optional[str] = None,
    rangos: Optional[List[Dict[str, Any]]] = None,
) -> Decimal:
    """
    Devuelve el profit mínimo (fracción 0–1) según costo unitario y perfil.

    EXPLICACIÓN PARA PRINCIPIANTES:
    El rango se decide SOLO por el costo de UNA unidad, no por costo × cantidad.
    Ejemplo: costo $450 × 3 uds → tramo 0–499 del perfil elegido.

    Args:
        costo_unitario: Costo proveedor por unidad (MXN sin IVA).
        perfil        : Tipo de cotización (lee BD); None → semilla.
        rangos        : Lista precalculada (opcional, más eficiente en bucles).

    Returns:
        Decimal con el mínimo (ej. Decimal('0.45')).
    """
    lista = _resolver_lista_rangos(perfil=perfil, rangos=rangos)
    costo = _a_decimal(costo_unitario)
    if costo < 0:
        costo = Decimal('0')

    # Recorremos de menor a mayor; el último rango sin tope atrapa $1500+
    for rango in lista:
        minimo = _a_decimal(rango['costo_min'])
        maximo = rango['costo_max']
        if maximo is None:
            if costo >= minimo:
                return _a_decimal(rango['profit_minimo'])
        else:
            # Intervalo [minimo, maximo): 499.99 → tramo bajo, 500 → siguiente
            if costo >= minimo and costo < _a_decimal(maximo):
                return _a_decimal(rango['profit_minimo'])

    # Defensa: último tramo de la lista o semilla $1500+
    if lista:
        return _a_decimal(lista[-1]['profit_minimo'])
    return Decimal('0.28')


def resolver_profit_linea(
    costo_unitario: NumberLike,
    profit_perfil: NumberLike,
    profit_override: Optional[NumberLike] = None,
    perfil: Optional[str] = None,
    rangos: Optional[List[Dict[str, Any]]] = None,
) -> Decimal:
    """
    Calcula el profit efectivo de una pieza.

    Fórmula de negocio:
        base = override si viene, si no el % del perfil
        efectivo = max(base, mínimo_por_costo_y_tipo)

    Args:
        costo_unitario  : Costo proveedor por unidad.
        profit_perfil   : % del perfil elegido (ej. 0.36 estándar).
        profit_override : % que el usuario puso en el modal (opcional).
        perfil          : Clave del tipo (para leer mínimos de BD).
        rangos          : Lista precalculada de tramos (opcional).

    Returns:
        Decimal del profit efectivo (nunca debajo del mínimo del rango).
    """
    minimo = obtener_profit_minimo(costo_unitario, perfil=perfil, rangos=rangos)
    # Si hay override explícito lo usamos; si no, el perfil
    if profit_override is not None and profit_override != '':
        base = _a_decimal(profit_override)
    else:
        base = _a_decimal(profit_perfil, default='0.36')

    # Nunca permitir profit >= 1 (rompería la división costo/(1-profit))
    if base >= Decimal('1'):
        base = Decimal('0.99')
    if base < Decimal('0'):
        base = Decimal('0')

    return max(base, minimo)


def profit_cumple_minimo(
    costo_unitario: NumberLike,
    profit_propuesto: NumberLike,
    perfil: Optional[str] = None,
    rangos: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    """
    True si el % propuesto es >= al mínimo del rango (costo + perfil).

    Args:
        costo_unitario   : Costo por unidad.
        profit_propuesto : Fracción 0–1 que envió el modal/API.
        perfil           : Tipo de cotización.
        rangos           : Lista precalculada (opcional).

    Returns:
        bool
    """
    propuesto = _a_decimal(profit_propuesto)
    minimo = obtener_profit_minimo(costo_unitario, perfil=perfil, rangos=rangos)
    return propuesto >= minimo


def calcular_precio_unitario_con_profit(
    costo_unitario: NumberLike,
    profit: NumberLike,
) -> Decimal:
    """
    precio_unitario_sin_iva = costo / (1 - profit).

    Args:
        costo_unitario : Costo proveedor.
        profit         : Margen efectivo (0–1).

    Returns:
        Decimal redondeado a 2 decimales.
    """
    costo = _a_decimal(costo_unitario)
    target = _a_decimal(profit)
    factor = Decimal('1') - target
    if factor <= 0:
        factor = Decimal('1')
    if costo <= 0:
        return Decimal('0.00')
    precio = costo / factor
    return precio.quantize(Decimal('0.01'))


def parsear_profit_overrides(raw: Any) -> Dict[int, Decimal]:
    """
    Convierte el JSON del modal {\"12\": 0.40, \"15\": 0.30} a dict tipado.

    Args:
        raw: str JSON, dict ya parseado, o vacío.

    Returns:
        Dict[linea_pk, profit_fracción].

    Raises:
        ValueError: si el JSON es inválido o un valor no es numérico.
    """
    import json

    if raw is None or raw == '':
        return {}
    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError('El mapa de profit por pieza no es JSON válido.') from exc
    else:
        raise ValueError('Formato de profit por pieza no reconocido.')

    if not isinstance(data, dict):
        raise ValueError('profit_por_pieza debe ser un objeto {linea_id: profit}.')

    resultado: Dict[int, Decimal] = {}
    for clave, valor in data.items():
        try:
            linea_id = int(clave)
            profit = _a_decimal(valor)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f'Profit inválido para línea "{clave}": se esperaba un número.'
            ) from exc
        if profit < 0 or profit >= 1:
            raise ValueError(
                f'Profit de la línea {linea_id} debe estar entre 0 y 99%.'
            )
        resultado[linea_id] = profit
    return resultado


def validar_profit_overrides_contra_lineas(
    lineas,
    overrides: Dict[int, Decimal],
    perfil: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Rechaza overrides explícitos debajo del mínimo (costo + tipo de cotización).

    EXPLICACIÓN PARA PRINCIPIANTES:
    Si el usuario manda 10% en una pieza de $100 (mínimo del perfil), la API
    responde error. El perfil por debajo del mínimo sí se eleva solo;
    aquí solo validamos lo que el usuario escribió a mano.

    Args:
        lineas    : Iterable de LineaCotizacion (cotizables).
        overrides : Mapa pk → profit propuesto.
        perfil    : Tipo de servicio elegido en el modal.

    Returns:
        (True, '') si todo OK; (False, mensaje) si hay violación.
    """
    # Una sola lectura de rangos para todo el lote
    lista_rangos = _resolver_lista_rangos(perfil=perfil)
    lineas_por_pk = {int(l.pk): l for l in lineas}
    for linea_id, profit in overrides.items():
        linea = lineas_por_pk.get(int(linea_id))
        if linea is None:
            return False, f'La línea #{linea_id} no pertenece a esta cotización.'
        if getattr(linea, 'es_linea_reacondicionado', False):
            continue
        costo = linea.costo_unitario or 0
        minimo = obtener_profit_minimo(costo, rangos=lista_rangos)
        if profit < minimo:
            nombre = (
                getattr(getattr(linea, 'producto', None), 'nombre', None)
                or f'línea #{linea_id}'
            )
            return False, (
                f'Profit {float(profit) * 100:.0f}% en "{nombre}" está debajo '
                f'del mínimo {float(minimo) * 100:.0f}% '
                f'(costo unitario ${float(costo):.2f}).'
            )
    return True, ''


def aplicar_profit_overrides_a_items(
    items: List[Dict[str, Any]],
    overrides: Dict[int, Decimal],
) -> List[Dict[str, Any]]:
    """
    Inyecta profit_override en cada ítem de pieza según el mapa del modal.

    Args:
        items     : Ítems serializados para PDF/Celery.
        overrides : pk → profit.

    Returns:
        Nueva lista de ítems (no muta servicios).
    """
    if not overrides:
        return items
    salida: List[Dict[str, Any]] = []
    for item in items:
        if item.get('es_servicio'):
            salida.append(item)
            continue
        pk = item.get('pk') or item.get('linea_pk')
        copia = dict(item)
        if pk is not None and int(pk) in overrides:
            copia['profit_override'] = float(overrides[int(pk)])
        salida.append(copia)
    return salida


def persistir_profit_aplicado_lineas(
    lineas,
    tipo_servicio_profit: NumberLike,
    overrides: Optional[Dict[int, Decimal]] = None,
    perfil: Optional[str] = None,
) -> int:
    """
    Guarda LineaCotizacion.profit_aplicado al enviar la cotización.

    Args:
        lineas                 : Líneas de pieza cotizables.
        tipo_servicio_profit   : profit_target del perfil (fracción).
        overrides              : Overrides del modal (opcionales).
        perfil                 : Clave del tipo (para mínimos de BD).

    Returns:
        Cantidad de líneas actualizadas.
    """
    overrides = overrides or {}
    lista_rangos = _resolver_lista_rangos(perfil=perfil)
    actualizadas = 0
    for linea in lineas:
        if getattr(linea, 'es_linea_reacondicionado', False):
            continue
        costo = linea.costo_unitario or 0
        if float(costo) <= 0:
            continue
        override = overrides.get(int(linea.pk))
        efectivo = resolver_profit_linea(
            costo,
            tipo_servicio_profit,
            profit_override=override,
            rangos=lista_rangos,
        )
        # update() evita disparar señales/save pesados innecesarios
        type(linea).objects.filter(pk=linea.pk).update(profit_aplicado=efectivo)
        actualizadas += 1
    return actualizadas
