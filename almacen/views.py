"""
Vistas para el módulo Almacén - Sistema de Inventario de Almacén Central

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
Este archivo contiene las vistas (views) que procesan las solicitudes HTTP.
Cada vista:
1. Recibe una solicitud (request) del navegador
2. Procesa los datos (consulta BD, valida formularios)
3. Retorna una respuesta (HTML renderizado)

Patrones utilizados:
- Vistas basadas en funciones (function-based views)
- Decoradores para control de acceso (@login_required)
- Mensajes flash (messages) para feedback al usuario
- Paginación para listas largas

Organización (modularización en curso):
- Este archivo: compras, cotizaciones residuales + reexports
- decorators.py: permission_required_with_message
- views_dashboard_distribucion.py: distribución multi-sucursal + Excel
- views_parametros_cotizador.py: panel de márgenes del cotizador
- views_catalogo.py: dashboard, productos, proveedores, categorías, bajas, APIs producto
- views_unidades.py: UnidadesInventario + APIs + buscar/crear orden

urls.py sigue importando from . import views; los nombres extraídos
se reexportan al inicio de este módulo (Fase 0 + Fase 1 + Fase 2).
"""

from collections import OrderedDict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_http_methods

from inventario.models import Empleado

from .forms import (
    CompraProductoForm,
    DevolucionCompraForm,
    ImagenLineaCotizacionForm,
    LineaCotizacionFormSet,
    LineaCotizacionFormSetCreacion,
    LineaServicioAdicionalForm,
    ProblemaCompraForm,
    RecepcionCompraForm,
    RechazoCotizacionForm,
    RespuestaLineaCotizacionForm,
    SolicitudCotizacionFiltroForm,
    SolicitudCotizacionForm,
    UnidadCompraFormSet,
)
from .models import (
    CompraProducto,
    ImagenLineaCotizacion,
    ImagenSolicitudCotizacion,
    LineaCotizacion,
    LineaServicioAdicional,
    MovimientoAlmacen,
    ProductoAlmacen,
    Proveedor,
    SolicitudCotizacion,
    UnidadCompra,
    UnidadInventario,
)

import logging

logger = logging.getLogger('almacen')



# ============================================================================
# REEXPORTS (modularización Fase 0 + Fase 1 + Fase 2)
# ============================================================================
# EXPLICACIÓN PARA PRINCIPIANTES:
# El decorador y las vistas autónomas viven en módulos hermanos.
# Los reexportamos aquí para que urls.py (views.foo) e imports antiguos
# (from almacen.views import ...) sigan funcionando sin cambios.
from .decorators import permission_required_with_message  # noqa: F401
from .views_dashboard_distribucion import (  # noqa: F401
    dashboard_distribucion_sucursales,
    exportar_distribucion_excel,
)
from .views_parametros_cotizador import (  # noqa: F401
    panel_parametros_cotizador,
)
from .views_catalogo import (  # noqa: F401
    acceso_denegado,
    api_buscar_productos,
    api_info_producto,
    crear_categoria,
    crear_producto,
    crear_proveedor,
    crear_solicitud,
    dashboard_almacen,
    detalle_producto,
    editar_categoria,
    editar_producto,
    editar_proveedor,
    eliminar_proveedor,
    lista_categorias,
    lista_movimientos,
    lista_productos,
    lista_proveedores,
    lista_solicitudes,
    procesar_solicitud,
)
from .views_unidades import (  # noqa: F401
    api_buscar_crear_orden_cliente,
    api_tecnicos_disponibles,
    api_unidad_info,
    api_unidades_producto,
    cambiar_estado_unidad,
    crear_unidad,
    detalle_unidad,
    editar_unidad,
    eliminar_unidad,
    lista_unidades,
    unidades_por_producto,
)


# ============================================================================
# COMPRAS Y COTIZACIONES
# ============================================================================

def _clave_grupo_compra_cotizacion(compra):
    """
    Arma la clave de agrupación para compras generadas desde cotización.

    EXPLICACIÓN PARA PRINCIPIANTES:
    -------------------------------
    Varias piezas distintas de la misma orden deben verse juntas en la lista.
    Prioridad de agrupación:
    1) FK a OrdenServicio (lo más confiable)
    2) Texto orden_cliente (si aún no hay orden vinculada)
    3) Grupo genérico "sin orden" (stock / sin referencia)

    Args:
        compra (CompraProducto): Compra individual a clasificar.

    Returns:
        str: Clave estable usada como llave del OrderedDict de grupos.
    """
    # Paso 1: si hay orden de servicio formal, usamos su ID
    if compra.orden_servicio_id:
        return f'os:{compra.orden_servicio_id}'

    # Paso 2: fallback por número visible de orden del cliente
    orden_texto = (compra.orden_cliente or '').strip()
    if orden_texto:
        return f'oc:{orden_texto.lower()}'

    # Paso 3: compras sin ninguna referencia de orden
    return '__sin_orden__'


def _agrupar_compras_por_orden(compras):
    """
    Agrupa compras de cotización por orden, preservando el orden de llegada.

    EXPLICACIÓN PARA PRINCIPIANTES:
    -------------------------------
    Recorremos la lista ya ordenada por fecha y metemos cada compra en su
    "canasta" de orden. Así en la plantilla podemos pintar una cabecera por
    orden y debajo cada pieza con su propio enlace a detalle/recepción.

    Args:
        compras (iterable): QuerySet o lista de CompraProducto.

    Returns:
        list[dict]: Lista de grupos con label, compras y contadores de estado.
    """
    grupos = OrderedDict()

    for compra in compras:
        # Cada compra cae en exactamente un grupo según la clave calculada
        clave = _clave_grupo_compra_cotizacion(compra)

        if clave not in grupos:
            # Cabecera legible: preferimos orden_cliente; si no, el ID de OS
            if compra.orden_servicio_id:
                label = (
                    compra.orden_cliente
                    or getattr(compra.orden_servicio, 'orden_cliente', None)
                    or f'OS #{compra.orden_servicio_id}'
                )
            elif (compra.orden_cliente or '').strip():
                label = compra.orden_cliente.strip()
            else:
                label = 'Sin orden / Stock'

            grupos[clave] = {
                'clave': clave,
                'label': label,
                'orden_servicio': compra.orden_servicio,
                'orden_cliente': (compra.orden_cliente or '').strip(),
                'numeros_solicitud': [],
                'compras': [],
                'total': 0,
                'pendientes': 0,
                'recibidas': 0,
                'problema': 0,
                'retrasadas': 0,
            }

        grupo = grupos[clave]
        grupo['compras'].append(compra)
        grupo['total'] += 1

        # Contadores para el resumen visual de la cabecera del grupo
        if compra.estado == 'recibida':
            grupo['recibidas'] += 1
        elif compra.estado in ('wpb', 'doa', 'devolucion_garantia'):
            grupo['problema'] += 1
        elif compra.estado == 'pendiente_llegada':
            grupo['pendientes'] += 1

        # Retrasada = aún no llega y ya pasó la ETA (usa property del modelo)
        if compra.esta_atrasada:
            grupo['retrasadas'] += 1

        # OneToOne inverso: si la compra no vino de cotización, no existe la relación
        try:
            linea_origen = compra.linea_cotizacion_origen
        except ObjectDoesNotExist:
            linea_origen = None

        if linea_origen and linea_origen.solicitud_id:
            num = linea_origen.solicitud.numero_solicitud
            if num and num not in grupo['numeros_solicitud']:
                grupo['numeros_solicitud'].append(num)

    return list(grupos.values())


@login_required
@permission_required_with_message('almacen.view_compraproducto')
def lista_compras(request):
    """
    Lista de compras separada en pestañas: directas vs cotizaciones.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Antes todo salía en una sola tabla. Ahora:
    - Pestaña "Cotizaciones" (default): compras tipo=cotizacion, agrupadas
      por orden de servicio para ver juntas las piezas de la misma OS.
    - Pestaña "Directas": compras tipo=compra, tabla plana como antes.

    Cada CompraProducto sigue siendo independiente: puedes entrar a confirmar
    la recepción de una pieza aunque las hermanas del grupo aún no lleguen.

    Filtros GET (compartidos por ambas pestañas):
    - tab: 'cotizaciones' | 'directas'
    - estado, producto, proveedor, orden_cliente
    """
    # Pestaña activa: cotizaciones por defecto (ahí importa el agrupado)
    tab = request.GET.get('tab', 'cotizaciones').strip().lower()
    if tab not in ('cotizaciones', 'directas'):
        tab = 'cotizaciones'

    # tipo real en BD: la pestaña traduce a filtro de modelo
    tipo_bd = 'cotizacion' if tab == 'cotizaciones' else 'compra'

    # Base queryset con joins para evitar N+1 en la plantilla
    compras_qs = CompraProducto.objects.select_related(
        'producto',
        'proveedor',
        'orden_servicio',
        'registrado_por',
        'linea_cotizacion_origen__solicitud',
    ).prefetch_related('unidades_compra').filter(tipo=tipo_bd)

    # --- Filtros compartidos (excepto tipo, que ya lo fija la pestaña) ---
    estado = request.GET.get('estado', '')
    if estado:
        compras_qs = compras_qs.filter(estado=estado)

    producto_id = request.GET.get('producto', '')
    if producto_id:
        compras_qs = compras_qs.filter(producto_id=producto_id)

    proveedor_id = request.GET.get('proveedor', '')
    if proveedor_id:
        compras_qs = compras_qs.filter(proveedor_id=proveedor_id)

    orden_cliente = request.GET.get('orden_cliente', '').strip()
    if orden_cliente:
        compras_qs = compras_qs.filter(orden_cliente__icontains=orden_cliente)

    compras_qs = compras_qs.order_by('-fecha_registro')

    # Contadores de pestaña (respetan los mismos filtros, sin forzar tipo de tab)
    filtros_comunes = Q()
    if estado:
        filtros_comunes &= Q(estado=estado)
    if producto_id:
        filtros_comunes &= Q(producto_id=producto_id)
    if proveedor_id:
        filtros_comunes &= Q(proveedor_id=proveedor_id)
    if orden_cliente:
        filtros_comunes &= Q(orden_cliente__icontains=orden_cliente)

    conteo_base = CompraProducto.objects.filter(filtros_comunes)
    total_cotizaciones = conteo_base.filter(tipo='cotizacion').count()
    total_directas = conteo_base.filter(tipo='compra').count()

    page = request.GET.get('page', 1)
    grupos_page = None
    compras_page = None

    if tab == 'cotizaciones':
        # Agrupamos TODAS las compras filtradas y paginamos por grupos de orden
        # (así un grupo no se parte entre dos páginas).
        grupos = _agrupar_compras_por_orden(compras_qs)
        paginator = Paginator(grupos, 15)
        grupos_page = paginator.get_page(page)
    else:
        # Directas: tabla plana, una fila por compra (comportamiento clásico)
        paginator = Paginator(compras_qs, 25)
        compras_page = paginator.get_page(page)

    # Datos para los selects de filtros
    productos = ProductoAlmacen.objects.filter(activo=True).order_by('nombre')
    proveedores = Proveedor.objects.filter(activo=True).order_by('nombre')

    context = {
        'tab': tab,
        'compras': compras_page,
        'grupos': grupos_page,
        'productos': productos,
        'proveedores': proveedores,
        'estado_filtro': estado,
        'producto_filtro': producto_id,
        'proveedor_filtro': proveedor_id,
        'orden_cliente_filtro': orden_cliente,
        'total_cotizaciones': total_cotizaciones,
        'total_directas': total_directas,
    }

    return render(request, 'almacen/compras/lista_compras.html', context)


@login_required
@permission_required_with_message('almacen.view_solicitudcotizacion')
def panel_cotizaciones(request):
    """
    Panel de cotizaciones pendientes de aprobación.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista muestra un dashboard específico para las cotizaciones
    que están esperando respuesta del cliente.
    
    IMPORTANTE - NUEVO SISTEMA DE COTIZACIONES:
    Ahora las cotizaciones se manejan con el modelo SolicitudCotizacion,
    que permite múltiples proveedores por cotización.
    
    Estados del nuevo sistema:
    - borrador: En preparación
    - enviada_front: Enviada a recepción para revisión
    - enviada_cliente: Enviada al cliente, esperando respuesta
    - parcialmente_aprobada: Algunas líneas aprobadas
    - totalmente_aprobada: Todas las líneas aprobadas
    - totalmente_rechazada: Todas las líneas rechazadas
    - completada: Proceso finalizado
    
    Incluye:
    - Cotizaciones en diferentes estados
    - Alertas de cotizaciones con muchos días sin respuesta
    - Estadísticas de aprobación/rechazo
    """
    from datetime import timedelta
    from django.db.models import Count, Q
    
    # Cotizaciones pendientes de respuesta del cliente
    # Incluye enviada_front (en revisión por recepción) y enviada_cliente (con el cliente)
    cotizaciones_pendientes = SolicitudCotizacion.objects.filter(
        estado__in=['enviada_front', 'enviada_cliente']
    ).select_related(
        'orden_servicio', 'creado_por'
    ).prefetch_related('lineas').order_by('-fecha_creacion')
    
    # Cotizaciones en borrador (aún no enviadas)
    cotizaciones_borrador = SolicitudCotizacion.objects.filter(
        estado='borrador'
    ).count()
    
    # Alertas: cotizaciones con más de 3 días sin respuesta
    fecha_limite = timezone.now() - timedelta(days=3)
    cotizaciones_urgentes = cotizaciones_pendientes.filter(
        fecha_creacion__lt=fecha_limite
    ).count()
    
    # Estadísticas del mes
    inicio_mes = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    cotizaciones_mes = SolicitudCotizacion.objects.filter(
        fecha_creacion__gte=inicio_mes
    )
    
    total_mes = cotizaciones_mes.count()
    aprobadas_mes = cotizaciones_mes.filter(
        estado__in=['parcialmente_aprobada', 'totalmente_aprobada', 'completada']
    ).count()
    rechazadas_mes = cotizaciones_mes.filter(estado='totalmente_rechazada').count()
    
    tasa_aprobacion = (aprobadas_mes / total_mes * 100) if total_mes > 0 else 0
    
    context = {
        'cotizaciones': cotizaciones_pendientes,
        'cotizaciones_urgentes': cotizaciones_urgentes,
        'cotizaciones_borrador': cotizaciones_borrador,
        'total_pendientes': cotizaciones_pendientes.count(),
        'estadisticas': {
            'total_mes': total_mes,
            'aprobadas_mes': aprobadas_mes,
            'rechazadas_mes': rechazadas_mes,
            'tasa_aprobacion': round(tasa_aprobacion, 1),
        }
    }
    
    return render(request, 'almacen/cotizaciones/panel_cotizaciones.html', context)


@login_required
@permission_required_with_message('almacen.add_compraproducto')
def crear_compra(request):
    """
    Crear nueva COMPRA DIRECTA con unidades individuales.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista maneja un formulario con "formset", que es una técnica
    de Django para manejar múltiples formularios relacionados.
    
    IMPORTANTE - SISTEMA DE COTIZACIONES:
    Las cotizaciones ahora se manejan en un sistema separado (SolicitudCotizacion)
    que permite múltiples proveedores por cotización. Esta vista es 
    EXCLUSIVAMENTE para compras directas.
    
    Estructura:
    - Formulario principal: CompraProductoForm (producto, cantidad, etc.)
    - Formset: UnidadCompraFormSet (detalles de cada pieza individual)
    
    Cuando el usuario guarda:
    1. Se valida el formulario principal
    2. Se validan todas las unidades del formset
    3. Se guarda la compra (tipo='compra' automáticamente)
    4. Se guardan las unidades vinculadas a la compra
    """
    if request.method == 'POST':
        form = CompraProductoForm(request.POST)
        formset = UnidadCompraFormSet(request.POST, prefix='unidades')
        
        if form.is_valid():
            # Guardar compra sin commit para agregar campos adicionales
            compra = form.save(commit=False)
            compra.registrado_por = request.user
            
            # SIEMPRE es compra directa (cotizaciones usan SolicitudCotizacion)
            compra.tipo = 'compra'
            compra.estado = 'pendiente_llegada'
            
            # Costo unitario inicial en 0 (se calculará después)
            compra.costo_unitario = 0
            
            compra.save()
            
            # Ahora procesar el formset de unidades
            formset = UnidadCompraFormSet(request.POST, prefix='unidades', instance=compra)
            
            if formset.is_valid():
                # VALIDACIÓN 1: Verificar que haya al menos una unidad
                unidades_validas = [
                    f for f in formset 
                    if f.cleaned_data and not f.cleaned_data.get('DELETE', False)
                ]
                
                if not unidades_validas:
                    compra.delete()
                    messages.error(
                        request,
                        'Error: Debes especificar al menos una línea de detalle con marca y costo.'
                    )
                    form = CompraProductoForm(request.POST)
                    formset = UnidadCompraFormSet(request.POST, prefix='unidades')
                    context = {
                        'form': form,
                        'formset': formset,
                        'titulo': 'Nueva Compra Directa',
                        'es_creacion': True,
                    }
                    return render(request, 'almacen/compras/form_compra.html', context)
                
                # VALIDACIÓN 2: Verificar que la suma de cantidades = cantidad total
                suma_cantidades = sum(
                    f.cleaned_data.get('cantidad', 0) for f in unidades_validas
                )
                
                if suma_cantidades != compra.cantidad:
                    compra.delete()
                    messages.error(
                        request,
                        f'Error: La suma de cantidades ({suma_cantidades}) '
                        f'no coincide con la cantidad total ({compra.cantidad}). '
                        f'Ajusta las cantidades para que sumen exactamente {compra.cantidad}.'
                    )
                    form = CompraProductoForm(request.POST)
                    formset = UnidadCompraFormSet(request.POST, prefix='unidades')
                    context = {
                        'form': form,
                        'formset': formset,
                        'titulo': 'Nueva Compra Directa',
                        'es_creacion': True,
                    }
                    return render(request, 'almacen/compras/form_compra.html', context)
                
                # VALIDACIÓN 3: Verificar que todas las unidades tengan marca y costo
                for i, unidad_form in enumerate(unidades_validas, start=1):
                    marca = unidad_form.cleaned_data.get('marca')
                    costo = unidad_form.cleaned_data.get('costo_unitario')
                    
                    if not marca:
                        compra.delete()
                        messages.error(
                            request,
                            f'Error en línea {i}: La marca es obligatoria.'
                        )
                        form = CompraProductoForm(request.POST)
                        formset = UnidadCompraFormSet(request.POST, prefix='unidades')
                        context = {
                            'form': form,
                            'formset': formset,
                            'titulo': 'Nueva Compra Directa',
                            'es_creacion': True,
                        }
                        return render(request, 'almacen/compras/form_compra.html', context)
                    
                    if not costo or costo <= 0:
                        compra.delete()
                        messages.error(
                            request,
                            f'Error en línea {i}: El costo unitario es obligatorio y debe ser mayor a 0.'
                        )
                        form = CompraProductoForm(request.POST)
                        formset = UnidadCompraFormSet(request.POST, prefix='unidades')
                        context = {
                            'form': form,
                            'formset': formset,
                            'titulo': 'Nueva Compra Directa',
                            'es_creacion': True,
                        }
                        return render(request, 'almacen/compras/form_compra.html', context)
                
                # Guardar las unidades
                unidades = formset.save(commit=False)
                
                # Asignar número de línea secuencial
                for i, unidad in enumerate(unidades, start=1):
                    unidad.numero_linea = i
                    unidad.save()
                
                # Eliminar las marcadas para borrar
                for obj in formset.deleted_objects:
                    obj.delete()
                
                # CALCULAR Y ACTUALIZAR COSTO PROMEDIO
                compra.actualizar_costo_desde_unidades()
                
                messages.success(
                    request,
                    f'Compra #{compra.pk} creada exitosamente para {compra.producto.nombre} '
                    f'({compra.cantidad} unidades @ ${compra.costo_unitario:.2f} promedio)'
                )
                return redirect('almacen:detalle_compra', pk=compra.pk)
            else:
                # Si el formset tiene errores, eliminar la compra creada
                compra.delete()
                messages.error(request, 'Error en los detalles de unidades. Verifica que todas las líneas tengan marca y costo.')
        else:
            messages.error(request, 'Error en el formulario. Verifica los datos.')
            formset = UnidadCompraFormSet(request.POST, prefix='unidades')
    else:
        form = CompraProductoForm(initial={
            'fecha_pedido': timezone.now().date(),
            'costo_unitario': 0,  # Se calculará automáticamente
        })
        formset = UnidadCompraFormSet(prefix='unidades')
    
    context = {
        'form': form,
        'formset': formset,
        'titulo': 'Nueva Compra Directa',
        'es_creacion': True,
    }
    
    return render(request, 'almacen/compras/form_compra.html', context)


