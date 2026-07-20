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
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Q, Prefetch
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_http_methods
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit
from django.conf import settings
from django.urls import reverse
from PIL import Image, ImageOps
import os
import logging

# Logger para registrar eventos de seguridad en vistas públicas
logger = logging.getLogger(__name__)
import json
import openpyxl
from decouple import config
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from .models import (
    OrdenServicio, 
    DetalleEquipo, 
    HistorialOrden, 
    ImagenOrden,
    VideoOrden,
    EstadoRHITSO,
    SeguimientoRHITSO,
    IncidenciaRHITSO,
    TipoIncidenciaRHITSO,
    CategoriaDiagnostico,
    ConfiguracionRHITSO,
    Cotizacion,
)
# EXPLICACIÓN PARA PRINCIPIANTES:
# Helpers, SICSER, gama, video, APIs, misc, concentrado, IA diag y perfil salieron del monolito.
# Reexportamos aquí para que urls.py (views.foo) e imports antiguos sigan igual.
# Portal cliente / chat viven en views_seguimiento_cliente.py (reexport).
# Dashboards encuestas/feedback/enlaces: Fase 4 (views_encuestas, etc.).
# Multimedia (compressors + eliminar/descargar): Fase 5.
# AJAX piezas/seguimiento/VM + notif pieza: Fase 6.
# RHITSO por orden + envíos al cliente: Fase 7.
# Dashboards grandes + exports Excel: Fase 8.
from .decorators import cache_page_dashboard, permission_required_with_message
from .services.historial import registrar_historial
from .services.multimedia import (  # noqa: F401
    comprimir_y_guardar_imagen,
    comprimir_y_guardar_video,
)
from .views_multimedia import (  # noqa: F401
    descargar_imagen_original,
    eliminar_imagen,
    eliminar_video,
)
from .views_piezas_cotizadas import (  # noqa: F401
    agregar_pieza_cotizada,
    editar_pieza_cotizada,
    eliminar_pieza_cotizada,
    obtener_pieza_cotizada,
)
from .views_seguimiento_piezas_ajax import (  # noqa: F401
    agregar_seguimiento_pieza,
    cambiar_estado_seguimiento,
    editar_seguimiento_pieza,
    eliminar_seguimiento_pieza,
    marcar_pieza_danada,
    marcar_pieza_incorrecta,
    marcar_pieza_recibida,
    obtener_seguimiento_pieza,
    reenviar_notificacion_pieza,
)
from .views_venta_mostrador_ajax import (  # noqa: F401
    agregar_pieza_venta_mostrador,
    crear_venta_mostrador,
    editar_pieza_venta_mostrador,
    eliminar_pieza_venta_mostrador,
)
from .services.notificaciones_piezas import (  # noqa: F401
    enviar_notificacion_pieza_recibida as _enviar_notificacion_pieza_recibida,
)
from .views_rhitso import (  # noqa: F401
    actualizar_estado_rhitso,
    agregar_comentario_rhitso,
    editar_diagnostico_sic,
    enviar_correo_rhitso,
    generar_pdf_rhitso_prueba,
    gestion_rhitso,
    registrar_incidencia,
    resolver_incidencia,
)
from .views_envios_cliente import (  # noqa: F401
    confirmar_envio_feedback,
    confirmar_envio_vigencia_vencida,
    enviar_diagnostico_cliente,
    enviar_evidencia_video,
    enviar_imagenes_cliente,
    enviar_imagenes_egreso_cliente,
    enviar_rewind_egreso_cliente,
    obtener_destinatarios_egreso,
    preview_pdf_diagnostico,
)
from .services.ventas_mostrador_analytics import (  # noqa: F401
    determinar_categoria_venta,
    obtener_top_productos_vendidos,
)
from .views_dashboard_rhitso import (  # noqa: F401
    dashboard_rhitso,
    exportar_analisis_rhitso,
    exportar_excel_rhitso,
)
from .views_dashboard_oow_fl import (  # noqa: F401
    dashboard_seguimiento_oow_fl,
    exportar_excel_dashboard_oow_fl,
)
from .views_dashboard_cotizaciones import (  # noqa: F401
    dashboard_cotizaciones,
    exportar_analisis_aceptaciones,
    exportar_analisis_rechazos,
    exportar_dashboard_cotizaciones,
)
from .views_dashboard_seguimiento_piezas import (  # noqa: F401
    dashboard_seguimiento_piezas,
    exportar_dashboard_seguimiento_piezas,
)
from .views_sicser import consultar_sicser, importar_orden_sicser  # noqa: F401
from .views_referencias_gama import (  # noqa: F401
    crear_referencia_gama,
    editar_referencia_gama,
    eliminar_referencia_gama,
    lista_referencias_gama,
    reactivar_referencia_gama,
)
from .views_video_resumen import (  # noqa: F401
    comprimir_video_resumen,
    estado_compresion_resumen,
    estado_video_resumen,
    generar_video_resumen,
)
from .views_apis_busqueda import (  # noqa: F401
    api_buscar_modelos_por_marca,
    api_buscar_orden_por_serie,
    api_buscar_ordenes_autocomplete,
    api_buscar_ordenes_reingreso,
)
from .views_misc import (  # noqa: F401
    acceso_denegado,
    actualizar_email_cliente,
)
from .views_concentrado import (  # noqa: F401
    concentrado_semanal,
    exportar_concentrado_excel,
    exportar_concentrado_pdf,
)
from .views_ia_diagnostico import (  # noqa: F401
    pulir_diagnostico_sic_ia,
    transcribir_audio_diagnostico,
)
from .views_perfil import (  # noqa: F401
    directorio_empleados,
    exportar_excel_mi_perfil,
    mi_perfil,
    perfil_empleado,
)
from .views_seguimiento_cliente import (  # noqa: F401
    cancelar_push_seguimiento,
    chat_seguimiento_cliente,
    confirmar_feedback_satisfaccion,
    diagnostico_pdf_seguimiento,
    feedback_rechazo_view,
    feedback_satisfaccion_cliente,
    manifest_seguimiento,
    registrar_evento_seguimiento_cliente,
    seguimiento_orden_cliente,
    suscribir_push_seguimiento,
    vapid_key_seguimiento,
)
from .views_encuestas import (  # noqa: F401
    api_analisis_sentimiento_ia,
    api_encuestas_comentarios,
    api_encuestas_distribucion_nps,
    api_encuestas_kpis,
    api_encuestas_lista,
    api_encuestas_por_responsable,
    api_encuestas_tendencia,
    dashboard_encuestas,
    exportar_encuestas_excel,
    exportar_encuestas_pdf,
)
from .views_feedback_rechazo_dash import (  # noqa: F401
    api_feedback_rechazo_comentarios,
    api_feedback_rechazo_kpis,
    api_feedback_rechazo_lista,
    api_feedback_rechazo_por_motivo,
    api_feedback_rechazo_tendencia,
    dashboard_feedback_rechazo,
    exportar_feedback_rechazo_excel,
)
from .views_seguimiento_enlaces import (  # noqa: F401
    api_seguimiento_enlaces_embudo,
    api_seguimiento_enlaces_kpis,
    api_seguimiento_enlaces_tabla,
    api_seguimiento_enlaces_tendencia,
    api_seguimiento_enlaces_top,
    dashboard_seguimiento_enlaces,
)
# Helpers de enlaces (antes privados en views.py; ahora en eventos_seguimiento)
from .eventos_seguimiento import (  # noqa: F401
    anotar_push_enlaces as _anotar_push_enlaces,
    filtrar_enlaces_seguimiento as _filtrar_enlaces_seguimiento,
)
from decimal import Decimal
from inventario.models import Empleado, Sucursal
from scorecard.models import ComponenteEquipo
from config.constants import (
    ESTADO_ORDEN_CHOICES,
    ESTADO_PIEZA_CHOICES,
    ESTADOS_PIEZA_RECIBIDOS,
    ESTADOS_PIEZA_PENDIENTES,
    ESTADOS_PIEZA_PROBLEMATICOS,
    COMPONENTES_DIAGNOSTICO_ORDEN,
)
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
    SubirVideoForm,
    EditarInformacionEquipoForm,
    CrearCotizacionForm,
    GuardarManoObraForm,
    GestionarCotizacionForm,
    ActualizarEstadoRHITSOForm,
    RegistrarIncidenciaRHITSOForm,
    ResolverIncidenciaRHITSOForm,
    EditarDiagnosticoSICForm,
)


# ============================================================================
# ANALYTICS VENTA MOSTRADOR (Fase 8):
#   services/ventas_mostrador_analytics.py (reexport al inicio)
# ============================================================================


# ============================================================================
# VISTA: Seleccionar Tipo de Orden
# EXPLICACIÓN: Página intermedia donde el usuario elige entre:
#              - Servicio con Diagnóstico (OOW-)
#              - Venta Mostrador (FL-)
# ============================================================================
@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def seleccionar_tipo_orden(request):
    """
    Vista de selección de tipo de orden de servicio.

    Args:
        request: Objeto HttpRequest de Django
        
    Returns:
        HttpResponse con el template de selección renderizado
    """
    context = {
        'titulo': 'Seleccionar Tipo de Servicio',
    }
    return render(request, 'servicio_tecnico/seleccionar_tipo_orden.html', context)


