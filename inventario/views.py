from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Sum, Count, F
from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Producto, Movimiento, Sucursal, Empleado
from .forms import ProductoForm, MovimientoForm, SucursalForm, MovimientoRapidoForm, EmpleadoForm
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

# ===== DASHBOARD PRINCIPAL =====
def dashboard(request):
    """
    Vista del dashboard principal con métricas e información resumida
    """
    # Estadísticas generales
    total_productos = Producto.objects.count()
    productos_stock_bajo = Producto.objects.filter(cantidad__lte=F('stock_minimo')).count()
    valor_total_inventario = Producto.objects.aggregate(
        total=Sum(F('cantidad') * F('costo_unitario'))
    )['total'] or 0
    
    # Productos con stock bajo (alertas)
    alertas_stock = Producto.objects.filter(cantidad__lte=F('stock_minimo'))[:10]
    
    # Movimientos recientes
    movimientos_recientes = Movimiento.objects.select_related('producto', 'sucursal_destino')[:10]
    
    # Productos más utilizados (últimos 30 días)
    fecha_limite = timezone.now() - timedelta(days=30)
    productos_mas_usados = (
        Movimiento.objects
        .filter(fecha_movimiento__gte=fecha_limite, tipo='salida')
        .values('producto__nombre')
        .annotate(total_usado=Sum('cantidad'))
        .order_by('-total_usado')[:5]
    )
    
    # Movimientos por categoría (últimos 30 días)
    movimientos_por_categoria = (
        Movimiento.objects
        .filter(fecha_movimiento__gte=fecha_limite)
        .values('producto__categoria')
        .annotate(total_movimientos=Count('id'))
        .order_by('-total_movimientos')
    )
    
    context = {
        'total_productos': total_productos,
        'productos_stock_bajo': productos_stock_bajo,
        'valor_total_inventario': valor_total_inventario,
        'alertas_stock': alertas_stock,
        'movimientos_recientes': movimientos_recientes,
        'productos_mas_usados': productos_mas_usados,
        'movimientos_por_categoria': movimientos_por_categoria,
    }
    
    return render(request, 'inventario/dashboard.html', context)

# ===== GESTIÓN DE PRODUCTOS =====
def lista_productos(request):
    """
    Lista de productos con filtros y búsqueda
    """
    productos = Producto.objects.all()
    
    # Filtros de búsqueda
    busqueda = request.GET.get('busqueda', '')
    categoria = request.GET.get('categoria', '')
    stock_bajo = request.GET.get('stock_bajo', '')
    
    # Aplicar filtros
    if busqueda:
        productos = productos.filter(
            Q(nombre__icontains=busqueda) |
            Q(codigo_qr__icontains=busqueda) |
            Q(descripcion__icontains=busqueda)
        )
    
    if categoria:
        productos = productos.filter(categoria=categoria)
    
    # Corregir filtro de stock bajo - verificar que sea exactamente 'true'
    if stock_bajo == 'true':
        productos = productos.filter(cantidad__lte=F('stock_minimo'))
    
    # Obtener opciones para filtros
    categorias = Producto.CATEGORIA_CHOICES
    
    # Calcular estadísticas de resumen correctamente en la vista
    total_productos = productos.count()
    productos_stock_bajo = productos.filter(cantidad__lte=F('stock_minimo')).count()
    
    # Calcular unidades totales
    unidades_totales = productos.aggregate(
        total=Sum('cantidad')
    )['total'] or 0
    
    # Calcular valor total del inventario
    valor_total = productos.aggregate(
        total=Sum(F('cantidad') * F('costo_unitario'))
    )['total'] or 0
    
    context = {
        'productos': productos,
        'categorias': categorias,
        'busqueda': busqueda,
        'categoria_seleccionada': categoria,
        'stock_bajo_seleccionado': stock_bajo == 'true',  # Pasar como booleano
        # Estadísticas calculadas en la vista
        'total_productos': total_productos,
        'productos_stock_bajo': productos_stock_bajo,
        'unidades_totales': unidades_totales,
        'valor_total': valor_total,
    }
    
    return render(request, 'inventario/lista_productos.html', context)

