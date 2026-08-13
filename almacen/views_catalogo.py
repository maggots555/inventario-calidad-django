"""
Catálogo base de Almacén: dashboard, productos, proveedores, categorías,
solicitudes de baja, movimientos, APIs de producto y acceso denegado.

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
Extraído de views.py (Fase 2 de modularización Almacén).
urls.py sigue usando views.dashboard_almacen, views.lista_productos, etc.
porque views.py reexporta estos nombres.

Efectos secundarios:
- CRUD sobre Proveedor / CategoriaAlmacen / ProductoAlmacen
- Solicitudes de baja (crear/procesar) y listado de movimientos
- APIs JSON de búsqueda/info de producto
- acceso_denegado: página amigable cuando falta un permiso
"""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from inventario.models import Empleado

from .decorators import permission_required_with_message
from .forms import (
    BusquedaProductoForm,
    CategoriaAlmacenForm,
    ProcesarSolicitudForm,
    ProductoAlmacenForm,
    ProveedorForm,
    SolicitudBajaForm,
)
from .models import (
    Auditoria,
    CategoriaAlmacen,
    MovimientoAlmacen,
    ProductoAlmacen,
    Proveedor,
    SolicitudBaja,
    UnidadInventario,
)
from .utils.sincronizar_solicitud_baja_vm import (
    registrar_pieza_vm_desde_solicitud_baja,
)

logger = logging.getLogger('almacen')


# ============================================================================
# DASHBOARD PRINCIPAL
# ============================================================================
@login_required
@permission_required_with_message('almacen.view_productoalmacen')
def dashboard_almacen(request):
    """
    Dashboard principal del módulo Almacén.
    
    Muestra KPIs y resúmenes:
    - Solicitudes pendientes
    - Productos con stock bajo
    - Valor total del inventario
    - Últimos movimientos
    - Auditorías en proceso
    """
    
    # KPIs principales
    solicitudes_pendientes = SolicitudBaja.objects.filter(
        estado='pendiente'
    ).count()
    
    productos_stock_bajo = ProductoAlmacen.objects.filter(
        activo=True,
        tipo_producto='resurtible',
        stock_actual__lte=F('stock_minimo')
    ).count()
    
    productos_agotados = ProductoAlmacen.objects.filter(
        activo=True,
        stock_actual=0
    ).count()
    
    # Valor total del inventario
    valor_inventario = ProductoAlmacen.objects.filter(
        activo=True
    ).aggregate(
        total=Coalesce(
            Sum(F('stock_actual') * F('costo_unitario'), output_field=DecimalField()),
            0,
            output_field=DecimalField()
        )
    )['total']
    
    # Total de productos activos
    total_productos = ProductoAlmacen.objects.filter(activo=True).count()
    
    # Últimas solicitudes pendientes (para cola de trabajo)
    ultimas_solicitudes = SolicitudBaja.objects.filter(
        estado='pendiente'
    ).select_related(
        'producto', 'solicitante', 'orden_servicio'
    ).order_by('-fecha_solicitud')[:5]
    
    # Productos que requieren reposición
    productos_reposicion = ProductoAlmacen.objects.filter(
        activo=True,
        tipo_producto='resurtible',
        stock_actual__lte=F('stock_minimo')
    ).select_related('categoria', 'proveedor_principal')[:5]
    
    # Últimos movimientos
    ultimos_movimientos = MovimientoAlmacen.objects.select_related(
        'producto', 'empleado'
    ).order_by('-fecha')[:10]
    
    # Auditorías en proceso
    auditorias_en_proceso = Auditoria.objects.filter(
        estado='en_proceso'
    ).count()
    
    context = {
        # KPIs
        'solicitudes_pendientes': solicitudes_pendientes,
        'productos_stock_bajo': productos_stock_bajo,
        'productos_agotados': productos_agotados,
        'valor_inventario': valor_inventario,
        'total_productos': total_productos,
        'auditorias_en_proceso': auditorias_en_proceso,
        # Listas
        'ultimas_solicitudes': ultimas_solicitudes,
        'productos_reposicion': productos_reposicion,
        'ultimos_movimientos': ultimos_movimientos,
    }
    
    return render(request, 'almacen/dashboard_almacen.html', context)