@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def inicio(request):
    """
    Vista principal de Servicio Técnico - Dashboard Completo

    Returns:
        HttpResponse con el template renderizado y todas las métricas
    """
    from django.db.models import Avg, Max, Min, F
    from django.db.models.functions import Coalesce
    from datetime import timedelta
    
    # ========================================================================
    # SECCIÓN 1: ESTADÍSTICAS GENERALES
    # ========================================================================
    total_ordenes = OrdenServicio.objects.count()
    
    # Órdenes activas (no entregadas ni canceladas)
    ordenes_activas_qs = OrdenServicio.objects.exclude(estado__in=['entregado', 'cancelado'])
    ordenes_activas = ordenes_activas_qs.count()
    
    # Órdenes finalizadas este mes
    from django.utils import timezone
    inicio_mes = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ordenes_finalizadas_mes = OrdenServicio.objects.filter(
        estado='entregado',
        fecha_entrega__gte=inicio_mes
    ).count()
    
    # Órdenes retrasadas (más de 15 días sin entregar)
    fecha_limite_retraso = timezone.now() - timedelta(days=15)
    ordenes_retrasadas = ordenes_activas_qs.filter(
        fecha_ingreso__lt=fecha_limite_retraso
    ).count()
    
    # ========================================================================
    # SECCIÓN 2: ÓRDENES POR ESTADO (Con nombres legibles)
    # ========================================================================
    ordenes_por_estado_raw = OrdenServicio.objects.values('estado').annotate(
        total=Count('numero_orden_interno')
    ).order_by('-total')
    
    # Convertir a lista con nombres legibles
    ordenes_por_estado = []
    estado_dict = dict(ESTADO_ORDEN_CHOICES)
    for item in ordenes_por_estado_raw:
        ordenes_por_estado.append({
            'estado': item['estado'],
            'estado_display': estado_dict.get(item['estado'], item['estado']),
            'total': item['total']
        })
    
    # ========================================================================
    # SECCIÓN 3: ÓRDENES POR TÉCNICO (Solo técnicos de laboratorio activos)
    # ========================================================================
    ordenes_por_tecnico = OrdenServicio.objects.filter(
        tecnico_asignado_actual__cargo='TECNICO DE LABORATORIO',
        tecnico_asignado_actual__activo=True
    ).exclude(
        estado__in=['entregado', 'cancelado']
    ).values(
        'tecnico_asignado_actual__nombre_completo',
        'tecnico_asignado_actual__id'
    ).annotate(
        total_ordenes=Count('numero_orden_interno')
    ).order_by('-total_ordenes')
    
    # Enriquecer con información adicional del técnico
    ordenes_por_tecnico_enriquecido = []
    for item in ordenes_por_tecnico:
        try:
            tecnico = Empleado.objects.get(id=item['tecnico_asignado_actual__id'])
            ordenes_por_tecnico_enriquecido.append({
                'tecnico_nombre': item['tecnico_asignado_actual__nombre_completo'],
                'total_ordenes': item['total_ordenes'],
                'foto_url': tecnico.get_foto_perfil_url(),
                'iniciales': tecnico.get_iniciales(),
            })
        except Empleado.DoesNotExist:
            pass
    
    # ========================================================================
    # SECCIÓN 4: ÓRDENES POR GAMA DE EQUIPO
    # ========================================================================
    ordenes_por_gama = OrdenServicio.objects.exclude(
        estado__in=['entregado', 'cancelado']
    ).values(
        'detalle_equipo__gama'
    ).annotate(
        total=Count('numero_orden_interno')
    ).order_by('-total')
    
    # Convertir a diccionario para fácil acceso
    ordenes_gama_dict = {item['detalle_equipo__gama']: item['total'] for item in ordenes_por_gama}
    ordenes_gama_alta = ordenes_gama_dict.get('alta', 0)
    ordenes_gama_media = ordenes_gama_dict.get('media', 0)
    ordenes_gama_baja = ordenes_gama_dict.get('baja', 0)
    
    # ========================================================================
    # SECCIÓN 5: ÓRDENES POR SUCURSAL
    # ========================================================================
    ordenes_por_sucursal = OrdenServicio.objects.exclude(
        estado__in=['entregado', 'cancelado']
    ).values(
        'sucursal__nombre'
    ).annotate(
        total=Count('numero_orden_interno')
    ).order_by('-total')
    
    # ========================================================================
    # SECCIÓN 6: ESTADÍSTICAS DE COTIZACIONES
    # ========================================================================
    from servicio_tecnico.models import Cotizacion
    
    # Cotizaciones pendientes de respuesta
    cotizaciones_pendientes = Cotizacion.objects.filter(
        usuario_acepto__isnull=True
    ).count()
    
    # Cotizaciones aceptadas
    cotizaciones_aceptadas = Cotizacion.objects.filter(
        usuario_acepto=True
    ).count()
    
    # Cotizaciones rechazadas
    cotizaciones_rechazadas = Cotizacion.objects.filter(
        usuario_acepto=False
    ).count()
    
    # ========================================================================
    # SECCIÓN 7: ÓRDENES RHITSO
    # ========================================================================
    ordenes_rhitso_activas = OrdenServicio.objects.filter(
        es_candidato_rhitso=True
    ).exclude(
        estado__in=['entregado', 'cancelado']
    ).count()
    
    # ========================================================================
    # SECCIÓN 8: TIEMPOS PROMEDIO (KPIs de Rendimiento)
    # ========================================================================
    # Calcular tiempo promedio de servicio (solo órdenes entregadas)
    ordenes_entregadas = OrdenServicio.objects.filter(estado='entregado')
    
    if ordenes_entregadas.exists():
        # Calcular días promedio usando días hábiles
        tiempos = []
        for orden in ordenes_entregadas[:100]:  # Últimas 100 órdenes para no sobrecargar
            tiempos.append(orden.dias_habiles_en_servicio)
        
        tiempo_promedio_servicio = sum(tiempos) / len(tiempos) if tiempos else 0
    else:
        tiempo_promedio_servicio = 0
    
    # ========================================================================
    # SECCIÓN 9: ÓRDENES SIN ACTUALIZACIÓN DE ESTADO (Top 10)
    # ========================================================================
    # Calculamos la última fecha de cambio de estado registrada en el historial
    # Si no existe un cambio de estado, usamos la fecha de ingreso como referencia
    from django.db.models import Q
    ordenes_sin_actualizacion_qs = OrdenServicio.objects.exclude(
        estado__in=['entregado', 'cancelado']
    ).select_related(
        'sucursal',
        'tecnico_asignado_actual',
        'detalle_equipo'
    ).annotate(
        last_estado_date=Coalesce(
            Max('historial__fecha_evento', filter=Q(historial__tipo_evento='cambio_estado')),
            F('fecha_ingreso')
        )
    )

    # Construir lista en Python con días desde la última actualización de estado
    ordenes_sin_actualizacion_list = []
    ahora = timezone.now()
    for orden in ordenes_sin_actualizacion_qs:
        last_date = orden.last_estado_date or orden.fecha_ingreso
        dias = (ahora - last_date).days if last_date else 0
        detalle = getattr(orden, 'detalle_equipo', None)
        ordenes_sin_actualizacion_list.append({
            'pk': orden.pk,
            'orden_cliente': detalle.orden_cliente if detalle and getattr(detalle, 'orden_cliente', None) else '',
            'numero_orden_interno': orden.numero_orden_interno,
            'fecha_ultimo_estado': last_date,
            'dias_sin_actualizacion': dias,
            'marca': getattr(detalle, 'marca', '') if detalle else '',
            'modelo': getattr(detalle, 'modelo', '') if detalle else '',
            'numero_serie': getattr(detalle, 'numero_serie', '') if detalle else '',
            'tecnico_nombre': orden.tecnico_asignado_actual.nombre_completo if orden.tecnico_asignado_actual else '',
            'estado': orden.estado,
            'estado_display': orden.get_estado_display(),
        })

    # Ordenar por días sin actualización descendente y tomar top 10
    ordenes_sin_actualizacion_list.sort(key=lambda x: x['dias_sin_actualizacion'], reverse=True)
    ordenes_sin_actualizacion = ordenes_sin_actualizacion_list[:10]
    
    # ========================================================================
    # SECCIÓN 10: ALERTAS Y SITUACIONES CRÍTICAS
    # ========================================================================
    
    # Órdenes en "Esperando Cotización" por más de 3 días
    fecha_limite_cotizacion = timezone.now() - timedelta(days=3)
    ordenes_esperando_cotizacion = OrdenServicio.objects.filter(
        estado='cotizacion',
        fecha_ingreso__lt=fecha_limite_cotizacion
    ).count()
    
    # Órdenes en "Esperando Piezas" por más de 7 días
    fecha_limite_piezas = timezone.now() - timedelta(days=7)
    ordenes_esperando_piezas = OrdenServicio.objects.filter(
        estado='esperando_piezas',
        fecha_ingreso__lt=fecha_limite_piezas
    ).count()
    
    # Órdenes finalizadas pero no entregadas (más de 5 días)
    fecha_limite_entrega = timezone.now() - timedelta(days=5)
    ordenes_finalizadas_pendientes = OrdenServicio.objects.filter(
        estado='finalizado',
        fecha_finalizacion__lt=fecha_limite_entrega
    ).count()

    # Indicadores rápidos adicionales (reemplazan accesos directos al admin)
    # Incidencias abiertas (no resueltas ni cerradas)
    try:
        incidencias_abiertas = IncidenciaRHITSO.objects.exclude(estado__in=['RESUELTA', 'CERRADA']).count()
    except Exception:
        incidencias_abiertas = 0

    # Pedidos de piezas retrasados (seguimientos de piezas cuya fecha estimada ya pasó y no han llegado)
    try:
        from .models import SeguimientoPieza
        piezas_retrasadas = SeguimientoPieza.objects.filter(
            fecha_entrega_real__isnull=True,
            fecha_entrega_estimada__lt=timezone.now().date()
        ).count()
    except Exception:
        piezas_retrasadas = 0
    
    # ========================================================================
    # CONTEXTO COMPLETO PARA EL TEMPLATE
    # ========================================================================
    context = {
        # Estadísticas Generales
        'total_ordenes': total_ordenes,
        'ordenes_activas': ordenes_activas,
        'ordenes_finalizadas_mes': ordenes_finalizadas_mes,
        'ordenes_retrasadas': ordenes_retrasadas,
        
        # Distribuciones
        'ordenes_por_estado': ordenes_por_estado,
        'ordenes_por_tecnico': ordenes_por_tecnico_enriquecido,
        'ordenes_por_sucursal': ordenes_por_sucursal,
        
        # Órdenes por Gama
        'ordenes_gama_alta': ordenes_gama_alta,
        'ordenes_gama_media': ordenes_gama_media,
        'ordenes_gama_baja': ordenes_gama_baja,
        
        # Cotizaciones
        'cotizaciones_pendientes': cotizaciones_pendientes,
        'cotizaciones_aceptadas': cotizaciones_aceptadas,
        'cotizaciones_rechazadas': cotizaciones_rechazadas,
        
        # RHITSO
        'ordenes_rhitso_activas': ordenes_rhitso_activas,
        
        # KPIs
        'tiempo_promedio_servicio': round(tiempo_promedio_servicio, 1),
        
    # Órdenes sin actualización de estado (Top 10)
    'ordenes_sin_actualizacion': ordenes_sin_actualizacion,
        
        # Alertas
        'ordenes_esperando_cotizacion': ordenes_esperando_cotizacion,
        'ordenes_esperando_piezas': ordenes_esperando_piezas,
        'ordenes_finalizadas_pendientes': ordenes_finalizadas_pendientes,
        
        # Total de alertas (para badge)
        'total_alertas': ordenes_esperando_cotizacion + ordenes_esperando_piezas + ordenes_finalizadas_pendientes + ordenes_retrasadas,
        # Indicadores rápidos
        'incidencias_abiertas': incidencias_abiertas,
        'piezas_retrasadas': piezas_retrasadas,
    }
    
    return render(request, 'servicio_tecnico/inicio.html', context)