@login_required
@permission_required_with_message('almacen.view_compraproducto')
def detalle_compra(request, pk):
    """
    Detalle de una compra o cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Muestra toda la información de una compra/cotización:
    - Datos generales (producto, cantidad, costos)
    - Estado actual y botones de acción disponibles
    - Lista de unidades individuales con sus estados
    - Historial de cambios (si aplica)
    """
    # linea_cotizacion_origen: necesario para ETA (tiempo_entrega_estimado)
    # sin disparar una query extra al leer las propiedades de llegada.
    compra = get_object_or_404(
        CompraProducto.objects.select_related(
            'producto',
            'proveedor',
            'orden_servicio',
            'registrado_por',
            'linea_cotizacion_origen',
        ).prefetch_related('unidades_compra'),
        pk=pk
    )
    
    # Obtener unidades ordenadas por número de línea
    unidades = compra.unidades_compra.all().order_by('numero_linea')
    
    # Calcular estadísticas de unidades
    total_unidades = unidades.count()
    unidades_recibidas = unidades.filter(estado='recibida').count()
    unidades_problema = unidades.filter(estado__in=['wpb', 'doa']).count()
    
    context = {
        'compra': compra,
        'unidades': unidades,
        'estadisticas_unidades': {
            'total': total_unidades,
            'recibidas': unidades_recibidas,
            'problema': unidades_problema,
            'pendientes': total_unidades - unidades_recibidas - unidades_problema,
        },
    }
    
    return render(request, 'almacen/compras/detalle_compra.html', context)


@login_required
@permission_required_with_message('almacen.change_compraproducto')
def editar_compra(request, pk):
    """
    Editar una compra o cotización existente.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Permite modificar una compra antes de que sea recibida.
    
    VALIDACIONES:
    1. La compra no debe estar en estado final (recibida, devuelta, cancelada)
    2. Debe haber al menos una línea de detalle con marca y costo
    3. La suma de cantidades debe coincidir con la cantidad total
    4. El costo promedio se recalcula automáticamente
    """
    compra = get_object_or_404(CompraProducto, pk=pk)
    
    # Validar que se puede editar
    if compra.estado in ['recibida', 'devuelta', 'cancelada']:
        messages.error(request, 'No se puede editar una compra en estado final.')
        return redirect('almacen:detalle_compra', pk=pk)
    
    if request.method == 'POST':
        form = CompraProductoForm(request.POST, instance=compra)
        formset = UnidadCompraFormSet(request.POST, prefix='unidades', instance=compra)
        
        if form.is_valid() and formset.is_valid():
            compra_actualizada = form.save(commit=False)
            
            # VALIDACIÓN 1: Verificar que haya al menos una unidad
            unidades_validas = [
                f for f in formset 
                if f.cleaned_data and not f.cleaned_data.get('DELETE', False)
            ]
            
            if not unidades_validas:
                messages.error(
                    request,
                    'Error: Debes especificar al menos una línea de detalle con marca y costo.'
                )
                context = {
                    'form': form,
                    'formset': formset,
                    'compra': compra,
                    'titulo': f'Editar Compra #{compra.pk}',
                    'es_creacion': False,
                }
                return render(request, 'almacen/compras/form_compra.html', context)
            
            # VALIDACIÓN 2: Verificar que la suma de cantidades = cantidad total
            suma_cantidades = sum(
                f.cleaned_data.get('cantidad', 0) for f in unidades_validas
            )
            
            if suma_cantidades != compra_actualizada.cantidad:
                messages.error(
                    request,
                    f'Error: La suma de cantidades ({suma_cantidades}) '
                    f'no coincide con la cantidad total ({compra_actualizada.cantidad}). '
                    f'Ajusta las cantidades para que sumen exactamente {compra_actualizada.cantidad}.'
                )
                context = {
                    'form': form,
                    'formset': formset,
                    'compra': compra,
                    'titulo': f'Editar Compra #{compra.pk}',
                    'es_creacion': False,
                }
                return render(request, 'almacen/compras/form_compra.html', context)
            
            # VALIDACIÓN 3: Verificar que todas las unidades tengan marca y costo
            for i, unidad_form in enumerate(unidades_validas, start=1):
                marca = unidad_form.cleaned_data.get('marca')
                costo = unidad_form.cleaned_data.get('costo_unitario')
                
                if not marca:
                    messages.error(request, f'Error en línea {i}: La marca es obligatoria.')
                    context = {
                        'form': form,
                        'formset': formset,
                        'compra': compra,
                        'titulo': f'Editar Compra #{compra.pk}',
                        'es_creacion': False,
                    }
                    return render(request, 'almacen/compras/form_compra.html', context)
                
                if not costo or costo <= 0:
                    messages.error(request, f'Error en línea {i}: El costo unitario es obligatorio y debe ser mayor a 0.')
                    context = {
                        'form': form,
                        'formset': formset,
                        'compra': compra,
                        'titulo': f'Editar Compra #{compra.pk}',
                        'es_creacion': False,
                    }
                    return render(request, 'almacen/compras/form_compra.html', context)
            
            # Guardar la compra
            compra_actualizada.save()
            
            # Guardar unidades
            unidades = formset.save(commit=False)
            
            # Reasignar números de línea
            for i, unidad in enumerate(unidades, start=1):
                unidad.numero_linea = i
                unidad.save()
            
            for obj in formset.deleted_objects:
                obj.delete()
            
            # RECALCULAR COSTO PROMEDIO
            compra_actualizada.actualizar_costo_desde_unidades()
            
            messages.success(
                request, 
                f'Compra actualizada exitosamente. Costo promedio: ${compra_actualizada.costo_unitario:.2f}'
            )
            return redirect('almacen:detalle_compra', pk=pk)
    else:
        form = CompraProductoForm(instance=compra)
        formset = UnidadCompraFormSet(prefix='unidades', instance=compra)
    
    context = {
        'form': form,
        'formset': formset,
        'compra': compra,
        'titulo': f'Editar Compra #{compra.pk}',
        'es_creacion': False,
    }
    
    return render(request, 'almacen/compras/form_compra.html', context)


@login_required
@permission_required_with_message('almacen.change_compraproducto')
def aprobar_cotizacion(request, pk):
    """
    Aprobar una cotización y convertirla en compra.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cuando el cliente acepta la cotización:
    1. El tipo cambia de 'cotizacion' a 'compra'
    2. El estado cambia a 'pendiente_llegada'
    3. Se registra la fecha de aprobación
    """
    compra = get_object_or_404(CompraProducto, pk=pk)
    
    if not compra.puede_aprobar():
        messages.error(request, 'Esta cotización no puede ser aprobada.')
        return redirect('almacen:detalle_compra', pk=pk)
    
    if request.method == 'POST':
        if compra.aprobar(usuario=request.user):
            messages.success(
                request,
                f'Cotización #{compra.pk} aprobada. Estado: Pendiente de Llegada.'
            )
        else:
            messages.error(request, 'Error al aprobar la cotización.')
    
    return redirect('almacen:detalle_compra', pk=pk)


@login_required
@permission_required_with_message('almacen.change_compraproducto')
def rechazar_cotizacion(request, pk):
    """
    Rechazar una cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cuando el cliente no acepta la cotización:
    1. El estado cambia a 'rechazada'
    2. Se registra el motivo del rechazo
    3. La cotización queda cerrada (no se puede reactivar)
    """
    compra = get_object_or_404(CompraProducto, pk=pk)
    
    if not compra.puede_rechazar():
        messages.error(request, 'Esta cotización no puede ser rechazada.')
        return redirect('almacen:detalle_compra', pk=pk)
    
    if request.method == 'POST':
        form = RechazoCotizacionForm(request.POST)
        if form.is_valid():
            motivo = form.cleaned_data.get('motivo', '')
            if compra.rechazar(motivo=motivo, usuario=request.user):
                messages.success(request, f'Cotización #{compra.pk} rechazada.')
            else:
                messages.error(request, 'Error al rechazar la cotización.')
            return redirect('almacen:detalle_compra', pk=pk)
    else:
        form = RechazoCotizacionForm()
    
    context = {
        'compra': compra,
        'form': form,
    }
    
    return render(request, 'almacen/compras/rechazar_cotizacion.html', context)


@login_required
@permission_required_with_message('almacen.change_compraproducto')
def recibir_compra(request, pk):
    """
    Confirmar la recepción de una compra.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cuando llega la compra al almacén:
    1. Se registra la fecha de recepción
    2. Se crean MovimientoAlmacen de entrada (actualiza stock)
    3. Se crean UnidadInventario automáticamente desde las UnidadCompra
    4. El estado cambia a 'recibida'
    
    FLUJO SIMPLIFICADO:
    -------------------
    Cada UnidadCompra tiene un campo 'cantidad' que indica cuántas piezas
    son de esa marca/modelo. El método UnidadCompra.recibir() crea
    N UnidadInventario según esa cantidad.
    
    Ejemplo:
    - UnidadCompra #1: cantidad=5, marca=Kingston → crea 5 UnidadInventario
    - UnidadCompra #2: cantidad=5, marca=Samsung → crea 5 UnidadInventario
    - Total: 10 UnidadInventario
    """
    compra = get_object_or_404(
        CompraProducto.objects.select_related('producto').prefetch_related('unidades_compra'),
        pk=pk
    )
    
    if not compra.puede_recibir():
        messages.error(request, 'Esta compra no puede ser recibida en su estado actual.')
        return redirect('almacen:detalle_compra', pk=pk)
    
    if request.method == 'POST':
        form = RecepcionCompraForm(request.POST)
        if form.is_valid():
            fecha_recepcion = form.cleaned_data['fecha_recepcion']
            crear_unidades = form.cleaned_data['crear_unidades']
            notificar_tecnico_st = form.cleaned_data.get('notificar_tecnico_st', True)
            observaciones = form.cleaned_data.get('observaciones', '')
            
            # Obtener empleado para el movimiento
            try:
                empleado = Empleado.objects.get(user=request.user)
            except Empleado.DoesNotExist:
                messages.error(request, 'No tienes perfil de empleado asociado.')
                return redirect('almacen:detalle_compra', pk=pk)
            
            # Obtener orden de servicio SOLO si viene de cotización
            # Esto hace que las unidades se creen como 'asignadas' (comprometidas)
            # Las compras directas quedan con orden_servicio=None → unidades 'disponibles'
            orden_servicio = None
            if compra.tipo == 'cotizacion':
                # Intentar obtener de la relación con SolicitudCotizacion
                if hasattr(compra, 'linea_cotizacion_origen') and compra.linea_cotizacion_origen:
                    if compra.linea_cotizacion_origen.solicitud:
                        orden_servicio = compra.linea_cotizacion_origen.solicitud.orden_servicio
                # Si no se encontró, intentar del campo directo
                if not orden_servicio:
                    orden_servicio = compra.orden_servicio
            
            # Recibir la compra (sync ST + email al técnico si aplica)
            if compra.recibir(
                fecha_recepcion=fecha_recepcion,
                crear_unidades=False,
                notificar_tecnico_st=notificar_tecnico_st,
            ):
                # Crear movimiento de entrada
                MovimientoAlmacen.objects.create(
                    tipo='entrada',
                    producto=compra.producto,
                    cantidad=compra.cantidad,
                    costo_unitario=compra.costo_unitario,
                    empleado=empleado,
                    compra=compra,
                    observaciones=f'Recepción de compra #{compra.pk}. {observaciones}'.strip(),
                )
                
                # Crear UnidadInventario si se solicitó
                total_unidades_creadas = 0
                
                if crear_unidades:
                    unidades_compra = compra.unidades_compra.filter(estado='pendiente')
                    
                    # NUEVO FLUJO SIMPLIFICADO:
                    # Cada UnidadCompra.recibir() crea N UnidadInventario según su cantidad
                    for unidad_compra in unidades_compra:
                        unidades_creadas = unidad_compra.recibir(
                            crear_unidad_inventario=True,
                            orden_servicio_destino=orden_servicio,
                            registrado_por=request.user
                        )
                        total_unidades_creadas += len(unidades_creadas)
                
                # Si es COTIZACIÓN, crear movimiento de SALIDA automático
                # porque la pieza va directo al servicio (no se queda en almacén)
                if compra.tipo == 'cotizacion' and orden_servicio:
                    MovimientoAlmacen.objects.create(
                        tipo='salida',
                        producto=compra.producto,
                        cantidad=compra.cantidad,
                        costo_unitario=compra.costo_unitario,
                        empleado=empleado,
                        compra=compra,
                        orden_servicio=orden_servicio,
                        observaciones=f'Asignación automática a servicio (Cotización #{compra.pk}). Orden: {orden_servicio.detalle_equipo.orden_cliente if orden_servicio.detalle_equipo else orden_servicio.pk}',
                    )
                
                mensaje_resultado = f'Compra #{compra.pk} recibida exitosamente. {total_unidades_creadas} unidades agregadas al inventario.'
                if compra.tipo == 'cotizacion' and orden_servicio:
                    mensaje_resultado += f' (Asignadas automáticamente a servicio)'
                
                messages.success(request, mensaje_resultado)

                # Aviso del sync hacia Servicio Técnico (seguimiento + estado orden)
                sync_st = getattr(compra, '_resultado_sync_seguimiento_st', None) or {}
                n_seg = sync_st.get('seguimientos_actualizados', 0)
                if n_seg:
                    messages.info(
                        request,
                        f'{n_seg} seguimiento(s) de piezas actualizado(s) a «Recibido» en Servicio Técnico.'
                    )
                if sync_st.get('estado_orden_actualizado'):
                    messages.info(
                        request,
                        'Orden ST actualizada a «Piezas Recibidas».'
                    )
                if notificar_tecnico_st and n_seg:
                    if sync_st.get('emails_enviados'):
                        messages.info(
                            request,
                            f'Se notificó por correo al técnico '
                            f'({sync_st["emails_enviados"]} email(s)).'
                        )
                    elif sync_st.get('emails_fallidos'):
                        messages.warning(
                            request,
                            'No se pudo notificar al técnico por correo. '
                            'Revisa el historial de la orden en ST.'
                        )
            else:
                messages.error(request, 'Error al recibir la compra.')
            
            return redirect('almacen:detalle_compra', pk=pk)
    else:
        form = RecepcionCompraForm(initial={
            'fecha_recepcion': timezone.now().date(),
            'crear_unidades': True,
            'notificar_tecnico_st': True,
        })
    
    context = {
        'compra': compra,
        'form': form,
    }
    
    return render(request, 'almacen/compras/recibir_compra.html', context)


@login_required
@permission_required_with_message('almacen.change_compraproducto')
def reportar_problema_compra(request, pk):
    """
    Reportar problema con una compra recibida (WPB o DOA).
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Si la pieza recibida tiene problemas:
    - WPB (Wrong Part): Enviaron una pieza incorrecta
    - DOA (Dead On Arrival): La pieza está dañada/no funciona
    
    Al reportar:
    1. Se registra el tipo de problema y descripción
    2. El estado cambia a 'wpb' o 'doa'
    3. Se puede iniciar proceso de devolución
    """
    compra = get_object_or_404(CompraProducto, pk=pk)
    
    if not compra.puede_marcar_problema():
        messages.error(request, 'No se puede reportar problema en esta compra.')
        return redirect('almacen:detalle_compra', pk=pk)
    
    if request.method == 'POST':
        form = ProblemaCompraForm(request.POST)
        if form.is_valid():
            tipo_problema = form.cleaned_data['tipo_problema']
            motivo = form.cleaned_data['motivo']
            
            if tipo_problema == 'wpb':
                compra.marcar_wpb(motivo=motivo)
                messages.warning(request, f'Compra #{compra.pk} marcada como WPB (Pieza Incorrecta).')
            else:
                compra.marcar_doa(motivo=motivo)
                messages.warning(request, f'Compra #{compra.pk} marcada como DOA (Dañada al Llegar).')
            
            return redirect('almacen:detalle_compra', pk=pk)
    else:
        form = ProblemaCompraForm()
    
    context = {
        'compra': compra,
        'form': form,
    }
    
    return render(request, 'almacen/compras/problema_compra.html', context)


@login_required
@permission_required_with_message('almacen.change_compraproducto')
def iniciar_devolucion(request, pk):
    """
    Iniciar proceso de devolución al proveedor.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Después de reportar un problema (WPB/DOA), se puede iniciar
    la devolución al proveedor:
    1. El estado cambia a 'devolucion_garantia'
    2. Se prepara la pieza para envío de vuelta
    3. Cuando llegue al proveedor, se confirma la devolución
    """
    compra = get_object_or_404(CompraProducto, pk=pk)
    
    if not compra.puede_devolver():
        messages.error(request, 'No se puede iniciar devolución para esta compra.')
        return redirect('almacen:detalle_compra', pk=pk)
    
    if request.method == 'POST':
        if compra.iniciar_devolucion():
            messages.info(
                request,
                f'Devolución iniciada para compra #{compra.pk}. Confirma cuando sea recibida por el proveedor.'
            )
        else:
            messages.error(request, 'Error al iniciar devolución.')
    
    return redirect('almacen:detalle_compra', pk=pk)


