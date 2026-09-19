"""
El diagnóstico se elige de un catálogo; el precio lo pone el tarifario.

Objetivo de negocio:
    Antes el técnico escribía a mano el "costo de mano de obra" de la orden.
    Eso permitía que el mismo servicio se capturara con montos distintos y,
    peor, que nadie supiera si el número incluía IVA. Al llegar el
    autofacturador eso se volvió un problema real: para emitir un CFDI hay que
    desglosar subtotal + IVA, y no se puede desglosar un monto ambiguo.

    Ahora el técnico elige QUÉ diagnóstico cobró (Estándar, Express, Alta Gama,
    Server…) y SIGMA pone el precio desde el mismo tarifario que usa el
    cotizador. El monto guardado siempre es SIN IVA.

EXPLICACIÓN PARA PRINCIPIANTES — por qué este archivo y no el modelo:
    `OrdenServicio` ya es un modelo enorme y la regla del proyecto es que el
    modelo guarde datos (campos, choices), no reglas de negocio. Calcular
    precios, decidir la gama del equipo y escribir historial son reglas, así
    que viven aquí. El modelo solo tiene el campo `perfil_diagnostico`.

Efectos secundarios:
    `aplicar_perfil_diagnostico()` escribe en OrdenServicio, Cotizacion,
    DetalleEquipo e HistorialOrden. El resto del módulo es solo lectura.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import List, Optional

from django.core.exceptions import ObjectDoesNotExist
from django.db import router, transaction

from config.constants import (
    PERFIL_DIAGNOSTICO_CHOICES,
    PERFIL_DIAGNOSTICO_GAMA,
)

CENTAVO = Decimal('0.01')

# Mapa clave → etiqueta legible ('estandar' → 'Estándar')
_PERFIL_LABELS = dict(PERFIL_DIAGNOSTICO_CHOICES)

# Claves válidas, en el orden en que deben aparecer en el selector.
PERFILES_VALIDOS = tuple(clave for clave, _ in PERFIL_DIAGNOSTICO_CHOICES)

# Perfiles que legítimamente cobran $0 de diagnóstico.
#
# EXPLICACIÓN PARA PRINCIPIANTES — por qué esta lista importa:
# Necesitamos distinguir dos ceros que se ven idénticos en el código:
#   - "Mostrador no cobra diagnóstico"  → $0 correcto, se guarda tal cual.
#   - "No pude leer el tarifario"       → $0 falso, borraría el cobro.
# Sin esta lista, un fallo de base de datos dejaría la orden en $0.00 y el
# técnico vería un mensaje de éxito. Eso es peor que un error visible.
PERFILES_SIN_CARGO = ('mostrador', 'rep_nivel_componente')


class TarifarioNoDisponible(Exception):
    """
    El tarifario del cotizador no pudo leerse o no tiene precio para el perfil.

    Se lanza SOLO al escribir (aplicar_perfil_diagnostico). Las lecturas
    informativas prefieren devolver $0.00 antes que romper una pantalla.
    """


def _dinero(valor) -> Decimal:
    """Redondea a 2 decimales como un cajero (0.005 sube a 0.01)."""
    return Decimal(str(valor or 0)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class OpcionDiagnostico:
    """
    Una fila del selector de tipo de diagnóstico.

    Args/campos:
        clave: identificador guardado en OrdenServicio.perfil_diagnostico.
        etiqueta: nombre visible ('Estándar').
        tarifa: precio SIN IVA que cobra ese perfil, según el tarifario vigente.
        gama: gama que aplicará al equipo, o None si ese perfil no la define.
    """

    clave: str
    etiqueta: str
    tarifa: Decimal
    gama: Optional[str]


def etiqueta_perfil(perfil: Optional[str]) -> str:
    """
    Nombre legible del perfil, para mensajes e historial.

    Args:
        perfil: clave del perfil ('estandar') o vacío.

    Returns:
        str: etiqueta del catálogo, o 'Sin definir' si no hay perfil.
    """
    if not perfil:
        return 'Sin definir'
    return _PERFIL_LABELS.get(perfil, perfil)


def es_perfil_valido(perfil: Optional[str]) -> bool:
    """
    True si la clave existe en el catálogo.

    Args:
        perfil: clave a verificar.

    Returns:
        bool
    """
    return bool(perfil) and perfil in PERFILES_VALIDOS


def _leer_tarifario() -> dict:
    """
    Trae el tarifario vigente del cotizador.

    EXPLICACIÓN PARA PRINCIPIANTES:
    El tarifario vive en el panel gerencial de parámetros del cotizador, con
    respaldo en el .env. Lo leemos en cada cálculo (no al arrancar Django) para
    que un cambio de precio de Presidencia aplique sin reiniciar el servidor.

    Returns:
        dict perfil → {'diagnostico': float, ...}

    Raises:
        TarifarioNoDisponible: si la configuración no se puede leer.

    Efectos secundarios:
        Lee ConfiguracionProfitPerfil del tenant activo (con fallback .env).
    """
    try:
        # Import diferido: Almacén es otra app; así evitamos ciclos al cargar.
        from almacen.utils.parametros_cotizador import obtener_profit_config

        return obtener_profit_config() or {}
    except Exception as exc:
        raise TarifarioNoDisponible(
            'No se pudo leer el tarifario de diagnósticos del cotizador.'
        ) from exc


def tarifa_perfil_estricta(perfil: str) -> Decimal:
    """
    Precio SIN IVA del perfil, fallando fuerte si el tarifario no sirve.

    Es la versión que se usa para COBRAR. Prefiere lanzar una excepción antes
    que devolver un cero que el sistema guardaría como si fuera un precio real.

    Args:
        perfil: clave del perfil ('estandar', 'alta_gama', …).

    Returns:
        Decimal con 2 decimales. Solo puede ser $0.00 para los perfiles que
        legítimamente no cobran diagnóstico (ver PERFILES_SIN_CARGO).

    Raises:
        ValueError: si el perfil no existe en el catálogo.
        TarifarioNoDisponible: si no hay tarifario, o si un perfil que SÍ debe
            cobrar tiene precio 0 (señal de configuración incompleta).

    Efectos secundarios:
        Lee el tarifario del tenant activo.
    """
    if not es_perfil_valido(perfil):
        raise ValueError(f'Perfil de diagnóstico desconocido: {perfil!r}')

    config = _leer_tarifario()
    monto = _dinero(config.get(perfil, {}).get('diagnostico', 0))

    # Paso: un cero solo es aceptable en los perfiles que no cobran. En los
    # demás significa que el panel de parámetros está a medio configurar, y
    # cobrar $0 por un diagnóstico Estándar sería un error silencioso.
    if monto <= 0 and perfil not in PERFILES_SIN_CARGO:
        raise TarifarioNoDisponible(
            f'El tarifario no tiene precio para el diagnóstico '
            f'"{etiqueta_perfil(perfil)}". Revisa el panel de parámetros '
            f'del cotizador antes de cobrarlo.'
        )

    return monto


def tarifa_perfil(perfil: Optional[str]) -> Decimal:
    """
    Precio SIN IVA del perfil, tolerante a fallos (solo para mostrar/comparar).

    Úsala para pintar pantallas o comparar contra lo ya cobrado. Para guardar
    un cobro nuevo usa tarifa_perfil_estricta().

    Args:
        perfil: clave del perfil ('estandar', 'alta_gama', …).

    Returns:
        Decimal con 2 decimales. $0.00 si el perfil no cobra diagnóstico,
        no existe, o si el tarifario no respondió.

    Efectos secundarios:
        Lee el tarifario del tenant activo.
    """
    if not es_perfil_valido(perfil):
        return Decimal('0.00')

    try:
        config = _leer_tarifario()
    except TarifarioNoDisponible:
        # Una pantalla sin precio es molesta; una pantalla caída es peor.
        return Decimal('0.00')

    return _dinero(config.get(perfil, {}).get('diagnostico', 0))


def gama_por_perfil(perfil: Optional[str], gama_actual: Optional[str]) -> Optional[str]:
    """
    Qué gama le corresponde al equipo según el diagnóstico elegido.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Un equipo de gama baja y uno de gama media pagan el mismo diagnóstico
    (Estándar), así que ese perfil NO alcanza para distinguirlos. En ese caso
    respetamos lo que ya dijo el catálogo marca/modelo, que sí sabe diferenciar.
    Los perfiles caros (Express, Alta Gama, Server) sí son concluyentes: si el
    cliente pagó ese diagnóstico, el equipo es de gama alta.

    Args:
        perfil: clave del perfil elegido.
        gama_actual: gama que hoy tiene el DetalleEquipo ('baja'/'media'/'alta'/'').

    Returns:
        Código de gama a aplicar, o None si este perfil no debe tocar la gama
        (Mostrador y Reparación nivel componente, o gama ya compatible).

    Efectos secundarios:
        Ninguno (función pura).
    """
    regla = PERFIL_DIAGNOSTICO_GAMA.get(perfil or '')
    if not regla:
        return None

    gama_destino = regla.get('gama')
    # Paso 1: perfiles sin cargo (Mostrador) no dicen nada de la gama.
    if not gama_destino:
        return None

    # Paso 2: si la gama actual ya es válida para este perfil, no la pisamos.
    actual = (gama_actual or '').strip().lower()
    if actual in regla.get('compatibles', ()):
        return None

    # Paso 3: si ya está en la gama destino, tampoco hay nada que cambiar.
    if actual == gama_destino:
        return None

    return gama_destino


def opciones_diagnostico() -> List[OpcionDiagnostico]:
    """
    Catálogo completo con el precio vigente de cada perfil.

    Lo usa el formulario para armar el selector y mostrar el monto al técnico
    antes de guardar, para que vea exactamente qué va a cobrar.

    Returns:
        Lista de OpcionDiagnostico en el orden del catálogo.

    Efectos secundarios:
        Una lectura del tarifario (se reutiliza para todos los perfiles).
    """
    # Leemos el tarifario UNA vez y no una por perfil: son 6 consultas evitadas.
    try:
        config = _leer_tarifario()
    except TarifarioNoDisponible:
        config = {}

    opciones: List[OpcionDiagnostico] = []
    for clave, etiqueta in PERFIL_DIAGNOSTICO_CHOICES:
        tarifa = _dinero(config.get(clave, {}).get('diagnostico', 0))
        regla = PERFIL_DIAGNOSTICO_GAMA.get(clave, {})
        opciones.append(
            OpcionDiagnostico(
                clave=clave,
                etiqueta=etiqueta,
                tarifa=tarifa,
                gama=regla.get('gama'),
            )
        )
    return opciones


def _gama_actual(orden) -> str:
    """Gama del equipo hoy ('baja'/'media'/'alta') o '' si no hay detalle."""
    try:
        return (orden.detalle_equipo.gama or '').strip().lower()
    except ObjectDoesNotExist:
        return ''
    except AttributeError:
        return ''


@dataclass(frozen=True)
class ResultadoAplicacion:
    """
    Qué cambió al aplicar un perfil de diagnóstico.

    Args/campos:
        perfil: clave aplicada.
        monto_anterior / monto_nuevo: mano de obra antes y después (sin IVA).
        gama_anterior / gama_nueva: gama del equipo; gama_nueva es None si no
            se tocó la gama.
    """

    perfil: str
    monto_anterior: Decimal
    monto_nuevo: Decimal
    gama_anterior: str
    gama_nueva: Optional[str]


def aplicar_perfil_diagnostico(orden, perfil: str, usuario=None) -> ResultadoAplicacion:
    """
    Guarda el diagnóstico elegido: monto del tarifario, gama e historial.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta es la única puerta para cambiar la mano de obra. Hace cuatro cosas en
    orden y deja todo consistente:
      1. Busca el precio del perfil en el tarifario (sin IVA).
      2. Lo guarda en la orden y, si ya existe, también en la cotización.
      3. Ajusta la gama del equipo si ese perfil la define.
      4. Escribe el historial para que se pueda auditar quién cobró qué.

    Args:
        orden: OrdenServicio a actualizar.
        perfil: clave del catálogo ('estandar', 'alta_gama', …).
        usuario: Empleado que hace el cambio (queda en el historial). Opcional.

    Returns:
        ResultadoAplicacion con los valores antes/después, para armar el
        mensaje que ve el técnico.

    Raises:
        ValueError: si el perfil no existe en el catálogo.
        TarifarioNoDisponible: si el tarifario no responde o no tiene precio
            para ese perfil. Preferimos fallar a guardar un cobro en $0.

    Efectos secundarios:
        Escribe OrdenServicio.costo_mano_obra, OrdenServicio.perfil_diagnostico,
        Cotizacion.costo_mano_obra (si hay cotización), DetalleEquipo.gama
        (si el perfil la define) y crea uno o dos HistorialOrden.
        Todo ocurre dentro de una transacción: o se guarda completo o nada.
    """
    from servicio_tecnico.models import HistorialOrden, OrdenServicio

    if not es_perfil_valido(perfil):
        raise ValueError(f'Perfil de diagnóstico desconocido: {perfil!r}')

    monto_anterior = _dinero(getattr(orden, 'costo_mano_obra', 0))
    perfil_anterior = getattr(orden, 'perfil_diagnostico', '') or ''
    gama_anterior = _gama_actual(orden)

    # Paso 1: el precio SIEMPRE sale del tarifario, nunca del formulario.
    # Versión estricta: si el tarifario falla, no seguimos. Guardar $0 aquí
    # significaría borrar el cobro del diagnóstico sin que nadie se entere.
    monto_nuevo = tarifa_perfil_estricta(perfil)

    # EXPLICACIÓN PARA PRINCIPIANTES — por qué hay una transacción:
    # Abajo se escriben hasta cuatro tablas (orden, cotización, equipo,
    # historial). Sin transacción, un error a la mitad dejaría la orden con el
    # monto nuevo y la cotización con el viejo. Ese descuadre no rompe nada de
    # inmediato: aparece semanas después, cuando el total que vio el cliente
    # no coincide con el de la factura.
    #
    # El `using=` no es decorativo. SIGMA tiene una base por país y Django abre
    # una conexión distinta por alias. Sin `using=`, la transacción se abriría
    # en `default` mientras los INSERT viajan a `mexico`: no protegería nada.
    db_alias = (
        getattr(orden._state, 'db', None)
        or router.db_for_write(OrdenServicio, instance=orden)
        or 'default'
    )

    with transaction.atomic(using=db_alias):
        # Paso 2: persistir en la orden (fuente de verdad de la mano de obra).
        orden.perfil_diagnostico = perfil
        orden.costo_mano_obra = monto_nuevo
        orden.save(update_fields=['perfil_diagnostico', 'costo_mano_obra'])

        # Paso 3: si ya hay cotización, mantener ambos montos alineados.
        cotizacion = getattr(orden, 'cotizacion', None)
        if cotizacion is not None:
            cotizacion.costo_mano_obra = monto_nuevo
            cotizacion.save(update_fields=['costo_mano_obra'])

        # Paso 4: cascada de gama, solo si este perfil es concluyente.
        gama_nueva = gama_por_perfil(perfil, gama_anterior)
        if gama_nueva:
            detalle = getattr(orden, 'detalle_equipo', None)
            if detalle is not None:
                detalle.gama = gama_nueva
                # update_fields evita tocar email/RFC/folio del cliente de paso.
                detalle.save(update_fields=['gama'])
                HistorialOrden.objects.create(
                    orden=orden,
                    tipo_evento='sistema',
                    comentario=(
                        f'Gama actualizada por tipo de diagnóstico '
                        f'({etiqueta_perfil(perfil)}): '
                        f'{_etiqueta_gama(gama_anterior)} → '
                        f'{_etiqueta_gama(gama_nueva)}'
                    ),
                    usuario=usuario,
                    es_sistema=True,
                )
            else:
                gama_nueva = None

        # Paso 5: rastro del cobro. Guardamos perfil Y monto: si mañana cambia
        # el tarifario, el historial sigue diciendo cuánto se cobró ese día.
        HistorialOrden.objects.create(
            orden=orden,
            tipo_evento='cotizacion',
            comentario=(
                f'Diagnóstico: {etiqueta_perfil(perfil_anterior)} → '
                f'{etiqueta_perfil(perfil)}. Mano de obra ${monto_anterior} → '
                f'${monto_nuevo} (sin IVA, tarifa del cotizador)'
            ),
            usuario=usuario,
            es_sistema=False,
        )

    return ResultadoAplicacion(
        perfil=perfil,
        monto_anterior=monto_anterior,
        monto_nuevo=monto_nuevo,
        gama_anterior=gama_anterior,
        gama_nueva=gama_nueva,
    )


def _etiqueta_gama(codigo: Optional[str]) -> str:
    """Etiqueta legible de la gama, reutilizando el helper ya existente."""
    from servicio_tecnico.utils_gama import etiqueta_gama

    return etiqueta_gama(codigo)