# ============================================================================
# CRUD: PROVEEDORES
# ============================================================================
@login_required
@permission_required_with_message('almacen.view_proveedor')
def lista_proveedores(request):
    """
    Lista todos los proveedores con búsqueda y paginación.
    """
    proveedores = Proveedor.objects.all()
    
    # Búsqueda
    q = request.GET.get('q', '').strip()
    if q:
        proveedores = proveedores.filter(
            Q(nombre__icontains=q) |
            Q(contacto__icontains=q) |
            Q(email__icontains=q)
        )
    
    # Filtro por estado activo
    activo = request.GET.get('activo', '')
    if activo == '1':
        proveedores = proveedores.filter(activo=True)
    elif activo == '0':
        proveedores = proveedores.filter(activo=False)
    
    # Paginación
    paginator = Paginator(proveedores.order_by('nombre'), 20)
    page = request.GET.get('page', 1)
    proveedores_page = paginator.get_page(page)
    
    context = {
        'proveedores': proveedores_page,
        'q': q,
        'activo_filtro': activo,
    }
    
    return render(request, 'almacen/proveedores/lista_proveedores.html', context)


@login_required
@permission_required_with_message('almacen.add_proveedor')
def crear_proveedor(request):
    """
    Crea un nuevo proveedor.
    """
    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            proveedor = form.save()
            messages.success(request, f'Proveedor "{proveedor.nombre}" creado correctamente.')
            return redirect('almacen:lista_proveedores')
    else:
        form = ProveedorForm()
    
    context = {
        'form': form,
        'titulo': 'Nuevo Proveedor',
        'boton': 'Crear Proveedor',
    }
    
    return render(request, 'almacen/proveedores/form_proveedor.html', context)


@login_required
@permission_required_with_message('almacen.change_proveedor')
def editar_proveedor(request, pk):
    """
    Edita un proveedor existente.
    """
    proveedor = get_object_or_404(Proveedor, pk=pk)
    
    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            form.save()
            messages.success(request, f'Proveedor "{proveedor.nombre}" actualizado.')
            return redirect('almacen:lista_proveedores')
    else:
        form = ProveedorForm(instance=proveedor)
    
    context = {
        'form': form,
        'proveedor': proveedor,
        'titulo': f'Editar: {proveedor.nombre}',
        'boton': 'Guardar Cambios',
    }
    
    return render(request, 'almacen/proveedores/form_proveedor.html', context)


@login_required
@permission_required_with_message('almacen.delete_proveedor')
def eliminar_proveedor(request, pk):
    """
    Elimina un proveedor (o lo desactiva si tiene productos asociados).
    """
    proveedor = get_object_or_404(Proveedor, pk=pk)
    
    if request.method == 'POST':
        # Verificar si tiene productos asociados
        if proveedor.productos_principales.exists():
            # Desactivar en lugar de eliminar
            proveedor.activo = False
            proveedor.save()
            messages.warning(
                request, 
                f'El proveedor "{proveedor.nombre}" tiene productos asociados. '
                f'Se ha desactivado en lugar de eliminar.'
            )
        else:
            nombre = proveedor.nombre
            proveedor.delete()
            messages.success(request, f'Proveedor "{nombre}" eliminado.')
        
        return redirect('almacen:lista_proveedores')
    
    context = {
        'proveedor': proveedor,
        'tiene_productos': proveedor.productos_principales.exists(),
    }
    
    return render(request, 'almacen/proveedores/eliminar_proveedor.html', context)


# ============================================================================
# CRUD: CATEGORÍAS
# ============================================================================
@login_required
@permission_required_with_message('almacen.view_categoriaalmacen')
def lista_categorias(request):
    """
    Lista todas las categorías con conteo de productos.
    """
    categorias = CategoriaAlmacen.objects.annotate(
        num_productos=Count('productos', filter=Q(productos__activo=True))
    ).order_by('nombre')
    
    context = {
        'categorias': categorias,
    }
    
    return render(request, 'almacen/categorias/lista_categorias.html', context)