@login_required
@permission_required_with_message('servicio_tecnico.add_ordenservicio')
def crear_orden(request):
    """
    Vista para crear una nueva orden de servicio técnico.

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

                # ── Enviar enlace de seguimiento para órdenes fuera de garantía ──
                # Refrescar porque DetalleEquipo.save() actualiza es_fuera_garantia
                # en la BD pero la instancia en memoria no lo refleja aún
                orden.refresh_from_db(fields=['es_fuera_garantia'])
                if orden.es_fuera_garantia:
                    try:
                        email_cli = orden.detalle_equipo.email_cliente
                        if email_cli:
                            from .tasks import enviar_seguimiento_cliente_task
                            from config.paises_config import get_pais_actual
                            enviar_seguimiento_cliente_task.delay(
                                orden_id=orden.id,
                                usuario_id=request.user.id,
                                db_alias=get_pais_actual()['db_alias'],
                            )
                    except Exception:
                        pass  # No bloquear la creación si falla el envío

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
@permission_required_with_message('servicio_tecnico.add_ordenservicio')
def crear_orden_venta_mostrador(request):
    """
    Vista para crear una nueva orden de Venta Mostrador (sin diagnóstico).

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

                # ── Enviar enlace de seguimiento para órdenes fuera de garantía (FL-) ──
                # Refrescar porque DetalleEquipo.save() actualiza es_fuera_garantia
                # en la BD pero la instancia en memoria no lo refleja aún
                orden.refresh_from_db(fields=['es_fuera_garantia'])
                if orden.es_fuera_garantia:
                    try:
                        email_cli = orden.detalle_equipo.email_cliente
                        if email_cli:
                            from .tasks import enviar_seguimiento_cliente_task
                            from config.paises_config import get_pais_actual
                            enviar_seguimiento_cliente_task.delay(
                                orden_id=orden.id,
                                usuario_id=request.user.id,
                                db_alias=get_pais_actual()['db_alias'],
                            )
                    except Exception:
                        pass  # No bloquear la creación si falla el envío

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
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def lista_ordenes_activas(request):
    """
    Vista para listar órdenes activas (no entregadas ni canceladas).

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
        'imagenes',  # Para contar imágenes eficientemente
        Prefetch(
            'historial',
            queryset=HistorialOrden.objects.filter(tipo_evento='cambio_estado').order_by('-fecha_evento')
        )  # Para calcular días sin actualización de estado eficientemente
    ).order_by('-fecha_ingreso')
    
    # Aplicar búsqueda si existe
    if busqueda:
        ordenes = ordenes.filter(
            Q(detalle_equipo__numero_serie__icontains=busqueda) |
            Q(detalle_equipo__orden_cliente__icontains=busqueda) |
            Q(numero_orden_interno__icontains=busqueda)
        )
    
    # ========================================================================
    # ESTADÍSTICAS UNIFICADAS POR TÉCNICO (AGRUPADAS POR SUCURSAL)
    # ========================================================================
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Esta sección calcula todas las estadísticas por técnico en una sola consulta optimizada.
    # Se agrupan por sucursal del técnico para facilitar la asignación equitativa por ubicación.
    
    from datetime import timedelta
    from django.db.models import Max, F, Q as QueryQ
    from collections import defaultdict
    
    # Obtener filtro temporal (por defecto: esta semana)
    filtro_temporal = request.GET.get('filtro_temporal', 'semana')
    
    # Calcular fechas según el filtro
    hoy = timezone.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())  # Lunes de esta semana
    
    if filtro_temporal == 'hoy':
        fecha_inicio_filtro = timezone.now().replace(hour=0, minute=0, second=0)
    elif filtro_temporal == 'semana':
        fecha_inicio_filtro = timezone.datetime.combine(inicio_semana, timezone.datetime.min.time())
        fecha_inicio_filtro = timezone.make_aware(fecha_inicio_filtro)
    else:  # 'historico'
        fecha_inicio_filtro = None
    
    # ========================================================================
    # PASO 1: Consultar órdenes activas por técnico con todos los datos
    # ========================================================================
    ordenes_activas_por_tecnico = OrdenServicio.objects.filter(
        tecnico_asignado_actual__cargo='TECNICO DE LABORATORIO',
        tecnico_asignado_actual__activo=True
    ).exclude(
        estado__in=['entregado', 'cancelado']
    ).values(
        'tecnico_asignado_actual__id'
    ).annotate(
        total_ordenes=Count('id')
    )
    ordenes_activas_dict = {item['tecnico_asignado_actual__id']: item['total_ordenes'] for item in ordenes_activas_por_tecnico}
    
    # ========================================================================
    # PASO 2: Equipos "No Enciende" activos por técnico
    # ========================================================================
    equipos_no_encienden_raw = OrdenServicio.objects.filter(
        tecnico_asignado_actual__cargo='TECNICO DE LABORATORIO',
        tecnico_asignado_actual__activo=True,
        detalle_equipo__equipo_enciende=False
    ).exclude(
        estado__in=['entregado', 'cancelado']
    ).values('tecnico_asignado_actual__id').annotate(
        total=Count('id')
    )
    equipos_no_encienden_dict = {item['tecnico_asignado_actual__id']: item['total'] for item in equipos_no_encienden_raw}
    
    # ========================================================================
    # PASO 3: Equipos por gama activos por técnico
    # ========================================================================
    equipos_por_gama_raw = OrdenServicio.objects.filter(
        tecnico_asignado_actual__cargo='TECNICO DE LABORATORIO',
        tecnico_asignado_actual__activo=True
    ).exclude(
        estado__in=['entregado', 'cancelado']
    ).values(
        'tecnico_asignado_actual__id',
        'detalle_equipo__gama'
    ).annotate(
        total=Count('id')
    )
    
    # Procesar en diccionario por técnico
    equipos_gama_dict = defaultdict(lambda: {'alta': 0, 'media': 0, 'baja': 0})
    for item in equipos_por_gama_raw:
        tecnico_id = item['tecnico_asignado_actual__id']
        gama = item['detalle_equipo__gama']
        total = item['total']
        equipos_gama_dict[tecnico_id][gama] = total
    
    # ========================================================================
    # PASO 4: Folios (FL-) activos por técnico
    # ========================================================================
    folios_fl_raw = OrdenServicio.objects.filter(
        tecnico_asignado_actual__cargo='TECNICO DE LABORATORIO',
        tecnico_asignado_actual__activo=True,
        detalle_equipo__orden_cliente__istartswith='FL-'
    ).exclude(
        estado__in=['entregado', 'cancelado']
    ).values('tecnico_asignado_actual__id').annotate(
        total=Count('id')
    )
    folios_fl_dict = {item['tecnico_asignado_actual__id']: item['total'] for item in folios_fl_raw}
    
    # ========================================================================
    # PASO 4.5: Asignaciones NETAS de Folios FL específicamente
    # ========================================================================
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Igual que las asignaciones netas generales (PASO 5), pero filtrando SOLO
    # las órdenes cuyo orden_cliente empieza con "FL-". Esto permite ver cuántos
    # folios FL le entraron/salieron a cada técnico hoy y en la semana/histórico.
    # El filtro extra es: orden__detalle_equipo__orden_cliente__istartswith='FL-'
    
    # Nota: inicio_hoy y fin_hoy se calculan en PASO 5, pero los necesitamos aquí.
    # Los calculamos una vez aquí y los reutilizamos en PASO 5.
    inicio_hoy = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    fin_hoy = inicio_hoy + timedelta(days=1)
    
    # --- FL netas HOY ---
    fl_hoy_entrantes = HistorialOrden.objects.filter(
        tipo_evento='cambio_tecnico',
        es_sistema=False,
        fecha_evento__gte=inicio_hoy,
        fecha_evento__lt=fin_hoy,
        orden__detalle_equipo__orden_cliente__istartswith='FL-'
    ).values('tecnico_nuevo__id').annotate(
        total=Count('id')
    )
    fl_hoy_entrantes_dict = {item['tecnico_nuevo__id']: item['total'] for item in fl_hoy_entrantes if item['tecnico_nuevo__id']}
    
    fl_hoy_salientes = HistorialOrden.objects.filter(
        tipo_evento='cambio_tecnico',
        es_sistema=False,
        fecha_evento__gte=inicio_hoy,
        fecha_evento__lt=fin_hoy,
        orden__detalle_equipo__orden_cliente__istartswith='FL-'
    ).values('tecnico_anterior__id').annotate(
        total=Count('id')
    )
    fl_hoy_salientes_dict = {item['tecnico_anterior__id']: item['total'] for item in fl_hoy_salientes if item['tecnico_anterior__id']}
    
    # --- FL netas SEMANA / HISTÓRICO ---
    if filtro_temporal == 'historico':
        fl_semana_entrantes = HistorialOrden.objects.filter(
            tipo_evento='cambio_tecnico',
            es_sistema=False,
            orden__detalle_equipo__orden_cliente__istartswith='FL-'
        ).values('tecnico_nuevo__id').annotate(
            total=Count('id')
        )
        fl_semana_salientes = HistorialOrden.objects.filter(
            tipo_evento='cambio_tecnico',
            es_sistema=False,
            orden__detalle_equipo__orden_cliente__istartswith='FL-'
        ).values('tecnico_anterior__id').annotate(
            total=Count('id')
        )
    elif filtro_temporal == 'semana':
        fl_semana_entrantes = HistorialOrden.objects.filter(
            tipo_evento='cambio_tecnico',
            es_sistema=False,
            fecha_evento__gte=fecha_inicio_filtro,
            orden__detalle_equipo__orden_cliente__istartswith='FL-'
        ).values('tecnico_nuevo__id').annotate(
            total=Count('id')
        )
        fl_semana_salientes = HistorialOrden.objects.filter(
            tipo_evento='cambio_tecnico',
            es_sistema=False,
            fecha_evento__gte=fecha_inicio_filtro,
            orden__detalle_equipo__orden_cliente__istartswith='FL-'
        ).values('tecnico_anterior__id').annotate(
            total=Count('id')
        )
    else:  # 'hoy'
        fl_semana_entrantes = []
        fl_semana_salientes = []
    
    fl_semana_entrantes_dict = {item['tecnico_nuevo__id']: item['total'] for item in fl_semana_entrantes if item['tecnico_nuevo__id']}
    fl_semana_salientes_dict = {item['tecnico_anterior__id']: item['total'] for item in fl_semana_salientes if item['tecnico_anterior__id']}
    
    # ========================================================================
    # PASO 5: Asignaciones NETAS (corrigiendo el bug)
    # ========================================================================
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # El bug estaba en que solo contábamos las asignaciones ENTRANTES (tecnico_nuevo)
    # pero no restábamos las SALIENTES (cuando se reasignaba a otro técnico).
    # Ahora calculamos: NETAS = ENTRANTES - SALIENTES
    
    # IMPORTANTE: inicio_hoy y fin_hoy ya se calcularon en PASO 4.5 (FL netas)
    
    # --- Asignaciones HOY ---
    # Entrantes: veces que el técnico fue asignado como tecnico_nuevo hoy
    asignaciones_hoy_entrantes = HistorialOrden.objects.filter(
        tipo_evento='cambio_tecnico',
        es_sistema=False,
        fecha_evento__gte=inicio_hoy,
        fecha_evento__lt=fin_hoy
    ).values('tecnico_nuevo__id').annotate(
        total=Count('id')
    )
    asignaciones_hoy_entrantes_dict = {item['tecnico_nuevo__id']: item['total'] for item in asignaciones_hoy_entrantes if item['tecnico_nuevo__id']}
    
    # Salientes: veces que el técnico perdió una orden (fue tecnico_anterior) hoy
    asignaciones_hoy_salientes = HistorialOrden.objects.filter(
        tipo_evento='cambio_tecnico',
        es_sistema=False,
        fecha_evento__gte=inicio_hoy,
        fecha_evento__lt=fin_hoy
    ).values('tecnico_anterior__id').annotate(
        total=Count('id')
    )
    asignaciones_hoy_salientes_dict = {item['tecnico_anterior__id']: item['total'] for item in asignaciones_hoy_salientes if item['tecnico_anterior__id']}
    
    # --- Asignaciones SEMANA / HISTÓRICO ---
    if filtro_temporal == 'historico':
        # Entrantes históricas
        asignaciones_semana_entrantes = HistorialOrden.objects.filter(
            tipo_evento='cambio_tecnico',
            es_sistema=False
        ).values('tecnico_nuevo__id').annotate(
            total=Count('id')
        )
        # Salientes históricas
        asignaciones_semana_salientes = HistorialOrden.objects.filter(
            tipo_evento='cambio_tecnico',
            es_sistema=False
        ).values('tecnico_anterior__id').annotate(
            total=Count('id')
        )
    elif filtro_temporal == 'semana':
        # Entrantes esta semana
        asignaciones_semana_entrantes = HistorialOrden.objects.filter(
            tipo_evento='cambio_tecnico',
            es_sistema=False,
            fecha_evento__gte=fecha_inicio_filtro
        ).values('tecnico_nuevo__id').annotate(
            total=Count('id')
        )
        # Salientes esta semana
        asignaciones_semana_salientes = HistorialOrden.objects.filter(
            tipo_evento='cambio_tecnico',
            es_sistema=False,
            fecha_evento__gte=fecha_inicio_filtro
        ).values('tecnico_anterior__id').annotate(
            total=Count('id')
        )
    else:  # 'hoy'
        asignaciones_semana_entrantes = []
        asignaciones_semana_salientes = []
    
    asignaciones_semana_entrantes_dict = {item['tecnico_nuevo__id']: item['total'] for item in asignaciones_semana_entrantes if item['tecnico_nuevo__id']}
    asignaciones_semana_salientes_dict = {item['tecnico_anterior__id']: item['total'] for item in asignaciones_semana_salientes if item['tecnico_anterior__id']}
    
    # ========================================================================
    # PASO 6: Última asignación por técnico (para rotación y "Última" columna)
    # ========================================================================
    ultimas_asignaciones = HistorialOrden.objects.filter(
        tipo_evento='cambio_tecnico',
        es_sistema=False,
        tecnico_nuevo__cargo='TECNICO DE LABORATORIO',
        tecnico_nuevo__activo=True
    ).values('tecnico_nuevo__id').annotate(
        ultima_fecha=Max('fecha_evento')
    )
    ultimas_asignaciones_dict = {item['tecnico_nuevo__id']: item['ultima_fecha'] for item in ultimas_asignaciones}
    
    # ========================================================================
    # PASO 7: Enriquecer datos por técnico y agrupar por sucursal → área
    # ========================================================================
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Ahora agrupamos por sucursal Y área (ej: Satélite → LABORATORIO DELL).
    # Esto permite asignaciones más precisas según la especialización del técnico.
    
    # Obtener todos los técnicos de laboratorio activos con su sucursal
    tecnicos_laboratorio = Empleado.objects.filter(
        cargo='TECNICO DE LABORATORIO',
        activo=True
    ).select_related('sucursal').order_by('sucursal__nombre', 'area', 'nombre_completo')
    
    # Agrupar técnicos por (sucursal_id, area) - usamos una tupla como clave
    tecnicos_por_sucursal_area = defaultdict(list)
    
    for tecnico in tecnicos_laboratorio:
        # Calcular asignaciones NETAS
        asignaciones_hoy_netas = (
            asignaciones_hoy_entrantes_dict.get(tecnico.id, 0) - 
            asignaciones_hoy_salientes_dict.get(tecnico.id, 0)
        )
        
        asignaciones_semana_netas = (
            asignaciones_semana_entrantes_dict.get(tecnico.id, 0) - 
            asignaciones_semana_salientes_dict.get(tecnico.id, 0)
        )
        
        # Calcular asignaciones NETAS de Folios FL
        folios_fl_hoy_netas = (
            fl_hoy_entrantes_dict.get(tecnico.id, 0) - 
            fl_hoy_salientes_dict.get(tecnico.id, 0)
        )
        
        folios_fl_semana_netas = (
            fl_semana_entrantes_dict.get(tecnico.id, 0) - 
            fl_semana_salientes_dict.get(tecnico.id, 0)
        )
        
        # Calcular tiempo desde última asignación
        ultima_asignacion = ultimas_asignaciones_dict.get(tecnico.id)
        if ultima_asignacion:
            delta = timezone.now() - ultima_asignacion
            horas = delta.total_seconds() / 3600
            if horas < 24:
                tiempo_sin_asignar = f"hace {int(horas)}h"
            else:
                dias = int(horas / 24)
                tiempo_sin_asignar = f"hace {dias}d"
        else:
            tiempo_sin_asignar = "Nunca"
        
        # Obtener datos de gama
        gama_data = equipos_gama_dict[tecnico.id]
        
        # Construir dict del técnico
        tecnico_data = {
            'tecnico_id': tecnico.id,
            'tecnico_nombre': tecnico.nombre_completo,
            'foto_url': tecnico.get_foto_perfil_url(),
            'iniciales': tecnico.get_iniciales(),
            'sucursal_id': tecnico.sucursal.id if tecnico.sucursal else None,
            'sucursal_nombre': tecnico.sucursal.nombre if tecnico.sucursal else 'Sin sucursal',
            'area': tecnico.area or 'Sin área',
            # Datos de carga
            'ordenes_actuales': ordenes_activas_dict.get(tecnico.id, 0),
            'equipos_no_encienden': equipos_no_encienden_dict.get(tecnico.id, 0),
            'gama_alta': gama_data['alta'],
            'gama_media': gama_data['media'],
            'gama_baja': gama_data['baja'],
            'folios_fl': folios_fl_dict.get(tecnico.id, 0),
            'folios_fl_hoy_netas': folios_fl_hoy_netas,
            'folios_fl_semana_netas': folios_fl_semana_netas,
            # Asignaciones NETAS (corregidas)
            'asignaciones_hoy_netas': asignaciones_hoy_netas,
            'asignaciones_semana_netas': asignaciones_semana_netas,
            # Tiempo
            'ultima_asignacion': ultima_asignacion,
            'tiempo_sin_asignar': tiempo_sin_asignar,
        }
        
        # Agrupar por (sucursal_id, area)
        sucursal_key = tecnico.sucursal.id if tecnico.sucursal else 'sin_sucursal'
        area_key = tecnico.area or 'sin_area'
        grupo_key = (sucursal_key, area_key)
        tecnicos_por_sucursal_area[grupo_key].append(tecnico_data)
    
    # ========================================================================
    # PASO 8: Calcular rotación SOLO para Satélite > Laboratorio OOW
    # ========================================================================
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # El badge "SIGUIENTE" solo se muestra para técnicos de Satélite en el área LABORATORIO OOW.
    # Otras sucursales/áreas no mostrarán este indicador.
    
    for grupo_key, tecnicos_list in tecnicos_por_sucursal_area.items():
        sucursal_key, area_key = grupo_key
        
        # Verificar si es Satélite y Laboratorio OOW
        # Obtenemos el nombre de la sucursal del primer técnico del grupo
        if tecnicos_list:
            sucursal_nombre = tecnicos_list[0]['sucursal_nombre']
            es_satelite = 'SATELITE' in sucursal_nombre.upper() or 'SATÉLITE' in sucursal_nombre.upper()
            es_lab_oow = 'OOW' in area_key.upper()
            
            # Solo calcular rotación si es Satélite > Lab OOW
            if es_satelite and es_lab_oow:
                # Ordenar técnicos de este grupo por prioridad de asignación
                tecnicos_ordenados = sorted(
                    tecnicos_list,
                    key=lambda x: (
                        x['ordenes_actuales'],  # Primero: menor carga actual
                        -(x['ultima_asignacion'].timestamp() if x['ultima_asignacion'] else 0),  # Segundo: más tiempo sin asignar
                        x['asignaciones_hoy_netas']  # Tercero: menos asignaciones netas hoy
                    )
                )
                
                # Marcar el primero como "siguiente en rotación"
                if tecnicos_ordenados:
                    siguiente_id = tecnicos_ordenados[0]['tecnico_id']
                    for tecnico_data in tecnicos_list:
                        tecnico_data['es_siguiente_rotacion'] = (tecnico_data['tecnico_id'] == siguiente_id)
            else:
                # Otras áreas/sucursales: no marcar a nadie como siguiente
                for tecnico_data in tecnicos_list:
                    tecnico_data['es_siguiente_rotacion'] = False
        
        # Ordenar lista final de este grupo: "Siguiente" primero (si aplica), luego por carga descendente
        tecnicos_list.sort(
            key=lambda x: (
                not x.get('es_siguiente_rotacion', False),  # False (siguiente) va primero
                -x['ordenes_actuales'],  # Luego por carga descendente
                x['tecnico_nombre']  # Desempate por nombre
            )
        )
    
    # ========================================================================
    # PASO 9: Organizar en estructura para el template (sucursal → áreas → técnicos)
    # ========================================================================
    # Agrupar por sucursal con sub-grupos por área
    sucursales_dict = defaultdict(lambda: defaultdict(list))
    
    for (sucursal_key, area_key), tecnicos_list in tecnicos_por_sucursal_area.items():
        for tecnico_data in tecnicos_list:
            sucursales_dict[sucursal_key][area_key].append(tecnico_data)
    
    # Convertir a lista ordenada de sucursales con sus áreas
    tecnicos_por_sucursal_ordenado = []
    
    # Ordenar sucursales alfabéticamente (sin_sucursal al final)
    sucursales_ordenadas = sorted(
        sucursales_dict.keys(),
        key=lambda k: ('zzz' if k == 'sin_sucursal' else sucursales_dict[k][list(sucursales_dict[k].keys())[0]][0]['sucursal_nombre'])
    )
    
    for sucursal_key in sucursales_ordenadas:
        areas_dict = sucursales_dict[sucursal_key]
        
        # Obtener nombre de sucursal del primer técnico
        primer_area = list(areas_dict.keys())[0]
        sucursal_nombre = areas_dict[primer_area][0]['sucursal_nombre']
        
        # Ordenar áreas alfabéticamente (sin_area al final)
        areas_ordenadas = sorted(
            areas_dict.keys(),
            key=lambda k: 'zzz' if k == 'sin_area' else k
        )
        
        # Construir sub-grupos de áreas
        areas_grupos = []
        for area_key in areas_ordenadas:
            areas_grupos.append({
                'area_nombre': area_key,
                'tecnicos': areas_dict[area_key]
            })
        
        tecnicos_por_sucursal_ordenado.append({
            'sucursal_nombre': sucursal_nombre,
            'areas': areas_grupos  # Nueva estructura con sub-grupos por área
        })
    
    # ========================================================================
    # HISTORIAL DE REASIGNACIONES DEL DÍA
    # ========================================================================
    reasignaciones_hoy = HistorialOrden.objects.filter(
        tipo_evento='cambio_tecnico',
        es_sistema=False,
        fecha_evento__gte=inicio_hoy,
        fecha_evento__lt=fin_hoy
    ).select_related(
        'orden',
        'tecnico_anterior',
        'tecnico_nuevo',
        'usuario'
    ).order_by('-fecha_evento')[:20]
    
    # Calcular total de órdenes activas
    total_ordenes_activas = OrdenServicio.objects.exclude(
        estado__in=['entregado', 'cancelado']
    ).count()
    
    # ========================================================================
    # PAGINACIÓN: 24 órdenes por página (múltiplo de las 5 columnas del grid)
    # ========================================================================
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Contamos el total ANTES de paginar para mostrar "Mostrando X-Y de Z órdenes".
    # Si pagináramos primero, el conteo solo reflejaría la página actual (máx 24).
    total_ordenes = ordenes.count()
    
    paginator = Paginator(ordenes, 24)
    pagina = request.GET.get('pagina', 1)
    
    try:
        ordenes_paginadas = paginator.page(pagina)
    except PageNotAnInteger:
        ordenes_paginadas = paginator.page(1)
    except EmptyPage:
        ordenes_paginadas = paginator.page(paginator.num_pages)
    
    context = {
        'ordenes': ordenes_paginadas,
        'tipo': 'activas',
        'titulo': 'Órdenes Activas',
        'total': total_ordenes,
        'busqueda': busqueda,
        'tecnicos_por_sucursal': tecnicos_por_sucursal_ordenado,  # NUEVA ESTRUCTURA UNIFICADA
        'reasignaciones_hoy': reasignaciones_hoy,
        'filtro_temporal': filtro_temporal,
        'total_ordenes_activas': total_ordenes_activas,
        'mostrar_estadisticas': True,
        'es_paginado': True,
        'paginator': paginator,
    }
    
    return render(request, 'servicio_tecnico/lista_ordenes.html', context)


@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def lista_ordenes_finalizadas(request):
    """
    Vista para listar órdenes finalizadas (entregadas o canceladas).

    Incluye búsqueda por número de serie y orden de cliente.
    Incluye paginación para mejorar rendimiento con muchos registros.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    La paginación divide los resultados en "páginas" de tamaño fijo (24 por defecto).
    Esto evita cargar cientos o miles de órdenes de una sola vez, lo cual haría
    que la página fuera muy lenta. El usuario navega entre páginas con controles
    de "Anterior" y "Siguiente".
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
    
    # Contar total ANTES de paginar para mostrar el conteo real
    total_ordenes = ordenes.count()
    
    # Paginación: 24 órdenes por página (múltiplo de las 5 columnas del grid)
    paginator = Paginator(ordenes, 24)
    pagina = request.GET.get('pagina', 1)
    
    try:
        ordenes_paginadas = paginator.page(pagina)
    except PageNotAnInteger:
        ordenes_paginadas = paginator.page(1)
    except EmptyPage:
        ordenes_paginadas = paginator.page(paginator.num_pages)
    
    # NO mostrar estadísticas en vista finalizadas (no tiene sentido ver cargas de trabajo de órdenes cerradas)
    context = {
        'ordenes': ordenes_paginadas,
        'tipo': 'finalizadas',
        'titulo': 'Órdenes Finalizadas',
        'total': total_ordenes,
        'busqueda': busqueda,
        'mostrar_estadisticas': False,  # No mostrar estadísticas aquí
        'es_paginado': True,
        'paginator': paginator,
    }
    
    return render(request, 'servicio_tecnico/lista_ordenes.html', context)


