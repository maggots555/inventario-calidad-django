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

Organización:
- Dashboard y vistas principales
- CRUD de Proveedores
- CRUD de Categorías  
- CRUD de Productos
- Gestión de Solicitudes
- Auditorías
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count, F, DecimalField
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.utils import timezone

from .models import (
    Proveedor,
    CategoriaAlmacen,
    ProductoAlmacen,
    CompraProducto,
    UnidadCompra,
    MovimientoAlmacen,
    SolicitudBaja,
    Auditoria,
    DiferenciaAuditoria,
    UnidadInventario,
    SolicitudCotizacion,
    LineaCotizacion,
    ImagenLineaCotizacion,
)
from .forms import (
    ProveedorForm,
    CategoriaAlmacenForm,
    ProductoAlmacenForm,
    CompraProductoForm,
    UnidadCompraForm,
    UnidadCompraFormSet,
    RecepcionCompraForm,
    ProblemaCompraForm,
    RechazoCotizacionForm,
    DevolucionCompraForm,
    MovimientoAlmacenForm,
    SolicitudBajaForm,
    ProcesarSolicitudForm,
    AuditoriaForm,
    DiferenciaAuditoriaForm,
    BusquedaProductoForm,
    EntradaRapidaForm,
    UnidadInventarioForm,
    UnidadInventarioFiltroForm,
    SolicitudCotizacionForm,
    LineaCotizacionForm,
    LineaCotizacionFormSet,
    SolicitudCotizacionFiltroForm,
    RespuestaLineaCotizacionForm,
    ImagenLineaCotizacionForm,
)
from inventario.models import Empleado