@login_required
@permission_required_with_message('almacen.add_categoriaalmacen')
def crear_categoria(request):
    """
    Crea una nueva categoría.
    """
    if request.method == 'POST':
        form = CategoriaAlmacenForm(request.POST)
        if form.is_valid():
            categoria = form.save()
            messages.success(request, f'Categoría "{categoria.nombre}" creada.')
            return redirect('almacen:lista_categorias')
    else:
        form = CategoriaAlmacenForm()
    
    context = {
        'form': form,
        'titulo': 'Nueva Categoría',
        'boton': 'Crear Categoría',
    }
    
    return render(request, 'almacen/categorias/form_categoria.html', context)


@login_required
@permission_required_with_message('almacen.change_categoriaalmacen')
def editar_categoria(request, pk):
    """
    Edita una categoría existente.
    """
    categoria = get_object_or_404(CategoriaAlmacen, pk=pk)
    
    if request.method == 'POST':
        form = CategoriaAlmacenForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            messages.success(request, f'Categoría "{categoria.nombre}" actualizada.')
            return redirect('almacen:lista_categorias')
    else:
        form = CategoriaAlmacenForm(instance=categoria)
    
    context = {
        'form': form,
        'categoria': categoria,
        'titulo': f'Editar: {categoria.nombre}',
        'boton': 'Guardar Cambios',
    }
    
    return render(request, 'almacen/categorias/form_categoria.html', context)


# ============================================================================
# CRUD: PRODUCTOS DE ALMACÉN
# ============================================================================
@login_required
@permission_required_with_message('almacen.view_productoalmacen')
def lista_productos(request):
    """
    Lista productos con búsqueda, filtros y paginación.
    """
    productos = ProductoAlmacen.objects.filter(activo=True).select_related(
        'categoria', 'proveedor_principal', 'sucursal'
    )
    
    # Procesar formulario de búsqueda
    form = BusquedaProductoForm(request.GET)
    
    if form.is_valid():
        # Búsqueda por texto
        q = form.cleaned_data.get('q')
        if q:
            productos = productos.filter(
                Q(codigo_producto__icontains=q) |
                Q(nombre__icontains=q) |
                Q(descripcion__icontains=q)
            )
        
        # Filtro por tipo
        tipo = form.cleaned_data.get('tipo')
        if tipo:
            productos = productos.filter(tipo_producto=tipo)
        
        # Filtro por categoría
        categoria = form.cleaned_data.get('categoria')
        if categoria:
            productos = productos.filter(categoria=categoria)
        
        # Filtro por stock
        stock = form.cleaned_data.get('stock')
        if stock == 'bajo':
            productos = productos.filter(
                tipo_producto='resurtible',
                stock_actual__lte=F('stock_minimo')
            )
        elif stock == 'agotado':
            productos = productos.filter(stock_actual=0)
        elif stock == 'disponible':
            productos = productos.filter(stock_actual__gt=0)
    
    # Contar por tipo
    total_resurtibles = productos.filter(tipo_producto='resurtible').count()
    total_unicos = productos.filter(tipo_producto='unico').count()
    
    # Paginación
    paginator = Paginator(productos.order_by('nombre'), 20)
    page = request.GET.get('page', 1)
    productos_page = paginator.get_page(page)
    
    context = {
        'productos': productos_page,
        'form': form,
        'total_resurtibles': total_resurtibles,
        'total_unicos': total_unicos,
        'total': productos.count(),
    }
    
    return render(request, 'almacen/productos/lista_productos.html', context)


@login_required
@permission_required_with_message('almacen.add_productoalmacen')
def crear_producto(request):
    """
    Crea un nuevo producto de almacén.
    """
    if request.method == 'POST':
        form = ProductoAlmacenForm(request.POST, request.FILES)
        if form.is_valid():
            producto = form.save(commit=False)
            producto.creado_por = request.user
            producto.save()
            messages.success(
                request, 
                f'Producto "{producto.codigo_producto} - {producto.nombre}" creado.'
            )
            return redirect('almacen:detalle_producto', pk=producto.pk)
    else:
        form = ProductoAlmacenForm()
    
    context = {
        'form': form,
        'titulo': 'Nuevo Producto',
        'boton': 'Crear Producto',
    }
    
    return render(request, 'almacen/productos/form_producto.html', context)