@login_required
@permission_required_with_message('almacen.change_compraproducto')
def confirmar_devolucion(request, pk):
    """
    Confirmar que la devolución fue completada.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cuando el proveedor recibe la pieza devuelta:
    1. El estado cambia a 'devuelta'
    2. Se crea un MovimientoAlmacen de salida (descuenta del stock)
    3. La compra queda cerrada
    """
    compra = get_object_or_404(CompraProducto, pk=pk)
    
    if not compra.puede_confirmar_devolucion():
        messages.error(request, 'No se puede confirmar devolución para esta compra.')
        return redirect('almacen:detalle_compra', pk=pk)
    
    if request.method == 'POST':
        form = DevolucionCompraForm(request.POST)
        if form.is_valid():
            observaciones = form.cleaned_data.get('observaciones', '')
            numero_guia = form.cleaned_data.get('numero_guia', '')
            
            if numero_guia:
                observaciones = f'Guía: {numero_guia}. {observaciones}'.strip()
            
            # Obtener empleado
            try:
                empleado = Empleado.objects.get(user=request.user)
            except Empleado.DoesNotExist:
                empleado = None
            
            if compra.confirmar_devolucion(empleado=empleado, observaciones=observaciones):
                messages.success(
                    request,
                    f'Devolución confirmada para compra #{compra.pk}. Stock actualizado.'
                )
            else:
                messages.error(request, 'Error al confirmar devolución.')
            
            return redirect('almacen:detalle_compra', pk=pk)
    else:
        form = DevolucionCompraForm()
    
    context = {
        'compra': compra,
        'form': form,
        # Stock final después de la devolución (stock actual - cantidad a devolver)
        'stock_final': compra.producto.stock_actual - compra.cantidad if compra.producto else 0,
    }
    
    return render(request, 'almacen/compras/confirmar_devolucion.html', context)


@login_required
@permission_required_with_message('almacen.delete_compraproducto')
def cancelar_compra(request, pk):
    """
    Cancelar una compra o cotización.
    
    NOTA: No se puede cancelar si ya fue recibida sin problemas.
    """
    compra = get_object_or_404(CompraProducto, pk=pk)
    
    if compra.estado == 'recibida':
        messages.error(request, 'No se puede cancelar una compra ya recibida.')
        return redirect('almacen:detalle_compra', pk=pk)
    
    if request.method == 'POST':
        motivo = request.POST.get('motivo', '')
        if compra.cancelar(motivo=motivo):
            messages.success(request, f'Compra #{compra.pk} cancelada.')
        else:
            messages.error(request, 'Error al cancelar la compra.')
    
    return redirect('almacen:detalle_compra', pk=pk)


@login_required
@permission_required_with_message('almacen.change_unidadcompra')
def recibir_unidad_compra(request, compra_pk, pk):
    """
    Recibir una unidad individual de una compra.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Si la compra tiene UnidadCompra definidas, se puede recibir
    cada pieza individualmente en lugar de todas a la vez.
    
    Esto es útil cuando:
    - Las piezas llegan en diferentes momentos
    - Se quiere verificar cada pieza antes de darla por recibida
    
    IMPORTANTE: No aplica a compras tipo «cotizacion». Ahí se debe usar
    «Confirmar Recepción» (flujo completo con stock y sync ST).
    """
    compra = get_object_or_404(CompraProducto, pk=compra_pk)
    unidad = get_object_or_404(UnidadCompra, pk=pk, compra=compra)

    # Bloqueo de seguridad: aunque ocultemos el botón, alguien podría POST a la URL
    if compra.tipo == 'cotizacion':
        messages.error(
            request,
            'En compras de cotización debes usar «Confirmar Recepción» '
            '(cierra la compra, actualiza stock y notifica a Servicio Técnico).'
        )
        return redirect('almacen:detalle_compra', pk=compra_pk)
    
    if not unidad.puede_recibir():
        messages.error(request, 'Esta unidad no puede ser recibida.')
        return redirect('almacen:detalle_compra', pk=compra_pk)
    
    if request.method == 'POST':
        unidades_inv = unidad.recibir(crear_unidad_inventario=True)
        # recibir() devuelve una lista de UnidadInventario creadas
        if unidades_inv:
            codigos = ', '.join(u.codigo_interno for u in unidades_inv if getattr(u, 'codigo_interno', None))
            messages.success(
                request,
                f'Unidad #{unidad.numero_linea} recibida. Inventario: {codigos or "creado"}'
            )
        else:
            messages.error(request, 'Error al recibir la unidad.')
    
    return redirect('almacen:detalle_compra', pk=compra_pk)


@login_required
@permission_required_with_message('almacen.change_unidadcompra')
def problema_unidad_compra(request, compra_pk, pk):
    """
    Reportar problema con una unidad específica de una compra.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Solo para compras directas. En cotizaciones el WPB/DOA se reporta
    con el botón grande «Reportar Problema» de la compra completa.
    """
    compra = get_object_or_404(CompraProducto, pk=compra_pk)
    unidad = get_object_or_404(UnidadCompra, pk=pk, compra=compra)

    if compra.tipo == 'cotizacion':
        messages.error(
            request,
            'En compras de cotización usa «Reportar Problema (WPB/DOA)» '
            'desde las acciones de la compra completa.'
        )
        return redirect('almacen:detalle_compra', pk=compra_pk)
    
    if request.method == 'POST':
        tipo = request.POST.get('tipo_problema', 'wpb')
        motivo = request.POST.get('motivo', '')
        
        if tipo == 'doa':
            unidad.marcar_doa(motivo=motivo)
            messages.warning(request, f'Unidad #{unidad.numero_linea} marcada como DOA.')
        else:
            unidad.marcar_wpb(motivo=motivo)
            messages.warning(request, f'Unidad #{unidad.numero_linea} marcada como WPB.')
    
    return redirect('almacen:detalle_compra', pk=compra_pk)


# ============================================================================
# SOLICITUDES DE COTIZACIÓN (MULTI-PROVEEDOR)
# ============================================================================

@login_required
@permission_required_with_message('almacen.view_solicitudcotizacion')
def lista_solicitudes_cotizacion(request):
    """
    Lista todas las solicitudes de cotización con filtros.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista muestra todas las solicitudes de cotización en una tabla.
    Permite filtrar por:
    - Estado (borrador, enviada, aprobada, etc.)
    - Fecha de creación
    - Búsqueda por número de solicitud u orden
    
    También muestra un resumen con contadores por estado para una
    visión rápida del flujo de trabajo.
    """
    # Obtener todas las solicitudes
    solicitudes = SolicitudCotizacion.objects.select_related(
        'orden_servicio',
        'creado_por'
    ).prefetch_related('lineas').order_by('-fecha_creacion')
    
    # Aplicar filtros
    filtro_form = SolicitudCotizacionFiltroForm(request.GET)
    
    if filtro_form.is_valid():
        estado = filtro_form.cleaned_data.get('estado')
        fecha_desde = filtro_form.cleaned_data.get('fecha_desde')
        fecha_hasta = filtro_form.cleaned_data.get('fecha_hasta')
        buscar = filtro_form.cleaned_data.get('buscar')
        
        if estado:
            solicitudes = solicitudes.filter(estado=estado)
        
        if fecha_desde:
            solicitudes = solicitudes.filter(fecha_creacion__date__gte=fecha_desde)
        
        if fecha_hasta:
            solicitudes = solicitudes.filter(fecha_creacion__date__lte=fecha_hasta)
        
        if buscar:
            solicitudes = solicitudes.filter(
                Q(numero_solicitud__icontains=buscar) |
                Q(numero_orden_cliente__icontains=buscar)
            )
    
    # Contadores por estado para el resumen
    contadores = SolicitudCotizacion.objects.values('estado').annotate(
        total=Count('id')
    )
    contadores_dict = {c['estado']: c['total'] for c in contadores}
    
    # Paginación
    paginator = Paginator(solicitudes, 20)
    page = request.GET.get('page', 1)
    solicitudes_page = paginator.get_page(page)
    
    context = {
        'solicitudes': solicitudes_page,
        'filtro_form': filtro_form,
        'contadores': contadores_dict,
        'titulo': 'Solicitudes de Cotización',
        # Para resaltar el KPI activo y mostrar el total en el encabezado
        'estado_filtro': request.GET.get('estado', ''),
        'total_general': sum(contadores_dict.values()),
    }
    
    return render(request, 'almacen/cotizaciones/lista_solicitudes.html', context)


@login_required
@permission_required_with_message('almacen.add_solicitudcotizacion')
def crear_solicitud_cotizacion(request):
    """
    Crear una nueva solicitud de cotización con múltiples líneas.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista maneja la creación de una solicitud de cotización.
    
    El proceso tiene tres partes:
    1. El formulario principal (SolicitudCotizacionForm) captura:
       - Número de orden del cliente (para vincular con servicio técnico)
       - O modo sin orden: datos del cliente + service tag + marca/modelo
       - Observaciones internas
    
    2. El formset (LineaCotizacionFormSet) captura las líneas:
       - Cada línea tiene: producto, descripción, proveedor, cantidad, costo
       - Se pueden agregar múltiples líneas dinámicamente con JavaScript
    
    3. Las imágenes de referencia (request.FILES):
       - Hasta 6 imágenes del equipo/piezas que el cliente quiere cotizar
       - Se procesan después de guardar la solicitud
    
    Flujo:
    1. GET: Muestra formularios vacíos
    2. POST: Valida ambos formularios
       - Si válidos: Guarda solicitud, líneas e imágenes, redirige a detalle
       - Si inválidos: Muestra errores
    """
    if request.method == 'POST':
        form = SolicitudCotizacionForm(request.POST)
        formset = LineaCotizacionFormSetCreacion(request.POST)
        
        if form.is_valid() and formset.is_valid():
            # Guardar la solicitud (cabecera)
            solicitud = form.save(commit=False)
            solicitud.creado_por = request.user
            solicitud.save()
            
            # Guardar las líneas (detalle)
            formset.instance = solicitud
            formset.save()
            
            # Procesar imágenes de referencia (hasta 6)
            imagenes = request.FILES.getlist('imagenes_referencia')
            descripciones = request.POST.getlist('descripcion_imagen')
            imagenes_guardadas = 0
            
            for i, imagen in enumerate(imagenes):
                if imagenes_guardadas >= ImagenSolicitudCotizacion.MAX_IMAGENES_POR_SOLICITUD:
                    break
                try:
                    descripcion = descripciones[i] if i < len(descripciones) else ''
                    ImagenSolicitudCotizacion.objects.create(
                        solicitud=solicitud,
                        imagen=imagen,
                        descripcion=descripcion,
                        subido_por=request.user,
                    )
                    imagenes_guardadas += 1
                except (ValueError, Exception) as e:
                    messages.warning(request, f'Error al subir imagen: {str(e)}')
            
            if imagenes_guardadas > 0:
                messages.info(request, f'{imagenes_guardadas} imagen(es) de referencia subidas.')

            # =================================================================
            # NOTIFICAR A COMPRAS cuando la solicitud es "Sin Orden Activa"
            # =================================================================
            # EXPLICACIÓN PARA PRINCIPIANTES:
            # Cuando una solicitud se crea sin una orden de servicio vinculada
            # (modo "sin orden activa"), el área de Compras necesita saberlo
            # de inmediato para procesar la cotización. Les enviamos:
            #   1. Push al dispositivo (notificación en tiempo real)
            #   2. Campanita interna (notificación del sistema)
            #   3. Email en segundo plano vía Celery (no bloquea al usuario)
            if solicitud.sin_orden_activa:
                try:
                    from notificaciones.push_service import enviar_push_a_usuario
                    from notificaciones.utils import notificar_info
                    from .tasks import notificar_compras_nueva_cotizacion_task

                    # Buscar todos los empleados con rol "Compras" que tengan
                    # usuario activo en el sistema (pueden recibir notificaciones)
                    compradores = Empleado.objects.filter(
                        rol='compras',
                        user__is_active=True,
                    ).select_related('user')

                    if compradores.exists():
                        # Construir la URL al detalle de la solicitud para que
                        # al hacer clic en la notificación los lleve directamente
                        url_solicitud = reverse(
                            'almacen:detalle_solicitud_cotizacion',
                            kwargs={'pk': solicitud.pk}
                        )

                        # Texto de la notificación — incluye el nombre del
                        # cliente y el service tag para identificación rápida
                        titulo_push = f'📋 Nueva cotización sin orden: {solicitud.numero_solicitud}'
                        mensaje_push = (
                            f'Cliente: {solicitud.nombre_cliente or "Sin nombre"} — '
                            f'S/T: {solicitud.service_tag or "N/A"}. '
                            f'Requiere atención para procesar la cotización.'
                        )

                        # Enviar push + campanita a cada empleado de Compras
                        for comprador in compradores:
                            try:
                                enviar_push_a_usuario(
                                    usuario=comprador.user,
                                    titulo=titulo_push,
                                    mensaje=mensaje_push,
                                    url=url_solicitud,
                                )
                            except Exception as push_err:
                                logger.warning(
                                    f"[COTIZACION] Error enviando push a {comprador.nombre_completo}: {push_err}"
                                )

                            try:
                                notificar_info(
                                    titulo=titulo_push,
                                    mensaje=mensaje_push,
                                    usuario=comprador.user,
                                    url=url_solicitud,
                                    app_origen='almacen',
                                )
                            except Exception as notif_err:
                                logger.warning(
                                    f"[COTIZACION] Error creando notificación para {comprador.nombre_completo}: {notif_err}"
                                )

                        # Enviar email en segundo plano vía Celery (no bloquea)
                        from config.paises_config import get_pais_actual
                        notificar_compras_nueva_cotizacion_task.delay(
                            solicitud.pk,
                            request.user.pk,
                            get_pais_actual()['db_alias'],
                        )
                        logger.info(
                            f"[COTIZACION] Notificaciones enviadas a {compradores.count()} "
                            f"empleado(s) de Compras para solicitud {solicitud.numero_solicitud}"
                        )
                except Exception as e:
                    # Si falla la notificación, NO debe impedir que la solicitud
                    # se haya creado correctamente. Solo registramos el error.
                    logger.error(f"[COTIZACION] Error al notificar a Compras: {e}")

            messages.success(
                request,
                f'Solicitud de cotización {solicitud.numero_solicitud} creada exitosamente.'
            )
            return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud.pk)
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = SolicitudCotizacionForm()
        formset = LineaCotizacionFormSetCreacion()

    # Obtener la sucursal del usuario logueado para mostrarla en el formulario
    # cuando se usa el modo "sin orden activa". Se muestra como dato informativo
    # (solo lectura) para que el técnico sepa desde qué sucursal está cotizando.
    sucursal_usuario = None
    try:
        sucursal_usuario = request.user.empleado.sucursal
    except Exception:
        # El usuario puede no tener perfil de empleado o sucursal asignada — es válido
        pass

    context = {
        'form': form,
        'formset': formset,
        'titulo': 'Nueva Solicitud de Cotización',
        'es_creacion': True,
        'max_imagenes_referencia': ImagenSolicitudCotizacion.MAX_IMAGENES_POR_SOLICITUD,
        # Sucursal del usuario actual, para pre-mostrar en modo sin orden activa
        'sucursal_usuario': sucursal_usuario,
    }
    
    return render(request, 'almacen/cotizaciones/form_solicitud.html', context)