@login_required
@permission_required_with_message('servicio_tecnico.change_ordenservicio')
def cerrar_orden(request, orden_id):
    """
    Vista para cambiar el estado de una orden a 'entregado'.

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

        # ── TRIGGER: Encuesta de satisfacción post-entrega ──────────────────
        # Se crea si la cotización fue aceptada y el cliente tiene email válido.
        # También aplica para VentaMostrador con al menos un servicio.
        # El operador confirma el envío desde el modal en detalle_orden.html.
        _feedback_sat_creado = False
        try:
            import secrets as _secrets_cerrar
            import uuid as _uuid_cerrar
            from django.core.signing import TimestampSigner as _TSignerCerrar
            from .models import FeedbackCliente as _FBCCerrar
            _cot_cerrar = getattr(orden, 'cotizacion', None)
            _email_cerrar = (
                orden.detalle_equipo.email_cliente
                if orden.detalle_equipo and orden.detalle_equipo.email_cliente
                else None
            )
            _email_valido = (
                _email_cerrar
                and _email_cerrar != 'cliente@ejemplo.com'
            )

            if (
                _cot_cerrar is not None
                and _cot_cerrar.usuario_acepto is True
                and not _cot_cerrar.motivo_rechazo
                and _email_valido
                and not _FBCCerrar.objects.filter(
                    orden=orden, tipo='satisfaccion'
                ).exists()
            ):
                _fb_cerrar = _FBCCerrar.objects.create(
                    orden=orden,
                    cotizacion=_cot_cerrar,
                    token=_secrets_cerrar.token_urlsafe(32),
                    tipo='satisfaccion',
                )
                request.session['feedback_satisfaccion_pendiente_id'] = _fb_cerrar.pk
                request.session['feedback_satisfaccion_email'] = _email_cerrar
                _feedback_sat_creado = True

            elif (
                not _feedback_sat_creado
                and hasattr(orden, 'venta_mostrador')
                and orden.venta_mostrador.tiene_al_menos_un_servicio
                and _email_valido
                and not _FBCCerrar.objects.filter(
                    orden=orden, tipo='satisfaccion'
                ).exists()
            ):
                _fb_cerrar = _FBCCerrar.objects.create(
                    orden=orden,
                    token=_secrets_cerrar.token_urlsafe(32),
                    tipo='satisfaccion',
                )
                request.session['feedback_satisfaccion_pendiente_id'] = _fb_cerrar.pk
                request.session['feedback_satisfaccion_email'] = _email_cerrar
                _feedback_sat_creado = True

        except Exception as _e_cerrar:
            import logging as _log_cerrar
            _log_cerrar.getLogger(__name__).warning(
                f"[FEEDBACK-SAT] Error al crear encuesta para orden {orden_id}: {_e_cerrar}"
            )
        # ────────────────────────────────────────────────────────────────────

        messages.success(
            request,
            f'Orden {orden.numero_orden_interno} marcada como entregada.'
        )
        # Si hay encuesta pendiente, ir a detalle para mostrar el modal de confirmación.
        if _feedback_sat_creado:
            return redirect('servicio_tecnico:detalle_orden', orden_id=orden.id)
    else:
        messages.warning(
            request,
            f'La orden debe estar en estado "Finalizado" para poder cerrarla. Estado actual: {orden.get_estado_display()}'
        )

    # Redirigir a la lista de órdenes activas
    return redirect('servicio_tecnico:lista_activas')


@login_required
@permission_required_with_message('servicio_tecnico.change_ordenservicio')
def cerrar_todas_finalizadas(request):
    """
    Vista para cerrar todas las órdenes en estado 'finalizado'.

    Solo procesa con método POST para evitar cambios accidentales.
    """
    if request.method == 'POST':
        from django.utils import timezone
        
        # Obtener todas las órdenes finalizadas
        ordenes_finalizadas = OrdenServicio.objects.filter(estado='finalizado')
        cantidad = ordenes_finalizadas.count()
        
        if cantidad > 0:
            # Capturar IDs ANTES del update: el .update() omite save() y señales,
            # por lo que el queryset ya no coincidirá después del cambio de estado.
            _ids_bulk = list(ordenes_finalizadas.values_list('id', flat=True))

            # Actualizar todas a 'entregado'
            ordenes_finalizadas.update(
                estado='entregado',
                fecha_entrega=timezone.now()
            )

            messages.success(
                request,
                f'Se cerraron {cantidad} orden(es) finalizada(s).'
            )

            # ── Encuestas de satisfacción para cierre en lote ──────────────
            # Para el bulk, no hay flujo de modal; se envían automáticamente
            # a las órdenes con cotización aceptada o VentaMostrador con servicios
            # que tengan email de cliente válido.
            try:
                import secrets as _secrets_bulk
                from .models import FeedbackCliente as _FBCBulk
                from .tasks import enviar_feedback_satisfaccion_task
                from config.paises_config import get_pais_actual
                _uid_bulk    = request.user.pk if request.user.is_authenticated else None
                _enviadas    = 0
                _ordenes_bulk = OrdenServicio.objects.filter(
                    id__in=_ids_bulk
                ).select_related('cotizacion', 'detalle_equipo', 'venta_mostrador')
                for _ord in _ordenes_bulk:
                    try:
                        _cot = getattr(_ord, 'cotizacion', None)
                        _email_bulk = (
                            _ord.detalle_equipo.email_cliente
                            if _ord.detalle_equipo and _ord.detalle_equipo.email_cliente
                            else None
                        )
                        _email_ok = (
                            _email_bulk
                            and _email_bulk != 'cliente@ejemplo.com'
                        )
                        _ya_existe = _FBCBulk.objects.filter(
                            orden=_ord, tipo='satisfaccion'
                        ).exists()

                        if (
                            _cot is not None
                            and _cot.usuario_acepto is True
                            and not _cot.motivo_rechazo
                            and _email_ok
                            and not _ya_existe
                        ):
                            _fb_bulk = _FBCBulk.objects.create(
                                orden=_ord,
                                cotizacion=_cot,
                                token=_secrets_bulk.token_urlsafe(32),
                                tipo='satisfaccion',
                            )
                            enviar_feedback_satisfaccion_task.delay(
                                feedback_id=_fb_bulk.pk,
                                usuario_id=_uid_bulk,
                                db_alias=get_pais_actual()['db_alias'],
                            )
                            _enviadas += 1

                        elif (
                            not _ya_existe
                            and hasattr(_ord, 'venta_mostrador')
                            and _ord.venta_mostrador.tiene_al_menos_un_servicio
                            and _email_ok
                        ):
                            _fb_bulk = _FBCBulk.objects.create(
                                orden=_ord,
                                token=_secrets_bulk.token_urlsafe(32),
                                tipo='satisfaccion',
                            )
                            enviar_feedback_satisfaccion_task.delay(
                                feedback_id=_fb_bulk.pk,
                                usuario_id=_uid_bulk,
                                db_alias=get_pais_actual()['db_alias'],
                            )
                            _enviadas += 1

                    except Exception as _e_ord:
                        import logging as _log_ord
                        _log_ord.getLogger(__name__).warning(
                            f"[FEEDBACK-SAT-BULK] Error para orden {_ord.pk}: {_e_ord}"
                        )
                if _enviadas > 0:
                    messages.info(
                        request,
                        f'📧 {_enviadas} encuesta(s) de satisfacción enviadas automáticamente.'
                    )
            except Exception as _e_bulk:
                import logging as _log_bulk
                _log_bulk.getLogger(__name__).warning(
                    f"[FEEDBACK-SAT-BULK] Error general en cierre masivo: {_e_bulk}"
                )
            # ────────────────────────────────────────────────────────────────
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


@login_required
@permission_required_with_message('servicio_tecnico.change_ordenservicio')
def cerrar_finalizados_garantia(request):
    """
    Vista para cerrar únicamente las órdenes finalizadas que están DENTRO de garantía.
    
    Filtra por estado='finalizado' y es_fuera_garantia=False.
    NO dispara envío de correos ni encuestas de satisfacción.
    Solo procesa con método POST para evitar cambios accidentales.
    """
    if request.method == 'POST':
        from django.utils import timezone

        # Solo órdenes finalizadas que están DENTRO de garantía
        ordenes_garantia = OrdenServicio.objects.filter(
            estado='finalizado',
            es_fuera_garantia=False
        )
        cantidad = ordenes_garantia.count()

        if cantidad > 0:
            ordenes_garantia.update(
                estado='entregado',
                fecha_entrega=timezone.now()
            )
            messages.success(
                request,
                f'Se cerraron {cantidad} orden(es) finalizada(s) de garantía.'
            )
        else:
            messages.info(
                request,
                'No hay órdenes finalizadas de garantía para cerrar.'
            )
    else:
        messages.warning(
            request,
            'Método no permitido. Use el botón correspondiente.'
        )

    return redirect('servicio_tecnico:lista_activas')


# ============================================================================
# VISTA DE DETALLES DE ORDEN (Vista Principal y Más Compleja)
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def detalle_orden(request, orden_id):
    """
    Vista completa de detalles de una orden de servicio.

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
            # Obtener el valor ANTES de crear el formulario
            # Hacemos una consulta directa a la BD para tener el valor real
            from .models import DetalleEquipo
            detalle_bd = DetalleEquipo.objects.get(pk=orden.detalle_equipo.pk)
            fecha_fin_anterior = detalle_bd.fecha_fin_diagnostico
            
            form_config = ConfiguracionAdicionalForm(
                request.POST,
                instance=orden.detalle_equipo
            )
            
            if form_config.is_valid():
                # ===============================================================
                # Guardar configuración adicional
                # ===============================================================
                # EXPLICACIÓN PARA PRINCIPIANTES:
                # El texto del diagnóstico (diagnostico_sic) se guarda tal cual
                # lo escribió el técnico, sin modificaciones. La detección de
                # piezas y números de parte la hace el TypeScript en el navegador
                # cuando el usuario da clic en "Detectar Piezas" en el modal.
                detalle_actualizado = form_config.save()
                
                # ===================================================================
                # NUEVA FUNCIONALIDAD: Cambiar estado al finalizar diagnóstico
                # ===================================================================
                # Verificar si se acaba de agregar la fecha de fin de diagnóstico
                fecha_fin_nueva = detalle_actualizado.fecha_fin_diagnostico
                
                if not fecha_fin_anterior and fecha_fin_nueva:
                    # Se agregó la fecha de fin de diagnóstico por primera vez
                    # → Cambiar estado a "equipo_diagnosticado"
                    estado_anterior = orden.estado
                    orden.estado = 'equipo_diagnosticado'
                    orden.save()
                    
                    # Registrar el cambio de estado en el historial
                    registrar_historial(
                        orden=orden,
                        tipo_evento='estado',
                        usuario=empleado_actual,
                        comentario=f"🔄 Estado cambiado automáticamente: '{dict(orden._meta.get_field('estado').choices).get(estado_anterior)}' → 'Equipo Diagnosticado' (Diagnóstico finalizado)",
                        es_sistema=True
                    )
                    
                    # Mensaje informativo al usuario
                    messages.info(
                        request,
                        '🔍 Estado actualizado automáticamente a: "Equipo Diagnosticado"'
                    )
                # ===================================================================
                
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
                    else:
                        messages.warning(
                            request,
                            '⚠️ Orden marcada como reingreso, pero no se pudo crear la incidencia de ScoreCard '
                            'porque no hay inspector de calidad ni técnico asignado. Asigna un responsable y vuelve a guardar.'
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
                        f'[OK] Responsables actualizados: {" | ".join(cambios)}'
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
        # FORMULARIO 6: Subir Imágenes - MEJORADO CON LOGGING
        # ------------------------------------------------------------------------
        elif form_type == 'subir_imagenes':
            # LOGGING: Información inicial para diagnóstico
            logger.info(f"📷 Inicio procesamiento de imágenes para orden {orden.numero_orden_interno}")
            logger.info(f"   - POST data: {request.POST.keys()}")
            logger.info(f"   - FILES data: {request.FILES.keys()}")
            logger.info(f"   - Content-Type: {request.content_type}")
            
            # Verificar si hay archivos en la petición
            if not request.FILES:
                logger.warning("⚠️ No se recibieron archivos en request.FILES")
                return JsonResponse({
                    'success': False,
                    'error': 'No se recibieron imágenes. Verifica que hayas seleccionado archivos.',
                    'debug_info': {
                        'content_type': request.content_type,
                        'post_keys': list(request.POST.keys()),
                        'files_keys': list(request.FILES.keys())
                    }
                })
            
            form_imagenes = SubirImagenesForm(request.POST, request.FILES)
            
            if form_imagenes.is_valid():
                # Procesar imágenes (múltiples archivos)
                imagenes_files = request.FILES.getlist('imagenes')
                tipo_imagen = form_imagenes.cleaned_data['tipo']
                descripcion = form_imagenes.cleaned_data.get('descripcion', '')
                
                logger.info(f"   - Tipo de imagen: {tipo_imagen}")
                logger.info(f"   - Cantidad de archivos recibidos: {len(imagenes_files)}")
                
                # Validar que haya imágenes
                if not imagenes_files:
                    logger.warning("⚠️ Lista de imágenes vacía")
                    return JsonResponse({
                        'success': False,
                        'error': 'No se detectaron imágenes en el formulario. Intenta seleccionarlas nuevamente.',
                    })
                
                # Validar cantidad máxima (30 imágenes POR CARGA, no total)
                imagenes_a_subir = len(imagenes_files)
                
                if imagenes_a_subir > 30:
                    logger.warning(f"⚠️ Intentó subir {imagenes_a_subir} imágenes (máximo: 30)")
                    # Retornar JSON con error en lugar de redirect
                    return JsonResponse({
                        'success': False,
                        'error': f'Solo puedes subir máximo 30 imágenes por carga. Seleccionaste {imagenes_a_subir}. Si necesitas más, realiza otra carga después.'
                    })
                
                # Procesar cada imagen
                imagenes_guardadas = 0
                imagenes_omitidas = []
                errores_procesamiento = []
                
                logger.info(f"📸 Procesando {len(imagenes_files)} imagen(es) | Tamaño total: {sum(f.size for f in imagenes_files)/(1024*1024):.2f}MB")
                
                try:
                    for idx, imagen_file in enumerate(imagenes_files):
                        logger.info(f"   [{idx+1}/{len(imagenes_files)}] Procesando: {imagen_file.name}")
                        
                        # Validar tamaño (50MB = 50 * 1024 * 1024 bytes)
                        if imagen_file.size > 50 * 1024 * 1024:
                            logger.warning(f"   ⚠️ Imagen {imagen_file.name} excede 50MB: {imagen_file.size / (1024*1024):.2f}MB")
                            imagenes_omitidas.append(f"{imagen_file.name} (tamaño: {imagen_file.size / (1024*1024):.2f}MB)")
                            continue
                        
                        # Validar formato de imagen
                        try:
                            from PIL import Image as PILImage
                            img_test = PILImage.open(imagen_file)
                            img_test.verify()  # Verificar que sea una imagen válida
                            imagen_file.seek(0)  # Resetear el cursor del archivo
                        except Exception as e:
                            logger.error(f"   ❌ Imagen inválida {imagen_file.name}: {str(e)}")
                            errores_procesamiento.append(f"{imagen_file.name}: No es una imagen válida o está corrupta")
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
                            logger.info(f"   ✅ Guardada: {imagen_file.name} (ID: {imagen_orden.pk})")
                        except Exception as e:
                            logger.error(f"   ❌ Error al guardar {imagen_file.name}: {str(e)}")
                            errores_procesamiento.append(f"{imagen_file.name}: {str(e)}")
                    
                    # Preparar respuesta
                    if imagenes_guardadas > 0:
                        logger.info(f"✅ Procesamiento completado: {imagenes_guardadas}/{len(imagenes_files)} imágenes guardadas")
                        
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
                        
                        # Si se suben imágenes de INGRESO → Cambiar estado según tipo de orden
                        # VentaMostrador: pasan directo a reparación (sin diagnóstico previo)
                        # Órdenes normales: pasan a diagnóstico
                        if tipo_imagen == 'ingreso':
                            if orden.tipo_servicio == 'venta_mostrador' and estado_anterior != 'reparacion':
                                orden.estado = 'reparacion'
                                cambio_realizado = True
                                mensaje_estado = f'Estado actualizado: {dict(ESTADO_ORDEN_CHOICES).get(estado_anterior)} → En Reparación'

                                # Registrar cambio automático en historial
                                HistorialOrden.objects.create(
                                    orden=orden,
                                    tipo_evento='estado',
                                    comentario=f'Cambio automático de estado: {dict(ESTADO_ORDEN_CHOICES).get(estado_anterior)} → En Reparación (imágenes de ingreso cargadas — Venta Mostrador)',
                                    usuario=empleado_actual,
                                    es_sistema=True
                                )
                            elif orden.tipo_servicio != 'venta_mostrador' and estado_anterior != 'diagnostico':
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
                        
                        # Si se suben imágenes de REPARACIÓN → Cambiar a "Control de Calidad"
                        # Aplica a todos los tipos de orden (garantía, OOW, diagnóstico, venta mostrador)
                        elif tipo_imagen == 'reparacion' and estado_anterior != 'control_calidad':
                            orden.estado = 'control_calidad'
                            cambio_realizado = True
                            mensaje_estado = f'Estado actualizado: {dict(ESTADO_ORDEN_CHOICES).get(estado_anterior)} → Control de Calidad'

                            # Registrar cambio automático en historial
                            HistorialOrden.objects.create(
                                orden=orden,
                                tipo_evento='estado',
                                comentario=f'Cambio automático de estado: {dict(ESTADO_ORDEN_CHOICES).get(estado_anterior)} → Control de Calidad (imágenes de reparación cargadas)',
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
                            'cambio_estado': cambio_realizado,
                            # Flag para el frontend: indica si ya existe un envío previo de
                            # imágenes de egreso por correo (para mostrar u ocultar el modal)
                            'egreso_correo_ya_enviado': (
                                HistorialOrden.objects
                                .filter(orden=orden, tipo_evento='email')
                                .filter(comentario__icontains='imágenes de egreso')
                                .exists()
                            ) if tipo_imagen == 'egreso' else False,
                             # Si la orden ya tiene los 4 tipos de fotos (para disparar modal rewind)
                            'tiene_4_tipos_fotos': (
                                {'ingreso', 'diagnostico', 'reparacion', 'egreso'}.issubset(
                                    set(orden.imagenes.values_list('tipo', flat=True).distinct())
                                )
                            ) if tipo_imagen == 'egreso' else False,
                            # Venta mostrador: solo requiere 3 tipos (sin diagnóstico)
                            'tiene_3_tipos_fotos': (
                                orden.tipo_servicio == 'venta_mostrador' and
                                {'ingreso', 'reparacion', 'egreso'}.issubset(
                                    set(orden.imagenes.values_list('tipo', flat=True).distinct())
                                )
                            ) if tipo_imagen == 'egreso' else False,
                            # Si el video rewind ya fue enviado al cliente
                            'rewind_ya_enviado': (
                                orden.historial.filter(
                                    tipo_evento='email',
                                    comentario__icontains='video rewind'
                                ).exists()
                            ) if tipo_imagen == 'egreso' else False,
                            'tipo_imagen': tipo_imagen,
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
                    logger.critical(f"❌ ERROR CRÍTICO AL PROCESAR IMÁGENES: {error_detallado}")
                    return JsonResponse({
                        'success': False,
                        'error': f'Error inesperado al procesar imágenes: {str(e)}',
                        'error_type': type(e).__name__,
                        'imagenes_guardadas': imagenes_guardadas,
                        'traceback': error_detallado if request.user.is_superuser else None  # Solo para superusers
                    }, status=500)
            else:
                # Formulario no válido
                logger.error(f"❌ Formulario de imágenes inválido: {form_imagenes.errors}")
                return JsonResponse({
                    'success': False,
                    'error': 'Error en el formulario. Verifica los datos enviados.',
                    'form_errors': dict(form_imagenes.errors)
                })
        
        # ------------------------------------------------------------------------
        # FORMULARIO: Subir Video de Evidencia
        # ------------------------------------------------------------------------
        # EXPLICACIÓN DEL CAMBIO (asíncrono con Celery):
        # Antes, este bloque llamaba a comprimir_y_guardar_video() de forma síncrona,
        # lo que mantenía el request HTTP abierto mientras FFmpeg comprimía el video
        # (hasta 5 minutos). Con videos 1080p, Cloudflare cortaba la conexión.
        #
        # Ahora el flujo es:
        #   1. Guardar el archivo crudo en /tmp (rápido)
        #   2. Despachar comprimir_video_evidencia_task.delay() a Celery
        #   3. Responder al cliente INMEDIATAMENTE con task_queued=True
        #   4. Celery comprime en segundo plano y notifica al usuario cuando termina
        #      (campanita siempre + push si el usuario tiene suscripciones activas)
        elif form_type == 'subir_video':
            import uuid as _uuid_video
            logger.info(f"🎥 Video recibido para Orden {orden.numero_orden_interno} — encolando en Celery")

            # Verificar que llegó el archivo
            if 'video' not in request.FILES:
                return JsonResponse({
                    'success': False,
                    'error': 'No se recibió ningún archivo de video.',
                })

            # Validar formulario (incluye tamaño, extensión y content-type en clean_video())
            form_video = SubirVideoForm(request.POST, request.FILES)
            if not form_video.is_valid():
                logger.error(f"❌ Formulario de video inválido: {form_video.errors}")
                return JsonResponse({
                    'success': False,
                    'error': 'Error en el formulario de video.',
                    'form_errors': dict(form_video.errors),
                })

            tipo_video  = form_video.cleaned_data['tipo']
            descripcion = form_video.cleaned_data.get('descripcion', '')
            video_file  = form_video.cleaned_data['video']  # ya validado por clean_video()

            # Orientación del dispositivo al grabar (0/90/180/270).
            # Capturada por el sensor del cliente en camara_video.ts y enviada en el form.
            # FFmpeg usará este valor para aplicar el transpose correcto al comprimir.
            try:
                orientacion_video = int(request.POST.get('orientacion_video', 0))
                if orientacion_video not in (0, 90, 180, 270):
                    orientacion_video = 0
            except (ValueError, TypeError):
                orientacion_video = 0

            # ── Guardar el archivo crudo en MEDIA_ROOT/video_tmp/ ────────────────
            # IMPORTANTE: Usamos MEDIA_ROOT en lugar de /tmp porque los archivos
            # en /tmp se limpian periódicamente por el SO (systemd-tmpfiles-clean).
            # Si Celery tarda en procesar, el archivo de /tmp ya no existe.
            # MEDIA_ROOT es un directorio persistente al que el worker Celery tiene acceso.
            # La tarea Celery es responsable de borrar el archivo en su bloque finally.
            try:
                extension_entrada = os.path.splitext(video_file.name)[1].lower() or '.webm'
                video_tmp_dir = os.path.join(settings.MEDIA_ROOT, 'video_tmp')
                os.makedirs(video_tmp_dir, exist_ok=True)
                nombre_tmp = f"sigmavideo_{_uuid_video.uuid4().hex[:8]}{extension_entrada}"
                archivo_tmp_path = os.path.join(video_tmp_dir, nombre_tmp)
                with open(archivo_tmp_path, 'wb') as tmp_in:
                    for chunk in video_file.chunks():
                        tmp_in.write(chunk)
            except Exception as e:
                logger.error(f"❌ No se pudo guardar video en /tmp: {e}")
                return JsonResponse({
                    'success': False,
                    'error': 'Error al recibir el archivo de video. Intenta de nuevo.',
                }, status=500)

            # ── Despachar la tarea Celery ─────────────────────────────────────────
            try:
                from .tasks import comprimir_video_evidencia_task
                from config.paises_config import get_pais_actual
                comprimir_video_evidencia_task.delay(
                    archivo_tmp_path=archivo_tmp_path,
                    nombre_original=video_file.name,
                    tamano_bytes=video_file.size,
                    orden_id=orden.pk,
                    tipo=tipo_video,
                    descripcion=descripcion,
                    empleado_id=empleado_actual.pk,
                    usuario_id=request.user.pk,
                    orientacion_video=orientacion_video,
                    db_alias=get_pais_actual()['db_alias'],
                )
                logger.info(
                    f"✅ Tarea Celery encolada para video de Orden {orden.numero_orden_interno} "
                    f"({round(video_file.size / (1024*1024), 1)} MB, tipo={tipo_video})"
                )
            except Exception as e:
                # Si Celery no está disponible (Redis caído, etc.), limpiar el tmp
                # y devolver error para que el técnico sepa que debe reintentar
                logger.error(f"❌ No se pudo encolar tarea Celery: {e}")
                try:
                    if os.path.exists(archivo_tmp_path):
                        os.remove(archivo_tmp_path)
                except Exception:
                    pass
                return JsonResponse({
                    'success': False,
                    'error': 'No se pudo encolar el video para procesamiento. Intenta de nuevo.',
                }, status=500)

            # ── Responder inmediatamente al cliente ───────────────────────────────
            return JsonResponse({
                'success': True,
                'task_queued': True,
                'message': (
                    'Video recibido. Se procesará en segundo plano. '
                    'Recibirás una notificación cuando esté listo.'
                ),
            })

        # ------------------------------------------------------------------------
        # FORMULARIO 7: Editar Información Principal del Equipo
        # ------------------------------------------------------------------------
        elif form_type == 'editar_info_equipo':
            # Capturar el email actual ANTES de guardar el formulario,
            # para poder detectar si cambió después de guardar.
            email_anterior = (
                orden.detalle_equipo.email_cliente
                if orden.detalle_equipo and orden.detalle_equipo.email_cliente
                else None
            )

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

                # ── Reenviar enlace de seguimiento si el email cambió ──────────
                # Solo aplica a órdenes fuera de garantía que ya tienen enlace.
                # Lógica:
                #   1. Si el correo nunca se envió y hay email nuevo → enviar.
                #   2. Si el correo ya se envió, extraemos a qué dirección
                #      se envió del historial. Si el email nuevo es diferente
                #      → resetear correo_enviado y reenviar al nuevo destino.
                try:
                    if orden.es_fuera_garantia:
                        email_nuevo = detalle_actualizado.email_cliente or ''
                        if email_nuevo:
                            from .models import EnlaceSeguimientoCliente
                            enlace_qs = EnlaceSeguimientoCliente.objects.filter(orden=orden)
                            enlace_obj = enlace_qs.first()

                            debe_enviar = False

                            if enlace_obj is None or not enlace_obj.correo_enviado:
                                # Caso 1: nunca se envió (o no existe enlace aún)
                                debe_enviar = True
                            else:
                                # Caso 2: ya se envió — buscar el email destino en historial
                                import re as _re
                                historial_envio = HistorialOrden.objects.filter(
                                    orden=orden,
                                    tipo_evento='email',
                                    comentario__icontains='Enlace de seguimiento público enviado',
                                ).order_by('fecha_evento').first()

                                email_enviado_previo = None
                                if historial_envio:
                                    _match = _re.search(
                                        r'enviado al cliente \((.+?)\)',
                                        historial_envio.comentario,
                                    )
                                    if _match:
                                        email_enviado_previo = _match.group(1).strip().lower()

                                if email_enviado_previo and email_nuevo.lower() != email_enviado_previo:
                                    # El email cambió respecto al que ya recibió el link
                                    EnlaceSeguimientoCliente.objects.filter(orden=orden).update(
                                        correo_enviado=False
                                    )
                                    debe_enviar = True

                            if debe_enviar:
                                from .tasks import enviar_seguimiento_cliente_task
                                from config.paises_config import get_pais_actual
                                enviar_seguimiento_cliente_task.delay(
                                    orden_id=orden.id,
                                    usuario_id=request.user.id,
                                    db_alias=get_pais_actual()['db_alias'],
                                )
                                messages.info(
                                    request,
                                    f'📧 Enlace de seguimiento enviado a {email_nuevo}.'
                                )
                except Exception:
                    pass  # No bloquear la actualización si falla el reenvío
                
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
            else:
                messages.error(request, '❌ Error al actualizar la información del equipo.')
        
        # ------------------------------------------------------------------------
        # FORMULARIO 8: Guardar Mano de Obra (SIN crear cotización ni cambiar estado)
        # ------------------------------------------------------------------------
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # La mano de obra vive en OrdenServicio.costo_mano_obra. Guardarla aquí
        # NO crea Cotizacion ni cambia el estado de la orden. Si ya existe
        # cotización, también sincronizamos Cotizacion.costo_mano_obra.
        elif form_type == 'guardar_mano_obra':
            form_guardar_mo = GuardarManoObraForm(request.POST, instance=orden)
            if form_guardar_mo.is_valid():
                costo_anterior = orden.costo_mano_obra
                orden_actualizada = form_guardar_mo.save()
                nuevo_costo = orden_actualizada.costo_mano_obra

                # Si ya hay cotización, mantener ambos valores alineados
                if hasattr(orden_actualizada, 'cotizacion'):
                    cotizacion_mo = orden_actualizada.cotizacion
                    cotizacion_mo.costo_mano_obra = nuevo_costo
                    cotizacion_mo.save(update_fields=['costo_mano_obra'])

                messages.success(
                    request,
                    f'✅ Mano de obra guardada: ${costo_anterior} → ${nuevo_costo}. '
                    f'La cotización no se crea automáticamente.'
                )
                HistorialOrden.objects.create(
                    orden=orden_actualizada,
                    tipo_evento='cotizacion',
                    comentario=(
                        f'Mano de obra guardada en la orden: '
                        f'${costo_anterior} → ${nuevo_costo} (sin crear cotización)'
                    ),
                    usuario=empleado_actual,
                    es_sistema=False,
                )
            else:
                messages.error(request, '❌ Error al guardar la mano de obra. Revisa el valor ingresado.')

            return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

        # ------------------------------------------------------------------------
        # FORMULARIO 8.1: Generar Cotización (solo crea Cotizacion; NO cambia estado)
        # ------------------------------------------------------------------------
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Este paso crea el registro Cotizacion (OneToOne) y copia la mano de obra
        # desde la orden. Almacén también puede crear la cotización al vincular
        # una SolicitudCotizacion. Aquí NO se cambia el estado de la orden:
        # el técnico lo hace manualmente cuando corresponda.
        elif form_type in ('crear_cotizacion', 'generar_cotizacion'):
            if hasattr(orden, 'cotizacion'):
                messages.warning(
                    request,
                    '⚠️ Esta orden ya tiene una cotización. Puedes agregar piezas o editar la mano de obra.'
                )
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

            # Si el usuario envió un valor de MO en el mismo POST, lo guardamos
            # en la orden antes de crear la cotización (opcional, por comodidad).
            costo_mo_post = request.POST.get('costo_mano_obra', '').strip()
            if costo_mo_post:
                form_mo_previo = GuardarManoObraForm(request.POST, instance=orden)
                if form_mo_previo.is_valid():
                    orden = form_mo_previo.save()
                else:
                    messages.error(request, '❌ Valor de mano de obra inválido. No se generó la cotización.')
                    return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

            # Crear Cotizacion copiando la MO ya registrada en la orden
            cotizacion = Cotizacion.objects.create(
                orden=orden,
                costo_mano_obra=orden.costo_mano_obra or Decimal('0.00'),
            )

            messages.success(
                request,
                f'✅ Cotización generada con mano de obra: ${cotizacion.costo_mano_obra}. '
                f'Ahora puedes agregar piezas. El estado de la orden no se cambió automáticamente.'
            )
            HistorialOrden.objects.create(
                orden=orden,
                tipo_evento='cotizacion',
                comentario=(
                    f'Cotización generada - Mano de obra copiada de la orden: '
                    f'${cotizacion.costo_mano_obra} (sin cambio automático de estado)'
                ),
                usuario=empleado_actual,
                es_sistema=False,
            )
            return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

        # ------------------------------------------------------------------------
        # FORMULARIO 8.5: Editar Fecha de Envío de Cotización
        # ------------------------------------------------------------------------
        elif form_type == 'editar_fecha_envio':
            if not hasattr(orden, 'cotizacion'):
                messages.error(request, '❌ No existe una cotización para esta orden.')
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

            fecha_envio_str = request.POST.get('fecha_envio', '').strip()
            if fecha_envio_str:
                try:
                    from datetime import datetime as dt
                    nueva_fecha = dt.strptime(fecha_envio_str, '%Y-%m-%dT%H:%M')
                    from django.utils import timezone
                    if timezone.is_naive(nueva_fecha):
                        nueva_fecha = timezone.make_aware(nueva_fecha)

                    cotizacion = orden.cotizacion
                    fecha_anterior = cotizacion.fecha_envio
                    cotizacion.fecha_envio = nueva_fecha
                    cotizacion.save(update_fields=['fecha_envio'])

                    messages.success(request, f'✅ Fecha de envío actualizada a: {nueva_fecha.strftime("%d/%m/%Y %H:%M")}')

                    HistorialOrden.objects.create(
                        orden=orden,
                        tipo_evento='cotizacion',
                        comentario=f'Fecha de envío de cotización editada: {fecha_anterior.strftime("%d/%m/%Y %H:%M") if fecha_anterior else "N/A"} → {nueva_fecha.strftime("%d/%m/%Y %H:%M")}',
                        usuario=empleado_actual,
                        es_sistema=False
                    )
                except (ValueError, TypeError) as e:
                    messages.error(request, f'❌ Formato de fecha inválido: {str(e)}')
            else:
                messages.error(request, '❌ No se proporcionó una fecha válida.')

            return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

        # ------------------------------------------------------------------------
        # FORMULARIO 8.6: Editar Costo de Mano de Obra (sincroniza orden + cotización)
        # ------------------------------------------------------------------------
        elif form_type == 'editar_mano_obra':
            if not hasattr(orden, 'cotizacion'):
                messages.error(request, '❌ No existe una cotización para esta orden.')
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

            costo_mano_obra_str = request.POST.get('costo_mano_obra', '').strip()
            if costo_mano_obra_str:
                try:
                    from decimal import Decimal, InvalidOperation
                    nuevo_costo = Decimal(costo_mano_obra_str)
                    if nuevo_costo < 0:
                        messages.error(request, '❌ El costo de mano de obra no puede ser negativo.')
                        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

                    cotizacion = orden.cotizacion
                    costo_anterior = cotizacion.costo_mano_obra
                    # Sincronizar ambos: cotización y orden (fuente de verdad de la MO)
                    cotizacion.costo_mano_obra = nuevo_costo
                    cotizacion.save(update_fields=['costo_mano_obra'])
                    orden.costo_mano_obra = nuevo_costo
                    orden.save(update_fields=['costo_mano_obra'])

                    messages.success(request, f'✅ Mano de obra actualizada: ${costo_anterior} → ${nuevo_costo}')

                    HistorialOrden.objects.create(
                        orden=orden,
                        tipo_evento='cotizacion',
                        comentario=f'Costo de mano de obra editado: ${costo_anterior} → ${nuevo_costo}',
                        usuario=empleado_actual,
                        es_sistema=False
                    )
                except (InvalidOperation, ValueError, TypeError) as e:
                    messages.error(request, f'❌ Valor de mano de obra inválido: {str(e)}')
            else:
                messages.error(request, '❌ No se proporcionó un valor válido para mano de obra.')

            return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
        
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
                
                # Guardar la cotización
                cotizacion_actualizada = form_gestionar_cotizacion.save()
                
                # NUEVO: Actualizar el estado de cada pieza según la decisión
                todas_las_piezas = cotizacion_actualizada.piezas_cotizadas.all()
                piezas_aceptadas_count = 0
                piezas_rechazadas_count = 0
                
                if accion == 'aceptar':
                    # Si acepta, actualizar cada pieza según si fue seleccionada
                    # NOTA: Solo procesar piezas si existen en la cotización
                    if todas_las_piezas.exists():
                        for pieza in todas_las_piezas:
                            if str(pieza.id) in piezas_seleccionadas_ids:
                                pieza.aceptada_por_cliente = True
                                piezas_aceptadas_count += 1
                            else:
                                pieza.aceptada_por_cliente = False
                                pieza.motivo_rechazo_pieza = 'Cliente decidió no incluir esta pieza'
                                piezas_rechazadas_count += 1
                            pieza.save()
                        
                        # ============================================================
                        # ✨ NUEVO: CREACIÓN AUTOMÁTICA DE SEGUIMIENTOS (Nov 2025)
                        # ============================================================
                        # Después de marcar las piezas como aceptadas, crear automáticamente
                        # los registros de SeguimientoPieza agrupados por proveedor
                        # para facilitar el tracking de pedidos.
                        
                        from .models import SeguimientoPieza
                        from collections import defaultdict
                        from datetime import date, timedelta
                        
                        # Obtener solo las piezas aceptadas que tienen proveedor
                        piezas_aceptadas_con_proveedor = todas_las_piezas.filter(
                            aceptada_por_cliente=True
                        ).exclude(proveedor='').exclude(proveedor__isnull=True)
                        
                        if piezas_aceptadas_con_proveedor.exists():
                            # Agrupar piezas por proveedor
                            piezas_por_proveedor = defaultdict(list)
                            for pieza in piezas_aceptadas_con_proveedor:
                                piezas_por_proveedor[pieza.proveedor].append(pieza)
                            
                            # Crear un SeguimientoPieza por cada proveedor
                            seguimientos_creados = 0
                            for proveedor, piezas_grupo in piezas_por_proveedor.items():
                                # Construir descripción de las piezas
                                descripcion_piezas = '\n'.join([
                                    f"• {pieza.componente.nombre} × {pieza.cantidad} (${pieza.costo_total})"
                                    for pieza in piezas_grupo
                                ])
                                
                                # Crear el seguimiento
                                seguimiento = SeguimientoPieza.objects.create(
                                    cotizacion=cotizacion_actualizada,
                                    proveedor=proveedor,
                                    descripcion_piezas=descripcion_piezas,
                                    fecha_pedido=date.today(),
                                    fecha_entrega_estimada=date.today() + timedelta(days=7),  # 7 días por defecto
                                    estado='pedido',
                                    notas_seguimiento=f'Seguimiento creado automáticamente al aceptar cotización'
                                )
                                
                                # Asociar las piezas al seguimiento
                                seguimiento.piezas.set(piezas_grupo)
                                seguimientos_creados += 1
                            
                            # Notificar al usuario que se crearon seguimientos
                            if seguimientos_creados > 0:
                                messages.info(
                                    request,
                                    f'📦 Se crearon automáticamente {seguimientos_creados} registro(s) de seguimiento '
                                    f'de piezas agrupados por proveedor. Puedes editarlos para agregar número de pedido '
                                    f'y ajustar fechas.'
                                )
                                
                                # Registrar en historial
                                HistorialOrden.objects.create(
                                    orden=orden,
                                    tipo_evento='cotizacion',
                                    comentario=f'📦 Sistema creó automáticamente {seguimientos_creados} seguimiento(s) de piezas agrupados por proveedor',
                                    usuario=empleado_actual,
                                    es_sistema=True
                                )
                        # Fin de creación automática de seguimientos
                        # ============================================================
                elif accion == 'rechazar':
                    # Si rechaza toda la cotización, todas las piezas se rechazan
                    for pieza in todas_las_piezas:
                        pieza.aceptada_por_cliente = False
                        pieza.motivo_rechazo_pieza = cotizacion_actualizada.get_motivo_rechazo_display()
                        pieza.save()
                        piezas_rechazadas_count += 1
                
                # Mensaje según la decisión
                if accion == 'aceptar':
                    # Obtener información del descuento
                    se_aplico_descuento = cotizacion_actualizada.descontar_mano_obra
                    
                    # Construir mensaje según si hay piezas o solo mano de obra
                    if todas_las_piezas.exists():
                        mensaje_piezas = f'{piezas_aceptadas_count} pieza(s) aceptada(s)'
                        if piezas_rechazadas_count > 0:
                            mensaje_piezas += f' y {piezas_rechazadas_count} pieza(s) rechazada(s)'
                        
                        # Agregar información de descuento si aplica
                        if se_aplico_descuento:
                            mensaje_completo = f'✅ Cotización ACEPTADA por el cliente ({mensaje_piezas}). 🎁 Mano de obra DESCONTADA como beneficio (ahorro: ${cotizacion_actualizada.costo_mano_obra}).'
                        else:
                            mensaje_completo = f'✅ Cotización ACEPTADA por el cliente ({mensaje_piezas}). Continúa con la reparación.'
                    else:
                        # Solo hay mano de obra
                        if se_aplico_descuento:
                            mensaje_completo = f'✅ Cotización ACEPTADA por el cliente (Solo mano de obra). 🎁 Diagnóstico GRATUITO como beneficio (ahorro: ${cotizacion_actualizada.costo_mano_obra}).'
                        else:
                            mensaje_completo = f'✅ Cotización ACEPTADA por el cliente (Solo mano de obra: ${cotizacion_actualizada.costo_mano_obra}). Continúa con la reparación.'
                    
                    messages.success(request, mensaje_completo)
                    
                    # 🆕 ACTUALIZACIÓN (Oct 2025): Cambiar estado a "Cliente Acepta Cotización"
                    # Independientemente de si hay piezas pendientes o no, el flujo ahora
                    # requiere que primero pase por este estado antes de ir a reparación
                    nuevo_estado = 'cliente_acepta_cotizacion'
                    mensaje_estado = 'Cliente Acepta Cotización'
                    
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
                            comentario=f'Cambio automático: cotización aceptada por el cliente',
                            usuario=empleado_actual,
                            es_sistema=True
                        )
                    
                    # Registrar en historial con detalle
                    if todas_las_piezas.exists():
                        # Construir comentario con información de descuento
                        if cotizacion_actualizada.descontar_mano_obra:
                            comentario_historial = (
                                f'✅ Cliente ACEPTÓ la cotización - {piezas_aceptadas_count} pieza(s) aceptada(s)\n'
                                f'   💰 Piezas: ${cotizacion_actualizada.costo_piezas_aceptadas}\n'
                                f'   🎁 Mano de obra DESCONTADA: ${cotizacion_actualizada.costo_mano_obra} (GRATIS)\n'
                                f'   📊 Total a pagar: ${cotizacion_actualizada.costo_total_final} (ahorro de ${cotizacion_actualizada.monto_descuento_mano_obra})'
                            )
                        else:
                            comentario_historial = (
                                f'✅ Cliente ACEPTÓ la cotización - {piezas_aceptadas_count} pieza(s) aceptada(s)\n'
                                f'   💰 Total: ${cotizacion_actualizada.costo_piezas_aceptadas + cotizacion_actualizada.costo_mano_obra}'
                            )
                    else:
                        # Solo mano de obra
                        if cotizacion_actualizada.descontar_mano_obra:
                            comentario_historial = (
                                f'✅ Cliente ACEPTÓ la cotización - Solo mano de obra\n'
                                f'   🎁 Diagnóstico GRATUITO como beneficio (ahorro: ${cotizacion_actualizada.costo_mano_obra})\n'
                                f'   📊 Total a pagar: $0.00'
                            )
                        else:
                            comentario_historial = f'Cliente ACEPTÓ la cotización - Solo mano de obra - Total: ${cotizacion_actualizada.costo_mano_obra}'
                    
                    HistorialOrden.objects.create(
                        orden=orden,
                        tipo_evento='cotizacion',
                        comentario=comentario_historial,
                        usuario=empleado_actual,
                        es_sistema=False
                    )
                
                elif accion == 'rechazar':
                    motivo = cotizacion_actualizada.get_motivo_rechazo_display()
                    motivo_clave = cotizacion_actualizada.motivo_rechazo
                    detalle_rechazo = cotizacion_actualizada.detalle_rechazo
                    
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
                    if detalle_rechazo:
                        comentario_historial += f' | Detalle: {detalle_rechazo}'
                    
                    HistorialOrden.objects.create(
                        orden=orden,
                        tipo_evento='cotizacion',
                        comentario=comentario_historial,
                        usuario=empleado_actual,
                        es_sistema=False
                    )

                    # ── SISTEMA DE FEEDBACK DE RECHAZO ──────────────────────────
                    # Motivos que requieren correo con link de feedback:
                    MOTIVOS_CON_FEEDBACK = {
                        'costo_alto', 'muchas_piezas', 'tiempo_largo',
                        'falta_justificacion', 'no_vale_pena', 'rechazo_sin_decision',
                        'no_especifica_motivo', 'no_autorizado_por_empresa', 'otro',
                    }
                    # Motivos que envían correo informativo (sin link de feedback):
                    MOTIVOS_VIGENCIA_VENCIDA = {'falta_de_respuesta'}
                    # Motivos que NO envían correo: no_hay_partes, solo_venta_mostrador, no_apto

                    email_cliente_actual = (
                        orden.detalle_equipo.email_cliente
                        if orden.detalle_equipo else None
                    )

                    if motivo_clave in MOTIVOS_CON_FEEDBACK and email_cliente_actual:
                        # Crear token de feedback usando django.core.signing
                        from django.core.signing import TimestampSigner
                        from .models import FeedbackCliente
                        import uuid

                        signer = TimestampSigner()
                        # El token es la firma de un UUID único
                        token_raw = str(uuid.uuid4())
                        token_firmado = signer.sign(token_raw)

                        feedback_obj = FeedbackCliente.objects.create(
                            orden=cotizacion_actualizada.orden,
                            cotizacion=cotizacion_actualizada,
                            token=token_firmado,
                            tipo='rechazo',
                            motivo_rechazo_snapshot=motivo_clave,
                            enviado_por=empleado_actual,
                        )
                        # Guardar feedback_id en sesión para que el modal en detalle_orden lo lea
                        request.session['feedback_pendiente_id'] = feedback_obj.pk
                        request.session['feedback_pendiente_email'] = email_cliente_actual

                    elif motivo_clave in MOTIVOS_VIGENCIA_VENCIDA and email_cliente_actual:
                        # Marcar en sesión que se debe enviar correo de vigencia vencida
                        request.session['vigencia_vencida_orden_id'] = orden.pk
                        request.session['vigencia_vencida_email'] = email_cliente_actual
                    # ────────────────────────────────────────────────────────────
                
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
    form_video = SubirVideoForm()
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
        'packing': orden.imagenes.filter(tipo='packing').order_by('-fecha_subida'),
    }
    
    total_imagenes = orden.imagenes.count()

    # ========================================================================
    # ORGANIZAR VIDEOS POR TIPO
    # ========================================================================

    videos_por_tipo = {
        'ingreso': orden.videos.filter(tipo='ingreso').order_by('-fecha_subida'),
        'diagnostico': orden.videos.filter(tipo='diagnostico').order_by('-fecha_subida'),
        'reparacion': orden.videos.filter(tipo='reparacion').order_by('-fecha_subida'),
        'egreso': orden.videos.filter(tipo='egreso').order_by('-fecha_subida'),
        'autorizacion': orden.videos.filter(tipo='autorizacion').order_by('-fecha_subida'),
        'packing': orden.videos.filter(tipo='packing').order_by('-fecha_subida'),
    }

    total_videos = orden.videos.count()

    # ── Video Resumen (generado por Celery — solo puede haber uno por orden) ──
    # Se pasa al template para mostrar el player si ya fue generado anteriormente
    video_resumen = orden.videos.filter(tipo='resumen').first()

    # Contar fotos de los tipos principales para saber si el botón debe habilitarse
    n_fotos_para_resumen = orden.imagenes.filter(
        tipo__in=['ingreso', 'diagnostico', 'reparacion', 'egreso']
    ).count()

    # Verificar si ya se enviaron correos de imágenes (para el estado de los botones)
    egreso_correo_ya_enviado = orden.historial.filter(
        tipo_evento='email',
        comentario__icontains='imágenes de egreso'
    ).exists()
    ingreso_correo_ya_enviado = orden.historial.filter(
        tipo_evento='email',
        comentario__icontains='imágenes de ingreso'
    ).exists()

    # ── Botón rewind: ¿tiene los tipos de fotos requeridos? ─────────────────
    # Diagnóstico: requiere los 4 tipos (ingreso + diagnóstico + reparación + egreso)
    # Venta mostrador: requiere solo 3 tipos (ingreso + reparación + egreso), sin diagnóstico
    _tipos_fotos_set = set(
        orden.imagenes.values_list('tipo', flat=True).distinct()
    )
    tiene_4_tipos_fotos = {'ingreso', 'diagnostico', 'reparacion', 'egreso'}.issubset(_tipos_fotos_set)
    tiene_3_tipos_fotos = (
        orden.tipo_servicio == 'venta_mostrador' and
        {'ingreso', 'reparacion', 'egreso'}.issubset(_tipos_fotos_set)
    )

    # ── ¿Ya se envió el correo rewind? ───────────────────────────────────────
    rewind_ya_enviado = orden.historial.filter(
        tipo_evento='email',
        comentario__icontains='video rewind'
    ).exists()
    
    # ========================================================================
    # DATOS DE COTIZACIÓN (Si existe)
    # ========================================================================
    
    # Inicializar formularios de cotización / mano de obra
    form_crear_cotizacion = None
    form_guardar_mano_obra = None
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
        # Sin cotización: formulario para guardar MO en la orden (no crea Cotizacion)
        form_guardar_mano_obra = GuardarManoObraForm(instance=orden)
        # Mantener alias legado por si algún template aún lo referencia
        form_crear_cotizacion = form_guardar_mano_obra
    # ========================================================================
    # CALCULAR SEGUIMIENTOS CON RETRASO
    # ========================================================================
    seguimientos_retrasados_count = 0
    if seguimientos_piezas:
        from django.utils import timezone
        hoy = timezone.now().date()
        for seguimiento in seguimientos_piezas:
            # Solo contar como retrasado si NO está en estado final (recibido, incorrecto, danado)
            if seguimiento.estado not in ['recibido', 'incorrecto', 'danado'] and seguimiento.fecha_entrega_estimada:
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
    # EMPLEADOS PARA COPIA EN ENVÍO DE IMÁGENES AL CLIENTE
    # ========================================================================
    # Obtener empleados de áreas CALIDAD y FRONTDESK que tengan email configurado
    # Estos empleados estarán disponibles para recibir copia del correo al cliente
    
    empleados_copia_imagenes = Empleado.objects.filter(
        Q(area='CALIDAD') | Q(area='FRONTDESK') | Q(area='CARRY IN'),
        activo=True,
        email__isnull=False
    ).exclude(
        email=''
    ).order_by('area', 'nombre_completo')
    
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
    
    # ========================================================================
    # COMPONENTES ADICIONALES PARA EL MODAL DE DIAGNÓSTICO
    # ========================================================================
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Obtenemos todos los ComponenteEquipo activos de la base de datos,
    # EXCLUYENDO los que ya están en COMPONENTES_DIAGNOSTICO_ORDEN.
    # Esto permite al usuario agregar componentes adicionales no predefinidos.
    
    # Nombres de componentes ya predefinidos
    componentes_predefinidos = [comp['componente_db'] for comp in COMPONENTES_DIAGNOSTICO_ORDEN]
    
    # Obtener ComponenteEquipo que NO están en la lista predefinida
    componentes_adicionales_disponibles = ComponenteEquipo.objects.filter(
        activo=True
    ).exclude(
        nombre__in=componentes_predefinidos
    ).values('nombre').order_by('nombre')
    
    # Convertir a lista simple de nombres para JavaScript
    componentes_adicionales_list = [comp['nombre'] for comp in componentes_adicionales_disponibles]
    
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
        'form_video': form_video,
        'form_editar_info': form_editar_info,
        
        # Formularios de Cotización
        'form_crear_cotizacion': form_crear_cotizacion,
        'form_guardar_mano_obra': form_guardar_mano_obra,
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
        
        # Historial y comentarios - ACTUALIZADO: Cargar todos (Opción A - Marzo 2026)
        'historial_automatico': historial_automatico,  # Todos los eventos
        'comentarios': comentarios[:20],  # Últimos 20 (comentarios siguen limitados)
        'total_eventos_historial': historial_automatico.count(),
        
        # Imágenes
        'imagenes_por_tipo': imagenes_por_tipo,
        'total_imagenes': total_imagenes,
        'egreso_correo_ya_enviado': egreso_correo_ya_enviado,
        'ingreso_correo_ya_enviado': ingreso_correo_ya_enviado,
        'tiene_4_tipos_fotos': tiene_4_tipos_fotos,
        'tiene_3_tipos_fotos': tiene_3_tipos_fotos,
        'rewind_ya_enviado': rewind_ya_enviado,

        # Videos
        'videos_por_tipo': videos_por_tipo,
        'total_videos': total_videos,
        'video_resumen': video_resumen,
        'n_fotos_para_resumen': n_fotos_para_resumen,
        
        # Empleados para copia en envío de imágenes
        'empleados_copia_imagenes': empleados_copia_imagenes,
        
        # Verificar si el usuario logueado ya está en la lista de CC
        # Si no está, el template agregará un checkbox extra para él
        'usuario_en_lista_cc': (
            hasattr(request.user, 'empleado') and 
            request.user.empleado and 
            empleados_copia_imagenes.filter(id=request.user.empleado.id).exists()
        ),
        
        # Componentes para el modal de diagnóstico
        'componentes_diagnostico_orden': COMPONENTES_DIAGNOSTICO_ORDEN,
        'componentes_adicionales_json': mark_safe(json.dumps(componentes_adicionales_list)),
        
        # Información adicional
        'dias_en_servicio': orden.dias_en_servicio,  # Días naturales (mantener por compatibilidad)
        'dias_habiles_en_servicio': orden.dias_habiles_en_servicio,  # Días hábiles (nuevo)
        'esta_retrasada': orden.esta_retrasada,
        
        # NUEVO: Variables contextuales para la UI
        'es_orden_diagnostico': orden.tipo_servicio == 'diagnostico',
        'es_orden_directa': orden.tipo_servicio == 'venta_mostrador',
        'tiene_cotizacion': cotizacion is not None,
        'tiene_venta_mostrador': venta_mostrador is not None,
        
        # Estadísticas de técnicos (para alertas) - Convertido a JSON para JavaScript
        'estadisticas_tecnicos': mark_safe(json.dumps(estadisticas_tecnicos)),

        # ── Feedback de rechazo pendiente de confirmar envío ──
        # Estas variables llegan desde la sesión tras guardar un rechazo de cotización.
        # El template las usa para mostrar el modal de confirmación de envío de correo.
        'feedback_pendiente_id': request.session.pop('feedback_pendiente_id', None),
        'feedback_pendiente_email': request.session.pop('feedback_pendiente_email', None),
        'vigencia_vencida_orden_id': request.session.pop('vigencia_vencida_orden_id', None),
        'vigencia_vencida_email': request.session.pop('vigencia_vencida_email', None),
        # ── Encuesta de satisfacción pendiente de confirmar envío ──
        'feedback_satisfaccion_pendiente_id': request.session.pop('feedback_satisfaccion_pendiente_id', None),
        'feedback_satisfaccion_email': request.session.pop('feedback_satisfaccion_email', None),

        # ── Integración IA — mejora de diagnósticos SIC (Ollama + Gemini) ──
        # Controla si el botón "Mejorar Diag. con IA" aparece en el template.
        # AI_ENABLED es True si al menos un proveedor está habilitado en .env.
        'ollama_enabled': getattr(settings, 'AI_ENABLED', False),
        # Lista unificada de modelos de todos los proveedores habilitados.
        # Formato: "[Proveedor] nombre_modelo" — ej: "[Gemini] gemini-2.0-flash"
        'ollama_models': getattr(settings, 'AI_MODELS', []),
    }
    
    return render(request, 'servicio_tecnico/detalle_orden.html', context)