@login_required
@permission_required_with_message('almacen.change_productoalmacen')
def editar_producto(request, pk):
    """
    Edita un producto existente.
    """
    producto = get_object_or_404(ProductoAlmacen, pk=pk)
    
    if request.method == 'POST':
        form = ProductoAlmacenForm(request.POST, request.FILES, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, f'Producto "{producto.nombre}" actualizado.')
            return redirect('almacen:detalle_producto', pk=producto.pk)
    else:
        form = ProductoAlmacenForm(instance=producto)
    
    context = {
        'form': form,
        'producto': producto,
        'titulo': f'Editar: {producto.codigo_producto}',
        'boton': 'Guardar Cambios',
    }
    
    return render(request, 'almacen/productos/form_producto.html', context)


@login_required
@permission_required_with_message('almacen.view_productoalmacen')
def detalle_producto(request, pk):
    """
    Muestra el detalle completo de un producto.
    
    Incluye:
    - Información general
    - Estado del stock (total y distribución por sucursal)
    - Historial de movimientos
    - Historial de compras
    - Órdenes de servicio vinculadas
    
    ACTUALIZADO (Enero 2026): Agregada distribución por sucursal
    """
    from inventario.models import Sucursal
    from django.db.models import Count
    
    producto = get_object_or_404(
        ProductoAlmacen.objects.select_related(
            'categoria', 'proveedor_principal', 'sucursal', 'creado_por'
        ),
        pk=pk
    )
    
    # ========== DISTRIBUCIÓN POR SUCURSAL (NUEVO - Enero 2026) ==========
    # EXPLICACIÓN: Solo contamos unidades DISPONIBLES (no asignadas ni vendidas)
    # Cuando se aprueba una solicitud de servicio, la disponibilidad cambia a 'asignada'
    # y automáticamente se descuenta del conteo de la sucursal
    distribucion_sucursales = []
    
    # Almacén Central (unidades sin sucursal asignada)
    central_count = producto.unidades.filter(
        sucursal_actual__isnull=True,
        disponibilidad='disponible'  # Solo disponibles
    ).count()
    
    if central_count > 0:
        distribucion_sucursales.append({
            'nombre': 'Almacén Central',
            'codigo': 'central',
            'cantidad': central_count,
            'es_central': True
        })
    
    # Sucursales activas con unidades disponibles
    for sucursal in Sucursal.objects.filter(activa=True).annotate(
        cantidad_unidades=Count('unidades_almacenadas', 
                                filter=Q(unidades_almacenadas__producto=producto,
                                       unidades_almacenadas__disponibilidad='disponible'))  # Solo disponibles
    ):
        if sucursal.cantidad_unidades > 0:
            distribucion_sucursales.append({
                'nombre': sucursal.nombre,
                'codigo': sucursal.codigo,
                'cantidad': sucursal.cantidad_unidades,
                'es_central': False
            })
    
    # Últimos movimientos
    # EXPLICACIÓN: detalle_equipo trae el folio (OOW-/FL-) para el enlace
    # del historial, sin una consulta extra por cada fila.
    movimientos = producto.movimientos.select_related(
        'empleado',
        'orden_servicio',
        'orden_servicio__detalle_equipo',
        'compra',
    ).order_by('-fecha')[:20]
    
    # Historial de compras
    compras = producto.historial_compras.select_related(
        'proveedor', 'orden_servicio'
    ).order_by('-fecha_recepcion', '-fecha_pedido')[:10]
    
    # Estadísticas de compras
    if compras.exists():
        from django.db.models import Avg, Min, Max
        stats_compras = producto.historial_compras.aggregate(
            costo_promedio=Avg('costo_unitario'),
            costo_minimo=Min('costo_unitario'),
            costo_maximo=Max('costo_unitario'),
            total_comprado=Sum('cantidad'),
        )
    else:
        stats_compras = None
    
    # Solicitudes pendientes para este producto
    solicitudes_pendientes = producto.solicitudes_baja.filter(
        estado__in=['pendiente', 'en_espera']
    ).select_related('solicitante')
    
    context = {
        'producto': producto,
        'distribucion_sucursales': distribucion_sucursales,  # NUEVO
        'movimientos': movimientos,
        'compras': compras,
        'stats_compras': stats_compras,
        'solicitudes_pendientes': solicitudes_pendientes,
    }
    
    return render(request, 'almacen/productos/detalle_producto.html', context)