@login_required
@permission_required_with_message('almacen.change_solicitudcotizacion')
def editar_solicitud_cotizacion(request, pk):
    """
    Editar una solicitud de cotización existente.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Similar a crear, pero carga los datos existentes en los formularios.
    
    Solo se puede editar si la solicitud está en estado 'borrador'.
    Una vez enviada al cliente, no se puede modificar.
    
    También permite agregar más imágenes de referencia.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    # Solo se puede editar en estado borrador
    if solicitud.estado != 'borrador':
        messages.error(
            request,
            'Solo se pueden editar solicitudes en estado borrador.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
    
    if request.method == 'POST':
        form = SolicitudCotizacionForm(request.POST, instance=solicitud)
        formset = LineaCotizacionFormSet(request.POST, instance=solicitud)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            
            # Procesar imágenes de referencia nuevas (hasta el límite)
            imagenes = request.FILES.getlist('imagenes_referencia')
            descripciones = request.POST.getlist('descripcion_imagen')
            imagenes_guardadas = 0
            
            for i, imagen in enumerate(imagenes):
                if not ImagenSolicitudCotizacion.puede_agregar_imagen(solicitud):
                    messages.warning(
                        request,
                        f'Se alcanzó el límite de {ImagenSolicitudCotizacion.MAX_IMAGENES_POR_SOLICITUD} imágenes.'
                    )
                    break
                try:
                    descripcion = descripciones[i] if i < len(descripciones) else ''
                    ImagenSolicitudCotizacion.objects.create(
                        solicitud=solicitud,
                        imagen=imagen,
                        descripcion=descripcion,
                        subido_por=request.user,
                    )
                    imagenes_guardadas += 1
                except (ValueError, Exception) as e:
                    messages.warning(request, f'Error al subir imagen: {str(e)}')
            
            if imagenes_guardadas > 0:
                messages.info(request, f'{imagenes_guardadas} imagen(es) de referencia agregadas.')
            
            messages.success(request, 'Solicitud actualizada exitosamente.')
            return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = SolicitudCotizacionForm(instance=solicitud)
        formset = LineaCotizacionFormSet(instance=solicitud)
    
    # Calcular imágenes restantes
    imagenes_actuales = ImagenSolicitudCotizacion.objects.filter(solicitud=solicitud).count()
    imagenes_restantes = max(0, ImagenSolicitudCotizacion.MAX_IMAGENES_POR_SOLICITUD - imagenes_actuales)
    
    context = {
        'form': form,
        'formset': formset,
        'solicitud': solicitud,
        'titulo': f'Editar Solicitud {solicitud.numero_solicitud}',
        'es_creacion': False,
        'max_imagenes_referencia': ImagenSolicitudCotizacion.MAX_IMAGENES_POR_SOLICITUD,
        'imagenes_referencia_actuales': imagenes_actuales,
        'imagenes_referencia_restantes': imagenes_restantes,
    }
    
    return render(request, 'almacen/cotizaciones/form_solicitud.html', context)


@login_required
@permission_required_with_message('almacen.change_lineacotizacion')
def editar_lineas_cotizacion(request, pk):
    """
    Editar líneas de cotización cuando la solicitud está en estado 'enviada_front'.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista permite modificar ciertos campos de las líneas de cotización
    DESPUÉS de que la solicitud fue enviada a Front, pero ANTES de que el
    cliente apruebe o se genere la compra.
    
    ¿Qué se puede editar?
    - Proveedor (si el original no tiene stock)
    - Costo unitario (si cambió el precio)
    - Cantidad (si el cliente pide más/menos)
    - Tiempo de entrega estimado
    - Notas adicionales
    
    ¿Qué NO se puede editar?
    - Producto (ya fue definido)
    - Descripción de la pieza (es la identidad)
    
    ¿Qué líneas se pueden editar?
    - Solo las que tienen estado 'pendiente' o 'rechazada'
    - Las líneas 'aprobada' o 'compra_generada' se muestran como solo lectura
    
    IMPORTANTE: El formset solo incluye las líneas editables.
    Las líneas bloqueadas se muestran como texto plano fuera del formset.
    """
    from .forms import EditarLineaCotizacionFormSet
    from .models import LineaCotizacion
    
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    # Se puede editar líneas en enviada_front o enviada_cliente (por si se necesita recotizar)
    if solicitud.estado not in ['enviada_front', 'enviada_cliente']:
        messages.error(
            request,
            'Solo se pueden editar líneas cuando la solicitud está en estado "Enviada a Front" o "Enviada a Cliente".'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
    
    # Filtrar solo líneas editables (pendiente o rechazada)
    lineas_editables_qs = solicitud.lineas.filter(
        estado_cliente__in=['pendiente', 'rechazada']
    ).order_by('numero_linea')
    
    # Líneas bloqueadas (aprobada o compra_generada) - solo para mostrar
    lineas_bloqueadas = solicitud.lineas.filter(
        estado_cliente__in=['aprobada', 'compra_generada']
    ).order_by('numero_linea')
    
    if request.method == 'POST':
        # El formset solo procesa líneas editables
        formset = EditarLineaCotizacionFormSet(
            request.POST,
            instance=solicitud,
            queryset=lineas_editables_qs
        )
        
        if formset.is_valid():
            # Guardar cambios y contar cuántas líneas se modificaron
            lineas_modificadas = 0
            
            for form in formset.forms:
                if form.has_changed():
                    form.save()
                    lineas_modificadas += 1
            
            if lineas_modificadas > 0:
                messages.success(
                    request,
                    f'Se actualizaron {lineas_modificadas} línea(s) de la cotización.'
                )
            else:
                messages.info(request, 'No se realizaron cambios en las líneas.')
            
            return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        formset = EditarLineaCotizacionFormSet(
            instance=solicitud,
            queryset=lineas_editables_qs
        )
    
    # Preparar información para el template
    lineas_editables_info = []
    for form, linea in zip(formset.forms, lineas_editables_qs):
        lineas_editables_info.append({
            'form': form,
            'linea': linea,
        })
    
    context = {
        'formset': formset,
        'solicitud': solicitud,
        'lineas_editables_info': lineas_editables_info,
        'lineas_bloqueadas': lineas_bloqueadas,
        'titulo': f'Editar Líneas - {solicitud.numero_solicitud}',
    }
    
    return render(request, 'almacen/cotizaciones/editar_lineas.html', context)


import json as _json  # alias para no colisionar con variables de vistas


def _serializar_profit_config() -> str:
    """
    Lee la configuración de profit vigente (panel BD + fallback .env)
    y la convierte a una cadena JSON lista para inyectar en el template.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    El template necesita pasar estos valores al JavaScript del navegador.
    Al usar |safe en el template, Django inserta el JSON sin escapar las
    comillas, de modo que el navegador lo interpreta como objeto JS válido.

    Importamos dentro de la función (importación diferida) para evitar
    importaciones circulares y para mantener el módulo ligero.

    Returns:
        str: Cadena JSON con la configuración de profit por perfil.
    """
    # Importación diferida: usa BD (panel) con respaldo .env
    from .utils.parametros_cotizador import obtener_profit_config

    profit_cfg = obtener_profit_config()
    # Construir un diccionario serializable (las listas de costos_fijos ya lo son)
    datos = {
        perfil: {
            'profit_target':  cfg['profit_target'],
            'costos_fijos':   cfg['costos_fijos'],
            'diagnostico':    cfg['diagnostico'],
        }
        for perfil, cfg in profit_cfg.items()
    }
    # Convertir a JSON compacto — se incrustará dentro de un <script>
    return _json.dumps(datos, separators=(',', ':'))


def _serializar_costeo_reacondicionado_config() -> str:
    """
    Serializa la configuración del costeo de reacondicionados para el modal TypeScript.

    Returns:
        str: JSON compacto con porcentajes y montos del .env.
    """
    from .utils.costeo_reacondicionado import serializar_config_costeo
    return _json.dumps(serializar_config_costeo(), separators=(',', ':'))


def _actualizar_estado_st_esperando_aprobacion_cliente(solicitud, usuario=None):
    """
    Compatibilidad: delega en el util de sync (no retrocede estados posteriores).

    EXPLICACIÓN PARA PRINCIPIANTES:
    La lógica real vive en sincronizar_estado_st.py. Esta función solo existe
    para que las vistas de envío de cotización sigan llamando el mismo nombre.
    """
    from almacen.utils.sincronizar_estado_st import (
        sincronizar_estado_st_al_enviar_cotizacion_cliente,
    )
    return sincronizar_estado_st_al_enviar_cotizacion_cliente(
        solicitud,
        usuario=usuario,
    )


def _extraer_datos_reacondicionado_post(post) -> dict:
    """
    Lee del POST los campos del equipo reacondicionado capturados en el modal.

    Args:
        post: request.POST de Django.

    Returns:
        dict: Datos del equipo y parámetros de costeo.
    """
    return {
        'costo_proveedor': post.get('reac_costo_proveedor', '').strip(),
        'dias_front_desk': post.get('reac_dias_front_desk', '1').strip(),
        'marca': post.get('reac_marca', '').strip(),
        'modelo': post.get('reac_modelo', '').strip(),
        'procesador': post.get('reac_procesador', '').strip(),
        'ram': post.get('reac_ram', '').strip(),
        'sistema_operativo': post.get('reac_sistema_operativo', '').strip(),
        'incluye_cargador': post.get('reac_incluye_cargador') == '1',
        'especificaciones': post.get('reac_especificaciones', '').strip(),
    }


def _validar_y_calcular_reacondicionado(datos: dict):
    """
    Valida campos obligatorios y ejecuta calcular_costeo().

    Returns:
        tuple: (ok: bool, resultado_o_error: dict|str)
    """
    from .utils.costeo_reacondicionado import calcular_costeo

    if not datos.get('marca'):
        return False, 'La marca del equipo es obligatoria.'
    if not datos.get('modelo'):
        return False, 'El modelo del equipo es obligatorio.'

    try:
        costo = float(datos.get('costo_proveedor') or 0)
        if costo <= 0:
            return False, 'El costo de proveedor debe ser mayor a cero.'
    except ValueError:
        return False, 'El costo de proveedor no es un número válido.'

    try:
        dias = int(datos.get('dias_front_desk') or 1)
        if dias < 1:
            dias = 1
    except ValueError:
        return False, 'Los días de front desk deben ser un número entero válido.'

    # Si los % variables en BD suman ≥ 100%, calcular_costeo lanza ValueError
    try:
        costeo = calcular_costeo(costo_proveedor=costo, dias_front_desk=dias)
    except ValueError as exc:
        return False, str(exc)

    datos_equipo = {
        'marca': datos['marca'],
        'modelo': datos['modelo'],
        'procesador': datos.get('procesador', ''),
        'ram': datos.get('ram', ''),
        'sistema_operativo': datos.get('sistema_operativo', ''),
        'incluye_cargador': datos.get('incluye_cargador', False),
        'especificaciones': datos.get('especificaciones', ''),
    }
    return True, {'costeo': costeo, 'datos_equipo': datos_equipo, 'dias_front_desk': dias, 'costo_proveedor': costo}


def _guardar_snapshot_reacondicionado(solicitud, datos_equipo, costeo, dias, costo):
    """Persiste en la solicitud el snapshot de la propuesta reacondicionada."""
    from decimal import Decimal
    solicitud.modo_cotizacion_cliente = 'reacondicionado'
    solicitud.costo_proveedor_reac = Decimal(str(costo))
    solicitud.dias_front_desk_reac = dias
    solicitud.reac_marca = datos_equipo.get('marca', '')
    solicitud.reac_modelo = datos_equipo.get('modelo', '')
    solicitud.reac_procesador = datos_equipo.get('procesador', '')
    solicitud.reac_ram = datos_equipo.get('ram', '')
    solicitud.reac_sistema_operativo = datos_equipo.get('sistema_operativo', '')
    solicitud.reac_incluye_cargador = bool(datos_equipo.get('incluye_cargador'))
    solicitud.reac_especificaciones = datos_equipo.get('especificaciones', '')
    solicitud.resultado_costeo_reac = costeo
    solicitud.save(update_fields=[
        'modo_cotizacion_cliente',
        'costo_proveedor_reac',
        'dias_front_desk_reac',
        'reac_marca',
        'reac_modelo',
        'reac_procesador',
        'reac_ram',
        'reac_sistema_operativo',
        'reac_incluye_cargador',
        'reac_especificaciones',
        'resultado_costeo_reac',
    ])


# SKU del catálogo para equipos reacondicionados ofertados al cliente
CODIGO_PRODUCTO_REACONDICIONADO = 'P0125'


def _construir_descripcion_linea_reac(datos_equipo: dict) -> str:
    """
    Arma una descripción compacta del equipo para LineaCotizacion.descripcion_pieza.

    Args:
        datos_equipo: dict con marca, modelo, procesador, ram, sistema_operativo, incluye_cargador.

    Returns:
        str: Texto truncado a 255 caracteres (límite del campo).
    """
    partes = []
    marca = (datos_equipo.get('marca') or '').strip()
    modelo = (datos_equipo.get('modelo') or '').strip()
    if marca or modelo:
        partes.append(f'{marca} {modelo}'.strip())
    if datos_equipo.get('procesador'):
        partes.append(str(datos_equipo['procesador']).strip())
    if datos_equipo.get('ram'):
        partes.append(str(datos_equipo['ram']).strip())
    if datos_equipo.get('sistema_operativo'):
        partes.append(str(datos_equipo['sistema_operativo']).strip())
    if datos_equipo.get('incluye_cargador'):
        partes.append('Con cargador')
    return ' | '.join(partes)[:255]


def _crear_o_actualizar_linea_reacondicionado(solicitud, datos_equipo, costeo, costo_proveedor):
    """
    Crea o actualiza la LineaCotizacion P0125 al enviar propuesta de equipo reacondicionado.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta línea permite a Front aprobar/rechazar la oferta de equipo igual que las piezas
    de reparación. Al aprobar y generar compras, el equipo va a PiezaVentaMostrador en ST.

    Args:
        solicitud: SolicitudCotizacion vinculada.
        datos_equipo: Especificaciones capturadas en el modal.
        costeo: Resultado de calcular_costeo().
        costo_proveedor: float, costo de adquisición sin IVA.

    Returns:
        tuple: (ok: bool, error: str|None)
    """
    from decimal import Decimal
    from .models import LineaCotizacion, ProductoAlmacen

    try:
        producto = ProductoAlmacen.objects.get(codigo_producto=CODIGO_PRODUCTO_REACONDICIONADO)
    except ProductoAlmacen.DoesNotExist:
        logger.error(
            f'[REAC] Producto {CODIGO_PRODUCTO_REACONDICIONADO} no existe en ProductoAlmacen. '
            f'Solicitud {solicitud.numero_solicitud}'
        )
        return False, (
            f'El producto {CODIGO_PRODUCTO_REACONDICIONADO} (equipo reacondicionado) '
            'no está en el catálogo de almacén. Contacte al administrador.'
        )

    subtotal_sin_iva = Decimal(str(costeo.get('subtotal_sin_iva', 0)))
    descripcion = _construir_descripcion_linea_reac(datos_equipo)

    notas_partes = []
    especificaciones = (datos_equipo.get('especificaciones') or '').strip()
    if especificaciones:
        notas_partes.append(especificaciones)
    total_contado = costeo.get('total_precio_contado_mxn')
    if total_contado is not None:
        notas_partes.append(f'Precio contado (IVA incl.): ${total_contado}')

    defaults = {
        'descripcion_pieza': descripcion,
        'cantidad': 1,
        'costo_unitario': Decimal(str(costo_proveedor)),
        'precio_unitario_cliente': subtotal_sin_iva,
        'subtotal_cliente_sin_iva': subtotal_sin_iva,
        'es_linea_reacondicionado': True,
        'es_necesaria': False,
        'estado_cliente': 'pendiente',
        'opcion_pago_reac': '',
        'notas': '\n'.join(notas_partes),
    }

    linea = solicitud.lineas.filter(
        producto=producto,
        es_linea_reacondicionado=True,
    ).first()

    if linea:
        for campo, valor in defaults.items():
            setattr(linea, campo, valor)
        linea.save()
        logger.info(
            f'[REAC] Línea reacondicionado actualizada en solicitud {solicitud.numero_solicitud}'
        )
    else:
        LineaCotizacion.objects.create(
            solicitud=solicitud,
            producto=producto,
            **defaults,
        )
        logger.info(
            f'[REAC] Línea reacondicionado creada en solicitud {solicitud.numero_solicitud}'
        )

    return True, None


def _opciones_servicios_adicionales():
    """
    Construye la lista de servicios adicionales para el dropdown del modal.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Los nombres vienen de TIPO_SERVICIO_ADICIONAL_CHOICES y los precios de
    PRECIOS_SERVICIOS_ADICIONALES (constants.py). Así el template no repite
    valores hardcodeados que pueden quedar desactualizados.

    Returns:
        list[dict]: Opciones con codigo, nombre y precio (IVA incluido).
    """
    from config.constants import (
        TIPO_SERVICIO_ADICIONAL_CHOICES,
        PRECIOS_SERVICIOS_ADICIONALES,
    )

    return [
        {
            'codigo': codigo,
            'nombre': nombre,
            'precio': PRECIOS_SERVICIOS_ADICIONALES.get(codigo, 0),
        }
        for codigo, nombre in TIPO_SERVICIO_ADICIONAL_CHOICES
    ]


@login_required
@permission_required_with_message('almacen.view_solicitudcotizacion')
def detalle_solicitud_cotizacion(request, pk):
    """
    Ver detalle completo de una solicitud de cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista muestra toda la información de una solicitud:
    - Datos de la cabecera (número, orden vinculada, estado)
    - Sugerencias de piezas del diagnóstico (si la orden ya las tiene)
    - Tabla con todas las líneas y sus estados
    - Imágenes de referencia de cada línea
    - Totales y resúmenes
    - Acciones disponibles según el estado
    
    Las acciones cambian según el estado:
    - Borrador: Editar, Enviar a cliente, Cancelar, Subir imágenes
    - Enviada: Registrar respuestas del cliente
    - Aprobada: Generar compras
    - Completada: Solo visualización
    
    También permite subir imágenes a las líneas cuando está en borrador.
    """
    solicitud = get_object_or_404(
        SolicitudCotizacion.objects.select_related(
            'orden_servicio',
            'orden_servicio__sucursal',        # Sucursal de la orden vinculada
            'orden_servicio__detalle_equipo',  # Detalle (incluye sugerencias de diagnóstico)
            'creado_por',
            'creado_por__empleado',            # Perfil de empleado del creador
            'creado_por__empleado__sucursal',  # Sucursal del creador (para sin_orden_activa)
        ).prefetch_related(
            'lineas__producto',
            'lineas__proveedor',
            'lineas__compra_generada',
            'lineas__imagenes',  # Incluir imágenes de cada línea
            'imagenes_referencia',  # Incluir imágenes de referencia de la solicitud
        ),
        pk=pk
    )
    
    # Información del equipo desde DetalleEquipo si está vinculada la orden
    info_orden = None
    if solicitud.orden_servicio:
        try:
            info_orden = solicitud.orden_servicio.detalle_equipo
        except Exception:
            pass

    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Al enviar el diagnóstico en ST se guardan piezas_sugeridas_diagnostico (JSON).
    # Front las ve aquí para comparar vs lo que cotizó Compras. No se editan desde Almacén.
    piezas_sugeridas_diagnostico = []
    if info_orden:
        sugerencias_raw = getattr(info_orden, 'piezas_sugeridas_diagnostico', None) or []
        if isinstance(sugerencias_raw, list):
            for item in sugerencias_raw:
                if not isinstance(item, dict):
                    continue
                componente = (item.get('componente_db') or '').strip()
                if not componente:
                    continue
                piezas_sugeridas_diagnostico.append({
                    'componente_db': componente,
                    'dpn': (item.get('dpn') or '').strip(),
                    'es_necesaria': bool(item.get('es_necesaria', True)),
                })

    # --- Datos extra para el modal de envío de cotización al cliente ---
    # Obtenemos gama, mano de obra y email del cliente para pre-llenar el modal

    # Gama del equipo (alta/media/baja) — solo disponible si hay orden vinculada
    gama_equipo = ''
    if info_orden:
        gama_equipo = getattr(info_orden, 'gama', '') or ''

    # Costo de mano de obra desde la Cotizacion de Servicio Técnico
    # (el usuario puede sobreescribirlo en el modal si lo desea)
    costo_mano_obra = None
    if solicitud.orden_servicio:
        try:
            # La Cotizacion está vinculada 1:1 a la OrdenServicio
            cotizacion_st = solicitud.orden_servicio.cotizacion
            costo_mano_obra = float(cotizacion_st.costo_mano_obra)
        except Exception:
            # La orden puede no tener cotización aún — es normal
            pass

    # Email del cliente para el campo "Destinatario" del modal
    email_cliente_modal = ''
    if info_orden:
        email_raw = getattr(info_orden, 'email_cliente', '') or ''
        # Excluir el email placeholder que usa ST cuando no hay email real
        if email_raw and email_raw != 'cliente@ejemplo.com':
            email_cliente_modal = email_raw
    elif solicitud.email_cliente:
        email_cliente_modal = solicitud.email_cliente

    # Asunto sugerido para el modal: prefijo + orden cliente o service tag
    from .utils.cotizacion_email_context import construir_asunto_correo_default
    asunto_correo_modal = construir_asunto_correo_default(solicitud, info_orden=info_orden)
    
    # Procesar subida de imagen (solo en estado borrador)
    mensaje_imagen = None
    if request.method == 'POST' and solicitud.estado == 'borrador':
        linea_pk = request.POST.get('linea_pk')
        if linea_pk and 'imagen' in request.FILES:
            try:
                linea = solicitud.lineas.get(pk=linea_pk)
                form = ImagenLineaCotizacionForm(
                    request.POST,
                    request.FILES,
                    linea=linea
                )
                if form.is_valid():
                    imagen = form.save(commit=False)
                    imagen.linea = linea
                    imagen.subido_por = request.user
                    imagen.save()
                    messages.success(
                        request,
                        f'Imagen subida exitosamente a la línea #{linea.numero_linea}.'
                    )
                else:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f'{error}')
            except LineaCotizacion.DoesNotExist:
                messages.error(request, 'Línea no encontrada.')
            except ValueError as e:
                messages.error(request, str(e))
            
            # Redirigir para evitar reenvío del formulario
            return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
    
    # Verificar si se puede subir imágenes
    puede_subir_imagenes = solicitud.estado == 'borrador'
    
    # Imágenes de referencia de la solicitud
    imagenes_referencia = solicitud.imagenes_referencia.all()
    max_imagenes_referencia = ImagenSolicitudCotizacion.MAX_IMAGENES_POR_SOLICITUD
    
    # Empleados disponibles para copia en notificación a front
    empleados_copia = Empleado.objects.filter(
        Q(area='CALIDAD') | Q(area='FRONTDESK') | Q(area='CARRY IN'),
        activo=True,
        email__isnull=False
    ).exclude(
        email=''
    ).order_by('area', 'nombre_completo')
    
    # Verificar si el usuario actual está en la lista de CC
    usuario_en_lista_cc = False
    if hasattr(request.user, 'empleado') and request.user.empleado:
        usuario_en_lista_cc = empleados_copia.filter(id=request.user.empleado.id).exists()

    # --- Sucursal para mostrar en el encabezado de la solicitud ---
    # Con orden: se obtiene directamente de la FK orden_servicio → sucursal
    sucursal_orden = None
    if solicitud.orden_servicio:
        sucursal_orden = solicitud.orden_servicio.sucursal

    # Sin orden activa: se obtiene del perfil de empleado de quien creó la solicitud.
    # El select_related ya cargó el camino creado_por → empleado → sucursal,
    # por lo que esto no genera queries adicionales.
    sucursal_creador = None
    try:
        sucursal_creador = solicitud.creado_por.empleado.sucursal
    except Exception:
        # El usuario puede no tener perfil de empleado o sucursal asignada — es válido
        pass

    from .utils.cotizacion_items_cliente import (
        solicitud_puede_descargar_pdf_final,
        solicitud_tiene_items_cotizables,
    )
    from config.constants import (
        MOTIVO_RECHAZO_COTIZACION,
        MOTIVOS_RECHAZO_CON_FEEDBACK,
        MOTIVOS_RECHAZO_VIGENCIA_VENCIDA,
    )
    from .utils.sincronizar_rechazo_cotizacion_st import (
        admite_motivo_rechazo_almacen,
        armar_detalle_rechazo_desde_items,
        label_motivo_rechazo,
        orden_admite_cotizacion_st,
        solicitud_requiere_motivo_rechazo_almacen,
        solicitud_requiere_motivo_rechazo_st,
    )
    import json as _json_motivos

    mostrar_modal_motivo_rechazo_st = solicitud_requiere_motivo_rechazo_st(solicitud)
    admite_motivo_rechazo_st = orden_admite_cotizacion_st(solicitud.orden_servicio)

    # Flujo paralelo: rechazo total SIN orden ST → tipificar en SolicitudCotizacion
    mostrar_modal_motivo_rechazo_almacen = solicitud_requiere_motivo_rechazo_almacen(
        solicitud,
    )
    admite_motivo_rechazo_almacen_flag = admite_motivo_rechazo_almacen(solicitud)

    # Valores ya guardados en Cotizacion ST (para precargar "Ver / editar")
    motivo_rechazo_st_actual = ''
    detalle_rechazo_st_actual = ''
    motivo_rechazo_st_etiqueta = ''
    if solicitud.orden_servicio_id and admite_motivo_rechazo_st:
        from servicio_tecnico.models import Cotizacion

        try:
            cotizacion_st_rechazo = Cotizacion.objects.get(
                orden_id=solicitud.orden_servicio_id,
            )
            motivo_rechazo_st_actual = cotizacion_st_rechazo.motivo_rechazo or ''
            detalle_rechazo_st_actual = cotizacion_st_rechazo.detalle_rechazo or ''
            if motivo_rechazo_st_actual:
                motivo_rechazo_st_etiqueta = label_motivo_rechazo(motivo_rechazo_st_actual)
        except Cotizacion.DoesNotExist:
            pass

    # Cabecera Almacén: motivo guardado o prefill desde piezas/servicios
    motivo_rechazo_solicitud_actual = ''
    detalle_rechazo_solicitud_actual = ''
    motivo_rechazo_solicitud_etiqueta = ''
    if admite_motivo_rechazo_almacen_flag:
        motivo_rechazo_solicitud_actual = solicitud.motivo_rechazo or ''
        if motivo_rechazo_solicitud_actual:
            motivo_rechazo_solicitud_etiqueta = label_motivo_rechazo(
                motivo_rechazo_solicitud_actual,
            )
        # EXPLICACIÓN: si aún no hay detalle guardado, armamos resumen de ítems
        detalle_guardado = (solicitud.detalle_rechazo or '').strip()
        if detalle_guardado:
            detalle_rechazo_solicitud_actual = detalle_guardado
        else:
            detalle_rechazo_solicitud_actual = armar_detalle_rechazo_desde_items(
                solicitud,
            )

    context = {
        'solicitud': solicitud,
        'info_orden': info_orden,
        'piezas_sugeridas_diagnostico': piezas_sugeridas_diagnostico,
        'titulo': f'Solicitud {solicitud.numero_solicitud}',
        'puede_subir_imagenes': puede_subir_imagenes,
        'max_imagenes_por_linea': ImagenLineaCotizacion.MAX_IMAGENES_POR_LINEA,
        'imagenes_referencia': imagenes_referencia,
        'max_imagenes_referencia': max_imagenes_referencia,
        'empleados_copia': empleados_copia,
        'usuario_en_lista_cc': usuario_en_lista_cc,
        # Sucursal del encabezado: con orden → de la orden; sin orden → del creador
        'sucursal_orden': sucursal_orden,
        'sucursal_creador': sucursal_creador,
        # Datos para el modal "Enviar Cotización al Cliente"
        'gama_equipo': gama_equipo,
        'costo_mano_obra': costo_mano_obra,
        'email_cliente_modal': email_cliente_modal,
        'asunto_correo_modal': asunto_correo_modal,
        # Configuración de profit serializada como JSON para inyectarla en el
        # template y leerla desde TypeScript. Los valores vienen del .env
        # (nunca del código fuente), así que no aparecen en el repositorio.
        'profit_config_json': _serializar_profit_config(),
        'costeo_reac_config_json': _serializar_costeo_reacondicionado_config(),
        # Opciones del dropdown "Agregar Servicio Adicional" (precios desde constants.py)
        'servicios_adicionales_opciones': _opciones_servicios_adicionales(),
        # Modal motivo catálogo ST
        'mostrar_modal_motivo_rechazo_st': mostrar_modal_motivo_rechazo_st,
        'admite_motivo_rechazo_st': admite_motivo_rechazo_st,
        'motivos_rechazo_cotizacion': MOTIVO_RECHAZO_COTIZACION,
        'email_cliente_rechazo': email_cliente_modal,
        'motivos_rechazo_con_feedback_json': _json_motivos.dumps(
            sorted(MOTIVOS_RECHAZO_CON_FEEDBACK | MOTIVOS_RECHAZO_VIGENCIA_VENCIDA)
        ),
        'motivo_rechazo_st_actual': motivo_rechazo_st_actual,
        'detalle_rechazo_st_actual': detalle_rechazo_st_actual,
        'motivo_rechazo_st_etiqueta': motivo_rechazo_st_etiqueta,
        # Modal motivo cabecera Almacén (sin orden / FL-)
        'mostrar_modal_motivo_rechazo_almacen': mostrar_modal_motivo_rechazo_almacen,
        'admite_motivo_rechazo_almacen': admite_motivo_rechazo_almacen_flag,
        'motivo_rechazo_solicitud_actual': motivo_rechazo_solicitud_actual,
        'detalle_rechazo_solicitud_actual': detalle_rechazo_solicitud_actual,
        'motivo_rechazo_solicitud_etiqueta': motivo_rechazo_solicitud_etiqueta,
    }

    context['puede_descargar_pdf_final'] = solicitud_puede_descargar_pdf_final(solicitud)
    context['tiene_items_cotizables'] = solicitud_tiene_items_cotizables(solicitud)

    return render(request, 'almacen/cotizaciones/detalle_solicitud.html', context)


@login_required
@permission_required_with_message('almacen.change_solicitudcotizacion')
def enviar_solicitud_cliente(request, pk):
    """
    Cambiar estado de la solicitud a 'enviada_front'.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta acción marca la solicitud como lista para que Recepción la revise.
    Recepción podrá entonces enviarla al cliente y registrar las respuestas.
    
    Requisitos:
    - Estado debe ser 'borrador'
    - Debe tener al menos una línea
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if request.method == 'POST':
        if solicitud.enviar_a_front():
            messages.success(
                request,
                f'Solicitud {solicitud.numero_solicitud} enviada a Front. '
                'Recepción puede ahora revisarla y compartirla con el cliente.'
            )
        else:
            messages.error(
                request,
                'No se puede enviar la solicitud. Verifica que esté en estado '
                'borrador y tenga al menos una línea.'
            )
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
@permission_required_with_message('almacen.change_solicitudcotizacion')
def enviar_solicitud_a_cliente(request, pk):
    """
    Cambiar estado de la solicitud de 'enviada_front' a 'enviada_cliente'.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta acción la realiza Recepción (Front) cuando ya compartió la cotización
    con el cliente final. A partir de este momento:
    - El cliente puede aprobar o rechazar cada línea
    - Ya no se pueden editar líneas ni reenviar notificaciones
    - Aparecen los botones de aprobar/rechazar en el detalle
    
    Requisitos:
    - Estado debe ser 'enviada_front'
    - Debe tener al menos una línea
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if request.method == 'POST':
        if solicitud.enviar_a_cliente():
            messages.success(
                request,
                f'Solicitud {solicitud.numero_solicitud} enviada al cliente. '
                'Ahora se pueden registrar las respuestas de aprobación/rechazo.'
            )
        else:
            messages.error(
                request,
                'No se puede enviar al cliente. Verifica que la solicitud esté '
                'en estado "Enviada a Front" y tenga al menos una línea.'
            )
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


# =============================================================================
# NUEVAS VISTAS: ENVÍO DE COTIZACIÓN DIRECTAMENTE AL CLIENTE FINAL
# =============================================================================

@login_required
@permission_required_with_message('almacen.change_solicitudcotizacion')
@require_http_methods(["POST"])
def api_enviar_cotizacion_cliente(request, pk):
    """
    Envía la cotización directamente al cliente final por correo con PDF adjunto.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista es el corazón del nuevo modal "Enviar Cotización al Cliente".
    Recibe los parámetros del modal (tipo de servicio, modo de agrupación,
    email del cliente, etc.), genera los PDF necesarios y los envía al cliente.

    Flujo:
    1. Valida los datos del POST (tipo_servicio, email_cliente, modo_agrupacion)
    2. Cambia el estado de la solicitud a 'enviada_cliente'
    3. Agrupa los ítems según el modo elegido (todo junto / piezas vs servicios / etc.)
    4. Para cada grupo, dispara una tarea Celery que genera el PDF y lo envía por email
    5. Si hay orden de ST vinculada, cambia su estado a 'cotizacion'
       («Esperando Aprobación Cliente») — este es el momento real de espera al cliente
    6. Retorna JsonResponse inmediato (el email se procesa en background)

    Args:
        request: HttpRequest POST con los datos del modal.
        pk     : ID de la SolicitudCotizacion.

    Returns:
        JsonResponse con {'success': bool, 'mensaje': str}
    """
    import json as _json
    from .tasks import enviar_cotizacion_cliente_task
    from config.paises_config import get_pais_actual

    try:
        solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)

        # --- 1. VALIDACIÓN DE ESTADO ---
        # La solicitud debe estar en un estado que permita el envío al cliente
        estados_validos = ['enviada_front', 'enviada_cliente', 'parcialmente_aprobada']
        if solicitud.estado not in estados_validos:
            return JsonResponse({
                'success': False,
                'error': f'Estado "{solicitud.get_estado_display()}" no permite envío al cliente. '
                         f'La solicitud debe estar en estado "Enviada a Front", "Enviada al Cliente" '
                         f'o "Parcialmente Aprobada".'
            })

        # --- 2. EXTRAER PARÁMETROS DEL POST ---
        modo_cotizacion = request.POST.get('modo_cotizacion', 'reparacion')
        tipo_servicio  = request.POST.get('tipo_servicio', 'estandar')
        email_cliente  = request.POST.get('email_cliente', '').strip()
        modo_agrupacion = request.POST.get('modo_agrupacion', 'todo_junto')
        mensaje_personalizado = request.POST.get('mensaje_personalizado', '').strip()
        # El descuento de diagnóstico ya no aplica: reparación se abona completa.
        incluir_descuento = False

        # Asunto personalizado del correo.
        # Si el usuario lo dejó vacío o con el prefijo por defecto sin texto adicional,
        # la tarea lo generará automáticamente con el perfil y folio.
        asunto_correo = request.POST.get('asunto_correo', '').strip()
        # Normalizar: si solo enviaron el prefijo vacío, tratar como sin asunto personalizado
        from .utils.cotizacion_email_context import es_asunto_correo_vacio
        if es_asunto_correo_vacio(asunto_correo):
            asunto_correo = ''

        # Mano de obra override — el campo es informativo, se envía como 0 desde el frontend.
        # Se mantiene la lectura por compatibilidad con llamadas directas a la API.
        mano_obra_raw = request.POST.get('mano_de_obra_override', '')
        mano_de_obra_override = None
        if mano_obra_raw:
            try:
                val = float(mano_obra_raw)
                mano_de_obra_override = val if val > 0 else None
            except ValueError:
                pass

        # Emails con copia (CC) — pueden venir múltiples campos con el mismo nombre
        copia_empleados = request.POST.getlist('copia_empleados')

        # --- 3. VALIDAR EMAIL DEL CLIENTE ---
        if not email_cliente:
            return JsonResponse({'success': False, 'error': 'El email del cliente es requerido.'})

        # Validación simple de formato email
        import re as _re
        if not _re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email_cliente):
            return JsonResponse({'success': False, 'error': f'El email "{email_cliente}" no tiene formato válido.'})

        # --- 4a. MODO REACONDICIONADO (propuesta de equipo certificado) ---
        if modo_cotizacion == 'reacondicionado':
            datos_post = _extraer_datos_reacondicionado_post(request.POST)
            ok, resultado = _validar_y_calcular_reacondicionado(datos_post)
            if not ok:
                return JsonResponse({'success': False, 'error': resultado})

            if solicitud.estado == 'enviada_front':
                solicitud.enviar_a_cliente()

            _guardar_snapshot_reacondicionado(
                solicitud,
                resultado['datos_equipo'],
                resultado['costeo'],
                resultado['dias_front_desk'],
                resultado['costo_proveedor'],
            )

            ok_linea, error_linea = _crear_o_actualizar_linea_reacondicionado(
                solicitud,
                resultado['datos_equipo'],
                resultado['costeo'],
                resultado['costo_proveedor'],
            )
            if not ok_linea:
                return JsonResponse({'success': False, 'error': error_linea})

            _db = get_pais_actual()['db_alias']
            enviar_cotizacion_cliente_task.delay(
                solicitud_id=solicitud.pk,
                email_cliente=email_cliente,
                copia_empleados=copia_empleados,
                tipo_servicio='reacondicionado',
                items=[],
                titulo_propuesta='Propuesta de Equipo Reacondicionado — Certificado SIC',
                incluir_descuento_diagnostico=False,
                mano_de_obra_override=None,
                mensaje_personalizado=mensaje_personalizado,
                asunto_correo=asunto_correo,
                usuario_id=request.user.pk,
                db_alias=_db,
                modo_cotizacion='reacondicionado',
                datos_equipo_reac=resultado['datos_equipo'],
                costeo_reac=resultado['costeo'],
            )
            # Al enviar al cliente: ST pasa a «Esperando Aprobación Cliente»
            _actualizar_estado_st_esperando_aprobacion_cliente(solicitud, usuario=request.user)
            return JsonResponse({
                'success': True,
                'mensaje': (
                    f'Propuesta de equipo reacondicionado enviada a {email_cliente}. '
                    'El correo se procesa en segundo plano.'
                ),
                'grupos_enviados': 1,
            })

        # --- 4. VALIDAR TIPO DE SERVICIO (modo reparación) ---
        from .utils.parametros_cotizador import obtener_profit_config
        tipos_validos = list(obtener_profit_config().keys())
        if tipo_servicio not in tipos_validos:
            return JsonResponse({'success': False, 'error': f'Tipo de servicio "{tipo_servicio}" no válido.'})

        # --- 5. CAMBIAR ESTADO A 'enviada_cliente' (si aún no lo está) ---
        if solicitud.estado == 'enviada_front':
            # Avanzar el estado usando el método del modelo
            solicitud.enviar_a_cliente()

        # Snapshot del perfil de profit (los precios se congelan en la primera
        # respuesta del cliente: aprobar o rechazar)
        if not solicitud.fecha_precios_cliente:
            solicitud.tipo_servicio_cliente = tipo_servicio
            # Siempre False: ya no se descuenta diagnóstico en reparación
            solicitud.incluir_descuento_diagnostico_cliente = False
            solicitud.save(update_fields=[
                'tipo_servicio_cliente',
                'incluir_descuento_diagnostico_cliente',
            ])

        # --- 6. CONSTRUIR GRUPOS DE ÍTEMS (solo pendiente + aprobada; excluye rechazadas) ---
        from .utils.cotizacion_items_cliente import (
            construir_grupos_cotizacion,
            obtener_lineas_cotizables,
            obtener_servicios_cotizables,
            serializar_linea_cotizacion,
            serializar_servicio_cotizacion,
            solicitud_tiene_items_cotizables,
        )

        if not solicitud_tiene_items_cotizables(solicitud):
            return JsonResponse({
                'success': False,
                'error': (
                    'No hay piezas ni servicios pendientes o aprobados para cotizar. '
                    'Las líneas rechazadas no se incluyen.'
                ),
            })

        items_piezas_todos = [
            serializar_linea_cotizacion(l) for l in obtener_lineas_cotizables(solicitud)
        ]
        items_servicios = [
            serializar_servicio_cotizacion(s) for s in obtener_servicios_cotizables(solicitud)
        ]
        grupos = construir_grupos_cotizacion(
            items_piezas_todos, items_servicios, modo_agrupacion
        )

        if not grupos:
            return JsonResponse({
                'success': False,
                'error': (
                    'No hay piezas ni servicios pendientes o aprobados para cotizar. '
                    'Las líneas rechazadas no se incluyen.'
                ),
            })

        # --- 8. DISPARAR TAREA CELERY PARA CADA GRUPO ---
        _db = get_pais_actual()['db_alias']
        usuario_id = request.user.pk

        for grupo in grupos:
            enviar_cotizacion_cliente_task.delay(
                solicitud_id=solicitud.pk,
                email_cliente=email_cliente,
                copia_empleados=copia_empleados,
                tipo_servicio=tipo_servicio,
                items=grupo['items'],
                titulo_propuesta=grupo['titulo'],
                incluir_descuento_diagnostico=incluir_descuento,
                mano_de_obra_override=mano_de_obra_override,
                mensaje_personalizado=mensaje_personalizado,
                asunto_correo=asunto_correo,
                usuario_id=usuario_id,
                db_alias=_db,
            )

        # Al enviar al cliente: orden ST → «Esperando Aprobación Cliente»
        # (si hay orden vinculada y aún no estaba en ese estado)
        _actualizar_estado_st_esperando_aprobacion_cliente(solicitud, usuario=request.user)

        # Mensaje de éxito según cuántos grupos se enviaron
        n_grupos = len(grupos)
        if n_grupos == 1:
            mensaje = f'Cotización enviada al cliente {email_cliente}. El correo se procesa en segundo plano.'
        else:
            mensaje = (
                f'{n_grupos} cotizaciones separadas enviadas a {email_cliente}. '
                f'Los correos se procesan en segundo plano.'
            )

        return JsonResponse({'success': True, 'mensaje': mensaje, 'grupos_enviados': n_grupos})

    except Exception as e:
        import traceback as _tb
        logger.error(f"[API_COTIZACION_CLIENTE] Error: {e}\n{_tb.format_exc()}")
        return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}'})


@login_required
@permission_required_with_message('almacen.view_solicitudcotizacion')
@require_http_methods(["GET"])
@xframe_options_sameorigin
def preview_pdf_cotizacion(request, pk):
    """
    Genera y devuelve un PDF de previsualización para el modal de envío al cliente.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista es la que llama el botón "Ver Previsualización" del modal.
    Genera el PDF con los parámetros actuales del modal (tipo de servicio,
    modo de agrupación) y lo devuelve directamente como respuesta PDF
    para mostrarlo en el iframe del modal.

    Args:
        request: HttpRequest GET con parámetros:
                 - tipo_servicio: str
                 - modo_agrupacion: str
                 - grupo_idx: int (0=primero, 1=segundo — para modo separado)
        pk     : ID de la SolicitudCotizacion.

    Returns:
        HttpResponse con content_type='application/pdf'
    """
    from django.http import HttpResponse
    from .utils.pdf_cotizacion_cliente import PDFCotizacionCliente
    from config.paises_config import get_pais_actual

    try:
        solicitud = get_object_or_404(
            SolicitudCotizacion.objects.select_related(
                'orden_servicio',
                'orden_servicio__detalle_equipo',
                'orden_servicio__sucursal',
                'creado_por',
                'creado_por__empleado__sucursal',
            ).prefetch_related('lineas__producto', 'servicios_adicionales'),
            pk=pk
        )

        tipo_servicio     = request.GET.get('tipo_servicio', 'estandar')
        modo_cotizacion   = request.GET.get('modo_cotizacion', 'reparacion')
        modo_agrupacion   = request.GET.get('modo_agrupacion', 'todo_junto')
        grupo_idx         = int(request.GET.get('grupo_idx', 0))

        _pais = get_pais_actual()

        # Preview de propuesta reacondicionada (motor distinto al de reparación)
        if modo_cotizacion == 'reacondicionado':
            from .utils.pdf_cotizacion_reacondicionado import PDFCotizacionReacondicionado

            datos_post = {
                'costo_proveedor': request.GET.get('reac_costo_proveedor', ''),
                'dias_front_desk': request.GET.get('reac_dias_front_desk', '1'),
                'marca': request.GET.get('reac_marca', ''),
                'modelo': request.GET.get('reac_modelo', ''),
                'procesador': request.GET.get('reac_procesador', ''),
                'ram': request.GET.get('reac_ram', ''),
                'sistema_operativo': request.GET.get('reac_sistema_operativo', ''),
                'incluye_cargador': request.GET.get('reac_incluye_cargador', '0'),
                'especificaciones': request.GET.get('reac_especificaciones', ''),
            }
            datos_post['incluye_cargador'] = datos_post['incluye_cargador'] == '1'
            ok, resultado = _validar_y_calcular_reacondicionado(datos_post)
            if not ok:
                return HttpResponse(resultado.encode(), content_type='text/plain', status=400)

            generador_reac = PDFCotizacionReacondicionado(
                solicitud=solicitud,
                datos_equipo=resultado['datos_equipo'],
                costeo=resultado['costeo'],
                pais_config=_pais,
            )
            resultado_pdf = generador_reac.generar_pdf()
            if not resultado_pdf['success']:
                return HttpResponse(
                    f'Error al generar PDF: {resultado_pdf.get("error", "desconocido")}'.encode(),
                    content_type='text/plain',
                    status=500,
                )
            pdf_bytes = resultado_pdf['buffer'].getvalue()
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = (
                f'inline; filename="{resultado_pdf["nombre_archivo"]}"'
            )
            return response

        from .utils.cotizacion_items_cliente import (
            construir_grupos_cotizacion,
            obtener_lineas_cotizables,
            obtener_servicios_cotizables,
            serializar_linea_cotizacion,
            serializar_servicio_cotizacion,
        )

        items_todos_piezas = [
            serializar_linea_cotizacion(l) for l in obtener_lineas_cotizables(solicitud)
        ]
        items_servicios = [
            serializar_servicio_cotizacion(s) for s in obtener_servicios_cotizables(solicitud)
        ]
        grupos = construir_grupos_cotizacion(
            items_todos_piezas, items_servicios, modo_agrupacion
        )

        if not grupos:
            return HttpResponse(
                b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n'
                b'2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n'
                b'3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n'
                b'xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n'
                b'0000000058 00000 n \n0000000115 00000 n \n'
                b'trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF',
                content_type='application/pdf'
            )

        # Elegir el grupo según el índice (para modo separado)
        grupo_idx = min(grupo_idx, len(grupos) - 1)
        grupo = grupos[grupo_idx]

        generador = PDFCotizacionCliente(
            solicitud=solicitud,
            tipo_servicio=tipo_servicio,
            items=grupo['items'],
            titulo_propuesta=grupo['titulo'],
            incluir_descuento_diagnostico=False,
            pais_config=_pais,
        )

        resultado = generador.generar_pdf()
        if not resultado['success']:
            return HttpResponse(
                f'Error al generar PDF: {resultado.get("error", "desconocido")}'.encode(),
                content_type='text/plain',
                status=500
            )

        pdf_bytes = resultado['buffer'].getvalue()
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="{resultado["nombre_archivo"]}"'
        )
        return response

    except Exception as e:
        import traceback as _tb
        logger.error(f"[PREVIEW_PDF_COTIZACION] Error: {e}\n{_tb.format_exc()}")
        return HttpResponse(f'Error: {str(e)}'.encode(), content_type='text/plain', status=500)


@login_required
@permission_required_with_message('almacen.view_solicitudcotizacion')
@require_http_methods(["GET"])
def descargar_pdf_cotizacion_final(request, pk):
    """
    Genera y descarga el PDF final con piezas/servicios aceptados y precios persistidos.

    Si solo se aceptó el equipo reacondicionado (línea P0125), genera el PDF de
    propuesta reacondicionada en lugar del PDF de piezas de reparación.

    Args:
        request: HttpRequest GET.
        pk     : ID de la SolicitudCotizacion.

    Returns:
        HttpResponse PDF inline o error en texto plano.
    """
    from django.http import HttpResponse
    from .utils.pdf_cotizacion_cliente import PDFCotizacionCliente
    from .utils.cotizacion_items_cliente import (
        construir_items_cotizacion_final,
        solicitud_puede_descargar_pdf_final,
        solicitud_pdf_final_es_solo_reacondicionado,
        extraer_datos_equipo_desde_solicitud,
    )
    from .utils.cotizacion_precios_cliente import obtener_tipo_servicio_solicitud
    from config.paises_config import get_pais_actual

    try:
        solicitud = get_object_or_404(
            SolicitudCotizacion.objects.select_related(
                'orden_servicio',
                'orden_servicio__detalle_equipo',
            ).prefetch_related('lineas__producto', 'servicios_adicionales'),
            pk=pk,
        )

        if not solicitud_puede_descargar_pdf_final(solicitud):
            return HttpResponse(
                'No hay ítems aceptados con precios guardados para generar el PDF final.'.encode(),
                content_type='text/plain',
                status=400,
            )

        _pais = get_pais_actual()

        # PDF final de equipo reacondicionado (solo línea P0125 aceptada)
        if solicitud_pdf_final_es_solo_reacondicionado(solicitud):
            from .utils.pdf_cotizacion_reacondicionado import PDFCotizacionReacondicionado
            from .utils.cotizacion_items_cliente import obtener_lineas_aceptadas_final

            linea_reac = obtener_lineas_aceptadas_final(solicitud).filter(
                es_linea_reacondicionado=True,
            ).first()

            generador_reac = PDFCotizacionReacondicionado(
                solicitud=solicitud,
                datos_equipo=extraer_datos_equipo_desde_solicitud(solicitud),
                costeo=solicitud.resultado_costeo_reac or {},
                pais_config=_pais,
                opcion_pago_aceptada=linea_reac.opcion_pago_reac if linea_reac else 'contado',
                modo_final=True,
            )
            resultado = generador_reac.generar_pdf()
            if not resultado['success']:
                return HttpResponse(
                    f'Error al generar PDF: {resultado.get("error", "desconocido")}'.encode(),
                    content_type='text/plain',
                    status=500,
                )
            pdf_bytes = resultado['buffer'].getvalue()
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = (
                f'inline; filename="{resultado["nombre_archivo"]}"'
            )
            return response

        items = construir_items_cotizacion_final(solicitud)
        if not items:
            return HttpResponse(
                'No se encontraron líneas aceptadas con precio al cliente.'.encode(),
                content_type='text/plain',
                status=400,
            )

        tipo_servicio = obtener_tipo_servicio_solicitud(solicitud)

        generador = PDFCotizacionCliente(
            solicitud=solicitud,
            tipo_servicio=tipo_servicio,
            items=items,
            incluir_descuento_diagnostico=False,
            pais_config=_pais,
            modo_final=True,
        )

        resultado = generador.generar_pdf()
        if not resultado['success']:
            return HttpResponse(
                f'Error al generar PDF: {resultado.get("error", "desconocido")}'.encode(),
                content_type='text/plain',
                status=500,
            )

        pdf_bytes = resultado['buffer'].getvalue()
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="{resultado["nombre_archivo"]}"'
        )
        return response

    except Exception as e:
        import traceback as _tb
        logger.error(f"[PDF_COTIZACION_FINAL] Error: {e}\n{_tb.format_exc()}")
        return HttpResponse(f'Error: {str(e)}'.encode(), content_type='text/plain', status=500)


@login_required
@permission_required_with_message('almacen.change_solicitudcotizacion')
@require_http_methods(["POST"])
def notificar_front(request, pk):
    """
    Enviar notificación de cotización a recepción (FRONTDESK) por correo.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista reemplaza el antiguo "Enviar a Cliente". En lugar de cambiar
    solo el estado, ahora envía un correo HTML a los empleados de FRONTDESK
    con el detalle de la cotización (piezas, costos, imágenes) para que
    recepción la comparta con el cliente.
    
    Flujo:
    1. Valida que la solicitud esté en borrador o enviada_front y tenga líneas
    2. Cambia el estado de la solicitud a 'enviada_front' (si estaba en borrador)
    3. Sincroniza la orden ST a 'cotizacion_recibida_proveedor' si aplica
    4. Dispara la tarea Celery para enviar el correo en segundo plano
    5. Devuelve JsonResponse inmediato
    
    Args:
        request: HttpRequest con datos POST del formulario
        pk: ID de la SolicitudCotizacion
    
    Returns:
        JsonResponse — el correo se procesa en background via Celery
    """
    from .tasks import notificar_front_cotizacion_task
    from .utils.sincronizar_estado_st import sincronizar_estado_st_al_notificar_front
    
    try:
        solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
        
        # Validar estado: permitir envío inicial (borrador) o reenvío (enviada_front)
        if solicitud.estado not in ['borrador', 'enviada_front']:
            return JsonResponse({
                'success': False,
                'error': 'Solo se puede notificar cuando la solicitud está en borrador o ya enviada a front.'
            }, status=400)
        
        # Validar que tenga al menos una línea
        if not solicitud.lineas.exists():
            return JsonResponse({
                'success': False,
                'error': 'La solicitud debe tener al menos una línea para notificar.'
            }, status=400)
        
        # Obtener destinatarios del formulario (los seleccionados en el modal)
        copia_empleados = request.POST.getlist('copia_empleados', [])
        copia_tecnico = request.POST.getlist('copia_tecnico', [])
        
        # Los destinatarios principales son los que el usuario seleccionó
        destinatarios = list(set(copia_empleados + copia_tecnico))
        
        if not destinatarios:
            return JsonResponse({
                'success': False,
                'error': 'Debes seleccionar al menos un destinatario.'
            }, status=400)
        
        mensaje_personalizado = request.POST.get('mensaje_personalizado', '').strip()
        
        # Cambiar estado de la solicitud a 'enviada_front' solo si está en borrador
        if solicitud.estado == 'borrador':
            solicitud.enviar_a_front(usuario=request.user)

        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Tras avisar a Front, la orden vinculada en ST pasa a
        # «Se Recibe Cotización de Proveedores» (si aún no avanzó más adelante).
        # También se intenta en reenvíos por si la orden se vinculó después.
        sincronizar_estado_st_al_notificar_front(
            solicitud,
            usuario=request.user,
        )
        
        # Disparar tarea Celery
        usuario_id = request.user.pk if request.user.is_authenticated else None
        from config.paises_config import get_pais_actual

        tarea = notificar_front_cotizacion_task.delay(
            solicitud_id=pk,
            destinatarios=destinatarios,
            mensaje_personalizado=mensaje_personalizado,
            usuario_id=usuario_id,
            db_alias=get_pais_actual()['db_alias'],
        )
        
        return JsonResponse({
            'success': True,
            'message': (
                f'Notificación en proceso de envío a {len(destinatarios)} '
                f'destinatario(s).'
            ),
            'data': {
                'task_id': tarea.id,
                'destinatario': ', '.join(destinatarios),
                'solicitud': solicitud.numero_solicitud,
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'Error al procesar la solicitud: {str(e)}'
        }, status=500)


@login_required
@permission_required_with_message('almacen.change_lineacotizacion')
def responder_linea_cotizacion(request, solicitud_pk, linea_pk):
    """
    Registrar la respuesta del cliente para una línea específica.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista permite a Recepción registrar si el cliente aprobó o
    rechazó una línea específica de la cotización.
    
    Si el cliente aprueba: La línea queda marcada para generar compra.
    Si el cliente rechaza: Se debe indicar el motivo.
    
    Después de cada respuesta, se actualiza automáticamente el estado
    general de la solicitud.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=solicitud_pk)
    linea = get_object_or_404(LineaCotizacion, pk=linea_pk, solicitud=solicitud)
    
    # Solo se puede responder si la solicitud está enviada
    if solicitud.estado not in ['enviada_cliente', 'parcialmente_aprobada']:
        messages.error(
            request,
            'Solo se pueden registrar respuestas en solicitudes enviadas al cliente.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud_pk)
    
    if request.method == 'POST':
        form = RespuestaLineaCotizacionForm(request.POST)
        
        if form.is_valid():
            decision = form.cleaned_data['decision']
            motivo = form.cleaned_data.get('motivo_rechazo', '')
            
            if decision == 'aprobar':
                if linea.es_linea_reacondicionado:
                    opcion = form.cleaned_data.get('opcion_pago_reac', '')
                    if not opcion:
                        messages.error(
                            request,
                            'Debes seleccionar la forma de pago del equipo reacondicionado.',
                        )
                        return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud_pk)
                    aprobado = linea.aprobar(opcion_pago_reac=opcion)
                else:
                    aprobado = linea.aprobar()
                if aprobado:
                    messages.success(
                        request,
                        f'Línea #{linea.numero_linea} aprobada por el cliente.'
                    )
                else:
                    if linea.es_linea_reacondicionado:
                        messages.error(
                            request,
                            'No se pudo aprobar el equipo reacondicionado. '
                            'Verifica el costeo guardado y la forma de pago.',
                        )
                    else:
                        messages.error(request, 'No se pudo aprobar la línea.')
            else:  # rechazar
                if linea.rechazar(motivo=motivo):
                    messages.warning(
                        request,
                        f'Línea #{linea.numero_linea} rechazada por el cliente.'
                    )
                    solicitud.refresh_from_db()
                    if solicitud.estado == 'totalmente_rechazada':
                        from almacen.utils.sincronizar_rechazo_cotizacion_st import (
                            mensaje_flash_tras_rechazo_total,
                        )
                        messages.info(
                            request,
                            mensaje_flash_tras_rechazo_total(solicitud),
                        )
                else:
                    messages.error(request, 'No se pudo rechazar la línea.')
        else:
            messages.error(request, 'Por favor corrige los errores.')
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud_pk)


