"""
Vistas HTTP de consulta e importación SICSER (Fase 1 lectura + Fase 2 import).

EXPLICACIÓN PARA PRINCIPIANTES:
Estas vistas vivían al final de views.py. Las movimos aquí porque ya dependen
de sicser_client / sicser_import y no tocan detalle_orden ni el resto del monolito.

urls.py sigue usando views.consultar_sicser porque views.py reexporta estos nombres.
"""

import logging
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .decorators import permission_required_with_message

logger = logging.getLogger(__name__)


@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def consultar_sicser(request):
    """
    Pantalla de consulta en tiempo real de órdenes SICSER (OOW y garantía Dell).

    Fase 1: listar y abrir formato digital en SICSER.
    Fase 2: importar registros como órdenes nuevas en SIGMA (botón por fila).
    UI: badges de «nuevas» en pestañas + pestaña Importadas (histórico local).

    Parámetros GET:
        tab (str): 'oow', 'garantia' o 'importadas' — pestaña activa.
        q (str): Texto de búsqueda (folio, service tag, cliente, DPS).
        refrescar (str): Si es '1', omite caché y vuelve a consultar SICSER.

    Efectos secundarios:
        Solo lectura remota (API SICSER) + consultas locales de importaciones;
        no crea órdenes por sí sola (eso lo hace importar_orden_sicser).
    """
    from config.paises_config import get_pais_actual
    from inventario.models import Sucursal
    from .sicser_client import (
        SicserAPIError,
        fetch_listado_garantias,
        fetch_listado_oow,
    )
    from .sicser_import import (
        contar_ordenes_importadas_sicser,
        listar_ordenes_importadas_sicser,
        mapa_importaciones_sicser,
    )

    pais = get_pais_actual()
    codigo_pais = pais.get('codigo', 'MX')
    tab = request.GET.get('tab', 'oow').strip().lower()
    if tab not in ('oow', 'garantia', 'importadas'):
        tab = 'oow'

    texto_busqueda = request.GET.get('q', '').strip()
    usar_cache = request.GET.get('refrescar') != '1'

    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Pedimos AMBAS APIs sin filtro de búsqueda para calcular badges de «N nuevas».
    # La búsqueda `q` se aplica después solo a la pestaña activa.
    ordenes_oow_todas = []
    ordenes_garantia_todas = []
    total_oow_pais = 0
    total_garantia_pais = 0
    error_oow = ''
    error_garantia = ''
    api_oow_ok = False
    api_garantia_ok = False

    try:
        ordenes_oow_todas, total_oow_pais = fetch_listado_oow(
            codigo_pais=codigo_pais,
            texto_busqueda='',
            usar_cache=usar_cache,
        )
        api_oow_ok = True
    except SicserAPIError as exc:
        error_oow = str(exc)
        logger.warning('Error consultando API OOW SICSER: %s', exc)

    try:
        ordenes_garantia_todas, total_garantia_pais = fetch_listado_garantias(
            codigo_pais=codigo_pais,
            texto_busqueda='',
            usar_cache=usar_cache,
        )
        api_garantia_ok = True
    except SicserAPIError as exc:
        error_garantia = str(exc)
        logger.warning('Error consultando API Garantías SICSER: %s', exc)

    mapa_oow, mapa_garantia = mapa_importaciones_sicser()
    sucursales = Sucursal.objects.filter(activa=True).order_by('nombre')
    puede_importar = request.user.has_perm('servicio_tecnico.add_ordenservicio')

    # Badges: pendientes = en SICSER y aún no importadas a SIGMA.
    nuevas_oow = (
        sum(1 for o in ordenes_oow_todas if str(o.id_orden) not in mapa_oow)
        if api_oow_ok else 0
    )
    nuevas_garantia = (
        sum(1 for o in ordenes_garantia_todas if str(o.numero_dps) not in mapa_garantia)
        if api_garantia_ok else 0
    )

    # Aplicar búsqueda solo a la pestaña activa (reutiliza el filtro del cliente).
    if tab == 'oow' and texto_busqueda and api_oow_ok:
        ordenes_oow, _ = fetch_listado_oow(
            codigo_pais=codigo_pais,
            texto_busqueda=texto_busqueda,
            usar_cache=True,
        )
    else:
        ordenes_oow = ordenes_oow_todas if tab == 'oow' else []

    if tab == 'garantia' and texto_busqueda and api_garantia_ok:
        ordenes_garantia, _ = fetch_listado_garantias(
            codigo_pais=codigo_pais,
            texto_busqueda=texto_busqueda,
            usar_cache=True,
        )
    else:
        ordenes_garantia = ordenes_garantia_todas if tab == 'garantia' else []

    filas_oow = [
        {
            'registro': orden,
            'sigma': mapa_oow.get(str(orden.id_orden)),
        }
        for orden in ordenes_oow
    ]
    filas_garantia = [
        {
            'registro': orden,
            'sigma': mapa_garantia.get(str(orden.numero_dps)),
        }
        for orden in ordenes_garantia
    ]

    total_importadas = contar_ordenes_importadas_sicser()
    filas_importadas = []
    if tab == 'importadas':
        filas_importadas = listar_ordenes_importadas_sicser(
            texto_busqueda=texto_busqueda,
            limite=100,
        )

    context = {
        'page_title': 'Consultar SICSER',
        'tab_activa': tab,
        'texto_busqueda': texto_busqueda,
        'pais_nombre': pais.get('nombre', ''),
        'codigo_pais': codigo_pais,
        'filas_oow': filas_oow,
        'filas_garantia': filas_garantia,
        'filas_importadas': filas_importadas,
        'total_oow_pais': total_oow_pais,
        'total_garantia_pais': total_garantia_pais,
        'total_oow_mostrado': len(filas_oow),
        'total_garantia_mostrado': len(filas_garantia),
        'nuevas_oow': nuevas_oow,
        'nuevas_garantia': nuevas_garantia,
        'total_importadas': total_importadas,
        'api_oow_ok': api_oow_ok,
        'api_garantia_ok': api_garantia_ok,
        'error_oow': error_oow,
        'error_garantia': error_garantia,
        'refresco_forzado': not usar_cache,
        'sucursales': sucursales,
        'puede_importar': puede_importar,
    }

    return render(request, 'servicio_tecnico/consultar_sicser.html', context)


