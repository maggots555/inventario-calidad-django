"""
Compras y cotizaciones simples (modelo CompraProducto).

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
Extraído de views.py (Fase 3 de modularización Almacén).
Aquí vive el flujo "compra/cotización clásica" por producto:
listar, crear, aprobar/rechazar, recibir, devoluciones y unidades de compra.

NO incluye SolicitudCotizacion multi-proveedor (eso es Fase 4).

urls.py sigue usando views.lista_compras, views.recibir_compra, etc.
porque views.py reexporta estos nombres.

Efectos secundarios:
- Crea/actualiza CompraProducto, UnidadCompra, MovimientoAlmacen, UnidadInventario
- Helpers privados _clave_grupo_compra_cotizacion / _agrupar_compras_por_orden
  solo sirven a lista_compras (agrupar por orden en la UI)
"""

from collections import OrderedDict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from config.constants import ESTADOS_SOLICITUD_CON_VIGENCIA
from inventario.models import Empleado

from .decorators import permission_required_with_message
from .forms import (
    CompraProductoForm,
    DevolucionCompraForm,
    ProblemaCompraForm,
    RecepcionCompraForm,
    RechazoCotizacionForm,
    UnidadCompraFormSet,
)
from .models import (
    CompraProducto,
    MovimientoAlmacen,
    ProductoAlmacen,
    Proveedor,
    SolicitudCotizacion,
    UnidadCompra,
    UnidadInventario,
)
from .utils.lista_compras_orden import ordenar_compras_para_lista
from .utils.vigencia_cotizacion import alerta_vigencia_panel


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
    Agrupa compras de cotización por orden, preservando el orden de la lista.

    EXPLICACIÓN PARA PRINCIPIANTES:
    -------------------------------
    Recorremos la lista ya ordenada (pendiente de llegada / días que faltan)
    y metemos cada compra en su "canasta" de orden. El grupo aparece cuando
    entra su primera pieza, así las órdenes urgentes quedan arriba. En la
    plantilla pintamos una cabecera por orden y debajo cada pieza.

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

    Orden por defecto (ambas pestañas): pendiente_llegada primero,
    y entre esas las más urgentes según dias_para_llegada.
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

    # Orden de negocio en Python: pendiente_llegada + días que faltan.
    # No se puede hacer solo con order_by SQL: dias_para_llegada es property.
    compras_ordenadas = ordenar_compras_para_lista(compras_qs)

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
        grupos = _agrupar_compras_por_orden(compras_ordenadas)
        paginator = Paginator(grupos, 15)
        grupos_page = paginator.get_page(page)
    else:
        # Directas: tabla plana, una fila por compra (mismo orden de urgencia)
        paginator = Paginator(compras_ordenadas, 25)
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
    Panel de cotizaciones pendientes (enviadas a Front o al cliente).

    Objetivo de negocio:
        Mostrar en un dashboard las solicitudes que todavía no tienen
        respuesta final, separadas por estatus:
        - enviada_front: Compras ya liberó; Recepción aún no comparte.
        - enviada_cliente: Recepción ya compartió; se espera al cliente.

    Args:
        request: HttpRequest autenticado con permiso view_solicitudcotizacion.

    Efectos secundarios:
        Ninguno (solo lectura). El template pinta dos pestañas Bootstrap.
        A cada solicitud se le pega ``alerta_panel`` ('vencida'/'urgente'/'ok')
        para que la tabla no recalcule la regla de 5 días hábiles.
    """
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # select_related trae de un jalón las FKs que la tabla va a mostrar
    # (orden, responsable de seguimiento, quien creó la solicitud).
    # Sin esto, cada fila haría queries extra (problema N+1).
    relaciones = (
        'orden_servicio',
        'orden_servicio__responsable_seguimiento',
        'creado_por',
        'creado_por__empleado',
    )

    # list(): evaluamos una vez para poder anotar alerta_panel y contar
    # «por vencer» en Python (los días hábiles no se calculan bien en SQL).
    cotizaciones_front = list(
        SolicitudCotizacion.objects.filter(
            estado='enviada_front'
        ).select_related(*relaciones).prefetch_related('lineas').order_by('-fecha_creacion')
    )
    cotizaciones_cliente = list(
        SolicitudCotizacion.objects.filter(
            estado='enviada_cliente'
        ).select_related(*relaciones).prefetch_related('lineas').order_by('-fecha_creacion')
    )

    total_front = len(cotizaciones_front)
    total_cliente = len(cotizaciones_cliente)

    # EXPLICACIÓN: alerta_vigencia_panel usa el reloj de 5 días hábiles
    # (no los 3 días calendario viejos). Pegamos el resultado en cada
    # objeto para que el template solo pregunte cot.alerta_panel.
    cotizaciones_por_vencer = 0
    for solicitud in cotizaciones_front + cotizaciones_cliente:
        alerta = alerta_vigencia_panel(solicitud)
        solicitud.alerta_panel = alerta
        if alerta == 'urgente':
            cotizaciones_por_vencer += 1

    cotizaciones_borrador = SolicitudCotizacion.objects.filter(
        estado='borrador'
    ).count()

    # Vencidas: COUNT en BD (el campo ya tiene índice). Misma regla que
    # esta_vencida: fecha límite menor o igual a ahora, estados con reloj.
    cotizaciones_vencidas = SolicitudCotizacion.objects.filter(
        estado__in=ESTADOS_SOLICITUD_CON_VIGENCIA,
        fecha_vencimiento_vigencia__lte=timezone.now(),
    ).count()

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
        'cotizaciones_front': cotizaciones_front,
        'cotizaciones_cliente': cotizaciones_cliente,
        'total_front': total_front,
        'total_cliente': total_cliente,
        'total_pendientes': total_front + total_cliente,
        'cotizaciones_por_vencer': cotizaciones_por_vencer,
        'cotizaciones_vencidas': cotizaciones_vencidas,
        'cotizaciones_borrador': cotizaciones_borrador,
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