# ============================================================================
# DASHBOARD PRINCIPAL
# ============================================================================
@login_required
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
def detalle_producto(request, pk):
    """
    Muestra el detalle completo de un producto.
    
    Incluye:
    - Información general
    - Estado del stock
    - Historial de movimientos
    - Historial de compras
    - Órdenes de servicio vinculadas
    """
    producto = get_object_or_404(
        ProductoAlmacen.objects.select_related(
            'categoria', 'proveedor_principal', 'sucursal', 'creado_por'
        ),
        pk=pk
    )
    
    # Últimos movimientos
    movimientos = producto.movimientos.select_related(
        'empleado', 'orden_servicio'
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
def lista_solicitudes(request):
    """
    Lista de solicitudes de baja con filtros por estado.
    """
    solicitudes = SolicitudBaja.objects.select_related(
        'producto', 'unidad_inventario', 'solicitante', 'agente_almacen', 'orden_servicio'
    )
    
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
def crear_solicitud(request):
    """
    Crea una nueva solicitud de baja.
    """
    if request.method == 'POST':
        form = SolicitudBajaForm(request.POST)
        if form.is_valid():
            solicitud = form.save(commit=False)
            
            # Obtener empleado del usuario actual
            try:
                empleado = Empleado.objects.get(user=request.user)
                solicitud.solicitante = empleado
            except Empleado.DoesNotExist:
                messages.error(
                    request, 
                    'No tienes un perfil de empleado asociado. Contacta al administrador.'
                )
                return redirect('almacen:lista_solicitudes')
            
            solicitud.save()
            messages.success(request, 'Solicitud creada correctamente.')
            return redirect('almacen:lista_solicitudes')
    else:
        form = SolicitudBajaForm()
    
    context = {
        'form': form,
        'titulo': 'Nueva Solicitud de Baja',
    }
    
    return render(request, 'almacen/solicitudes/form_solicitud.html', context)


@login_required
def procesar_solicitud(request, pk):
    """
    Procesa (aprueba o rechaza) una solicitud de baja.
    Solo para agentes de almacén.
    """
    solicitud = get_object_or_404(
        SolicitudBaja.objects.select_related('producto', 'unidad_inventario', 'solicitante', 'orden_servicio'),
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
                solicitud.aprobar(agente, observaciones)
                messages.success(
                    request, 
                    f'Solicitud #{solicitud.pk} aprobada. Stock actualizado.'
                )
            else:
                solicitud.rechazar(agente, observaciones)
                messages.warning(request, f'Solicitud #{solicitud.pk} rechazada.')
            
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
def lista_movimientos(request):
    """
    Lista de movimientos de almacén (entradas y salidas).
    """
    movimientos = MovimientoAlmacen.objects.select_related(
        'producto', 'empleado', 'orden_servicio', 'solicitud_baja'
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


@login_required
def registrar_entrada(request):
    """
    Registra una entrada de productos al almacén.
    """
    if request.method == 'POST':
        form = EntradaRapidaForm(request.POST)
        if form.is_valid():
            producto = form.cleaned_data['producto']
            cantidad = form.cleaned_data['cantidad']
            costo_unitario = form.cleaned_data['costo_unitario']
            proveedor = form.cleaned_data.get('proveedor')
            numero_factura = form.cleaned_data.get('numero_factura', '')
            observaciones = form.cleaned_data.get('observaciones', '')
            
            # Obtener empleado
            try:
                empleado = Empleado.objects.get(user=request.user)
            except Empleado.DoesNotExist:
                messages.error(request, 'No tienes perfil de empleado asociado.')
                return redirect('almacen:dashboard')
            
            # Crear compra si hay proveedor
            compra = None
            if proveedor:
                compra = CompraProducto.objects.create(
                    producto=producto,
                    proveedor=proveedor,
                    cantidad=cantidad,
                    costo_unitario=costo_unitario,
                    fecha_pedido=timezone.now().date(),
                    fecha_recepcion=timezone.now().date(),
                    numero_factura=numero_factura,
                    registrado_por=request.user,
                )
            
            # Crear movimiento de entrada
            MovimientoAlmacen.objects.create(
                tipo='entrada',
                producto=producto,
                cantidad=cantidad,
                costo_unitario=costo_unitario,
                empleado=empleado,
                compra=compra,
                observaciones=observaciones,
            )
            
            messages.success(
                request,
                f'Entrada registrada: {cantidad} unidades de {producto.nombre}'
            )
            return redirect('almacen:detalle_producto', pk=producto.pk)
    else:
        form = EntradaRapidaForm()
    
    context = {
        'form': form,
        'titulo': 'Registrar Entrada',
    }
    
    return render(request, 'almacen/movimientos/form_entrada.html', context)


# ============================================================================
# API / AJAX ENDPOINTS
# ============================================================================
@login_required
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
# VISTAS: UNIDADES DE INVENTARIO
# ============================================================================

@login_required
def lista_unidades(request):
    """
    Lista de todas las unidades individuales de inventario.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista muestra todas las unidades físicas individuales registradas.
    
    Funcionalidades:
    - Filtrado por producto, marca, estado, disponibilidad, origen
    - Búsqueda por código interno, número de serie, modelo
    - Paginación para manejar grandes cantidades de unidades
    - Contadores de resumen (total, disponibles, por revisar)
    
    La diferencia con "lista_productos" es que aquí vemos cada unidad física
    individual, no el producto consolidado. Por ejemplo:
    - lista_productos: "SSD 1TB - Stock: 20"
    - lista_unidades: 20 registros individuales, cada uno con su marca/modelo/serie
    """
    
    # Inicializar queryset base
    unidades = UnidadInventario.objects.select_related(
        'producto',
        'producto__categoria',
        'compra',
        'orden_servicio_origen',
        'orden_servicio_destino',
    ).order_by('-fecha_registro')
    
    # Procesar filtros
    form_filtro = UnidadInventarioFiltroForm(request.GET or None)
    
    if form_filtro.is_valid():
        # Filtrar por producto
        producto = form_filtro.cleaned_data.get('producto')
        if producto:
            unidades = unidades.filter(producto=producto)
        
        # Filtrar por marca
        marca = form_filtro.cleaned_data.get('marca')
        if marca:
            unidades = unidades.filter(marca=marca)
        
        # Filtrar por estado
        estado = form_filtro.cleaned_data.get('estado')
        if estado:
            unidades = unidades.filter(estado=estado)
        
        # Filtrar por disponibilidad
        disponibilidad = form_filtro.cleaned_data.get('disponibilidad')
        if disponibilidad:
            unidades = unidades.filter(disponibilidad=disponibilidad)
        
        # Filtrar por origen
        origen = form_filtro.cleaned_data.get('origen')
        if origen:
            unidades = unidades.filter(origen=origen)
        
        # Búsqueda de texto
        buscar = form_filtro.cleaned_data.get('buscar')
        if buscar:
            unidades = unidades.filter(
                Q(codigo_interno__icontains=buscar) |
                Q(numero_serie__icontains=buscar) |
                Q(modelo__icontains=buscar) |
                Q(producto__nombre__icontains=buscar) |
                Q(notas__icontains=buscar)
            )
    
    # Contadores para resumen
    total_unidades = unidades.count()
    unidades_disponibles = unidades.filter(disponibilidad='disponible').count()
    unidades_para_revision = unidades.filter(estado='para_revision').count()
    unidades_defectuosas = unidades.filter(estado='defectuoso').count()
    
    # Paginación
    paginator = Paginator(unidades, 25)  # 25 unidades por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'form_filtro': form_filtro,
        'total_unidades': total_unidades,
        'unidades_disponibles': unidades_disponibles,
        'unidades_para_revision': unidades_para_revision,
        'unidades_defectuosas': unidades_defectuosas,
        'titulo': 'Unidades de Inventario',
    }
    
    return render(request, 'almacen/lista_unidades.html', context)


@login_required
def crear_unidad(request, producto_id=None):
    """
    Crear una nueva unidad de inventario.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista permite registrar una nueva unidad física individual.
    
    Si se proporciona producto_id, el formulario viene pre-seleccionado
    con ese producto (útil cuando se accede desde el detalle de un producto).
    
    Flujo:
    1. GET: Muestra formulario vacío (o con producto preseleccionado)
    2. POST: Valida datos y crea la unidad
    3. Redirige a la lista o al detalle del producto
    
    Parámetros:
    - producto_id (opcional): ID del producto para preseleccionar
    """
    
    # Si viene de un producto específico, preseleccionarlo
    producto_inicial = None
    if producto_id:
        producto_inicial = get_object_or_404(ProductoAlmacen, pk=producto_id, activo=True)
    
    if request.method == 'POST':
        form = UnidadInventarioForm(request.POST)
        
        if form.is_valid():
            unidad = form.save()
            
            messages.success(
                request,
                f'Unidad "{unidad.codigo_interno}" creada exitosamente.'
            )
            
            # Si vino de un producto, regresar al detalle del producto
            if producto_id:
                return redirect('almacen:detalle_producto', pk=producto_id)
            
            # Si no, ir a la lista de unidades
            return redirect('almacen:lista_unidades')
    else:
        # Preparar datos iniciales
        initial_data = {}
        if producto_inicial:
            initial_data['producto'] = producto_inicial
            initial_data['costo_unitario'] = producto_inicial.costo_unitario
        
        form = UnidadInventarioForm(initial=initial_data)
        
        # Si hay producto inicial, deshabilitar el campo para evitar cambios
        if producto_inicial:
            form.fields['producto'].widget.attrs['disabled'] = True
    
    context = {
        'form': form,
        'titulo': 'Registrar Nueva Unidad',
        'producto_inicial': producto_inicial,
    }
    
    return render(request, 'almacen/crear_unidad.html', context)


@login_required
def detalle_unidad(request, pk):
    """
    Detalle de una unidad específica de inventario.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Muestra toda la información de una unidad individual:
    - Datos del producto padre
    - Marca, modelo, número de serie
    - Estado y disponibilidad actual
    - Origen y trazabilidad (de dónde vino, a dónde fue)
    - Imágenes de referencia de la cotización (si aplica)
    - Historial de cambios (si implementado)
    
    También permite acciones rápidas como:
    - Cambiar estado/disponibilidad
    - Asignar a una orden de servicio
    - Marcar como defectuosa
    
    Trazabilidad de imágenes:
    - Si la unidad proviene de una cotización (compra.linea_cotizacion_origen)
    - Se muestran las imágenes de referencia que se subieron en la cotización
    - Esto permite verificar visualmente que la pieza recibida es correcta
    """
    
    unidad = get_object_or_404(
        UnidadInventario.objects.select_related(
            'producto',
            'producto__categoria',
            'producto__proveedor_principal',
            'compra',
            'compra__linea_cotizacion_origen',
            'compra__linea_cotizacion_origen__solicitud',
            'orden_servicio_origen',
            'orden_servicio_destino',
        ),
        pk=pk
    )
    
    # Obtener imágenes de cotización si existen
    # La trazabilidad es: UnidadInventario → compra → linea_cotizacion_origen → imagenes
    imagenes_cotizacion = None
    linea_cotizacion = None
    solicitud_cotizacion = None
    
    if unidad.compra:
        try:
            linea_cotizacion = unidad.compra.linea_cotizacion_origen
            if linea_cotizacion:
                solicitud_cotizacion = linea_cotizacion.solicitud
                imagenes_cotizacion = linea_cotizacion.imagenes.all()
        except:
            pass
    
    context = {
        'unidad': unidad,
        'titulo': f'Unidad: {unidad.codigo_interno}',
        'imagenes_cotizacion': imagenes_cotizacion,
        'linea_cotizacion': linea_cotizacion,
        'solicitud_cotizacion': solicitud_cotizacion,
    }
    
    return render(request, 'almacen/detalle_unidad.html', context)


@login_required
def editar_unidad(request, pk):
    """
    Editar una unidad de inventario existente.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Permite modificar los datos de una unidad existente.
    
    Restricciones:
    - El código interno no se puede cambiar (es autogenerado)
    - El producto padre no se puede cambiar (por integridad)
    - Los campos de sistema (fechas) son solo lectura
    
    Flujo:
    1. GET: Muestra formulario con datos actuales
    2. POST: Valida y guarda cambios
    3. Redirige al detalle de la unidad
    """
    
    unidad = get_object_or_404(UnidadInventario, pk=pk)
    
    if request.method == 'POST':
        form = UnidadInventarioForm(request.POST, instance=unidad)
        
        if form.is_valid():
            form.save()
            
            messages.success(
                request,
                f'Unidad "{unidad.codigo_interno}" actualizada exitosamente.'
            )
            
            return redirect('almacen:detalle_unidad', pk=pk)
    else:
        form = UnidadInventarioForm(instance=unidad)
        # El producto no se puede cambiar
        form.fields['producto'].widget.attrs['disabled'] = True
    
    context = {
        'form': form,
        'unidad': unidad,
        'titulo': f'Editar Unidad: {unidad.codigo_interno}',
    }
    
    return render(request, 'almacen/editar_unidad.html', context)


@login_required
def eliminar_unidad(request, pk):
    """
    Eliminar una unidad de inventario.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista maneja la eliminación de una unidad individual.
    
    ⚠️ IMPORTANTE: La eliminación es permanente. En un sistema de producción,
    considera implementar "soft delete" (marcar como eliminado en lugar de borrar).
    
    Restricciones:
    - Solo se pueden eliminar unidades que no estén asignadas a órdenes
    - Requiere confirmación (método POST)
    
    Flujo:
    1. GET: Muestra página de confirmación
    2. POST: Elimina la unidad y redirige
    """
    
    unidad = get_object_or_404(UnidadInventario, pk=pk)
    
    # Verificar que no esté asignada a una orden activa
    if unidad.orden_servicio_destino:
        messages.error(
            request,
            f'No se puede eliminar la unidad "{unidad.codigo_interno}" '
            f'porque está asignada a la orden {unidad.orden_servicio_destino}.'
        )
        return redirect('almacen:detalle_unidad', pk=pk)
    
    if request.method == 'POST':
        codigo = unidad.codigo_interno
        producto_id = unidad.producto.pk
        
        unidad.delete()
        
        messages.success(
            request,
            f'Unidad "{codigo}" eliminada exitosamente.'
        )
        
        # Regresar al detalle del producto
        return redirect('almacen:detalle_producto', pk=producto_id)
    
    context = {
        'unidad': unidad,
        'titulo': f'Eliminar Unidad: {unidad.codigo_interno}',
    }
    
    return render(request, 'almacen/eliminar_unidad.html', context)


@login_required
def cambiar_estado_unidad(request, pk):
    """
    Cambiar rápidamente el estado de una unidad (AJAX).
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta es una vista API que permite cambiar el estado de una unidad
    sin recargar toda la página (usando AJAX desde JavaScript).
    
    Acepta POST con:
    - estado: nuevo estado (nuevo, usado_bueno, defectuoso, etc.)
    - disponibilidad: nueva disponibilidad (disponible, reservada, etc.)
    
    Retorna JSON con el resultado.
    """
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    unidad = get_object_or_404(UnidadInventario, pk=pk)
    
    # Obtener nuevos valores
    nuevo_estado = request.POST.get('estado')
    nueva_disponibilidad = request.POST.get('disponibilidad')
    
    cambios = []
    
    # Validar y aplicar estado
    if nuevo_estado:
        estados_validos = [e[0] for e in UnidadInventario._meta.get_field('estado').choices]
        if nuevo_estado in estados_validos:
            unidad.estado = nuevo_estado
            cambios.append(f'estado a {unidad.get_estado_display()}')
    
    # Validar y aplicar disponibilidad
    if nueva_disponibilidad:
        disponibilidades_validas = [d[0] for d in UnidadInventario._meta.get_field('disponibilidad').choices]
        if nueva_disponibilidad in disponibilidades_validas:
            unidad.disponibilidad = nueva_disponibilidad
            cambios.append(f'disponibilidad a {unidad.get_disponibilidad_display()}')
    
    if cambios:
        unidad.save()
        return JsonResponse({
            'success': True,
            'message': f'Unidad actualizada: {", ".join(cambios)}',
            'estado': unidad.estado,
            'estado_display': unidad.get_estado_display(),
            'disponibilidad': unidad.disponibilidad,
            'disponibilidad_display': unidad.get_disponibilidad_display(),
        })
    
    return JsonResponse({'success': False, 'error': 'No se proporcionaron cambios válidos'})


@login_required
def unidades_por_producto(request, producto_id):
    """
    Lista de unidades para un producto específico.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista muestra solo las unidades de un producto específico.
    
    Es útil cuando se accede desde el detalle de un producto y se quiere
    ver todas sus unidades individuales con más detalle.
    
    Incluye:
    - Resumen por marca (cuántas de cada marca)
    - Resumen por estado (cuántas nuevas, usadas, defectuosas)
    - Lista AGRUPADA de unidades (expandibles por grupo)
    
    AGRUPACIÓN:
    Las unidades se agrupan por: Producto + Marca + Modelo + Estado + Origen
    Esto permite mostrar "10 unidades" en lugar de 10 filas separadas.
    """
    
    producto = get_object_or_404(ProductoAlmacen, pk=producto_id)
    
    # Obtener unidades del producto
    unidades = UnidadInventario.objects.filter(
        producto=producto
    ).select_related(
        'compra',
        'orden_servicio_origen',
        'orden_servicio_destino',
    ).order_by('-fecha_registro')
    
    # Resumen por marca
    resumen_marcas = unidades.values('marca').annotate(
        cantidad=Count('id')
    ).order_by('-cantidad')
    
    # Resumen por estado
    resumen_estados = unidades.values('estado').annotate(
        cantidad=Count('id')
    ).order_by('estado')
    
    # Resumen por disponibilidad
    resumen_disponibilidad = unidades.values('disponibilidad').annotate(
        cantidad=Count('id')
    ).order_by('disponibilidad')
    
    # AGRUPACIÓN DE UNIDADES
    # Agrupar por marca, modelo, estado y origen para mostrar grupos expandibles
    from itertools import groupby
    from operator import attrgetter
    
    # Ordenar para que groupby funcione correctamente
    unidades_ordenadas = unidades.order_by('marca', 'modelo', 'estado', 'origen', '-fecha_registro')
    
    # Agrupar unidades
    grupos = []
    for key, group in groupby(unidades_ordenadas, key=lambda u: (u.marca or 'Sin marca', u.modelo or 'Sin modelo', u.estado, u.origen)):
        unidades_grupo = list(group)
        marca, modelo, estado, origen = key
        
        # Calcular estadísticas del grupo
        disponibles_grupo = sum(1 for u in unidades_grupo if u.disponibilidad == 'disponible')
        costo_promedio = sum(u.costo_unitario or 0 for u in unidades_grupo) / len(unidades_grupo) if unidades_grupo else 0
        
        grupos.append({
            'marca': marca,
            'modelo': modelo,
            'estado': estado,
            'origen': origen,
            'cantidad': len(unidades_grupo),
            'unidades': unidades_grupo,
            'disponibles': disponibles_grupo,
            'costo_promedio': costo_promedio,
        })
    
    # Paginación de grupos (no de unidades individuales)
    paginator = Paginator(grupos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'producto': producto,
        'page_obj': page_obj,
        'total_unidades': unidades.count(),
        'unidades_disponibles': unidades.filter(disponibilidad='disponible').count(),
        'resumen_marcas': resumen_marcas,
        'resumen_estados': resumen_estados,
        'resumen_disponibilidad': resumen_disponibilidad,
        'titulo': f'Unidades de: {producto.nombre}',
        'vista_agrupada': True,  # Indicador para el template
    }
    
    return render(request, 'almacen/unidades_por_producto.html', context)


@login_required
def api_unidad_info(request, pk):
    """
    API para obtener información de una unidad específica (JSON).
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista devuelve información de una unidad en formato JSON.
    
    Es útil para:
    - Mostrar tooltips o modales sin recargar la página
    - Integración con otros sistemas
    - Consultas AJAX desde JavaScript
    """
    
    try:
        unidad = UnidadInventario.objects.select_related('producto').get(pk=pk)
        
        data = {
            'success': True,
            'unidad': {
                'id': unidad.pk,
                'codigo_interno': unidad.codigo_interno,
                'producto_nombre': unidad.producto.nombre,
                'producto_id': unidad.producto.pk,
                'numero_serie': unidad.numero_serie or '',
                'marca': unidad.marca or '',
                'modelo': unidad.modelo or '',
                'estado': unidad.estado,
                'estado_display': unidad.get_estado_display(),
                'disponibilidad': unidad.disponibilidad,
                'disponibilidad_display': unidad.get_disponibilidad_display(),
                'origen': unidad.origen,
                'origen_display': unidad.get_origen_display(),
                'costo_unitario': float(unidad.costo_unitario) if unidad.costo_unitario else 0,
                'ubicacion_especifica': unidad.ubicacion_especifica or '',
                'fecha_registro': unidad.fecha_registro.strftime('%d/%m/%Y %H:%M') if unidad.fecha_registro else '',
                'notas': unidad.notas or '',
            }
        }
    except UnidadInventario.DoesNotExist:
        data = {'success': False, 'error': 'Unidad no encontrada'}
    
    return JsonResponse(data)


@login_required
def api_unidades_producto(request):
    """
    API para obtener las unidades disponibles de un producto (JSON).
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista se usa en el formulario de solicitud de baja.
    Cuando el usuario selecciona un producto, JavaScript llama a esta API
    para obtener las unidades específicas (con marca/modelo/serie) disponibles.
    
    Parámetros GET:
    - producto_id: ID del ProductoAlmacen
    
    Retorna:
    - Lista de unidades disponibles del producto
    - Información de stock del producto
    """
    producto_id = request.GET.get('producto_id')
    
    if not producto_id:
        return JsonResponse({
            'success': False,
            'error': 'Se requiere producto_id',
            'unidades': [],
            'stock_info': ''
        })
    
    try:
        producto = ProductoAlmacen.objects.get(pk=producto_id)
        
        # Obtener unidades disponibles
        unidades = UnidadInventario.objects.filter(
            producto_id=producto_id,
            disponibilidad='disponible'
        ).order_by('marca', 'modelo', 'fecha_registro')
        
        # Construir lista de unidades
        unidades_data = []
        for u in unidades:
            unidades_data.append({
                'id': u.pk,
                'codigo_interno': u.codigo_interno or '',
                'numero_serie': u.numero_serie or '',
                'marca': u.marca or '',
                'modelo': u.modelo or '',
                'estado': u.estado,
                'estado_display': u.get_estado_display(),
                'disponibilidad': u.disponibilidad,
                'origen': u.origen,
                'origen_display': u.get_origen_display(),
            })
        
        # Info de stock
        stock_info = f"Stock disponible: {producto.stock_actual} unidades"
        if unidades_data:
            stock_info += f" ({len(unidades_data)} con seguimiento individual)"
        
        return JsonResponse({
            'success': True,
            'producto_id': producto.pk,
            'producto_nombre': producto.nombre,
            'stock_actual': producto.stock_actual,
            'stock_info': stock_info,
            'unidades': unidades_data,
            'total_unidades': len(unidades_data)
        })
        
    except ProductoAlmacen.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Producto no encontrado',
            'unidades': [],
            'stock_info': ''
        })


