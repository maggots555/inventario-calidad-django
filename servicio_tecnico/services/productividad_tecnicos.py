"""
Productividad de técnicos: consultas y generación de Excel.

Objetivo de negocio:
    Separar claramente el flujo OOW (diagnóstico/reparación + posible upsell VM)
    del flujo FL (venta mostrador pura, sin diagnóstico), por técnico y período.

EXPLICACIÓN PARA PRINCIPIANTES:
    tipo_servicio='diagnostico' → nació como reparación/diagnóstico (folio OOW-…).
    tipo_servicio='venta_mostrador' → nació solo para mostrador (folio FL-…).
    Una orden OOW puede tener VM adicional (upsell); un FL nunca es "reparación".
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Exists, OuterRef, Prefetch, Q, QuerySet
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from config.constants import PAQUETES_CHOICES
from servicio_tecnico.models import Cotizacion, OrdenServicio, PiezaVentaMostrador, VentaMostrador

# Estados que cuentan como "trabajo terminado" (egreso / listo o ya entregado).
ESTADOS_FINALIZADOS = ('finalizado', 'entregado')

# Nombres de las 5 hojas del Excel (orden fijo para tests).
HOJAS_EXCEL = (
    'Resumen por técnico',
    'Detalle reparaciones OOW',
    'Detalle upsell OOW',
    'Detalle VM pura FL',
    'Detalle diagnósticos',
)

_PAQUETES_MAP = dict(PAQUETES_CHOICES)

TipoFlujoVM = Literal['upsell_oow', 'vm_pura_fl']


def _datos_cliente_equipo(orden: OrdenServicio) -> tuple[str, str]:
    """
    Obtiene orden_cliente y Service Tag (número de serie) del detalle.

    Args:
        orden: OrdenServicio (idealmente con select_related detalle_equipo).

    Returns:
        Tupla (orden_cliente, service_tag). Si no hay detalle, strings vacíos.
    """
    # EXPLICACIÓN: folio de negocio = orden_cliente; Service Tag = numero_serie.
    try:
        detalle = orden.detalle_equipo
    except ObjectDoesNotExist:
        return '', ''
    return (
        (detalle.orden_cliente or '').strip(),
        (detalle.numero_serie or '').strip(),
    )


def _normalizar_fecha_inicio(fecha: date | datetime | str | None) -> datetime | None:
    """Convierte el filtro de inicio a datetime aware (inicio del día)."""
    if fecha is None or fecha == '':
        return None
    if isinstance(fecha, str):
        dt = datetime.strptime(fecha, '%Y-%m-%d')
        return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
    if isinstance(fecha, date) and not isinstance(fecha, datetime):
        dt = datetime.combine(fecha, time.min)
        return timezone.make_aware(dt)
    if isinstance(fecha, datetime) and timezone.is_naive(fecha):
        return timezone.make_aware(fecha)
    return fecha


def _normalizar_fecha_fin(fecha: date | datetime | str | None) -> datetime | None:
    """Convierte el filtro de fin a datetime aware (fin del día)."""
    if fecha is None or fecha == '':
        return None
    if isinstance(fecha, str):
        dt = datetime.combine(datetime.strptime(fecha, '%Y-%m-%d'), time.max)
        return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
    if isinstance(fecha, date) and not isinstance(fecha, datetime):
        dt = datetime.combine(fecha, time.max)
        return timezone.make_aware(dt)
    if isinstance(fecha, datetime) and timezone.is_naive(fecha):
        return timezone.make_aware(fecha)
    return fecha


def _fecha_a_date(fecha: date | datetime | str | None) -> date | None:
    """Extrae solo la parte date para filtrar DateField."""
    if fecha is None or fecha == '':
        return None
    if isinstance(fecha, str):
        return datetime.strptime(fecha, '%Y-%m-%d').date()
    if isinstance(fecha, datetime):
        return fecha.date()
    if isinstance(fecha, date):
        return fecha
    return None


def _aplicar_filtros_comunes(
    qs: QuerySet[OrdenServicio],
    *,
    sucursal_id: int | str | None = None,
    tecnico_id: int | str | None = None,
    gama: str | None = None,
) -> QuerySet[OrdenServicio]:
    """Aplica filtros opcionales de sucursal, técnico y gama."""
    if sucursal_id:
        qs = qs.filter(sucursal_id=sucursal_id)
    if tecnico_id:
        qs = qs.filter(tecnico_asignado_actual_id=tecnico_id)
    if gama:
        qs = qs.filter(detalle_equipo__gama=gama)
    return qs


def queryset_ordenes_finalizadas(
    fecha_inicio: date | datetime | str | None = None,
    fecha_fin: date | datetime | str | None = None,
    sucursal_id: int | str | None = None,
    tecnico_id: int | str | None = None,
    gama: str | None = None,
) -> QuerySet[OrdenServicio]:
    """
    Órdenes en estado finalizado/entregado con fecha_finalizacion en el período.

    Returns:
        QuerySet de OrdenServicio con select_related útiles.
    """
    qs = OrdenServicio.objects.filter(
        estado__in=ESTADOS_FINALIZADOS,
        fecha_finalizacion__isnull=False,
    ).select_related(
        'sucursal',
        'tecnico_asignado_actual',
        'detalle_equipo',
    )

    inicio = _normalizar_fecha_inicio(fecha_inicio)
    fin = _normalizar_fecha_fin(fecha_fin)
    if inicio is not None:
        qs = qs.filter(fecha_finalizacion__gte=inicio)
    if fin is not None:
        qs = qs.filter(fecha_finalizacion__lte=fin)

    return _aplicar_filtros_comunes(
        qs,
        sucursal_id=sucursal_id,
        tecnico_id=tecnico_id,
        gama=gama,
    )


def obtener_reparaciones_productivas(
    fecha_inicio: date | datetime | str | None = None,
    fecha_fin: date | datetime | str | None = None,
    sucursal_id: int | str | None = None,
    tecnico_id: int | str | None = None,
    gama: str | None = None,
) -> list[dict[str, Any]]:
    """
    Reparaciones OOW: diagnóstico + finalizada + cotización aceptada.

    Ya NO incluye FL ni órdenes solo-VM (esas van a upsell o VM pura).

    Returns:
        Lista de dicts (una fila por orden OOW con cot aceptada).
    """
    cot_aceptada = Cotizacion.objects.filter(
        orden_id=OuterRef('pk'),
        usuario_acepto=True,
    )
    tiene_vm = VentaMostrador.objects.filter(orden_id=OuterRef('pk'))

    qs = (
        queryset_ordenes_finalizadas(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            sucursal_id=sucursal_id,
            tecnico_id=tecnico_id,
            gama=gama,
        )
        # Solo flujo con diagnóstico (OOW), no venta_mostrador (FL).
        .filter(tipo_servicio='diagnostico')
        .annotate(
            _cot_aceptada=Exists(cot_aceptada),
            _tiene_vm=Exists(tiene_vm),
        )
        .filter(_cot_aceptada=True)
        .select_related('cotizacion', 'venta_mostrador')
        .order_by('tecnico_asignado_actual__nombre_completo', 'fecha_finalizacion')
    )

    filas: list[dict[str, Any]] = []
    for orden in qs:
        valor_cot = Decimal('0.00')
        try:
            valor_cot = orden.cotizacion.costo_total_final or Decimal('0.00')
        except Cotizacion.DoesNotExist:
            valor_cot = Decimal('0.00')

        tiene_upsell = bool(getattr(orden, '_tiene_vm', False))
        folio_vm = ''
        if tiene_upsell:
            try:
                folio_vm = orden.venta_mostrador.folio_venta
            except VentaMostrador.DoesNotExist:
                folio_vm = ''
                tiene_upsell = False

        tecnico = orden.tecnico_asignado_actual
        orden_cliente, service_tag = _datos_cliente_equipo(orden)
        filas.append({
            'orden_id': orden.pk,
            'folio': orden_cliente,
            'service_tag': service_tag,
            'tipo_servicio': orden.tipo_servicio,
            'tecnico_id': tecnico.pk if tecnico else None,
            'tecnico': tecnico.nombre_completo if tecnico else 'Sin técnico',
            'sucursal': orden.sucursal.nombre if orden.sucursal else '',
            'estado': orden.estado,
            'fecha_finalizacion': orden.fecha_finalizacion,
            'cot_aceptada': True,
            'tiene_upsell_vm': tiene_upsell,
            'valor_cot_aceptada': valor_cot,
            'folio_vm': folio_vm,
        })
    return filas


def _filas_vm_por_tipo_servicio(
    tipo_servicio: str,
    tipo_flujo: TipoFlujoVM,
    fecha_inicio: date | datetime | str | None = None,
    fecha_fin: date | datetime | str | None = None,
    sucursal_id: int | str | None = None,
    tecnico_id: int | str | None = None,
    gama: str | None = None,
) -> list[dict[str, Any]]:
    """
    Construye filas de detalle VM filtradas por tipo_servicio de la orden.

    Args:
        tipo_servicio: 'diagnostico' (upsell OOW) o 'venta_mostrador' (FL).
        tipo_flujo: etiqueta de negocio para el Excel/resumen.

    Returns:
        Lista de dicts con desglose de servicios/paquetes.
    """
    qs = (
        queryset_ordenes_finalizadas(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            sucursal_id=sucursal_id,
            tecnico_id=tecnico_id,
            gama=gama,
        )
        .filter(
            tipo_servicio=tipo_servicio,
            venta_mostrador__isnull=False,
        )
        .select_related(
            'venta_mostrador',
            'tecnico_asignado_actual',
            'sucursal',
            'detalle_equipo',
        )
        .prefetch_related(
            Prefetch(
                'venta_mostrador__piezas_vendidas',
                queryset=PiezaVentaMostrador.objects.all(),
            ),
        )
        .order_by('tecnico_asignado_actual__nombre_completo', 'fecha_finalizacion')
    )

    filas: list[dict[str, Any]] = []
    for orden in qs:
        try:
            vm = orden.venta_mostrador
        except VentaMostrador.DoesNotExist:
            continue

        piezas = list(vm.piezas_vendidas.all())
        resumen_piezas = '; '.join(
            f'{p.descripcion_pieza} x{p.cantidad}' for p in piezas
        ) if piezas else ''

        tecnico = orden.tecnico_asignado_actual
        orden_cliente, service_tag = _datos_cliente_equipo(orden)
        filas.append({
            'orden_id': orden.pk,
            'folio': orden_cliente,
            'service_tag': service_tag,
            'tipo_servicio': orden.tipo_servicio,
            'tipo_flujo': tipo_flujo,
            'folio_vm': vm.folio_venta,
            'tecnico_id': tecnico.pk if tecnico else None,
            'tecnico': tecnico.nombre_completo if tecnico else 'Sin técnico',
            'sucursal': orden.sucursal.nombre if orden.sucursal else '',
            'paquete': vm.paquete,
            'paquete_nombre': _PAQUETES_MAP.get(vm.paquete, vm.paquete),
            'costo_paquete': vm.costo_paquete or Decimal('0.00'),
            'incluye_limpieza': vm.incluye_limpieza,
            'costo_limpieza': vm.costo_limpieza or Decimal('0.00'),
            'incluye_reinstalacion': vm.incluye_reinstalacion_so,
            'costo_reinstalacion': vm.costo_reinstalacion or Decimal('0.00'),
            'incluye_respaldo': vm.incluye_respaldo,
            'costo_respaldo': vm.costo_respaldo or Decimal('0.00'),
            'incluye_cambio_pieza': vm.incluye_cambio_pieza,
            'costo_cambio_pieza': vm.costo_cambio_pieza or Decimal('0.00'),
            'incluye_kit': vm.incluye_kit_limpieza,
            'costo_kit': vm.costo_kit or Decimal('0.00'),
            'resumen_piezas': resumen_piezas,
            'total_vm': vm.total_venta,
        })
    return filas


def obtener_upsell_oow(
    fecha_inicio: date | datetime | str | None = None,
    fecha_fin: date | datetime | str | None = None,
    sucursal_id: int | str | None = None,
    tecnico_id: int | str | None = None,
    gama: str | None = None,
) -> list[dict[str, Any]]:
    """
    Upsell OOW: órdenes con diagnóstico finalizadas que además tienen VM.

    Returns:
        Filas con desglose de servicios adicionales sobre una reparación.
    """
    return _filas_vm_por_tipo_servicio(
        tipo_servicio='diagnostico',
        tipo_flujo='upsell_oow',
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        sucursal_id=sucursal_id,
        tecnico_id=tecnico_id,
        gama=gama,
    )


def obtener_vm_pura_fl(
    fecha_inicio: date | datetime | str | None = None,
    fecha_fin: date | datetime | str | None = None,
    sucursal_id: int | str | None = None,
    tecnico_id: int | str | None = None,
    gama: str | None = None,
) -> list[dict[str, Any]]:
    """
    VM pura FL: órdenes tipo venta_mostrador (sin diagnóstico) finalizadas.

    Returns:
        Filas con desglose de servicios de mostrador puro.
    """
    return _filas_vm_por_tipo_servicio(
        tipo_servicio='venta_mostrador',
        tipo_flujo='vm_pura_fl',
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        sucursal_id=sucursal_id,
        tecnico_id=tecnico_id,
        gama=gama,
    )


def obtener_diagnosticos_realizados(
    fecha_inicio: date | datetime | str | None = None,
    fecha_fin: date | datetime | str | None = None,
    sucursal_id: int | str | None = None,
    tecnico_id: int | str | None = None,
    gama: str | None = None,
) -> list[dict[str, Any]]:
    """
    Diagnósticos SIC no vacíos atribuidos al técnico asignado actual.

    Fecha: fecha_fin_diagnostico en rango; si es null, fallback a fecha_ingreso.
    """
    qs = OrdenServicio.objects.filter(
        detalle_equipo__isnull=False,
    ).exclude(
        detalle_equipo__diagnostico_sic__isnull=True,
    ).exclude(
        detalle_equipo__diagnostico_sic='',
    ).select_related(
        'sucursal',
        'tecnico_asignado_actual',
        'detalle_equipo',
    )

    qs = _aplicar_filtros_comunes(
        qs,
        sucursal_id=sucursal_id,
        tecnico_id=tecnico_id,
        gama=gama,
    )

    d_inicio = _fecha_a_date(fecha_inicio)
    d_fin = _fecha_a_date(fecha_fin)
    inicio_dt = _normalizar_fecha_inicio(fecha_inicio)
    fin_dt = _normalizar_fecha_fin(fecha_fin)

    cond_con_fecha = Q(detalle_equipo__fecha_fin_diagnostico__isnull=False)
    cond_sin_fecha = Q(detalle_equipo__fecha_fin_diagnostico__isnull=True)

    if d_inicio is not None:
        cond_con_fecha &= Q(detalle_equipo__fecha_fin_diagnostico__gte=d_inicio)
    if d_fin is not None:
        cond_con_fecha &= Q(detalle_equipo__fecha_fin_diagnostico__lte=d_fin)
    if inicio_dt is not None:
        cond_sin_fecha &= Q(fecha_ingreso__gte=inicio_dt)
    if fin_dt is not None:
        cond_sin_fecha &= Q(fecha_ingreso__lte=fin_dt)

    if d_inicio is not None or d_fin is not None or inicio_dt is not None or fin_dt is not None:
        qs = qs.filter(cond_con_fecha | cond_sin_fecha)

    qs = qs.order_by(
        'tecnico_asignado_actual__nombre_completo',
        'fecha_ingreso',
    )

    filas: list[dict[str, Any]] = []
    for orden in qs:
        detalle = orden.detalle_equipo
        texto = (detalle.diagnostico_sic or '').strip()
        if not texto:
            continue

        fecha_diag: date | datetime | None = detalle.fecha_fin_diagnostico
        if fecha_diag is None:
            fecha_diag = orden.fecha_ingreso

        tecnico = orden.tecnico_asignado_actual
        extracto = texto if len(texto) <= 200 else texto[:197] + '...'
        orden_cliente, service_tag = _datos_cliente_equipo(orden)
        filas.append({
            'orden_id': orden.pk,
            'folio': orden_cliente,
            'service_tag': service_tag,
            'tecnico_id': tecnico.pk if tecnico else None,
            'tecnico': tecnico.nombre_completo if tecnico else 'Sin técnico',
            'sucursal': orden.sucursal.nombre if orden.sucursal else '',
            'fecha_diagnostico': fecha_diag,
            'longitud_texto': len(texto),
            'extracto': extracto,
        })
    return filas


def _contadores_vm_vacios(prefijo: str) -> dict[str, int | Decimal]:
    """Inicializa contadores de desglose VM con prefijo Upsell_ o FL_."""
    return {
        f'{prefijo}conteo': 0,
        f'{prefijo}ingreso': Decimal('0.00'),
        f'{prefijo}limpieza': 0,
        f'{prefijo}reinstalacion': 0,
        f'{prefijo}respaldo': 0,
        f'{prefijo}cambio_pieza': 0,
        f'{prefijo}kit': 0,
        f'{prefijo}paquete_premium': 0,
        f'{prefijo}paquete_oro': 0,
        f'{prefijo}paquete_plata': 0,
    }


def _acumular_desglose_vm(bucket: dict[str, Any], fila: dict[str, Any], prefijo: str) -> None:
    """Suma una fila VM al bucket del técnico con el prefijo dado."""
    bucket[f'{prefijo}conteo'] += 1
    bucket[f'{prefijo}ingreso'] += fila.get('total_vm') or Decimal('0.00')
    if fila.get('incluye_limpieza'):
        bucket[f'{prefijo}limpieza'] += 1
    if fila.get('incluye_reinstalacion'):
        bucket[f'{prefijo}reinstalacion'] += 1
    if fila.get('incluye_respaldo'):
        bucket[f'{prefijo}respaldo'] += 1
    if fila.get('incluye_cambio_pieza'):
        bucket[f'{prefijo}cambio_pieza'] += 1
    if fila.get('incluye_kit'):
        bucket[f'{prefijo}kit'] += 1
    paquete = fila.get('paquete') or 'ninguno'
    if paquete == 'premium':
        bucket[f'{prefijo}paquete_premium'] += 1
    elif paquete == 'oro':
        bucket[f'{prefijo}paquete_oro'] += 1
    elif paquete == 'plata':
        bucket[f'{prefijo}paquete_plata'] += 1


def agregar_resumen_por_tecnico(
    reparaciones: list[dict[str, Any]],
    upsell_oow: list[dict[str, Any]],
    vm_pura_fl: list[dict[str, Any]],
    diagnosticos: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Une las cuatro métricas en una fila por técnico (conteos OOW / FL separados).

    Args:
        reparaciones: OOW con cot aceptada.
        upsell_oow: VM sobre órdenes diagnóstico.
        vm_pura_fl: VM sobre órdenes venta_mostrador.
        diagnosticos: diagnósticos SIC.

    Returns:
        Lista ordenada por nombre de técnico.
    """
    por_tecnico: dict[Any, dict[str, Any]] = {}

    def _bucket(tecnico_id: Any, tecnico: str, sucursal: str) -> dict[str, Any]:
        clave = tecnico_id if tecnico_id is not None else f'nombre:{tecnico}'
        if clave not in por_tecnico:
            base: dict[str, Any] = {
                'tecnico_id': tecnico_id,
                'tecnico': tecnico,
                'sucursales': set(),
                'reparaciones_oow': 0,
                'diagnosticos': 0,
                'valor_cot_aceptada': Decimal('0.00'),
            }
            base.update(_contadores_vm_vacios('upsell_'))
            base.update(_contadores_vm_vacios('fl_'))
            por_tecnico[clave] = base
        if sucursal:
            por_tecnico[clave]['sucursales'].add(sucursal)
        return por_tecnico[clave]

    for fila in reparaciones:
        b = _bucket(fila['tecnico_id'], fila['tecnico'], fila.get('sucursal', ''))
        b['reparaciones_oow'] += 1
        b['valor_cot_aceptada'] += fila.get('valor_cot_aceptada') or Decimal('0.00')

    for fila in upsell_oow:
        b = _bucket(fila['tecnico_id'], fila['tecnico'], fila.get('sucursal', ''))
        _acumular_desglose_vm(b, fila, 'upsell_')

    for fila in vm_pura_fl:
        b = _bucket(fila['tecnico_id'], fila['tecnico'], fila.get('sucursal', ''))
        _acumular_desglose_vm(b, fila, 'fl_')

    for fila in diagnosticos:
        b = _bucket(fila['tecnico_id'], fila['tecnico'], fila.get('sucursal', ''))
        b['diagnosticos'] += 1

    resultado: list[dict[str, Any]] = []
    for b in por_tecnico.values():
        sucursales = sorted(b['sucursales'])
        fila_out = {k: v for k, v in b.items() if k != 'sucursales'}
        fila_out['sucursales'] = ', '.join(sucursales)
        resultado.append(fila_out)

    resultado.sort(key=lambda x: x['tecnico'].lower())
    return resultado


