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
from django.db.models import Count, Q, Prefetch
from django.utils import timezone
from django.http import JsonResponse
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_http_methods
from PIL import Image
import os
import json
from .models import (
    OrdenServicio, 
    DetalleEquipo, 
    HistorialOrden, 
    ImagenOrden,
    EstadoRHITSO,
    SeguimientoRHITSO,
    IncidenciaRHITSO,
    TipoIncidenciaRHITSO,
    CategoriaDiagnostico,
    ConfiguracionRHITSO,
)
from inventario.models import Empleado
from config.constants import ESTADO_ORDEN_CHOICES
from .utils_rhitso import (
    calcular_dias_habiles,
    calcular_dias_en_estatus,
    obtener_color_por_dias_rhitso,
    formatear_tiempo_transcurrido,
    obtener_estado_proceso_rhitso,
)
from .forms import (
    NuevaOrdenForm,
    NuevaOrdenVentaMostradorForm,
    ConfiguracionAdicionalForm,
    ReingresoRHITSOForm,
    CambioEstadoForm,
    AsignarResponsablesForm,
    ComentarioForm,
    SubirImagenesForm,
    EditarInformacionEquipoForm,
    CrearCotizacionForm,
    GestionarCotizacionForm,
    ActualizarEstadoRHITSOForm,
    RegistrarIncidenciaRHITSOForm,
    ResolverIncidenciaRHITSOForm,
    EditarDiagnosticoSICForm,
)


