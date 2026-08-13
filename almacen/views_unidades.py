"""
Unidades de inventario individuales + APIs relacionadas.

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
Extraído de views.py (Fase 2 de modularización Almacén).
Aquí vive el seguimiento de cada pieza física (UnidadInventario),
no el producto consolidado del catálogo.

urls.py sigue usando views.lista_unidades, views.api_buscar_crear_orden_cliente,
etc. porque views.py reexporta estos nombres.

Efectos secundarios:
- CRUD de UnidadInventario y cambio de estado
- APIs JSON de unidades / técnicos
- api_buscar_crear_orden_cliente puede crear OrdenServicio en ST
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from inventario.models import Empleado

from .decorators import permission_required_with_message
from .forms import UnidadInventarioFiltroForm, UnidadInventarioForm
from .models import ProductoAlmacen, SolicitudBaja, UnidadInventario


# ============================================================================
# VISTAS: UNIDADES DE INVENTARIO
# ============================================================================

@login_required
@permission_required_with_message('almacen.view_unidadinventario')
def lista_unidades(request):
    """
    Lista de todas las unidades individuales de inventario.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista muestra todas las unidades físicas individuales registradas.
    
    Funcionalidades:
    - Filtrado por producto, marca, estado, disponibilidad, origen
    - Búsqueda por código interno, número de serie, modelo u orden del cliente
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
        # EXPLICACIÓN: el folio del cliente vive en DetalleEquipo (OneToOne
        # de la orden). Lo cargamos aquí para no hacer 1 query extra por fila.
        'orden_servicio_destino__detalle_equipo',
        'sucursal_actual',  # NUEVO: Para mostrar ubicación
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
            # EXPLICACIÓN: también buscamos el folio visible (OOW-/FL-) y el
            # número interno SIGMA (ORD-…) de la orden a la que está asignada.
            unidades = unidades.filter(
                Q(codigo_interno__icontains=buscar) |
                Q(numero_serie__icontains=buscar) |
                Q(modelo__icontains=buscar) |
                Q(producto__nombre__icontains=buscar) |
                Q(notas__icontains=buscar) |
                Q(orden_servicio_destino__detalle_equipo__orden_cliente__icontains=buscar) |
                Q(orden_servicio_destino__numero_orden_interno__icontains=buscar)
            )
    
    # ========== FILTRO POR SUCURSAL (NUEVO) ==========
    from inventario.models import Sucursal
    sucursal_filtro = request.GET.get('sucursal', '')
    
    if sucursal_filtro == 'central':
        unidades = unidades.filter(sucursal_actual__isnull=True)
    elif sucursal_filtro:
        try:
            unidades = unidades.filter(sucursal_actual_id=int(sucursal_filtro))
        except (ValueError, TypeError):
            pass
    
    # Contadores por sucursal (para pestañas)
    # IMPORTANTE: Solo contamos unidades con disponibilidad='disponible'
    # Las asignadas, vendidas o descartadas NO deben aparecer en los contadores
    from django.db.models import Count
    resumen_sucursales = []
    
    # Almacén Central (solo disponibles)
    central_count = UnidadInventario.objects.filter(
        sucursal_actual__isnull=True,
        disponibilidad='disponible'  # Solo unidades disponibles
    ).count()
    resumen_sucursales.append({
        'codigo': 'central',
        'nombre': 'Almacén Central',
        'count': central_count
    })
    
    # Sucursales (solo disponibles)
    for sucursal in Sucursal.objects.filter(activa=True):
        # Contar solo unidades disponibles en esta sucursal
        sucursal_count = UnidadInventario.objects.filter(
            sucursal_actual=sucursal,
            disponibilidad='disponible'
        ).count()
        
        resumen_sucursales.append({
            'codigo': str(sucursal.id),
            'nombre': sucursal.nombre,
            'count': sucursal_count
        })
    
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
        'resumen_sucursales': resumen_sucursales,  # NUEVO
        'sucursal_filtro': sucursal_filtro,  # NUEVO
        'titulo': 'Unidades de Inventario',
    }
    
    return render(request, 'almacen/lista_unidades.html', context)