# ============================================================================
# SOLICITUDES DE BAJA
# ============================================================================
@login_required
@permission_required_with_message('almacen.view_solicitudbaja')
def lista_solicitudes(request):
    """
    Lista de solicitudes de baja con filtros por estado.
    """
    solicitudes = SolicitudBaja.objects.select_related(
        'producto', 'unidad_inventario', 'solicitante', 'agente_almacen', 'orden_servicio'
    ).prefetch_related('unidades_seleccionadas')
    
    # Filtro por estado
    estado = request.GET.get('estado', '')
    if estado:
        solicitudes = solicitudes.filter(estado=estado)
    
    # Por defecto, mostrar pendientes primero
    solicitudes = solicitudes.order_by(
        # Pendientes primero, luego por fecha
        '-fecha_solicitud'
    )
    
    # Paginación
    paginator = Paginator(solicitudes, 20)
    page = request.GET.get('page', 1)
    solicitudes_page = paginator.get_page(page)
    
    # Contadores
    contadores = {
        'pendientes': SolicitudBaja.objects.filter(estado='pendiente').count(),
        'aprobadas': SolicitudBaja.objects.filter(estado='aprobada').count(),
        'rechazadas': SolicitudBaja.objects.filter(estado='rechazada').count(),
    }
    
    context = {
        'solicitudes': solicitudes_page,
        'estado_filtro': estado,
        'contadores': contadores,
    }
    
    return render(request, 'almacen/solicitudes/lista_solicitudes.html', context)


@login_required
@permission_required_with_message('almacen.add_solicitudbaja')
def crear_solicitud(request):
    """
    Crea una nueva solicitud de salida de productos del almacén.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Renderiza el formulario SolicitudBajaForm con autocompletado de producto
    y orden (TypeScript en solicitud_baja_form.ts). Al enviar POST valida
    stock, técnico, prefijo OOW/FL y unidades seleccionadas.

    ACTUALIZADO (Enero 2026):
    - Procesa unidades seleccionadas del formulario
    - Valida que el empleado tenga sucursal asignada
    - Filtra unidades por sucursal (empleados) o todas (agentes de almacén)

    Efectos secundarios al guardar:
        Avisa a almacenistas (push + campanita) y encola correo To/CC
        (Compras + solicitante). Si el aviso falla, la solicitud queda.
    """
    # Obtener empleado del usuario actual
    try:
        empleado = Empleado.objects.get(user=request.user)
    except Empleado.DoesNotExist:
        messages.error(
            request, 
            'No tienes un perfil de empleado asociado. Contacta al administrador.'
        )
        return redirect('almacen:dashboard_almacen')
    
    # ========== VALIDACIÓN: Empleado debe tener sucursal asignada (NUEVO) ==========
    # Solo se exige para empleados normales, agentes de almacén pueden no tenerla
    es_agente_almacen = request.user.is_staff
    
    if not es_agente_almacen and not empleado.sucursal:
        messages.error(
            request,
            'Tu perfil no tiene una sucursal asignada. '
            'No puedes crear solicitudes hasta que un administrador te asigne una sucursal. '
            'Por favor, contacta al departamento de sistemas.'
        )
        return redirect('almacen:dashboard_almacen')
    
    if request.method == 'POST':
        # Pasar parámetros extras al formulario
        form = SolicitudBajaForm(
            request.POST,
            empleado_actual=empleado,
            es_agente_almacen=es_agente_almacen
        )
        
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.solicitante = empleado
            solicitud.save()
            
            # ========== GUARDAR UNIDADES SELECCIONADAS ==========
            # Obtener IDs de unidades seleccionadas del formulario validado
            unidades_ids = form.cleaned_data.get('unidades_ids', [])
            
            if unidades_ids:
                # Obtener las unidades y agregarlas al ManyToMany
                unidades = UnidadInventario.objects.filter(id__in=unidades_ids)
                solicitud.unidades_seleccionadas.set(unidades)
            
            # Guardar formulario completo (incluyendo ManyToMany)
            form.save_m2m()

            # EXPLICACIÓN: el HTML solo hace POST; el aviso vive aquí.
            # Push/campanita a almacenistas; correo To ellos y CC a Compras
            # + quien pidió. Si el aviso falla, la baja ya existe.
            try:
                from almacen.utils.notificar_solicitud_baja import (
                    notificar_nueva_solicitud_baja,
                )
                notificar_nueva_solicitud_baja(solicitud)
            except Exception:
                logger.exception(
                    '[NOTIF-BAJA] Error al notificar solicitud #%s',
                    solicitud.pk,
                )
            
            messages.success(request, 'Solicitud creada correctamente.')
            return redirect('almacen:lista_solicitudes')
    else:
        # Pasar parámetros extras al formulario vacío
        form = SolicitudBajaForm(
            empleado_actual=empleado,
            es_agente_almacen=es_agente_almacen
        )
    
    context = {
        'form': form,
        'titulo': 'Nueva solicitud',
        'empleado': empleado,
        'es_agente_almacen': es_agente_almacen,
    }
    
    return render(request, 'almacen/solicitudes/form_solicitud.html', context)