@login_required
@permission_required_with_message('almacen.change_lineacotizacion')
def aprobar_todas_lineas(request, pk):
    """
    Aprobar todas las líneas pendientes de una solicitud.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Atajo para cuando el cliente aprueba toda la cotización.
    En lugar de aprobar línea por línea, se aprueban todas a la vez.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if request.method == 'POST':
        lineas_pendientes = solicitud.lineas.filter(
            estado_cliente='pendiente',
            es_linea_reacondicionado=False,
        )
        aprobadas = 0
        
        for linea in lineas_pendientes:
            if linea.aprobar():
                aprobadas += 1
        
        if aprobadas > 0:
            messages.success(
                request,
                f'Se aprobaron {aprobadas} línea(s) de la cotización.'
            )
        reac_pendientes = solicitud.lineas.filter(
            estado_cliente='pendiente',
            es_linea_reacondicionado=True,
        ).count()
        if reac_pendientes > 0:
            messages.info(
                request,
                f'Quedan {reac_pendientes} equipo(s) reacondicionado(s) pendiente(s). '
                'Apruébalos uno por uno para elegir la forma de pago.',
            )
        elif aprobadas == 0:
            messages.info(request, 'No había líneas pendientes por aprobar.')
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
@permission_required_with_message('almacen.change_lineacotizacion')
def rechazar_todas_lineas(request, pk):
    """
    Rechazar todas las líneas pendientes de una solicitud.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Atajo para marcar todas las líneas pendientes como rechazadas
    (texto libre por línea, igual que rechazar una sola).

    Cuando el estado pase a ``totalmente_rechazada``, al volver al detalle
    se abrirá el modal de motivo de catálogo ST (si aún no está registrado).
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)

    if request.method == 'POST':
        motivo = request.POST.get('motivo', 'Rechazado por el cliente')
        lineas_pendientes = solicitud.lineas.filter(estado_cliente='pendiente')
        rechazadas = 0

        for linea in lineas_pendientes:
            if linea.rechazar(motivo=motivo):
                rechazadas += 1

        if rechazadas > 0:
            messages.warning(
                request,
                f'Se rechazaron {rechazadas} línea(s) de la cotización.',
            )
            solicitud.refresh_from_db()
            if solicitud.estado == 'totalmente_rechazada':
                from almacen.utils.sincronizar_rechazo_cotizacion_st import (
                    mensaje_flash_tras_rechazo_total,
                )
                messages.info(
                    request,
                    mensaje_flash_tras_rechazo_total(solicitud),
                )
        else:
            messages.info(request, 'No había líneas pendientes por rechazar.')

    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