@login_required
def api_tecnicos_disponibles(request):
    """
    API para obtener la lista de técnicos de laboratorio disponibles (JSON).
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista se usa en el formulario de solicitud de baja.
    Cuando el usuario selecciona "Servicio Técnico" como tipo de solicitud,
    JavaScript llama a esta API para obtener la lista de técnicos disponibles.
    
    Los técnicos se filtran por:
    - activo=True: Solo empleados activos
    - cargo__icontains='TECNICO DE LABORATORIO': Solo técnicos de laboratorio
    
    Retorna:
    - success: bool indicando si la operación fue exitosa
    - tecnicos: Lista de técnicos con id y nombre
    - total: Cantidad de técnicos disponibles
    
    Ejemplo de respuesta:
    {
        "success": true,
        "tecnicos": [
            {"id": 1, "nombre": "Juan Pérez", "sucursal": "Matriz"},
            {"id": 2, "nombre": "María García", "sucursal": "Sucursal Norte"}
        ],
        "total": 2
    }
    """
    # Importar Empleado desde inventario
    from inventario.models import Empleado
    
    try:
        # Filtrar técnicos de laboratorio activos
        tecnicos = Empleado.objects.filter(
            activo=True,
            cargo__icontains='TECNICO DE LABORATORIO'
        ).select_related('sucursal').order_by('nombre_completo')
        
        # Construir lista de técnicos
        tecnicos_data = []
        for tecnico in tecnicos:
            tecnicos_data.append({
                'id': tecnico.pk,
                'nombre': tecnico.nombre_completo,
                'cargo': tecnico.cargo,
                'sucursal': tecnico.sucursal.nombre if tecnico.sucursal else 'Sin asignar',
            })
        
        return JsonResponse({
            'success': True,
            'tecnicos': tecnicos_data,
            'total': len(tecnicos_data)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'tecnicos': [],
            'total': 0
        })


