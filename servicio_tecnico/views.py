"""
Vistas para la aplicación de Servicio Técnico

EXPLICACIÓN PARA PRINCIPIANTES:
- Las vistas son funciones que reciben una petición HTTP y devuelven una respuesta
- @login_required: Decorador que requiere que el usuario esté autenticado
- render(): Función que toma un template HTML y lo renderiza con datos (context)
- redirect(): Función que redirige al usuario a otra URL
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from django.http import JsonResponse
from django.utils.safestring import mark_safe
from PIL import Image
import os
import json
from .models import OrdenServicio, DetalleEquipo, HistorialOrden, ImagenOrden
from inventario.models import Empleado
from .forms import (
    NuevaOrdenForm,
    ConfiguracionAdicionalForm,
    ReingresoRHITSOForm,
    CambioEstadoForm,
    AsignarResponsablesForm,
    ComentarioForm,
    SubirImagenesForm,
)


@login_required
def inicio(request):
    """
    Vista principal de Servicio Técnico
    Muestra un dashboard con estadísticas básicas
    """
    # Estadísticas generales
    total_ordenes = OrdenServicio.objects.count()
    ordenes_activas = OrdenServicio.objects.exclude(estado__in=['entregado', 'cancelado']).count()
    ordenes_retrasadas = OrdenServicio.objects.filter(
        estado__in=['diagnostico', 'reparacion', 'esperando_piezas']
    ).count()
    
    # Órdenes por estado
    ordenes_por_estado = OrdenServicio.objects.values('estado').annotate(
        total=Count('numero_orden_interno')
    ).order_by('-total')
    
    # Órdenes recientes (últimas 10)
    ordenes_recientes = OrdenServicio.objects.select_related(
        'sucursal',
        'tecnico_asignado_actual',
        'detalle_equipo'
    ).order_by('-fecha_ingreso')[:10]
    
    context = {
        'total_ordenes': total_ordenes,
        'ordenes_activas': ordenes_activas,
        'ordenes_retrasadas': ordenes_retrasadas,
        'ordenes_por_estado': ordenes_por_estado,
        'ordenes_recientes': ordenes_recientes,
    }
    
    return render(request, 'servicio_tecnico/inicio.html', context)


@login_required
def crear_orden(request):
    """
    Vista para crear una nueva orden de servicio técnico.
    
    EXPLICACIÓN DEL FLUJO:
    1. Si la petición es GET (usuario accede al formulario):
       - Se crea un formulario vacío
       - Se renderiza el template con el formulario
    
    2. Si la petición es POST (usuario envía el formulario):
       - Se valida el formulario
       - Si es válido:
         * Se guarda la orden (esto crea OrdenServicio Y DetalleEquipo)
         * Se muestra un mensaje de éxito
         * Se redirige a la página de inicio
       - Si NO es válido:
         * Se muestra el formulario con los errores
    
    Args:
        request: Objeto HttpRequest con la petición del usuario
    
    Returns:
        HttpResponse: Renderiza el template o redirige
    """
    
    # Verificar el método HTTP
    if request.method == 'POST':
        # El usuario envió el formulario (click en "Guardar")
        # Crear instancia del formulario con los datos enviados
        form = NuevaOrdenForm(request.POST, user=request.user)
        
        # Validar el formulario (llama a clean_<campo>() y clean())
        if form.is_valid():
            try:
                # Guardar el formulario (esto crea OrdenServicio Y DetalleEquipo)
                # El método save() del formulario maneja toda la lógica
                orden = form.save()
                
                # Mensaje de éxito para el usuario
                messages.success(
                    request,
                    f'¡Orden {orden.numero_orden_interno} creada exitosamente! '
                    f'Equipo: {orden.detalle_equipo.marca} {orden.detalle_equipo.modelo}'
                )
                
                # Redirigir al inicio (o podrías redirigir al detalle de la orden)
                return redirect('servicio_tecnico:inicio')
            
            except Exception as e:
                # Si algo sale mal al guardar, mostrar error
                messages.error(
                    request,
                    f'Error al crear la orden: {str(e)}'
                )
        else:
            # El formulario tiene errores de validación
            messages.warning(
                request,
                'Por favor corrige los errores en el formulario.'
            )
    
    else:
        # GET: Usuario accede al formulario por primera vez
        # Crear un formulario vacío
        form = NuevaOrdenForm(user=request.user)
    
    # Contexto para el template
    context = {
        'form': form,
        'titulo': 'Nueva Orden de Servicio',
        'accion': 'Crear',  # Para el botón "Crear Orden"
    }
    
    return render(request, 'servicio_tecnico/form_nueva_orden.html', context)


@login_required
def lista_ordenes_activas(request):
    """
    Vista para listar órdenes activas (no entregadas ni canceladas).
    
    EXPLICACIÓN:
    Muestra todas las órdenes que están en proceso, incluyendo:
    - En espera, recepción, diagnóstico, cotización
    - Esperando piezas, en reparación, control de calidad
    - Finalizadas pero no entregadas
    
    Incluye búsqueda por número de serie y orden de cliente.
    """
    # Obtener parámetro de búsqueda
    busqueda = request.GET.get('busqueda', '').strip()
    
    # Filtrar órdenes activas (excluir entregadas y canceladas)
    ordenes = OrdenServicio.objects.exclude(
        estado__in=['entregado', 'cancelado']
    ).select_related(
        'sucursal',
        'tecnico_asignado_actual',
        'detalle_equipo'
    ).prefetch_related(
        'imagenes'  # Para contar imágenes eficientemente
    ).order_by('-fecha_ingreso')
    
    # Aplicar búsqueda si existe
    if busqueda:
        ordenes = ordenes.filter(
            Q(detalle_equipo__numero_serie__icontains=busqueda) |
            Q(detalle_equipo__orden_cliente__icontains=busqueda) |
            Q(numero_orden_interno__icontains=busqueda)
        )
    
    context = {
        'ordenes': ordenes,
        'tipo': 'activas',
        'titulo': 'Órdenes Activas',
        'total': ordenes.count(),
        'busqueda': busqueda,
    }
    
    return render(request, 'servicio_tecnico/lista_ordenes.html', context)


@login_required
def lista_ordenes_finalizadas(request):
    """
    Vista para listar órdenes finalizadas (entregadas o canceladas).
    
    EXPLICACIÓN:
    Muestra todas las órdenes que ya fueron:
    - Entregadas al cliente
    - Canceladas por algún motivo
    
    Incluye búsqueda por número de serie y orden de cliente.
    """
    # Obtener parámetro de búsqueda
    busqueda = request.GET.get('busqueda', '').strip()
    
    # Filtrar órdenes finalizadas (entregadas o canceladas)
    ordenes = OrdenServicio.objects.filter(
        estado__in=['entregado', 'cancelado']
    ).select_related(
        'sucursal',
        'tecnico_asignado_actual',
        'detalle_equipo'
    ).prefetch_related(
        'imagenes'  # Para contar imágenes eficientemente
    ).order_by('-fecha_entrega', '-fecha_actualizacion')
    
    # Aplicar búsqueda si existe
    if busqueda:
        ordenes = ordenes.filter(
            Q(detalle_equipo__numero_serie__icontains=busqueda) |
            Q(detalle_equipo__orden_cliente__icontains=busqueda) |
            Q(numero_orden_interno__icontains=busqueda)
        )
    
    context = {
        'ordenes': ordenes,
        'tipo': 'finalizadas',
        'titulo': 'Órdenes Finalizadas',
        'total': ordenes.count(),
        'busqueda': busqueda,
    }
    
    return render(request, 'servicio_tecnico/lista_ordenes.html', context)


@login_required
def cerrar_orden(request, orden_id):
    """
    Vista para cambiar el estado de una orden a 'entregado'.
    
    EXPLICACIÓN:
    Marca una orden como entregada, registrando la fecha de entrega
    y cambiando el estado a 'entregado'.
    
    Solo funciona con órdenes en estado 'finalizado'.
    """
    # Obtener la orden o mostrar error 404
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    
    # Verificar que esté en estado 'finalizado'
    if orden.estado == 'finalizado':
        # Cambiar estado a entregado
        orden.estado = 'entregado'
        orden.fecha_entrega = timezone.now()
        orden.save()
        
        messages.success(
            request,
            f'Orden {orden.numero_orden_interno} marcada como entregada.'
        )
    else:
        messages.warning(
            request,
            f'La orden debe estar en estado "Finalizado" para poder cerrarla. Estado actual: {orden.get_estado_display()}'
        )
    
    # Redirigir a la lista de órdenes activas
    return redirect('servicio_tecnico:lista_activas')


@login_required
def cerrar_todas_finalizadas(request):
    """
    Vista para cerrar todas las órdenes en estado 'finalizado'.
    
    EXPLICACIÓN:
    Marca todas las órdenes finalizadas como entregadas en un solo paso.
    Útil para cerrar múltiples órdenes al final del día.
    
    Solo procesa con método POST para evitar cambios accidentales.
    """
    if request.method == 'POST':
        from django.utils import timezone
        
        # Obtener todas las órdenes finalizadas
        ordenes_finalizadas = OrdenServicio.objects.filter(estado='finalizado')
        cantidad = ordenes_finalizadas.count()
        
        if cantidad > 0:
            # Actualizar todas a 'entregado'
            ordenes_finalizadas.update(
                estado='entregado',
                fecha_entrega=timezone.now()
            )
            
            messages.success(
                request,
                f'Se cerraron {cantidad} orden(es) finalizada(s).'
            )
        else:
            messages.info(
                request,
                'No hay órdenes finalizadas para cerrar.'
            )
    else:
        messages.warning(
            request,
            'Método no permitido. Use el botón "Cerrar Todas".'
        )
    
    return redirect('servicio_tecnico:lista_activas')


# ============================================================================
# VISTA DE DETALLES DE ORDEN (Vista Principal y Más Compleja)
# ============================================================================

@login_required
def detalle_orden(request, orden_id):
    """
    Vista completa de detalles de una orden de servicio.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta es la vista más compleja del sistema porque maneja MÚLTIPLES formularios
    en una sola página:
    
    1. Configuración Adicional (diagnóstico, fechas)
    2. Reingreso/RHITSO (checkboxes y selects)
    3. Cambio de Estado (dropdown de estados)
    4. Comentarios (textarea para agregar notas)
    5. Subir Imágenes (múltiples archivos)
    
    FLUJO DE PROCESAMIENTO:
    - Si es GET: Mostrar todos los formularios vacíos/llenos con datos actuales
    - Si es POST: Procesar el formulario específico que se envió
      * Usamos un campo oculto 'form_type' para saber qué formulario se envió
      * Solo procesamos ese formulario específico
      * Los demás formularios se vuelven a crear con datos actuales
    
    Args:
        request: Petición HTTP
        orden_id: ID de la orden a mostrar
    
    Returns:
        Renderiza el template con todos los formularios y datos
    """
    
    # Obtener la orden o mostrar error 404
    orden = get_object_or_404(
        OrdenServicio.objects.select_related(
            'sucursal',
            'responsable_seguimiento',
            'tecnico_asignado_actual',
            'detalle_equipo',
            'orden_original',
            'incidencia_scorecard'
        ).prefetch_related(
            'imagenes',
            'historial__usuario',
            'historial__tecnico_anterior',
            'historial__tecnico_nuevo'
        ),
        pk=orden_id
    )
    
    # Obtener el empleado actual del usuario
    empleado_actual = None
    if hasattr(request.user, 'empleado'):
        empleado_actual = request.user.empleado
    
    # ========================================================================
    # PROCESAMIENTO DE FORMULARIOS (POST)
    # ========================================================================
    
    if request.method == 'POST':
        # Identificar qué formulario se envió
        form_type = request.POST.get('form_type', '')
        
        # ------------------------------------------------------------------------
        # FORMULARIO 1: Configuración Adicional
        # ------------------------------------------------------------------------
        if form_type == 'configuracion':
            form_config = ConfiguracionAdicionalForm(
                request.POST,
                instance=orden.detalle_equipo
            )
            
            if form_config.is_valid():
                form_config.save()
                messages.success(request, '✅ Configuración actualizada correctamente.')
                
                # Registrar en historial
                HistorialOrden.objects.create(
                    orden=orden,
                    tipo_evento='actualizacion',
                    comentario='Configuración adicional actualizada (diagnóstico, fechas)',
                    usuario=empleado_actual,
                    es_sistema=False
                )
                
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
            else:
                messages.error(request, '❌ Error al actualizar la configuración.')
        
        # ------------------------------------------------------------------------
        # FORMULARIO 2: Reingreso y RHITSO
        # ------------------------------------------------------------------------
        elif form_type == 'reingreso_rhitso':
            form_reingreso = ReingresoRHITSOForm(request.POST, instance=orden)
            
            if form_reingreso.is_valid():
                orden_actualizada = form_reingreso.save()
                
                # Si se marcó como reingreso, crear incidencia de ScoreCard
                if orden_actualizada.es_reingreso and not orden_actualizada.incidencia_scorecard:
                    incidencia = orden_actualizada.crear_incidencia_reingreso(usuario=empleado_actual)
                    if incidencia:
                        messages.success(
                            request,
                            f'✅ Orden marcada como reingreso. Incidencia creada: {incidencia.folio}'
                        )
                
                messages.success(request, '✅ Información de reingreso/RHITSO actualizada.')
                
                # Registrar en historial
                comentario_historial = []
                if orden_actualizada.es_reingreso:
                    comentario_historial.append('Marcada como REINGRESO')
                if orden_actualizada.es_candidato_rhitso:
                    comentario_historial.append(f'Candidato a RHITSO: {orden_actualizada.get_motivo_rhitso_display()}')
                
                if comentario_historial:
                    HistorialOrden.objects.create(
                        orden=orden,
                        tipo_evento='actualizacion',
                        comentario=' | '.join(comentario_historial),
                        usuario=empleado_actual,
                        es_sistema=False
                    )
                
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
            else:
                messages.error(request, '❌ Error al actualizar reingreso/RHITSO.')
        
        # ------------------------------------------------------------------------
        # FORMULARIO 3: Cambio de Estado
        # ------------------------------------------------------------------------
        elif form_type == 'cambio_estado':
            form_estado = CambioEstadoForm(request.POST, instance=orden)
            
            if form_estado.is_valid():
                estado_anterior = orden.estado
                orden_actualizada = form_estado.save()
                
                # Actualizar fecha de finalización si cambió a 'finalizado'
                if orden_actualizada.estado == 'finalizado' and estado_anterior != 'finalizado':
                    orden_actualizada.fecha_finalizacion = timezone.now()
                    orden_actualizada.save()
                
                # Actualizar fecha de entrega si cambió a 'entregado'
                if orden_actualizada.estado == 'entregado' and estado_anterior != 'entregado':
                    orden_actualizada.fecha_entrega = timezone.now()
                    orden_actualizada.save()
                
                # Agregar comentario adicional si existe
                comentario_cambio = form_estado.cleaned_data.get('comentario_cambio', '')
                if comentario_cambio:
                    HistorialOrden.objects.create(
                        orden=orden,
                        tipo_evento='comentario',
                        comentario=f'[Cambio de estado] {comentario_cambio}',
                        usuario=empleado_actual,
                        es_sistema=False
                    )
                
                messages.success(
                    request,
                    f'✅ Estado cambiado a: {orden_actualizada.get_estado_display()}'
                )
                
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
            else:
                messages.error(request, '❌ Error al cambiar el estado.')
        
        # ------------------------------------------------------------------------
        # FORMULARIO 4: Asignar Responsables
        # ------------------------------------------------------------------------
        elif form_type == 'asignar_responsables':
            form_responsables = AsignarResponsablesForm(request.POST, instance=orden)
            
            if form_responsables.is_valid():
                # Guardar técnico anterior antes de cambiar
                tecnico_anterior = orden.tecnico_asignado_actual
                responsable_anterior = orden.responsable_seguimiento
                
                orden_actualizada = form_responsables.save()
                
                # Registrar cambios en el historial
                cambios = []
                if tecnico_anterior != orden_actualizada.tecnico_asignado_actual:
                    cambios.append(
                        f'Técnico: {tecnico_anterior.nombre_completo} → {orden_actualizada.tecnico_asignado_actual.nombre_completo}'
                    )
                    # Crear entrada específica de cambio de técnico
                    HistorialOrden.objects.create(
                        orden=orden,
                        tipo_evento='cambio_tecnico',
                        comentario=f'Técnico reasignado',
                        usuario=empleado_actual,
                        tecnico_anterior=tecnico_anterior,
                        tecnico_nuevo=orden_actualizada.tecnico_asignado_actual,
                        es_sistema=False
                    )
                
                if responsable_anterior != orden_actualizada.responsable_seguimiento:
                    cambios.append(
                        f'Responsable: {responsable_anterior.nombre_completo} → {orden_actualizada.responsable_seguimiento.nombre_completo}'
                    )
                    # Crear entrada de cambio de responsable
                    HistorialOrden.objects.create(
                        orden=orden,
                        tipo_evento='actualizacion',
                        comentario=f'Responsable de seguimiento cambiado a: {orden_actualizada.responsable_seguimiento.nombre_completo}',
                        usuario=empleado_actual,
                        es_sistema=False
                    )
                
                if cambios:
                    messages.success(
                        request,
                        f'✅ Responsables actualizados: {" | ".join(cambios)}'
                    )
                else:
                    messages.info(request, 'ℹ️ No se realizaron cambios en los responsables.')
                
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
            else:
                messages.error(request, '❌ Error al asignar responsables.')
        
        # ------------------------------------------------------------------------
        # FORMULARIO 5: Agregar Comentario
        # ------------------------------------------------------------------------
        elif form_type == 'comentario':
            form_comentario = ComentarioForm(request.POST)
            
            if form_comentario.is_valid():
                form_comentario.save(orden=orden, usuario=empleado_actual)
                messages.success(request, '✅ Comentario agregado correctamente.')
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
            else:
                messages.error(request, '❌ Error al agregar el comentario.')
        
        # ------------------------------------------------------------------------
        # FORMULARIO 6: Subir Imágenes
        # ------------------------------------------------------------------------
        elif form_type == 'subir_imagenes':
            form_imagenes = SubirImagenesForm(request.POST, request.FILES)
            
            if form_imagenes.is_valid():
                # Procesar imágenes (múltiples archivos)
                imagenes_files = request.FILES.getlist('imagenes')
                tipo_imagen = form_imagenes.cleaned_data['tipo']
                descripcion = form_imagenes.cleaned_data.get('descripcion', '')
                
                # Validar cantidad máxima (30 imágenes POR CARGA, no total)
                imagenes_a_subir = len(imagenes_files)
                
                if imagenes_a_subir > 30:
                    messages.error(
                        request,
                        f'❌ Solo puedes subir máximo 30 imágenes por carga. '
                        f'Seleccionaste {imagenes_a_subir}. Si necesitas más, '
                        f'realiza otra carga después.'
                    )
                    return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
                
                # Procesar cada imagen
                imagenes_guardadas = 0
                for imagen_file in imagenes_files:
                    # Validar tamaño (6MB = 6 * 1024 * 1024 bytes)
                    if imagen_file.size > 6 * 1024 * 1024:
                        messages.warning(
                            request,
                            f'⚠️ Imagen "{imagen_file.name}" excede 6MB y fue omitida.'
                        )
                        continue
                    
                    # Comprimir y guardar imagen
                    try:
                        imagen_orden = comprimir_y_guardar_imagen(
                            orden=orden,
                            imagen_file=imagen_file,
                            tipo=tipo_imagen,
                            descripcion=descripcion,
                            empleado=empleado_actual
                        )
                        imagenes_guardadas += 1
                    except Exception as e:
                        messages.warning(
                            request,
                            f'⚠️ Error al procesar "{imagen_file.name}": {str(e)}'
                        )
                
                if imagenes_guardadas > 0:
                    messages.success(
                        request,
                        f'✅ {imagenes_guardadas} imagen(es) subida(s) correctamente.'
                    )
                    
                    # Registrar en historial
                    HistorialOrden.objects.create(
                        orden=orden,
                        tipo_evento='imagen',
                        comentario=f'{imagenes_guardadas} imagen(es) tipo "{dict(form_imagenes.fields["tipo"].choices)[tipo_imagen]}" agregadas',
                        usuario=empleado_actual,
                        es_sistema=False
                    )
                
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
            else:
                messages.error(request, '❌ Error al subir las imágenes.')
    
    # ========================================================================
    # CREAR FORMULARIOS VACÍOS O CON DATOS ACTUALES (GET o POST con errores)
    # ========================================================================
    
    form_config = ConfiguracionAdicionalForm(instance=orden.detalle_equipo)
    form_reingreso = ReingresoRHITSOForm(instance=orden)
    form_estado = CambioEstadoForm(instance=orden)
    form_responsables = AsignarResponsablesForm(instance=orden)
    form_comentario = ComentarioForm()
    form_imagenes = SubirImagenesForm()
    
    # ========================================================================
    # OBTENER HISTORIAL Y COMENTARIOS
    # ========================================================================
    
    # Historial completo ordenado por fecha (más reciente primero)
    historial_completo = orden.historial.all().order_by('-fecha_evento')
    
    # Separar historial automático y comentarios
    historial_automatico = historial_completo.exclude(tipo_evento='comentario')
    comentarios = historial_completo.filter(tipo_evento='comentario')
    
    # ========================================================================
    # ORGANIZAR IMÁGENES POR TIPO
    # ========================================================================
    
    imagenes_por_tipo = {
        'ingreso': orden.imagenes.filter(tipo='ingreso').order_by('-fecha_subida'),
        'diagnostico': orden.imagenes.filter(tipo='diagnostico').order_by('-fecha_subida'),
        'reparacion': orden.imagenes.filter(tipo='reparacion').order_by('-fecha_subida'),
        'egreso': orden.imagenes.filter(tipo='egreso').order_by('-fecha_subida'),
        'otras': orden.imagenes.filter(tipo='otras').order_by('-fecha_subida'),
    }
    
    total_imagenes = orden.imagenes.count()
    
    # ========================================================================
    # ESTADÍSTICAS DE TÉCNICOS (Para alertas de carga de trabajo)
    # ========================================================================
    
    # Obtener todos los técnicos de laboratorio para mostrar sus estadísticas
    tecnicos_laboratorio = Empleado.objects.filter(
        activo=True,
        cargo__icontains='TECNICO DE LABORATORIO'
    )
    
    # Crear diccionario con estadísticas de cada técnico
    # Esto se usa en el template para mostrar alertas
    estadisticas_tecnicos = {}
    for tecnico in tecnicos_laboratorio:
        estadisticas_tecnicos[tecnico.pk] = tecnico.obtener_estadisticas_ordenes_activas()
    
    # ========================================================================
    # CONTEXT PARA EL TEMPLATE
    # ========================================================================
    
    context = {
        'orden': orden,
        'detalle': orden.detalle_equipo,
        
        # Formularios
        'form_config': form_config,
        'form_reingreso': form_reingreso,
        'form_estado': form_estado,
        'form_responsables': form_responsables,
        'form_comentario': form_comentario,
        'form_imagenes': form_imagenes,
        
        # Historial y comentarios
        'historial_automatico': historial_automatico[:20],  # Últimos 20
        'comentarios': comentarios[:20],  # Últimos 20
        
        # Imágenes
        'imagenes_por_tipo': imagenes_por_tipo,
        'total_imagenes': total_imagenes,
        
        # Información adicional
        'dias_en_servicio': orden.dias_en_servicio,
        'esta_retrasada': orden.esta_retrasada,
        
        # Estadísticas de técnicos (para alertas) - Convertido a JSON para JavaScript
        'estadisticas_tecnicos': mark_safe(json.dumps(estadisticas_tecnicos)),
    }
    
    return render(request, 'servicio_tecnico/detalle_orden.html', context)


# ============================================================================
# FUNCIÓN AUXILIAR: Comprimir y Guardar Imagen
# ============================================================================

def comprimir_y_guardar_imagen(orden, imagen_file, tipo, descripcion, empleado):
    """
    Comprime y guarda una imagen con la estructura de carpetas solicitada.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta función hace lo siguiente:
    1. Crea la estructura de carpetas: media/servicio_tecnico/{service_tag}/{tipo}/
    2. Genera un nombre único para la imagen: {tipo}_{timestamp}.jpg
    3. Guarda la imagen ORIGINAL (alta resolución, sin comprimir)
    4. Crea una versión COMPRIMIDA para mostrar en la galería
    5. Guarda ambas versiones en el registro de la base de datos
    
    Args:
        orden: OrdenServicio a la que pertenece la imagen
        imagen_file: Archivo de imagen subido
        tipo: Tipo de imagen (ingreso, egreso, etc.)
        descripcion: Descripción opcional
        empleado: Empleado que sube la imagen
    
    Returns:
        ImagenOrden: Registro de imagen creado con ambas versiones
    """
    from django.core.files.base import ContentFile
    from io import BytesIO
    import time
    
    # Obtener número de serie del equipo
    service_tag = orden.detalle_equipo.numero_serie
    
    # Crear timestamp único
    timestamp = int(time.time() * 1000)  # Milisegundos
    
    # Extensión del archivo original
    extension = os.path.splitext(imagen_file.name)[1].lower()
    if not extension:
        extension = '.jpg'
    
    # Nombre del archivo: {tipo}_{timestamp}{extension}
    nombre_archivo = f"{tipo}_{timestamp}{extension}"
    nombre_archivo_original = f"{tipo}_{timestamp}_original{extension}"
    
    # Abrir imagen con Pillow
    img_original = Image.open(imagen_file)
    
    # Convertir a RGB si es necesario (para JPG)
    if img_original.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img_original.size, (255, 255, 255))
        background.paste(img_original, mask=img_original.split()[-1] if img_original.mode == 'RGBA' else None)
        img_original = background
    
    # ========================================================================
    # GUARDAR IMAGEN ORIGINAL (SIN COMPRIMIR - ALTA RESOLUCIÓN)
    # ========================================================================
    buffer_original = BytesIO()
    img_original.save(buffer_original, format='JPEG', quality=95, optimize=False)
    buffer_original.seek(0)
    
    # ========================================================================
    # CREAR VERSIÓN COMPRIMIDA PARA GALERÍA
    # ========================================================================
    img_comprimida = img_original.copy()
    max_size = (1920, 1920)
    img_comprimida.thumbnail(max_size, Image.Resampling.LANCZOS)
    
    # Guardar versión comprimida en buffer
    buffer_comprimido = BytesIO()
    img_comprimida.save(buffer_comprimido, format='JPEG', quality=85, optimize=True)
    buffer_comprimido.seek(0)
    
    # ========================================================================
    # CREAR REGISTRO DE IMAGENORDEN
    # ========================================================================
    imagen_orden = ImagenOrden(
        orden=orden,
        tipo=tipo,
        descripcion=descripcion,
        subido_por=empleado
    )
    
    # Guardar archivo comprimido (para galería)
    imagen_orden.imagen.save(nombre_archivo, ContentFile(buffer_comprimido.getvalue()), save=False)
    
    # Guardar archivo original (para descargas)
    imagen_orden.imagen_original.save(nombre_archivo_original, ContentFile(buffer_original.getvalue()), save=False)
    
    # Guardar el objeto (esto dispara el save() del modelo que crea el historial)
    imagen_orden.save()
    
    return imagen_orden


# ============================================================================
# VISTA: Descargar Imagen Original
# ============================================================================

@login_required
def descargar_imagen_original(request, imagen_id):
    """
    Descarga la imagen original (alta resolución) de una orden.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista permite descargar la versión original (sin comprimir) de una imagen.
    Incluye validaciones de seguridad:
    - Usuario debe estar autenticado
    - La imagen debe existir
    - Debe tener versión original guardada
    
    Args:
        request: Objeto HttpRequest
        imagen_id: ID de la ImagenOrden
    
    Returns:
        HttpResponse con el archivo de imagen para descargar
    """
    from django.http import FileResponse, Http404, HttpResponseForbidden
    
    # Obtener la imagen o retornar 404
    imagen = get_object_or_404(ImagenOrden, pk=imagen_id)
    
    # Verificar que el usuario tiene permiso (empleado activo)
    try:
        empleado = request.user.empleado
        if not empleado.activo:
            return HttpResponseForbidden("No tienes permisos para descargar imágenes.")
    except:
        return HttpResponseForbidden("Debes ser un empleado activo para descargar imágenes.")
    
    # Verificar que existe la imagen original
    if not imagen.imagen_original:
        messages.warning(
            request,
            '⚠️ Esta imagen no tiene versión original guardada. '
            'Se descargará la versión comprimida.'
        )
        archivo_imagen = imagen.imagen
    else:
        archivo_imagen = imagen.imagen_original
    
    # Verificar que el archivo existe físicamente
    if not archivo_imagen or not archivo_imagen.storage.exists(archivo_imagen.name):
        raise Http404("El archivo de imagen no existe.")
    
    # Obtener el nombre del archivo original
    nombre_archivo = os.path.basename(archivo_imagen.name)
    
    # Crear nombre descriptivo para descarga
    tipo_texto = imagen.get_tipo_display()
    orden_numero = imagen.orden.numero_orden_interno
    service_tag = imagen.orden.detalle_equipo.numero_serie
    nombre_descarga = f"{orden_numero}_{service_tag}_{tipo_texto}_{nombre_archivo}"
    
    # Abrir archivo y crear respuesta
    archivo = archivo_imagen.open('rb')
    response = FileResponse(archivo, content_type='image/jpeg')
    response['Content-Disposition'] = f'attachment; filename="{nombre_descarga}"'
    
    return response