def detalle_producto(request, producto_id):
    """
    Vista detallada de un producto con su historial de movimientos
    """
    producto = get_object_or_404(Producto, id=producto_id)
    movimientos = Movimiento.objects.filter(producto=producto).select_related(
        'empleado_destinatario', 'usuario_registro_empleado', 'sucursal_destino'
    ).order_by('-fecha_movimiento')[:20]
    
    context = {
        'producto': producto,
        'movimientos': movimientos,
        'qr_image': producto.generar_qr_image(),
    }
    
    return render(request, 'inventario/detalle_producto.html', context)

def crear_producto(request):
    """
    Crear un nuevo producto
    """
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            producto = form.save()
            messages.success(request, f'Producto "{producto.nombre}" creado exitosamente con código QR: {producto.codigo_qr}')
            return redirect('detalle_producto', producto_id=producto.id)
    else:
        form = ProductoForm()
    
    return render(request, 'inventario/form_producto.html', {
        'form': form,
        'titulo': 'Crear Producto',
        'boton_texto': 'Crear Producto'
    })

def editar_producto(request, producto_id):
    """
    Editar un producto existente
    """
    producto = get_object_or_404(Producto, id=producto_id)
    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, f'Producto "{producto.nombre}" actualizado exitosamente.')
            return redirect('detalle_producto', producto_id=producto.id)
    else:
        form = ProductoForm(instance=producto)
    
    return render(request, 'inventario/form_producto.html', {
        'form': form,
        'producto': producto,
        'titulo': f'Editar: {producto.nombre}',
        'boton_texto': 'Guardar Cambios'
    })

def eliminar_producto(request, producto_id):
    """
    Eliminar un producto (con confirmación)
    """
    producto = get_object_or_404(Producto, id=producto_id)
    
    if request.method == 'POST':
        nombre = producto.nombre
        producto.delete()
        messages.success(request, f'Producto "{nombre}" eliminado exitosamente.')
        return redirect('lista_productos')
    
    return render(request, 'inventario/confirmar_eliminacion.html', {
        'producto': producto,
        'movimientos_count': Movimiento.objects.filter(producto=producto).count()
    })

# ===== GESTIÓN DE MOVIMIENTOS =====
def lista_movimientos(request):
    """
    Lista de todos los movimientos con filtros
    """
    movimientos = Movimiento.objects.select_related('producto', 'sucursal_destino').order_by('-fecha_movimiento')
    
    # Filtros
    tipo = request.GET.get('tipo')
    producto_id = request.GET.get('producto')
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if tipo:
        movimientos = movimientos.filter(tipo=tipo)
    
    if producto_id:
        movimientos = movimientos.filter(producto_id=producto_id)
    
    if fecha_desde:
        movimientos = movimientos.filter(fecha_movimiento__gte=fecha_desde)
    
    if fecha_hasta:
        movimientos = movimientos.filter(fecha_movimiento__lte=fecha_hasta)
    
    # Paginación (opcional: mostrar solo los primeros 50)
    movimientos_limitados = movimientos[:50]
    
    # Calcular estadísticas de resumen correctamente en la vista
    total_movimientos = movimientos.count()
    entradas_count = movimientos.filter(tipo='entrada').count()
    salidas_count = movimientos.filter(tipo='salida').count()
    ajustes_count = movimientos.filter(tipo='ajuste').count()
    devoluciones_count = movimientos.filter(tipo='devolucion').count()
    
    context = {
        'movimientos': movimientos_limitados,
        'tipos_movimiento': Movimiento.TIPO_CHOICES,
        'productos': Producto.objects.all()[:20],  # Primeros 20 para el selector
        # Estadísticas calculadas en la vista
        'total_movimientos': total_movimientos,
        'entradas_count': entradas_count,
        'salidas_count': salidas_count,
        'ajustes_count': ajustes_count,
        'devoluciones_count': devoluciones_count,
    }
    
    return render(request, 'inventario/lista_movimientos.html', context)