def registrar_historial(orden, tipo_evento, usuario, comentario='', es_sistema=False):
    """
    Función helper para registrar eventos en el historial de la orden.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta función crea un registro en la tabla HistorialOrden cada vez que
    sucede algo importante en una orden (cambio de estado, comentario, etc.)
    
    PARÁMETROS:
    - orden: La orden de servicio
    - tipo_evento: Tipo de acción (ej: 'actualizacion', 'estado', 'comentario', 'cotizacion')
    - usuario: El empleado que realizó la acción (puede ser None para eventos del sistema)
    - comentario: Descripción detallada del evento (opcional)
    - es_sistema: True si es un evento automático del sistema
    
    TIPOS DE EVENTO VÁLIDOS:
    - 'estado': Cambio de estado
    - 'comentario': Comentario agregado
    - 'actualizacion': Actualización de información
    - 'imagen': Imagen subida
    - 'cambio_tecnico': Reasignación de técnico
    - 'cotizacion': Eventos relacionados con cotización
    """
    HistorialOrden.objects.create(
        orden=orden,
        tipo_evento=tipo_evento,
        comentario=comentario,
        usuario=usuario,
        es_sistema=es_sistema
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
                
                # Redirigir al detalle de la orden recién creada
                # Usamos el nombre de la URL 'servicio_tecnico:detalle_orden' y pasamos el id de la orden
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.id)
            
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
def crear_orden_venta_mostrador(request):
    """
    Vista para crear una nueva orden de Venta Mostrador (sin diagnóstico).
    
    EXPLICACIÓN DEL FLUJO:
    Las ventas mostrador son servicios directos que NO requieren diagnóstico técnico:
    - Instalación de piezas compradas en el momento
    - Reinstalación de sistema operativo
    - Limpieza express
    - Venta de accesorios
    
    El flujo es más simple que una orden normal:
    1. Se crea la orden con tipo_servicio='venta_mostrador'
    2. El estado inicial es 'recepcion' (pueden empezar de inmediato)
    3. Se redirige al detalle de la orden para agregar los servicios específicos
    
    Args:
        request: Objeto HttpRequest
    
    Returns:
        HttpResponse: Renderiza el template o redirige
    """
    
    if request.method == 'POST':
        form = NuevaOrdenVentaMostradorForm(request.POST, user=request.user)
        
        if form.is_valid():
            try:
                # Guardar la orden (automáticamente se marca como venta_mostrador)
                orden = form.save()
                
                # Mensaje de éxito
                messages.success(
                    request,
                    f'¡Orden de Venta Mostrador {orden.numero_orden_interno} creada exitosamente! '
                    f'Ahora agrega los servicios y paquetes específicos.'
                )
                
                # Redirigir al detalle de la orden para agregar la venta mostrador
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.id)
            
            except Exception as e:
                messages.error(
                    request,
                    f'Error al crear la orden de venta mostrador: {str(e)}'
                )
        else:
            messages.warning(
                request,
                'Por favor corrige los errores en el formulario.'
            )
    
    else:
        # GET: Mostrar formulario vacío
        form = NuevaOrdenVentaMostradorForm(user=request.user)
    
    context = {
        'form': form,
        'titulo': 'Nueva Venta Mostrador',
        'subtitulo': 'Servicio Directo sin Diagnóstico',
        'accion': 'Crear',
        'es_venta_mostrador': True,  # Flag para el template
    }
    
    return render(request, 'servicio_tecnico/form_nueva_orden_venta_mostrador.html', context)


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
    
    # ========================================================================
    # ESTADÍSTICAS: EQUIPOS "NO ENCIENDE" POR TÉCNICO (ACTIVOS + HISTÓRICO)
    # ========================================================================
    # ACTUALIZACIÓN: Se divide en dos consultas para mostrar:
    # 1. ACTIVOS: Solo equipos "No Enciende" actualmente en proceso (carga específica)
    # 2. HISTÓRICO: Desglose de equipos por si encendían o no (experiencia detallada)
    
    # --- CONSULTA 1: Equipos "No Enciende" ACTIVOS (carga actual específica) ---
    equipos_no_enciende_activos_raw = OrdenServicio.objects.exclude(
        estado__in=['entregado', 'cancelado']
    ).filter(
        detalle_equipo__equipo_enciende=False,
        tecnico_asignado_actual__cargo='TECNICO DE LABORATORIO'
    ).values(
        'tecnico_asignado_actual__nombre_completo',
        'tecnico_asignado_actual__id'
    ).annotate(
        total_no_enciende=Count('numero_orden_interno')
    ).order_by('-total_no_enciende', 'tecnico_asignado_actual__nombre_completo')
    
    # --- CONSULTA 2: Equipos HISTÓRICOS con desglose por "equipo_enciende" ---
    # Esta consulta agrupa por técnico y por si el equipo enciende o no
    equipos_historico_desglose_raw = OrdenServicio.objects.filter(
        tecnico_asignado_actual__cargo='TECNICO DE LABORATORIO'
    ).values(
        'tecnico_asignado_actual__nombre_completo',
        'tecnico_asignado_actual__id',
        'detalle_equipo__equipo_enciende'
    ).annotate(
        total_equipos=Count('numero_orden_interno')
    ).order_by('tecnico_asignado_actual__nombre_completo', 'detalle_equipo__equipo_enciende')
    
    # --- PROCESAR DATOS ACTIVOS ---
    equipos_no_enciende_activos_dict = {}
    for item in equipos_no_enciende_activos_raw:
        tecnico_id = item['tecnico_asignado_actual__id']
        equipos_no_enciende_activos_dict[tecnico_id] = item['total_no_enciende']
    
    # --- PROCESAR DATOS HISTÓRICOS CON DESGLOSE ---
    equipos_historico_dict = {}
    for item in equipos_historico_desglose_raw:
        tecnico_id = item['tecnico_asignado_actual__id']
        equipo_enciende = item['detalle_equipo__equipo_enciende']
        total = item['total_equipos']
        
        if tecnico_id not in equipos_historico_dict:
            equipos_historico_dict[tecnico_id] = {
                'nombre': item['tecnico_asignado_actual__nombre_completo'],
                'si_enciende': 0,
                'no_enciende': 0,
                'total': 0
            }
        
        if equipo_enciende:
            equipos_historico_dict[tecnico_id]['si_enciende'] = total
        else:
            equipos_historico_dict[tecnico_id]['no_enciende'] = total
        
        equipos_historico_dict[tecnico_id]['total'] += total
    
    # --- COMBINAR ACTIVOS Y HISTÓRICOS ---
    equipos_no_enciende_por_tecnico = []
    for tecnico_id, historico_data in equipos_historico_dict.items():
        tecnico_obj = Empleado.objects.get(id=tecnico_id)
        
        equipos_no_enciende_por_tecnico.append({
            'tecnico_id': tecnico_id,
            'nombre': historico_data['nombre'],
            'foto_url': tecnico_obj.get_foto_perfil_url(),
            'iniciales': tecnico_obj.get_iniciales(),
            # Datos ACTIVOS (solo "No Enciende" en proceso)
            'activos': equipos_no_enciende_activos_dict.get(tecnico_id, 0),
            # Datos HISTÓRICOS (desglose por si enciende o no)
            'historico': {
                'si_enciende': historico_data['si_enciende'],
                'no_enciende': historico_data['no_enciende'],
                'total': historico_data['total']
            }
        })
    
    # Ordenar por total histórico descendente
    equipos_no_enciende_por_tecnico.sort(key=lambda x: x['historico']['total'], reverse=True)
    
    # ========================================================================
    # ESTADÍSTICAS: EQUIPOS POR GAMA POR TÉCNICO (ACTIVOS + HISTÓRICO)
    # ========================================================================
    # ACTUALIZACIÓN: Se divide en dos consultas para mostrar:
    # 1. ACTIVOS: Carga de trabajo actual (solo órdenes en proceso)
    # 2. HISTÓRICO: Total de equipos manejados (incluyendo cerrados)
    
    # --- CONSULTA 1: EQUIPOS ACTIVOS (Carga actual) ---
    equipos_por_gama_activos_raw = OrdenServicio.objects.exclude(
        estado__in=['entregado', 'cancelado']
    ).filter(
        tecnico_asignado_actual__cargo='TECNICO DE LABORATORIO'
    ).values(
        'tecnico_asignado_actual__nombre_completo',
        'tecnico_asignado_actual__id',
        'detalle_equipo__gama'
    ).annotate(
        total_equipos=Count('numero_orden_interno')
    ).order_by('tecnico_asignado_actual__nombre_completo', 'detalle_equipo__gama')
    
    # --- CONSULTA 2: EQUIPOS HISTÓRICO TOTAL (Todas las órdenes) ---
    equipos_por_gama_historico_raw = OrdenServicio.objects.filter(
        tecnico_asignado_actual__cargo='TECNICO DE LABORATORIO'
    ).values(
        'tecnico_asignado_actual__nombre_completo',
        'tecnico_asignado_actual__id',
        'detalle_equipo__gama'
    ).annotate(
        total_equipos=Count('numero_orden_interno')
    ).order_by('tecnico_asignado_actual__nombre_completo', 'detalle_equipo__gama')
    
    # --- PROCESAR DATOS ACTIVOS ---
    equipos_activos_dict = {}
    for item in equipos_por_gama_activos_raw:
        tecnico_id = item['tecnico_asignado_actual__id']
        gama = item['detalle_equipo__gama']
        total = item['total_equipos']
        
        if tecnico_id not in equipos_activos_dict:
            equipos_activos_dict[tecnico_id] = {
                'alta': 0, 'media': 0, 'baja': 0, 'total': 0
            }
        
        equipos_activos_dict[tecnico_id][gama] = total
        equipos_activos_dict[tecnico_id]['total'] += total
    
    # --- PROCESAR DATOS HISTÓRICOS ---
    equipos_por_gama_por_tecnico = {}
    for item in equipos_por_gama_historico_raw:
        tecnico_id = item['tecnico_asignado_actual__id']
        tecnico_nombre = item['tecnico_asignado_actual__nombre_completo']
        gama = item['detalle_equipo__gama']
        total = item['total_equipos']
        
        if tecnico_id not in equipos_por_gama_por_tecnico:
            # Obtener información adicional del técnico
            tecnico_obj = Empleado.objects.get(id=tecnico_id)
            
            # Obtener datos activos para este técnico (si existen)
            activos_data = equipos_activos_dict.get(tecnico_id, {
                'alta': 0, 'media': 0, 'baja': 0, 'total': 0
            })
            
            equipos_por_gama_por_tecnico[tecnico_id] = {
                'nombre': tecnico_nombre,
                'foto_url': tecnico_obj.get_foto_perfil_url(),
                'iniciales': tecnico_obj.get_iniciales(),
                # Datos ACTIVOS
                'activos': {
                    'alta': activos_data.get('alta', 0),
                    'media': activos_data.get('media', 0),
                    'baja': activos_data.get('baja', 0),
                    'total': activos_data.get('total', 0)
                },
                # Datos HISTÓRICOS
                'historico': {
                    'alta': 0,
                    'media': 0,
                    'baja': 0,
                    'total': 0
                }
            }
        
        # Agregar datos históricos
        equipos_por_gama_por_tecnico[tecnico_id]['historico'][gama] = total
        equipos_por_gama_por_tecnico[tecnico_id]['historico']['total'] += total
    
    # Convertir a lista ordenada por total histórico descendente
    equipos_por_gama_por_tecnico = sorted(
        equipos_por_gama_por_tecnico.values(),
        key=lambda x: x['historico']['total'],
        reverse=True
    )
    
    # Calcular total de órdenes activas (sin filtro de búsqueda) para las estadísticas
    total_ordenes_activas = OrdenServicio.objects.exclude(
        estado__in=['entregado', 'cancelado']
    ).count()
    
    context = {
        'ordenes': ordenes,
        'tipo': 'activas',
        'titulo': 'Órdenes Activas',
        'total': ordenes.count(),
        'busqueda': busqueda,
        'equipos_no_enciende_por_tecnico': equipos_no_enciende_por_tecnico,
        'equipos_por_gama_por_tecnico': equipos_por_gama_por_tecnico,
        'total_ordenes_activas': total_ordenes_activas,  # Para mostrar en estadísticas
        'mostrar_estadisticas': True,  # Siempre mostrar en vista activas
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
    
    # NO mostrar estadísticas en vista finalizadas (no tiene sentido ver cargas de trabajo de órdenes cerradas)
    context = {
        'ordenes': ordenes,
        'tipo': 'finalizadas',
        'titulo': 'Órdenes Finalizadas',
        'total': ordenes.count(),
        'busqueda': busqueda,
        'mostrar_estadisticas': False,  # No mostrar estadísticas aquí
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
    
    # VALIDACIÓN: No permitir modificar orden convertida
    if orden.estado == 'convertida_a_diagnostico':
        messages.error(
            request,
            f'❌ La orden {orden.numero_orden_interno} fue convertida a diagnóstico y ya no puede modificarse. '
            f'Esta orden está cerrada permanentemente.'
        )
        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.id)
    
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
                orden_actualizada = form_reingreso.save(commit=False)
                
                # ===================================================================
                # ASIGNAR ESTADO RHITSO AUTOMÁTICO SI ES CANDIDATO
                # ===================================================================
                # EXPLICACIÓN: Si se marca como candidato RHITSO y NO tiene estado
                # asignado, le ponemos automáticamente el primer estado
                if orden_actualizada.es_candidato_rhitso and not orden_actualizada.estado_rhitso:
                    try:
                        primer_estado = EstadoRHITSO.objects.filter(orden=1).first()
                        if primer_estado:
                            orden_actualizada.estado_rhitso = primer_estado.estado
                            messages.info(
                                request,
                                f'🎯 Estado RHITSO asignado automáticamente: {primer_estado.estado}'
                            )
                    except EstadoRHITSO.DoesNotExist:
                        pass  # Si no hay estados, continuar sin asignar
                
                # Guardar la orden con el estado asignado
                orden_actualizada.save()
                
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
                
                # El formulario maneja automáticamente las fechas en su método save()
                orden_actualizada = form_estado.save()
                
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
                # DEPURACIÓN: Mostrar errores específicos del formulario
                errores_detallados = []
                for campo, errores in form_estado.errors.items():
                    for error in errores:
                        errores_detallados.append(f"{campo}: {error}")
                
                if errores_detallados:
                    messages.error(
                        request, 
                        f'❌ Error al cambiar el estado: {" | ".join(errores_detallados)}'
                    )
                else:
                    messages.error(request, '❌ Error al cambiar el estado.')
        
        # ------------------------------------------------------------------------
        # FORMULARIO 4: Asignar Responsables
        # ------------------------------------------------------------------------
        elif form_type == 'asignar_responsables':
            # IMPORTANTE: Refrescar el objeto desde la base de datos PRIMERO
            # Esto previene que se use una versión en caché del objeto
            orden.refresh_from_db()
            
            # Guardar los valores actuales DESPUÉS del refresh
            tecnico_anterior_id = orden.tecnico_asignado_actual.id if orden.tecnico_asignado_actual else None
            responsable_anterior_id = orden.responsable_seguimiento.id if orden.responsable_seguimiento else None
            tecnico_anterior_obj = orden.tecnico_asignado_actual
            responsable_anterior_obj = orden.responsable_seguimiento
            
            form_responsables = AsignarResponsablesForm(request.POST, instance=orden)
            
            if form_responsables.is_valid():
                # Obtener los NUEVOS valores del formulario sin guardar
                orden_actualizada = form_responsables.save(commit=False)
                tecnico_nuevo_id = orden_actualizada.tecnico_asignado_actual.id if orden_actualizada.tecnico_asignado_actual else None
                responsable_nuevo_id = orden_actualizada.responsable_seguimiento.id if orden_actualizada.responsable_seguimiento else None
                
                # Guardar SOLO los campos del formulario para evitar triggers del modelo
                # Esto previene que el método save() del modelo registre el cambio automáticamente
                orden_actualizada.save(update_fields=['tecnico_asignado_actual', 'responsable_seguimiento'])
                
                # Ahora registramos los cambios MANUALMENTE en el historial
                cambios = []
                
                # Cambio de técnico
                if tecnico_anterior_id != tecnico_nuevo_id:
                    cambios.append(
                        f'Técnico: {tecnico_anterior_obj.nombre_completo if tecnico_anterior_obj else "Sin asignar"} → {orden_actualizada.tecnico_asignado_actual.nombre_completo if orden_actualizada.tecnico_asignado_actual else "Sin asignar"}'
                    )
                    HistorialOrden.objects.create(
                        orden=orden,
                        tipo_evento='cambio_tecnico',
                        comentario=f'Técnico reasignado de {tecnico_anterior_obj.nombre_completo if tecnico_anterior_obj else "Sin asignar"} a {orden_actualizada.tecnico_asignado_actual.nombre_completo if orden_actualizada.tecnico_asignado_actual else "Sin asignar"}',
                        usuario=empleado_actual,
                        tecnico_anterior=tecnico_anterior_obj,
                        tecnico_nuevo=orden_actualizada.tecnico_asignado_actual,
                        es_sistema=False
                    )
                
                # Cambio de responsable
                if responsable_anterior_id != responsable_nuevo_id:
                    cambios.append(
                        f'Responsable: {responsable_anterior_obj.nombre_completo if responsable_anterior_obj else "Sin asignar"} → {orden_actualizada.responsable_seguimiento.nombre_completo if orden_actualizada.responsable_seguimiento else "Sin asignar"}'
                    )
                    HistorialOrden.objects.create(
                        orden=orden,
                        tipo_evento='actualizacion',
                        comentario=f'Responsable de seguimiento cambiado de {responsable_anterior_obj.nombre_completo if responsable_anterior_obj else "Sin asignar"} a {orden_actualizada.responsable_seguimiento.nombre_completo if orden_actualizada.responsable_seguimiento else "Sin asignar"}',
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
                    # Retornar JSON con error en lugar de redirect
                    return JsonResponse({
                        'success': False,
                        'error': f'Solo puedes subir máximo 30 imágenes por carga. Seleccionaste {imagenes_a_subir}. Si necesitas más, realiza otra carga después.'
                    })
                
                # Procesar cada imagen
                imagenes_guardadas = 0
                imagenes_omitidas = []
                errores_procesamiento = []
                
                try:
                    for imagen_file in imagenes_files:
                        # Validar tamaño (6MB = 6 * 1024 * 1024 bytes)
                        if imagen_file.size > 6 * 1024 * 1024:
                            imagenes_omitidas.append(imagen_file.name)
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
                            errores_procesamiento.append(f"{imagen_file.name}: {str(e)}")
                    
                    # Preparar respuesta
                    if imagenes_guardadas > 0:
                        # Registrar en historial
                        HistorialOrden.objects.create(
                            orden=orden,
                            tipo_evento='imagen',
                            comentario=f'{imagenes_guardadas} imagen(es) tipo "{dict(form_imagenes.fields["tipo"].choices)[tipo_imagen]}" agregadas',
                            usuario=empleado_actual,
                            es_sistema=False
                        )
                        
                        # ================================================================
                        # CAMBIO AUTOMÁTICO DE ESTADO SEGÚN TIPO DE IMAGEN
                        # ================================================================
                        estado_anterior = orden.estado
                        cambio_realizado = False
                        mensaje_estado = ''
                        
                        # Si se suben imágenes de INGRESO → Cambiar a "En Diagnóstico"
                        if tipo_imagen == 'ingreso' and estado_anterior != 'diagnostico':
                            orden.estado = 'diagnostico'
                            cambio_realizado = True
                            mensaje_estado = f'Estado actualizado: {dict(ESTADO_ORDEN_CHOICES).get(estado_anterior)} → En Diagnóstico'
                            
                            # Registrar cambio automático en historial
                            HistorialOrden.objects.create(
                                orden=orden,
                                tipo_evento='estado',
                                comentario=f'Cambio automático de estado: {dict(ESTADO_ORDEN_CHOICES).get(estado_anterior)} → En Diagnóstico (imágenes de ingreso cargadas)',
                                usuario=empleado_actual,
                                es_sistema=True
                            )
                        
                        # Si se suben imágenes de EGRESO → Cambiar a "Finalizado - Listo para Entrega"
                        elif tipo_imagen == 'egreso' and estado_anterior != 'finalizado':
                            from django.utils import timezone as tz_module
                            orden.estado = 'finalizado'
                            orden.fecha_finalizacion = tz_module.now()
                            cambio_realizado = True
                            mensaje_estado = f'Estado actualizado: {dict(ESTADO_ORDEN_CHOICES).get(estado_anterior)} → Finalizado - Listo para Entrega'
                            
                            # Registrar cambio automático en historial
                            HistorialOrden.objects.create(
                                orden=orden,
                                tipo_evento='estado',
                                comentario=f'Cambio automático de estado: {dict(ESTADO_ORDEN_CHOICES).get(estado_anterior)} → Finalizado - Listo para Entrega (imágenes de egreso cargadas)',
                                usuario=empleado_actual,
                                es_sistema=True
                            )
                        
                        # Guardar cambios si hubo actualización de estado
                        if cambio_realizado:
                            orden.save()
                        
                        # Construir mensaje de respuesta
                        mensaje = f'✅ {imagenes_guardadas} imagen(es) subida(s) correctamente.'
                        if mensaje_estado:
                            mensaje += f' {mensaje_estado}.'
                        
                        # Retornar respuesta JSON exitosa
                        return JsonResponse({
                            'success': True,
                            'message': mensaje,
                            'imagenes_guardadas': imagenes_guardadas,
                            'imagenes_omitidas': imagenes_omitidas,
                            'errores': errores_procesamiento,
                            'cambio_estado': cambio_realizado
                        })
                    else:
                        # No se guardó ninguna imagen
                        return JsonResponse({
                            'success': False,
                            'error': 'No se pudo guardar ninguna imagen.',
                            'imagenes_omitidas': imagenes_omitidas,
                            'errores': errores_procesamiento
                        })
                        
                except Exception as e:
                    # Capturar cualquier error inesperado y retornarlo
                    import traceback
                    error_detallado = traceback.format_exc()
                    print(f"❌ ERROR AL PROCESAR IMÁGENES: {error_detallado}")
                    return JsonResponse({
                        'success': False,
                        'error': f'Error inesperado al procesar imágenes: {str(e)}',
                        'error_type': type(e).__name__,
                        'imagenes_guardadas': imagenes_guardadas
                    }, status=500)
            else:
                # Formulario no válido
                return JsonResponse({
                    'success': False,
                    'error': 'Error en el formulario. Verifica los datos enviados.',
                    'form_errors': form_imagenes.errors
                })
        
        # ------------------------------------------------------------------------
        # FORMULARIO 7: Editar Información Principal del Equipo
        # ------------------------------------------------------------------------
        elif form_type == 'editar_info_equipo':
            form_editar_info = EditarInformacionEquipoForm(
                request.POST,
                instance=orden.detalle_equipo
            )
            
            if form_editar_info.is_valid():
                detalle_actualizado = form_editar_info.save()
                messages.success(request, '✅ Información del equipo actualizada correctamente.')
                
                # Registrar en historial
                HistorialOrden.objects.create(
                    orden=orden,
                    tipo_evento='actualizacion',
                    comentario='Información principal del equipo actualizada (marca, modelo, número de serie, etc.)',
                    usuario=empleado_actual,
                    es_sistema=False
                )
                
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
            else:
                messages.error(request, '❌ Error al actualizar la información del equipo.')
        
        # ------------------------------------------------------------------------
        # FORMULARIO 8: Crear Cotización
        # ------------------------------------------------------------------------
        elif form_type == 'crear_cotizacion':
            # Verificar que no exista ya una cotización
            if hasattr(orden, 'cotizacion'):
                messages.warning(request, '⚠️ Esta orden ya tiene una cotización. Edítala desde el admin.')
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
            
            form_crear_cotizacion = CrearCotizacionForm(request.POST)
            
            if form_crear_cotizacion.is_valid():
                # Crear la cotización vinculada a la orden
                cotizacion = form_crear_cotizacion.save(commit=False)
                cotizacion.orden = orden
                cotizacion.save()
                
                messages.success(
                    request,
                    f'✅ Cotización creada correctamente con mano de obra: ${cotizacion.costo_mano_obra}. '
                    f'Ahora agrega las piezas necesarias desde el admin.'
                )
                
                # Registrar en historial
                HistorialOrden.objects.create(
                    orden=orden,
                    tipo_evento='cotizacion',
                    comentario=f'Cotización creada - Mano de obra: ${cotizacion.costo_mano_obra}',
                    usuario=empleado_actual,
                    es_sistema=False
                )
                
                # MODIFICACIÓN: Se eliminó el cambio automático de estado
                # Ahora el usuario debe cambiar manualmente el estado usando
                # el formulario de "Asignación de Estado" en la sección 2
                # 
                # CÓDIGO ANTERIOR (ELIMINADO):
                # - Cambiaba automáticamente orden.estado = 'cotizacion'
                # - Mostraba mensaje: "Estado actualizado automáticamente"
                # - Registraba en historial como "Cambio automático de estado"
                
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
            else:
                messages.error(request, '❌ Error al crear la cotización.')
        
        # ------------------------------------------------------------------------
        # FORMULARIO 9: Gestionar Cotización (Aceptar/Rechazar)
        # ------------------------------------------------------------------------
        elif form_type == 'gestionar_cotizacion':
            # Verificar que existe cotización
            if not hasattr(orden, 'cotizacion'):
                messages.error(request, '❌ No existe una cotización para esta orden.')
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
            
            form_gestionar_cotizacion = GestionarCotizacionForm(
                request.POST,
                instance=orden.cotizacion
            )
            
            if form_gestionar_cotizacion.is_valid():
                accion = form_gestionar_cotizacion.cleaned_data.get('accion')
                
                # NUEVO: Obtener las piezas seleccionadas desde el POST
                piezas_seleccionadas_ids = request.POST.getlist('piezas_seleccionadas')
                
                # VALIDACIÓN: Si acepta, debe tener al menos una pieza seleccionada
                if accion == 'aceptar' and not piezas_seleccionadas_ids:
                    messages.error(
                        request,
                        '❌ Debes seleccionar al menos una pieza para aceptar la cotización.'
                    )
                    return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
                
                # Guardar la cotización
                cotizacion_actualizada = form_gestionar_cotizacion.save()
                
                # NUEVO: Actualizar el estado de cada pieza según la decisión
                todas_las_piezas = cotizacion_actualizada.piezas_cotizadas.all()
                piezas_aceptadas_count = 0
                piezas_rechazadas_count = 0
                
                if accion == 'aceptar':
                    # Si acepta, actualizar cada pieza según si fue seleccionada
                    for pieza in todas_las_piezas:
                        if str(pieza.id) in piezas_seleccionadas_ids:
                            pieza.aceptada_por_cliente = True
                            piezas_aceptadas_count += 1
                        else:
                            pieza.aceptada_por_cliente = False
                            pieza.motivo_rechazo_pieza = 'Cliente decidió no incluir esta pieza'
                            piezas_rechazadas_count += 1
                        pieza.save()
                elif accion == 'rechazar':
                    # Si rechaza toda la cotización, todas las piezas se rechazan
                    for pieza in todas_las_piezas:
                        pieza.aceptada_por_cliente = False
                        pieza.motivo_rechazo_pieza = cotizacion_actualizada.get_motivo_rechazo_display()
                        pieza.save()
                        piezas_rechazadas_count += 1
                
                # Mensaje según la decisión
                if accion == 'aceptar':
                    mensaje_piezas = f'{piezas_aceptadas_count} pieza(s) aceptada(s)'
                    if piezas_rechazadas_count > 0:
                        mensaje_piezas += f' y {piezas_rechazadas_count} pieza(s) rechazada(s)'
                    
                    messages.success(
                        request,
                        f'✅ Cotización ACEPTADA por el cliente ({mensaje_piezas}). Continúa con la reparación.'
                    )
                    
                    # Cambiar estado a "Esperando Piezas" o "En Reparación" según el caso
                    # Si hay piezas pendientes de llegar, estado = esperando_piezas
                    # Si todas las piezas están, estado = reparacion
                    tiene_seguimientos_pendientes = orden.cotizacion.seguimientos_piezas.exclude(
                        estado='recibido'
                    ).exists()
                    
                    if tiene_seguimientos_pendientes:
                        nuevo_estado = 'esperando_piezas'
                        mensaje_estado = 'Esperando Llegada de Piezas'
                    else:
                        nuevo_estado = 'reparacion'
                        mensaje_estado = 'En Reparación'
                    
                    if orden.estado != nuevo_estado:
                        estado_anterior = orden.estado
                        orden.estado = nuevo_estado
                        orden.save()
                        
                        messages.info(
                            request,
                            f'ℹ️ Estado actualizado automáticamente a: {mensaje_estado}'
                        )
                        
                        HistorialOrden.objects.create(
                            orden=orden,
                            tipo_evento='cambio_estado',
                            estado_anterior=estado_anterior,
                            estado_nuevo=nuevo_estado,
                            comentario=f'Cambio automático: cotización aceptada',
                            usuario=empleado_actual,
                            es_sistema=True
                        )
                    
                    # Registrar en historial con detalle de piezas
                    comentario_historial = f'Cliente ACEPTÓ la cotización - {mensaje_piezas} - Total: ${cotizacion_actualizada.costo_piezas_aceptadas + cotizacion_actualizada.costo_mano_obra}'
                    HistorialOrden.objects.create(
                        orden=orden,
                        tipo_evento='cotizacion',
                        comentario=comentario_historial,
                        usuario=empleado_actual,
                        es_sistema=False
                    )
                
                elif accion == 'rechazar':
                    motivo = cotizacion_actualizada.get_motivo_rechazo_display()
                    detalle = cotizacion_actualizada.detalle_rechazo
                    
                    messages.warning(
                        request,
                        f'⚠️ Cotización RECHAZADA por el cliente. Motivo: {motivo} ({piezas_rechazadas_count} pieza(s) rechazada(s))'
                    )
                    
                    # Cambiar estado a "Cotización Rechazada"
                    if orden.estado != 'rechazada':
                        estado_anterior = orden.estado
                        orden.estado = 'rechazada'
                        orden.save()
                        
                        messages.info(
                            request,
                            'ℹ️ Estado actualizado automáticamente a: Cotización Rechazada'
                        )
                        
                        HistorialOrden.objects.create(
                            orden=orden,
                            tipo_evento='cambio_estado',
                            estado_anterior=estado_anterior,
                            estado_nuevo='rechazada',
                            comentario=f'Cambio automático: cotización rechazada',
                            usuario=empleado_actual,
                            es_sistema=True
                        )
                    
                    # Registrar en historial
                    comentario_historial = f'Cliente RECHAZÓ la cotización - Motivo: {motivo} ({piezas_rechazadas_count} pieza(s) rechazada(s))'
                    if detalle:
                        comentario_historial += f' | Detalle: {detalle}'
                    
                    HistorialOrden.objects.create(
                        orden=orden,
                        tipo_evento='cotizacion',
                        comentario=comentario_historial,
                        usuario=empleado_actual,
                        es_sistema=False
                    )
                
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
            else:
                messages.error(request, '❌ Error al procesar la decisión de cotización.')
    
    # ========================================================================
    # CREAR FORMULARIOS VACÍOS O CON DATOS ACTUALES (GET o POST con errores)
    # ========================================================================
    
    # IMPORTANTE: Obtener cotización PRIMERO (se necesita para otros formularios)
    cotizacion = getattr(orden, 'cotizacion', None)
    
    form_config = ConfiguracionAdicionalForm(instance=orden.detalle_equipo)
    form_reingreso = ReingresoRHITSOForm(instance=orden)
    form_estado = CambioEstadoForm(instance=orden)
    form_responsables = AsignarResponsablesForm(instance=orden)
    form_comentario = ComentarioForm()
    form_imagenes = SubirImagenesForm()
    form_editar_info = EditarInformacionEquipoForm(instance=orden.detalle_equipo)
    
    # Formulario para agregar/editar piezas (usado en el modal)
    from .forms import PiezaCotizadaForm, SeguimientoPiezaForm
    form_pieza = PiezaCotizadaForm()
    # MODIFICADO: Pasar la cotización al formulario de seguimiento
    form_seguimiento = SeguimientoPiezaForm(cotizacion=cotizacion) if cotizacion else SeguimientoPiezaForm()
    
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
        'autorizacion': orden.imagenes.filter(tipo='autorizacion').order_by('-fecha_subida'),
    }
    
    total_imagenes = orden.imagenes.count()
    
    # ========================================================================
    # DATOS DE COTIZACIÓN (Si existe)
    # ========================================================================
    
    # Inicializar formularios de cotización
    form_crear_cotizacion = None
    form_gestionar_cotizacion = None
    piezas_cotizadas = None
    seguimientos_piezas = None
    
    if cotizacion:
        # Si existe cotización, preparar formulario de gestión
        # Solo si no tiene respuesta aún (usuario_acepto es None)
        if cotizacion.usuario_acepto is None:
            form_gestionar_cotizacion = GestionarCotizacionForm(instance=cotizacion)
        
        # Obtener piezas cotizadas ordenadas por prioridad
        piezas_cotizadas = cotizacion.piezas_cotizadas.select_related(
            'componente'
        ).order_by('orden_prioridad', 'fecha_creacion')
        
        # Obtener seguimientos de piezas (pedidos a proveedores)
        seguimientos_piezas = cotizacion.seguimientos_piezas.all().order_by(
            '-fecha_pedido'
        )
    else:
        # Si no existe cotización, preparar formulario para crear
        form_crear_cotizacion = CrearCotizacionForm()
    
    # ========================================================================
    # CALCULAR SEGUIMIENTOS CON RETRASO
    # ========================================================================
    seguimientos_retrasados_count = 0
    if seguimientos_piezas:
        from django.utils import timezone
        hoy = timezone.now().date()
        for seguimiento in seguimientos_piezas:
            if seguimiento.estado != 'recibido' and seguimiento.fecha_entrega_estimada:
                if hoy > seguimiento.fecha_entrega_estimada:
                    seguimientos_retrasados_count += 1
    
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
    
    # ========================================================================
    # VENTA MOSTRADOR - FASE 3 (ACTUALIZADO: Octubre 2025)
    # ========================================================================
    # NUEVO: El contexto de venta mostrador se carga SIEMPRE, independientemente
    # del tipo_servicio, porque ahora es un complemento opcional disponible
    # para todas las órdenes.
    
    from .forms import VentaMostradorForm, PiezaVentaMostradorForm
    
    # Inicializar variables de venta mostrador
    venta_mostrador = None
    piezas_venta_mostrador = []
    
    # Verificar si ya existe venta mostrador (independiente del tipo)
    if hasattr(orden, 'venta_mostrador'):
        venta_mostrador = orden.venta_mostrador
        
        # Obtener todas las piezas vendidas
        piezas_venta_mostrador = venta_mostrador.piezas_vendidas.select_related(
            'componente'
        ).order_by('-fecha_venta')
    
    # Preparar formularios (siempre disponibles)
    form_venta_mostrador = VentaMostradorForm(
        instance=venta_mostrador if venta_mostrador else None
    )
    form_pieza_venta_mostrador = PiezaVentaMostradorForm()
    
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
        'form_editar_info': form_editar_info,
        
        # Formularios de Cotización
        'form_crear_cotizacion': form_crear_cotizacion,
        'form_gestionar_cotizacion': form_gestionar_cotizacion,
        
        # Formularios para modales (Piezas y Seguimientos)
        'form_pieza': form_pieza,
        'form_seguimiento': form_seguimiento,
        
        # ACTUALIZADOS: Formularios de Venta Mostrador - SIEMPRE disponibles
        'venta_mostrador': venta_mostrador,
        'form_venta_mostrador': form_venta_mostrador,
        'form_pieza_venta_mostrador': form_pieza_venta_mostrador,
        'piezas_venta_mostrador': piezas_venta_mostrador,
        
        # Datos de Cotización
        'cotizacion': cotizacion,
        'piezas_cotizadas': piezas_cotizadas,
        'seguimientos_piezas': seguimientos_piezas,
        'seguimientos_retrasados_count': seguimientos_retrasados_count,
        
        # Historial y comentarios
        'historial_automatico': historial_automatico[:20],  # Últimos 20
        'comentarios': comentarios[:20],  # Últimos 20
        
        # Imágenes
        'imagenes_por_tipo': imagenes_por_tipo,
        'total_imagenes': total_imagenes,
        
        # Información adicional
        'dias_en_servicio': orden.dias_en_servicio,
        'esta_retrasada': orden.esta_retrasada,
        
        # NUEVO: Variables contextuales para la UI
        'es_orden_diagnostico': orden.tipo_servicio == 'diagnostico',
        'es_orden_directa': orden.tipo_servicio == 'venta_mostrador',
        'tiene_cotizacion': cotizacion is not None,
        'tiene_venta_mostrador': venta_mostrador is not None,
        
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


# ============================================================================
# VISTA: Eliminar Imagen de Orden
# ============================================================================

@login_required
@require_http_methods(["POST"])
def eliminar_imagen(request, imagen_id):
    """
    Elimina una imagen de una orden de servicio.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista elimina completamente una imagen:
    1. Verifica permisos del usuario
    2. Elimina el registro de la base de datos
    3. Elimina los archivos físicos (imagen comprimida y original)
    4. Registra la acción en el historial
    5. Retorna JSON con el resultado
    
    Validaciones de seguridad:
    - Usuario debe estar autenticado
    - Solo método POST permitido
    - Usuario debe ser empleado activo
    - La imagen debe existir
    
    Args:
        request: Objeto HttpRequest
        imagen_id: ID de la ImagenOrden a eliminar
    
    Returns:
        JsonResponse con éxito o error
    """
    # Verificar que el usuario es un empleado activo
    try:
        empleado_actual = request.user.empleado
        if not empleado_actual.activo:
            return JsonResponse({
                'success': False,
                'error': 'No tienes permisos para eliminar imágenes.'
            }, status=403)
    except:
        return JsonResponse({
            'success': False,
            'error': 'Debes ser un empleado activo para eliminar imágenes.'
        }, status=403)
    
    # Obtener la imagen o retornar error 404
    try:
        imagen = ImagenOrden.objects.select_related('orden', 'subido_por').get(pk=imagen_id)
    except ImagenOrden.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'La imagen no existe.'
        }, status=404)
    
    try:
        # Guardar información para el historial antes de eliminar
        orden = imagen.orden
        tipo_imagen = imagen.get_tipo_display()
        descripcion_imagen = imagen.descripcion or imagen.nombre_archivo
        
        # Eliminar archivos físicos del sistema de archivos
        archivos_eliminados = []
        
        # Eliminar imagen comprimida
        if imagen.imagen:
            try:
                ruta_imagen = imagen.imagen.path
                if os.path.exists(ruta_imagen):
                    os.remove(ruta_imagen)
                    archivos_eliminados.append('imagen comprimida')
            except Exception as e:
                print(f"⚠️ No se pudo eliminar archivo comprimido: {str(e)}")
        
        # Eliminar imagen original
        if imagen.imagen_original:
            try:
                ruta_original = imagen.imagen_original.path
                if os.path.exists(ruta_original):
                    os.remove(ruta_original)
                    archivos_eliminados.append('imagen original')
            except Exception as e:
                print(f"⚠️ No se pudo eliminar archivo original: {str(e)}")
        
        # Eliminar registro de la base de datos
        imagen.delete()
        
        # Registrar en historial
        HistorialOrden.objects.create(
            orden=orden,
            tipo_evento='imagen',
            comentario=f'Imagen {tipo_imagen} eliminada: {descripcion_imagen} (Eliminada por: {empleado_actual.nombre_completo})',
            usuario=empleado_actual,
            es_sistema=False
        )
        
        # Mensaje de éxito
        mensaje_archivos = f" ({', '.join(archivos_eliminados)})" if archivos_eliminados else ""
        
        return JsonResponse({
            'success': True,
            'message': f'✅ Imagen {tipo_imagen} eliminada correctamente{mensaje_archivos}.',
            'imagen_id': imagen_id
        })
        
    except Exception as e:
        # Capturar cualquier error inesperado
        import traceback
        error_detallado = traceback.format_exc()
        print(f"❌ ERROR AL ELIMINAR IMAGEN: {error_detallado}")
        
        return JsonResponse({
            'success': False,
            'error': f'Error inesperado al eliminar la imagen: {str(e)}',
            'error_type': type(e).__name__
        }, status=500)