# ============================================================================
# API: BUSCAR O CREAR ORDEN DE SERVICIO POR ORDEN_CLIENTE
# ============================================================================
@login_required
def api_buscar_crear_orden_cliente(request):
    """
    API para buscar una orden de servicio por orden_cliente o crearla si no existe.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta API se usa en el formulario de solicitud de baja del almacén.
    Permite al usuario:
    1. Buscar órdenes existentes escribiendo el número de orden del cliente
    2. Si no existe, crear automáticamente una nueva orden de servicio
    
    El campo orden_cliente está en el modelo DetalleEquipo (no en OrdenServicio),
    por eso buscamos en DetalleEquipo y accedemos a la orden a través de la relación.
    
    VALIDACIÓN DE FORMATO:
    - El número de orden debe empezar con 'OOW-' o 'FL-'
    - Ejemplo válido: 'OOW-12345' o 'FL-2025-001'
    
    MÉTODOS HTTP:
    - GET: Buscar orden existente por orden_cliente
    - POST: Crear nueva orden si no existe
    
    PARÁMETROS GET:
    - orden_cliente: Número de orden del cliente a buscar
    
    PARÁMETROS POST (JSON):
    - orden_cliente: Número de orden del cliente
    - sucursal_id: ID de la sucursal donde se registra
    - tecnico_id: ID del técnico asignado (obligatorio para servicio técnico)
    
    RETORNA:
    {
        "success": true/false,
        "found": true/false (si se encontró orden existente),
        "created": true/false (si se creó nueva orden),
        "orden_id": int (ID de OrdenServicio),
        "orden_cliente": str,
        "numero_orden_interno": str,
        "estado": str,
        "sucursal": str,
        "error": str (si hay error)
    }
    """
    import re
    import json
    from servicio_tecnico.models import OrdenServicio, DetalleEquipo
    from inventario.models import Sucursal, Empleado
    
    # Validar formato de orden_cliente (debe empezar con OOW- o FL-)
    def validar_formato_orden(orden_cliente: str) -> tuple[bool, str]:
        """
        Valida que el número de orden tenga el formato correcto.
        
        Retorna:
        - (True, '') si el formato es válido
        - (False, 'mensaje de error') si el formato es inválido
        """
        if not orden_cliente:
            return False, 'El número de orden es requerido'
        
        orden_cliente = orden_cliente.strip().upper()
        
        # Verificar que empiece con OOW- o FL-
        if not (orden_cliente.startswith('OOW-') or orden_cliente.startswith('FL-')):
            return False, 'El número de orden debe empezar con "OOW-" o "FL-"'
        
        return True, ''
    
    if request.method == 'GET':
        # ========== MODO BÚSQUEDA ==========
        orden_cliente = request.GET.get('orden_cliente', '').strip().upper()
        
        if not orden_cliente:
            return JsonResponse({
                'success': False,
                'error': 'Se requiere el parámetro orden_cliente',
                'found': False
            })
        
        # Validar formato
        formato_valido, error_formato = validar_formato_orden(orden_cliente)
        if not formato_valido:
            return JsonResponse({
                'success': False,
                'error': error_formato,
                'found': False,
                'formato_invalido': True
            })
        
        # Buscar en DetalleEquipo por orden_cliente
        try:
            detalle = DetalleEquipo.objects.select_related(
                'orden', 'orden__sucursal'
            ).get(orden_cliente__iexact=orden_cliente)
            
            orden = detalle.orden
            
            return JsonResponse({
                'success': True,
                'found': True,
                'created': False,
                'orden_id': orden.pk,
                'orden_cliente': detalle.orden_cliente,
                'numero_orden_interno': orden.numero_orden_interno,
                'estado': orden.estado,
                'estado_display': orden.get_estado_display(),
                'sucursal': orden.sucursal.nombre if orden.sucursal else 'Sin asignar',
            })
            
        except DetalleEquipo.DoesNotExist:
            # No se encontró, indicar que se puede crear
            return JsonResponse({
                'success': True,
                'found': False,
                'created': False,
                'orden_cliente': orden_cliente,
                'mensaje': f'No se encontró orden con número "{orden_cliente}". Se puede crear automáticamente.'
            })
            
        except DetalleEquipo.MultipleObjectsReturned:
            # Caso raro: múltiples órdenes con mismo orden_cliente
            return JsonResponse({
                'success': False,
                'error': f'Se encontraron múltiples órdenes con el número "{orden_cliente}". Contacte al administrador.',
                'found': False
            })
    
    elif request.method == 'POST':
        # ========== MODO CREACIÓN ==========
        try:
            # Parsear datos JSON del body
            data = json.loads(request.body)
            orden_cliente = data.get('orden_cliente', '').strip().upper()
            sucursal_id = data.get('sucursal_id')
            tecnico_id = data.get('tecnico_id')
            
            # Determinar tipo de servicio según el tipo de solicitud
            # 'servicio_tecnico' → 'diagnostico', 'venta_mostrador' → 'venta_mostrador'
            tipo_solicitud = data.get('tipo_solicitud', 'servicio_tecnico')
            tipo_servicio = 'venta_mostrador' if tipo_solicitud == 'venta_mostrador' else 'diagnostico'
            
            # Validar formato
            formato_valido, error_formato = validar_formato_orden(orden_cliente)
            if not formato_valido:
                return JsonResponse({
                    'success': False,
                    'error': error_formato,
                    'created': False,
                    'formato_invalido': True
                })
            
            # Validar que no exista ya
            if DetalleEquipo.objects.filter(orden_cliente__iexact=orden_cliente).exists():
                return JsonResponse({
                    'success': False,
                    'error': f'Ya existe una orden con el número "{orden_cliente}"',
                    'created': False
                })
            
            # Validar sucursal
            if not sucursal_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Se requiere seleccionar una sucursal',
                    'created': False
                })
            
            try:
                sucursal = Sucursal.objects.get(pk=sucursal_id)
            except Sucursal.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Sucursal no válida',
                    'created': False
                })
            
            # Validar técnico
            if not tecnico_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Se requiere seleccionar un técnico',
                    'created': False
                })
            
            try:
                tecnico = Empleado.objects.get(pk=tecnico_id)
            except Empleado.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Técnico no válido',
                    'created': False
                })
            
            # Obtener empleado del usuario actual (responsable de seguimiento)
            try:
                responsable = Empleado.objects.get(user=request.user)
            except Empleado.DoesNotExist:
                # Si el usuario no tiene empleado asociado, usar el técnico como responsable
                responsable = tecnico
            
            # ========== CREAR ORDEN DE SERVICIO ==========
            # tipo_servicio: 'diagnostico' para Servicio Técnico, 'venta_mostrador' para Venta Mostrador
            orden = OrdenServicio.objects.create(
                sucursal=sucursal,
                responsable_seguimiento=responsable,
                tecnico_asignado_actual=tecnico,
                estado='almacen',  # Estado especial: Proveniente de Almacén
                tipo_servicio=tipo_servicio,  # Dinámico según tipo de solicitud
            )
            
            # ========== CREAR DETALLE DE EQUIPO ==========
            # Crear DetalleEquipo con datos mínimos requeridos
            DetalleEquipo.objects.create(
                orden=orden,
                orden_cliente=orden_cliente,
                tipo_equipo='Laptop',  # Valor por defecto
                marca='Otra',  # Marca genérica - se actualizará después
                modelo='Por definir',  # Se actualizará después
                numero_serie='ALMACEN-' + orden_cliente,  # Placeholder
                gama='media',  # Valor por defecto
                falla_principal='Orden creada desde Almacén - Pendiente de registrar falla',
                email_cliente='pendiente@actualizar.com',  # Placeholder
            )
            
            # Determinar descripción del tipo de orden para el mensaje
            tipo_orden_desc = 'Venta Mostrador' if tipo_servicio == 'venta_mostrador' else 'Diagnóstico'
            
            return JsonResponse({
                'success': True,
                'found': False,
                'created': True,
                'orden_id': orden.pk,
                'orden_cliente': orden_cliente,
                'numero_orden_interno': orden.numero_orden_interno,
                'estado': orden.estado,
                'estado_display': orden.get_estado_display(),
                'sucursal': sucursal.nombre,
                'tipo_servicio': tipo_servicio,
                'mensaje': f'Orden "{orden_cliente}" ({tipo_orden_desc}) creada exitosamente con estado "Proveniente de Almacén"'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Datos JSON inválidos',
                'created': False
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error al crear la orden: {str(e)}',
                'created': False
            })
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Método no permitido. Use GET para buscar o POST para crear.',
            'found': False
        }, status=405)


