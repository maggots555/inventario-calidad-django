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

# Claves válidas del catálogo, en el orden en que deben aparecer.
PERFILES_VALIDOS = tuple(clave for clave, _ in PERFIL_DIAGNOSTICO_CHOICES)

# ============================================================================
# REGLA CENTRAL: cobrable = tiene precio configurado (> $0)
# ============================================================================
# EXPLICACIÓN PARA PRINCIPIANTES:
# Un diagnóstico que vale $0 no es un cobro de cero pesos: es un servicio que
# este negocio no cobra (Mostrador, Reparación nivel componente) o un precio
# que Gerencia todavía no configuró. En los dos casos no hay nada que
# registrar, así que ese perfil no se ofrece en el selector ni se puede
# guardar.
#
# Lo importante es que la regla mira el TARIFARIO, no una lista escrita aquí.
# Si mañana Gerencia decide cobrar el diagnóstico de Mostrador, aparece solo;
# si pone Express en $0, desaparece solo. Ningún programador tiene que enterarse.


class TarifarioNoDisponible(Exception):
    """
    No hay un precio válido para cobrar este diagnóstico.

    Cubre dos situaciones que para quien captura significan lo mismo
    ("ahora no puedo cobrar esto"), con mensajes distintos:
      - El tarifario no se pudo leer (base caída, tabla sin migrar).
      - El perfil existe pero está configurado en $0.

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
        disponible: False cuando el perfil ya no tiene precio configurado y
            solo aparece porque la orden lo tenía guardado de antes.
    """

    clave: str
    etiqueta: str
    tarifa: Decimal
    gama: Optional[str]
    disponible: bool = True


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
        Decimal con 2 decimales, siempre mayor a cero.

    Raises:
        ValueError: si el perfil no existe en el catálogo.
        TarifarioNoDisponible: si no hay tarifario, o si el perfil está
            configurado en $0 (no es cobrable).

    Efectos secundarios:
        Lee el tarifario del tenant activo.
    """
    if not es_perfil_valido(perfil):
        raise ValueError(f'Perfil de diagnóstico desconocido: {perfil!r}')

    config = _leer_tarifario()
    monto = _dinero(config.get(perfil, {}).get('diagnostico', 0))

    # Paso: $0 no es un cobro válido. O el perfil no se cobra en este negocio,
    # o el panel de parámetros está a medio configurar. En ambos casos guardar
    # el cero sería registrar un cobro que no existe.
    if monto <= 0:
        raise TarifarioNoDisponible(
            f'El diagnóstico "{etiqueta_perfil(perfil)}" no tiene precio '
            f'configurado en el tarifario del cotizador, así que no se puede '
            f'cobrar. Revisa el panel de parámetros.'
        )

    return monto


def perfil_es_cobrable(perfil: Optional[str]) -> bool:
    """
    True si este diagnóstico tiene un precio configurado mayor a cero.

    Es lo que decide si el perfil aparece en el selector. Se consulta contra
    el tarifario vivo, no contra una lista fija.

    Args:
        perfil: clave del perfil.

    Returns:
        bool: False si no existe, vale $0 o el tarifario no responde.

    Efectos secundarios:
        Lee el tarifario del tenant activo.
    """
    return tarifa_perfil(perfil) > 0


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


def opciones_diagnostico(perfil_actual: Optional[str] = None) -> List[OpcionDiagnostico]:
    """
    Diagnósticos que hoy se pueden cobrar, con su precio vigente.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Solo devuelve los perfiles con precio mayor a cero. Un diagnóstico en $0
    no se cobra, así que ofrecerlo en el selector solo daría lugar a capturas
    que no significan nada.

    El argumento `perfil_actual` cubre un caso incómodo: una orden que ya tiene
    guardado un perfil que después quedó en $0. Si lo dejáramos fuera, el
    selector mostraría otra cosa distinta a la que la orden realmente tiene, y
    al guardar se perdería el dato sin que nadie lo pidiera. Por eso ese perfil
    se incluye igual, marcado como no disponible.

    Args:
        perfil_actual: perfil ya guardado en la orden (o None / '').

    Returns:
        Lista de OpcionDiagnostico en el orden del catálogo. Puede venir vacía
        si el tarifario no responde o no hay ningún precio configurado.

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
        es_cobrable = tarifa > 0

        # Paso: sin precio no se ofrece, salvo que la orden ya lo tenga guardado.
        if not es_cobrable and clave != (perfil_actual or ''):
            continue

        regla = PERFIL_DIAGNOSTICO_GAMA.get(clave, {})
        opciones.append(
            OpcionDiagnostico(
                clave=clave,
                etiqueta=etiqueta,
                tarifa=tarifa,
                gama=regla.get('gama'),
                disponible=es_cobrable,
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
