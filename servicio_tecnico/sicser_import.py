"""
Importación de órdenes desde SICSER hacia SIGMA (Fase 2).

Objetivo de negocio:
    Crear OrdenServicio + DetalleEquipo en SIGMA a partir de registros OOW o
    de garantía Dell listados en las APIs de SICSER.

Reglas confirmadas:
    - OOW: orden_cliente = OOW-{dígitos finales del folio}
    - Garantía: orden_cliente = numero_dps (sin prefijo OOW-)
    - Garantía: siempre marca Dell y tipo Laptop
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from config.constants import MARCAS_EQUIPOS_CHOICES, TIPO_EQUIPO_CHOICES
from inventario.models import Empleado, Sucursal

from .models import DetalleEquipo, OrdenServicio, ReferenciaGamaEquipo
from .sicser_client import OrdenGarantiaSicser, OrdenOOWSicser

logger = logging.getLogger(__name__)

# Palabras clave en el nombre de sucursal SIGMA según código CIS SICSER.
CIS_SUCURSAL_KEYWORDS: dict[str, list[str]] = {
    'DROP': ['drop off', 'dropoff', 'drop-off', 'drop'],
    'SAT': ['satélite', 'satelite', 'satellite', ' sic', 'sic '],
    'MTR': ['monterrey'],
    'GDL': ['guadalajara'],
    'BUA': ['buenos aires'],
    'BOG': ['bogotá', 'bogota'],
    'MED': ['medellín', 'medellin'],
    'SAN': ['santiago'],
}

MARCAS_VALIDAS = {valor for valor, _ in MARCAS_EQUIPOS_CHOICES if valor}
TIPOS_VALIDOS = {valor for valor, _ in TIPO_EQUIPO_CHOICES if valor}

# Alias de marcas que envía SICSER y no coinciden exactamente con SIGMA.
ALIAS_MARCA_SICSER: dict[str, str] = {
    'OMEN': 'HP',
    'HEWLETT PACKARD': 'HP',
    'HEWLETT-PACKARD': 'HP',
}


class SicserImportError(Exception):
    """Error de negocio al importar una orden desde SICSER."""


@dataclass(frozen=True)
class ResultadoImportacionSicser:
    """
    Resultado exitoso de una importación SICSER → SIGMA.

    Atributos:
        orden: OrdenServicio creada.
        creada: Siempre True en importación exitosa (reservado para idempotencia futura).
        mensaje: Texto para mostrar al usuario.
    """

    orden: OrdenServicio
    creada: bool
    mensaje: str


def normalizar_marca_oow(marca_raw: str) -> str:
    """
    Convierte la marca de SICSER a un valor válido de MARCAS_EQUIPOS_CHOICES.

    Args:
        marca_raw: Texto de marca desde la API OOW.

    Returns:
        str: Código de marca válido en SIGMA (ej. HP, Lenovo, Otra).
    """
    marca = (marca_raw or '').strip()
    if not marca:
        return 'Otra'

    marca_upper = marca.upper()
    if marca_upper in ALIAS_MARCA_SICSER:
        return ALIAS_MARCA_SICSER[marca_upper]

    for codigo, etiqueta in MARCAS_EQUIPOS_CHOICES:
        if not codigo:
            continue
        if marca_upper == codigo.upper() or marca_upper == etiqueta.upper():
            return codigo

    return 'Otra'


def normalizar_tipo_equipo(tipo_raw: str, default: str = 'Laptop') -> str:
    """
    Normaliza el tipo de equipo al catálogo de SIGMA.

    Args:
        tipo_raw: Valor desde SICSER (ej. LAPTOP).
        default: Valor por defecto si no hay coincidencia.

    Returns:
        str: PC, Laptop o AIO.
    """
    tipo = (tipo_raw or '').strip().upper()
    mapa = {
        'LAPTOP': 'Laptop',
        'NOTEBOOK': 'Laptop',
        'PC': 'PC',
        'DESKTOP': 'PC',
        'AIO': 'AIO',
        'ALL IN ONE': 'AIO',
    }
    resultado = mapa.get(tipo, default)
    return resultado if resultado in TIPOS_VALIDOS else default


def resolver_sucursal_por_cis(codigo_cis_url: str, sucursal_id: int | None = None) -> Sucursal:
    """
    Determina la sucursal SIGMA para una orden importada.

    Args:
        codigo_cis_url: Código CIS corto (DROP, SAT, MTR, etc.).
        sucursal_id: PK de sucursal elegida manualmente por el operador (opcional).

    Returns:
        Sucursal: Instancia activa a asignar a la orden.

    Raises:
        SicserImportError: Si no hay sucursales activas o la PK no es válida.
    """
    if sucursal_id:
        try:
            return Sucursal.objects.get(pk=sucursal_id, activa=True)
        except Sucursal.DoesNotExist as exc:
            raise SicserImportError('La sucursal seleccionada no es válida o está inactiva.') from exc

    keywords = CIS_SUCURSAL_KEYWORDS.get(codigo_cis_url.upper(), [])
    sucursales = list(Sucursal.objects.filter(activa=True).order_by('nombre'))

    if not sucursales:
        raise SicserImportError('No hay sucursales activas en SIGMA. Configure al menos una sucursal.')

    if keywords:
        for sucursal in sucursales:
            nombre = sucursal.nombre.lower()
            if any(palabra in nombre for palabra in keywords):
                return sucursal

    # Fallback: primera sucursal activa del país/tenant.
    return sucursales[0]


def resolver_tecnico(usuario) -> Empleado:
    """
    Asigna el técnico de la orden importada (misma lógica que NuevaOrdenForm).

    Args:
        usuario: Usuario Django que ejecuta la importación.

    Returns:
        Empleado: Técnico asignado.

    Raises:
        SicserImportError: Si no hay empleado disponible.
    """
    if usuario and hasattr(usuario, 'empleado') and usuario.empleado:
        return usuario.empleado

    empleado = Empleado.objects.filter(activo=True).first()
    if empleado:
        return empleado

    raise SicserImportError('No hay empleados activos para asignar a la orden importada.')


def extraer_falla_garantia(instrucciones_dell: str) -> str:
    """
    Extrae el texto de falla desde instrucciones_dell de la API de garantías.

    EXPLICACIÓN PARA PRINCIPIANTES:
    El formato Dell imprime el bloque completo de SICSER en
    “DESCRIPCIÓN DE LA FALLA INICIAL”. Por eso preferimos el texto íntegro
    (hasta 4000 chars). Si viene vacío, usamos un mensaje por defecto.

    Args:
        instrucciones_dell: Bloque de texto de diagnóstico Dell.

    Returns:
        str: Descripción de falla para falla_principal.
    """
    texto = (instrucciones_dell or '').strip()
    if not texto:
        return 'Orden importada desde SICSER (garantía Dell)'
    return texto[:4000]


def es_mis_desde_grupo(nombre_grupo: str) -> bool:
    """
    Indica si la orden de garantía corresponde a Mail-In Service.

    Args:
        nombre_grupo: Valor nombre_grupo de SICSER (ej. Carry In).

    Returns:
        bool: True si el texto sugiere MIS.
    """
    grupo = (nombre_grupo or '').lower()
    return 'mail' in grupo and 'in' in grupo


def parsear_fecha_sicser(fecha_texto: str):
    """
    Intenta convertir la fecha de SICSER a datetime con zona horaria.

    Args:
        fecha_texto: Cadena de fecha desde la API.

    Returns:
        datetime | None: Fecha parseada o None si falla.
    """
    if not fecha_texto:
        return None

    limpio = fecha_texto.strip().split('.')[0]
    formatos = (
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
    )
    for formato in formatos:
        try:
            naive = datetime.strptime(limpio[:19], formato)
            return timezone.make_aware(naive, timezone.get_current_timezone())
        except ValueError:
            continue
    return None


def buscar_orden_importada(origen: str, id_externo: str) -> OrdenServicio | None:
    """
    Busca si ya existe una orden importada desde el mismo registro SICSER.

    Args:
        origen: 'oow' o 'garantia'.
        id_externo: id_orden o numero_dps como cadena.

    Returns:
        OrdenServicio | None: Orden existente o None.
    """
    if not id_externo:
        return None

    detalle = (
        DetalleEquipo.objects
        .select_related('orden')
        .filter(sicser_origen=origen, sicser_id_externo=str(id_externo))
        .first()
    )
    return detalle.orden if detalle else None


def mapa_importaciones_sicser() -> tuple[dict[str, dict], dict[str, dict]]:
    """
    Construye mapas de órdenes ya importadas para la pantalla de consulta.

    Returns:
        tuple: (mapa_oow por id_orden, mapa_garantia por numero_dps).
    """
    detalles = (
        DetalleEquipo.objects
        .filter(sicser_origen__in=['oow', 'garantia'], sicser_id_externo__gt='')
        .select_related('orden')
    )

    mapa_oow: dict[str, dict] = {}
    mapa_garantia: dict[str, dict] = {}

    for detalle in detalles:
        info = {
            'orden_id': detalle.orden_id,
            'numero_orden_interno': detalle.orden.numero_orden_interno,
            'orden_cliente': detalle.orden_cliente,
        }
        if detalle.sicser_origen == 'oow':
            mapa_oow[detalle.sicser_id_externo] = info
        elif detalle.sicser_origen == 'garantia':
            mapa_garantia[detalle.sicser_id_externo] = info

    return mapa_oow, mapa_garantia


def listar_ordenes_importadas_sicser(
    texto_busqueda: str = '',
    limite: int = 100,
) -> list[dict]:
    """
    Lista órdenes ya creadas en SIGMA desde SICSER (histórico local).

    Objetivo de negocio:
        Mostrar en la pestaña Importadas las órdenes que ya existen en SIGMA,
        aunque el registro ya no aparezca en la API de SICSER.

    Args:
        texto_busqueda: Filtro opcional por folio, DPS, service tag, cliente u orden.
        limite: Máximo de filas a devolver (más recientes primero).

    Returns:
        list[dict]: Filas listas para el template (origen, folio, ids, URLs).
    """
    from django.db.models import Q

    from .sicser_client import (
        etiqueta_cis_legible,
        parsear_codigo_cis_para_url,
        parsear_codigo_pais_desde_folio_oow,
        url_formato_garantia,
        url_formato_oow,
    )

    # EXPLICACIÓN PARA PRINCIPIANTES:
    # El histórico vive en DetalleEquipo: si sicser_origen y sicser_id_externo
    # están llenos, la orden se creó desde SICSER (manual o futura sync).
    queryset = (
        DetalleEquipo.objects
        .filter(sicser_origen__in=['oow', 'garantia'], sicser_id_externo__gt='')
        .select_related('orden', 'orden__sucursal')
        .order_by('-orden__fecha_ingreso')
    )

    filtro = (texto_busqueda or '').strip()
    if filtro:
        queryset = queryset.filter(
            Q(orden_cliente__icontains=filtro)
            | Q(folio_sicser__icontains=filtro)
            | Q(sicser_id_externo__icontains=filtro)
            | Q(numero_serie__icontains=filtro)
            | Q(nombre_cliente__icontains=filtro)
            | Q(orden__numero_orden_interno__icontains=filtro)
            | Q(sicser_ciudad__icontains=filtro)
            | Q(sicser_estado__icontains=filtro)
            | Q(sicser_cis__icontains=filtro)
        )

    filas: list[dict] = []
    for detalle in queryset[:limite]:
        origen = detalle.sicser_origen
        folio = (detalle.folio_sicser or detalle.sicser_id_externo or '').strip()

        # CIS: guardado al importar; si falta en OOW, se deduce del folio.
        codigo_cis = (detalle.sicser_cis or '').strip().upper()
        if not codigo_cis and origen == 'oow' and folio:
            codigo_cis = parsear_codigo_cis_para_url(folio)

        url_formato = ''
        if origen == 'garantia' and folio:
            url_formato = url_formato_garantia(folio)
        elif origen == 'oow' and folio:
            codigo_pais = parsear_codigo_pais_desde_folio_oow(folio) or 'MX'
            url_formato = url_formato_oow(
                folio,
                codigo_cis or parsear_codigo_cis_para_url(folio),
                codigo_pais,
            )

        filas.append({
            'orden_id': detalle.orden_id,
            'numero_orden_interno': detalle.orden.numero_orden_interno,
            'orden_cliente': detalle.orden_cliente,
            'origen': origen,
            'origen_etiqueta': 'OOW' if origen == 'oow' else 'Garantía Dell',
            'folio_sicser': folio,
            'sicser_id_externo': detalle.sicser_id_externo,
            'service_tag': detalle.numero_serie,
            'nombre_cliente': detalle.nombre_cliente,
            'fecha_ingreso': detalle.orden.fecha_ingreso,
            'sucursal': detalle.orden.sucursal.nombre if detalle.orden.sucursal else '',
            'ciudad': (detalle.sicser_ciudad or '').strip(),
            'estado': (detalle.sicser_estado or '').strip(),
            'codigo_cis': codigo_cis,
            'cis_etiqueta': etiqueta_cis_legible(codigo_cis) if codigo_cis else '',
            'url_formato_digital': url_formato,
        })

    return filas


def contar_ordenes_importadas_sicser() -> int:
    """
    Cuenta cuántas órdenes de SIGMA fueron importadas desde SICSER.

    Returns:
        int: Total de DetalleEquipo con origen SICSER.
    """
    return DetalleEquipo.objects.filter(
        sicser_origen__in=['oow', 'garantia'],
        sicser_id_externo__gt='',
    ).count()


def _calcular_gama(marca: str, modelo: str) -> str:
    """Obtiene gama desde tabla de referencia o 'media' por defecto."""
    referencia = ReferenciaGamaEquipo.obtener_gama(marca, modelo)
    if referencia:
        return referencia.gama
    return 'media'


@transaction.atomic
def importar_orden_oow_desde_sicser(
    registro: OrdenOOWSicser,
    usuario,
    sucursal_id: int | None = None,
) -> ResultadoImportacionSicser:
    """
    Crea una orden de diagnóstico OOW en SIGMA desde un registro SICSER.

    Args:
        registro: Datos normalizados de la API OOW.
        usuario: Usuario que ejecuta la importación.
        sucursal_id: Sucursal opcional elegida en la UI.

    Returns:
        ResultadoImportacionSicser: Orden creada y mensaje de éxito.

    Raises:
        SicserImportError: Si ya existe o faltan datos obligatorios.
    """
    id_externo = str(registro.id_orden)
    existente = buscar_orden_importada('oow', id_externo)
    if existente:
        raise SicserImportError(
            f'Esta orden SICSER ya está en SIGMA como {existente.numero_orden_interno}.'
        )

    orden_cliente = registro.preview_orden_sigma
    if DetalleEquipo.objects.filter(orden_cliente__iexact=orden_cliente).exists():
        raise SicserImportError(
            f'Ya existe una orden con número de cliente "{orden_cliente}" en SIGMA.'
        )

    if not registro.service_tag:
        raise SicserImportError('El registro SICSER no trae service tag; no se puede importar.')

    sucursal = resolver_sucursal_por_cis(registro.codigo_cis_url, sucursal_id)
    tecnico = resolver_tecnico(usuario)
    marca = normalizar_marca_oow(registro.marca)
    tipo_equipo = normalizar_tipo_equipo(registro.tipo_equipo)
    modelo = (registro.modelo or '')[:100]
    email = registro.email or 'cliente@ejemplo.com'

    orden = OrdenServicio(
        sucursal=sucursal,
        tecnico_asignado_actual=tecnico,
        tipo_servicio='diagnostico',
        estado='espera',
    )
    fecha_ingreso = parsear_fecha_sicser(registro.fecha)
    if fecha_ingreso:
        orden.fecha_ingreso = fecha_ingreso

    orden.save()

    detalle = DetalleEquipo(
        orden=orden,
        tipo_equipo=tipo_equipo,
        marca=marca,
        modelo=modelo,
        numero_serie=registro.service_tag.upper(),
        orden_cliente=orden_cliente,
        folio_sicser=registro.folio,
        sicser_id_externo=id_externo,
        sicser_origen='oow',
        sicser_cis=registro.codigo_cis_url or '',
        email_cliente=email,
        nombre_cliente=registro.nombre_cliente[:200],
        rfc_cliente=registro.rfc[:13],
        telefono_cliente=registro.telefono[:20],
        falla_principal=(registro.descripcion_falla or 'Importada desde SICSER OOW')[:4000],
        gama=_calcular_gama(marca, modelo),
        equipo_enciende=True,
        es_mis=False,
    )
    detalle.save()

    orden.refresh_from_db(fields=['es_fuera_garantia', 'numero_orden_interno'])

    logger.info(
        'Orden OOW importada desde SICSER: %s → %s (sicser_id=%s)',
        registro.folio,
        orden.numero_orden_interno,
        id_externo,
    )

    return ResultadoImportacionSicser(
        orden=orden,
        creada=True,
        mensaje=(
            f'Orden {orden.numero_orden_interno} creada con número de cliente '
            f'{orden_cliente} desde SICSER.'
        ),
    )


@transaction.atomic
def importar_orden_garantia_desde_sicser(
    registro: OrdenGarantiaSicser,
    usuario,
    sucursal_id: int | None = None,
) -> ResultadoImportacionSicser:
    """
    Crea una orden en garantía Dell en SIGMA desde un registro SICSER.

    Args:
        registro: Datos normalizados de la API de garantías.
        usuario: Usuario que ejecuta la importación.
        sucursal_id: Sucursal opcional elegida en la UI.

    Returns:
        ResultadoImportacionSicser: Orden creada y mensaje de éxito.

    Raises:
        SicserImportError: Si ya existe o faltan datos obligatorios.
    """
    id_externo = str(registro.numero_dps)
    existente = buscar_orden_importada('garantia', id_externo)
    if existente:
        raise SicserImportError(
            f'Esta garantía SICSER ya está en SIGMA como {existente.numero_orden_interno}.'
        )

    orden_cliente = id_externo
    if DetalleEquipo.objects.filter(orden_cliente__iexact=orden_cliente).exists():
        raise SicserImportError(
            f'Ya existe una orden con número de cliente "{orden_cliente}" en SIGMA.'
        )

    if not registro.service_tag:
        raise SicserImportError('El registro SICSER no trae service tag; no se puede importar.')

    # Garantías Dell: CIS inferido desde ciudad/estado (la API no envía CIS explícito).
    sucursal = resolver_sucursal_por_cis(registro.codigo_cis_url or 'SAT', sucursal_id)
    tecnico = resolver_tecnico(usuario)
    modelo = (registro.especificaciones or 'Latitude')[:100]
    email = registro.email_contacto or 'cliente@ejemplo.com'
    nombre_cliente = (registro.contacto or registro.empresa or '')[:200]

    orden = OrdenServicio(
        sucursal=sucursal,
        tecnico_asignado_actual=tecnico,
        tipo_servicio='diagnostico',
        estado='espera',
    )
    fecha_ingreso = parsear_fecha_sicser(registro.fecha_recepcion)
    if fecha_ingreso:
        orden.fecha_ingreso = fecha_ingreso

    orden.save()

    detalle = DetalleEquipo(
        orden=orden,
        tipo_equipo='Laptop',
        marca='Dell',
        modelo=modelo,
        numero_serie=registro.service_tag.upper(),
        orden_cliente=orden_cliente,
        folio_sicser=id_externo,
        sicser_id_externo=id_externo,
        sicser_origen='garantia',
        sicser_ciudad=(registro.ciudad or '')[:100],
        sicser_estado=(registro.estado or '')[:100],
        sicser_cis=registro.codigo_cis_url or '',
        email_cliente=email,
        nombre_cliente=nombre_cliente,
        telefono_cliente=(registro.telefono or '')[:20],
        falla_principal=extraer_falla_garantia(registro.instrucciones_dell),
        gama=_calcular_gama('Dell', modelo),
        equipo_enciende=True,
        es_mis=es_mis_desde_grupo(registro.nombre_grupo),
    )
    detalle.save()

    orden.refresh_from_db(fields=['es_fuera_garantia', 'numero_orden_interno'])

    logger.info(
        'Orden garantía importada desde SICSER: DPS %s → %s',
        id_externo,
        orden.numero_orden_interno,
    )

    return ResultadoImportacionSicser(
        orden=orden,
        creada=True,
        mensaje=(
            f'Orden {orden.numero_orden_interno} creada con DPS {orden_cliente} '
            f'(garantía Dell) desde SICSER.'
        ),
    )