# ============================================================================
# COMPRAS Y COTIZACIONES
# ============================================================================

@login_required
def lista_compras(request):
    """
    Lista de todas las compras y cotizaciones.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista muestra una tabla con todas las compras/cotizaciones,
    permitiendo filtrar por tipo, estado, producto y proveedor.
    
    Filtros disponibles:
    - tipo: 'cotizacion' o 'compra'
    - estado: cualquier estado del workflow
    - producto: ID del producto
    - proveedor: ID del proveedor
    - orden_cliente: búsqueda por número de orden visible
    """
    compras = CompraProducto.objects.select_related(
        'producto', 'proveedor', 'orden_servicio', 'registrado_por'
    ).prefetch_related('unidades_compra')
    
    # Filtro por tipo
    tipo = request.GET.get('tipo', '')
    if tipo:
        compras = compras.filter(tipo=tipo)
    
    # Filtro por estado
    estado = request.GET.get('estado', '')
    if estado:
        compras = compras.filter(estado=estado)
    
    # Filtro por producto
    producto_id = request.GET.get('producto', '')
    if producto_id:
        compras = compras.filter(producto_id=producto_id)
    
    # Filtro por proveedor
    proveedor_id = request.GET.get('proveedor', '')
    if proveedor_id:
        compras = compras.filter(proveedor_id=proveedor_id)
    
    # Búsqueda por orden_cliente
    orden_cliente = request.GET.get('orden_cliente', '').strip()
    if orden_cliente:
        compras = compras.filter(orden_cliente__icontains=orden_cliente)
    
    compras = compras.order_by('-fecha_registro')
    
    # Paginación
    paginator = Paginator(compras, 25)
    page = request.GET.get('page', 1)
    compras_page = paginator.get_page(page)
    
    # Datos para filtros
    productos = ProductoAlmacen.objects.filter(activo=True).order_by('nombre')
    proveedores = Proveedor.objects.filter(activo=True).order_by('nombre')
    
    context = {
        'compras': compras_page,
        'productos': productos,
        'proveedores': proveedores,
        'tipo_filtro': tipo,
        'estado_filtro': estado,
        'producto_filtro': producto_id,
        'proveedor_filtro': proveedor_id,
        'orden_cliente_filtro': orden_cliente,
    }
    
    return render(request, 'almacen/compras/lista_compras.html', context)