@login_required
@permission_required_with_message('almacen.add_unidadinventario')
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
@permission_required_with_message('almacen.view_unidadinventario')
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
@permission_required_with_message('almacen.change_unidadinventario')
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
@permission_required_with_message('almacen.delete_unidadinventario')
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
@permission_required_with_message('almacen.change_unidadinventario')
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
@permission_required_with_message('almacen.view_unidadinventario')
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
        # EXPLICACIÓN: mismo join que en lista_unidades para pintar el folio
        # bajo el badge ASIGNADA/RESERVADA sin consultas N+1.
        'orden_servicio_destino__detalle_equipo',
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
@permission_required_with_message('almacen.view_unidadinventario')
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
@permission_required_with_message('almacen.view_unidadinventario')
def api_unidades_producto(request):
    """
    API para obtener las unidades disponibles de un producto (JSON).
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista se usa en el formulario de solicitud de baja.
    Cuando el usuario selecciona un producto, JavaScript llama a esta API
    para obtener las unidades específicas (con marca/modelo/serie) disponibles.
    
    ACTUALIZACIÓN (Enero 2026):
    Ahora retorna las unidades AGRUPADAS por marca/modelo/estado para
    una mejor visualización en el formulario (similar a unidades_por_producto.html)
    
    FILTRADO POR SUCURSAL (Enero 2026):
    - Empleados normales: Solo ven unidades de su sucursal
    - Agentes de almacén (is_staff): Ven todas las unidades
    
    Parámetros GET:
    - producto_id: ID del ProductoAlmacen
    
    Retorna:
    - grupos: Lista de grupos de unidades (marca/modelo/estado)
    - unidades: Lista plana de todas las unidades (para compatibilidad)
    - stock_info: Información del stock del producto
    """
    producto_id = request.GET.get('producto_id')
    
    if not producto_id:
        return JsonResponse({
            'success': False,
            'error': 'Se requiere producto_id',
            'unidades': [],
            'grupos': [],
            'stock_info': ''
        })
    
    try:
        # ========== OBTENER EMPLEADO Y VERIFICAR PERMISOS (NUEVO - Enero 2026) ==========
        try:
            empleado = Empleado.objects.get(user=request.user)
        except Empleado.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'No tienes un perfil de empleado asociado',
                'unidades': [],
                'grupos': [],
                'stock_info': ''
            })
        
        es_agente_almacen = request.user.is_staff
        
        producto = ProductoAlmacen.objects.get(pk=producto_id)
        
        # Obtener unidades disponibles (con sucursal_actual para filtrado)
        unidades = UnidadInventario.objects.filter(
            producto_id=producto_id,
            disponibilidad='disponible'
        ).select_related('sucursal_actual')
        
        # ========== FILTRADO POR SUCURSAL DEL EMPLEADO (NUEVO - Enero 2026) ==========
        # Si NO es agente de almacén Y tiene sucursal asignada, filtrar por su sucursal
        if not es_agente_almacen and empleado.sucursal:
            unidades = unidades.filter(sucursal_actual=empleado.sucursal)
        
        # Ordenar después del filtrado
        unidades = unidades.order_by('marca', 'modelo', 'estado', 'fecha_registro')
        
        # Construir lista plana de unidades (para compatibilidad)
        unidades_data = []
        for u in unidades:
            # ========== DETECTAR SOLICITUDES PENDIENTES (NUEVO - Enero 2026) ==========
            # Verificar si esta unidad tiene una solicitud pendiente
            solicitud_pendiente = None
            tiene_solicitud_pendiente = False
            
            # Buscar en solicitudes pendientes que tienen esta unidad seleccionada
            solicitudes_pendientes = SolicitudBaja.objects.filter(
                unidades_seleccionadas=u,
                estado='pendiente'
            ).select_related('solicitante', 'orden_servicio').first()
            
            if solicitudes_pendientes:
                tiene_solicitud_pendiente = True
                solicitud_pendiente = {
                    'id': solicitudes_pendientes.pk,
                    'solicitante': solicitudes_pendientes.solicitante.nombre_completo if solicitudes_pendientes.solicitante else 'Desconocido',
                    'fecha': solicitudes_pendientes.fecha_solicitud.strftime('%d/%m/%Y %H:%M'),
                    'tipo': solicitudes_pendientes.get_tipo_solicitud_display(),
                    'cantidad': solicitudes_pendientes.cantidad,
                }
            
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
                'costo_unitario': float(u.costo_unitario or 0),
                'tiene_solicitud_pendiente': tiene_solicitud_pendiente,  # NUEVO
                'solicitud_pendiente': solicitud_pendiente,  # NUEVO
                # Información de sucursal (Enero 2026)
                'sucursal_actual': {
                    'codigo': u.sucursal_actual.codigo,
                    'nombre': u.sucursal_actual.nombre,
                } if u.sucursal_actual else None,
            })
        
        # ========== AGRUPACIÓN DE UNIDADES ==========
        # Similar a unidades_por_producto view
        from itertools import groupby
        
        grupos_data = []
        for key, group in groupby(unidades, key=lambda u: (u.marca or 'Sin marca', u.modelo or 'Sin modelo', u.estado)):
            unidades_grupo = list(group)
            marca, modelo, estado = key
            
            # Construir lista de unidades del grupo
            unidades_grupo_data = []
            for u in unidades_grupo:
                # Detectar solicitudes pendientes
                solicitudes_pendientes = SolicitudBaja.objects.filter(
                    unidades_seleccionadas=u,
                    estado='pendiente'
                ).select_related('solicitante').first()
                
                tiene_solicitud_pendiente = False
                solicitud_pendiente = None
                
                if solicitudes_pendientes:
                    tiene_solicitud_pendiente = True
                    solicitud_pendiente = {
                        'id': solicitudes_pendientes.pk,
                        'solicitante': solicitudes_pendientes.solicitante.nombre_completo if solicitudes_pendientes.solicitante else 'Desconocido',
                        'fecha': solicitudes_pendientes.fecha_solicitud.strftime('%d/%m/%Y %H:%M'),
                        'tipo': solicitudes_pendientes.get_tipo_solicitud_display(),
                    }
                
                unidades_grupo_data.append({
                    'id': u.pk,
                    'codigo_interno': u.codigo_interno or '',
                    'numero_serie': u.numero_serie or '',
                    'costo_unitario': float(u.costo_unitario or 0),
                    'fecha_registro': u.fecha_registro.strftime('%d/%m/%Y'),
                    'origen': u.origen,
                    'origen_display': u.get_origen_display(),
                    'tiene_solicitud_pendiente': tiene_solicitud_pendiente,  # NUEVO
                    'solicitud_pendiente': solicitud_pendiente,  # NUEVO
                    # Información de sucursal (Enero 2026)
                    'sucursal_actual': {
                        'codigo': u.sucursal_actual.codigo,
                        'nombre': u.sucursal_actual.nombre,
                    } if u.sucursal_actual else None,
                })
            
            grupos_data.append({
                'marca': marca,
                'modelo': modelo,
                'estado': estado,
                'estado_display': dict(unidades_grupo[0]._meta.get_field('estado').choices).get(estado, estado),
                'cantidad': len(unidades_grupo),
                'unidades': unidades_grupo_data,
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
            'unidades': unidades_data,  # Lista plana (compatibilidad)
            'grupos': grupos_data,  # Grupos (nuevo)
            'total_unidades': len(unidades_data),
            'total_grupos': len(grupos_data),
        })
        
    except ProductoAlmacen.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Producto no encontrado',
            'unidades': [],
            'grupos': [],
            'stock_info': ''
        })