def _estilos_excel() -> dict[str, Any]:
    """Estilos reutilizables al estilo del export de aceptaciones."""
    return {
        'header_font': Font(bold=True, color='FFFFFF', size=11),
        'header_fill': PatternFill(start_color='198754', end_color='198754', fill_type='solid'),
        'header_align': Alignment(horizontal='center', vertical='center', wrap_text=True),
        'title_font': Font(bold=True, size=14, color='FFFFFF'),
        'title_fill': PatternFill(start_color='212529', end_color='212529', fill_type='solid'),
        'title_align': Alignment(horizontal='center', vertical='center'),
        'subtitle_font': Font(italic=True, size=10, color='666666'),
        'border': Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin'),
        ),
        'number_fmt': '#,##0.00',
    }


def _aplicar_header(ws, fila: int, headers: list[str], estilos: dict[str, Any]) -> None:
    """Escribe y estiliza la fila de encabezados."""
    for col, texto in enumerate(headers, 1):
        cell = ws.cell(row=fila, column=col, value=texto)
        cell.font = estilos['header_font']
        cell.fill = estilos['header_fill']
        cell.alignment = estilos['header_align']
        cell.border = estilos['border']


def _auto_ajustar(ws, max_width: int = 45) -> None:
    """Ajusta anchos de columna según contenido."""
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value is not None:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = min(max_len + 3, max_width)