def crear_movimiento(request):
    """
    Crear un nuevo movimiento de inventario
    """
    if request.method == 'POST':
        form = MovimientoForm(request.POST)
        if form.is_valid():
            movimiento = form.save()
            messages.success(request, f'Movimiento registrado exitosamente. Nuevo stock: {movimiento.stock_posterior}')
            return redirect('lista_movimientos')
    else:
        form = MovimientoForm()
    
    return render(request, 'inventario/form_movimiento.html', {
        'form': form,
        'titulo': 'Registrar Movimiento',
        'boton_texto': 'Registrar Movimiento'
    })

def movimiento_rapido(request):
    """
    Formulario rápido para movimientos usando código QR
    """
    if request.method == 'POST':
        form = MovimientoRapidoForm(request.POST)
        if form.is_valid():
            movimiento = form.save()
            producto = movimiento.producto
            messages.success(request, f'Movimiento registrado: {producto.nombre}. Nuevo stock: {movimiento.stock_posterior}')
            return redirect('movimiento_rapido')
    else:
        form = MovimientoRapidoForm()
    
    return render(request, 'inventario/movimiento_rapido.html', {
        'form': form,
        'titulo': 'Movimiento Rápido (Scanner QR)'
    })

# ===== GESTIÓN DE SUCURSALES =====
def lista_sucursales(request):
    """
    Lista de todas las sucursales
    """
    sucursales = Sucursal.objects.all()
    return render(request, 'inventario/lista_sucursales.html', {'sucursales': sucursales})

def crear_sucursal(request):
    """
    Crear una nueva sucursal
    """
    if request.method == 'POST':
        form = SucursalForm(request.POST)
        if form.is_valid():
            sucursal = form.save()
            messages.success(request, f'Sucursal "{sucursal.nombre}" creada exitosamente.')
            return redirect('lista_sucursales')
    else:
        form = SucursalForm()
    
    return render(request, 'inventario/form_sucursal.html', {
        'form': form,
        'titulo': 'Crear Sucursal',
        'boton_texto': 'Crear Sucursal'
    })

def editar_sucursal(request, sucursal_id):
    """
    Editar una sucursal existente
    """
    sucursal = get_object_or_404(Sucursal, id=sucursal_id)
    if request.method == 'POST':
        form = SucursalForm(request.POST, instance=sucursal)
        if form.is_valid():
            form.save()
            messages.success(request, f'Sucursal "{sucursal.nombre}" actualizada exitosamente.')
            return redirect('lista_sucursales')
    else:
        form = SucursalForm(instance=sucursal)
    
    return render(request, 'inventario/form_sucursal.html', {
        'form': form,
        'sucursal': sucursal,
        'titulo': f'Editar: {sucursal.nombre}',
        'boton_texto': 'Guardar Cambios'
    })

def eliminar_sucursal(request, sucursal_id):
    """
    Eliminar una sucursal (con validaciones de seguridad)
    """
    sucursal = get_object_or_404(Sucursal, id=sucursal_id)
    
    if request.method == 'POST':
        # Verificar si la sucursal tiene movimientos asociados
        movimientos_asociados = Movimiento.objects.filter(sucursal_destino=sucursal).count()
        
        if movimientos_asociados > 0:
            messages.error(
                request, 
                f'No se puede eliminar la sucursal "{sucursal.nombre}" porque tiene {movimientos_asociados} movimiento(s) asociado(s). '
                'Primero debe eliminar o reasignar estos movimientos.'
            )
        else:
            nombre_sucursal = sucursal.nombre
            try:
                sucursal.delete()
                messages.success(request, f'Sucursal "{nombre_sucursal}" eliminada exitosamente.')
            except Exception as e:
                messages.error(request, f'Error al eliminar la sucursal: {str(e)}')
        
        return redirect('lista_sucursales')
    
    # Si es GET, mostrar confirmación con información básica de la sucursal
    context = {
        'sucursal': sucursal,
        'movimientos_asociados': Movimiento.objects.filter(sucursal_destino=sucursal).count()
    }
    return render(request, 'inventario/confirmar_eliminar_sucursal.html', context)