# ============================================================================
# CONFIRMAR ENVÍO FEEDBACK / VIGENCIA (Fase 7):
#   views_envios_cliente.py (reexport al inicio)
# ============================================================================


# ============================================================================
# PORTAL CLIENTE (seguimiento/PWA/push/eventos/feedback rechazo):
# vive en views_seguimiento_cliente.py (reexport al inicio).
# config/urls.py sigue importando estos nombres desde servicio_tecnico.views.
# ============================================================================


# ============================================================================
# MULTIMEDIA (Fase 5):
#   compressors → services/multimedia.py
#   descargar/eliminar → views_multimedia.py (reexport al inicio)
# detalle_orden importa comprimir_y_guardar_imagen desde services.multimedia
# ============================================================================


# ============================================================================
# REFERENCIAS DE GAMA: viven en views_referencias_gama.py (reexport al inicio).
# ============================================================================


# ============================================================================
# AJAX PIEZAS / SEGUIMIENTO / VENTA MOSTRADOR (Fase 6):
#   views_piezas_cotizadas.py
#   views_seguimiento_piezas_ajax.py
#   views_venta_mostrador_ajax.py
# Notificación pieza recibida → services/notificaciones_piezas.py
# ============================================================================


# ============================================================================
# RHITSO POR ORDEN (Fase 7):
#   views_rhitso.py (gestión, estados, incidencias, correo, PDF prueba)
# Dashboards RHITSO → Fase 8
# ============================================================================