@login_required
@permission_required_with_message('almacen.view_solicitudbaja')
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
    - rol=Empleado.ROL_TECNICO: Solo rol técnico del sistema (no texto de cargo)
    
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
        # Filtrar técnicos activos por rol del sistema
        tecnicos = Empleado.objects.filter(
            activo=True,
            rol=Empleado.ROL_TECNICO,
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
@permission_required_with_message('almacen.add_solicitudbaja')
def api_buscar_crear_orden_cliente(request):
    """
    API para buscar una orden de servicio por orden_cliente o crearla si no existe.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Usada en el formulario de Nueva solicitud del almacén. Permite:
    1. Buscar órdenes existentes por número de orden del cliente (coincidencia exacta)
    2. Crear automáticamente una orden si no existe al enviar el formulario
    
    El campo orden_cliente vive en DetalleEquipo; la búsqueda cruza esa relación.
    
    VALIDACIÓN DE FORMATO Y PREFIJO:
    - Formato base: debe empezar con 'OOW-' o 'FL-'
    - Con tipo_solicitud en GET/POST:
      - servicio_tecnico  → solo acepta OOW-
      - venta_mostrador   → solo acepta FL-
    
    MÉTODOS HTTP:
    - GET: Buscar orden existente
    - POST: Crear nueva orden si no existe
    
    PARÁMETROS GET:
    - orden_cliente (str): Número a buscar (ej. OOW-12345)
    - tipo_solicitud (str, opcional): 'servicio_tecnico' o 'venta_mostrador' para validar prefijo
    
    PARÁMETROS POST (JSON):
    - orden_cliente (str): Número de orden del cliente
    - tipo_solicitud (str, opcional): Valida prefijo OOW/FL según tipo
    - sucursal_id (int): Sucursal donde se registra la orden nueva
    - tecnico_id (int): Técnico asignado (obligatorio para servicio técnico)
    
    RETORNA:
    {
        "success": true/false,
        "found": true/false,
        "created": true/false,
        "orden_id": int,
        "orden_cliente": str,
        "numero_orden_interno": str,
        "estado": str,
        "sucursal": str,
        "error": str
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
    
    def validar_prefijo_por_tipo(orden_cliente: str, tipo_solicitud: str) -> tuple[bool, str]:
        """
        Valida que el prefijo de la orden coincida con el tipo de solicitud.
        
        - servicio_tecnico → solo OOW- (diagnóstico)
        - venta_mostrador → solo FL- (venta mostrador)
        """
        if not tipo_solicitud or not orden_cliente:
            return True, ''
        
        orden_cliente = orden_cliente.strip().upper()
        
        if tipo_solicitud == 'servicio_tecnico' and not orden_cliente.startswith('OOW-'):
            return False, 'Para Servicio Técnico el número de orden debe empezar con "OOW-"'
        if tipo_solicitud == 'venta_mostrador' and not orden_cliente.startswith('FL-'):
            return False, 'Para Venta Mostrador el número de orden debe empezar con "FL-"'
        
        return True, ''
    
    if request.method == 'GET':
        # ========== MODO BÚSQUEDA ==========
        orden_cliente = request.GET.get('orden_cliente', '').strip().upper()
        tipo_solicitud = request.GET.get('tipo_solicitud', '').strip()
        
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
        
        # Validar prefijo según tipo de solicitud (si se envía)
        prefijo_valido, error_prefijo = validar_prefijo_por_tipo(orden_cliente, tipo_solicitud)
        if not prefijo_valido:
            return JsonResponse({
                'success': False,
                'error': error_prefijo,
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
            
            # Validar prefijo según tipo de solicitud
            prefijo_valido, error_prefijo = validar_prefijo_por_tipo(orden_cliente, tipo_solicitud)
            if not prefijo_valido:
                return JsonResponse({
                    'success': False,
                    'error': error_prefijo,
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

