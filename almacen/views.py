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
    MovimientoAlmacen,
    SolicitudBaja,
    Auditoria,
    DiferenciaAuditoria,
    UnidadInventario,
)
from .forms import (
    ProveedorForm,
    CategoriaAlmacenForm,
    ProductoAlmacenForm,
    CompraProductoForm,
    MovimientoAlmacenForm,
    SolicitudBajaForm,
    ProcesarSolicitudForm,
    AuditoriaForm,
    DiferenciaAuditoriaForm,
    BusquedaProductoForm,
    EntradaRapidaForm,
    UnidadInventarioForm,
    UnidadInventarioFiltroForm,
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
    - Historial de cambios (si implementado)
    
    También permite acciones rápidas como:
    - Cambiar estado/disponibilidad
    - Asignar a una orden de servicio
    - Marcar como defectuosa
    """
    
    unidad = get_object_or_404(
        UnidadInventario.objects.select_related(
            'producto',
            'producto__categoria',
            'producto__proveedor_principal',
            'compra',
            'orden_servicio_origen',
            'orden_servicio_destino',
        ),
        pk=pk
    )
    
    context = {
        'unidad': unidad,
        'titulo': f'Unidad: {unidad.codigo_interno}',
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
    - Lista paginada de todas las unidades
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
    
    # Paginación
    paginator = Paginator(unidades, 20)
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