# ============================================================================
# ENVÍOS AL CLIENTE (Fase 7):
#   views_envios_cliente.py (imágenes, rewind, video, diagnóstico, preview)
# ============================================================================


# ============================================================================
# DASHBOARDS GRANDES (Fase 8):
#   views_dashboard_rhitso.py
#   views_dashboard_oow_fl.py
#   views_dashboard_cotizaciones.py
# Helpers VM → services/ventas_mostrador_analytics.py
# ============================================================================


# ============================================================================
# APIs DE BÚSQUEDA: viven en views_apis_busqueda.py (reexport al inicio).
# ============================================================================

# ============================================================================
# DASHBOARD SEGUIMIENTO PIEZAS (Fase 8):
#   views_dashboard_seguimiento_piezas.py (reexport al inicio)
# ============================================================================


# ============================================================================
# MISC: viven en views_misc.py (acceso_denegado, actualizar_email_cliente — reexport al inicio).
# ============================================================================

# ============================================================================
# CONCENTRADO SEMANAL: vive en views_concentrado.py (reexport al inicio).
# ============================================================================

# ============================================================================
# FEEDBACK SATISFACCIÓN (confirmar + formulario público):
# vive en views_seguimiento_cliente.py (reexport al inicio).
# ============================================================================

# ============================================================================
# DASHBOARDS FASE 4 (encuestas / feedback rechazo / enlaces):
# viven en views_encuestas.py, views_feedback_rechazo_dash.py,
# views_seguimiento_enlaces.py (reexport al inicio).
# Helpers de push/filtro de enlaces: eventos_seguimiento.py
# ============================================================================

# ============================================================================
# PERFIL / DIRECTORIO: viven en views_perfil.py (reexport al inicio).
# ============================================================================

# ============================================================================
# IA DIAGNÓSTICO (pulir): vive en views_ia_diagnostico.py (reexport al inicio).
# ============================================================================

# ============================================================================
# CHAT SEGUIMIENTO CLIENTE: vive en views_seguimiento_cliente.py (reexport).
# ============================================================================

# ============================================================================
# IA DIAGNÓSTICO (transcribir audio): vive en views_ia_diagnostico.py (reexport).
# ============================================================================

# ============================================================================
# VIDEO RESUMEN: vive en views_video_resumen.py (reexport al inicio).
# ============================================================================

# ============================================================================
# SICSER: consultar_sicser / importar_orden_sicser viven en views_sicser.py
# y se reexportan al inicio de este módulo (compatibilidad con urls.py).
# ============================================================================