# ===== FUNCIONES AJAX/API =====
def buscar_producto_qr(request):
    """
    API endpoint para buscar producto por código QR (AJAX)
    """
    codigo_qr = request.GET.get('codigo_qr')
    
    if not codigo_qr:
        return JsonResponse({'error': 'Código QR requerido'}, status=400)
    
    try:
        producto = Producto.objects.get(codigo_qr=codigo_qr)
        data = {
            'id': producto.id,
            'nombre': producto.nombre,
            'codigo_qr': producto.codigo_qr,
            'cantidad_actual': producto.cantidad,
            'categoria': producto.get_categoria_display(),
            'ubicacion': producto.ubicacion,
        }
        return JsonResponse(data)
    except Producto.DoesNotExist:
        return JsonResponse({'error': 'Producto no encontrado'}, status=404)

def generar_qr_producto(request, producto_id):
    """
    Generar y mostrar código QR de un producto
    """
    producto = get_object_or_404(Producto, id=producto_id)
    
    # Generar QR como imagen
    import qrcode
    from io import BytesIO
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(producto.codigo_qr)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Crear respuesta HTTP con la imagen
    response = HttpResponse(content_type="image/png")
    img.save(response, "PNG")
    
    return response


# ===== GESTIÓN DE EMPLEADOS =====
def lista_empleados(request):
    """
    Lista de empleados con filtros
    """
    empleados = Empleado.objects.all()
    
    # Filtros de búsqueda
    busqueda = request.GET.get('busqueda', '')
    area = request.GET.get('area', '')
    activo = request.GET.get('activo', '')
    
    if busqueda:
        empleados = empleados.filter(
            Q(nombre_completo__icontains=busqueda) |
            Q(cargo__icontains=busqueda) |
            Q(area__icontains=busqueda)
        )
    
    if area:
        empleados = empleados.filter(area__icontains=area)
    
    if activo == 'true':
        empleados = empleados.filter(activo=True)
    elif activo == 'false':
        empleados = empleados.filter(activo=False)
    
    # Obtener áreas únicas para filtro
    areas_disponibles = Empleado.objects.values_list('area', flat=True).distinct().order_by('area')
    
    context = {
        'empleados': empleados,
        'busqueda': busqueda,
        'area_seleccionada': area,
        'activo_seleccionado': activo,
        'areas_disponibles': areas_disponibles,
    }
    
    return render(request, 'inventario/lista_empleados.html', context)

def crear_empleado(request):
    """
    Crear un nuevo empleado
    """
    if request.method == 'POST':
        form = EmpleadoForm(request.POST)
        if form.is_valid():
            empleado = form.save()
            messages.success(request, f'Empleado {empleado.nombre_completo} creado exitosamente.')
            return redirect('lista_empleados')
    else:
        form = EmpleadoForm()
    
    return render(request, 'inventario/form_empleado.html', {
        'form': form,
        'titulo': 'Agregar Empleado',
        'boton_texto': 'Crear Empleado'
    })

def editar_empleado(request, empleado_id):
    """
    Editar un empleado existente
    """
    empleado = get_object_or_404(Empleado, id=empleado_id)
    
    if request.method == 'POST':
        form = EmpleadoForm(request.POST, instance=empleado)
        if form.is_valid():
            empleado = form.save()
            messages.success(request, f'Empleado {empleado.nombre_completo} actualizado exitosamente.')
            return redirect('lista_empleados')
    else:
        form = EmpleadoForm(instance=empleado)
    
    return render(request, 'inventario/form_empleado.html', {
        'form': form,
        'titulo': f'Editar Empleado: {empleado.nombre_completo}',
        'boton_texto': 'Actualizar Empleado',
        'empleado': empleado
    })

def eliminar_empleado(request, empleado_id):
    """
    Marcar empleado como inactivo (soft delete)
    """
    empleado = get_object_or_404(Empleado, id=empleado_id)
    
    if request.method == 'POST':
        empleado.activo = False
        empleado.save()
        messages.success(request, f'Empleado {empleado.nombre_completo} marcado como inactivo.')
        return redirect('lista_empleados')
    
    return render(request, 'inventario/confirmar_eliminacion.html', {
        'objeto': empleado,
        'tipo': 'empleado',
        'url_cancelar': 'lista_empleados'
    })