def _fmt_fecha(valor: date | datetime | None) -> str:
    """Formato legible para celdas de fecha."""
    if valor is None:
        return ''
    if isinstance(valor, datetime):
        if timezone.is_aware(valor):
            return timezone.localtime(valor).strftime('%d/%m/%Y %H:%M')
        return valor.strftime('%d/%m/%Y %H:%M')
    return valor.strftime('%d/%m/%Y')


def _si_no(valor: bool) -> str:
    """Booleano a Sí/No en español."""
    return 'Sí' if valor else 'No'


def _escribir_hoja_detalle_vm(
    wb: Workbook,
    nombre_hoja: str,
    titulo: str,
    filas_vm: list[dict[str, Any]],
    filtros_texto: str,
    estilos: dict[str, Any],
) -> None:
    """
    Escribe una hoja de detalle VM (upsell OOW o VM pura FL).

    Args:
        wb: Workbook destino.
        nombre_hoja / titulo: identificación de la hoja.
        filas_vm: datos ya filtrados por tipo de flujo.
        filtros_texto / estilos: cabecera común.
    """
    ws = wb.create_sheet(nombre_hoja)
    ws.merge_cells('A1:P1')
    ws['A1'] = titulo
    ws['A1'].font = estilos['title_font']
    ws['A1'].fill = estilos['title_fill']
    ws['A1'].alignment = estilos['title_align']
    ws.merge_cells('A2:P2')
    ws['A2'] = filtros_texto
    ws['A2'].font = estilos['subtitle_font']

    headers = [
        'Orden cliente',
        'Service Tag',
        'Folio VM',
        'Técnico',
        'Paquete',
        'Costo paquete',
        'Limpieza',
        'Costo limpieza',
        'Reinstalación SO',
        'Costo reinstalación',
        'Respaldo',
        'Costo respaldo',
        'Cambio pieza',
        'Kit limpieza',
        'Piezas',
        'Total VM',
    ]
    _aplicar_header(ws, 4, headers, estilos)
    fila = 5
    for row in filas_vm:
        vals = [
            row['folio'],
            row['service_tag'],
            row['folio_vm'],
            row['tecnico'],
            row['paquete_nombre'],
            float(row['costo_paquete']),
            _si_no(row['incluye_limpieza']),
            float(row['costo_limpieza']),
            _si_no(row['incluye_reinstalacion']),
            float(row['costo_reinstalacion']),
            _si_no(row['incluye_respaldo']),
            float(row['costo_respaldo']),
            _si_no(row['incluye_cambio_pieza']),
            _si_no(row['incluye_kit']),
            row['resumen_piezas'],
            float(row['total_vm']),
        ]
        for col, val in enumerate(vals, 1):
            cell = ws.cell(row=fila, column=col, value=val)
            cell.border = estilos['border']
            if col in (6, 8, 10, 12, 16):
                cell.number_format = estilos['number_fmt']
        fila += 1
    _auto_ajustar(ws)