# ============================================================================
# VISTAS PARA GESTIÓN DE REFERENCIAS DE GAMA
# ============================================================================

@login_required
def lista_referencias_gama(request):
    """
    Lista todas las referencias de gama de equipos con filtros de búsqueda.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista muestra un listado de todas las referencias de gama (alta, media, baja)
    que se usan para clasificar automáticamente los equipos cuando se crea una orden.
    
    Funcionalidad:
    - Listado completo de referencias
    - Filtros por marca, modelo y gama
    - Búsqueda por texto
    - Ordenamiento por campos
    """
    from .models import ReferenciaGamaEquipo
    
    # Obtener todas las referencias activas primero
    referencias = ReferenciaGamaEquipo.objects.all()
    
    # Filtros de búsqueda
    busqueda = request.GET.get('busqueda', '')
    filtro_marca = request.GET.get('marca', '')
    filtro_gama = request.GET.get('gama', '')
    mostrar_inactivos = request.GET.get('mostrar_inactivos', '') == 'on'
    
    if busqueda:
        # Buscar en marca o modelo
        referencias = referencias.filter(
            Q(marca__icontains=busqueda) | 
            Q(modelo_base__icontains=busqueda)
        )
    
    if filtro_marca:
        referencias = referencias.filter(marca__iexact=filtro_marca)
    
    if filtro_gama:
        referencias = referencias.filter(gama=filtro_gama)
    
    if not mostrar_inactivos:
        referencias = referencias.filter(activo=True)
    
    # Obtener listas únicas para los filtros
    marcas_disponibles = ReferenciaGamaEquipo.objects.values_list('marca', flat=True).distinct().order_by('marca')
    
    # Ordenamiento
    orden = request.GET.get('orden', 'marca')
    if orden in ['marca', '-marca', 'modelo_base', '-modelo_base', 'gama', '-gama', 'rango_costo_min', '-rango_costo_min']:
        referencias = referencias.order_by(orden)
    
    context = {
        'referencias': referencias,
        'busqueda': busqueda,
        'filtro_marca': filtro_marca,
        'filtro_gama': filtro_gama,
        'mostrar_inactivos': mostrar_inactivos,
        'marcas_disponibles': marcas_disponibles,
        'total_referencias': referencias.count(),
        'gamas_choices': [
            ('alta', 'Alta'),
            ('media', 'Media'),
            ('baja', 'Baja'),
        ],
    }
    
    return render(request, 'servicio_tecnico/referencias_gama/lista.html', context)


@login_required
def crear_referencia_gama(request):
    """
    Crea una nueva referencia de gama de equipo.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista permite agregar una nueva referencia al catálogo.
    Cuando creas una referencia (por ejemplo: "Lenovo ThinkPad - Alta"),
    el sistema automáticamente clasificará equipos Lenovo ThinkPad como gama alta
    cuando se cree una orden de servicio.
    """
    from .models import ReferenciaGamaEquipo
    from .forms import ReferenciaGamaEquipoForm
    
    if request.method == 'POST':
        form = ReferenciaGamaEquipoForm(request.POST)
        
        if form.is_valid():
            try:
                referencia = form.save()
                messages.success(
                    request,
                    f'✅ Referencia creada: {referencia.marca} {referencia.modelo_base} - '
                    f'Gama {referencia.get_gama_display()}'
                )
                return redirect('servicio_tecnico:lista_referencias_gama')
            except Exception as e:
                messages.error(request, f'❌ Error al crear referencia: {str(e)}')
    else:
        form = ReferenciaGamaEquipoForm()
    
    context = {
        'form': form,
        'titulo': 'Crear Nueva Referencia de Gama',
        'accion': 'Crear',
    }
    
    return render(request, 'servicio_tecnico/referencias_gama/form.html', context)


@login_required
def editar_referencia_gama(request, referencia_id):
    """
    Edita una referencia de gama existente.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Permite modificar los datos de una referencia ya creada.
    Útil cuando:
    - Cambian los rangos de precio de un modelo
    - Necesitas corregir el nombre de marca o modelo
    - Quieres cambiar la clasificación de gama
    """
    from .models import ReferenciaGamaEquipo
    from .forms import ReferenciaGamaEquipoForm
    
    referencia = get_object_or_404(ReferenciaGamaEquipo, id=referencia_id)
    
    if request.method == 'POST':
        form = ReferenciaGamaEquipoForm(request.POST, instance=referencia)
        
        if form.is_valid():
            try:
                referencia = form.save()
                messages.success(
                    request,
                    f'✅ Referencia actualizada: {referencia.marca} {referencia.modelo_base}'
                )
                return redirect('servicio_tecnico:lista_referencias_gama')
            except Exception as e:
                messages.error(request, f'❌ Error al actualizar: {str(e)}')
    else:
        form = ReferenciaGamaEquipoForm(instance=referencia)
    
    context = {
        'form': form,
        'referencia': referencia,
        'titulo': f'Editar Referencia: {referencia.marca} {referencia.modelo_base}',
        'accion': 'Actualizar',
    }
    
    return render(request, 'servicio_tecnico/referencias_gama/form.html', context)


@login_required
def eliminar_referencia_gama(request, referencia_id):
    """
    Desactiva (soft delete) una referencia de gama.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    En lugar de eliminar permanentemente la referencia, solo la marca como "inactiva".
    Esto significa que:
    - Ya no se usará para calcular gamas automáticamente
    - Se puede reactivar si es necesario
    - Se mantiene el historial
    
    Nota: Es mejor desactivar que eliminar para mantener consistencia en el sistema.
    """
    from .models import ReferenciaGamaEquipo
    
    referencia = get_object_or_404(ReferenciaGamaEquipo, id=referencia_id)
    
    if request.method == 'POST':
        try:
            # Soft delete: solo marcar como inactivo
            referencia.activo = False
            referencia.save()
            
            messages.success(
                request,
                f'✅ Referencia desactivada: {referencia.marca} {referencia.modelo_base}. '
                f'Ya no se usará para clasificación automática.'
            )
        except Exception as e:
            messages.error(request, f'❌ Error al desactivar: {str(e)}')
        
        return redirect('servicio_tecnico:lista_referencias_gama')
    
    context = {
        'referencia': referencia,
    }
    
    return render(request, 'servicio_tecnico/referencias_gama/confirmar_eliminar.html', context)


@login_required
def reactivar_referencia_gama(request, referencia_id):
    """
    Reactiva una referencia previamente desactivada.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Si desactivaste una referencia por error o necesitas volver a usarla,
    esta función la marca como activa nuevamente.
    """
    from .models import ReferenciaGamaEquipo
    
    referencia = get_object_or_404(ReferenciaGamaEquipo, id=referencia_id)
    
    try:
        referencia.activo = True
        referencia.save()
        
        messages.success(
            request,
            f'✅ Referencia reactivada: {referencia.marca} {referencia.modelo_base}'
        )
    except Exception as e:
        messages.error(request, f'❌ Error al reactivar: {str(e)}')
    
    return redirect('servicio_tecnico:lista_referencias_gama')


# ============================================================================
# VISTAS AJAX: GESTIÓN DE PIEZAS COTIZADAS
# ============================================================================