@login_required
@permission_required_with_message('servicio_tecnico.add_ordenservicio')
@require_http_methods(['POST'])
def importar_orden_sicser(request):
    """
    Importa un registro de SICSER como orden nueva en SIGMA.

    Parámetros POST:
        tipo (str): 'oow' o 'garantia'.
        id_externo (str): id_orden (OOW) o numero_dps (garantía).
        sucursal_id (str, opcional): Sucursal SIGMA a asignar.
        tab (str): Pestaña para redirigir tras importar.
        q (str): Filtro de búsqueda a preservar en la redirección.

    Efectos secundarios:
        Crea OrdenServicio + DetalleEquipo en la base de datos del país activo.
    """
    from config.paises_config import get_pais_actual
    from .sicser_client import (
        SicserAPIError,
        buscar_registro_garantia_por_dps,
        buscar_registro_oow_por_id,
    )
    from .sicser_import import (
        SicserImportError,
        importar_orden_garantia_desde_sicser,
        importar_orden_oow_desde_sicser,
    )

    tipo = request.POST.get('tipo', '').strip().lower()
    id_externo = request.POST.get('id_externo', '').strip()
    tab = request.POST.get('tab', 'oow').strip().lower() or 'oow'
    texto_busqueda = request.POST.get('q', '').strip()
    sucursal_id_raw = request.POST.get('sucursal_id', '').strip()

    sucursal_id = int(sucursal_id_raw) if sucursal_id_raw.isdigit() else None
    codigo_pais = get_pais_actual().get('codigo', 'MX')

    redirect_url = 'servicio_tecnico:consultar_sicser'
    query_parts = [f'tab={tab}']
    if texto_busqueda:
        query_parts.append(f'q={quote(texto_busqueda)}')
    redirect_suffix = '?' + '&'.join(query_parts)

    if tipo not in ('oow', 'garantia') or not id_externo:
        messages.error(request, 'Datos de importación SICSER incompletos o inválidos.')
        return redirect(redirect_url + redirect_suffix)

    try:
        if tipo == 'oow':
            registro = buscar_registro_oow_por_id(int(id_externo), codigo_pais)
            if not registro:
                raise SicserImportError(
                    'No se encontró la orden OOW en SICSER. Actualice el listado e intente de nuevo.'
                )
            resultado = importar_orden_oow_desde_sicser(
                registro,
                request.user,
                sucursal_id=sucursal_id,
            )
        else:
            registro = buscar_registro_garantia_por_dps(int(id_externo), codigo_pais)
            if not registro:
                raise SicserImportError(
                    'No se encontró la garantía en SICSER. Actualice el listado e intente de nuevo.'
                )
            resultado = importar_orden_garantia_desde_sicser(
                registro,
                request.user,
                sucursal_id=sucursal_id,
            )

        messages.success(request, resultado.mensaje)
        return redirect('servicio_tecnico:detalle_orden', orden_id=resultado.orden.pk)

    except (SicserImportError, SicserAPIError, ValueError) as exc:
        messages.error(request, f'No se pudo importar desde SICSER: {exc}')
        return redirect(redirect_url + redirect_suffix)