def generar_workbook_productividad_tecnicos(
    fecha_inicio: date | datetime | str | None = None,
    fecha_fin: date | datetime | str | None = None,
    sucursal_id: int | str | None = None,
    tecnico_id: int | str | None = None,
    gama: str | None = None,
) -> Workbook | None:
    """
    Arma el Excel de productividad con 5 hojas (OOW / upsell / FL / diagnósticos).

    Returns:
        Workbook openpyxl, o None si no hay ninguna fila en las métricas.
    """
    filtros = {
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'sucursal_id': sucursal_id,
        'tecnico_id': tecnico_id,
        'gama': gama,
    }

    reparaciones = obtener_reparaciones_productivas(**filtros)
    upsell_oow = obtener_upsell_oow(**filtros)
    vm_pura_fl = obtener_vm_pura_fl(**filtros)
    diagnosticos = obtener_diagnosticos_realizados(**filtros)

    if not reparaciones and not upsell_oow and not vm_pura_fl and not diagnosticos:
        return None

    resumen = agregar_resumen_por_tecnico(
        reparaciones, upsell_oow, vm_pura_fl, diagnosticos,
    )
    estilos = _estilos_excel()

    wb = Workbook()
    wb.remove(wb.active)

    filtros_texto = (
        f"Período: {fecha_inicio or 'Inicio'} - {fecha_fin or 'Actual'}"
    )
    if sucursal_id:
        filtros_texto += f' | Sucursal ID: {sucursal_id}'
    if tecnico_id:
        filtros_texto += f' | Técnico ID: {tecnico_id}'
    if gama:
        filtros_texto += f' | Gama: {gama}'
    generado = timezone.localtime().strftime('%d/%m/%Y %H:%M:%S')

    # ------------------------------------------------------------------
    # HOJA 1: Resumen por técnico (OOW y FL separados)
    # ------------------------------------------------------------------
    headers1 = [
        'Técnico',
        'Sucursal(es)',
        'Reparaciones OOW',
        'Upsell OOW',
        'VM pura FL',
        'Diagnósticos',
        'Valor cot OOW',
        'Ingreso upsell OOW',
        'Ingreso VM FL',
        'Upsell limpieza',
        'Upsell reinst. SO',
        'Upsell respaldo',
        'Upsell cambio pieza',
        'Upsell kit',
        'Upsell Prem.',
        'Upsell Oro',
        'Upsell Plata',
        'FL limpieza',
        'FL reinst. SO',
        'FL respaldo',
        'FL cambio pieza',
        'FL kit',
        'FL Prem.',
        'FL Oro',
        'FL Plata',
    ]
    num_cols = len(headers1)
    ultima = get_column_letter(num_cols)

    ws1 = wb.create_sheet(HOJAS_EXCEL[0])
    ws1.merge_cells(f'A1:{ultima}1')
    ws1['A1'] = 'PRODUCTIVIDAD TÉCNICOS — RESUMEN (OOW vs FL)'
    ws1['A1'].font = estilos['title_font']
    ws1['A1'].fill = estilos['title_fill']
    ws1['A1'].alignment = estilos['title_align']
    ws1.merge_cells(f'A2:{ultima}2')
    ws1['A2'] = filtros_texto
    ws1['A2'].font = estilos['subtitle_font']
    ws1['A2'].alignment = Alignment(horizontal='center')
    ws1.merge_cells(f'A3:{ultima}3')
    ws1['A3'] = (
        f'Generado: {generado} | '
        'OOW = diagnóstico/reparación; Upsell = VM adicional en OOW; '
        'FL = venta mostrador sin diagnóstico'
    )
    ws1['A3'].font = estilos['subtitle_font']
    ws1['A3'].alignment = Alignment(horizontal='center')

    _aplicar_header(ws1, 5, headers1, estilos)
    fila = 6
    for row in resumen:
        vals = [
            row['tecnico'],
            row['sucursales'],
            row['reparaciones_oow'],
            row['upsell_conteo'],
            row['fl_conteo'],
            row['diagnosticos'],
            float(row['valor_cot_aceptada']),
            float(row['upsell_ingreso']),
            float(row['fl_ingreso']),
            row['upsell_limpieza'],
            row['upsell_reinstalacion'],
            row['upsell_respaldo'],
            row['upsell_cambio_pieza'],
            row['upsell_kit'],
            row['upsell_paquete_premium'],
            row['upsell_paquete_oro'],
            row['upsell_paquete_plata'],
            row['fl_limpieza'],
            row['fl_reinstalacion'],
            row['fl_respaldo'],
            row['fl_cambio_pieza'],
            row['fl_kit'],
            row['fl_paquete_premium'],
            row['fl_paquete_oro'],
            row['fl_paquete_plata'],
        ]
        for col, val in enumerate(vals, 1):
            cell = ws1.cell(row=fila, column=col, value=val)
            cell.border = estilos['border']
            if col in (7, 8, 9):
                cell.number_format = estilos['number_fmt']
        fila += 1
    _auto_ajustar(ws1)

    # ------------------------------------------------------------------
    # HOJA 2: Detalle reparaciones OOW
    # ------------------------------------------------------------------
    ws2 = wb.create_sheet(HOJAS_EXCEL[1])
    ws2.merge_cells('A1:J1')
    ws2['A1'] = 'DETALLE REPARACIONES OOW (diagnóstico + cot aceptada)'
    ws2['A1'].font = estilos['title_font']
    ws2['A1'].fill = estilos['title_fill']
    ws2['A1'].alignment = estilos['title_align']
    ws2.merge_cells('A2:J2')
    ws2['A2'] = filtros_texto
    ws2['A2'].font = estilos['subtitle_font']

    headers2 = [
        'Orden cliente',
        'Service Tag',
        'Técnico',
        'Sucursal',
        'Estado',
        'Fecha finalización',
        '¿Cot aceptada?',
        '¿Tiene upsell VM?',
        'Valor aceptado cot',
        'Folio VM',
    ]
    _aplicar_header(ws2, 4, headers2, estilos)
    fila = 5
    for row in reparaciones:
        vals = [
            row['folio'],
            row['service_tag'],
            row['tecnico'],
            row['sucursal'],
            row['estado'],
            _fmt_fecha(row['fecha_finalizacion']),
            _si_no(row['cot_aceptada']),
            _si_no(row['tiene_upsell_vm']),
            float(row['valor_cot_aceptada']),
            row['folio_vm'],
        ]
        for col, val in enumerate(vals, 1):
            cell = ws2.cell(row=fila, column=col, value=val)
            cell.border = estilos['border']
            if col == 9:
                cell.number_format = estilos['number_fmt']
        fila += 1
    _auto_ajustar(ws2)

    # ------------------------------------------------------------------
    # HOJAS 3 y 4: Upsell OOW / VM pura FL
    # ------------------------------------------------------------------
    _escribir_hoja_detalle_vm(
        wb,
        HOJAS_EXCEL[2],
        'DETALLE UPSELL OOW (adicionales sobre diagnóstico)',
        upsell_oow,
        filtros_texto,
        estilos,
    )
    _escribir_hoja_detalle_vm(
        wb,
        HOJAS_EXCEL[3],
        'DETALLE VM PURA FL (sin diagnóstico)',
        vm_pura_fl,
        filtros_texto,
        estilos,
    )

    # ------------------------------------------------------------------
    # HOJA 5: Detalle diagnósticos
    # ------------------------------------------------------------------
    ws5 = wb.create_sheet(HOJAS_EXCEL[4])
    ws5.merge_cells('A1:G1')
    ws5['A1'] = 'DETALLE DIAGNÓSTICOS'
    ws5['A1'].font = estilos['title_font']
    ws5['A1'].fill = estilos['title_fill']
    ws5['A1'].alignment = estilos['title_align']
    ws5.merge_cells('A2:G2')
    ws5['A2'] = (
        f'{filtros_texto} | Fecha: fin diagnóstico o, si falta, fecha de ingreso'
    )
    ws5['A2'].font = estilos['subtitle_font']

    headers5 = [
        'Orden cliente',
        'Service Tag',
        'Técnico',
        'Sucursal',
        'Fecha diagnóstico',
        'Longitud texto',
        'Extracto diagnóstico',
    ]
    _aplicar_header(ws5, 4, headers5, estilos)
    fila = 5
    for row in diagnosticos:
        vals = [
            row['folio'],
            row['service_tag'],
            row['tecnico'],
            row['sucursal'],
            _fmt_fecha(row['fecha_diagnostico']),
            row['longitud_texto'],
            row['extracto'],
        ]
        for col, val in enumerate(vals, 1):
            cell = ws5.cell(row=fila, column=col, value=val)
            cell.border = estilos['border']
        fila += 1
    _auto_ajustar(ws5)

    return wb