@login_required
@permission_required_with_message('almacen.change_solicitudbaja')
def procesar_solicitud(request, pk):
    """
    Procesa (aprueba o rechaza) una solicitud de baja.
    Solo para agentes de almacén.

    Args:
        request: HttpRequest GET (formulario) o POST (acción).
        pk: ID de la SolicitudBaja en estado pendiente.

    Efectos secundarios:
        - Aprobar: descuenta stock (SolicitudBaja.aprobar) y, si hay orden
          OOW-/FL-, registra la pieza en Venta Mostrador (util paralelo a cotización).
        - Rechazar: solo cambia estado; no toca stock ni ST.
        - Aviso al solicitante (push/campanita) y correo To/CC a Compras.
    """
    solicitud = get_object_or_404(
        SolicitudBaja.objects.select_related(
            'producto', 
            'unidad_inventario', 
            'solicitante', 
            'orden_servicio',
            'orden_servicio__detalle_equipo',  # Cargar detalle_equipo para acceder a orden_cliente
            'tecnico_asignado'  # Cargar técnico asignado
        ).prefetch_related('unidades_seleccionadas'),
        pk=pk, 
        estado='pendiente'
    )
    
    if request.method == 'POST':
        form = ProcesarSolicitudForm(request.POST)
        if form.is_valid():
            accion = form.cleaned_data['accion']
            observaciones = form.cleaned_data['observaciones']
            
            # Obtener empleado del usuario actual (agente)
            try:
                agente = Empleado.objects.get(user=request.user)
            except Empleado.DoesNotExist:
                messages.error(request, 'No tienes perfil de empleado asociado.')
                return redirect('almacen:lista_solicitudes')
            
            if accion == 'aprobar':
                # Primero sale el stock; después (si aplica) se refleja en ST.
                solicitud.aprobar(agente, observaciones)
                pieza_vm = registrar_pieza_vm_desde_solicitud_baja(solicitud)
                if pieza_vm:
                    folio_orden = solicitud.orden_servicio.numero_orden_interno
                    messages.success(
                        request,
                        f'Solicitud #{solicitud.pk} aprobada. Stock actualizado. '
                        f'Pieza registrada en Venta Mostrador de la orden {folio_orden}.'
                    )
                else:
                    messages.success(
                        request,
                        f'Solicitud #{solicitud.pk} aprobada. Stock actualizado.'
                    )
            else:
                solicitud.rechazar(agente, observaciones)
                messages.warning(request, f'Solicitud #{solicitud.pk} rechazada.')

            # EXPLICACIÓN: To = quien pidió; CC = Compras. El enlace va
            # al listado (procesar ya no aplica: deja de estar pendiente).
            try:
                from almacen.utils.notificar_solicitud_baja import (
                    notificar_solicitud_baja_procesada,
                )
                notificar_solicitud_baja_procesada(solicitud)
            except Exception:
                logger.exception(
                    '[NOTIF-BAJA] Error al notificar procesamiento #%s',
                    solicitud.pk,
                )
            
            return redirect('almacen:lista_solicitudes')
    else:
        form = ProcesarSolicitudForm()
    
    context = {
        'form': form,
        'solicitud': solicitud,
    }
    
    return render(request, 'almacen/solicitudes/procesar_solicitud.html', context)