@permission_required_with_message('almacen.change_lineacotizacion')
def registrar_motivo_rechazo_st(request, pk):
    """
    Registra motivo/detalle de catálogo ST tras un rechazo total.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Se llama desde el modal que aparece solo cuando la solicitud está
    en ``totalmente_rechazada`` y aún falta `Cotizacion.motivo_rechazo`.

    No vuelve a rechazar líneas: solo escribe la cabecera ST y, si el
    checkbox lo pide, encola el correo de feedback.
    """
    from almacen.utils.sincronizar_rechazo_cotizacion_st import (
        motivo_rechazo_es_valido,
        procesar_feedback_rechazo_desde_almacen,
        sincronizar_cabecera_rechazo_st,
        label_motivo_rechazo,
    )

    solicitud = get_object_or_404(
        SolicitudCotizacion.objects.select_related(
            'orden_servicio',
            'orden_servicio__detalle_equipo',
        ),
        pk=pk,
    )

    if request.method != 'POST':
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    if solicitud.estado != 'totalmente_rechazada':
        messages.error(
            request,
            'Solo puedes registrar el motivo de catálogo ST cuando la '
            'solicitud está totalmente rechazada.',
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    motivo_clave = (request.POST.get('motivo_rechazo') or '').strip()
    detalle_rechazo = (request.POST.get('detalle_rechazo') or '').strip()

    if not motivo_rechazo_es_valido(motivo_clave):
        messages.error(
            request,
            'Debes seleccionar un motivo de rechazo del catálogo.',
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    # Si ya había motivo, igual permitimos actualizar (reabrir modal manual).
    empleado_actual = getattr(request.user, 'empleado', None)
    cotizacion = sincronizar_cabecera_rechazo_st(
        solicitud,
        motivo_clave=motivo_clave,
        detalle_rechazo=detalle_rechazo,
        empleado=empleado_actual,
    )
    if cotizacion is None:
        messages.warning(
            request,
            'No se pudo guardar el motivo en ST (sin orden válida o es venta mostrador).',
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    label = label_motivo_rechazo(motivo_clave)
    messages.success(
        request,
        f'Motivo de rechazo registrado en ST: {label}.',
    )

    enviar_feedback = request.POST.get('enviar_feedback') in (
        'on', '1', 'true', 'True',
    )
    resultado_fb = procesar_feedback_rechazo_desde_almacen(
        solicitud,
        motivo_clave,
        enviar_feedback=enviar_feedback,
        empleado=empleado_actual,
        usuario_id=request.user.pk if request.user.is_authenticated else None,
    )
    if enviar_feedback and resultado_fb.get('enviado'):
        messages.success(request, f"📧 {resultado_fb['mensaje']}")
    elif enviar_feedback and resultado_fb.get('mensaje'):
        messages.warning(request, resultado_fb['mensaje'])

    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
@permission_required_with_message('almacen.change_lineacotizacion')
def registrar_motivo_rechazo_solicitud(request, pk):
    """
    Registra motivo/detalle de rechazo en la cabecera de Almacén (sin orden ST).

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cuando la cotización queda ``totalmente_rechazada`` sin orden vinculada
    (o con orden FL- venta_mostrador), tipificamos en SolicitudCotizacion
    con el mismo catálogo que ST, pero:
    - No se crea OrdenServicio
    - No se crea Cotizacion ST
    - No se envía FeedbackCliente (exige orden)

    Args:
        request: POST con motivo_rechazo y detalle_rechazo.
        pk: PK de SolicitudCotizacion.

    Efectos secundarios:
        Actualiza motivo_rechazo / detalle_rechazo de la solicitud.
    """
    from almacen.utils.sincronizar_rechazo_cotizacion_st import (
        admite_motivo_rechazo_almacen,
        guardar_motivo_rechazo_solicitud,
        label_motivo_rechazo,
        motivo_rechazo_es_valido,
    )

    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)

    if request.method != 'POST':
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    if solicitud.estado != 'totalmente_rechazada':
        messages.error(
            request,
            'Solo puedes registrar el motivo cuando la solicitud '
            'está totalmente rechazada.',
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    # EXPLICACIÓN: si hay camino ST, este endpoint no aplica
    if not admite_motivo_rechazo_almacen(solicitud):
        messages.error(
            request,
            'Esta cotización tiene orden de Servicio Técnico: '
            'usa el registro de motivo ST.',
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    motivo_clave = (request.POST.get('motivo_rechazo') or '').strip()
    detalle_rechazo = (request.POST.get('detalle_rechazo') or '').strip()

    if not motivo_rechazo_es_valido(motivo_clave):
        messages.error(
            request,
            'Debes seleccionar un motivo de rechazo del catálogo.',
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    try:
        guardar_motivo_rechazo_solicitud(
            solicitud,
            motivo_clave=motivo_clave,
            detalle=detalle_rechazo,
        )
    except ValueError:
        messages.error(
            request,
            'Debes seleccionar un motivo de rechazo del catálogo.',
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    label = label_motivo_rechazo(motivo_clave)
    messages.success(
        request,
        f'Motivo de rechazo registrado en la cotización: {label}.',
    )
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


# ============================================================================
# VISTAS PARA SERVICIOS ADICIONALES (Venta Mostrador en Cotizaciones)
# ============================================================================

@login_required
@permission_required_with_message('almacen.add_lineaservicioadicional')
def agregar_servicio_adicional(request, solicitud_pk):
    """
    Agregar un servicio adicional a una solicitud de cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista permite agregar servicios de Venta Mostrador (limpieza,
    reinstalación de SO, paquetes, etc.) a una cotización existente.
    
    Los servicios adicionales aparecen debajo de las líneas de cotización
    y el cliente puede aprobarlos/rechazarlos por separado.
    
    Cuando el cliente aprueba y se generan las compras, estos servicios
    se crean automáticamente en el VentaMostrador de la orden.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=solicitud_pk)
    
    # Solo se pueden agregar servicios en estados iniciales
    if solicitud.estado not in ['borrador', 'enviada_front', 'enviada_cliente']:
        messages.error(
            request,
            'No se pueden agregar servicios adicionales en este estado de la solicitud.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud_pk)
    
    if request.method == 'POST':
        form = LineaServicioAdicionalForm(request.POST)
        
        if form.is_valid():
            servicio = form.save(commit=False)
            servicio.solicitud = solicitud
            servicio.save()
            
            messages.success(
                request,
                f'Servicio "{servicio.get_tipo_servicio_display()}" agregado a la cotización.'
            )
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        # GET: redirigir al detalle
        pass
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud_pk)


@login_required
@permission_required_with_message('almacen.delete_lineaservicioadicional')
def eliminar_servicio_adicional(request, solicitud_pk, servicio_pk):
    """
    Eliminar un servicio adicional de una solicitud de cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Elimina un servicio adicional que fue agregado por error o que el
    cliente ya no quiere. Solo se puede eliminar si aún no ha sido
    aprobado/rechazado por el cliente.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=solicitud_pk)
    servicio = get_object_or_404(
        LineaServicioAdicional,
        pk=servicio_pk,
        solicitud=solicitud
    )
    
    # Solo se pueden eliminar servicios pendientes
    if servicio.estado_cliente != 'pendiente':
        messages.error(
            request,
            'No se puede eliminar un servicio que ya fue respondido por el cliente.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud_pk)
    
    if request.method == 'POST':
        nombre_servicio = servicio.get_tipo_servicio_display()
        servicio.delete()
        messages.success(
            request,
            f'Servicio "{nombre_servicio}" eliminado de la cotización.'
        )
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud_pk)


@login_required
@permission_required_with_message('almacen.change_lineaservicioadicional')
def responder_servicio_adicional(request, solicitud_pk, servicio_pk):
    """
    Registrar la respuesta del cliente para un servicio adicional.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Similar a responder_linea_cotizacion, pero para servicios adicionales.
    Permite registrar si el cliente aprobó o rechazó el servicio.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=solicitud_pk)
    servicio = get_object_or_404(
        LineaServicioAdicional,
        pk=servicio_pk,
        solicitud=solicitud
    )
    
    # Solo se puede responder si la solicitud está enviada
    if solicitud.estado not in ['enviada_cliente', 'parcialmente_aprobada']:
        messages.error(
            request,
            'Solo se pueden registrar respuestas en solicitudes enviadas al cliente.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud_pk)
    
    if request.method == 'POST':
        decision = request.POST.get('decision', '')
        motivo = request.POST.get('motivo_rechazo', '')
        
        if decision == 'aprobar':
            if servicio.aprobar():
                messages.success(
                    request,
                    f'Servicio "{servicio.get_tipo_servicio_display()}" aprobado por el cliente.'
                )
            else:
                messages.error(request, 'No se pudo aprobar el servicio.')
        elif decision == 'rechazar':
            if servicio.rechazar(motivo=motivo):
                messages.warning(
                    request,
                    f'Servicio "{servicio.get_tipo_servicio_display()}" rechazado por el cliente.'
                )
            else:
                messages.error(request, 'No se pudo rechazar el servicio.')
        else:
            messages.error(request, 'Decisión no válida.')
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud_pk)


@login_required
@permission_required_with_message('almacen.change_lineaservicioadicional')
def aprobar_todos_servicios(request, pk):
    """
    Aprobar todos los servicios adicionales pendientes de una solicitud.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Atajo para cuando el cliente aprueba todos los servicios adicionales.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if request.method == 'POST':
        servicios_pendientes = solicitud.servicios_adicionales.filter(estado_cliente='pendiente')
        aprobados = 0
        
        for servicio in servicios_pendientes:
            if servicio.aprobar():
                aprobados += 1
        
        if aprobados > 0:
            messages.success(
                request,
                f'Se aprobaron {aprobados} servicio(s) adicional(es).'
            )
        else:
            messages.info(request, 'No había servicios pendientes por aprobar.')
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
@permission_required_with_message('almacen.change_lineaservicioadicional')
def rechazar_todos_servicios(request, pk):
    """
    Rechazar todos los servicios adicionales pendientes de una solicitud.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if request.method == 'POST':
        motivo = request.POST.get('motivo', 'Rechazado por el cliente')
        servicios_pendientes = solicitud.servicios_adicionales.filter(estado_cliente='pendiente')
        rechazados = 0
        
        for servicio in servicios_pendientes:
            if servicio.rechazar(motivo=motivo):
                rechazados += 1
        
        if rechazados > 0:
            messages.warning(
                request,
                f'Se rechazaron {rechazados} servicio(s) adicional(es).'
            )
        else:
            messages.info(request, 'No había servicios pendientes por rechazar.')
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
@permission_required_with_message('almacen.add_compraproducto')
def generar_compras_solicitud(request, pk):
    """
    Genera CompraProducto para las líneas aprobadas y VentaMostrador para servicios adicionales.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Una vez que el cliente ha aprobado las líneas y/o servicios adicionales,
    esta acción crea:
    
    1. CompraProducto para cada línea de pieza aprobada
       - Queda vinculado a la línea de cotización
       - Tiene estado 'pendiente_llegada'
       - Hereda el producto, proveedor, cantidad y costo de la línea
       - Se vincula a la misma orden de servicio
    
    2. VentaMostrador (o actualiza si ya existe) para servicios adicionales aprobados
       - Mapea cada servicio a su campo correspondiente en VentaMostrador
       - Ejemplo: 'limpieza' → incluye_limpieza=True, costo_limpieza=$450
    
    3. En órdenes OOW de reparación (no FL-): crea SeguimientoPieza en ST
       agrupados por proveedor y pasa la orden a «Esperando Llegada de Piezas».
    
    Esto integra el flujo de cotizaciones con el flujo existente de compras
    y ventas mostrador.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if request.method == 'POST':
        # Bloquear compras en modo sin orden activa hasta vincular orden de servicio
        if solicitud.compras_pendientes_sin_orden():
            messages.error(
                request,
                'Debes crear o vincular una orden de servicio antes de generar las compras.'
            )
            return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

        puede_generar_compras = solicitud.puede_generar_compras()
        puede_generar_venta = solicitud.puede_generar_venta_mostrador()
        
        # Validar que haya algo que generar
        if not puede_generar_compras and not puede_generar_venta:
            messages.error(
                request,
                'No hay líneas ni servicios aprobados pendientes de procesar.'
            )
            return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
        
        mensajes_exito = []

        # ====== Piezas en Venta Mostrador (FL- o equipos reacondicionados en OOW) ======
        # Se llama ANTES de generar_compras() porque generar_compras() pasa las líneas
        # a estado 'compra_generada' y este método filtra por estado='aprobada'.
        necesita_piezas_vm = (
            puede_generar_compras
            and solicitud.orden_servicio
            and (
                solicitud.orden_servicio.tipo_servicio == 'venta_mostrador'
                or solicitud.lineas.filter(
                    es_linea_reacondicionado=True,
                    estado_cliente='aprobada',
                ).exists()
            )
        )
        if necesita_piezas_vm:
            n_piezas = solicitud.generar_piezas_venta_mostrador()
            if n_piezas:
                mensajes_exito.append(
                    f'{n_piezas} pieza(s) registrada(s) en sección Venta Mostrador'
                )

        # Generar compras para piezas (CompraProducto para control de inventario/almacén)
        if puede_generar_compras:
            compras = solicitud.generar_compras(usuario=request.user)
            if compras:
                mensajes_exito.append(
                    f'{len(compras)} compra(s) de piezas generada(s)'
                )
            # Mensaje del sync ST (seguimiento de piezas + estado esperando_piezas)
            sync_st = getattr(solicitud, '_resultado_sync_seguimiento_st', None) or {}
            n_seg = sync_st.get('seguimientos_creados', 0)
            if n_seg:
                mensajes_exito.append(
                    f'{n_seg} seguimiento(s) de piezas registrado(s) en Servicio Técnico'
                )
            if sync_st.get('estado_actualizado'):
                mensajes_exito.append(
                    'orden ST actualizada a «Esperando Llegada de Piezas»'
                )
        
        # Generar VentaMostrador para servicios adicionales (paquetes, limpieza, etc.)
        if puede_generar_venta:
            venta = solicitud.generar_venta_mostrador()
            if venta:
                mensajes_exito.append(
                    f'Venta Mostrador creada/actualizada ({venta.folio_venta})'
                )
        
        # Mostrar mensajes al usuario
        if mensajes_exito:
            messages.success(
                request,
                'Se generaron exitosamente: ' + '. '.join(mensajes_exito) + '.'
            )
        else:
            messages.warning(request, 'No se pudieron generar las compras/servicios.')
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
@permission_required_with_message('almacen.change_solicitudcotizacion')
def vincular_orden_solicitud(request, pk):
    """
    Vincular una solicitud de cotización (sin orden activa) a una orden de servicio.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cuando una cotización se crea sin orden activa (el equipo aún no ingresa),
    esta vista permite buscar y vincular la orden de servicio correspondiente
    cuando el equipo ya ingresó formalmente.
    
    BÚSQUEDA:
    - Por número de orden interno (ORD-2025-0001)
    - Por número de orden cliente (OOW-12345, FL-67890)
    - Por service tag / número de serie
    - Por nombre del cliente
    """
    from servicio_tecnico.models import OrdenServicio, DetalleEquipo
    
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if not solicitud.puede_vincular_orden():
        messages.error(
            request,
            'No se puede vincular una orden. La solicitud ya tiene orden activa '
            'o está completada/cancelada.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
    
    resultados = []
    termino_busqueda = ''
    
    if request.method == 'POST':
        termino_busqueda = request.POST.get('busqueda', '').strip()
        orden_pk = request.POST.get('orden_pk', '')
        
        # Si se seleccionó una orden específica, vincularla
        if orden_pk:
            orden = get_object_or_404(OrdenServicio, pk=orden_pk)
            
            try:
                solicitud.vincular_orden(orden)
                messages.success(
                    request,
                    f'Solicitud {solicitud.numero_solicitud} vinculada exitosamente '
                    f'a la orden {orden.numero_orden_interno}.'
                )
            except ValueError as e:
                messages.error(request, str(e))
            
            return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
        
        # Buscar órdenes que coincidan
        if termino_busqueda:
            from django.db.models import Q
            
            # Buscar por número de orden interno, orden cliente, o service tag
            resultados = OrdenServicio.objects.filter(
                Q(numero_orden_interno__icontains=termino_busqueda) |
                Q(detalle_equipo__orden_cliente__icontains=termino_busqueda) |
                Q(detalle_equipo__numero_serie__icontains=termino_busqueda) |
                Q(detalle_equipo__nombre_cliente__icontains=termino_busqueda)
            ).select_related('detalle_equipo').order_by('-fecha_ingreso')[:20]
            
            # Si no hay resultados y tenemos service_tag de la solicitud, buscar por eso
            if not resultados and solicitud.service_tag:
                resultados = OrdenServicio.objects.filter(
                    detalle_equipo__numero_serie__icontains=solicitud.service_tag
                ).select_related('detalle_equipo').order_by('-fecha_ingreso')[:20]
    
    # Si es GET, buscar automáticamente por service_tag si existe
    elif solicitud.service_tag:
        from servicio_tecnico.models import OrdenServicio
        resultados = OrdenServicio.objects.filter(
            detalle_equipo__numero_serie__icontains=solicitud.service_tag
        ).select_related('detalle_equipo').order_by('-fecha_ingreso')[:20]
        termino_busqueda = solicitud.service_tag
    
    return render(request, 'almacen/cotizaciones/vincular_orden.html', {
        'solicitud': solicitud,
        'resultados': resultados,
        'termino_busqueda': termino_busqueda,
    })


@login_required
@permission_required_with_message('almacen.change_solicitudcotizacion')
def crear_orden_fl_desde_cotizacion(request, pk):
    """
    Crea una OrdenServicio tipo FL- (Venta Mostrador / Servicio Directo) directamente
    desde el detalle de una SolicitudCotizacion que no tiene orden vinculada.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cuando una cotización se creó en modo "sin orden activa" (el cliente solicitó
    precio antes de ingresar físicamente el equipo) y el cliente acepta la cotización,
    en lugar de obligar al usuario a ir a Servicio Técnico a crear la orden manualmente,
    esta vista crea la orden FL- (Servicio Directo sin Diagnóstico) aquí mismo,
    usando todos los datos del cliente y equipo que ya fueron capturados en la solicitud.

    Flujo:
    1. GET  → muestra modal con el formulario mínimo (técnico + número FL- sugerido)
    2. POST → crea OrdenServicio + DetalleEquipo con datos reales de la solicitud,
              llama a solicitud.vincular_orden() para sincronizar con ST,
              re-guarda las LineaCotizacion para que se sincronicen como PiezaCotizada,
              redirige al detalle con mensaje de éxito.

    Restricciones:
    - Solo aplica si solicitud.puede_vincular_orden() es True (sin_orden_activa + no completada/cancelada)
    - El tipo de servicio es siempre 'venta_mostrador' (Servicio Directo sin Diagnóstico)
    - El número FL- se auto-sugiere pero puede ser editado por el usuario

    Args:
        request: HttpRequest de Django
        pk     : PK de la SolicitudCotizacion

    Efectos secundarios:
        - Crea OrdenServicio y DetalleEquipo en servicio_tecnico
        - Modifica SolicitudCotizacion (vincula orden, desactiva sin_orden_activa)
        - Crea Cotizacion en servicio_tecnico (vía solicitud.vincular_orden → save)
        - Re-sincroniza LineaCotizacion → PiezaCotizada en servicio_tecnico
    """
    from servicio_tecnico.models import OrdenServicio, DetalleEquipo

    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)

    # Validar que la solicitud esté en modo sin_orden_activa y pueda vincularse
    if not solicitud.puede_vincular_orden():
        messages.error(
            request,
            'No se puede crear una orden. La solicitud ya tiene orden activa '
            'o está completada/cancelada.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    if request.method == 'GET':
        # ====== PREPARAR DATOS PARA EL MODAL ======

        # Obtener lista de técnicos de laboratorio activos para el selector
        tecnicos = Empleado.objects.filter(
            activo=True,
            cargo__icontains='TECNICO DE LABORATORIO'
        ).select_related('sucursal').order_by('nombre_completo')

        # Auto-generar sugerencia de número FL- con formato FL-YYYY-NNNN
        # Busca el último FL- de este año en DetalleEquipo para sugerir el siguiente
        año_actual = timezone.now().year
        ultimo_fl = DetalleEquipo.objects.filter(
            orden_cliente__startswith=f'FL-{año_actual}'
        ).order_by('-orden_cliente').first()

        if ultimo_fl:
            # Extraer el número secuencial del último FL- y sumar 1
            try:
                ultimo_num = int(ultimo_fl.orden_cliente.split('-')[-1])
                siguiente_num = ultimo_num + 1
            except (ValueError, IndexError):
                siguiente_num = 1
        else:
            # Si no hay ningún FL- este año, empezar desde 1
            siguiente_num = 1

        numero_fl_sugerido = f"FL-{año_actual}-{siguiente_num:04d}"

        return JsonResponse({
            'success': True,
            'tecnicos': [
                {
                    'id': t.pk,
                    'nombre': t.nombre_completo,
                    'sucursal': t.sucursal.nombre if t.sucursal else 'Sin asignar',
                }
                for t in tecnicos
            ],
            'numero_fl_sugerido': numero_fl_sugerido,
            # Datos del cliente/equipo para mostrar resumen en el modal
            'resumen': {
                'nombre_cliente': solicitud.nombre_cliente or '(sin nombre)',
                'email_cliente': solicitud.email_cliente or '(sin email)',
                'telefono_cliente': solicitud.telefono_cliente or '(sin teléfono)',
                'tipo_equipo': solicitud.tipo_equipo or 'Por definir',
                'marca': solicitud.marca or 'Por definir',
                'modelo': solicitud.modelo or 'Por definir',
                'numero_serie': solicitud.service_tag or '(sin service tag)',
            }
        })

    # ====== POST: Crear la orden FL- ======
    tecnico_id = request.POST.get('tecnico_id', '').strip()
    numero_fl = request.POST.get('numero_fl', '').strip().upper()

    # --- Validación de campos requeridos ---
    if not tecnico_id:
        messages.error(request, 'Debes seleccionar un técnico para crear la orden.')
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    if not numero_fl:
        messages.error(request, 'El número de folio FL- es obligatorio.')
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    # Validar que el número FL- tenga el formato correcto
    if not numero_fl.startswith('FL-'):
        messages.error(request, 'El folio debe comenzar con "FL-" (ej: FL-2026-0001).')
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    # Verificar que el número FL- no esté ya en uso en DetalleEquipo
    if DetalleEquipo.objects.filter(orden_cliente=numero_fl).exists():
        messages.error(
            request,
            f'El folio {numero_fl} ya está registrado en otra orden. '
            'Por favor usa un número diferente.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    # --- Obtener el técnico ---
    try:
        tecnico = Empleado.objects.get(pk=tecnico_id)
    except Empleado.DoesNotExist:
        messages.error(request, 'El técnico seleccionado no es válido.')
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    # --- Determinar la sucursal desde el usuario que creó la solicitud ---
    # Se intenta obtener la sucursal del empleado creador; si no tiene, se usa la del técnico
    try:
        empleado_creador = Empleado.objects.get(user=solicitud.creado_por)
        sucursal = empleado_creador.sucursal
    except (Empleado.DoesNotExist, AttributeError):
        # Fallback: usar la sucursal del técnico asignado
        sucursal = tecnico.sucursal

    if not sucursal:
        messages.error(
            request,
            'No se pudo determinar la sucursal. '
            'El creador de la solicitud o el técnico no tienen sucursal asignada.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    # --- Obtener el responsable de seguimiento (el usuario actual) ---
    try:
        responsable = Empleado.objects.get(user=request.user)
    except Empleado.DoesNotExist:
        # Si el usuario actual no tiene empleado asociado, usar el técnico como responsable
        responsable = tecnico

    try:
        # ====== PASO 1: Crear la OrdenServicio ======
        # tipo_servicio='venta_mostrador' porque estas órdenes son Servicio Directo sin Diagnóstico
        # estado='almacen' porque se origina desde el módulo Almacén
        orden = OrdenServicio.objects.create(
            sucursal=sucursal,
            responsable_seguimiento=responsable,
            tecnico_asignado_actual=tecnico,
            estado='almacen',
            tipo_servicio='venta_mostrador',
        )

        # ====== PASO 2: Crear el DetalleEquipo con los datos REALES del cliente ======
        # A diferencia del flujo genérico de solicitudes de baja (que usa placeholders),
        # aquí ya tenemos datos reales del cliente capturados en la SolicitudCotizacion.

        # Determinar tipo_equipo: usar el de la solicitud o fallback a 'Laptop'
        tipo_equipo_real = solicitud.tipo_equipo if solicitud.tipo_equipo else 'Laptop'

        # Determinar marca: usar la de la solicitud o fallback a 'Otra'
        marca_real = solicitud.marca if solicitud.marca else 'Otra'

        # Determinar modelo: usar el de la solicitud o placeholder
        modelo_real = solicitud.modelo if solicitud.modelo else 'Por definir'

        # Determinar número de serie: usar service_tag de la solicitud o placeholder
        numero_serie_real = solicitud.service_tag if solicitud.service_tag else f'ALMACEN-{numero_fl}'

        # Determinar falla_principal: usar observaciones de la solicitud o texto genérico
        falla_real = (
            solicitud.observaciones
            if solicitud.observaciones
            else 'Servicio directo sin diagnóstico - Cotización aprobada por cliente'
        )

        # Email del cliente: usar el de la solicitud o placeholder
        email_real = solicitud.email_cliente if solicitud.email_cliente else 'pendiente@actualizar.com'

        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente=numero_fl,        # Número FL- define es_fuera_garantia=True automáticamente
            tipo_equipo=tipo_equipo_real,
            marca=marca_real,
            modelo=modelo_real,
            numero_serie=numero_serie_real,
            gama='media',                   # Valor por defecto; el técnico puede ajustar después
            falla_principal=falla_real,
            email_cliente=email_real,
            # Datos adicionales del cliente (campos opcionales en DetalleEquipo)
            nombre_cliente=solicitud.nombre_cliente or '',
            telefono_cliente=solicitud.telefono_cliente or '',
            rfc_cliente=solicitud.rfc_cliente or '',
        )

        # ====== PASO 3: Vincular la solicitud con la nueva orden ======
        # vincular_orden() hace:
        #   - self.orden_servicio = orden
        #   - self.sin_orden_activa = False
        #   - Sincroniza numero_orden_cliente desde DetalleEquipo
        #   - self.save() → crea Cotizacion en ST vía _sincronizar_cotizacion_st()
        solicitud.vincular_orden(orden)

        # ====== PASO 4: Crear VentaMostrador vacío para la nueva orden ======
        # Para órdenes FL- (Venta Mostrador / Servicio Directo), NO se sincronizan
        # las líneas a PiezaCotizada (flujo de diagnóstico). En su lugar se crea el
        # VentaMostrador vacío ahora para que exista el objeto receptor; las piezas
        # individuales se crearán como PiezaVentaMostrador cuando el usuario pulse
        # "Generar Compras" en el detalle de la cotización.
        from servicio_tecnico.models import VentaMostrador as VentaMostradorModel
        VentaMostradorModel.objects.get_or_create(
            orden=orden,
            defaults={'fecha_venta': timezone.now()}
        )

        # Construir mensaje de éxito con información de la orden creada
        mensaje = (
            f'Orden {numero_fl} creada exitosamente y vinculada a la solicitud. '
            f'Orden interna: {orden.numero_orden_interno}. '
            f'Las piezas aprobadas se registrarán en Venta Mostrador al generar compras.'
        )

        messages.success(request, mensaje)

        logger.info(
            f"OrdenServicio {orden.numero_orden_interno} (FL: {numero_fl}) creada desde "
            f"SolicitudCotizacion {solicitud.numero_solicitud} por usuario {request.user}"
        )

    except ValueError as e:
        # Error de validación del método vincular_orden (ej: ya tiene otra solicitud activa)
        messages.error(request, f'Error al vincular la orden: {str(e)}')
        # Si la orden fue creada pero falló el vínculo, eliminarla para evitar órfanos
        try:
            orden.delete()
        except Exception:
            pass
    except Exception as e:
        messages.error(request, f'Error inesperado al crear la orden: {str(e)}')
        logger.error(
            f"Error al crear OrdenServicio desde SolicitudCotizacion {pk}: {e}",
            exc_info=True
        )
        # Intentar eliminar la orden parcialmente creada si existe
        try:
            orden.delete()
        except Exception:
            pass

    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
@permission_required_with_message('almacen.change_solicitudcotizacion')
def cancelar_solicitud_cotizacion(request, pk):
    """
    Cancelar una solicitud de cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cancela la solicitud completa. Solo se puede cancelar si no está
    completada (es decir, si aún no se generaron todas las compras).
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if request.method == 'POST':
        motivo = request.POST.get('motivo', '')
        
        if solicitud.cancelar(motivo=motivo):
            messages.success(
                request,
                f'Solicitud {solicitud.numero_solicitud} cancelada.'
            )
        else:
            messages.error(
                request,
                'No se puede cancelar esta solicitud (ya está completada o cancelada).'
            )
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
@permission_required_with_message('almacen.delete_solicitudcotizacion')
def eliminar_solicitud_cotizacion(request, pk):
    """
    Eliminar una solicitud de cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Elimina permanentemente la solicitud y todas sus líneas.
    Solo se puede eliminar si está en estado 'borrador' o 'cancelada'.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if solicitud.estado not in ['borrador', 'cancelada']:
        messages.error(
            request,
            'Solo se pueden eliminar solicitudes en estado borrador o canceladas.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
    
    if request.method == 'POST':
        numero = solicitud.numero_solicitud
        solicitud.delete()
        messages.success(request, f'Solicitud {numero} eliminada.')
        return redirect('almacen:lista_solicitudes_cotizacion')
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


# ============================================================================
# GESTIÓN DE IMÁGENES DE LÍNEAS DE COTIZACIÓN
# ============================================================================

@login_required
@permission_required_with_message('almacen.change_lineacotizacion')
def gestionar_imagenes_linea(request, solicitud_pk, linea_pk):
    """
    Gestionar imágenes de referencia de una línea de cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista permite ver, subir y eliminar imágenes de referencia
    para una línea específica de cotización.
    
    ¿Por qué es útil?
    - El proveedor ve exactamente qué pieza se necesita
    - El cliente puede verificar las especificaciones
    - Queda evidencia visual para trazabilidad
    
    Restricciones:
    - Solo se pueden gestionar imágenes si la solicitud está en estado 'borrador'
    - Máximo 5 imágenes por línea
    - Las imágenes mayores a 2MB se comprimen automáticamente
    
    Args:
        request: Solicitud HTTP
        solicitud_pk: ID de la SolicitudCotizacion
        linea_pk: ID de la LineaCotizacion
    
    Returns:
        Renderizado del template con el formulario y las imágenes actuales
    """
    # Obtener la solicitud y validar acceso
    solicitud = get_object_or_404(
        SolicitudCotizacion.objects.select_related('orden_servicio'),
        pk=solicitud_pk
    )
    
    # Obtener la línea y validar que pertenece a la solicitud
    linea = get_object_or_404(
        LineaCotizacion.objects.select_related('producto', 'proveedor'),
        pk=linea_pk,
        solicitud=solicitud
    )
    
    # Solo se pueden gestionar imágenes en estado borrador
    puede_editar = solicitud.estado == 'borrador'
    
    # Obtener imágenes existentes
    imagenes = linea.imagenes.all().order_by('fecha_subida')
    
    # Calcular información de límites
    imagenes_restantes = ImagenLineaCotizacion.imagenes_restantes(linea)
    puede_agregar = imagenes_restantes > 0 and puede_editar
    
    # Procesar formulario de subida
    if request.method == 'POST' and puede_agregar:
        form = ImagenLineaCotizacionForm(
            request.POST,
            request.FILES,
            linea=linea
        )
        
        if form.is_valid():
            try:
                # Guardar la imagen asociándola a la línea y al usuario
                imagen = form.save(commit=False)
                imagen.linea = linea
                imagen.subido_por = request.user
                imagen.save()
                
                messages.success(
                    request,
                    f'Imagen subida exitosamente. '
                    f'Quedan {ImagenLineaCotizacion.imagenes_restantes(linea)} espacios disponibles.'
                )
                
                # Redirigir para evitar reenvío del formulario
                return redirect(
                    'almacen:gestionar_imagenes_linea',
                    solicitud_pk=solicitud_pk,
                    linea_pk=linea_pk
                )
                
            except ValueError as e:
                messages.error(request, str(e))
        else:
            # Mostrar errores de validación
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = ImagenLineaCotizacionForm(linea=linea) if puede_agregar else None
    
    context = {
        'solicitud': solicitud,
        'linea': linea,
        'imagenes': imagenes,
        'form': form,
        'puede_editar': puede_editar,
        'puede_agregar': puede_agregar,
        'imagenes_restantes': imagenes_restantes,
        'max_imagenes': ImagenLineaCotizacion.MAX_IMAGENES_POR_LINEA,
        'titulo': f'Imágenes - Línea #{linea.numero_linea}',
    }
    
    return render(request, 'almacen/cotizaciones/gestionar_imagenes_linea.html', context)


@login_required
@permission_required_with_message('almacen.change_lineacotizacion')
def eliminar_imagen_linea(request, solicitud_pk, linea_pk, imagen_pk):
    """
    Eliminar una imagen de una línea de cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista elimina una imagen específica de una línea de cotización.
    
    Validaciones:
    - La imagen debe pertenecer a la línea indicada
    - La solicitud debe estar en estado 'borrador'
    - Solo se procesa si es una solicitud POST (para evitar eliminaciones accidentales)
    
    Args:
        request: Solicitud HTTP
        solicitud_pk: ID de la SolicitudCotizacion
        linea_pk: ID de la LineaCotizacion
        imagen_pk: ID de la ImagenLineaCotizacion a eliminar
    
    Returns:
        Redirección a la vista de gestión de imágenes
    """
    # Validar la cadena completa: solicitud → línea → imagen
    solicitud = get_object_or_404(SolicitudCotizacion, pk=solicitud_pk)
    linea = get_object_or_404(LineaCotizacion, pk=linea_pk, solicitud=solicitud)
    imagen = get_object_or_404(ImagenLineaCotizacion, pk=imagen_pk, linea=linea)
    
    # Solo se pueden eliminar imágenes en estado borrador
    if solicitud.estado != 'borrador':
        messages.error(
            request,
            'Solo se pueden eliminar imágenes cuando la solicitud está en borrador.'
        )
        return redirect(
            'almacen:detalle_solicitud_cotizacion',
            pk=solicitud_pk
        )
    
    # Solo procesar eliminación con método POST
    if request.method == 'POST':
        nombre_archivo = imagen.nombre_archivo
        imagen.delete()
        messages.success(
            request,
            f'Imagen "{nombre_archivo}" eliminada correctamente.'
        )
    
    return redirect(
        'almacen:detalle_solicitud_cotizacion',
        pk=solicitud_pk
    )


@login_required
@permission_required_with_message('almacen.view_lineacotizacion')
def api_imagenes_linea(request, linea_pk):
    """
    API para obtener las imágenes de una línea en formato JSON.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista retorna las imágenes de una línea en formato JSON,
    útil para actualizar la interfaz con JavaScript sin recargar la página.
    
    La respuesta incluye:
    - Lista de imágenes con su URL, descripción y metadata
    - Información sobre cuántas imágenes más se pueden subir
    - Si se puede agregar más imágenes
    
    Args:
        request: Solicitud HTTP
        linea_pk: ID de la LineaCotizacion
    
    Returns:
        JsonResponse con la información de las imágenes
    """
    linea = get_object_or_404(
        LineaCotizacion.objects.select_related('solicitud'),
        pk=linea_pk
    )
    
    imagenes = linea.imagenes.all().order_by('fecha_subida')
    
    imagenes_data = []
    for img in imagenes:
        imagenes_data.append({
            'id': img.pk,
            'url': img.imagen.url,
            'nombre': img.nombre_archivo,
            'descripcion': img.descripcion or '',
            'fecha_subida': img.fecha_subida.strftime('%d/%m/%Y %H:%M'),
            'fue_comprimida': img.fue_comprimida,
            'tamano_kb': img.tamano_final_kb,
        })
    
    return JsonResponse({
        'success': True,
        'imagenes': imagenes_data,
        'total_imagenes': len(imagenes_data),
        'imagenes_restantes': ImagenLineaCotizacion.imagenes_restantes(linea),
        'puede_agregar': ImagenLineaCotizacion.puede_agregar_imagen(linea),
        'max_imagenes': ImagenLineaCotizacion.MAX_IMAGENES_POR_LINEA,
        'puede_editar': linea.solicitud.estado == 'borrador',
    })

