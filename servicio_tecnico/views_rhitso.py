"""
Vistas RHITSO por orden (Fase 7 modularización).

EXPLICACIÓN PARA PRINCIPIANTES:
Panel de gestión RHITSO, estados, incidencias, comentarios, correo y PDF de prueba.
urls.py sigue usando views.<nombre> porque views.py reexporta estos símbolos.
NO incluye dashboards RHITSO (eso es Fase 8).
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from inventario.models import Empleado

from .decorators import permission_required_with_message
from .forms import (
    ActualizarEstadoRHITSOForm,
    EditarDiagnosticoSICForm,
    RegistrarIncidenciaRHITSOForm,
    ResolverIncidenciaRHITSOForm,
)
from .models import (
    ConfiguracionRHITSO,
    EstadoRHITSO,
    ImagenOrden,
    IncidenciaRHITSO,
    OrdenServicio,
    SeguimientoRHITSO,
)
from .services.historial import registrar_historial


# ============================================================================
# RHITSO - SISTEMA DE SEGUIMIENTO ESPECIALIZADO
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def gestion_rhitso(request, orden_id):
    """
    Vista principal del módulo RHITSO - Panel de gestión completo.

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

    detalle_equipo = orden.detalle_equipo
    
    # Preparar diccionario con información del equipo

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

            estado_obj = EstadoRHITSO.objects.get(estado=orden.estado_rhitso)
            
            # Calcular días en RHITSO usando property del modelo

            dias_en_rhitso = orden.dias_en_rhitso
            
            # Obtener configuración para alertas (días máximos permitidos)

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

    # Seguimientos automáticos del sistema (es_cambio_automatico=True)

    seguimientos_sistema = orden.seguimientos_rhitso.filter(
        es_cambio_automatico=True
    ).select_related(
        'estado',
        'usuario_actualizacion'
    ).order_by('-fecha_actualizacion')
    
    # Seguimientos manuales (es_cambio_automatico=False)

    seguimientos_manuales = orden.seguimientos_rhitso.filter(
        es_cambio_automatico=False
    ).select_related(
        'estado',
        'usuario_actualizacion'
    ).order_by('-fecha_actualizacion')
    
    # Obtener último seguimiento RHITSO (de cualquier tipo)

    ultimo_seguimiento_rhitso = (
        seguimientos_manuales.first() or 
        seguimientos_sistema.first()
    )
    
    # =======================================================================
    # PASO 6: OBTENER INCIDENCIAS Y CALCULAR ESTADÍSTICAS
    # =======================================================================

    # Obtener todas las incidencias de la orden
    incidencias = orden.incidencias_rhitso.select_related(
        'tipo_incidencia',
        'usuario_registro',
        'resuelto_por'
    ).order_by('-fecha_ocurrencia')
    
    # Calcular estadísticas de incidencias

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

    # Obtener todas las imágenes de la orden
    imagenes_rhitso = orden.imagenes.select_related('subido_por').order_by('-fecha_subida')
    
    # Organizar imágenes por tipo (igual que en detalle_orden)

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

    # Formulario para cambiar estado RHITSO

    form_estado = ActualizarEstadoRHITSOForm()
    
    # Formulario para registrar incidencias

    form_incidencia = RegistrarIncidenciaRHITSOForm()
    
    # Formulario para resolver incidencias

    form_resolver_incidencia = ResolverIncidenciaRHITSOForm()
    
    # Formulario para editar diagnóstico SIC

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

    # Importar settings para obtener destinatarios RHITSO
    from django.conf import settings
    
    # A) DESTINATARIOS PRINCIPALES - Desde settings.py

    destinatarios_rhitso = settings.RHITSO_EMAIL_RECIPIENTS
    
    # B) EMPLEADOS PARA "CON COPIA A" - Filtrados por área

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
    # EXPLICACIÓN: El asunto por defecto es el mismo que usa la task al enviar
    # (editable en el modal). Formato: emoji + orden del cliente (OOW/FL…).
    asunto_correo = f'🔧ENVIO DE EQUIPO RHITSO - {orden_cliente}'
    
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
@permission_required_with_message('servicio_tecnico.change_ordenservicio')
@require_http_methods(["POST"])
def actualizar_estado_rhitso(request, orden_id):
    """
    Vista AJAX para actualizar el estado RHITSO de una orden.

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
        
        # Paso 6: Actualizar fechas especiales (SOLO SI EL USUARIO LAS PROPORCIONA)
    
        # Si el usuario proporcionó una fecha de envío, usarla
        if fecha_envio:
            orden.fecha_envio_rhitso = fecha_envio
        
        # Si el usuario proporcionó una fecha de recepción, usarla
        if fecha_recepcion:
            orden.fecha_recepcion_rhitso = fecha_recepcion
        
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
@permission_required_with_message('servicio_tecnico.add_incidenciarhitso')
@require_http_methods(["POST"])
def registrar_incidencia(request, orden_id):
    """
    Vista AJAX para registrar una nueva incidencia RHITSO.

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
@permission_required_with_message('servicio_tecnico.change_incidenciarhitso')
@require_http_methods(["POST"])
def resolver_incidencia(request, incidencia_id):
    """
    Vista AJAX para resolver/cerrar una incidencia existente.

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
@permission_required_with_message('servicio_tecnico.change_ordenservicio')
@require_http_methods(["POST"])
def editar_diagnostico_sic(request, orden_id):
    """
    Vista para editar el diagnóstico SIC y datos relacionados con RHITSO.

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
@permission_required_with_message('servicio_tecnico.change_ordenservicio')
@require_http_methods(["POST"])
def agregar_comentario_rhitso(request, orden_id):
    """
    Vista AJAX para agregar un comentario manual al historial RHITSO.

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

# ============================================================================
# VISTA: ENVIAR CORREO Y FORMATO RHITSO - FASE 10
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
@require_http_methods(["POST"])
def enviar_correo_rhitso(request, orden_id):
    """
    Vista para encolar el correo RHITSO (PDF + imágenes) vía Celery.

    Objetivo de negocio:
        Validar destinatarios y asunto del modal, y disparar el envío en
        segundo plano sin hacer esperar al usuario.

    Args:
        request: HttpRequest POST con destinatarios_principales, copia_empleados
                 y asunto_correo (editable en el modal).
        orden_id: ID de la OrdenServicio candidata RHITSO.

    Returns:
        JsonResponse inmediato con task_id; el Worker procesa el correo.

    Efectos secundarios:
        Encola enviar_correo_rhitso_task con db_alias del país actual.
    """
    from .tasks import enviar_correo_rhitso_task

    try:
        # =======================================================================
        # PASO 1: OBTENER Y VALIDAR LA ORDEN (rápido, solo consulta a BD)
        # =======================================================================
        orden = get_object_or_404(OrdenServicio, pk=orden_id)

        if not orden.es_candidato_rhitso:
            return JsonResponse({
                'success': False,
                'mensaje': '❌ Esta orden no está marcada como candidato RHITSO.'
            }, status=400)

        # =======================================================================
        # PASO 2: OBTENER Y VALIDAR DESTINATARIOS DEL FORMULARIO
        # =======================================================================
        destinatarios_principales = request.POST.getlist('destinatarios_principales')
        copia_empleados = request.POST.getlist('copia_empleados')

        if not destinatarios_principales:
            return JsonResponse({
                'success': False,
                'mensaje': '❌ Debe seleccionar al menos un destinatario principal.'
            }, status=400)

        # =======================================================================
        # PASO 2.5: ASUNTO DEL CORREO (editable en el modal)
        # =======================================================================
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # El modal manda "asunto_correo". Si el usuario lo borra o llega vacío,
        # reconstruimos el default histórico: 🔧ENVIO DE EQUIPO RHITSO - {orden_cliente}.
        asunto_correo = request.POST.get('asunto_correo', '').strip()
        if not asunto_correo:
            detalle = getattr(orden, 'detalle_equipo', None)
            orden_para_asunto = orden.numero_orden_interno
            if detalle and detalle.orden_cliente:
                orden_para_asunto = detalle.orden_cliente
            asunto_correo = f'🔧ENVIO DE EQUIPO RHITSO - {orden_para_asunto}'

        # =======================================================================
        # PASO 3: DISPARAR TAREA CELERY EN SEGUNDO PLANO
        # =======================================================================
        # EXPLICACIÓN: .delay() es la forma de enviar una tarea a Celery.
        # - NO espera a que termine (retorna inmediatamente con un task_id)
        # - El Worker de Celery la ejecutará en paralelo
        # - Pasamos solo tipos simples: int, list de strings
        # - NUNCA pasar objetos Django directamente (no son serializables a JSON)
        usuario_id = request.user.pk if request.user.is_authenticated else None

        from config.paises_config import get_pais_actual
        tarea = enviar_correo_rhitso_task.delay(
            orden_id=orden_id,
            destinatarios_principales=destinatarios_principales,
            copia_empleados=copia_empleados,
            asunto_correo=asunto_correo,
            usuario_id=usuario_id,
            db_alias=get_pais_actual()['db_alias'],
        )

        return JsonResponse({
            'success': True,
            'mensaje': (
                f'✅ Correo en proceso de envío a {len(destinatarios_principales)} destinatario(s). '
                f'El PDF y las imágenes se están procesando en segundo plano.'
            ),
            'data': {
                'task_id': tarea.id,
                'destinatarios': len(destinatarios_principales),
                'copias': len(copia_empleados),
                'orden': orden.numero_orden_interno,
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'mensaje': f'❌ Error al procesar la solicitud: {str(e)}'
        }, status=500)


# ============================================================================
# VISTA DE PRUEBA: GENERAR PDF RHITSO
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def generar_pdf_rhitso_prueba(request, orden_id):
    """
    Vista de prueba para generar el PDF RHITSO.

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