@login_required
@require_http_methods(["POST"])
def agregar_pieza_cotizada(request, orden_id):
    """
    Agrega una nueva pieza a una cotización existente.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista maneja el formulario modal para agregar piezas a una cotización.
    Responde con JSON para actualizar la interfaz sin recargar la página (AJAX).
    
    FLUJO:
    1. Obtiene la orden y verifica que tenga cotización
    2. Valida el formulario recibido
    3. Asocia la pieza a la cotización
    4. Actualiza los totales de la cotización
    5. Devuelve JSON con el resultado
    """
    from django.http import JsonResponse
    from .forms import PiezaCotizadaForm
    from .models import PiezaCotizada, Cotizacion
    
    try:
        orden = get_object_or_404(OrdenServicio, id=orden_id)
        
        # Verificar que existe cotización
        if not hasattr(orden, 'cotizacion'):
            return JsonResponse({
                'success': False,
                'error': '❌ Esta orden no tiene cotización asociada'
            }, status=400)
        
        cotizacion = orden.cotizacion
        
        # Procesar formulario
        form = PiezaCotizadaForm(request.POST)
        
        if form.is_valid():
            pieza = form.save(commit=False)
            pieza.cotizacion = cotizacion
            pieza.save()
            
            # Registrar en historial
            registrar_historial(
                orden=orden,
                tipo_evento='cotizacion',
                usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
                comentario=f"✅ Pieza agregada: {pieza.componente.nombre} (x{pieza.cantidad})",
                es_sistema=False
            )
            
            return JsonResponse({
                'success': True,
                'message': f'✅ Pieza agregada: {pieza.componente.nombre}',
                'pieza_id': pieza.id,
                'pieza_html': _render_pieza_row(pieza, cotizacion)  # Función helper
            })
        else:
            # Devolver errores del formulario
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = error_list[0]  # Primer error de cada campo
            
            return JsonResponse({
                'success': False,
                'errors': errors
            }, status=400)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def editar_pieza_cotizada(request, pieza_id):
    """
    Edita una pieza cotizada existente.
    
    EXPLICACIÓN:
    Permite modificar cantidad, costo, prioridad de una pieza.
    Puede usarse incluso después de aceptar la cotización (para ajustar costos reales).
    """
    from django.http import JsonResponse
    from .forms import PiezaCotizadaForm
    from .models import PiezaCotizada
    
    try:
        pieza = get_object_or_404(PiezaCotizada, id=pieza_id)
        cotizacion = pieza.cotizacion
        orden = cotizacion.orden
        
        # Procesar formulario de edición
        form = PiezaCotizadaForm(request.POST, instance=pieza)
        
        if form.is_valid():
            pieza_actualizada = form.save()
            
            # Registrar en historial
            registrar_historial(
                orden=orden,
                tipo_evento='cotizacion',
                usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
                comentario=f"✏️ Pieza modificada: {pieza_actualizada.componente.nombre}",
                es_sistema=False
            )
            
            return JsonResponse({
                'success': True,
                'message': f'✅ Pieza actualizada: {pieza_actualizada.componente.nombre}',
                'pieza_html': _render_pieza_row(pieza_actualizada, cotizacion)
            })
        else:
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = error_list[0]
            
            return JsonResponse({
                'success': False,
                'errors': errors
            }, status=400)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def eliminar_pieza_cotizada(request, pieza_id):
    """
    Elimina una pieza de la cotización.
    
    ⚠️ VALIDACIÓN IMPORTANTE:
    NO se puede eliminar si la cotización ya fue aceptada por el usuario.
    En ese caso, se debe editar la cantidad a 0 si ya no se necesita.
    """
    from django.http import JsonResponse
    from .models import PiezaCotizada
    
    try:
        pieza = get_object_or_404(PiezaCotizada, id=pieza_id)
        cotizacion = pieza.cotizacion
        orden = cotizacion.orden
        
        # ⚠️ VALIDACIÓN: No eliminar si cotización aceptada
        if cotizacion.usuario_acepto:
            return JsonResponse({
                'success': False,
                'error': '❌ No puedes eliminar piezas de una cotización ya aceptada. ' +
                         'Puedes editarla y cambiar la cantidad a 0 si ya no la necesitas.'
            }, status=403)
        
        # Guardar info antes de eliminar
        componente_nombre = pieza.componente.nombre
        
        # Eliminar
        pieza.delete()
        
        # Registrar en historial
        registrar_historial(
            orden=orden,
            tipo_evento='cotizacion',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=f"🗑️ Pieza eliminada: {componente_nombre}",
            es_sistema=False
        )
        
        return JsonResponse({
            'success': True,
            'message': f'✅ Pieza eliminada: {componente_nombre}'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)


# ============================================================================
# VISTAS AJAX: GESTIÓN DE SEGUIMIENTOS DE PIEZAS
# ============================================================================

@login_required
@require_http_methods(["POST"])
def agregar_seguimiento_pieza(request, orden_id):
    """
    Agrega un nuevo seguimiento de pedido a proveedor.
    
    EXPLICACIÓN:
    Permite registrar un nuevo pedido a un proveedor con su información
    de tracking: proveedor, fecha de pedido, fecha estimada, etc.
    """
    from django.http import JsonResponse
    from .forms import SeguimientoPiezaForm
    from .models import SeguimientoPieza
    
    try:
        orden = get_object_or_404(OrdenServicio, id=orden_id)
        
        # Verificar que existe cotización
        if not hasattr(orden, 'cotizacion'):
            return JsonResponse({
                'success': False,
                'error': '❌ Esta orden no tiene cotización asociada'
            }, status=400)
        
        cotizacion = orden.cotizacion
        
        # Procesar formulario
        form = SeguimientoPiezaForm(request.POST, cotizacion=cotizacion)
        
        if form.is_valid():
            seguimiento = form.save(commit=False)
            seguimiento.cotizacion = cotizacion
            seguimiento.save()
            form.save_m2m()  # Guardar relaciones ManyToMany (piezas)
            
            # Registrar en historial
            registrar_historial(
                orden=orden,
                tipo_evento='cotizacion',
                usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
                comentario=f"📦 Seguimiento agregado - Proveedor: {seguimiento.proveedor}",
                es_sistema=False
            )
            
            return JsonResponse({
                'success': True,
                'message': f'✅ Seguimiento agregado: {seguimiento.proveedor}',
                'seguimiento_id': seguimiento.id,
                'seguimiento_html': _render_seguimiento_card(seguimiento)
            })
        else:
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = error_list[0]
            
            return JsonResponse({
                'success': False,
                'errors': errors
            }, status=400)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def editar_seguimiento_pieza(request, seguimiento_id):
    """
    Edita un seguimiento existente.
    
    EXPLICACIÓN:
    Permite actualizar información del seguimiento: cambiar fechas,
    actualizar estado, agregar notas, etc.
    """
    from django.http import JsonResponse
    from .forms import SeguimientoPiezaForm
    from .models import SeguimientoPieza
    
    try:
        seguimiento = get_object_or_404(SeguimientoPieza, id=seguimiento_id)
        estado_anterior = seguimiento.estado
        cotizacion = seguimiento.cotizacion
        orden = cotizacion.orden
        
        # Procesar formulario
        form = SeguimientoPiezaForm(request.POST, instance=seguimiento, cotizacion=cotizacion)
        
        if form.is_valid():
            seguimiento_actualizado = form.save()
            
            # Si cambió a "recibido", enviar notificación
            if estado_anterior != 'recibido' and seguimiento_actualizado.estado == 'recibido':
                _enviar_notificacion_pieza_recibida(orden, seguimiento_actualizado)
            
            # Registrar en historial
            registrar_historial(
                orden=orden,
                tipo_evento='cotizacion',
                usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
                comentario=f"✏️ Seguimiento actualizado - {seguimiento_actualizado.proveedor}",
                es_sistema=False
            )
            
            return JsonResponse({
                'success': True,
                'message': f'✅ Seguimiento actualizado: {seguimiento_actualizado.proveedor}',
                'seguimiento_html': _render_seguimiento_card(seguimiento_actualizado)
            })
        else:
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = error_list[0]
            
            return JsonResponse({
                'success': False,
                'errors': errors
            }, status=400)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def eliminar_seguimiento_pieza(request, seguimiento_id):
    """
    Elimina un seguimiento de pieza.
    
    NOTA:
    A diferencia de las piezas, los seguimientos SÍ se pueden eliminar
    incluso después de aceptar la cotización (son solo para tracking).
    """
    from django.http import JsonResponse
    from .models import SeguimientoPieza
    
    try:
        seguimiento = get_object_or_404(SeguimientoPieza, id=seguimiento_id)
        cotizacion = seguimiento.cotizacion
        orden = cotizacion.orden
        proveedor_nombre = seguimiento.proveedor
        
        # Eliminar
        seguimiento.delete()
        
        # Registrar en historial
        registrar_historial(
            orden=orden,
            tipo_evento='cotizacion',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=f"🗑️ Seguimiento eliminado - Proveedor: {proveedor_nombre}",
            es_sistema=False
        )
        
        return JsonResponse({
            'success': True,
            'message': f'✅ Seguimiento eliminado: {proveedor_nombre}'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def marcar_pieza_recibida(request, seguimiento_id):
    """
    Marca una pieza como recibida y envía notificación al técnico.
    
    EXPLICACIÓN:
    Función especial para marcar un seguimiento como recibido.
    Requiere la fecha de entrega real y automáticamente:
    1. Cambia el estado a "recibido"
    2. Registra la fecha actual como fecha_entrega_real
    3. Envía email al técnico asignado
    """
    from django.http import JsonResponse
    from django.utils import timezone
    from .models import SeguimientoPieza
    
    try:
        seguimiento = get_object_or_404(SeguimientoPieza, id=seguimiento_id)
        cotizacion = seguimiento.cotizacion
        orden = cotizacion.orden
        
        # Obtener fecha de entrega real del POST
        fecha_entrega_real_str = request.POST.get('fecha_entrega_real')
        
        if not fecha_entrega_real_str:
            return JsonResponse({
                'success': False,
                'error': '❌ Debes proporcionar la fecha de entrega real'
            }, status=400)
        
        # Convertir string a date
        from datetime import datetime
        try:
            fecha_entrega_real = datetime.strptime(fecha_entrega_real_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': '❌ Formato de fecha inválido (debe ser YYYY-MM-DD)'
            }, status=400)
        
        # Actualizar seguimiento
        seguimiento.estado = 'recibido'
        seguimiento.fecha_entrega_real = fecha_entrega_real
        seguimiento.save()
        
        # Enviar notificación por email
        _enviar_notificacion_pieza_recibida(orden, seguimiento)
        
        # Registrar en historial
        registrar_historial(
            orden=orden,
            tipo_evento='cotizacion',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=f"📬 Pieza recibida - {seguimiento.proveedor} - Notificación enviada a técnico",
            es_sistema=False
        )
        
        return JsonResponse({
            'success': True,
            'message': f'✅ Pieza marcada como recibida. Email enviado al técnico.',
            'seguimiento_html': _render_seguimiento_card(seguimiento)
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)


@login_required
def cambiar_estado_seguimiento(request, seguimiento_id):
    """
    Cambia el estado de un seguimiento de pieza de forma rápida.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista permite cambiar el estado del seguimiento sin necesidad de 
    editar todo el formulario. Es útil para actualizaciones rápidas del progreso.
    
    FLUJO TÍPICO:
    pedido → confirmado → transito → retrasado → recibido
    
    ESTADOS VÁLIDOS:
    - pedido: Pedido realizado al proveedor
    - confirmado: Proveedor confirmó el pedido
    - transito: Paquete en camino
    - retrasado: Hay retraso en la entrega
    - recibido: Pieza recibida (usar marcar_pieza_recibida en su lugar)
    
    RETORNA:
    JSON con el HTML actualizado del card para reemplazarlo dinámicamente
    """
    from django.http import JsonResponse
    from .models import SeguimientoPieza
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    try:
        seguimiento = get_object_or_404(SeguimientoPieza, id=seguimiento_id)
        cotizacion = seguimiento.cotizacion
        orden = cotizacion.orden
        
        # Obtener empleado actual
        try:
            empleado_actual = request.user.empleado
        except AttributeError:
            return JsonResponse({
                'success': False,
                'error': '❌ Usuario no asociado a un empleado'
            }, status=403)
        
        # Obtener nuevo estado
        nuevo_estado = request.POST.get('nuevo_estado')
        
        # Validar estado
        estados_validos = ['pedido', 'confirmado', 'transito', 'retrasado', 'recibido']
        if nuevo_estado not in estados_validos:
            return JsonResponse({
                'success': False,
                'error': f'❌ Estado inválido: {nuevo_estado}'
            }, status=400)
        
        # Guardar estado anterior para historial
        estado_anterior = seguimiento.get_estado_display()
        
        # Actualizar estado
        seguimiento.estado = nuevo_estado
        seguimiento.save()
        
        # Obtener nombre del nuevo estado
        estado_nuevo_display = seguimiento.get_estado_display()
        
        # Registrar en historial
        registrar_historial(
            orden=orden,
            tipo_evento='cotizacion',
            usuario=empleado_actual,
            comentario=f"📦 Estado de seguimiento actualizado: {estado_anterior} → {estado_nuevo_display} ({seguimiento.proveedor})",
            es_sistema=False
        )
        
        # Si cambió a "recibido", enviar notificación
        if nuevo_estado == 'recibido' and not seguimiento.fecha_entrega_real:
            from django.utils import timezone
            seguimiento.fecha_entrega_real = timezone.now().date()
            seguimiento.save()
            _enviar_notificacion_pieza_recibida(orden, seguimiento)
        
        return JsonResponse({
            'success': True,
            'message': f'✅ Estado actualizado a: {estado_nuevo_display}',
            'card_html': _render_seguimiento_card(seguimiento)
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)


# ============================================================================
# FUNCIONES HELPER: RENDER HTML Y NOTIFICACIONES
# ============================================================================

def _render_pieza_row(pieza, cotizacion):
    """
    Renderiza una fila de la tabla de piezas como HTML.
    
    EXPLICACIÓN:
    Esta función genera el HTML de una fila de pieza para insertarla
    dinámicamente en la tabla después de agregar/editar via AJAX.
    
    NOTA: Idealmente esto debería usar un template parcial, pero por
    simplicidad lo generamos aquí directamente.
    """
    puede_eliminar = 'false' if cotizacion.usuario_acepto else 'true'
    
    html = f'''
    <tr data-pieza-id="{pieza.id}">
        <td>
            <span class="badge bg-primary">{pieza.orden_prioridad}</span>
        </td>
        <td>
            <strong>{pieza.componente.nombre}</strong><br>
            <small class="text-muted">{pieza.componente.get_tipo_equipo_display()}</small>
            {f'<br><small>{pieza.descripcion_adicional}</small>' if pieza.descripcion_adicional else ''}
        </td>
        <td class="text-center">{pieza.cantidad}</td>
        <td class="text-end">${pieza.costo_unitario:.2f}</td>
        <td class="text-end"><strong>${pieza.costo_total:.2f}</strong></td>
        <td class="text-center">
            {'<span class="badge bg-success">Sí</span>' if pieza.es_necesaria else '<span class="badge bg-info">Opcional</span>'}
        </td>
        <td class="text-center">
            {'<span class="badge bg-warning text-dark">Técnico</span>' if pieza.sugerida_por_tecnico else ''}
        </td>
        <td class="text-center">
            <button type="button" class="btn btn-sm btn-outline-primary me-1" 
                    onclick="editarPieza({pieza.id})" title="Editar">
                📝
            </button>
            {'<button type="button" class="btn btn-sm btn-outline-danger" onclick="eliminarPieza(' + str(pieza.id) + ')" title="Eliminar">🗑️</button>' if not cotizacion.usuario_acepto else '<span class="text-muted" title="No se puede eliminar (cotización aceptada)">🔒</span>'}
        </td>
    </tr>
    '''
    
    return html.strip()


def _render_seguimiento_card(seguimiento):
    """
    Renderiza una card de seguimiento como HTML.
    
    EXPLICACIÓN:
    Genera el HTML de una card de seguimiento para insertarla
    dinámicamente después de agregar/editar via AJAX.
    """
    from django.utils import timezone
    
    # Calcular si hay retraso
    retraso_dias = 0
    hay_retraso = False
    if seguimiento.estado != 'recibido' and seguimiento.fecha_entrega_estimada:
        hoy = timezone.now().date()
        if hoy > seguimiento.fecha_entrega_estimada:
            retraso_dias = (hoy - seguimiento.fecha_entrega_estimada).days
            hay_retraso = True
    
    # Definir estilos según estado (ACTUALIZADOS según ESTADO_PIEZA_CHOICES)
    estado_badges = {
        'pedido': 'bg-primary',
        'confirmado': 'bg-info',
        'transito': 'bg-warning text-dark',
        'retrasado': 'bg-danger',
        'recibido': 'bg-success',
    }
    
    estado_nombres = {
        'pedido': '📋 Pedido Realizado',
        'confirmado': '✅ Confirmado',
        'transito': '🚚 En Tránsito',
        'retrasado': '⚠️ Retrasado',
        'recibido': '📬 Recibido',
    }
    
    border_class = ''
    if seguimiento.estado == 'recibido':
        border_class = 'border-success'
    elif hay_retraso or seguimiento.estado == 'retrasado':
        border_class = 'border-danger'
    
    html = f'''
    <div class="card seguimiento-card {border_class}" data-seguimiento-id="{seguimiento.id}">
        <div class="card-body">
            <h6 class="card-title">
                🏪 {seguimiento.proveedor}
                <span class="badge {estado_badges.get(seguimiento.estado, 'bg-secondary')} float-end">
                    {estado_nombres.get(seguimiento.estado, seguimiento.estado)}
                </span>
            </h6>
            
            <p class="card-text">
                <small><strong>Piezas:</strong> {seguimiento.descripcion_piezas}</small><br>
                {f'<small><strong>Pedido:</strong> {seguimiento.numero_pedido}</small><br>' if seguimiento.numero_pedido else ''}
                <small><strong>Fecha Pedido:</strong> {seguimiento.fecha_pedido.strftime('%d/%m/%Y')}</small><br>
                <small><strong>Entrega Estimada:</strong> {seguimiento.fecha_entrega_estimada.strftime('%d/%m/%Y')}</small><br>
                {f'<small><strong>Entrega Real:</strong> {seguimiento.fecha_entrega_real.strftime("%d/%m/%Y")}</small><br>' if seguimiento.fecha_entrega_real else ''}
            </p>
            
            <!-- NUEVO: Piezas Vinculadas -->
            {'<div class="mt-2 p-2" style="background-color: rgba(13, 110, 253, 0.05); border-left: 3px solid #0d6efd; border-radius: 4px;"><small class="text-primary fw-bold"><i class="bi bi-box-seam"></i> Piezas Vinculadas:</small><ul class="list-unstyled mb-0 mt-1">' + ''.join([f'<li class="small text-muted"><i class="bi bi-check2"></i> {pieza.componente.nombre} × {pieza.cantidad}</li>' for pieza in seguimiento.piezas.all()]) + '</ul></div>' if seguimiento.piezas.exists() else ''}
            
            {f'<div class="alert alert-danger alert-sm mb-2"><strong>⚠️ RETRASO:</strong> {retraso_dias} días</div>' if hay_retraso else ''}
            
            {f'<p class="card-text"><small class="text-muted"><strong>Notas:</strong> {seguimiento.notas_seguimiento}</small></p>' if seguimiento.notas_seguimiento else ''}
            
            <div class="mt-3">
                <!-- Fila 1: Cambio rápido de estado -->
                {f'''
                <div class="btn-group btn-group-sm w-100 mb-2" role="group">
                    {f'<button type="button" class="btn btn-info" onclick="cambiarEstadoSeguimiento({seguimiento.id}, \'confirmado\')" title="Confirmar pedido">✅ Confirmar</button>' if seguimiento.estado == 'pedido' else ''}
                    {f'<button type="button" class="btn btn-warning" onclick="cambiarEstadoSeguimiento({seguimiento.id}, \'transito\')" title="Marcar en tránsito">� En Tránsito</button>' if seguimiento.estado in ['pedido', 'confirmado'] else ''}
                    {f'<button type="button" class="btn btn-danger" onclick="cambiarEstadoSeguimiento({seguimiento.id}, \'retrasado\')" title="Marcar como retrasado">⚠️ Retrasado</button>' if seguimiento.estado in ['pedido', 'confirmado', 'transito'] else ''}
                    <button type="button" class="btn btn-success" onclick="marcarRecibido({seguimiento.id})" title="Marcar como recibido">📬 Recibido</button>
                </div>
                ''' if seguimiento.estado != 'recibido' else ''}
                
                <!-- Fila 2: Editar y Eliminar -->
                <div class="btn-group btn-group-sm w-100" role="group">
                    <button type="button" class="btn btn-outline-primary" onclick="editarSeguimiento({seguimiento.id})" title="Editar">
                        📝 Editar
                    </button>
                    <button type="button" class="btn btn-outline-danger" onclick="eliminarSeguimiento({seguimiento.id})" title="Eliminar">
                        🗑️ Eliminar
                    </button>
                </div>
            </div>
        </div>
    </div>
    '''
    
    return html.strip()


def _enviar_notificacion_pieza_recibida(orden, seguimiento):
    """
    Envía email al técnico notificando que una pieza fue recibida.
    
    EXPLICACIÓN:
    Esta función se ejecuta automáticamente cuando se marca un seguimiento
    como "recibido". Envía un email al técnico asignado para que sepa
    que ya puede continuar con la reparación.
    
    CONTENIDO DEL EMAIL:
    - Número de orden
    - Cliente
    - Proveedor de la pieza
    - Descripción de las piezas recibidas
    - Fecha de recepción
    """
    from django.core.mail import send_mail
    from django.conf import settings
    
    try:
        # Verificar que hay técnico asignado
        if not orden.tecnico_asignado or not orden.tecnico_asignado.correo:
            print(f"⚠️ No se envió email: Orden #{orden.numero_orden} no tiene técnico con email")
            return
        
        # Construir email
        asunto = f'📬 Pieza Recibida - Orden #{orden.numero_orden}'
        
        mensaje = f'''
Hola {orden.tecnico_asignado.usuario.first_name},

Te informamos que ha llegado una pieza para la orden que tienes asignada:

📋 INFORMACIÓN DE LA ORDEN:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Orden: #{orden.numero_orden}
• Cliente: {orden.cliente.nombre}
• Equipo: {orden.tipo_equipo} - {orden.marca}

📦 INFORMACIÓN DE LA PIEZA:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Proveedor: {seguimiento.proveedor}
• Piezas: {seguimiento.descripcion_piezas}
• Fecha de recepción: {seguimiento.fecha_entrega_real.strftime('%d/%m/%Y')}
{f'• Número de pedido: {seguimiento.numero_pedido}' if seguimiento.numero_pedido else ''}

Ya puedes recoger la pieza en almacén y continuar con la reparación.

---
Sistema de Servicio Técnico
Este es un mensaje automático, por favor no responder.
        '''
        
        # Enviar email
        send_mail(
            subject=asunto,
            message=mensaje,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[orden.tecnico_asignado.correo],
            fail_silently=False,
        )
        
        print(f"✅ Email enviado a {orden.tecnico_asignado.correo} - Pieza recibida Orden #{orden.numero_orden}")
    
    except Exception as e:
        print(f"❌ Error al enviar email de notificación: {str(e)}")
        # No levantamos la excepción para no afectar el flujo principal


# ============================================================================
# VISTAS AJAX PARA VENTA MOSTRADOR - FASE 3
# ============================================================================

@login_required
@require_http_methods(["POST"])
def crear_venta_mostrador(request, orden_id):
    """
    Crea una nueva venta mostrador asociada a una orden.
    
    ACTUALIZACIÓN (Octubre 2025): Sistema refactorizado
    Ya no valida tipo_servicio porque venta_mostrador es un complemento
    opcional de cualquier orden.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista maneja el formulario modal para crear una venta mostrador.
    Responde con JSON para actualizar la interfaz sin recargar la página (AJAX).
    
    FLUJO:
    1. Obtiene la orden (cualquier tipo)
    2. Verifica que NO tenga venta mostrador existente
    3. Valida el formulario recibido
    4. Crea la venta mostrador asociada a la orden
    5. Registra en historial
    6. Devuelve JSON con el resultado
    
    Args:
        request: HttpRequest con datos POST del formulario
        orden_id: ID de la orden a la que se asocia la venta
    
    Returns:
        JsonResponse con success=True/False y datos de la venta
    """
    from django.http import JsonResponse
    from .forms import VentaMostradorForm
    from .models import VentaMostrador
    
    try:
        # Obtener la orden (CUALQUIER tipo)
        orden = get_object_or_404(OrdenServicio, id=orden_id)
        
        # Verificar que NO tenga venta mostrador existente
        if hasattr(orden, 'venta_mostrador'):
            return JsonResponse({
                'success': False,
                'error': '❌ Esta orden ya tiene una venta mostrador registrada'
            }, status=400)
        
        # Procesar formulario
        form = VentaMostradorForm(request.POST)
        
        if form.is_valid():
            venta = form.save(commit=False)
            venta.orden = orden
            venta.save()
            
            # Registrar en historial
            empleado_actual = request.user.empleado if hasattr(request.user, 'empleado') else None
            registrar_historial(
                orden=orden,
                tipo_evento='actualizacion',
                usuario=empleado_actual,
                comentario=f"✅ Venta Mostrador creada: {venta.folio_venta} | Paquete: {venta.get_paquete_display()} | Total: ${venta.total_venta}",
                es_sistema=False
            )
            
            return JsonResponse({
                'success': True,
                'message': f'✅ Venta Mostrador creada: {venta.folio_venta}',
                'folio_venta': venta.folio_venta,
                'total_venta': float(venta.total_venta),
                'paquete': venta.get_paquete_display(),
                'es_complemento': orden.tipo_servicio == 'diagnostico',  # Info contextual
                'redirect_url': f'/servicio-tecnico/ordenes/{orden_id}/'  # Redirigir para refrescar
            })
        else:
            # Devolver errores del formulario
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = error_list[0]  # Primer error de cada campo
            
            return JsonResponse({
                'success': False,
                'errors': errors
            }, status=400)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def agregar_pieza_venta_mostrador(request, orden_id):
    """
    Agrega una nueva pieza a una venta mostrador existente.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista maneja el formulario modal para agregar piezas individuales
    a una venta mostrador. Por ejemplo: RAM adicional, cables, accesorios.
    Responde con JSON para actualizar la interfaz sin recargar (AJAX).
    
    FLUJO:
    1. Obtiene la orden y verifica que tenga venta mostrador
    2. Valida el formulario de pieza recibido
    3. Asocia la pieza a la venta mostrador
    4. Actualiza el total de la venta automáticamente (property)
    5. Registra en historial
    6. Devuelve JSON con la fila HTML de la nueva pieza
    
    Args:
        request: HttpRequest con datos POST del formulario
        orden_id: ID de la orden que tiene la venta mostrador
    
    Returns:
        JsonResponse con success=True/False y HTML de la pieza
    """
    from django.http import JsonResponse
    from .forms import PiezaVentaMostradorForm
    from .models import PiezaVentaMostrador, VentaMostrador
    
    try:
        orden = get_object_or_404(OrdenServicio, id=orden_id)
        
        # Verificar que existe venta mostrador
        if not hasattr(orden, 'venta_mostrador'):
            return JsonResponse({
                'success': False,
                'error': '❌ Esta orden no tiene venta mostrador asociada'
            }, status=400)
        
        venta_mostrador = orden.venta_mostrador
        
        # Procesar formulario
        form = PiezaVentaMostradorForm(request.POST)
        
        if form.is_valid():
            pieza = form.save(commit=False)
            pieza.venta_mostrador = venta_mostrador
            pieza.save()
            
            # Registrar en historial
            registrar_historial(
                orden=orden,
                tipo_evento='actualizacion',
                usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
                comentario=f"✅ Pieza agregada a venta mostrador: {pieza.descripcion_pieza} (x{pieza.cantidad}) - ${pieza.subtotal}",
                es_sistema=False
            )
            
            return JsonResponse({
                'success': True,
                'message': f'✅ Pieza agregada: {pieza.descripcion_pieza}',
                'pieza_id': pieza.id,
                'descripcion': pieza.descripcion_pieza,
                'cantidad': pieza.cantidad,
                'precio_unitario': float(pieza.precio_unitario),
                'subtotal': float(pieza.subtotal),
                'total_venta_actualizado': float(venta_mostrador.total_venta),
                'redirect_url': f'/servicio-tecnico/ordenes/{orden_id}/'  # Redirigir para refrescar
            })
        else:
            # Devolver errores del formulario
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = error_list[0]  # Primer error de cada campo
            
            return JsonResponse({
                'success': False,
                'errors': errors
            }, status=400)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def editar_pieza_venta_mostrador(request, pieza_id):
    """
    Edita una pieza de venta mostrador existente.
    
    EXPLICACIÓN:
    Permite modificar cantidad, precio unitario, descripción de una pieza.
    Actualiza automáticamente el total de la venta.
    
    Args:
        request: HttpRequest con datos POST del formulario
        pieza_id: ID de la pieza a editar
    
    Returns:
        JsonResponse con success=True/False y datos actualizados
    """
    from django.http import JsonResponse
    from .forms import PiezaVentaMostradorForm
    from .models import PiezaVentaMostrador
    
    try:
        pieza = get_object_or_404(PiezaVentaMostrador, id=pieza_id)
        venta_mostrador = pieza.venta_mostrador
        orden = venta_mostrador.orden
        
        # Procesar formulario de edición
        form = PiezaVentaMostradorForm(request.POST, instance=pieza)
        
        if form.is_valid():
            pieza_actualizada = form.save()
            
            # Registrar en historial
            registrar_historial(
                orden=orden,
                tipo_evento='actualizacion',
                usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
                comentario=f"✏️ Pieza modificada: {pieza_actualizada.descripcion_pieza} - ${pieza_actualizada.subtotal}",
                es_sistema=False
            )
            
            return JsonResponse({
                'success': True,
                'message': f'✅ Pieza actualizada: {pieza_actualizada.descripcion_pieza}',
                'pieza_id': pieza_actualizada.id,
                'descripcion': pieza_actualizada.descripcion_pieza,
                'cantidad': pieza_actualizada.cantidad,
                'precio_unitario': float(pieza_actualizada.precio_unitario),
                'subtotal': float(pieza_actualizada.subtotal),
                'total_venta_actualizado': float(venta_mostrador.total_venta),
                'redirect_url': f'/servicio-tecnico/ordenes/{orden.id}/'
            })
        else:
            # Devolver errores del formulario
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = error_list[0]
            
            return JsonResponse({
                'success': False,
                'errors': errors
            }, status=400)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def eliminar_pieza_venta_mostrador(request, pieza_id):
    """
    Elimina una pieza de venta mostrador.
    
    EXPLICACIÓN:
    Elimina una pieza vendida y actualiza el total de la venta.
    Registra la acción en el historial.
    
    Args:
        request: HttpRequest
        pieza_id: ID de la pieza a eliminar
    
    Returns:
        JsonResponse con success=True/False
    """
    from django.http import JsonResponse
    from .models import PiezaVentaMostrador
    
    try:
        pieza = get_object_or_404(PiezaVentaMostrador, id=pieza_id)
        venta_mostrador = pieza.venta_mostrador
        orden = venta_mostrador.orden
        
        # Guardar info antes de eliminar
        descripcion = pieza.descripcion_pieza
        subtotal = pieza.subtotal
        
        # Eliminar pieza
        pieza.delete()
        
        # Registrar en historial
        registrar_historial(
            orden=orden,
            tipo_evento='actualizacion',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=f"🗑️ Pieza eliminada de venta mostrador: {descripcion} (${subtotal})",
            es_sistema=False
        )
        
        # Recalcular total (se hace automáticamente por el property total_venta)
        return JsonResponse({
            'success': True,
            'message': f'✅ Pieza eliminada: {descripcion}',
            'total_venta_actualizado': float(venta_mostrador.total_venta),
            'redirect_url': f'/servicio-tecnico/ordenes/{orden.id}/'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)


# ⛔ VISTA ELIMINADA: convertir_venta_a_diagnostico()
# 


# ============================================================================
# RHITSO - SISTEMA DE SEGUIMIENTO ESPECIALIZADO
# ============================================================================

@login_required
def gestion_rhitso(request, orden_id):
    """
    Vista principal del módulo RHITSO - Panel de gestión completo.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista es el centro de control para órdenes que requieren reparación
    externa especializada (RHITSO). Muestra toda la información relevante:
    - Información del equipo y diagnóstico SIC
    - Estado actual RHITSO y timeline completo
    - Incidencias registradas y su seguimiento
    - Galería de imágenes específica RHITSO
    - Formularios para gestionar el proceso
    
    FLUJO DE LA VISTA:
    1. Obtiene la orden y valida que sea candidato RHITSO
    2. Prepara información del equipo y diagnóstico
    3. Obtiene estado RHITSO actual y calcula métricas
    4. Consulta historial de seguimientos e incidencias
    5. Filtra galería de imágenes RHITSO
    6. Prepara formularios para acciones
    7. Renderiza template con todo el contexto
    
    Args:
        request: HttpRequest object
        orden_id: ID de la orden de servicio
    
    Returns:
        HttpResponse con el template renderizado o redirect si hay error
    """
    # =======================================================================
    # PASO 1: OBTENER ORDEN Y VALIDAR
    # =======================================================================
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    
    # Validar que la orden es candidato RHITSO
    # EXPLICACIÓN: es_candidato_rhitso es un campo booleano que indica si
    # la orden requiere reparación externa especializada
    if not orden.es_candidato_rhitso:
        messages.error(
            request,
            '❌ Esta orden no está marcada como candidato RHITSO. '
            'Primero debe completar el diagnóstico inicial.'
        )
        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.id)
    
    # =======================================================================
    # PASO 2: OBTENER INFORMACIÓN DEL EQUIPO
    # =======================================================================
    # EXPLICACIÓN: detalle_equipo es una relación OneToOne que contiene
    # toda la información técnica del equipo (marca, modelo, serie, etc.)
    detalle_equipo = orden.detalle_equipo
    
    # Preparar diccionario con información del equipo
    # EXPLICACIÓN: Organizamos la información en un diccionario para
    # facilitar su uso en el template. Incluye datos de la orden y del equipo.
    equipo_info = {
        # Información básica del equipo
        'marca': detalle_equipo.marca if detalle_equipo else 'No especificada',
        'modelo': detalle_equipo.modelo if detalle_equipo else 'No especificado',
        'numero_serie': detalle_equipo.numero_serie if detalle_equipo else 'No especificado',
        
        # Información de la orden
        'sucursal': orden.sucursal.nombre if orden.sucursal else 'No especificada',
        'fecha_ingreso': orden.fecha_ingreso,
        'estado_orden': orden.get_estado_display(),
        
        # Orden del cliente y accesorios
        'orden_cliente': detalle_equipo.orden_cliente if (detalle_equipo and detalle_equipo.orden_cliente) else 'No especificada',
        'numero_serie_cargador': detalle_equipo.numero_serie_cargador if (detalle_equipo and detalle_equipo.numero_serie_cargador) else 'No incluye',
    }
    
    # =======================================================================
    # PASO 3: OBTENER ESTADO RHITSO ACTUAL Y CALCULAR MÉTRICAS
    # =======================================================================
    estado_rhitso_info = None
    
    if orden.estado_rhitso:
        try:
            # Buscar el estado en la tabla EstadoRHITSO para obtener detalles
            # EXPLICACIÓN: EstadoRHITSO contiene información adicional como
            # el color para mostrar en la UI y el responsable (owner)
            estado_obj = EstadoRHITSO.objects.get(estado=orden.estado_rhitso)
            
            # Calcular días en RHITSO usando property del modelo
            # EXPLICACIÓN: dias_en_rhitso es una property que calcula
            # automáticamente los días transcurridos desde el envío
            dias_en_rhitso = orden.dias_en_rhitso
            
            # Obtener configuración para alertas (días máximos permitidos)
            # EXPLICACIÓN: ConfiguracionRHITSO almacena parámetros del sistema
            # como días máximos antes de alertar
            config = ConfiguracionRHITSO.objects.first()
            dias_alerta = config.dias_maximos_rhitso if config else 7
            
            # Determinar si hay alerta por exceso de tiempo
            tiene_alerta = dias_en_rhitso > dias_alerta if dias_en_rhitso else False
            
            estado_rhitso_info = {
                'estado': estado_obj.estado,
                'estado_display': estado_obj.descripcion or estado_obj.estado,
                'color': estado_obj.color,
                'owner': estado_obj.owner,
                'orden': estado_obj.orden,
                'dias': dias_en_rhitso,
                'tiene_alerta': tiene_alerta,
                'dias_alerta': dias_alerta,
            }
        except EstadoRHITSO.DoesNotExist:
            # Si el estado no existe en el catálogo, usar valores por defecto
            estado_rhitso_info = {
                'estado': orden.estado_rhitso,
                'estado_display': orden.estado_rhitso,
                'color': 'secondary',
                'owner': 'SIC',
                'orden': 1,
                'dias': orden.dias_en_rhitso,
                'tiene_alerta': False,
                'dias_alerta': 7,
            }
    
    # =======================================================================
    # PASO 4: OBTENER DIAGNÓSTICO SIC
    # =======================================================================
    # EXPLICACIÓN: El diagnóstico SIC es el diagnóstico inicial realizado
    # por el técnico de SIC antes de enviar el equipo a RHITSO
    diagnostico_info = {
        'diagnostico_sic': detalle_equipo.diagnostico_sic if detalle_equipo else '',
        'motivo_rhitso': orden.get_motivo_rhitso_display() if orden.motivo_rhitso else 'No especificado',
        'motivo_rhitso_code': orden.motivo_rhitso,
        'descripcion_rhitso': orden.descripcion_rhitso or '',
        'complejidad': orden.get_complejidad_estimada_display() if orden.complejidad_estimada else 'No especificada',
        'complejidad_code': orden.complejidad_estimada,
        'tecnico': orden.tecnico_diagnostico,
        'fecha_diagnostico': orden.fecha_diagnostico_sic,
    }
    
    # =======================================================================
    # PASO 5: OBTENER HISTORIAL RHITSO
    # =======================================================================
    # EXPLICACIÓN: Obtenemos dos tipos de registros históricos:
    # 1. Seguimientos automáticos (cambios detectados por signals del sistema)
    # 2. Seguimientos manuales (cambios registrados por usuarios mediante formulario)
    
    # Seguimientos automáticos del sistema (es_cambio_automatico=True)
    # EXPLICACIÓN: Estos son cambios que el sistema detectó automáticamente,
    # como cuando se guarda una orden y cambia el estado_rhitso por programación
    seguimientos_sistema = orden.seguimientos_rhitso.filter(
        es_cambio_automatico=True
    ).select_related(
        'estado',
        'usuario_actualizacion'
    ).order_by('-fecha_actualizacion')
    
    # Seguimientos manuales (es_cambio_automatico=False)
    # EXPLICACIÓN: Estos son cambios que un usuario registró manualmente usando
    # el formulario "Actualizar Estado RHITSO" con observaciones
    seguimientos_manuales = orden.seguimientos_rhitso.filter(
        es_cambio_automatico=False
    ).select_related(
        'estado',
        'usuario_actualizacion'
    ).order_by('-fecha_actualizacion')
    
    # Obtener último seguimiento RHITSO (de cualquier tipo)
    # EXPLICACIÓN: Para mostrar las observaciones del estado actual,
    # priorizamos los seguimientos manuales porque tienen más contexto
    ultimo_seguimiento_rhitso = (
        seguimientos_manuales.first() or 
        seguimientos_sistema.first()
    )
    
    # =======================================================================
    # PASO 6: OBTENER INCIDENCIAS Y CALCULAR ESTADÍSTICAS
    # =======================================================================
    # EXPLICACIÓN: Las incidencias son problemas o eventos negativos que
    # ocurren durante el proceso RHITSO (retrasos, daños, costos extra)
    
    # Obtener todas las incidencias de la orden
    incidencias = orden.incidencias_rhitso.select_related(
        'tipo_incidencia',
        'usuario_registro',
        'resuelto_por'
    ).order_by('-fecha_ocurrencia')
    
    # Calcular estadísticas de incidencias
    # EXPLICACIÓN: Usamos aggregate y filter para contar incidencias
    # por diferentes criterios sin hacer múltiples queries
    incidencias_stats = {
        'total': incidencias.count(),
        'abiertas': incidencias.filter(estado__in=['ABIERTA', 'EN_REVISION']).count(),
        'criticas_abiertas': incidencias.filter(
            estado__in=['ABIERTA', 'EN_REVISION'],
            impacto_cliente='ALTO'
        ).count(),
        'resueltas': incidencias.filter(estado__in=['RESUELTA', 'CERRADA']).count(),
        'costo_total_incidencias': sum(
            i.costo_adicional or 0 for i in incidencias
        ),
    }
    
    # =======================================================================
    # PASO 7: OBTENER GALERÍA RHITSO
    # =======================================================================
    # EXPLICACIÓN: Preparamos las imágenes de la orden organizadas por tipo
    # para mostrarlas en tabs en la galería RHITSO
    
    # Obtener todas las imágenes de la orden
    imagenes_rhitso = orden.imagenes.select_related('subido_por').order_by('-fecha_subida')
    
    # Organizar imágenes por tipo (igual que en detalle_orden)
    # EXPLICACIÓN: Creamos un diccionario con las imágenes separadas por tipo
    # para poder mostrarlas en tabs específicos en el template
    imagenes_por_tipo_rhitso = {
        'ingreso': orden.imagenes.filter(tipo='ingreso').order_by('-fecha_subida'),
        'diagnostico': orden.imagenes.filter(tipo='diagnostico').order_by('-fecha_subida'),
        'reparacion': orden.imagenes.filter(tipo='reparacion').order_by('-fecha_subida'),
        'egreso': orden.imagenes.filter(tipo='egreso').order_by('-fecha_subida'),
        'autorizacion': orden.imagenes.filter(tipo='autorizacion').order_by('-fecha_subida'),
    }
    
    # =======================================================================
    # PASO 8: PREPARAR FORMULARIOS
    # =======================================================================
    # EXPLICACIÓN: Instanciamos los 4 formularios que permiten gestionar
    # el proceso RHITSO. Estos formularios fueron creados en la Fase 3
    
    # Formulario para cambiar estado RHITSO
    # EXPLICACIÓN: Este formulario carga dinámicamente los estados
    # disponibles desde la base de datos
    form_estado = ActualizarEstadoRHITSOForm()
    
    # Formulario para registrar incidencias
    # EXPLICACIÓN: ModelForm que valida y crea objetos IncidenciaRHITSO
    form_incidencia = RegistrarIncidenciaRHITSOForm()
    
    # Formulario para resolver incidencias
    # EXPLICACIÓN: Form simple para documentar la resolución de una incidencia
    form_resolver_incidencia = ResolverIncidenciaRHITSOForm()
    
    # Formulario para editar diagnóstico SIC
    # EXPLICACIÓN: Formulario multi-modelo que actualiza DetalleEquipo y OrdenServicio
    # Pre-llenamos con valores actuales usando 'initial'
    # LÓGICA MEJORADA: Si no hay tecnico_diagnostico asignado, usa el técnico actual de la orden
    # Esto permite flexibilidad (se puede cambiar) pero automatiza el proceso inicial
    tecnico_inicial = orden.tecnico_diagnostico or orden.tecnico_asignado_actual
    
    form_diagnostico = EditarDiagnosticoSICForm(initial={
        'diagnostico_sic': detalle_equipo.diagnostico_sic if detalle_equipo else '',
        'motivo_rhitso': orden.motivo_rhitso,
        'descripcion_rhitso': orden.descripcion_rhitso,
        'complejidad_estimada': orden.complejidad_estimada,
        'tecnico_diagnostico': tecnico_inicial,  # Auto-inicializa con fallback
    })
    
    # =======================================================================
    # PASO 8.5: PREPARAR DATOS PARA MODAL DE ENVÍO DE CORREO RHITSO
    # =======================================================================
    # EXPLICACIÓN: Preparamos los datos necesarios para el modal de envío
    # de correo a RHITSO, incluyendo destinatarios, empleados y archivos
    
    # Importar settings para obtener destinatarios RHITSO
    from django.conf import settings
    
    # A) DESTINATARIOS PRINCIPALES - Desde settings.py
    # EXPLICACIÓN: Estos son los correos fijos de RHITSO configurados en .env
    destinatarios_rhitso = settings.RHITSO_EMAIL_RECIPIENTS
    
    # B) EMPLEADOS PARA "CON COPIA A" - Filtrados por área
    # EXPLICACIÓN: Filtramos empleados activos de las áreas especificadas
    # y que tengan email configurado. La búsqueda es case-insensitive.
    from django.db.models import Q
    
    # Crear filtros case-insensitive para las áreas
    areas_filtro = Q()
    for area in settings.RHITSO_AREAS_COPIA:
        areas_filtro |= Q(area__iexact=area)
    
    # Obtener empleados que cumplan los criterios
    empleados_copia = Empleado.objects.filter(
        areas_filtro,
        activo=True,
        email__isnull=False
    ).exclude(
        email=''
    ).order_by('area', 'nombre_completo')
    
    # C) DATOS DEL EQUIPO PARA EL CORREO
    # EXPLICACIÓN: Preparamos la información que se mostrará en el correo
    # Usamos la orden del cliente (OOW-5544, FL-1234) en lugar de la orden interna
    orden_cliente = detalle_equipo.orden_cliente if (detalle_equipo and detalle_equipo.orden_cliente) else 'No especificada'
    
    datos_correo = {
        'orden': orden_cliente,  # Orden del cliente (OOW-5544, FL-1234, etc.)
        'orden_interna': orden.numero_orden_interno,  # Orden interna para referencia (ORD-2025-0010)
        'serie': detalle_equipo.numero_serie if detalle_equipo else 'No especificado',
        'modelo': f"{detalle_equipo.marca} {detalle_equipo.modelo}" if detalle_equipo else 'No especificado',
        'motivo_rhitso': orden.descripcion_rhitso or 'No especificado',
        'cargador': 'SIN CARGADOR',  # Por defecto
    }
    
    # Verificar si tiene cargador y su serie
    if detalle_equipo and detalle_equipo.tiene_cargador:
        if detalle_equipo.numero_serie_cargador:
            datos_correo['cargador'] = detalle_equipo.numero_serie_cargador
        else:
            datos_correo['cargador'] = 'CON CARGADOR (sin número de serie)'
    
    # D) ARCHIVOS QUE SE ADJUNTARÁN
    # EXPLICACIÓN: Contamos las imágenes que se adjuntarán al correo
    
    # 1. Imágenes para el PDF (tipo 'autorizacion')
    imagenes_autorizacion = orden.imagenes.filter(tipo='autorizacion').count()
    
    # 2. Imágenes para adjuntar (tipo 'ingreso')
    imagenes_ingreso = orden.imagenes.filter(tipo='ingreso')
    cantidad_imagenes_ingreso = imagenes_ingreso.count()
    
    archivos_adjuntos = {
        'tiene_imagenes_autorizacion': imagenes_autorizacion > 0,
        'cantidad_autorizacion': imagenes_autorizacion,
        'cantidad_imagenes_ingreso': cantidad_imagenes_ingreso,
        'imagenes_ingreso': imagenes_ingreso,  # Para previsualización
    }
    
    # E) PREVISUALIZACIÓN DEL CORREO
    # EXPLICACIÓN: Generamos el asunto y cuerpo del correo que se enviará
    asunto_correo = f"ENVIO DE EQUIPO RHITSO: {orden_cliente} - {datos_correo['modelo']}"
    
    cuerpo_correo = f"""Buen día Team Rhitso:

Envío los datos del equipo para su revisión.

Orden: {datos_correo['orden']}
Serie: {datos_correo['serie']}
Modelo: {datos_correo['modelo']}
Motivo RHITSO: {datos_correo['motivo_rhitso']}
Cargador: {datos_correo['cargador']}

Adjunto encontrarán:
- PDF con datos del equipo e imágenes de autorización
- {cantidad_imagenes_ingreso} imagen(es) de ingreso del equipo

Saludos cordiales."""
    
    previsualizacion_correo = {
        'asunto': asunto_correo,
        'cuerpo': cuerpo_correo,
    }
    
    # =======================================================================
    # PASO 9: PREPARAR CONTEXTO COMPLETO
    # =======================================================================
    # EXPLICACIÓN: El contexto es un diccionario que contiene todos los
    # datos que necesita el template para renderizar la página
    context = {
        # Orden y equipo
        'orden': orden,
        'detalle_equipo': detalle_equipo,
        'equipo_info': equipo_info,
        
        # Estado RHITSO
        'estado_rhitso_info': estado_rhitso_info,
        
        # Diagnóstico
        'diagnostico_info': diagnostico_info,
        
        # Historial
        'seguimientos_sistema': seguimientos_sistema,
        'seguimientos_manuales': seguimientos_manuales,
        'ultimo_seguimiento_rhitso': ultimo_seguimiento_rhitso,
        
        # Incidencias
        'incidencias': incidencias,
        'incidencias_stats': incidencias_stats,
        
        # Galería
        'imagenes_rhitso': imagenes_rhitso,
        'imagenes_por_tipo_rhitso': imagenes_por_tipo_rhitso,
        
        # Formularios
        'form_estado': form_estado,
        'form_incidencia': form_incidencia,
        'form_resolver_incidencia': form_resolver_incidencia,
        'form_diagnostico': form_diagnostico,
        
        # DATOS PARA MODAL DE ENVÍO DE CORREO RHITSO (FASE 10)
        'destinatarios_rhitso': destinatarios_rhitso,
        'empleados_copia': empleados_copia,
        'datos_correo': datos_correo,
        'archivos_adjuntos': archivos_adjuntos,
        'previsualizacion_correo': previsualizacion_correo,
    }
    
    # =======================================================================
    # PASO 10: RENDERIZAR TEMPLATE
    # =======================================================================
    # EXPLICACIÓN: render() toma el template y el contexto, y genera
    # el HTML final que se envía al navegador del usuario
    return render(request, 'servicio_tecnico/rhitso/gestion_rhitso.html', context)

# ============================================================================
# VISTAS AJAX PARA GESTIÓN RHITSO - FASE 5
# ============================================================================

@login_required
@require_http_methods(["POST"])
def actualizar_estado_rhitso(request, orden_id):
    """
    Vista AJAX para actualizar el estado RHITSO de una orden.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Esta vista procesa el formulario de cambio de estado RHITSO.
    Cuando el usuario selecciona un nuevo estado y lo guarda:
    1. Valida que el formulario esté correcto
    2. Actualiza el estado_rhitso en la orden
    3. Crea un registro automático en SeguimientoRHITSO (vía signal)
    4. Actualiza fechas especiales (envío/recepción)
    5. Retorna respuesta JSON con éxito o errores
    
    ¿Por qué JsonResponse?
    Porque el template usa JavaScript para enviar el formulario de forma
    asíncrona (AJAX). En lugar de recargar toda la página, solo actualizamos
    la sección del estado.
    
    FLUJO COMPLETO:
    1. Usuario llena formulario en template
    2. JavaScript envía formulario por AJAX
    3. Esta vista procesa y valida datos
    4. Signal crea SeguimientoRHITSO automáticamente
    5. Vista retorna JSON: {success: true/false, mensaje, data}
    6. JavaScript actualiza la UI sin recargar página
    
    Args:
        request: HttpRequest con datos POST del formulario
        orden_id: ID de la orden a actualizar
    
    Returns:
        JsonResponse con resultado de la operación
    """
    try:
        # Paso 1: Obtener orden y validar que sea candidato RHITSO
        orden = get_object_or_404(OrdenServicio, pk=orden_id)
        
        if not orden.es_candidato_rhitso:
            return JsonResponse({
                'success': False,
                'mensaje': '❌ Esta orden no es candidato RHITSO'
            }, status=400)
        
        # Paso 2: Guardar estado anterior para el registro
        # EXPLICACIÓN: Necesitamos saber cuál era el estado previo para
        # el historial. Lo guardamos ANTES de hacer cualquier cambio.
        estado_anterior = orden.estado_rhitso
        
        # Paso 3: Validar formulario con datos POST
        form = ActualizarEstadoRHITSOForm(request.POST)
        
        if not form.is_valid():
            # Si el formulario tiene errores, retornamos los mensajes
            # EXPLICACIÓN: form.errors es un diccionario con los errores
            # de cada campo. Lo convertimos a lista para mostrarlo en UI.
            errores = []
            for field, errors in form.errors.items():
                for error in errors:
                    errores.append(f"{field}: {error}")
            
            return JsonResponse({
                'success': False,
                'mensaje': '❌ Formulario inválido',
                'errores': errores
            }, status=400)
        
        # Paso 4: Obtener datos validados del formulario
        nuevo_estado = form.cleaned_data['estado_rhitso']
        observaciones = form.cleaned_data['observaciones']
        notificar_cliente = form.cleaned_data.get('notificar_cliente', False)
        fecha_envio = form.cleaned_data.get('fecha_envio_rhitso')
        fecha_recepcion = form.cleaned_data.get('fecha_recepcion_rhitso')
        
        # Paso 5: Actualizar estado en la orden
        orden.estado_rhitso = nuevo_estado
        
        # Paso 6: Actualizar fechas especiales
        # EXPLICACIÓN: Se actualizan las fechas según lo ingresado en el formulario
        # o automáticamente según el estado seleccionado
        
        # Si el usuario proporcionó una fecha de envío, usarla
        if fecha_envio:
            orden.fecha_envio_rhitso = fecha_envio
        # Si no, detectar automáticamente si es un estado de envío
        elif 'ENVIADO' in nuevo_estado.upper() or 'ACEPTA ENVIO' in nuevo_estado.upper():
            if not orden.fecha_envio_rhitso:  # Solo si no tiene fecha previa
                orden.fecha_envio_rhitso = timezone.now()
        
        # Si el usuario proporcionó una fecha de recepción, usarla
        if fecha_recepcion:
            orden.fecha_recepcion_rhitso = fecha_recepcion
        # Si no, detectar automáticamente si es un estado de retorno
        elif 'RETORNADO' in nuevo_estado.upper() or 'EQUIPO RETORNADO' in nuevo_estado.upper():
            if not orden.fecha_recepcion_rhitso:  # Solo si no tiene fecha previa
                orden.fecha_recepcion_rhitso = timezone.now()
        
        # Paso 7: Guardar cambios en la base de datos
        orden.save()
        
        # IMPORTANTE: El signal post_save de OrdenServicio se ejecuta aquí
        # automáticamente y crea el registro en SeguimientoRHITSO con:
        # - El estado nuevo y anterior
        # - Las observaciones
        # - El usuario que hizo el cambio
        # - El tiempo que estuvo en el estado anterior
        
        # Paso 8: Crear registro manual en SeguimientoRHITSO con observaciones
        # EXPLICACIÓN: Aunque el signal crea un registro automático, aquí
        # creamos uno adicional con las observaciones del usuario y su información
        try:
            estado_obj = EstadoRHITSO.objects.get(estado=nuevo_estado, activo=True)
            
            # Calcular tiempo en estado anterior
            ultimo_seguimiento = orden.seguimientos_rhitso.exclude(
                estado__estado=nuevo_estado
            ).order_by('-fecha_actualizacion').first()
            
            tiempo_anterior_dias = None
            if ultimo_seguimiento:
                tiempo_delta = timezone.now() - ultimo_seguimiento.fecha_actualizacion
                # EXPLICACIÓN: Convertir timedelta a días (número entero)
                # timedelta.days devuelve solo la parte de días completos
                # timedelta.total_seconds() / 86400 da el total de días con decimales
                tiempo_anterior_dias = tiempo_delta.days
            
            SeguimientoRHITSO.objects.create(
                orden=orden,
                estado=estado_obj,
                estado_anterior=estado_anterior if estado_anterior else 'Sin estado previo',
                observaciones=observaciones,
                usuario_actualizacion=request.user.empleado if hasattr(request.user, 'empleado') else None,
                tiempo_en_estado_anterior=tiempo_anterior_dias,
                notificado_cliente=notificar_cliente,
                es_cambio_automatico=False  # 🔧 MARCADO COMO MANUAL (usuario hizo el cambio)
            )
        except EstadoRHITSO.DoesNotExist:
            pass  # El signal ya creó el registro básico
        
        # Paso 9: Registrar en historial general de la orden
        registrar_historial(
            orden=orden,
            tipo_evento='estado',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=f"🔄 Estado RHITSO actualizado: {estado_anterior or 'Sin estado'} → {nuevo_estado}. "
                      f"Observaciones: {observaciones}",
            es_sistema=False
        )
        
        # Paso 10: Preparar datos para respuesta JSON
        # EXPLICACIÓN: Enviamos información actualizada para que JavaScript
        # pueda actualizar la UI sin recargar la página
        dias_en_rhitso = orden.dias_en_rhitso if orden.dias_en_rhitso is not None else 0
        
        return JsonResponse({
            'success': True,
            'mensaje': f'✅ Estado RHITSO actualizado correctamente a: {nuevo_estado}',
            'data': {
                'nuevo_estado': nuevo_estado,
                'estado_anterior': estado_anterior,
                'observaciones': observaciones,
                'fecha_actualizacion': timezone.now().strftime('%d/%m/%Y %H:%M'),
                'usuario': request.user.empleado.nombre_completo if hasattr(request.user, 'empleado') else request.user.username,
                'dias_en_rhitso': dias_en_rhitso,
                'notificado_cliente': notificar_cliente
            }
        })
        
    except Exception as e:
        # Manejar cualquier error inesperado
        return JsonResponse({
            'success': False,
            'mensaje': f'❌ Error al actualizar estado: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def registrar_incidencia(request, orden_id):
    """
    Vista AJAX para registrar una nueva incidencia RHITSO.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Las incidencias son problemas que ocurren durante el proceso RHITSO.
    Esta vista:
    1. Valida el formulario de incidencia
    2. Crea el registro en la base de datos
    3. Si es incidencia CRÍTICA, crea alerta automática (vía signal)
    4. Registra en historial de la orden
    5. Retorna datos de la incidencia creada en JSON
    
    ¿Qué es una incidencia?
    Ejemplos: daño adicional, retraso injustificado, pieza incorrecta,
    mala comunicación, costo no autorizado, etc.
    
    ¿Por qué es importante?
    Permite documentar todos los problemas y hacer seguimiento de:
    - Qué salió mal
    - Cuándo ocurrió
    - Impacto al cliente
    - Costo adicional
    - Cómo se resolvió
    
    Args:
        request: HttpRequest con datos POST del formulario
        orden_id: ID de la orden donde ocurrió la incidencia
    
    Returns:
        JsonResponse con resultado y datos de la incidencia creada
    """
    try:
        # Paso 1: Obtener orden y validar
        orden = get_object_or_404(OrdenServicio, pk=orden_id)
        
        if not orden.es_candidato_rhitso:
            return JsonResponse({
                'success': False,
                'mensaje': '❌ Esta orden no es candidato RHITSO'
            }, status=400)
        
        # Paso 2: Validar formulario
        form = RegistrarIncidenciaRHITSOForm(request.POST)
        
        if not form.is_valid():
            errores = []
            for field, errors in form.errors.items():
                for error in errors:
                    errores.append(f"{field}: {error}")
            
            return JsonResponse({
                'success': False,
                'mensaje': '❌ Formulario inválido',
                'errores': errores
            }, status=400)
        
        # Paso 3: Crear incidencia sin guardar aún
        # EXPLICACIÓN: commit=False crea el objeto pero no lo guarda en BD.
        # Esto nos permite asignar campos adicionales antes de guardar.
        incidencia = form.save(commit=False)
        incidencia.orden = orden
        
        # Asignar usuario que registra la incidencia
        if hasattr(request.user, 'empleado'):
            incidencia.usuario_registro = request.user.empleado
        else:
            # Si no tiene empleado asociado, no podemos crear la incidencia
            return JsonResponse({
                'success': False,
                'mensaje': '❌ Usuario no tiene empleado asociado'
            }, status=400)
        
        # Paso 4: Guardar incidencia
        incidencia.save()
        
        # IMPORTANTE: Si la incidencia es CRÍTICA, el signal post_save de
        # IncidenciaRHITSO automáticamente creará un evento en HistorialOrden
        # con emoji ⚠️ y marcará como alerta de alta prioridad
        
        # Paso 5: Registrar en historial general (para todas las incidencias)
        tipo_incidencia_str = incidencia.tipo_incidencia.nombre if incidencia.tipo_incidencia else 'Sin tipo'
        
        registrar_historial(
            orden=orden,
            tipo_evento='comentario',
            usuario=incidencia.usuario_registro,
            comentario=f"⚠️ Nueva incidencia registrada: {incidencia.titulo} | "
                      f"Tipo: {tipo_incidencia_str} | "
                      f"Prioridad: {incidencia.get_prioridad_display()} | "
                      f"Impacto: {incidencia.get_impacto_cliente_display()}",
            es_sistema=False
        )
        
        # Paso 6: Preparar datos de la incidencia para respuesta JSON
        # EXPLICACIÓN: Enviamos todos los datos necesarios para que JavaScript
        # pueda agregar la nueva incidencia a la lista sin recargar la página
        return JsonResponse({
            'success': True,
            'mensaje': f'✅ Incidencia "{incidencia.titulo}" registrada correctamente',
            'data': {
                'id': incidencia.id,
                'titulo': incidencia.titulo,
                'tipo_incidencia': tipo_incidencia_str,
                'descripcion': incidencia.descripcion_detallada,
                'estado': incidencia.get_estado_display(),
                'prioridad': incidencia.get_prioridad_display(),
                'impacto_cliente': incidencia.get_impacto_cliente_display(),
                'costo_adicional': float(incidencia.costo_adicional) if incidencia.costo_adicional else 0.00,
                'fecha_ocurrencia': incidencia.fecha_ocurrencia.strftime('%d/%m/%Y %H:%M'),
                'usuario_registro': incidencia.usuario_registro.nombre_completo,
                'es_critica': incidencia.tipo_incidencia.gravedad == 'CRITICA' if incidencia.tipo_incidencia else False
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'mensaje': f'❌ Error al registrar incidencia: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def resolver_incidencia(request, incidencia_id):
    """
    Vista AJAX para resolver/cerrar una incidencia existente.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Cuando una incidencia se resuelve, necesitamos documentar:
    - Qué acción se tomó para resolverla
    - Quién la resolvió
    - Cuándo se resolvió
    - Si hubo algún costo adicional final
    
    Esta vista usa el método marcar_como_resuelta() del modelo IncidenciaRHITSO,
    que automáticamente:
    - Cambia el estado a 'RESUELTA'
    - Guarda la fecha/hora de resolución
    - Asigna el usuario que resolvió
    - Guarda la descripción de la acción tomada
    
    ¿Por qué es importante resolver incidencias?
    - Cierra el ciclo de seguimiento
    - Documenta la solución para futuras referencias
    - Permite análisis de cuántas incidencias se resuelven
    - Mejora la relación con RHITSO (si ellos son responsables)
    
    Args:
        request: HttpRequest con datos POST del formulario
        incidencia_id: ID de la incidencia a resolver
    
    Returns:
        JsonResponse con resultado de la operación
    """
    try:
        # Paso 1: Obtener incidencia
        incidencia = get_object_or_404(IncidenciaRHITSO, pk=incidencia_id)
        
        # Paso 2: Verificar que no esté ya resuelta
        if incidencia.esta_resuelta:
            return JsonResponse({
                'success': False,
                'mensaje': '⚠️ Esta incidencia ya está resuelta o cerrada'
            }, status=400)
        
        # Paso 3: Validar formulario
        form = ResolverIncidenciaRHITSOForm(request.POST)
        
        if not form.is_valid():
            errores = []
            for field, errors in form.errors.items():
                for error in errors:
                    errores.append(f"{field}: {error}")
            
            return JsonResponse({
                'success': False,
                'mensaje': '❌ Formulario inválido',
                'errores': errores
            }, status=400)
        
        # Paso 4: Obtener datos del formulario
        accion_tomada = form.cleaned_data['accion_tomada']
        costo_adicional_final = form.cleaned_data.get('costo_adicional_final')
        
        # Paso 5: Actualizar costo si se proporcionó uno nuevo
        if costo_adicional_final is not None:
            incidencia.costo_adicional = costo_adicional_final
        
        # Paso 6: Marcar incidencia como resuelta usando método del modelo
        # EXPLICACIÓN: Este método hace todo el trabajo:
        # - Cambia estado a 'RESUELTA'
        # - Guarda fecha_resolucion = ahora
        # - Asigna resuelto_por = usuario actual
        # - Guarda accion_tomada
        # - Llama a save()
        if hasattr(request.user, 'empleado'):
            incidencia.marcar_como_resuelta(
                usuario=request.user.empleado,
                accion_tomada=accion_tomada
            )
        else:
            # Si no hay empleado, actualizar manualmente
            incidencia.estado = 'RESUELTA'
            incidencia.fecha_resolucion = timezone.now()
            incidencia.accion_tomada = accion_tomada
            incidencia.save()
        
        # Paso 7: Registrar en historial de la orden
        registrar_historial(
            orden=incidencia.orden,
            tipo_evento='comentario',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=f"✅ Incidencia resuelta: {incidencia.titulo} | "
                      f"Acción tomada: {accion_tomada[:100]}..." if len(accion_tomada) > 100 else accion_tomada,
            es_sistema=False
        )
        
        # Paso 8: Preparar respuesta JSON
        return JsonResponse({
            'success': True,
            'mensaje': f'✅ Incidencia "{incidencia.titulo}" resuelta correctamente',
            'data': {
                'id': incidencia.id,
                'titulo': incidencia.titulo,
                'estado': incidencia.get_estado_display(),
                'fecha_resolucion': incidencia.fecha_resolucion.strftime('%d/%m/%Y %H:%M'),
                'resuelto_por': incidencia.resuelto_por.nombre_completo if incidencia.resuelto_por else 'Sistema',
                'accion_tomada': incidencia.accion_tomada,
                'costo_final': float(incidencia.costo_adicional)
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'mensaje': f'❌ Error al resolver incidencia: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def editar_diagnostico_sic(request, orden_id):
    """
    Vista para editar el diagnóstico SIC y datos relacionados con RHITSO.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Esta vista es especial porque maneja campos de DOS modelos diferentes:
    1. DetalleEquipo → diagnostico_sic (el diagnóstico técnico)
    2. OrdenServicio → motivo_rhitso, descripcion_rhitso, complejidad_estimada, etc.
    
    ¿Cuándo se usa?
    Cuando el técnico de SIC hace el diagnóstico inicial y determina que
    el equipo necesita ir a RHITSO. Aquí documenta:
    - Qué problema tiene el equipo (diagnóstico técnico)
    - Por qué necesita ir a RHITSO (reballing, soldadura, etc.)
    - Qué tan complejo es el trabajo
    - Quién hizo el diagnóstico
    
    DIFERENCIA CON OTRAS VISTAS:
    Las otras 3 vistas retornan JsonResponse porque son AJAX.
    Esta vista puede:
    - Retornar JsonResponse si se llama por AJAX
    - Hacer redirect si se llama normalmente
    
    Args:
        request: HttpRequest con datos POST del formulario
        orden_id: ID de la orden a actualizar
    
    Returns:
        JsonResponse o redirect según cómo se llamó
    """
    try:
        # Paso 1: Obtener orden y detalle_equipo
        orden = get_object_or_404(OrdenServicio, pk=orden_id)
        detalle_equipo = orden.detalle_equipo
        
        if not detalle_equipo:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'mensaje': '❌ Esta orden no tiene detalle de equipo'
                }, status=400)
            else:
                messages.error(request, '❌ Esta orden no tiene detalle de equipo')
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.id)
        
        # Paso 2: Validar formulario
        form = EditarDiagnosticoSICForm(request.POST)
        
        if not form.is_valid():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                errores = []
                for field, errors in form.errors.items():
                    for error in errors:
                        errores.append(f"{field}: {error}")
                
                return JsonResponse({
                    'success': False,
                    'mensaje': '❌ Formulario inválido',
                    'errores': errores
                }, status=400)
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
                return redirect('servicio_tecnico:gestion_rhitso', orden_id=orden.id)
        
        # Paso 3: Obtener datos validados
        diagnostico_sic = form.cleaned_data['diagnostico_sic']
        motivo_rhitso = form.cleaned_data['motivo_rhitso']
        descripcion_rhitso = form.cleaned_data['descripcion_rhitso']
        complejidad_estimada = form.cleaned_data['complejidad_estimada']
        tecnico_diagnostico = form.cleaned_data['tecnico_diagnostico']
        
        # Paso 4: Actualizar DetalleEquipo
        # EXPLICACIÓN: El diagnóstico técnico va en DetalleEquipo porque
        # es información específica del equipo, no de la orden
        detalle_equipo.diagnostico_sic = diagnostico_sic
        detalle_equipo.save()
        
        # Paso 5: Actualizar OrdenServicio
        # EXPLICACIÓN: Los datos RHITSO van en OrdenServicio porque son
        # específicos del proceso de reparación externa de esta orden
        orden.motivo_rhitso = motivo_rhitso
        orden.descripcion_rhitso = descripcion_rhitso
        orden.complejidad_estimada = complejidad_estimada
        orden.tecnico_diagnostico = tecnico_diagnostico
        
        # Si no tiene fecha de diagnóstico, asignar ahora
        if not orden.fecha_diagnostico_sic:
            orden.fecha_diagnostico_sic = timezone.now()
        
        orden.save()
        
        # Paso 6: Registrar en historial
        registrar_historial(
            orden=orden,
            tipo_evento='actualizacion',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=f"📝 Diagnóstico SIC actualizado | "
                      f"Motivo RHITSO: {motivo_rhitso} | "
                      f"Complejidad: {complejidad_estimada} | "
                      f"Técnico: {tecnico_diagnostico.nombre_completo if tecnico_diagnostico else 'No asignado'}",
            es_sistema=False
        )
        
        # Paso 7: Retornar respuesta según tipo de petición
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Es petición AJAX → Retornar JSON
            return JsonResponse({
                'success': True,
                'mensaje': '✅ Diagnóstico SIC actualizado correctamente',
                'data': {
                    'diagnostico_sic': diagnostico_sic,
                    'motivo_rhitso': motivo_rhitso,
                    'descripcion_rhitso': descripcion_rhitso,
                    'complejidad_estimada': complejidad_estimada,
                    'complejidad_display': dict(form.fields['complejidad_estimada'].choices).get(complejidad_estimada, ''),
                    'tecnico_diagnostico': tecnico_diagnostico.nombre_completo if tecnico_diagnostico else 'No asignado',
                    'fecha_actualizacion': timezone.now().strftime('%d/%m/%Y %H:%M')
                }
            })
        else:
            # Es petición normal → Redirect con mensaje
            messages.success(request, '✅ Diagnóstico SIC actualizado correctamente')
            return redirect('servicio_tecnico:gestion_rhitso', orden_id=orden.id)
        
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'mensaje': f'❌ Error al actualizar diagnóstico: {str(e)}'
            }, status=500)
        else:
            messages.error(request, f'❌ Error al actualizar diagnóstico: {str(e)}')
            return redirect('servicio_tecnico:gestion_rhitso', orden_id=orden.id)


@login_required
@require_http_methods(["POST"])
def agregar_comentario_rhitso(request, orden_id):
    """
    Vista AJAX para agregar un comentario manual al historial RHITSO.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Los comentarios manuales permiten a los usuarios agregar notas,
    observaciones o actualizaciones al historial RHITSO sin cambiar
    el estado del proceso.
    
    Diferencia entre:
    - Seguimientos automáticos: Se crean automáticamente al cambiar estado
    - Comentarios manuales: Los crea el usuario cuando quiere documentar algo
    
    Ejemplos de comentarios útiles:
    - "Llamé a RHITSO para consultar estado, aún no tienen respuesta"
    - "Cliente preguntó por el equipo, le informé que está en proceso"
    - "Recibí cotización preliminar de RHITSO: $1,500 MXN"
    - "RHITSO confirmó que necesitan pieza adicional, llegará mañana"
    
    ¿Por qué es importante?
    - Documentación completa del proceso
    - Comunicación entre técnicos del mismo equipo
    - Referencia futura para casos similares
    - Transparencia con el cliente
    
    Args:
        request: HttpRequest con datos POST (comentario)
        orden_id: ID de la orden donde agregar el comentario
    
    Returns:
        JsonResponse con resultado de la operación
    """
    try:
        # Paso 1: Obtener orden y validar
        orden = get_object_or_404(OrdenServicio, pk=orden_id)
        
        if not orden.es_candidato_rhitso:
            return JsonResponse({
                'success': False,
                'mensaje': '❌ Esta orden no es candidato RHITSO'
            }, status=400)
        
        # Paso 2: Validar que haya comentario
        comentario = request.POST.get('comentario', '').strip()
        
        if not comentario:
            return JsonResponse({
                'success': False,
                'mensaje': '⚠️ El comentario no puede estar vacío'
            }, status=400)
        
        # Validar longitud mínima
        if len(comentario) < 10:
            return JsonResponse({
                'success': False,
                'mensaje': '⚠️ El comentario debe tener al menos 10 caracteres'
            }, status=400)
        
        # Validar longitud máxima (opcional, por seguridad)
        if len(comentario) > 1000:
            return JsonResponse({
                'success': False,
                'mensaje': '⚠️ El comentario no puede exceder 1000 caracteres'
            }, status=400)
        
        # Paso 3: Registrar comentario en historial
        # EXPLICACIÓN: Usamos la función registrar_historial que:
        # - Crea un objeto HistorialOrden
        # - Asigna tipo_evento='comentario'
        # - Guarda el usuario que lo creó
        # - Marca la fecha/hora actual automáticamente
        registrar_historial(
            orden=orden,
            tipo_evento='comentario',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=f"💬 {comentario}",  # Emoji para identificar comentarios manuales
            es_sistema=False
        )
        
        # Paso 4: Preparar datos para respuesta JSON
        # EXPLICACIÓN: Enviamos los datos del comentario creado para que
        # JavaScript pueda agregarlo a la lista sin recargar la página
        usuario_nombre = (
            request.user.empleado.nombre_completo 
            if hasattr(request.user, 'empleado') 
            else request.user.username
        )
        
        return JsonResponse({
            'success': True,
            'mensaje': '✅ Comentario agregado correctamente al historial RHITSO',
            'data': {
                'comentario': comentario,
                'usuario': usuario_nombre,
                'fecha': timezone.now().strftime('%d/%m/%Y %H:%M'),
                'tipo': 'comentario_manual'
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'mensaje': f'❌ Error al agregar comentario: {str(e)}'
        }, status=500)


# Esta vista manejaba la conversión de ventas mostrador a diagnóstico,
# creando una NUEVA orden cuando el servicio fallaba.
# 
# ELIMINADA EN: Octubre 2025 (Sistema Refactorizado)
# MOTIVO: Venta mostrador ahora es un complemento opcional que puede
#         coexistir con cotización en la MISMA orden. No se requiere
#         duplicar órdenes para agregar diagnóstico.
#
# BENEFICIOS:
# - Menos duplicación de datos
# - Seguimiento más simple (una sola orden)
# - Código más limpio (~107 líneas eliminadas)
# - Mayor flexibilidad en el flujo de trabajo


# ============================================================================
# VISTA: ENVIAR CORREO Y FORMATO RHITSO - FASE 10
# ============================================================================

@login_required
@require_http_methods(["POST"])
def enviar_correo_rhitso(request, orden_id):
    """
    Vista para enviar correo electrónico a RHITSO con información del equipo.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Esta vista procesa el formulario del modal de envío de correo a RHITSO.
    Realiza las siguientes acciones:
    
    1. Valida que la orden sea candidato RHITSO
    2. Recopila destinatarios principales y empleados en copia
    3. Prepara los datos del equipo para el correo
    4. Genera PDF con información del equipo e imágenes de autorización
    5. Comprime imágenes de ingreso para adjuntar
    6. Envía el correo con todos los adjuntos
    7. Registra el envío en el historial de la orden
    8. Limpia archivos temporales
    
    FLUJO DEL CORREO:
    - Para: Destinatarios RHITSO (configurados en .env)
    - CC: Empleados seleccionados (CALIDAD, FRONTDESK, COMPRAS)
    - Asunto: 🔧 Envío de Equipo RHITSO - Orden #[NUMERO]
    - Adjuntos:
      * PDF con datos del equipo e imágenes de autorización
      * Imágenes de ingreso (comprimidas)
    
    Args:
        request: HttpRequest object con datos POST del formulario
        orden_id: ID de la orden de servicio
    
    Returns:
        JsonResponse con resultado del envío o redirect en caso de error
    """
    import os
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone
    from django.conf import settings
    from .utils.pdf_generator import PDFGeneratorRhitso
    from .utils.image_compressor import ImageCompressor
    
    try:
        # =======================================================================
        # PASO 1: OBTENER Y VALIDAR LA ORDEN
        # =======================================================================
        orden = get_object_or_404(OrdenServicio, pk=orden_id)
        
        if not orden.es_candidato_rhitso:
            return JsonResponse({
                'success': False,
                'mensaje': '❌ Esta orden no está marcada como candidato RHITSO.'
            }, status=400)
        
        # =======================================================================
        # PASO 2: OBTENER DESTINATARIOS DEL FORMULARIO
        # =======================================================================
        destinatarios_principales = request.POST.getlist('destinatarios_principales')
        copia_empleados = request.POST.getlist('copia_empleados')
        
        # Validar que haya al menos un destinatario
        if not destinatarios_principales:
            return JsonResponse({
                'success': False,
                'mensaje': '❌ Debe seleccionar al menos un destinatario principal.'
            }, status=400)
        
        # =======================================================================
        # PASO 3: GENERAR PDF CON DATOS DEL EQUIPO E IMÁGENES DE AUTORIZACIÓN
        # =======================================================================
        print(f"📄 Generando PDF para Orden {orden.numero_orden_interno}...")
        
        # Obtener imágenes de autorización para incluir en el PDF
        imagenes_autorizacion = list(orden.imagenes.filter(tipo='autorizacion'))
        
        # Generar el PDF usando el generador existente
        generator = PDFGeneratorRhitso(orden, imagenes_autorizacion)
        resultado_pdf = generator.generar_pdf()
        
        if not resultado_pdf.get('success'):
            error_msg = resultado_pdf.get('error', 'Error desconocido')
            print(f"❌ Error generando PDF: {error_msg}")
            return JsonResponse({
                'success': False,
                'mensaje': f"❌ Error al generar PDF: {error_msg}"
            }, status=500)
        
        pdf_path = resultado_pdf['ruta']
        print(f"✅ PDF generado: {pdf_path}")
        
        # =======================================================================
        # PASO 4: COMPRIMIR Y ANALIZAR IMÁGENES DE INGRESO PARA ADJUNTAR
        # =======================================================================
        print(f"🖼️ Procesando imágenes de ingreso...")
        
        imagenes_ingreso = list(orden.imagenes.filter(tipo='ingreso'))
        compressor = ImageCompressor()
        
        # Preparar lista de imágenes para calcular tamaño
        imagenes_para_correo = []
        for imagen in imagenes_ingreso:
            imagenes_para_correo.append({
                'ruta': imagen.imagen.path,
                'nombre': os.path.basename(imagen.imagen.path)
            })
        
        # Calcular tamaño total del correo con análisis completo
        print(f"📊 Analizando tamaño del correo...")
        analisis = compressor.calcular_tamaño_correo(
            ruta_pdf=pdf_path,
            imagenes=imagenes_para_correo,
            contenido_html=""  # El HTML es pequeño, no afecta mucho
        )
        
        if not analisis['success']:
            return JsonResponse({
                'success': False,
                'mensaje': f"❌ Error al analizar tamaño del correo: {analisis.get('error', 'Error desconocido')}"
            }, status=500)
        
        # Mostrar información detallada del análisis
        print(f"\n📦 ANÁLISIS DEL CORREO:")
        print(f"  📄 PDF: {analisis['detalles']['pdf']['tamaño_mb']} MB")
        print(f"  🖼️ Imágenes:")
        print(f"     • Original: {analisis['detalles']['imagenes']['tamaño_original_mb']} MB")
        print(f"     • Comprimido: {analisis['detalles']['imagenes']['tamaño_comprimido_mb']} MB")
        print(f"     • Reducción: {analisis['detalles']['imagenes']['reduccion_total_mb']} MB")
        print(f"  📊 TOTAL: {analisis['tamaño_total_mb']} MB / 25 MB")
        
        # Verificar si excede el límite
        if analisis['excede_limite']:
            print(f"\n⚠️ ADVERTENCIA: El correo excede el límite de Gmail!")
            for recomendacion in analisis['recomendaciones']:
                print(f"  {recomendacion}")
            
            return JsonResponse({
                'success': False,
                'mensaje': f"❌ El correo excede el límite de Gmail ({analisis['tamaño_total_mb']} MB). "
                          f"Reduce el número de imágenes o usa un servicio de transferencia de archivos.",
                'data': {
                    'tamaño_total_mb': analisis['tamaño_total_mb'],
                    'limite_mb': 25,
                    'imagenes_validas': analisis['imagenes_validas_count'],
                    'imagenes_excluidas': analisis['imagenes_excluidas_count']
                }
            }, status=400)
        
        # Mostrar imágenes excluidas si las hay
        if analisis['imagenes_excluidas_count'] > 0:
            print(f"\n⚠️ {analisis['imagenes_excluidas_count']} imagen(es) excluidas:")
            for img_excluida in analisis['imagenes_excluidas']:
                print(f"  • {img_excluida['nombre']}: {img_excluida['razon']}")
        
        # Mostrar recomendaciones
        print(f"\n💡 RECOMENDACIONES:")
        for recomendacion in analisis['recomendaciones']:
            print(f"  {recomendacion}")
        
        # Usar las imágenes comprimidas
        imagenes_paths = [img['ruta_comprimida'] for img in analisis['imagenes_validas']]
        print(f"\n✅ {len(imagenes_paths)} imágenes listas para adjuntar")
        
        # =======================================================================
        # PASO 5: PREPARAR CONTENIDO HTML DEL CORREO
        # =======================================================================
        print(f"📧 Preparando contenido del correo...")
        
        # Obtener fecha y hora actual
        ahora = timezone.now()
        fecha_actual = ahora.strftime('%d/%m/%Y')
        hora_actual = ahora.strftime('%H:%M')
        
        # Preparar contexto para la plantilla HTML
        context = {
            'orden': orden,
            'fecha_actual': fecha_actual,
            'hora_actual': hora_actual,
            # Datos de contacto (puedes personalizar estos valores)
            'agente_nombre': 'Equipo de Soporte Técnico',
            'agente_celular': '55-35-45-81-92',
            'agente_correo': settings.DEFAULT_FROM_EMAIL,
        }
        
        # Renderizar plantilla HTML
        html_content = render_to_string(
            'servicio_tecnico/emails/rhitso_envio.html',
            context
        )
        
        # =======================================================================
        # PASO 6: CREAR Y ENVIAR EL CORREO ELECTRÓNICO
        # =======================================================================
        print(f"✉️ Enviando correo electrónico...")
        
        # Determinar qué orden usar en el asunto (preferir orden del cliente)
        orden_para_asunto = orden.numero_orden_interno
        if orden.detalle_equipo and orden.detalle_equipo.orden_cliente:
            orden_para_asunto = orden.detalle_equipo.orden_cliente
        
        # Crear asunto del correo en mayúsculas
        asunto = f'🔧ENVIO DE EQUIPO RHITSO - {orden_para_asunto}'
        
        # Crear lista completa de destinatarios (principal + copias)
        todos_destinatarios = list(destinatarios_principales)
        if copia_empleados:
            todos_destinatarios.extend(copia_empleados)
        
        # Personalizar el remitente para RHITSO
        # Extraer solo el email del DEFAULT_FROM_EMAIL si tiene formato "Nombre <email>"
        from_email_base = settings.DEFAULT_FROM_EMAIL
        if '<' in from_email_base and '>' in from_email_base:
            # Extraer solo el email entre < >
            email_address = from_email_base.split('<')[1].split('>')[0]
        else:
            email_address = from_email_base
        
        # Crear remitente personalizado para RHITSO
        from_email_rhitso = f'RHITSO System <{email_address}>'
        
        # Crear mensaje de correo
        email = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=from_email_rhitso,  # Remitente personalizado para RHITSO
            to=destinatarios_principales,
            cc=copia_empleados if copia_empleados else None,
        )
        
        # Indicar que el contenido es HTML
        email.content_subtype = 'html'
        
        # Adjuntar el PDF
        if os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as pdf_file:
                email.attach(os.path.basename(pdf_path), pdf_file.read(), 'application/pdf')
            print(f"  📎 PDF adjuntado: {os.path.basename(pdf_path)}")
        
        # Adjuntar las imágenes comprimidas
        for imagen_path in imagenes_paths:
            if os.path.exists(imagen_path):
                filename = os.path.basename(imagen_path)
                with open(imagen_path, 'rb') as img_file:
                    email.attach(filename, img_file.read(), 'image/jpeg')
                print(f"  📎 Imagen adjuntada: {filename}")
        
        # Enviar el correo
        email.send()
        print(f"✅ Correo enviado exitosamente")
        
        # =======================================================================
        # PASO 7: REGISTRAR EN HISTORIAL
        # =======================================================================
        comentario = f"📧 Correo RHITSO enviado a: {', '.join(destinatarios_principales[:2])}"
        if len(destinatarios_principales) > 2:
            comentario += f" y {len(destinatarios_principales) - 2} más"
        if copia_empleados:
            comentario += f" (con {len(copia_empleados)} copia(s))"
        
        registrar_historial(
            orden=orden,
            tipo_evento='sistema',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=comentario,
            es_sistema=False
        )
        
        # =======================================================================
        # PASO 8: LIMPIAR ARCHIVOS TEMPORALES
        # =======================================================================
        print(f"🧹 Limpiando archivos temporales...")
        
        # Eliminar PDF temporal
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
                print(f"  🗑️ PDF eliminado: {pdf_path}")
            except Exception as e:
                print(f"  ⚠️ No se pudo eliminar PDF: {e}")
        
        # Eliminar imágenes comprimidas temporales
        for imagen_path in imagenes_paths:
            if 'compressed' in imagen_path and os.path.exists(imagen_path):
                try:
                    os.remove(imagen_path)
                    print(f"  🗑️ Imagen eliminada: {imagen_path}")
                except Exception as e:
                    print(f"  ⚠️ No se pudo eliminar imagen: {e}")
        
        # =======================================================================
        # PASO 9: RESPUESTA DE ÉXITO CON INFORMACIÓN DETALLADA
        # =======================================================================
        return JsonResponse({
            'success': True,
            'mensaje': f'✅ Correo enviado exitosamente a {len(destinatarios_principales)} destinatario(s)',
            'data': {
                'destinatarios': len(destinatarios_principales),
                'copias': len(copia_empleados),
                'pdf': {
                    'generado': True,
                    'tamaño_mb': analisis['detalles']['pdf']['tamaño_mb']
                },
                'imagenes': {
                    'adjuntas': len(imagenes_paths),
                    'excluidas': analisis['imagenes_excluidas_count'],
                    'tamaño_original_mb': analisis['detalles']['imagenes']['tamaño_original_mb'],
                    'tamaño_comprimido_mb': analisis['detalles']['imagenes']['tamaño_comprimido_mb'],
                    'reduccion_mb': analisis['detalles']['imagenes']['reduccion_total_mb']
                },
                'correo': {
                    'tamaño_total_mb': analisis['tamaño_total_mb'],
                    'limite_mb': 25,
                    'porcentaje_usado': round((analisis['tamaño_total_mb'] / 25) * 100, 1)
                }
            }
        })
        
    except Exception as e:
        # Registrar error en consola
        print(f"❌ Error al enviar correo RHITSO: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JsonResponse({
            'success': False,
            'mensaje': f'❌ Error al enviar el correo: {str(e)}'
        }, status=500)


# ============================================================================
# VISTA DE PRUEBA: GENERAR PDF RHITSO
# ============================================================================

@login_required
def generar_pdf_rhitso_prueba(request, orden_id):
    """
    Vista de prueba para generar el PDF RHITSO.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista es temporal para probar que el generador de PDF funciona correctamente.
    Una vez integrado al modal, esta vista se puede eliminar.
    
    ¿Qué hace?
    1. Busca la orden de servicio por ID
    2. Obtiene las imágenes de autorización (si existen)
    3. Genera el PDF usando PDFGeneratorRhitso
    4. Devuelve el PDF para descargar o muestra un error
    
    Args:
        request: Objeto HttpRequest de Django
        orden_id: ID de la orden de servicio
        
    Returns:
        - Si success=True: Descarga del PDF
        - Si success=False: Página con mensaje de error
    """
    try:
        # Importar el generador de PDF
        from .utils.pdf_generator import PDFGeneratorRhitso
        from django.http import FileResponse
        
        # Buscar la orden (lanza 404 si no existe)
        orden = get_object_or_404(OrdenServicio, id=orden_id)
        
        # Verificar que sea candidato RHITSO
        if not orden.es_candidato_rhitso:
            messages.warning(request, '⚠️ Esta orden no está marcada como candidato RHITSO.')
        
        # Obtener imágenes de autorización/pass (tipo específico)
        imagenes_autorizacion = ImagenOrden.objects.filter(
            orden=orden,
            tipo='autorizacion'
        ).order_by('-fecha_subida')
        
        # Crear instancia del generador
        generador = PDFGeneratorRhitso(
            orden=orden,
            imagenes_autorizacion=list(imagenes_autorizacion)
        )
        
        # Generar el PDF
        resultado = generador.generar_pdf()
        
        if resultado['success']:
            # Abrir el archivo PDF generado
            pdf_file = open(resultado['ruta'], 'rb')
            
            # Crear respuesta HTTP para descargar el archivo
            response = FileResponse(
                pdf_file,
                content_type='application/pdf'
            )
            
            # Configurar headers para descarga
            response['Content-Disposition'] = f'attachment; filename="{resultado["archivo"]}"'
            
            # Mensaje de éxito (se mostrará en la próxima página que visite el usuario)
            messages.success(
                request, 
                f'✅ PDF generado exitosamente: {resultado["archivo"]} '
                f'({resultado["size"] / 1024:.1f} KB)'
            )
            
            return response
        else:
            # Si hubo error al generar
            messages.error(
                request,
                f'❌ Error al generar el PDF: {resultado.get("error", "Error desconocido")}'
            )
            return redirect('servicio_tecnico:detalle_orden', orden_id=orden_id)
    
    except Exception as e:
        # Capturar cualquier otro error
        messages.error(
            request,
            f'❌ Error inesperado al generar PDF: {str(e)}'
        )
        
        # Log del error para debugging
        import traceback
        print("Error generando PDF RHITSO:")
        traceback.print_exc()
        
        return redirect('servicio_tecnico:lista_ordenes')


# ============================================================================
# DASHBOARD RHITSO - VISTA CONSOLIDADA DE CANDIDATOS
# ============================================================================

@login_required
def dashboard_rhitso(request):
    """
    Dashboard consolidado de todos los candidatos RHITSO.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Este dashboard replica la funcionalidad del sistema PHP, mostrando:
    - Estadísticas generales (total candidatos, enviados, con diagnóstico, incidencias)
    - Estadísticas por sucursal (Satelite, Drop, MIS)
    - 3 pestañas con tablas filtradas: Activos, Pendientes, Excluidos
    - Filtros dinámicos por estado RHITSO
    - Exportación a Excel
    
    ¿Por qué un dashboard separado?
    - Vista rápida de TODAS las órdenes RHITSO (no solo una)
    - Métricas agregadas para toma de decisiones
    - Identificación rápida de problemas y retrasos
    - Reportes y exportaciones
    
    Flujo de la vista:
    1. Consultar todas las órdenes candidatas a RHITSO
    2. Calcular estadísticas generales y por sucursal
    3. Preparar datos de cada orden (días hábiles, incidencias, etc.)
    4. Separar órdenes en 3 categorías (activos, pendientes, excluidos)
    5. Preparar datos para exportación Excel
    6. Renderizar template con contexto completo
    
    Args:
        request: HttpRequest object
    
    Returns:
        HttpResponse con el dashboard renderizado
    """
    # =======================================================================
    # PASO 1: CONSULTA OPTIMIZADA DE CANDIDATOS RHITSO
    # =======================================================================
    
    # EXPLICACIÓN: select_related() carga las relaciones en una sola consulta
    # Esto evita el "N+1 problem" (hacer una consulta por cada relación)
    candidatos_rhitso = OrdenServicio.objects.filter(
        es_candidato_rhitso=True
    ).select_related(
        'detalle_equipo',              # Información del equipo
        'sucursal',                    # Sucursal de la orden
        'tecnico_asignado_actual',     # Técnico asignado
        'responsable_seguimiento'      # Responsable del seguimiento
    ).prefetch_related(
        # EXPLICACIÓN: prefetch_related() hace una consulta separada optimizada
        # para relaciones many-to-many o reverse foreign keys
        Prefetch(
            'seguimientos_rhitso',
            queryset=SeguimientoRHITSO.objects.select_related('estado', 'usuario_actualizacion').order_by('-fecha_actualizacion'),
            to_attr='seguimientos_ordenados'
        ),
        Prefetch(
            'incidencias_rhitso',
            queryset=IncidenciaRHITSO.objects.filter(estado__in=['ABIERTA', 'EN_REVISION']),
            to_attr='incidencias_abiertas'
        ),
        Prefetch(
            'incidencias_rhitso',
            queryset=IncidenciaRHITSO.objects.filter(estado='RESUELTA'),
            to_attr='incidencias_resueltas_lista'
        ),
    ).order_by('-fecha_ingreso')
    
    # =======================================================================
    # PASO 2: CALCULAR ESTADÍSTICAS GENERALES
    # =======================================================================
    
    # EXPLICACIÓN: Count() es una función agregada que cuenta registros
    # Usamos Q() para condiciones complejas (OR, AND, NOT)
    total_candidatos = candidatos_rhitso.count()
    total_enviados = candidatos_rhitso.filter(fecha_envio_rhitso__isnull=False).count()
    total_con_diagnostico = candidatos_rhitso.exclude(detalle_equipo__diagnostico_sic='').count()
    
    # Contar incidencias abiertas (en todas las órdenes)
    total_incidencias_abiertas = IncidenciaRHITSO.objects.filter(
        orden__in=candidatos_rhitso,
        estado__in=['ABIERTA', 'EN_REVISION']
    ).count()
    
    # =======================================================================
    # PASO 3: CALCULAR ESTADÍSTICAS POR SUCURSAL
    # =======================================================================
    
    # EXPLICACIÓN: Contamos cuántas órdenes hay en cada sucursal
    # Estas son las 3 sucursales principales según el sistema PHP
    stats_sucursal = {
        'satelite': candidatos_rhitso.filter(sucursal__nombre__icontains='Satelite').count(),
        'drop': candidatos_rhitso.filter(sucursal__nombre__icontains='Drop').count(),
        'mis': candidatos_rhitso.filter(sucursal__nombre__icontains='MIS').count(),
    }
    
    # =======================================================================
    # PASO 4: PREPARAR DATOS DETALLADOS DE CADA ORDEN
    # =======================================================================
    
    # EXPLICACIÓN: Estados que indican órdenes "excluidas" del proceso activo
    estados_excluidos = ['CERRADO', 'USUARIO NO ACEPTA ENVIO A RHITSO']
    estados_pendientes = ['PENDIENTE DE CONFIRMAR ENVIO A RHITSO']
    
    # Listas para separar órdenes por categoría
    activos = []
    pendientes = []
    excluidos = []
    
    # Iterar sobre cada orden para preparar sus datos
    for orden in candidatos_rhitso:
        # ===================================================================
        # 4.1: INFORMACIÓN BÁSICA
        # ===================================================================
        detalle = orden.detalle_equipo
        
        # Estado RHITSO actual (campo de texto simple)
        estado_rhitso_nombre = orden.estado_rhitso if orden.estado_rhitso else 'Pendiente'
        estado_rhitso_display = estado_rhitso_nombre
        
        # Buscar owner del estado (si existe en catálogo)
        try:
            estado_obj = EstadoRHITSO.objects.get(estado=estado_rhitso_nombre)
            owner_actual = estado_obj.owner
        except EstadoRHITSO.DoesNotExist:
            owner_actual = ''
        
        # ===================================================================
        # 4.2: CALCULAR DÍAS HÁBILES
        # ===================================================================
        
        # Días hábiles en SIC (desde ingreso hasta hoy o hasta envío a RHITSO)
        if orden.fecha_envio_rhitso:
            # Si ya se envió a RHITSO, contar hasta esa fecha
            dias_habiles_sic = calcular_dias_habiles(
                orden.fecha_ingreso,
                orden.fecha_envio_rhitso
            )
        else:
            # Si no se ha enviado, contar hasta hoy
            dias_habiles_sic = calcular_dias_habiles(orden.fecha_ingreso)
        
        # Días hábiles en RHITSO (si aplica)
        dias_habiles_rhitso = 0
        if orden.fecha_envio_rhitso:
            if orden.fecha_recepcion_rhitso:
                # Ya regresó de RHITSO
                dias_habiles_rhitso = calcular_dias_habiles(
                    orden.fecha_envio_rhitso,
                    orden.fecha_recepcion_rhitso
                )
            else:
                # Todavía en RHITSO
                dias_habiles_rhitso = calcular_dias_habiles(
                    orden.fecha_envio_rhitso
                )
        
        # ===================================================================
        # 4.3: CALCULAR DÍAS SIN ACTUALIZACIÓN
        # ===================================================================
        
        # EXPLICACIÓN: Buscamos el último comentario de usuario (no del sistema)
        ultimo_seguimiento_usuario = None
        if hasattr(orden, 'seguimientos_ordenados') and orden.seguimientos_ordenados:
            # Buscar el último seguimiento que NO sea automático
            for seg in orden.seguimientos_ordenados:
                if not seg.es_cambio_automatico:
                    ultimo_seguimiento_usuario = seg
                    break
        
        if ultimo_seguimiento_usuario:
            dias_sin_actualizar = calcular_dias_en_estatus(
                ultimo_seguimiento_usuario.fecha_actualizacion
            )
            fecha_ultimo_comentario = ultimo_seguimiento_usuario.fecha_actualizacion
            ultimo_comentario = ultimo_seguimiento_usuario.observaciones
        else:
            # Si no hay seguimientos, contar desde fecha de ingreso
            dias_sin_actualizar = calcular_dias_en_estatus(orden.fecha_ingreso)
            fecha_ultimo_comentario = None
            ultimo_comentario = ''
        
        # ===================================================================
        # 4.4: CONTAR INCIDENCIAS
        # ===================================================================
        
        # EXPLICACIÓN: Usamos los prefetch que definimos arriba
        incidencias_abiertas_count = len(orden.incidencias_abiertas) if hasattr(orden, 'incidencias_abiertas') else 0
        incidencias_resueltas_count = len(orden.incidencias_resueltas_lista) if hasattr(orden, 'incidencias_resueltas_lista') else 0
        total_incidencias = incidencias_abiertas_count + incidencias_resueltas_count
        
        # ===================================================================
        # 4.5: DETERMINAR ESTADO DEL PROCESO
        # ===================================================================
        
        estado_proceso = obtener_estado_proceso_rhitso(orden)
        
        # ===================================================================
        # 4.6: DETERMINAR COLOR SEGÚN DÍAS EN RHITSO
        # ===================================================================
        
        color_badge_dias = obtener_color_por_dias_rhitso(dias_habiles_rhitso)
        
        # ===================================================================
        # 4.7: CONSTRUIR DICCIONARIO CON TODA LA INFORMACIÓN
        # ===================================================================
        
        orden_data = {
            # Información básica
            'id': orden.id,
            'numero_orden_interno': orden.numero_orden_interno,
            'fecha_ingreso': orden.fecha_ingreso,
            'estado_orden': orden.get_estado_display(),
            
            # Información del equipo
            'servicio': detalle.falla_principal if detalle else 'Sin observaciones',
            'numero_serie': detalle.numero_serie if detalle else 'N/A',
            'marca': detalle.marca if detalle else 'N/A',
            'modelo': detalle.modelo if detalle else 'N/A',
            'orden_cliente': detalle.orden_cliente if detalle else 'N/A',
            
            # Sucursal
            'sucursal': orden.sucursal.nombre if orden.sucursal else 'N/A',
            
            # Estado RHITSO
            'estado_rhitso_nombre': estado_rhitso_nombre,
            'estado_rhitso_display': estado_rhitso_display,
            'owner_actual': owner_actual,
            
            # Incidencias
            'incidencias_abiertas': incidencias_abiertas_count,
            'incidencias_resueltas': incidencias_resueltas_count,
            'total_incidencias': total_incidencias,
            
            # Fechas y tiempos
            'fecha_envio_rhitso': orden.fecha_envio_rhitso,
            'dias_habiles_sic': dias_habiles_sic,
            'dias_habiles_rhitso': dias_habiles_rhitso,
            'dias_sin_actualizar': dias_sin_actualizar,
            'fecha_ultimo_comentario': fecha_ultimo_comentario,
            'ultimo_comentario': ultimo_comentario,
            
            # Estado del proceso
            'estado_proceso': estado_proceso,
            'color_badge_dias': color_badge_dias,
            
            # Diagnóstico
            'tiene_diagnostico': bool(detalle and detalle.diagnostico_sic),
        }
        
        # ===================================================================
        # 4.8: CLASIFICAR ORDEN EN CATEGORÍA CORRESPONDIENTE
        # ===================================================================
        
        # EXPLICACIÓN: Separamos las órdenes según su estado RHITSO
        if estado_rhitso_nombre in estados_excluidos:
            excluidos.append(orden_data)
        elif estado_rhitso_nombre in estados_pendientes:
            pendientes.append(orden_data)
        else:
            activos.append(orden_data)
    
    # =======================================================================
    # PASO 5: OBTENER LISTA DE ESTADOS RHITSO PARA FILTROS
    # =======================================================================
    
    # EXPLICACIÓN: Creamos listas de estados únicos para los dropdowns de filtro
    estados_activos = list(set(orden['estado_rhitso_display'] for orden in activos))
    estados_pendientes_lista = list(set(orden['estado_rhitso_display'] for orden in pendientes))
    estados_excluidos_lista = list(set(orden['estado_rhitso_display'] for orden in excluidos))
    
    # Ordenar alfabéticamente
    estados_activos.sort()
    estados_pendientes_lista.sort()
    estados_excluidos_lista.sort()
    
    # =======================================================================
    # PASO 6: PREPARAR CONTEXTO PARA EL TEMPLATE
    # =======================================================================
    
    context = {
        # Estadísticas generales
        'total_candidatos': total_candidatos,
        'total_enviados': total_enviados,
        'total_con_diagnostico': total_con_diagnostico,
        'total_incidencias_abiertas': total_incidencias_abiertas,
        
        # Estadísticas por sucursal
        'stats_sucursal': stats_sucursal,
        
        # Órdenes por categoría
        'activos': activos,
        'pendientes': pendientes,
        'excluidos': excluidos,
        
        # Contadores para pestañas
        'count_activos': len(activos),
        'count_pendientes': len(pendientes),
        'count_excluidos': len(excluidos),
        
        # Listas de estados para filtros
        'estados_activos': estados_activos,
        'estados_pendientes': estados_pendientes_lista,
        'estados_excluidos': estados_excluidos_lista,
        
        # Información adicional
        'fecha_actualizacion': timezone.now(),
    }
    
    return render(request, 'servicio_tecnico/rhitso/dashboard_rhitso.html', context)