@login_required
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
    - enviada_cliente: Esperando respuesta del cliente
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
    cotizaciones_pendientes = SolicitudCotizacion.objects.filter(
        estado='enviada_cliente'
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
    
    return render(request, 'almacen/compras/panel_cotizaciones.html', context)


@login_required
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
            
            compra.save()
            
            # Ahora procesar el formset de unidades
            formset = UnidadCompraFormSet(request.POST, prefix='unidades', instance=compra)
            
            if formset.is_valid():
                unidades = formset.save(commit=False)
                
                # Asignar número de línea secuencial
                for i, unidad in enumerate(unidades, start=1):
                    unidad.numero_linea = i
                    unidad.save()
                
                # Eliminar las marcadas para borrar
                for obj in formset.deleted_objects:
                    obj.delete()
                
                # CORRECCIÓN: Crear UnidadCompra genéricas si faltan para completar la cantidad
                # Esto asegura que siempre haya tantas UnidadCompra como unidades se compraron
                unidades_existentes = compra.unidades_compra.count()
                if unidades_existentes < compra.cantidad:
                    # MEJORA: Buscar la primera unidad con datos para copiar marca/modelo
                    # Si el usuario especificó "Kingston A400" en la primera, las demás heredan esos datos
                    primera_unidad = compra.unidades_compra.first()
                    
                    # Valores por defecto (si no hay ninguna unidad especificada)
                    marca_base = 'Genérico/Sin marca'
                    modelo_base = ''
                    especificaciones_base = ''
                    costo_base = None
                    
                    # Si existe una unidad especificada, copiar sus datos
                    if primera_unidad:
                        marca_base = primera_unidad.marca or marca_base
                        modelo_base = primera_unidad.modelo or modelo_base
                        especificaciones_base = primera_unidad.especificaciones or especificaciones_base
                        costo_base = primera_unidad.costo_unitario
                    
                    # Crear las unidades faltantes heredando los datos de la primera
                    for i in range(unidades_existentes + 1, compra.cantidad + 1):
                        from almacen.models import UnidadCompra
                        UnidadCompra.objects.create(
                            compra=compra,
                            numero_linea=i,
                            marca=marca_base,
                            modelo=modelo_base,
                            especificaciones=especificaciones_base,
                            costo_unitario=costo_base,
                            estado='pendiente',
                            notas='Unidad creada automáticamente (datos heredados de primera unidad)'
                        )
                
                messages.success(
                    request,
                    f'Compra #{compra.pk} creada exitosamente para {compra.producto.nombre} ({compra.cantidad} unidades)'
                )
                return redirect('almacen:detalle_compra', pk=compra.pk)
            else:
                # Si el formset tiene errores, eliminar la compra creada
                compra.delete()
                messages.error(request, 'Error en los detalles de unidades. Verifica los datos.')
        else:
            messages.error(request, 'Error en el formulario. Verifica los datos.')
            formset = UnidadCompraFormSet(request.POST, prefix='unidades')
    else:
        form = CompraProductoForm(initial={
            'fecha_pedido': timezone.now().date(),
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
    compra = get_object_or_404(
        CompraProducto.objects.select_related(
            'producto', 'proveedor', 'orden_servicio', 'registrado_por'
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
def editar_compra(request, pk):
    """
    Editar una compra o cotización existente.
    
    NOTA: Solo se puede editar si no ha sido recibida o está en estado final.
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
            form.save()
            
            unidades = formset.save(commit=False)
            
            # Reasignar números de línea
            for i, unidad in enumerate(unidades, start=1):
                unidad.numero_linea = i
                unidad.save()
            
            for obj in formset.deleted_objects:
                obj.delete()
            
            messages.success(request, 'Compra actualizada exitosamente.')
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
def recibir_compra(request, pk):
    """
    Confirmar la recepción de una compra.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cuando llega la compra al almacén:
    1. Se registra la fecha de recepción
    2. Se crean MovimientoAlmacen de entrada (actualiza stock)
    3. Se pueden crear UnidadInventario automáticamente
    4. El estado cambia a 'recibida'
    """
    compra = get_object_or_404(
        CompraProducto.objects.select_related('producto'),
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
            observaciones = form.cleaned_data.get('observaciones', '')
            
            # Obtener empleado para el movimiento
            try:
                empleado = Empleado.objects.get(user=request.user)
            except Empleado.DoesNotExist:
                messages.error(request, 'No tienes perfil de empleado asociado.')
                return redirect('almacen:detalle_compra', pk=pk)
            
            # Recibir la compra
            if compra.recibir(fecha_recepcion=fecha_recepcion, crear_unidades=False):
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
                if crear_unidades:
                    unidades_compra = compra.unidades_compra.filter(estado='pendiente')
                    
                    # Obtener descripción de la línea de cotización si existe
                    # Esta descripción contiene detalles como "RAM DDR4 16GB Kingston Fury"
                    descripcion_pieza = ''
                    orden_servicio = None
                    if hasattr(compra, 'linea_cotizacion_origen') and compra.linea_cotizacion_origen:
                        descripcion_pieza = compra.linea_cotizacion_origen.descripcion_pieza
                        # Obtener la orden de servicio desde la solicitud de cotización
                        if compra.linea_cotizacion_origen.solicitud:
                            orden_servicio = compra.linea_cotizacion_origen.solicitud.orden_servicio
                    
                    # CORRECCIÓN: Procesar unidades existentes Y crear las faltantes
                    unidades_creadas = 0
                    
                    if unidades_compra.exists():
                        # Procesar las unidades definidas
                        for unidad_compra in unidades_compra:
                            unidad_compra.recibir(crear_unidad_inventario=True)
                            unidades_creadas += 1
                    
                    # IMPORTANTE: Si hay menos UnidadCompra que la cantidad total,
                    # crear las unidades faltantes heredando datos de la primera
                    if unidades_creadas < compra.cantidad:
                        # MEJORA: Buscar la primera UnidadCompra para heredar marca/modelo
                        primera_unidad_compra = compra.unidades_compra.first()
                        
                        # Valores por defecto
                        marca_base = 'Genérico/Sin marca'
                        modelo_base = descripcion_pieza if descripcion_pieza else ''
                        especificaciones_base = ''
                        costo_base = compra.costo_unitario
                        
                        # Si existe una UnidadCompra, heredar sus datos
                        if primera_unidad_compra:
                            marca_base = primera_unidad_compra.marca or marca_base
                            modelo_base = primera_unidad_compra.modelo or modelo_base
                            especificaciones_base = primera_unidad_compra.especificaciones or especificaciones_base
                            if primera_unidad_compra.costo_unitario:
                                costo_base = primera_unidad_compra.costo_unitario
                        
                        for i in range(unidades_creadas, compra.cantidad):
                            # Si viene de cotización con orden, ya está asignada
                            # Si no tiene orden, queda disponible
                            disponibilidad = 'asignada' if orden_servicio else 'disponible'
                            
                            UnidadInventario.objects.create(
                                producto=compra.producto,
                                estado='nuevo',
                                disponibilidad=disponibilidad,
                                origen='compra',
                                compra=compra,
                                costo_unitario=costo_base,
                                registrado_por=request.user,
                                # Heredar marca/modelo de la primera unidad especificada
                                marca=marca_base,
                                modelo=modelo_base,
                                especificaciones=especificaciones_base,
                                # Vincular con la orden de servicio de la cotización
                                orden_servicio_destino=orden_servicio,
                                notas=f'Creada desde compra #{compra.pk} (unidad {i+1}/{compra.cantidad}, datos heredados)',
                            )
                            unidades_creadas += 1
                
                messages.success(
                    request,
                    f'Compra #{compra.pk} recibida. {compra.cantidad} unidades agregadas al inventario.'
                )
            else:
                messages.error(request, 'Error al recibir la compra.')
            
            return redirect('almacen:detalle_compra', pk=pk)
    else:
        form = RecepcionCompraForm(initial={
            'fecha_recepcion': timezone.now().date(),
            'crear_unidades': True,
        })
    
    context = {
        'compra': compra,
        'form': form,
    }
    
    return render(request, 'almacen/compras/recibir_compra.html', context)


@login_required
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
    """
    compra = get_object_or_404(CompraProducto, pk=compra_pk)
    unidad = get_object_or_404(UnidadCompra, pk=pk, compra=compra)
    
    if not unidad.puede_recibir():
        messages.error(request, 'Esta unidad no puede ser recibida.')
        return redirect('almacen:detalle_compra', pk=compra_pk)
    
    if request.method == 'POST':
        unidad_inv = unidad.recibir(crear_unidad_inventario=True)
        if unidad_inv:
            messages.success(
                request,
                f'Unidad #{unidad.numero_linea} recibida. Inventario: {unidad_inv.codigo_interno}'
            )
        else:
            messages.error(request, 'Error al recibir la unidad.')
    
    return redirect('almacen:detalle_compra', pk=compra_pk)


@login_required
def problema_unidad_compra(request, compra_pk, pk):
    """
    Reportar problema con una unidad específica de una compra.
    """
    compra = get_object_or_404(CompraProducto, pk=compra_pk)
    unidad = get_object_or_404(UnidadCompra, pk=pk, compra=compra)
    
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
    }
    
    return render(request, 'almacen/cotizaciones/lista_solicitudes.html', context)


@login_required
def crear_solicitud_cotizacion(request):
    """
    Crear una nueva solicitud de cotización con múltiples líneas.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista maneja la creación de una solicitud de cotización.
    
    El proceso tiene dos partes:
    1. El formulario principal (SolicitudCotizacionForm) captura:
       - Número de orden del cliente (para vincular con servicio técnico)
       - Observaciones internas
    
    2. El formset (LineaCotizacionFormSet) captura las líneas:
       - Cada línea tiene: producto, descripción, proveedor, cantidad, costo
       - Se pueden agregar múltiples líneas dinámicamente con JavaScript
    
    Flujo:
    1. GET: Muestra formularios vacíos
    2. POST: Valida ambos formularios
       - Si válidos: Guarda solicitud y líneas, redirige a detalle
       - Si inválidos: Muestra errores
    """
    if request.method == 'POST':
        form = SolicitudCotizacionForm(request.POST)
        formset = LineaCotizacionFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            # Guardar la solicitud (cabecera)
            solicitud = form.save(commit=False)
            solicitud.creado_por = request.user
            solicitud.save()
            
            # Guardar las líneas (detalle)
            formset.instance = solicitud
            formset.save()
            
            messages.success(
                request,
                f'Solicitud de cotización {solicitud.numero_solicitud} creada exitosamente.'
            )
            return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud.pk)
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = SolicitudCotizacionForm()
        formset = LineaCotizacionFormSet()
    
    context = {
        'form': form,
        'formset': formset,
        'titulo': 'Nueva Solicitud de Cotización',
        'es_creacion': True,
    }
    
    return render(request, 'almacen/cotizaciones/form_solicitud.html', context)


@login_required
def editar_solicitud_cotizacion(request, pk):
    """
    Editar una solicitud de cotización existente.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Similar a crear, pero carga los datos existentes en los formularios.
    
    Solo se puede editar si la solicitud está en estado 'borrador'.
    Una vez enviada al cliente, no se puede modificar.
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
            
            messages.success(request, 'Solicitud actualizada exitosamente.')
            return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = SolicitudCotizacionForm(instance=solicitud)
        formset = LineaCotizacionFormSet(instance=solicitud)
    
    context = {
        'form': form,
        'formset': formset,
        'solicitud': solicitud,
        'titulo': f'Editar Solicitud {solicitud.numero_solicitud}',
        'es_creacion': False,
    }
    
    return render(request, 'almacen/cotizaciones/form_solicitud.html', context)


@login_required
def detalle_solicitud_cotizacion(request, pk):
    """
    Ver detalle completo de una solicitud de cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista muestra toda la información de una solicitud:
    - Datos de la cabecera (número, orden vinculada, estado)
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
            'creado_por'
        ).prefetch_related(
            'lineas__producto',
            'lineas__proveedor',
            'lineas__compra_generada',
            'lineas__imagenes',  # Incluir imágenes de cada línea
        ),
        pk=pk
    )
    
    # Información del equipo desde DetalleEquipo si está vinculada la orden
    info_orden = None
    if solicitud.orden_servicio:
        try:
            info_orden = solicitud.orden_servicio.detalle_equipo
        except:
            pass
    
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
    
    context = {
        'solicitud': solicitud,
        'info_orden': info_orden,
        'titulo': f'Solicitud {solicitud.numero_solicitud}',
        'puede_subir_imagenes': puede_subir_imagenes,
        'max_imagenes_por_linea': ImagenLineaCotizacion.MAX_IMAGENES_POR_LINEA,
    }
    
    return render(request, 'almacen/cotizaciones/detalle_solicitud.html', context)


@login_required
def enviar_solicitud_cliente(request, pk):
    """
    Cambiar estado de la solicitud a 'enviada_cliente'.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta acción marca la solicitud como lista para compartir con el cliente.
    Recepción podrá entonces enviarla y registrar las respuestas.
    
    Requisitos:
    - Estado debe ser 'borrador'
    - Debe tener al menos una línea
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if request.method == 'POST':
        if solicitud.enviar_a_cliente():
            messages.success(
                request,
                f'Solicitud {solicitud.numero_solicitud} enviada a cliente. '
                'Recepción puede ahora compartirla y registrar respuestas.'
            )
        else:
            messages.error(
                request,
                'No se puede enviar la solicitud. Verifica que esté en estado '
                'borrador y tenga al menos una línea.'
            )
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
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
                if linea.aprobar():
                    messages.success(
                        request,
                        f'Línea #{linea.numero_linea} aprobada por el cliente.'
                    )
                else:
                    messages.error(request, 'No se pudo aprobar la línea.')
            else:  # rechazar
                if linea.rechazar(motivo=motivo):
                    messages.warning(
                        request,
                        f'Línea #{linea.numero_linea} rechazada por el cliente.'
                    )
                else:
                    messages.error(request, 'No se pudo rechazar la línea.')
        else:
            messages.error(request, 'Por favor corrige los errores.')
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud_pk)


@login_required
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
        lineas_pendientes = solicitud.lineas.filter(estado_cliente='pendiente')
        aprobadas = 0
        
        for linea in lineas_pendientes:
            if linea.aprobar():
                aprobadas += 1
        
        if aprobadas > 0:
            messages.success(
                request,
                f'Se aprobaron {aprobadas} línea(s) de la cotización.'
            )
        else:
            messages.info(request, 'No había líneas pendientes por aprobar.')
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
def rechazar_todas_lineas(request, pk):
    """
    Rechazar todas las líneas pendientes de una solicitud.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Atajo para cuando el cliente rechaza toda la cotización.
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
                f'Se rechazaron {rechazadas} línea(s) de la cotización.'
            )
        else:
            messages.info(request, 'No había líneas pendientes por rechazar.')
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
def generar_compras_solicitud(request, pk):
    """
    Genera CompraProducto para las líneas aprobadas.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Una vez que el cliente ha aprobado las líneas, esta acción crea
    los registros de CompraProducto para cada línea aprobada.
    
    Cada CompraProducto:
    - Queda vinculado a la línea de cotización
    - Tiene estado 'pendiente_llegada'
    - Hereda el producto, proveedor, cantidad y costo de la línea
    - Se vincula a la misma orden de servicio
    
    Esto integra el flujo de cotizaciones con el flujo existente de compras.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if request.method == 'POST':
        if not solicitud.puede_generar_compras():
            messages.error(
                request,
                'No se pueden generar compras. Verifica que haya líneas '
                'aprobadas sin compra generada.'
            )
            return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
        
        compras = solicitud.generar_compras(usuario=request.user)
        
        if compras:
            messages.success(
                request,
                f'Se generaron {len(compras)} compra(s) exitosamente. '
                'Puedes verlas en la lista de compras.'
            )
        else:
            messages.error(request, 'No se pudieron generar las compras.')
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
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
            'almacen:gestionar_imagenes_linea',
            solicitud_pk=solicitud_pk,
            linea_pk=linea_pk
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
        'almacen:gestionar_imagenes_linea',
        solicitud_pk=solicitud_pk,
        linea_pk=linea_pk
    )


@login_required
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