# ===== REPORTES =====
def descargar_reporte_excel(request):
    """
    Genera y descarga un reporte completo en Excel con información del inventario
    """
    # Crear el workbook (archivo Excel)
    wb = openpyxl.Workbook()
    
    # === HOJA 1: RESUMEN GENERAL ===
    ws_resumen = wb.active
    ws_resumen.title = "Resumen General"
    
    # Estilos para encabezados
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    
    # Título del reporte
    ws_resumen['A1'] = 'REPORTE DE INVENTARIO'
    ws_resumen['A1'].font = Font(bold=True, size=16)
    ws_resumen['A2'] = f'Generado el: {timezone.now().strftime("%d/%m/%Y %H:%M")}'
    
    # Estadísticas generales
    ws_resumen['A4'] = 'ESTADÍSTICAS GENERALES'
    ws_resumen['A4'].font = header_font
    ws_resumen['A4'].fill = header_fill
    
    # Calcular estadísticas
    total_productos = Producto.objects.count()
    productos_stock_bajo = Producto.objects.filter(cantidad__lte=F('stock_minimo')).count()
    valor_total_inventario = Producto.objects.aggregate(
        total=Sum(F('cantidad') * F('costo_unitario'))
    )['total'] or 0
    total_unidades = Producto.objects.aggregate(total=Sum('cantidad'))['total'] or 0
    
    # Escribir estadísticas
    estadisticas = [
        ['Total de Productos:', total_productos],
        ['Productos con Stock Bajo:', productos_stock_bajo],
        ['Total de Unidades en Stock:', total_unidades],
        ['Valor Total del Inventario:', f'${valor_total_inventario:,.2f}']
    ]
    
    for i, (descripcion, valor) in enumerate(estadisticas, start=5):
        ws_resumen[f'A{i}'] = descripcion
        ws_resumen[f'B{i}'] = valor
        ws_resumen[f'A{i}'].font = Font(bold=True)
    
    # === HOJA 2: PRODUCTOS CON STOCK BAJO ===
    ws_stock_bajo = wb.create_sheet("Stock Bajo")
    
    # Encabezados
    headers_stock = ['Código QR', 'Nombre', 'Categoría', 'Stock Actual', 'Stock Mínimo', 'Diferencia', 'Costo Unitario', 'Valor en Stock']
    for col, header in enumerate(headers_stock, start=1):
        cell = ws_stock_bajo.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
    
    # Obtener productos con stock bajo
    productos_stock_bajo_list = Producto.objects.filter(cantidad__lte=F('stock_minimo')).order_by('cantidad')
    
    for row, producto in enumerate(productos_stock_bajo_list, start=2):
        diferencia = producto.stock_minimo - producto.cantidad
        valor_stock = producto.cantidad * producto.costo_unitario
        
        datos = [
            producto.codigo_qr,
            producto.nombre,
            producto.get_categoria_display(),
            producto.cantidad,
            producto.stock_minimo,
            diferencia,
            f'${producto.costo_unitario:.2f}',
            f'${valor_stock:.2f}'
        ]
        
        for col, dato in enumerate(datos, start=1):
            ws_stock_bajo.cell(row=row, column=col, value=dato)
    
    # === HOJA 3: PRODUCTOS MÁS UTILIZADOS ===
    ws_mas_usados = wb.create_sheet("Productos Más Utilizados")
    
    # Encabezados
    headers_usados = ['Producto', 'Categoría', 'Total Utilizado (30 días)', 'Stock Actual', 'Promedio Diario']
    for col, header in enumerate(headers_usados, start=1):
        cell = ws_mas_usados.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
    
    # Obtener productos más utilizados (últimos 30 días)
    fecha_limite = timezone.now() - timedelta(days=30)
    productos_mas_usados = (
        Movimiento.objects
        .filter(fecha_movimiento__gte=fecha_limite, tipo='salida')
        .values('producto__nombre', 'producto__categoria', 'producto__cantidad')
        .annotate(total_usado=Sum('cantidad'))
        .order_by('-total_usado')[:20]  # Top 20
    )
    
    for row, item in enumerate(productos_mas_usados, start=2):
        promedio_diario = item['total_usado'] / 30
        
        datos = [
            item['producto__nombre'],
            dict(Producto.CATEGORIA_CHOICES).get(item['producto__categoria'], item['producto__categoria']),
            item['total_usado'],
            item['producto__cantidad'],
            f'{promedio_diario:.1f}'
        ]
        
        for col, dato in enumerate(datos, start=1):
            ws_mas_usados.cell(row=row, column=col, value=dato)
    
    # === HOJA 4: TODOS LOS PRODUCTOS ===
    ws_todos = wb.create_sheet("Inventario Completo")
    
    # Encabezados
    headers_todos = ['Código QR', 'Nombre', 'Descripción', 'Categoría', 'Stock Actual', 'Stock Mínimo', 'Estado Calidad', 'Costo Unitario', 'Valor Total', 'Fecha Ingreso']
    for col, header in enumerate(headers_todos, start=1):
        cell = ws_todos.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
    
    # Obtener todos los productos
    todos_productos = Producto.objects.all().order_by('nombre')
    
    for row, producto in enumerate(todos_productos, start=2):
        valor_total = producto.cantidad * producto.costo_unitario
        
        datos = [
            producto.codigo_qr,
            producto.nombre,
            producto.descripcion[:50] + '...' if len(producto.descripcion) > 50 else producto.descripcion,
            producto.get_categoria_display(),
            producto.cantidad,
            producto.stock_minimo,
            producto.get_estado_calidad_display(),
            f'${producto.costo_unitario:.2f}',
            f'${valor_total:.2f}',
            producto.fecha_ingreso.strftime('%d/%m/%Y')
        ]
        
        for col, dato in enumerate(datos, start=1):
            ws_todos.cell(row=row, column=col, value=dato)
    
    # === HOJA 5: MOVIMIENTOS RECIENTES ===
    ws_movimientos = wb.create_sheet("Movimientos Recientes")
    
    # Encabezados
    headers_mov = ['Fecha', 'Tipo', 'Producto', 'Cantidad', 'Destinatario/Área', 'Usuario Registro', 'Observaciones']
    for col, header in enumerate(headers_mov, start=1):
        cell = ws_movimientos.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
    
    # Obtener movimientos recientes (últimos 100)
    movimientos_recientes = Movimiento.objects.select_related('producto', 'empleado_destinatario').order_by('-fecha_movimiento')[:100]
    
    for row, mov in enumerate(movimientos_recientes, start=2):
        destinatario = ""
        if mov.empleado_destinatario:
            destinatario = f"{mov.empleado_destinatario.nombre_completo}"
            if mov.empleado_destinatario.area:
                destinatario += f" ({mov.empleado_destinatario.area})"
        elif mov.destinatario:
            destinatario = mov.destinatario
        
        usuario_registro = ""
        if mov.usuario_registro_empleado:
            usuario_registro = mov.usuario_registro_empleado.nombre_completo
        elif mov.usuario_registro:
            usuario_registro = mov.usuario_registro
        
        datos = [
            mov.fecha_movimiento.strftime('%d/%m/%Y %H:%M'),
            mov.get_tipo_display(),
            mov.producto.nombre,
            mov.cantidad,
            destinatario,
            usuario_registro,
            mov.observaciones[:100] + '...' if len(mov.observaciones) > 100 else mov.observaciones
        ]
        
        for col, dato in enumerate(datos, start=1):
            ws_movimientos.cell(row=row, column=col, value=dato)
    
    # Ajustar ancho de columnas para todas las hojas
    for ws in wb.worksheets:
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)  # Máximo 50 caracteres
            ws.column_dimensions[column_letter].width = adjusted_width
    
    # Crear la respuesta HTTP con el archivo Excel
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="Reporte_Inventario_{timezone.now().strftime("%Y%m%d_%H%M")}.xlsx"'
    
    # Guardar el workbook en la respuesta
    wb.save(response)
    
    return response