# ============================================================================
# MOVIMIENTOS (ENTRADAS/SALIDAS)
# ============================================================================
@login_required
@permission_required_with_message('almacen.view_movimientoalmacen')
def lista_movimientos(request):
    """
    Lista de movimientos de almacén (entradas y salidas).
    """
    # EXPLICACIÓN: detalle_equipo trae el folio para el badge-enlace a ST.
    movimientos = MovimientoAlmacen.objects.select_related(
        'producto',
        'empleado',
        'orden_servicio',
        'orden_servicio__detalle_equipo',
        'solicitud_baja',
        'compra',
    )
    
    # Filtro por tipo
    tipo = request.GET.get('tipo', '')
    if tipo:
        movimientos = movimientos.filter(tipo=tipo)
    
    # Filtro por producto
    producto_id = request.GET.get('producto', '')
    if producto_id:
        movimientos = movimientos.filter(producto_id=producto_id)
    
    movimientos = movimientos.order_by('-fecha')
    
    # Paginación
    paginator = Paginator(movimientos, 30)
    page = request.GET.get('page', 1)
    movimientos_page = paginator.get_page(page)
    
    context = {
        'movimientos': movimientos_page,
        'tipo_filtro': tipo,
    }
    
    return render(request, 'almacen/movimientos/lista_movimientos.html', context)


# ============================================================================
# API / AJAX ENDPOINTS
# ============================================================================
@login_required
@permission_required_with_message('almacen.view_productoalmacen')
def api_buscar_productos(request):
    """
    API para búsqueda de productos (autocompletado).
    Retorna JSON con productos que coinciden con la búsqueda.
    """
    q = request.GET.get('q', '').strip()
    
    if len(q) < 2:
        return JsonResponse({'productos': []})
    
    productos = ProductoAlmacen.objects.filter(
        activo=True
    ).filter(
        Q(codigo_producto__icontains=q) |
        Q(nombre__icontains=q)
    )[:10]
    
    data = {
        'productos': [
            {
                'id': p.pk,
                'codigo': p.codigo_producto,
                'nombre': p.nombre,
                'stock': p.stock_actual,
                'costo': float(p.costo_unitario),
                'tipo': p.tipo_producto,
            }
            for p in productos
        ]
    }
    
    return JsonResponse(data)


@login_required
@permission_required_with_message('almacen.view_productoalmacen')
def api_info_producto(request, pk):
    """
    API para obtener información de un producto específico.
    """
    try:
        producto = ProductoAlmacen.objects.get(pk=pk, activo=True)
        data = {
            'success': True,
            'producto': {
                'id': producto.pk,
                'codigo': producto.codigo_producto,
                'nombre': producto.nombre,
                'stock': producto.stock_actual,
                'costo': float(producto.costo_unitario),
                'tipo': producto.tipo_producto,
                'stock_minimo': producto.stock_minimo,
                'stock_maximo': producto.stock_maximo,
            }
        }
    except ProductoAlmacen.DoesNotExist:
        data = {'success': False, 'error': 'Producto no encontrado'}
    
    return JsonResponse(data)

# ============================================================================
# VISTA DE ACCESO DENEGADO
# ============================================================================
@login_required
def acceso_denegado(request):
    """
    Vista para mostrar página de acceso denegado con información del error.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista se ejecuta cuando un usuario intenta acceder a una funcionalidad
    del módulo Almacén pero NO tiene el permiso necesario.
    
    Muestra información útil:
    - Mensaje de error personalizado
    - Permiso específico que se requería
    - Grupos/roles a los que pertenece el usuario
    - Sugerencia de contactar al administrador
    
    Parámetros GET:
        - mensaje: Descripción del error
        - permiso: Permiso que se requería (formato: 'app.permiso_modelo')
    
    Returns:
        Renderiza template almacen/acceso_denegado.html
    """
    # Obtener parámetros de la URL
    mensaje = request.GET.get(
        'mensaje', 
        'No tienes permisos para acceder a esta sección del módulo Almacén.'
    )
    permiso = request.GET.get('permiso', 'N/A')
    
    # Obtener grupos del usuario para mostrar información útil
    grupos = request.user.groups.all()
    
    context = {
        'mensaje': mensaje,
        'permiso_requerido': permiso,
        'grupos_usuario': grupos,
    }
    
    return render(request, 'almacen/acceso_denegado.html', context)

