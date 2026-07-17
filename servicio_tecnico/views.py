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
# FUNCIONES AUXILIARES PARA ANÁLISIS DE VENTAS MOSTRADOR
# ============================================================================

def determinar_categoria_venta(venta_mostrador):
    """
    Determina la categoría principal de una VentaMostrador.

    PARÁMETROS:
    - venta_mostrador: Instancia de VentaMostrador
    
    RETORNA:
    dict con keys:
        'categoria': str (ej: "Paquete Premium", "Piezas (3 unidades)")
        'icono': str (emoji para visual)
    """
    from .models import VentaMostrador
    
    # OPCIÓN 1: Si hay paquete (premium/oro/plata)
    if venta_mostrador.paquete != 'ninguno':
        paquete_nombre = venta_mostrador.paquete.capitalize()
        return {
            'categoria': f'Paquete {paquete_nombre}',
            'icono': '📦'
        }
    
    # OPCIÓN 2: Si hay piezas individuales vendidas
    cantidad_piezas = venta_mostrador.piezas_vendidas.count()
    if cantidad_piezas > 0:
        plural = "unidad" if cantidad_piezas == 1 else "unidades"
        return {
            'categoria': f'Piezas ({cantidad_piezas} {plural})',
            'icono': '⚙️'
        }
    
    # OPCIÓN 3: Si hay servicios adicionales
    if venta_mostrador.incluye_cambio_pieza:
        return {
            'categoria': 'Cambio de Pieza',
            'icono': '🔧'
        }
    
    if venta_mostrador.incluye_limpieza:
        return {
            'categoria': 'Limpieza & Mantenimiento',
            'icono': '🧹'
        }
    
    if venta_mostrador.incluye_kit_limpieza:
        return {
            'categoria': 'Kit Limpieza',
            'icono': '🧽'
        }
    
    if venta_mostrador.incluye_reinstalacion_so:
        return {
            'categoria': 'Reinstalación SO',
            'icono': '💾'
        }
    
    # OPCIÓN 4: Si nada de lo anterior
    return {
        'categoria': 'Otros Servicios',
        'icono': '📝'
    }


def obtener_top_productos_vendidos(ordenes, limite=5):
    """
    Obtiene los TOP N productos más vendidos en las órdenes dadas.

    RETORNA:
    list de dicts con keys:
        'descripcion': str (nombre de la pieza)
        'cantidad': int (total vendidas)
        'subtotal': Decimal (monto total generado)
    """
    from collections import defaultdict
    from decimal import Decimal
    from .models import VentaMostrador
    
    # Diccionario para acumular datos por pieza
    piezas_vendidas = defaultdict(lambda: {'cantidad': 0, 'subtotal': Decimal('0.00')})
    
    # Recorrer todas las órdenes con venta mostrador
    for orden in ordenes:
        if hasattr(orden, 'venta_mostrador') and orden.venta_mostrador:
            venta = orden.venta_mostrador
            # Contar cada pieza vendida
            for pieza in venta.piezas_vendidas.all():
                clave = pieza.descripcion_pieza
                piezas_vendidas[clave]['cantidad'] += pieza.cantidad
                piezas_vendidas[clave]['subtotal'] += pieza.subtotal
    
    # Convertir a lista y ordenar por cantidad descendente
    piezas_lista = [
        {
            'descripcion': desc,
            'cantidad': data['cantidad'],
            'subtotal': data['subtotal']
        }
        for desc, data in piezas_vendidas.items()
    ]
    
    piezas_lista.sort(key=lambda x: x['cantidad'], reverse=True)
    
    # Retornar solo los top N
    return piezas_lista[:limite]


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
# VISTA: confirmar_envio_feedback
# El operador acepta o cancela el envío del correo de feedback al cliente.
# Se llama vía POST desde el modal en detalle_orden.html.
# ============================================================================

@login_required
@require_http_methods(['POST'])
def confirmar_envio_feedback(request, feedback_id):
    """
    Recibe la decisión del operador sobre si enviar o no el correo de feedback.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Cuando el operador rechaza una cotización, se muestra un modal preguntando
    si quiere enviar el correo al cliente. Esta vista procesa esa respuesta.

    Si acepta → encola la tarea Celery que envía el correo.
    Si cancela → no hace nada (el token queda guardado pero sin correo enviado).
    """
    from .models import FeedbackCliente
    from .tasks import enviar_feedback_rechazo_task

    feedback = get_object_or_404(FeedbackCliente, pk=feedback_id)
    accion = request.POST.get('accion', 'cancelar')
    orden_id = feedback.cotizacion.orden.pk

    if accion == 'enviar':
        if feedback.correo_enviado:
            messages.warning(request, '⚠️ El correo de feedback ya fue enviado anteriormente.')
        else:
            usuario_id = request.user.pk if request.user.is_authenticated else None
            from config.paises_config import get_pais_actual
            enviar_feedback_rechazo_task.delay(feedback_id=feedback.pk, usuario_id=usuario_id, db_alias=get_pais_actual()['db_alias'])
            messages.success(
                request,
                f'📧 Correo de feedback enviado a {feedback.cotizacion.orden.detalle_equipo.email_cliente}. '
                f'El cliente tiene 12 días para responder.'
            )
    else:
        messages.info(request, 'ℹ️ Envío de correo de feedback cancelado.')

    return redirect('servicio_tecnico:detalle_orden', orden_id=orden_id)


# ============================================================================
# VISTA: confirmar_envio_vigencia_vencida
# Envío opcional del correo de cotización vencida (motivo: falta_de_respuesta).
# ============================================================================

@login_required
@require_http_methods(['POST'])
def confirmar_envio_vigencia_vencida(request, orden_id):
    """
    Encola el correo informativo de cotización vencida por falta de respuesta.
    """
    from .tasks import enviar_vigencia_vencida_task

    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    accion = request.POST.get('accion', 'cancelar')

    if accion == 'enviar':
        usuario_id = request.user.pk if request.user.is_authenticated else None
        from config.paises_config import get_pais_actual
        enviar_vigencia_vencida_task.delay(orden_id=orden.pk, usuario_id=usuario_id, db_alias=get_pais_actual()['db_alias'])
        email_cl = orden.detalle_equipo.email_cliente if orden.detalle_equipo else '(sin email)'
        messages.success(
            request,
            f'📧 Correo de cotización vencida enviado a {email_cl}.'
        )
    else:
        messages.info(request, 'ℹ️ Envío de correo cancelado.')

    return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)


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
    Vista para enviar correo electrónico a RHITSO con información del equipo.

    REFACTORIZADO CON CELERY:
    Esta vista ahora solo hace la validación rápida (< 1 segundo) y delega
    el trabajo pesado (PDF, imágenes, email.send) a una tarea Celery en
    segundo plano. El usuario recibe respuesta inmediata sin esperar.

    Flujo:
        1. Validar que la orden existe y es candidato RHITSO
        2. Validar que hay al menos un destinatario
        3. Disparar tarea Celery con .delay() → retorna un ID de tarea
        4. Responder al usuario inmediatamente con "Enviando en segundo plano..."

    Args:
        request: HttpRequest object con datos POST del formulario
        orden_id: ID de la orden de servicio

    Returns:
        JsonResponse inmediato — el correo se procesa en background
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


# ============================================================================
# ENVIAR IMÁGENES AL CLIENTE POR CORREO ELECTRÓNICO
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
@require_http_methods(["POST"])
def enviar_imagenes_cliente(request, orden_id):
    """
    Vista para enviar imágenes de ingreso del equipo al cliente por correo electrónico.
    
    REFACTORIZADO CON CELERY:
    La vista ahora solo valida datos y dispara la tarea Celery.
    La compresión de imágenes, envío de email e historial se procesan en segundo plano.

    Args:
        request: HttpRequest object con datos POST del formulario
        orden_id: ID de la orden de servicio
    
    Returns:
        JsonResponse inmediato — el correo se procesa en background
    """
    from .tasks import enviar_imagenes_cliente_task
    
    try:
        # =======================================================================
        # PASO 1: OBTENER Y VALIDAR LA ORDEN
        # =======================================================================
        orden = get_object_or_404(OrdenServicio.objects.select_related('detalle_equipo'), pk=orden_id)
        
        # Validar que el cliente tenga email configurado
        email_cliente = orden.detalle_equipo.email_cliente
        if not email_cliente or email_cliente == 'cliente@ejemplo.com':
            return JsonResponse({
                'success': False,
                'error': '❌ El email del cliente no está configurado o es el valor por defecto. '
                        'Por favor, actualiza el email del cliente antes de enviar.'
            }, status=400)
        
        # =======================================================================
        # PASO 2: OBTENER Y VALIDAR IMÁGENES SELECCIONADAS
        # =======================================================================
        imagenes_ids = request.POST.getlist('imagenes_seleccionadas')
        
        if not imagenes_ids:
            return JsonResponse({
                'success': False,
                'error': '❌ Debes seleccionar al menos una imagen para enviar.'
            }, status=400)
        
        # Verificar que las imágenes existen y son de tipo ingreso
        imagenes = ImagenOrden.objects.filter(
            id__in=imagenes_ids,
            orden=orden,
            tipo='ingreso'
        )
        
        if not imagenes.exists():
            return JsonResponse({
                'success': False,
                'error': '❌ Las imágenes seleccionadas no son válidas.'
            }, status=400)
        
        # =======================================================================
        # PASO 3: OBTENER DATOS DEL FORMULARIO
        # =======================================================================
        copia_empleados = request.POST.getlist('copia_empleados', [])
        copia_tecnico = request.POST.getlist('copia_tecnico', [])
        destinatarios_copia = list(set(copia_empleados + copia_tecnico))
        
        mensaje_personalizado = request.POST.get('mensaje_personalizado', '').strip()

        # Modelo IA elegido en el selector del modal (vacío = automático)
        modelo_ia_inspeccion = request.POST.get('modelo_ia_inspeccion', '').strip()
        
        # =======================================================================
        # PASO 4: DISPARAR TAREA CELERY EN SEGUNDO PLANO
        # =======================================================================
        usuario_id = request.user.pk if request.user.is_authenticated else None
        
        # Convertir IDs a lista de strings (JSON serializable)
        imagenes_ids_str = [str(i) for i in imagenes_ids]
        
        from config.paises_config import get_pais_actual
        tarea = enviar_imagenes_cliente_task.delay(
            orden_id=orden_id,
            imagenes_ids=imagenes_ids_str,
            destinatarios_copia=destinatarios_copia,
            mensaje_personalizado=mensaje_personalizado,
            usuario_id=usuario_id,
            modelo_ia_inspeccion=modelo_ia_inspeccion,
            db_alias=get_pais_actual()['db_alias'],
        )

        # Registrar de inmediato que el envío fue iniciado, para que el botón
        # muestre "ya enviado / reenviar" en la recarga sin esperar a que
        # termine la tarea Celery (icontains='imágenes de ingreso').
        HistorialOrden.objects.create(
            orden=orden,
            usuario=getattr(request.user, 'empleado', None),
            tipo_evento='email',
            comentario=f'Envío de imágenes de ingreso al cliente iniciado — tarea en segundo plano (task_id: {tarea.id})',
        )

        # ── Disparar envío de enlace de seguimiento (solo fuera de garantía) ──
        if orden.es_fuera_garantia:
            from .tasks import enviar_seguimiento_cliente_task
            from config.paises_config import get_pais_actual
            enviar_seguimiento_cliente_task.delay(
                orden_id=orden_id,
                usuario_id=usuario_id,
                db_alias=get_pais_actual()['db_alias'],
            )
        
        return JsonResponse({
            'success': True,
            'message': (
                f'✅ Imágenes en proceso de envío a {email_cliente}. '
                f'La compresión y envío se están procesando en segundo plano.'
            ),
            'data': {
                'task_id': tarea.id,
                'destinatario': email_cliente,
                'imagenes_seleccionadas': len(imagenes_ids),
                'orden': orden.numero_orden_interno,
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        return JsonResponse({
            'success': False,
            'error': f'❌ Error al procesar la solicitud: {str(e)}'
        }, status=500)


# ============================================================================
# ENVIAR IMÁGENES DE EGRESO AL CLIENTE
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
@require_http_methods(["POST"])
def enviar_imagenes_egreso_cliente(request, orden_id):
    """
    Vista para enviar las imágenes de egreso al cliente por correo electrónico.

    Flujo:
    1. Valida que la orden exista y tenga imágenes de egreso.
    2. Busca en el historial el último envío de imágenes de ingreso para reutilizar
       los mismos destinatarios (email principal + CC). Si no hay historial previo,
       usa el email del cliente sin CC.
    3. Dispara la tarea Celery enviar_imagenes_egreso_cliente_task en segundo plano.
    4. Retorna JsonResponse inmediato con task_id, destinatario y lista de correos CC.
    """
    import re as _re
    from .tasks import enviar_imagenes_egreso_cliente_task

    try:
        # ===================================================================
        # PASO 1: OBTENER Y VALIDAR LA ORDEN
        # ===================================================================
        orden = get_object_or_404(
            OrdenServicio.objects.select_related('detalle_equipo'), pk=orden_id
        )

        # Validar email del cliente
        email_cliente = orden.detalle_equipo.email_cliente
        if not email_cliente or email_cliente == 'cliente@ejemplo.com':
            return JsonResponse({
                'success': False,
                'error': (
                    '❌ El email del cliente no está configurado o es el valor por defecto. '
                    'Por favor, actualiza el email del cliente antes de enviar.'
                )
            }, status=400)

        # ===================================================================
        # PASO 2: VERIFICAR QUE EXISTAN IMÁGENES DE EGRESO
        # ===================================================================
        imagenes_egreso = ImagenOrden.objects.filter(orden=orden, tipo='egreso')
        if not imagenes_egreso.exists():
            return JsonResponse({
                'success': False,
                'error': '❌ Esta orden no tiene imágenes de egreso registradas.'
            }, status=400)

        # ===================================================================
        # PASO 3: RECUPERAR DESTINATARIOS DEL HISTORIAL DE INGRESO
        #
        # Se parsea el comentario del último HistorialOrden con tipo_evento='email'
        # que corresponda al envío de imágenes de ingreso.
        # Patrón del comentario guardado por enviar_imagenes_cliente_task:
        #   "📧 Imágenes de ingreso enviadas al cliente (background) (email@ejemplo.com)
        #    📸 Cantidad de imágenes: X
        #    📦 Tamaño total: X.XX MB
        #    👥 Copia a: cc1@email.com, cc2@email.com"
        # ===================================================================
        destinatarios_copia = []

        historial_ingreso = (
            HistorialOrden.objects
            .filter(orden=orden, tipo_evento='email')
            .filter(comentario__icontains='imágenes de ingreso')
            .order_by('-fecha_evento')
            .first()
        )

        if historial_ingreso:
            # Extraer los correos en CC de la línea "👥 Copia a: ..."
            match_cc = _re.search(
                r'Copia a:\s*(.+)',
                historial_ingreso.comentario,
                _re.IGNORECASE
            )
            if match_cc:
                raw_cc = match_cc.group(1).strip()
                # Separar por coma y limpiar espacios
                destinatarios_copia = [
                    email.strip()
                    for email in raw_cc.split(',')
                    if email.strip() and '@' in email.strip()
                ]

        # ===================================================================
        # PASO 4: DISPARAR TAREA CELERY EN SEGUNDO PLANO
        # ===================================================================
        usuario_id = request.user.pk if request.user.is_authenticated else None

        from config.paises_config import get_pais_actual
        tarea = enviar_imagenes_egreso_cliente_task.delay(
            orden_id=orden_id,
            destinatarios_copia=destinatarios_copia,
            usuario_id=usuario_id,
            db_alias=get_pais_actual()['db_alias'],
        )

        # Registrar de inmediato que el envío fue iniciado, para que el botón
        # muestre "ya enviado / reenviar" en la recarga sin esperar a que
        # termine la tarea Celery (icontains='imágenes de egreso').
        HistorialOrden.objects.create(
            orden=orden,
            usuario=getattr(request.user, 'empleado', None),
            tipo_evento='email',
            comentario=f'Envío de imágenes de egreso al cliente iniciado — tarea en segundo plano (task_id: {tarea.id})',
        )

        return JsonResponse({
            'success': True,
            'message': (
                f'✅ Imágenes de egreso en proceso de envío a {email_cliente}. '
                f'La compresión y envío se están procesando en segundo plano.'
            ),
            'data': {
                'task_id': tarea.id,
                'destinatario': email_cliente,
                'destinatarios_copia': destinatarios_copia,
                'imagenes_count': imagenes_egreso.count(),
                'orden': orden.numero_orden_interno,
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'❌ Error al procesar la solicitud: {str(e)}'
        }, status=500)


# ============================================================================
# ENVIAR VIDEO REWIND DE EGRESO AL CLIENTE
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
@require_http_methods(["POST"])
def enviar_rewind_egreso_cliente(request, orden_id):
    """
    Vista que dispara la cadena Celery para generar el video rewind y enviarlo
    al cliente por correo electrónico.

    Flujo:
    1. Valida que la orden exista, tenga email válido e imágenes de egreso.
    2. Verifica que la orden tenga los 4 tipos de fotos (ingreso, diagnóstico,
       reparación, egreso). Si no, rechaza la solicitud con un error descriptivo.
    3. Recupera los destinatarios CC del historial del envío de ingreso previo.
    4. Lanza un chain Celery:
           generar_video_resumen_task  →  enviar_rewind_egreso_email_task
       La primera tarea genera el video y lo guarda; la segunda envía el correo
       con el thumbnail embebido y el botón CTA de seguimiento.
    5. Retorna JsonResponse inmediato. El video puede tardar varios minutos.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Un "chain" de Celery es como una tubería: la salida de la primera tarea
    (el video_id del VideoOrden creado) se pasa automáticamente como primer
    argumento de la segunda tarea.
    """
    import re as _re
    from django.http import Http404 as _Http404

    # Http404 se trata por separado (orden no encontrada → 404, no 500)
    try:
        # ===================================================================
        # PASO 1: OBTENER Y VALIDAR LA ORDEN
        # ===================================================================
        orden = get_object_or_404(
            OrdenServicio.objects.select_related('detalle_equipo'), pk=orden_id
        )
    except _Http404:
        return JsonResponse({
            'success': False,
            'error': '❌ Orden no encontrada.',
        }, status=404)

    try:
        # ===================================================================
        # PASO 2: VALIDAR EMAIL, IMÁGENES Y TIPOS DE FOTOS
        # ===================================================================
        email_cliente = orden.detalle_equipo.email_cliente
        if not email_cliente or email_cliente == 'cliente@ejemplo.com':
            return JsonResponse({
                'success': False,
                'error': (
                    '❌ El email del cliente no está configurado o es el valor por defecto. '
                    'Por favor, actualiza el email del cliente antes de enviar.'
                )
            }, status=400)

        # ===================================================================
        # PASO 3: VERIFICAR QUE EXISTAN IMÁGENES DE EGRESO
        # ===================================================================
        if not ImagenOrden.objects.filter(orden=orden, tipo='egreso').exists():
            return JsonResponse({
                'success': False,
                'error': '❌ Esta orden no tiene imágenes de egreso registradas.'
            }, status=400)

        # ===================================================================
        # PASO 4: VERIFICAR LOS TIPOS DE FOTOS REQUERIDOS
        # Diagnóstico: requiere 4 tipos (ingreso, diagnóstico, reparación, egreso)
        # Venta mostrador: requiere 3 tipos (ingreso, reparación, egreso)
        # ===================================================================
        es_venta_mostrador = orden.tipo_servicio == 'venta_mostrador'

        tipos_presentes = set(
            ImagenOrden.objects.filter(orden=orden)
            .values_list('tipo', flat=True)
            .distinct()
        )

        if es_venta_mostrador:
            tipos_requeridos = {'ingreso', 'reparacion', 'egreso'}
        else:
            tipos_requeridos = {'ingreso', 'diagnostico', 'reparacion', 'egreso'}

        tipos_faltantes = tipos_requeridos - tipos_presentes

        if tipos_faltantes:
            nombres = {
                'ingreso': 'Ingreso',
                'diagnostico': 'Diagnóstico',
                'reparacion': 'Reparación',
                'egreso': 'Egreso',
            }
            faltantes_texto = ', '.join(nombres.get(t, t) for t in sorted(tipos_faltantes))
            n_requeridos = len(tipos_requeridos)
            return JsonResponse({
                'success': False,
                'error': (
                    f'❌ Para generar el video rewind se necesitan fotos de los {n_requeridos} tipos. '
                    f'Faltan fotos de: {faltantes_texto}.'
                )
            }, status=400)

        # ===================================================================
        # PASO 5: RECUPERAR DESTINATARIOS CC DEL HISTORIAL DE INGRESO
        # (misma lógica que enviar_imagenes_egreso_cliente)
        # ===================================================================
        destinatarios_copia = []

        historial_ingreso = (
            HistorialOrden.objects
            .filter(orden=orden, tipo_evento='email')
            .filter(comentario__icontains='imágenes de ingreso')
            .order_by('-fecha_evento')
            .first()
        )

        if historial_ingreso:
            match_cc = _re.search(
                r'Copia a:\s*(.+)',
                historial_ingreso.comentario,
                _re.IGNORECASE
            )
            if match_cc:
                raw_cc = match_cc.group(1).strip()
                destinatarios_copia = [
                    email.strip()
                    for email in raw_cc.split(',')
                    if email.strip() and '@' in email.strip()
                ]

        # ===================================================================
        # PASO 6: LANZAR CHAIN CELERY
        # ===================================================================
        from celery import chain as celery_chain
        from .tasks import generar_video_resumen_task, enviar_rewind_egreso_email_task
        from config.paises_config import get_pais_actual

        usuario_id = request.user.pk if request.user.is_authenticated else None
        _db_alias_rewind = get_pais_actual()['db_alias']

        cadena = celery_chain(
            generar_video_resumen_task.s(orden_id, usuario_id, _db_alias_rewind),
            enviar_rewind_egreso_email_task.s(orden_id, usuario_id, destinatarios_copia, _db_alias_rewind),
        )
        tarea_raiz = cadena.delay()

        # Registrar de inmediato que la generación fue iniciada, para que el botón
        # muestre "ya enviado / reenviar" en la recarga sin esperar a que
        # termine la cadena Celery (icontains='video rewind').
        HistorialOrden.objects.create(
            orden=orden,
            usuario=getattr(request.user, 'empleado', None),
            tipo_evento='email',
            comentario=f'Generación de video rewind al cliente iniciada — tarea en segundo plano (task_id: {tarea_raiz.id})',
        )

        return JsonResponse({
            'success': True,
            'message': (
                f'✅ Video rewind en proceso de generación para {email_cliente}. '
                f'El video y el correo se procesarán en segundo plano — puede tardar varios minutos.'
            ),
            'data': {
                'task_id': str(tarea_raiz.id),
                'destinatario': email_cliente,
                'destinatarios_copia': destinatarios_copia,
                'orden': orden.numero_orden_interno,
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'❌ Error al procesar la solicitud: {str(e)}'
        }, status=500)


# ============================================================================
# ENVIAR EVIDENCIA EN VIDEO AL CLIENTE POR CORREO ELECTRÓNICO
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
@require_http_methods(["POST"])
def enviar_evidencia_video(request, orden_id):
    """
    Vista para enviar evidencia en video del servicio al cliente por correo electrónico.

    Flujo:
    1. Valida que la orden exista y tenga videos seleccionados.
    2. Dispara la tarea Celery enviar_evidencia_video_task en segundo plano.
    3. La tarea extrae frames, genera análisis IA opcional y envía el correo.
    4. Retorna JsonResponse inmediato con task_id.
    """
    from .tasks import enviar_evidencia_video_task

    try:
        orden = get_object_or_404(OrdenServicio.objects.select_related('detalle_equipo'), pk=orden_id)

        email_cliente = orden.detalle_equipo.email_cliente
        if not email_cliente or email_cliente == 'cliente@ejemplo.com':
            return JsonResponse({
                'success': False,
                'error': '❌ El email del cliente no está configurado o es el valor por defecto. '
                        'Por favor, actualiza el email del cliente antes de enviar.'
            }, status=400)

        video_ids = request.POST.getlist('videos_seleccionados')

        if not video_ids:
            return JsonResponse({
                'success': False,
                'error': '❌ Debes seleccionar al menos un video para enviar.'
            }, status=400)

        videos = VideoOrden.objects.filter(
            id__in=video_ids,
            orden=orden,
        ).exclude(tipo__in=['resumen', 'resumen_comprimido'])

        if not videos.exists():
            return JsonResponse({
                'success': False,
                'error': '❌ Los videos seleccionados no son válidos.'
            }, status=400)

        copia_empleados = request.POST.getlist('copia_empleados', [])
        copia_tecnico = request.POST.getlist('copia_tecnico', [])
        destinatarios_copia = list(set(copia_empleados + copia_tecnico))

        modelo_ia_analisis = request.POST.get('modelo_ia_analisis', '').strip()
        mensaje_personalizado = request.POST.get('mensaje_personalizado', '').strip()

        usuario_id = request.user.pk if request.user.is_authenticated else None

        video_ids_str = [str(i) for i in video_ids]

        from config.paises_config import get_pais_actual
        tarea = enviar_evidencia_video_task.delay(
            orden_id=orden_id,
            video_ids=video_ids_str,
            destinatarios_copia=destinatarios_copia,
            modelo_ia_analisis=modelo_ia_analisis,
            usuario_id=usuario_id,
            mensaje_personalizado=mensaje_personalizado,
            db_alias=get_pais_actual()['db_alias'],
        )

        HistorialOrden.objects.create(
            orden=orden,
            usuario=getattr(request.user, 'empleado', None),
            tipo_evento='email',
            comentario=f'Envío de evidencia en video al cliente iniciado — tarea en segundo plano (task_id: {tarea.id})',
        )

        return JsonResponse({
            'success': True,
            'message': (
                f'✅ Evidencia en video en proceso de envío a {email_cliente}. '
                f'El análisis y envío se están procesando en segundo plano.'
            ),
            'data': {
                'task_id': tarea.id,
                'destinatario': email_cliente,
                'videos_seleccionados': len(video_ids),
                'orden': orden.numero_orden_interno,
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'❌ Error al procesar la solicitud: {str(e)}'
        }, status=500)


# ============================================================================
# DIAGNÓSTICO: OBTENER DESTINATARIOS DEL HISTORIAL DE INGRESO (API auxiliar)
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
@require_http_methods(["GET"])
def obtener_destinatarios_egreso(request, orden_id):
    """
    API auxiliar que devuelve los destinatarios del último envío de imágenes
    de ingreso para esta orden. El frontend los muestra en el modal de confirmación
    antes de disparar el envío de egreso, para que el usuario pueda verificarlos.
    """
    import re as _re

    try:
        orden = get_object_or_404(
            OrdenServicio.objects.select_related('detalle_equipo'), pk=orden_id
        )

        email_cliente = orden.detalle_equipo.email_cliente
        email_valido = (
            bool(email_cliente)
            and email_cliente != 'cliente@ejemplo.com'
        )

        destinatarios_copia = []
        historial_encontrado = False

        historial_ingreso = (
            HistorialOrden.objects
            .filter(orden=orden, tipo_evento='email')
            .filter(comentario__icontains='imágenes de ingreso')
            .order_by('-fecha_evento')
            .first()
        )

        if historial_ingreso:
            historial_encontrado = True
            import re as _re2
            match_cc = _re2.search(
                r'Copia a:\s*(.+)',
                historial_ingreso.comentario,
                _re2.IGNORECASE
            )
            if match_cc:
                raw_cc = match_cc.group(1).strip()
                destinatarios_copia = [
                    email.strip()
                    for email in raw_cc.split(',')
                    if email.strip() and '@' in email.strip()
                ]

        # Verificar si ya se enviaron imágenes de egreso previamente
        egreso_ya_enviado = (
            HistorialOrden.objects
            .filter(orden=orden, tipo_evento='email')
            .filter(comentario__icontains='imágenes de egreso')
            .exists()
        )

        # Contar imágenes de egreso disponibles
        imagenes_egreso_count = ImagenOrden.objects.filter(
            orden=orden, tipo='egreso'
        ).count()

        return JsonResponse({
            'success': True,
            'email': email_cliente if email_valido else '',
            'email_valido': email_valido,
            'destinatarios_copia': destinatarios_copia,
            'desde_historial': historial_encontrado,
            'egreso_ya_enviado': egreso_ya_enviado,
            'imagenes_egreso_count': imagenes_egreso_count,
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================================================
# ENVIAR DIAGNÓSTICO AL CLIENTE CON PDF ADJUNTO
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
@require_http_methods(["POST"])
def enviar_diagnostico_cliente(request, orden_id):
    """
    Vista para enviar el diagnóstico técnico al cliente por correo electrónico.
    
    REFACTORIZADO CON CELERY:
    La vista ahora solo valida datos del formulario y dispara la tarea Celery.
    Todo lo pesado (PDF, imágenes, email) se ejecuta en segundo plano.
    
    Flujo:
    1. Valida datos (email, diagnóstico, folio, tamaño de imágenes)
    2. Dispara tarea Celery con .delay()
    3. Responde inmediatamente al usuario

    Args:
        request: HttpRequest con datos POST del formulario del modal
        orden_id: ID de la orden de servicio
    
    Returns:
        JsonResponse inmediato — el correo se procesa en background
    """
    from .tasks import enviar_diagnostico_cliente_task
    
    try:
        # =======================================================================
        # PASO 1: OBTENER Y VALIDAR LA ORDEN
        # =======================================================================
        orden = get_object_or_404(
            OrdenServicio.objects.select_related('detalle_equipo'),
            pk=orden_id
        )
        detalle = orden.detalle_equipo
        
        # Validar que el cliente tenga email configurado
        email_cliente = detalle.email_cliente
        if not email_cliente or email_cliente == 'cliente@ejemplo.com':
            return JsonResponse({
                'success': False,
                'error': '❌ El email del cliente no está configurado o es el valor por defecto. '
                        'Por favor, actualiza el email del cliente antes de enviar.'
            }, status=400)
        
        # Validar que tenga diagnóstico SIC
        if not detalle.diagnostico_sic or not detalle.diagnostico_sic.strip():
            return JsonResponse({
                'success': False,
                'error': '❌ El diagnóstico SIC está vacío. Debes completar el diagnóstico antes de enviar.'
            }, status=400)
        
        # Validar que tenga falla principal
        if not detalle.falla_principal or not detalle.falla_principal.strip():
            return JsonResponse({
                'success': False,
                'error': '❌ La falla principal está vacía. Debes registrar la falla antes de enviar.'
            }, status=400)
        
        # =======================================================================
        # PASO 2: OBTENER DATOS DEL FORMULARIO
        # =======================================================================
        folio = request.POST.get('folio', '').strip()
        if not folio:
            return JsonResponse({
                'success': False,
                'error': '❌ El folio es obligatorio. Ingresa un folio para el diagnóstico.'
            }, status=400)
        
        componentes_json = request.POST.get('componentes', '[]')
        try:
            componentes_data = json.loads(componentes_json)
        except (json.JSONDecodeError, ValueError):
            componentes_data = []
        
        imagenes_ids = request.POST.getlist('imagenes_seleccionadas')
        
        copia_empleados = request.POST.getlist('copia_empleados', [])
        copia_tecnico = request.POST.getlist('copia_tecnico', [])
        destinatarios_copia = list(set(copia_empleados + copia_tecnico))
        
        mensaje_personalizado = request.POST.get('mensaje_personalizado', '').strip()
        
        email_empleado = ''
        nombre_empleado = ''
        if hasattr(request.user, 'empleado') and request.user.empleado:
            email_empleado = request.user.empleado.email or ''
            nombre_empleado = request.user.empleado.nombre_completo or ''
        
        # =======================================================================
        # PASO 3: DISPARAR TAREA CELERY EN SEGUNDO PLANO
        # =======================================================================
        usuario_id = request.user.pk if request.user.is_authenticated else None
        
        from config.paises_config import get_pais_actual
        tarea = enviar_diagnostico_cliente_task.delay(
            orden_id=orden_id,
            folio=folio,
            componentes_data=componentes_data,
            imagenes_ids=imagenes_ids,
            destinatarios_copia=destinatarios_copia,
            mensaje_personalizado=mensaje_personalizado,
            email_empleado=email_empleado,
            nombre_empleado=nombre_empleado,
            usuario_id=usuario_id,
            db_alias=get_pais_actual()['db_alias'],
        )
        
        return JsonResponse({
            'success': True,
            'message': (
                f'✅ Diagnóstico en proceso de envío a {email_cliente}. '
                f'El PDF, imágenes y correo se están procesando en segundo plano.'
            ),
            'data': {
                'task_id': tarea.id,
                'destinatario': email_cliente,
                'folio': folio,
                'orden': orden.numero_orden_interno,
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'❌ Error al procesar la solicitud: {str(e)}'
        }, status=500)


# ============================================================================
# PREVIEW PDF DIAGNÓSTICO (para iframe en el modal)
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
@require_http_methods(["GET"])
@xframe_options_exempt
def preview_pdf_diagnostico(request, orden_id):
    """
    Genera el PDF de diagnóstico y lo retorna inline para vista previa en iframe.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista genera el mismo PDF que se enviará al cliente, pero en lugar de
    enviarlo por correo, lo muestra directamente en el navegador dentro de un
    iframe. Esto permite al usuario verificar el contenido antes de enviar.
    
    Args:
        request: HttpRequest con parámetros GET (folio, componentes)
        orden_id: ID de la orden de servicio
    
    Returns:
        HttpResponse con el PDF inline (Content-Disposition: inline)
    """
    from django.http import FileResponse
    from .utils.pdf_diagnostico import PDFGeneratorDiagnostico
    
    try:
        orden = get_object_or_404(
            OrdenServicio.objects.select_related('detalle_equipo'),
            pk=orden_id
        )
        
        # Obtener parámetros de query
        folio = request.GET.get('folio', 'PREVIEW')
        componentes_json = request.GET.get('componentes', '[]')
        
        try:
            componentes_data = json.loads(componentes_json)
        except (json.JSONDecodeError, ValueError):
            componentes_data = []
        
        # Email del empleado actual
        email_empleado = ''
        if hasattr(request.user, 'empleado') and request.user.empleado:
            email_empleado = request.user.empleado.email or ''
        
        # Preparar componentes para el PDF
        componentes_para_pdf = []
        for comp in componentes_data:
            componentes_para_pdf.append({
                'componente_db': comp.get('componente_db', ''),
                'dpn': comp.get('dpn', ''),
                'seleccionado': comp.get('seleccionado', False),
                'es_necesaria': comp.get('es_necesaria', True)
            })
        
        # Obtener config del país para que el PDF muestre el nombre correcto
        from config.paises_config import get_pais_actual
        _pais_pdf = get_pais_actual()
        
        # Generar PDF
        generador = PDFGeneratorDiagnostico(
            orden=orden,
            folio=folio,
            componentes_seleccionados=componentes_para_pdf,
            email_empleado=email_empleado,
            pais_config=_pais_pdf
        )
        resultado = generador.generar_pdf()
        
        if not resultado['success']:
            return HttpResponse(
                f'Error al generar PDF: {resultado.get("error", "Desconocido")}',
                status=500
            )
        
        # Retornar PDF inline
        response = FileResponse(
            open(resultado['ruta'], 'rb'),
            content_type='application/pdf'
        )
        response['Content-Disposition'] = f'inline; filename="{resultado["archivo"]}"'
        
        return response
        
    except Exception as e:
        print(f"❌ Error generando preview PDF diagnóstico: {str(e)}")
        import traceback
        traceback.print_exc()
        return HttpResponse(f'Error: {str(e)}', status=500)


# ============================================================================
# DASHBOARD RHITSO - VISTA CONSOLIDADA DE CANDIDATOS
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def dashboard_rhitso(request):
    """
    Dashboard consolidado de todos los candidatos RHITSO.
 
    Args:
        request: HttpRequest object
    
    Returns:
        HttpResponse con el dashboard renderizado
    """
    from .utils_rhitso_analytics import obtener_embudo_rhitso

    # Filtros compartidos con el reporte de análisis (GET params)
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')
    sucursal_id = request.GET.get('sucursal', '') or None

    embudo = obtener_embudo_rhitso(
        fecha_inicio=fecha_inicio or None,
        fecha_fin=fecha_fin or None,
        sucursal_id=sucursal_id,
    )

    # =======================================================================
    # PASO 1: CONSULTA OPTIMIZADA DE CANDIDATOS RHITSO
    # =======================================================================

    # Esto evita el "N+1 problem" (hacer una consulta por cada relación)
    candidatos_rhitso = OrdenServicio.objects.filter(
        es_candidato_rhitso=True,
        id__in=embudo['candidatos_qs'].values_list('id', flat=True),
    ).select_related(
        'detalle_equipo',              # Información del equipo
        'sucursal',                    # Sucursal de la orden
        'tecnico_asignado_actual',     # Técnico asignado
        'responsable_seguimiento'      # Responsable del seguimiento
    ).prefetch_related(

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
        
        # Días hábiles en SIC (tiempo total del proceso desde ingreso hasta completar)
        # EXPLICACIÓN: Este cálculo representa el tiempo TOTAL de la orden, incluyendo
        # todo el ciclo: diagnóstico SIC + envío a RHITSO + recepción de RHITSO
        if orden.fecha_recepcion_rhitso:
            # Si ya regresó de RHITSO, contar desde ingreso hasta recepción (proceso completado)
            dias_habiles_sic = calcular_dias_habiles(
                orden.fecha_ingreso,
                orden.fecha_recepcion_rhitso
            )
        else:
            # Si no ha regresado (o nunca se envió), contar hasta hoy
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

        # Embudo de conversión RHITSO
        'embudo': embudo,
        'filtro_fecha_inicio': fecha_inicio,
        'filtro_fecha_fin': fecha_fin,
        'filtro_sucursal': sucursal_id or '',
    }
    
    return render(request, 'servicio_tecnico/rhitso/dashboard_rhitso.html', context)


# =============================================================================
# EXPORTACIÓN EXCEL RHITSO CON OPENPYXL
# =============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def exportar_excel_rhitso(request):
    """
    Genera y descarga un reporte Excel profesional de candidatos RHITSO.

    Args:
        request: HttpRequest object
    
    Returns:
        HttpResponse con archivo Excel para descarga
    """
    # =========================================================================
    # PASO 1: PREPARAR DATOS (REUTILIZAR LÓGICA DEL DASHBOARD)
    # =========================================================================
    
    # EXPLICACIÓN: Reutilizamos la misma consulta optimizada del dashboard
    from .utils_rhitso_analytics import obtener_queryset_candidatos

    fecha_inicio = request.GET.get('fecha_inicio', '') or None
    fecha_fin = request.GET.get('fecha_fin', '') or None
    sucursal_id = request.GET.get('sucursal', '') or None

    candidatos_rhitso = obtener_queryset_candidatos(
        fecha_inicio, fecha_fin, sucursal_id
    ).select_related(
        'detalle_equipo',
        'sucursal',
        'tecnico_asignado_actual',
        'responsable_seguimiento'
    ).prefetch_related(
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
    
    # Estados para clasificación
    estados_excluidos = ['CERRADO', 'USUARIO NO ACEPTA ENVIO A RHITSO']
    estados_pendientes = ['PENDIENTE DE CONFIRMAR ENVIO A RHITSO']
    
    # Listas para separar órdenes por categoría
    activos = []
    pendientes = []
    excluidos = []
    
    # Procesar cada orden
    for orden in candidatos_rhitso:
        detalle = orden.detalle_equipo
        
        # Estado RHITSO actual
        estado_rhitso_nombre = orden.estado_rhitso if orden.estado_rhitso else 'Pendiente'
        estado_rhitso_display = estado_rhitso_nombre
        
        # Buscar owner del estado
        try:
            estado_obj = EstadoRHITSO.objects.get(estado=estado_rhitso_nombre)
            owner_actual = estado_obj.owner
        except EstadoRHITSO.DoesNotExist:
            owner_actual = ''
        
        # Calcular días hábiles en SIC (tiempo total del proceso)
        if orden.fecha_recepcion_rhitso:
            dias_habiles_sic = calcular_dias_habiles(orden.fecha_ingreso, orden.fecha_recepcion_rhitso)
        else:
            dias_habiles_sic = calcular_dias_habiles(orden.fecha_ingreso)
        
        # Calcular días hábiles en RHITSO
        dias_habiles_rhitso = 0
        if orden.fecha_envio_rhitso:
            if orden.fecha_recepcion_rhitso:
                dias_habiles_rhitso = calcular_dias_habiles(orden.fecha_envio_rhitso, orden.fecha_recepcion_rhitso)
            else:
                dias_habiles_rhitso = calcular_dias_habiles(orden.fecha_envio_rhitso)
        
        # Calcular días sin actualización
        ultimo_seguimiento_usuario = None
        if hasattr(orden, 'seguimientos_ordenados') and orden.seguimientos_ordenados:
            for seg in orden.seguimientos_ordenados:
                if not seg.es_cambio_automatico:
                    ultimo_seguimiento_usuario = seg
                    break
        
        if ultimo_seguimiento_usuario:
            dias_sin_actualizar = calcular_dias_en_estatus(ultimo_seguimiento_usuario.fecha_actualizacion)
            fecha_ultimo_comentario = ultimo_seguimiento_usuario.fecha_actualizacion
            ultimo_comentario = ultimo_seguimiento_usuario.observaciones
        else:
            dias_sin_actualizar = calcular_dias_en_estatus(orden.fecha_ingreso)
            fecha_ultimo_comentario = None
            ultimo_comentario = ''
        
        # Contar incidencias
        incidencias_abiertas_count = len(orden.incidencias_abiertas) if hasattr(orden, 'incidencias_abiertas') else 0
        incidencias_resueltas_count = len(orden.incidencias_resueltas_lista) if hasattr(orden, 'incidencias_resueltas_lista') else 0
        total_incidencias = incidencias_abiertas_count + incidencias_resueltas_count
        
        # Determinar estado del proceso
        estado_proceso = obtener_estado_proceso_rhitso(orden)
        
        # Construir diccionario con toda la información
        orden_data = {
            'orden_cliente': detalle.orden_cliente if detalle else 'Sin orden',
            'numero_serie': detalle.numero_serie if detalle else 'N/A',
            'marca': detalle.marca if detalle else 'N/A',
            'modelo': detalle.modelo if detalle else 'N/A',
            'fecha_ingreso': orden.fecha_ingreso,
            'sucursal': orden.sucursal.nombre if orden.sucursal else 'N/A',
            'estado_orden': orden.get_estado_display(),
            'estado_rhitso_display': estado_rhitso_display,
            'owner_actual': owner_actual,
            'total_incidencias': f"{incidencias_abiertas_count}/{total_incidencias}",
            'fecha_envio_rhitso': orden.fecha_envio_rhitso,
            'dias_habiles_sic': dias_habiles_sic,
            'dias_habiles_rhitso': dias_habiles_rhitso,
            'dias_sin_actualizar': dias_sin_actualizar,
            'estado_proceso': estado_proceso,
            'fecha_ultimo_comentario': fecha_ultimo_comentario,
            'ultimo_comentario': ultimo_comentario if ultimo_comentario else 'Sin comentario',
        }
        
        # Clasificar orden en categoría correspondiente
        if estado_rhitso_nombre in estados_excluidos:
            excluidos.append(orden_data)
        elif estado_rhitso_nombre in estados_pendientes:
            pendientes.append(orden_data)
        else:
            activos.append(orden_data)
    
    # =========================================================================
    # PASO 2: CREAR WORKBOOK DE EXCEL
    # =========================================================================
    
    # EXPLICACIÓN: Workbook es el archivo Excel completo
    wb = openpyxl.Workbook()
    
    # Eliminar la hoja por defecto
    if 'Sheet' in wb.sheetnames:
        del wb['Sheet']
    
    # =========================================================================
    # PASO 3: DEFINIR ESTILOS PROFESIONALES (COMO INVENTARIO)
    # =========================================================================
    
    # EXPLICACIÓN: Definimos estilos reutilizables para mantener consistencia
    
    # Fuente para encabezados: Blanco, negrita, tamaño 11
    header_font = Font(
        name='Calibri',
        bold=True,
        color="FFFFFF",
        size=11
    )
    
    # Relleno azul para encabezados (#366092 es el azul corporativo)
    header_fill = PatternFill(
        start_color="366092",
        end_color="366092",
        fill_type="solid"
    )
    
    # Alineación centrada para encabezados
    header_alignment = Alignment(
        horizontal='center',
        vertical='center',
        wrap_text=True
    )
    
    # Bordes para todas las celdas
    thin_border = Border(
        left=Side(style='thin', color='000000'),
        right=Side(style='thin', color='000000'),
        top=Side(style='thin', color='000000'),
        bottom=Side(style='thin', color='000000')
    )
    
    # Fuente normal para datos
    normal_font = Font(name='Calibri', size=10)
    
    # Alineación para comentarios (con wrap text)
    wrap_alignment = Alignment(
        horizontal='left',
        vertical='top',
        wrap_text=True
    )
    
    # =========================================================================
    # PASO 4: DEFINIR ENCABEZADOS (17 COLUMNAS)
    # =========================================================================
    
    # EXPLICACIÓN: Estos son los títulos de las columnas que aparecerán en Excel
    headers = [
        'Servicio Cliente',
        'N° Serie',
        'Marca',
        'Modelo',
        'Fecha Ingreso a SIC',
        'Sucursal',
        'Estado General',
        'Estado RHITSO',
        'Owner',
        'Incidencias',
        'Fecha Envío RHITSO',
        'Días Hábiles SIC',
        'Días Hábiles RHITSO',
        'Días en estatus',
        'Estado Proceso',
        'Fecha Último Comentario',
        'Comentario'
    ]
    
    # Anchos óptimos para cada columna (en caracteres)
    column_widths = [20, 15, 15, 15, 18, 15, 18, 25, 15, 12, 18, 18, 18, 15, 20, 20, 50]
    
    # =========================================================================
    # PASO 5: FUNCIÓN AUXILIAR PARA CREAR HOJAS FORMATEADAS
    # =========================================================================
    
    def crear_hoja_excel(nombre_hoja, datos_lista, color_categoria):
        """
        Crea una hoja de Excel con formato profesional.

        """
        # Crear la hoja
        ws = wb.create_sheet(nombre_hoja)
        
        # PASO 5.1: Agregar encabezados con estilo
        for col_num, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
        
        # PASO 5.2: Configurar anchos de columna
        for col_num, width in enumerate(column_widths, start=1):
            column_letter = get_column_letter(col_num)
            ws.column_dimensions[column_letter].width = width
        
        # PASO 5.3: Congelar primera fila (encabezados)
        # EXPLICACIÓN: freeze_panes permite que los encabezados permanezcan
        # visibles cuando el usuario hace scroll hacia abajo
        ws.freeze_panes = 'A2'
        
        # PASO 5.4: Agregar datos fila por fila
        for row_num, orden in enumerate(datos_lista, start=2):
            # Preparar los valores de cada columna
            valores = [
                orden['orden_cliente'],
                orden['numero_serie'],
                orden['marca'],
                orden['modelo'],
                orden['fecha_ingreso'].strftime('%d/%m/%Y') if orden['fecha_ingreso'] else '',
                orden['sucursal'],
                orden['estado_orden'],
                orden['estado_rhitso_display'],
                orden['owner_actual'],
                orden['total_incidencias'],
                orden['fecha_envio_rhitso'].strftime('%d/%m/%Y') if orden['fecha_envio_rhitso'] else 'No enviado',
                orden['dias_habiles_sic'],
                orden['dias_habiles_rhitso'],
                orden['dias_sin_actualizar'],
                orden['estado_proceso'],
                orden['fecha_ultimo_comentario'].strftime('%d/%m/%Y %H:%M') if orden['fecha_ultimo_comentario'] else 'Sin comentario',
                orden['ultimo_comentario']
            ]
            
            # Escribir valores en las celdas
            for col_num, valor in enumerate(valores, start=1):
                cell = ws.cell(row=row_num, column=col_num, value=valor)
                cell.font = normal_font
                cell.border = thin_border
                
                # Aplicar wrap text en la columna de comentarios (última columna)
                if col_num == len(headers):  # Columna de comentario
                    cell.alignment = wrap_alignment
                else:
                    cell.alignment = Alignment(horizontal='left', vertical='center')
            
            # PASO 5.5: Colorear fila según estado y urgencia
            # EXPLICACIÓN: Aplicamos colores para identificar visualmente el estado
            
            estado_proc = orden['estado_proceso']
            dias_sin_act = orden['dias_sin_actualizar']
            
            # Determinar color de fila
            row_fill = None
            
            if estado_proc == 'Completado':
                # Verde claro para órdenes completadas
                row_fill = PatternFill(start_color="D4EDDA", end_color="D4EDDA", fill_type="solid")
            elif estado_proc == 'En RHITSO':
                # Amarillo claro para órdenes en RHITSO
                row_fill = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid")
            elif estado_proc == 'Solo en SIC':
                # Gris claro para órdenes solo en SIC
                row_fill = PatternFill(start_color="E2E3E5", end_color="E2E3E5", fill_type="solid")
            
            # Sobrescribir con rojo si tiene más de 5 días sin actualizar (URGENTE)
            if dias_sin_act > 5:
                row_fill = PatternFill(start_color="F8D7DA", end_color="F8D7DA", fill_type="solid")
            
            # Aplicar el color a toda la fila
            if row_fill:
                for col_num in range(1, len(headers) + 1):
                    ws.cell(row=row_num, column=col_num).fill = row_fill
        
        # PASO 5.6: Agregar auto-filtro a los encabezados
        # EXPLICACIÓN: Permite al usuario filtrar datos directamente en Excel
        ws.auto_filter.ref = ws.dimensions
    
    # =========================================================================
    # PASO 6: CREAR LAS 3 HOJAS
    # =========================================================================
    
    # Hoja 1: Activos
    crear_hoja_excel(f"Activos ({len(activos)})", activos, "FFF3CD")
    
    # Hoja 2: Pendientes
    crear_hoja_excel(f"Pendientes ({len(pendientes)})", pendientes, "E2E3E5")
    
    # Hoja 3: Excluidos
    crear_hoja_excel(f"Excluidos ({len(excluidos)})", excluidos, "F8D7DA")
    
    # =========================================================================
    # PASO 7: PREPARAR RESPUESTA HTTP PARA DESCARGA
    # =========================================================================
    
    # EXPLICACIÓN: Creamos una respuesta HTTP con el tipo de contenido adecuado
    # para que el navegador sepa que es un archivo Excel y lo descargue
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    
    # Definir el nombre del archivo con fecha y hora actual
    nombre_archivo = f'Reporte_RHITSO_{timezone.now().strftime("%Y%m%d_%H%M")}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    
    # Guardar el workbook en la respuesta
    wb.save(response)
    
    return response


@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def exportar_analisis_rhitso(request):
    """
    Genera y descarga el reporte Excel del embudo de conversión RHITSO.

    Incluye resumen de KPIs, detalle de candidatos, rechazos de cotización
    con observaciones y órdenes sin decisión de envío.

    Args:
        request: HttpRequest con filtros opcionales fecha_inicio, fecha_fin, sucursal.

    Returns:
        HttpResponse con archivo Excel (.xlsx) para descarga.
    """
    from .utils_rhitso_analytics import (
        obtener_embudo_rhitso,
        obtener_filas_hoja_rechazos_y_no_aptos,
        obtener_detalle_todas_candidatas,
    )

    fecha_inicio = request.GET.get('fecha_inicio', '') or None
    fecha_fin = request.GET.get('fecha_fin', '') or None
    sucursal_id = request.GET.get('sucursal', '') or None

    embudo = obtener_embudo_rhitso(fecha_inicio, fecha_fin, sucursal_id)
    detalle_candidatos = obtener_detalle_todas_candidatas(fecha_inicio, fecha_fin, sucursal_id)
    comentarios_rechazo = obtener_filas_hoja_rechazos_y_no_aptos(embudo['candidatos_qs'])

    wb = openpyxl.Workbook()
    if 'Sheet' in wb.sheetnames:
        del wb['Sheet']

    header_font = Font(name='Calibri', bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin_border = Border(
        left=Side(style='thin', color='000000'),
        right=Side(style='thin', color='000000'),
        top=Side(style='thin', color='000000'),
        bottom=Side(style='thin', color='000000'),
    )
    normal_font = Font(name='Calibri', size=10)
    wrap_alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
    title_font = Font(name='Calibri', bold=True, size=14, color='FFFFFF')
    title_fill = PatternFill(start_color='212529', end_color='212529', fill_type='solid')
    kpi_label_font = Font(name='Calibri', bold=True, size=11)
    kpi_value_font = Font(name='Calibri', bold=True, size=12, color='366092')

    filtros_texto = f"Período ingreso: {fecha_inicio or 'Inicio'} — {fecha_fin or 'Hoy'}"
    if sucursal_id:
        filtros_texto += f" | Sucursal ID: {sucursal_id}"

    def aplicar_encabezados(ws, headers, fila=1):
        """Escribe encabezados con estilo corporativo en la hoja indicada."""
        for col_idx, titulo in enumerate(headers, start=1):
            celda = ws.cell(row=fila, column=col_idx, value=titulo)
            celda.font = header_font
            celda.fill = header_fill
            celda.alignment = header_alignment
            celda.border = thin_border

    def ajustar_anchos(ws, anchos):
        """Configura ancho de columnas según lista de caracteres."""
        for idx, ancho in enumerate(anchos, start=1):
            ws.column_dimensions[get_column_letter(idx)].width = ancho

    # -------------------------------------------------------------------------
    # HOJA 1: RESUMEN DEL EMBUDO
    # -------------------------------------------------------------------------
    ws_resumen = wb.create_sheet('Resumen')
    ws_resumen.merge_cells('A1:D1')
    titulo = ws_resumen['A1']
    titulo.value = 'Análisis RHITSO — Embudo de Conversión'
    titulo.font = title_font
    titulo.fill = title_fill
    titulo.alignment = Alignment(horizontal='center', vertical='center')

    ws_resumen.merge_cells('A2:D2')
    subtitulo = ws_resumen['A2']
    subtitulo.value = filtros_texto
    subtitulo.font = Font(name='Calibri', italic=True, size=10, color='666666')
    subtitulo.alignment = Alignment(horizontal='center')

    fila_kpi = 4
    resumen_filas = [
        ('NIVEL 1 — Candidatos RHITSO', embudo['total_candidatos'], '100%', ''),
        ('', '', '', ''),
        ('NIVEL 2 — Decisión de envío a RHITSO', '', '', ''),
        ('  Aceptaron envío', embudo['acepto_envio_count'], f"{embudo['acepto_envio_pct']}%", 'sobre candidatos'),
        ('  Rechazaron envío', embudo['rechazo_envio_count'], f"{embudo['rechazo_envio_pct']}%", 'sobre candidatos'),
        ('  Sin decisión de envío', embudo['sin_decision_envio_count'], f"{embudo['sin_decision_envio_pct']}%", 'sobre candidatos'),
        ('', '', '', ''),
        ('NIVEL 3 — Cohorte: aceptaron envío', embudo['total_cohorte_acepto'], '', 'base cohorte'),
        ('  Cliente acepta cotización', embudo['acepto_cotiz_count'], f"{embudo['acepto_cotiz_pct']}%", 'sobre cohorte'),
        ('  Cliente no acepta cotización', embudo['rechazo_cotiz_count'], f"{embudo['rechazo_cotiz_pct']}%", 'sobre cohorte'),
        ('  No apto para reparación', embudo['no_apto_count'], f"{embudo['no_apto_pct']}%", 'sobre cohorte'),
        ('  En proceso (sin esos estados)', embudo['en_proceso_cohorte_count'], f"{embudo['en_proceso_cohorte_pct']}%", 'sobre cohorte'),
    ]

    ws_resumen.cell(row=3, column=1, value='Métrica').font = kpi_label_font
    ws_resumen.cell(row=3, column=2, value='Cantidad').font = kpi_label_font
    ws_resumen.cell(row=3, column=3, value='%').font = kpi_label_font
    ws_resumen.cell(row=3, column=4, value='Referencia').font = kpi_label_font

    for etiqueta, cantidad, pct, ref in resumen_filas:
        ws_resumen.cell(row=fila_kpi, column=1, value=etiqueta).font = normal_font
        if cantidad != '':
            celda_cnt = ws_resumen.cell(row=fila_kpi, column=2, value=cantidad)
            celda_cnt.font = kpi_value_font
        ws_resumen.cell(row=fila_kpi, column=3, value=pct).font = normal_font
        ws_resumen.cell(row=fila_kpi, column=4, value=ref).font = Font(name='Calibri', size=9, color='888888')
        fila_kpi += 1

    nota_fila = fila_kpi + 1
    ws_resumen.merge_cells(f'A{nota_fila}:D{nota_fila + 2}')
    nota = ws_resumen[f'A{nota_fila}']
    nota.value = (
        'Nota: Las métricas se basan en estados RHITSO registrados en SeguimientoRHITSO. '
        'Si el técnico no actualiza el estado en el panel RHITSO, el embudo puede mostrar '
        '"sin decisión" aunque exista respuesta en el flujo SIC de cotización.'
    )
    nota.font = Font(name='Calibri', italic=True, size=9, color='666666')
    nota.alignment = wrap_alignment

    ajustar_anchos(ws_resumen, [42, 14, 10, 22])

    # -------------------------------------------------------------------------
    # HOJA 2: DETALLE CANDIDATOS
    # -------------------------------------------------------------------------
    ws_detalle = wb.create_sheet('Detalle Candidatos')
    headers_detalle = [
        'ID Orden', 'Orden Cliente', 'N° Serie', 'Marca', 'Modelo', 'Sucursal',
        'Fecha Ingreso', 'Técnico Asignado',
        'Estado RHITSO Actual', 'Estado Orden SIC',
        'Aceptó Envío', 'Rechazó Envío', 'Aceptó Cotiz.', 'Rechazó Cotiz.', 'No Apto',
    ]
    aplicar_encabezados(ws_detalle, headers_detalle)

    for row_idx, fila in enumerate(detalle_candidatos, start=2):
        valores = [
            fila['id'],
            fila['orden_cliente'],
            fila['numero_serie'],
            fila['marca'],
            fila['modelo'],
            fila['sucursal'],
            fila['fecha_ingreso'].strftime('%d/%m/%Y %H:%M') if fila['fecha_ingreso'] else '',
            fila['tecnico_asignado'],
            fila['estado_rhitso_actual'],
            fila['estado_orden'],
            'Sí' if fila['acepto_envio'] else 'No',
            'Sí' if fila['rechazo_envio'] else 'No',
            'Sí' if fila['acepto_cotiz'] else 'No',
            'Sí' if fila['rechazo_cotiz'] else 'No',
            'Sí' if fila['no_apto'] else 'No',
        ]
        for col_idx, valor in enumerate(valores, start=1):
            celda = ws_detalle.cell(row=row_idx, column=col_idx, value=valor)
            celda.font = normal_font
            celda.border = thin_border
            celda.alignment = wrap_alignment

    ajustar_anchos(ws_detalle, [10, 22, 16, 14, 18, 14, 18, 26, 30, 18, 12, 12, 12, 12, 10])
    ws_detalle.freeze_panes = 'A2'

    # -------------------------------------------------------------------------
    # HOJA 3: RECHAZOS COTIZACIÓN Y NO APTOS (con observaciones)
    # -------------------------------------------------------------------------
    ws_rechazos = wb.create_sheet('Rechazos Cotización')
    headers_rechazos = [
        'Orden Cliente', 'N° Serie', 'Marca', 'Modelo', 'Sucursal',
        'Estado RHITSO', 'Fecha Cambio Estado', 'Usuario', 'Observaciones / Motivo',
    ]
    aplicar_encabezados(ws_rechazos, headers_rechazos)

    for row_idx, seg in enumerate(comentarios_rechazo, start=2):
        detalle = seg.orden.detalle_equipo
        usuario_nombre = ''
        if seg.usuario_actualizacion:
            usuario_nombre = str(seg.usuario_actualizacion)
        estado_rhitso = seg.estado.estado if seg.estado else 'N/A'
        observaciones = (seg.observaciones or '').strip()
        if not observaciones:
            observaciones = 'Sin comentario disponible'
        valores = [
            detalle.orden_cliente if detalle else 'N/A',
            detalle.numero_serie if detalle else 'N/A',
            detalle.marca if detalle else 'N/A',
            detalle.modelo if detalle else 'N/A',
            seg.orden.sucursal.nombre if seg.orden.sucursal else 'N/A',
            estado_rhitso,
            seg.fecha_actualizacion.strftime('%d/%m/%Y %H:%M'),
            usuario_nombre,
            observaciones,
        ]
        for col_idx, valor in enumerate(valores, start=1):
            celda = ws_rechazos.cell(row=row_idx, column=col_idx, value=valor)
            celda.font = normal_font
            celda.border = thin_border
            celda.alignment = wrap_alignment

    ajustar_anchos(ws_rechazos, [22, 16, 14, 18, 14, 28, 18, 22, 55])
    ws_rechazos.freeze_panes = 'A2'

    # -------------------------------------------------------------------------
    # HOJA 4: SIN DECISIÓN DE ENVÍO
    # -------------------------------------------------------------------------
    ws_sin_decision = wb.create_sheet('Sin Decisión Envío')
    headers_sin = [
        'ID Orden', 'Orden Cliente', 'N° Serie', 'Marca', 'Modelo',
        'Sucursal', 'Fecha Ingreso', 'Estado RHITSO Actual',
    ]
    aplicar_encabezados(ws_sin_decision, headers_sin)

    sin_decision_filas = [
        construir_fila
        for construir_fila in detalle_candidatos
        if not construir_fila['acepto_envio'] and not construir_fila['rechazo_envio']
    ]

    for row_idx, fila in enumerate(sin_decision_filas, start=2):
        valores = [
            fila['id'],
            fila['orden_cliente'],
            fila['numero_serie'],
            fila['marca'],
            fila['modelo'],
            fila['sucursal'],
            fila['fecha_ingreso'].strftime('%d/%m/%Y %H:%M') if fila['fecha_ingreso'] else '',
            fila['estado_rhitso_actual'],
        ]
        for col_idx, valor in enumerate(valores, start=1):
            celda = ws_sin_decision.cell(row=row_idx, column=col_idx, value=valor)
            celda.font = normal_font
            celda.border = thin_border
            celda.alignment = wrap_alignment

    ajustar_anchos(ws_sin_decision, [10, 22, 16, 14, 18, 14, 18, 30])
    ws_sin_decision.freeze_panes = 'A2'

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    nombre_archivo = f'Analisis_RHITSO_{timezone.now().strftime("%Y%m%d_%H%M")}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    wb.save(response)
    return response


# ============================================================================
# DASHBOARD DE SEGUIMIENTO ESPECIALIZADO OOW-/FL-
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@cache_page_dashboard
def dashboard_seguimiento_oow_fl(request):
    """
    Dashboard especializado para seguimiento de órdenes con prefijo OOW- y FL-.

    Returns:
        HttpResponse: Renderiza el template con todo el contexto de datos
    """
    from django.db.models import Q, Count, Sum, Avg, F, When, Case, Value, CharField
    from django.db.models.functions import Coalesce
    from decimal import Decimal
    from datetime import timedelta
    from .utils_rhitso import (
        calcular_dias_habiles,
        calcular_dias_por_estatus,
        calcular_promedio_dias_por_estatus,
        agrupar_ordenes_por_mes
    )
    
    # =========================================================================
    # PASO 1: OBTENER FILTROS DE LA URL
    # =========================================================================
    
    responsable_id = request.GET.get('responsable_id', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    estado_filtro = request.GET.get('estado', '')
    sucursal_id = request.GET.get('sucursal_id', '')
    prefijo_filtro = request.GET.get('prefijo', 'ambos')  # 'OOW', 'FL', o 'ambos'
    
    # =========================================================================
    # PASO 2: CONSTRUIR QUERY BASE (FILTRO PRINCIPAL POR PREFIJO)
    # =========================================================================
    
    # Query base: órdenes con prefijo OOW- o FL- en orden_cliente
    if prefijo_filtro == 'OOW':
        ordenes = OrdenServicio.objects.filter(
            detalle_equipo__orden_cliente__istartswith='OOW-'
        )
    elif prefijo_filtro == 'FL':
        ordenes = OrdenServicio.objects.filter(
            detalle_equipo__orden_cliente__istartswith='FL-'
        )
    else:  # 'ambos' (default)
        ordenes = OrdenServicio.objects.filter(
            Q(detalle_equipo__orden_cliente__istartswith='OOW-') |
            Q(detalle_equipo__orden_cliente__istartswith='FL-')
        )
    
    # Optimizar consultas con select_related y prefetch_related
    ordenes = ordenes.select_related(
        'detalle_equipo',
        'sucursal',
        'responsable_seguimiento',
        'tecnico_asignado_actual',
        'venta_mostrador',
        'cotizacion'
    ).prefetch_related(
        'historial'
    )
    
    # =========================================================================
    # PASO 3: APLICAR FILTROS ADICIONALES
    # =========================================================================
    
    if responsable_id == 'sin_asignar':
        # Filtrar solo órdenes sin responsable asignado
        ordenes = ordenes.filter(responsable_seguimiento__isnull=True)
    elif responsable_id:
        ordenes = ordenes.filter(responsable_seguimiento_id=responsable_id)
    
    if fecha_desde:
        try:
            from datetime import datetime
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            ordenes = ordenes.filter(fecha_ingreso__date__gte=fecha_desde_obj)
        except ValueError:
            pass  # Ignorar si el formato es inválido
    
    if fecha_hasta:
        try:
            from datetime import datetime
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            ordenes = ordenes.filter(fecha_ingreso__date__lte=fecha_hasta_obj)
        except ValueError:
            pass
    
    if estado_filtro:
        ordenes = ordenes.filter(estado=estado_filtro)
    
    if sucursal_id:
        ordenes = ordenes.filter(sucursal_id=sucursal_id)
    
    # =========================================================================
    # PASO 4: CALCULAR MÉTRICAS GENERALES
    # =========================================================================
    
    total_ordenes = ordenes.count()
    
    # Contar por estado
    ordenes_activas = ordenes.exclude(estado__in=['entregado', 'cancelado']).count()
    ordenes_finalizadas = ordenes.filter(estado='finalizado').count()
    ordenes_entregadas = ordenes.filter(estado='entregado').count()
    
    # Contar ventas mostrador
    total_ventas_mostrador = ordenes.filter(venta_mostrador__isnull=False).count()
    
    # Contar con cotización
    total_con_cotizacion = ordenes.filter(cotizacion__isnull=False).count()
    cotizaciones_aceptadas = ordenes.filter(
        cotizacion__isnull=False,
        cotizacion__usuario_acepto=True
    ).count()
    cotizaciones_pendientes = ordenes.filter(
        cotizacion__isnull=False,
        cotizacion__usuario_acepto__isnull=True
    ).count()
    cotizaciones_rechazadas = ordenes.filter(
        cotizacion__isnull=False,
        cotizacion__usuario_acepto=False
    ).count()
    
    # Calcular montos totales
    monto_total_ventas_mostrador = Decimal('0.00')
    monto_total_cotizaciones = Decimal('0.00')
    
    for orden in ordenes:
        if hasattr(orden, 'venta_mostrador') and orden.venta_mostrador:
            monto_total_ventas_mostrador += orden.venta_mostrador.total_venta
        
        if hasattr(orden, 'cotizacion') and orden.cotizacion:
            if orden.cotizacion.usuario_acepto:
                monto_total_cotizaciones += orden.cotizacion.costo_total_final
    
    monto_total_general = monto_total_ventas_mostrador + monto_total_cotizaciones
    
    # Calcular tiempo promedio (días hábiles)
    total_dias_habiles = 0
    ordenes_con_tiempo = 0
    
    for orden in ordenes:
        dias = orden.dias_habiles_en_servicio
        if dias >= 0:
            total_dias_habiles += dias
            ordenes_con_tiempo += 1
    
    tiempo_promedio = round(total_dias_habiles / ordenes_con_tiempo, 1) if ordenes_con_tiempo > 0 else 0
    
    # Calcular % en tiempo (<= 15 días hábiles)
    ordenes_en_tiempo = sum(1 for orden in ordenes if orden.dias_habiles_en_servicio <= 15)
    porcentaje_en_tiempo = round((ordenes_en_tiempo / total_ordenes) * 100, 1) if total_ordenes > 0 else 0
    
    # Calcular ingreso promedio diario
    if fecha_desde and fecha_hasta:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            dias_rango = calcular_dias_habiles(fecha_desde_obj, fecha_hasta_obj)
            if dias_rango > 0:
                ingreso_promedio_dia = round(total_ordenes / dias_rango, 1)
            else:
                ingreso_promedio_dia = 0
        except:
            ingreso_promedio_dia = 0
    else:
        ingreso_promedio_dia = 0
    
    # =========================================================================
    # PASO 5: AGRUPAR POR RESPONSABLE DE SEGUIMIENTO
    # =========================================================================
    
    responsables_data = {}
    
    for orden in ordenes:
        # EXPLICACIÓN: Algunas órdenes OOW/FL pueden no tener responsable asignado.
        # En ese caso usamos id=0 y nombre "Sin asignar" para no romper el dashboard.
        if orden.responsable_seguimiento:
            resp_id = orden.responsable_seguimiento.id
            resp_nombre = orden.responsable_seguimiento.nombre_completo
        else:
            resp_id = 0
            resp_nombre = "Sin asignar"
        
        if resp_id not in responsables_data:
            responsables_data[resp_id] = {
                'id': resp_id,
                'nombre': resp_nombre,
                'total_ordenes': 0,
                'ordenes_activas': 0,
                'ordenes_finalizadas': 0,
                'ordenes_entregadas': 0,
                'ventas_mostrador': 0,
                'con_cotizacion': 0,
                'cotizaciones_aceptadas': 0,
                'cotizaciones_pendientes': 0,
                'cotizaciones_rechazadas': 0,
                'monto_ventas_mostrador': Decimal('0.00'),
                'monto_cotizaciones': Decimal('0.00'),
                'dias_acumulados': 0,
            }
        
        # Acumular estadísticas
        responsables_data[resp_id]['total_ordenes'] += 1
        
        if orden.estado not in ['entregado', 'cancelado']:
            responsables_data[resp_id]['ordenes_activas'] += 1
        
        if orden.estado == 'finalizado':
            responsables_data[resp_id]['ordenes_finalizadas'] += 1
        
        if orden.estado == 'entregado':
            responsables_data[resp_id]['ordenes_entregadas'] += 1
        
        if hasattr(orden, 'venta_mostrador') and orden.venta_mostrador:
            responsables_data[resp_id]['ventas_mostrador'] += 1
            responsables_data[resp_id]['monto_ventas_mostrador'] += orden.venta_mostrador.total_venta
        
        if hasattr(orden, 'cotizacion') and orden.cotizacion:
            responsables_data[resp_id]['con_cotizacion'] += 1
            if orden.cotizacion.usuario_acepto is True:
                responsables_data[resp_id]['cotizaciones_aceptadas'] += 1
                responsables_data[resp_id]['monto_cotizaciones'] += orden.cotizacion.costo_total_final
            elif orden.cotizacion.usuario_acepto is False:
                responsables_data[resp_id]['cotizaciones_rechazadas'] += 1
            else:
                # Si es None (null), está pendiente
                responsables_data[resp_id]['cotizaciones_pendientes'] += 1
        
        responsables_data[resp_id]['dias_acumulados'] += orden.dias_habiles_en_servicio
    
    # Calcular promedios y montos totales por responsable
    for resp_id, data in responsables_data.items():
        if data['total_ordenes'] > 0:
            data['tiempo_promedio'] = round(data['dias_acumulados'] / data['total_ordenes'], 1)
            # Tasa de finalización = porcentaje de órdenes ENTREGADAS
            data['tasa_finalizacion'] = round(
                (data['ordenes_entregadas'] / data['total_ordenes']) * 100,
                1
            )
        else:
            data['tiempo_promedio'] = 0
            data['tasa_finalizacion'] = 0
        
        data['monto_total'] = data['monto_ventas_mostrador'] + data['monto_cotizaciones']
    
    # Convertir a lista y ordenar por total de órdenes (descendente)
    responsables_lista = sorted(
        responsables_data.values(),
        key=lambda x: x['total_ordenes'],
        reverse=True
    )
    
    # =========================================================================
    # PASO 5.5: PREPARAR GRÁFICO 1 - VENTAS MOSTRADOR POR RESPONSABLE + CATEGORÍA
    # =========================================================================
    
    # Crear estructura con datos de ventas mostrador por responsable
    # Incluyendo la categoría de producto vendido
    grafico_ventas_mostrador_responsables = {
        'labels': [],  # Nombres de responsables
        'data': [],  # Montos en $
        'categorias': [],  # Categoría de producto vendido
        'iconos': [],  # Emojis para visual
        'desglose': [],  # NUEVO: Desglose completo de productos por responsable
    }
    
    # Filtrar responsables que tengan ventas mostrador > 0
    responsables_con_ventas = [
        r for r in responsables_lista 
        if r['ventas_mostrador'] > 0
    ]
    
    # Para cada responsable con ventas, obtener categoría de producto
    for responsable in responsables_con_ventas:
        resp_id = responsable['id']
        
        # Obtener todas las órdenes de este responsable con venta mostrador
        # EXPLICACIÓN: Mismo manejo seguro — si no tiene responsable, su id es 0
        ordenes_resp = [
            o for o in ordenes
            if (o.responsable_seguimiento.id if o.responsable_seguimiento else 0) == resp_id
        ]
        
        # NUEVO: Crear desglose detallado de productos vendidos por este responsable
        productos_responsable = {}  # {descripcion: {cantidad, subtotal, categoria}}
        categorias_contador = {}
        
        for orden in ordenes_resp:
            if hasattr(orden, 'venta_mostrador') and orden.venta_mostrador:
                venta = orden.venta_mostrador
                
                # ===== INCLUIR PAQUETES =====
                if venta.paquete != 'ninguno':
                    desc_paquete = f"Paquete {venta.paquete.upper()}"
                    costo_paq = float(venta.costo_paquete)
                    
                    if desc_paquete not in productos_responsable:
                        productos_responsable[desc_paquete] = {
                            'cantidad': 0,
                            'subtotal': 0
                        }
                    
                    productos_responsable[desc_paquete]['cantidad'] += 1
                    productos_responsable[desc_paquete]['subtotal'] += costo_paq
                
                # ===== INCLUIR SERVICIOS =====
                servicios_venta = []
                
                if venta.incluye_cambio_pieza and venta.costo_cambio_pieza > 0:
                    servicios_venta.append({
                        'nombre': 'Cambio de Pieza',
                        'costo': float(venta.costo_cambio_pieza)
                    })
                
                if venta.incluye_limpieza and venta.costo_limpieza > 0:
                    servicios_venta.append({
                        'nombre': 'Limpieza y Mantenimiento',
                        'costo': float(venta.costo_limpieza)
                    })
                
                if venta.incluye_kit_limpieza and venta.costo_kit > 0:
                    servicios_venta.append({
                        'nombre': 'Kit de Limpieza',
                        'costo': float(venta.costo_kit)
                    })
                
                if venta.incluye_reinstalacion_so and venta.costo_reinstalacion > 0:
                    servicios_venta.append({
                        'nombre': 'Reinstalación SO',
                        'costo': float(venta.costo_reinstalacion)
                    })
                
                # Agregar servicios al desglose
                for servicio in servicios_venta:
                    desc_servicio = servicio['nombre']
                    costo_servicio = servicio['costo']
                    
                    if desc_servicio not in productos_responsable:
                        productos_responsable[desc_servicio] = {
                            'cantidad': 0,
                            'subtotal': 0
                        }
                    
                    productos_responsable[desc_servicio]['cantidad'] += 1
                    productos_responsable[desc_servicio]['subtotal'] += costo_servicio
                
                # ===== INCLUIR PIEZAS INDIVIDUALES =====
                piezas = venta.piezas_vendidas.all()
                for pieza in piezas:
                    desc = pieza.descripcion_pieza[:50]  # Truncar descripción
                    
                    if desc not in productos_responsable:
                        productos_responsable[desc] = {
                            'cantidad': 0,
                            'subtotal': 0
                        }
                    
                    productos_responsable[desc]['cantidad'] += pieza.cantidad
                    productos_responsable[desc]['subtotal'] += float(pieza.subtotal)
                
                # Contar categorías
                cat_info = determinar_categoria_venta(venta)
                categoria = cat_info['categoria']
                categorias_contador[categoria] = categorias_contador.get(categoria, 0) + 1
        
        # Obtener la categoría más vendida
        if categorias_contador:
            categoria_principal = max(categorias_contador, key=categorias_contador.get)
            # Obtener información de la primera venta para obtener icono
            primera_venta = None
            for orden in ordenes_resp:
                if hasattr(orden, 'venta_mostrador') and orden.venta_mostrador:
                    primera_venta = orden.venta_mostrador
                    break
            
            cat_info = determinar_categoria_venta(primera_venta) if primera_venta else {'categoria': 'Desconocido', 'icono': '❓'}
        else:
            cat_info = {'categoria': 'Sin categoría', 'icono': '❌'}
        
        # NUEVO: Ordenar productos por subtotal (mayor primero)
        productos_ordenados = sorted(
            productos_responsable.items(),
            key=lambda x: x[1]['subtotal'],
            reverse=True
        )
        
        # Convertir a formato para tooltip
        desglose_texto = []
        for desc, info in productos_ordenados[:10]:  # Top 10 productos
            desglose_texto.append({
                'descripcion': desc,
                'cantidad': info['cantidad'],
                'subtotal': info['subtotal']
            })
        
        # Agregar datos al gráfico
        grafico_ventas_mostrador_responsables['labels'].append(responsable['nombre'])
        grafico_ventas_mostrador_responsables['data'].append(float(responsable['monto_ventas_mostrador']))
        grafico_ventas_mostrador_responsables['categorias'].append(cat_info['categoria'])
        grafico_ventas_mostrador_responsables['iconos'].append(cat_info['icono'])
        grafico_ventas_mostrador_responsables['desglose'].append(desglose_texto)
    
    # =========================================================================
    # PASO 5.6: PREPARAR GRÁFICO 2 - TOP PRODUCTOS VENDIDOS
    # =========================================================================
    
    top_productos = obtener_top_productos_vendidos(ordenes, limite=5)
    
    grafico_top_productos = {
        'labels': [p['descripcion'][:30] for p in top_productos],  # Truncar descripciones largas
        'data': [int(p['cantidad']) for p in top_productos],
        'montos': [float(p['subtotal']) for p in top_productos],
    }
    
    # =========================================================================
    # PASO 6: CALCULAR DÍAS PROMEDIO POR ESTATUS
    # =========================================================================
    
    # Obtener estadísticas separadas: estados de proceso vs estados finales
    resultado_dias_por_estatus = calcular_promedio_dias_por_estatus(ordenes)
    
    # Estados de proceso (sin entregado/cancelado) - para la tabla principal
    dias_por_estatus_proceso = resultado_dias_por_estatus['estados_proceso']
    
    # Estados finales (entregado/cancelado) - para mostrar por separado
    dias_por_estatus_finales = resultado_dias_por_estatus['estados_finales']
    
    # =========================================================================
    # PASO 7: GENERAR DATOS MENSUALES
    # =========================================================================
    
    datos_mensuales = agrupar_ordenes_por_mes(ordenes)
    
    # =========================================================================
    # PASO 8: IDENTIFICAR ALERTAS
    # =========================================================================
    
    alertas = {
        'retrasadas': [],  # >15 días hábiles
        'sin_actualizacion': [],  # >5 días sin cambio de estado
        'cotizaciones_pendientes': [],  # >7 días sin respuesta
        'en_reparacion_larga': [],  # >10 días en estado 'reparacion'
    }
    
    # Función auxiliar para construir datos de alerta con información completa
    def construir_datos_alerta(orden, dias, tipo_dias='hábiles'):
        """
        Construye un diccionario con toda la información necesaria para mostrar
        una alerta en el dashboard de forma profesional.
        
        Args:
            orden: Instancia de OrdenServicio
            dias: Número de días de la alerta
            tipo_dias: Descripción del tipo de días (hábiles, sin respuesta, etc.)
        
        Returns:
            dict: Diccionario con datos completos de la alerta
        """
        return {
            'orden': orden,
            'dias': dias,
            'tipo_dias': tipo_dias,
            # Información adicional para tablas mejoradas
            'orden_cliente': orden.detalle_equipo.orden_cliente if orden.detalle_equipo else 'N/A',
            'estado': orden.get_estado_display(),
            'estado_codigo': orden.estado,
            'responsable': orden.responsable_seguimiento.nombre_completo if orden.responsable_seguimiento else 'Sin asignar',
            'modelo': orden.detalle_equipo.modelo if orden.detalle_equipo else 'N/A',
            'gama': orden.detalle_equipo.get_gama_display() if orden.detalle_equipo and hasattr(orden.detalle_equipo, 'get_gama_display') else orden.detalle_equipo.gama if orden.detalle_equipo else 'N/A',
            'es_candidato_rhitso': orden.es_candidato_rhitso,
        }
    
    for orden in ordenes:
        # Retrasadas (>15 días hábiles sin entregar)
        # Excluir estados finales: entregado y cancelado
        if orden.estado not in ['entregado', 'cancelado'] and orden.dias_habiles_en_servicio > 15:
            alertas['retrasadas'].append(
                construir_datos_alerta(orden, orden.dias_habiles_en_servicio, 'días hábiles')
            )
        
        # Sin actualización (>5 días hábiles)
        dias_sin_act = orden.dias_sin_actualizacion_estado
        if dias_sin_act > 5 and orden.estado not in ['entregado', 'cancelado']:
            alertas['sin_actualizacion'].append(
                construir_datos_alerta(orden, dias_sin_act, 'días sin cambio')
            )
        
        # Cotizaciones pendientes (>7 días sin respuesta)
        if hasattr(orden, 'cotizacion') and orden.cotizacion:
            if orden.cotizacion.usuario_acepto is None and orden.cotizacion.dias_sin_respuesta > 7:
                alertas['cotizaciones_pendientes'].append(
                    construir_datos_alerta(orden, orden.cotizacion.dias_sin_respuesta, 'días sin respuesta')
                )
        
        # En reparación prolongada (>10 días en estado reparacion)
        if orden.estado == 'reparacion':
            dias_por_estado = calcular_dias_por_estatus(orden)
            dias_reparacion = dias_por_estado.get('reparacion', 0)
            if dias_reparacion > 10:
                alertas['en_reparacion_larga'].append(
                    construir_datos_alerta(orden, dias_reparacion, 'días en reparación')
                )
    
    # Ordenar alertas por días (mayor a menor) para priorizar las más críticas
    for tipo_alerta in alertas:
        alertas[tipo_alerta].sort(key=lambda x: x['dias'], reverse=True)
    
    # =========================================================================
    # PASO 9: PREPARAR DATOS PARA GRÁFICOS (Chart.js)
    # =========================================================================
    
    # Gráfico 1: Órdenes por responsable
    grafico_responsables = {
        'labels': [r['nombre'] for r in responsables_lista],
        'data': [r['total_ordenes'] for r in responsables_lista],
    }
    
    # Gráfico 2: Días promedio por estatus
    # Ordenar estados en el orden lógico del proceso (sin estados finales)
    # Los estados finales (entregado/cancelado) se muestran por separado
    orden_estados = ['espera', 'diagnostico', 'cotizacion', 'reparacion', 'finalizado', 'control_calidad']
    estados_ordenados = []
    dias_ordenados = []
    
    # Buscar cada estado en los datos de proceso
    # Nota: dias_por_estatus_proceso tiene claves formateadas (ej: 'Control Calidad')
    for estado_codigo in orden_estados:
        # Convertir código a nombre formateado para buscar en el diccionario
        nombre_formateado = estado_codigo.replace('_', ' ').title()
        if nombre_formateado in dias_por_estatus_proceso:
            estados_ordenados.append(nombre_formateado)
            dias_ordenados.append(dias_por_estatus_proceso[nombre_formateado]['promedio'])
    
    grafico_dias_estatus = {
        'labels': estados_ordenados,
        'data': dias_ordenados,
    }
    
    # Gráfico 3: Evolución mensual (últimos 6 meses)
    meses_recientes = datos_mensuales[-6:] if len(datos_mensuales) > 6 else datos_mensuales
    
    grafico_evolucion_mensual = {
        'labels': [m['mes'] for m in meses_recientes],
        'data_ordenes': [m['total_ordenes'] for m in meses_recientes],
        'data_finalizadas': [m['ordenes_finalizadas'] for m in meses_recientes],
        'data_entregadas': [m['ordenes_entregadas'] for m in meses_recientes],
    }
    
    # Gráfico 4: Distribución por estado
    estados_distribucion = {}
    for orden in ordenes:
        estado = orden.get_estado_display()
        estados_distribucion[estado] = estados_distribucion.get(estado, 0) + 1
    
    grafico_distribucion_estados = {
        'labels': list(estados_distribucion.keys()),
        'data': list(estados_distribucion.values()),
    }
    
    # =========================================================================
    # PASO 10: OBTENER LISTAS PARA FILTROS
    # =========================================================================
    
    # Lista de responsables para filtro
    lista_responsables = Empleado.objects.filter(
        ordenes_responsable__in=ordenes
    ).distinct().order_by('nombre_completo')
    
    # Lista de sucursales para filtro
    lista_sucursales = Sucursal.objects.filter(
        ordenes_servicio__in=ordenes
    ).distinct().order_by('nombre')
    
    # Lista de estados para filtro (choices del modelo)
    from config.constants import ESTADO_ORDEN_CHOICES
    lista_estados = ESTADO_ORDEN_CHOICES
    
    # =========================================================================
    # PASO 11: PREPARAR CONTEXTO COMPLETO
    # =========================================================================
    
    context = {
        # Filtros actuales
        'filtros': {
            'responsable_id': responsable_id,
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta,
            'estado': estado_filtro,
            'sucursal_id': sucursal_id,
            'prefijo': prefijo_filtro,
        },
        
        # Listas para selectores de filtros
        'lista_responsables': lista_responsables,
        'lista_sucursales': lista_sucursales,
        'lista_estados': lista_estados,
        
        # Métricas generales
        'metricas': {
            'total_ordenes': total_ordenes,
            'ordenes_activas': ordenes_activas,
            'ordenes_finalizadas': ordenes_finalizadas,
            'ordenes_entregadas': ordenes_entregadas,
            'total_ventas_mostrador': total_ventas_mostrador,
            'total_con_cotizacion': total_con_cotizacion,
            'cotizaciones_aceptadas': cotizaciones_aceptadas,
            'cotizaciones_pendientes': cotizaciones_pendientes,
            'cotizaciones_rechazadas': cotizaciones_rechazadas,
            'monto_ventas_mostrador': monto_total_ventas_mostrador,
            'monto_cotizaciones': monto_total_cotizaciones,
            'monto_total': monto_total_general,
            'tiempo_promedio': tiempo_promedio,
            'porcentaje_en_tiempo': porcentaje_en_tiempo,
            'ingreso_promedio_dia': ingreso_promedio_dia,
        },
        
        # Datos por responsable
        'responsables': responsables_lista,
        
        # Días por estatus - SEPARADOS: proceso vs finales
        # 'dias_por_estatus' contiene SOLO estados de proceso (sin entregado/cancelado)
        # 'dias_por_estatus_finales' contiene estadísticas de cierre (entregado/cancelado)
        'dias_por_estatus': dias_por_estatus_proceso,
        'dias_por_estatus_finales': dias_por_estatus_finales,
        
        # Datos mensuales
        'datos_mensuales': datos_mensuales,
        'meses_recientes': meses_recientes,
        
        # Alertas
        'alertas': alertas,
        'total_alertas': (
            len(alertas['retrasadas']) +
            len(alertas['sin_actualizacion']) +
            len(alertas['cotizaciones_pendientes']) +
            len(alertas['en_reparacion_larga'])
        ),
        
        # Datos para gráficos
        'grafico_responsables': grafico_responsables,
        'grafico_dias_estatus': grafico_dias_estatus,
        'grafico_evolucion_mensual': grafico_evolucion_mensual,
        'grafico_distribucion_estados': grafico_distribucion_estados,
        
        # NUEVOS GRÁFICOS: Ventas Mostrador
        'grafico_ventas_mostrador_responsables': grafico_ventas_mostrador_responsables,
        'grafico_top_productos': grafico_top_productos,
        
        # Órdenes completas (para tabla detallada)
        'ordenes': ordenes[:100],  # Limitar a 100 para rendimiento inicial
        'total_ordenes_tabla': ordenes.count(),
    }
    
    return render(request, 'servicio_tecnico/dashboard_seguimiento_oow_fl.html', context)


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
def exportar_excel_dashboard_oow_fl(request):
    """
    Exporta el dashboard OOW-/FL- a Excel con múltiples hojas de análisis

    Requiere: openpyxl instalado (pip install openpyxl)
    
    Returns:
        HttpResponse: Archivo Excel para descarga
    """
    from django.http import HttpResponse
    from django.db.models import Q
    from datetime import datetime
    
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
        from .excel_exporters import (
            get_header_style, get_title_style, get_kpi_title_style, get_kpi_value_style,
            get_estado_color, apply_cell_style, auto_adjust_column_width,
            calcular_metricas_generales, calcular_distribucion_estados,
            calcular_estadisticas_por_responsable, calcular_top_productos,
            calcular_estadisticas_por_sucursal
        )
    except ImportError as e:
        from django.http import JsonResponse
        return JsonResponse({
            'success': False,
            'error': f'Error al importar librerías: {str(e)}. Asegúrate de tener openpyxl instalado.'
        })
    
    # =========================================================================
    # PASO 1: OBTENER FILTROS Y CONSTRUIR QUERY (IGUAL QUE EL DASHBOARD)
    # =========================================================================
    
    responsable_id = request.GET.get('responsable_id', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    estado_filtro = request.GET.get('estado', '')
    sucursal_id = request.GET.get('sucursal_id', '')
    prefijo_filtro = request.GET.get('prefijo', 'ambos')
    
    # Query base: órdenes con prefijo OOW- o FL-
    if prefijo_filtro == 'OOW':
        ordenes = OrdenServicio.objects.filter(
            detalle_equipo__orden_cliente__istartswith='OOW-'
        )
    elif prefijo_filtro == 'FL':
        ordenes = OrdenServicio.objects.filter(
            detalle_equipo__orden_cliente__istartswith='FL-'
        )
    else:  # 'ambos' (default)
        ordenes = OrdenServicio.objects.filter(
            Q(detalle_equipo__orden_cliente__istartswith='OOW-') |
            Q(detalle_equipo__orden_cliente__istartswith='FL-')
        )
    
    # Optimizar consultas
    ordenes = ordenes.select_related(
        'detalle_equipo',
        'sucursal',
        'responsable_seguimiento',
        'tecnico_asignado_actual',
        'venta_mostrador',
        'cotizacion'
    ).prefetch_related('historial')
    
    # Aplicar filtros adicionales
    if responsable_id == 'sin_asignar':
        ordenes = ordenes.filter(responsable_seguimiento__isnull=True)
    elif responsable_id:
        ordenes = ordenes.filter(responsable_seguimiento_id=responsable_id)
    
    if fecha_desde:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            ordenes = ordenes.filter(fecha_ingreso__date__gte=fecha_desde_obj)
        except ValueError:
            pass
    
    if fecha_hasta:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            ordenes = ordenes.filter(fecha_ingreso__date__lte=fecha_hasta_obj)
        except ValueError:
            pass
    
    if estado_filtro:
        ordenes = ordenes.filter(estado=estado_filtro)
    
    if sucursal_id:
        ordenes = ordenes.filter(sucursal_id=sucursal_id)
    
    # Ordenar por fecha de ingreso
    ordenes = ordenes.order_by('-fecha_ingreso')
    
    # =========================================================================
    # PASO 2: CALCULAR MÉTRICAS Y ESTADÍSTICAS
    # =========================================================================
    
    metricas = calcular_metricas_generales(ordenes)
    distribucion_estados = calcular_distribucion_estados(ordenes)
    responsables_stats = calcular_estadisticas_por_responsable(ordenes)
    top_productos = calcular_top_productos(ordenes, limite=10)
    sucursales_stats = calcular_estadisticas_por_sucursal(ordenes)
    
    # =========================================================================
    # PASO 3: CREAR WORKBOOK
    # =========================================================================
    
    wb = Workbook()
    wb.remove(wb.active)  # Eliminar hoja predeterminada
    
    # =========================================================================
    # HOJA 1: RESUMEN GENERAL
    # =========================================================================
    
    ws1 = wb.create_sheet("Resumen General")
    
    # Título principal
    ws1.merge_cells('A1:F1')
    title_cell = ws1['A1']
    
    # Determinar texto de filtros para el título
    filtros_texto = []
    if prefijo_filtro != 'ambos':
        filtros_texto.append(f"Prefijo: {prefijo_filtro}-")
    if responsable_id == 'sin_asignar':
        filtros_texto.append("Responsable: Sin asignar")
    elif responsable_id:
        try:
            resp = Empleado.objects.get(id=responsable_id)
            filtros_texto.append(f"Responsable: {resp.nombre_completo}")
        except:
            pass
    if fecha_desde or fecha_hasta:
        rango = f"Desde: {fecha_desde or 'inicio'} Hasta: {fecha_hasta or 'hoy'}"
        filtros_texto.append(rango)
    
    filtros_str = " | ".join(filtros_texto) if filtros_texto else "Todos los registros"
    
    title_cell.value = f"DASHBOARD OOW-/FL- - {datetime.now().strftime('%d/%m/%Y')} - {filtros_str}"
    apply_cell_style(title_cell, get_title_style())
    ws1.row_dimensions[1].height = 30
    
    # KPIs Principales
    row = 3
    ws1.merge_cells(f'A{row}:F{row}')
    kpi_section = ws1[f'A{row}']
    kpi_section.value = "📊 INDICADORES CLAVE (KPIs)"
    apply_cell_style(kpi_section, get_kpi_title_style())
    
    row += 2
    kpis_data = [
        ('Total de Órdenes OOW-/FL-', metricas['total_ordenes']),
        ('Órdenes Activas', metricas['ordenes_activas']),
        ('Órdenes Entregadas', metricas['ordenes_entregadas']),
        ('Órdenes Finalizadas', metricas['ordenes_finalizadas']),
        ('', ''),  # Separador
        ('Ventas Mostrador', metricas['total_ventas_mostrador']),
        ('Monto Ventas Mostrador', f"${metricas['monto_ventas_mostrador']:,.2f}"),
        ('', ''),  # Separador
        ('Total con Cotización', metricas['total_con_cotizacion']),
        ('Cotizaciones Aceptadas ✅', metricas['cotizaciones_aceptadas']),
        ('Cotizaciones Pendientes ⏳', metricas['cotizaciones_pendientes']),
        ('Cotizaciones Rechazadas ❌', metricas['cotizaciones_rechazadas']),
        ('Monto Cotizaciones', f"${metricas['monto_cotizaciones']:,.2f}"),
        ('', ''),  # Separador
        ('Monto Total Generado', f"${metricas['monto_total']:,.2f}"),
        ('Tiempo Promedio (días hábiles)', metricas['tiempo_promedio']),
        ('% en Tiempo (≤15 días)', f"{metricas['porcentaje_en_tiempo']}%"),
    ]
    
    for kpi_name, kpi_value in kpis_data:
        if kpi_name == '':  # Fila vacía como separador
            row += 1
            continue
            
        ws1[f'A{row}'] = kpi_name
        ws1[f'B{row}'] = kpi_value
        apply_cell_style(ws1[f'A{row}'], get_kpi_title_style())
        apply_cell_style(ws1[f'B{row}'], get_kpi_value_style())
        row += 1
    
    # Distribución por Estado
    row += 2
    ws1.merge_cells(f'A{row}:C{row}')
    dist_section = ws1[f'A{row}']
    dist_section.value = "📈 DISTRIBUCIÓN POR ESTADO"
    apply_cell_style(dist_section, get_kpi_title_style())
    
    row += 1
    ws1[f'A{row}'] = 'Estado'
    ws1[f'B{row}'] = 'Cantidad'
    ws1[f'C{row}'] = '% del Total'
    apply_cell_style(ws1[f'A{row}'], get_header_style())
    apply_cell_style(ws1[f'B{row}'], get_header_style())
    apply_cell_style(ws1[f'C{row}'], get_header_style())
    
    row += 1
    for estado, cantidad in distribucion_estados.items():
        porcentaje = round((cantidad / metricas['total_ordenes'] * 100), 1) if metricas['total_ordenes'] > 0 else 0
        ws1[f'A{row}'] = estado
        ws1[f'B{row}'] = cantidad
        ws1[f'C{row}'] = f"{porcentaje}%"
        row += 1
    
    auto_adjust_column_width(ws1)
    
    # =========================================================================
    # HOJA 2: CONSOLIDADO POR RESPONSABLE
    # =========================================================================
    
    ws2 = wb.create_sheet("Consolidado Responsables")
    
    # Título
    ws2.merge_cells('A1:K1')
    title_cell = ws2['A1']
    title_cell.value = "ANÁLISIS CONSOLIDADO POR RESPONSABLE DE SEGUIMIENTO"
    apply_cell_style(title_cell, get_title_style())
    ws2.row_dimensions[1].height = 25
    
    # Encabezados
    headers_resp = [
        'Responsable', 'Total Órdenes', 'Activas', 'Entregadas',
        'Ventas Mostrador', 'Monto VM', 'Cotizaciones Aceptadas',
        'Monto Cotizaciones', 'Monto Total', 'Tiempo Promedio (días)',
        'Tasa Entrega (%)'
    ]
    for col_num, header in enumerate(headers_resp, 1):
        cell = ws2.cell(row=3, column=col_num)
        cell.value = header
        apply_cell_style(cell, get_header_style())
    
    # Datos por responsable
    row = 4
    for resp in responsables_stats:
        ws2.cell(row=row, column=1).value = resp['nombre']
        ws2.cell(row=row, column=2).value = resp['total_ordenes']
        ws2.cell(row=row, column=3).value = resp['ordenes_activas']
        ws2.cell(row=row, column=4).value = resp['ordenes_entregadas']
        ws2.cell(row=row, column=5).value = resp['ventas_mostrador']
        ws2.cell(row=row, column=6).value = f"${resp['monto_ventas_mostrador']:,.2f}"
        ws2.cell(row=row, column=7).value = resp['cotizaciones_aceptadas']
        ws2.cell(row=row, column=8).value = f"${resp['monto_cotizaciones']:,.2f}"
        ws2.cell(row=row, column=9).value = f"${resp['monto_total']:,.2f}"
        ws2.cell(row=row, column=10).value = resp['tiempo_promedio']
        ws2.cell(row=row, column=11).value = f"{resp['tasa_entrega']}%"
        row += 1
    
    auto_adjust_column_width(ws2)
    
    # =========================================================================
    # HOJA 3: TOP PRODUCTOS VENDIDOS
    # =========================================================================
    
    ws3 = wb.create_sheet("Top Productos")
    
    # Título
    ws3.merge_cells('A1:D1')
    title_cell = ws3['A1']
    title_cell.value = "TOP PRODUCTOS/SERVICIOS MÁS VENDIDOS (VENTAS MOSTRADOR)"
    apply_cell_style(title_cell, get_title_style())
    ws3.row_dimensions[1].height = 25
    
    # Encabezados
    headers_prod = ['#', 'Producto/Servicio', 'Cantidad Vendida', 'Monto Total']
    for col_num, header in enumerate(headers_prod, 1):
        cell = ws3.cell(row=3, column=col_num)
        cell.value = header
        apply_cell_style(cell, get_header_style())
    
    # Datos de productos
    row = 4
    for idx, prod in enumerate(top_productos, 1):
        ws3.cell(row=row, column=1).value = idx
        ws3.cell(row=row, column=2).value = prod['descripcion']
        ws3.cell(row=row, column=3).value = prod['cantidad']
        ws3.cell(row=row, column=4).value = f"${prod['monto']:,.2f}"
        
        # Resaltar top 3
        if idx <= 3:
            color = '28a745' if idx == 1 else 'ffc107' if idx == 2 else '17a2b8'
            ws3.cell(row=row, column=1).fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
            ws3.cell(row=row, column=1).font = Font(bold=True, color="FFFFFF", size=12)
        
        row += 1
    
    auto_adjust_column_width(ws3)
    
    # =========================================================================
    # HOJA 4: ANÁLISIS POR SUCURSAL
    # =========================================================================
    
    ws4 = wb.create_sheet("Por Sucursal")
    
    # Título
    ws4.merge_cells('A1:E1')
    title_cell = ws4['A1']
    title_cell.value = "ANÁLISIS POR SUCURSAL"
    apply_cell_style(title_cell, get_title_style())
    ws4.row_dimensions[1].height = 25
    
    # Encabezados
    headers_suc = ['Sucursal', 'Total Órdenes', 'Ventas Mostrador', 'Cotizaciones', 'Monto Total']
    for col_num, header in enumerate(headers_suc, 1):
        cell = ws4.cell(row=3, column=col_num)
        cell.value = header
        apply_cell_style(cell, get_header_style())
    
    # Datos por sucursal
    row = 4
    for suc in sucursales_stats:
        ws4.cell(row=row, column=1).value = suc['nombre']
        ws4.cell(row=row, column=2).value = suc['total_ordenes']
        ws4.cell(row=row, column=3).value = suc['ventas_mostrador']
        ws4.cell(row=row, column=4).value = suc['cotizaciones']
        ws4.cell(row=row, column=5).value = f"${suc['monto_total']:,.2f}"
        row += 1
    
    auto_adjust_column_width(ws4)
    
    # =========================================================================
    # HOJAS INDIVIDUALES POR RESPONSABLE (CON SEPARACIÓN ACTIVAS/CERRADAS)
    # =========================================================================
    
    for resp_stat in responsables_stats:
        # Crear hoja con nombre del responsable (límite de 31 caracteres para Excel)
        nombre_hoja = resp_stat['nombre'][:28]
        ws_resp = wb.create_sheet(nombre_hoja)
        
        # Título con nombre del responsable
        ws_resp.merge_cells('A1:P1')
        title_cell = ws_resp['A1']
        title_cell.value = f"REPORTE INDIVIDUAL - {resp_stat['nombre']}"
        apply_cell_style(title_cell, get_title_style())
        ws_resp.row_dimensions[1].height = 25
        
        # Resumen de estadísticas personales
        row = 3
        ws_resp[f'A{row}'] = "📊 ESTADÍSTICAS PERSONALES"
        apply_cell_style(ws_resp[f'A{row}'], get_kpi_title_style())
        row += 2
        
        stats_personales = [
            ('Total de Órdenes:', resp_stat['total_ordenes']),
            ('Órdenes Activas:', resp_stat['ordenes_activas']),
            ('Órdenes Entregadas:', resp_stat['ordenes_entregadas']),
            ('Tiempo Promedio:', f"{resp_stat['tiempo_promedio']} días"),
            ('Tasa de Entrega:', f"{resp_stat['tasa_entrega']}%"),
            ('', ''),  # Separador
            ('Ventas Mostrador:', resp_stat['ventas_mostrador']),
            ('Monto Ventas Mostrador:', f"${resp_stat['monto_ventas_mostrador']:,.2f}"),
            ('', ''),  # Separador
            ('Cotizaciones Aceptadas:', resp_stat['cotizaciones_aceptadas']),
            ('Cotizaciones Pendientes:', resp_stat['cotizaciones_pendientes']),
            ('Cotizaciones Rechazadas:', resp_stat['cotizaciones_rechazadas']),
            ('Monto Cotizaciones:', f"${resp_stat['monto_cotizaciones']:,.2f}"),
            ('', ''),  # Separador
            ('MONTO TOTAL GENERADO:', f"${resp_stat['monto_total']:,.2f}"),
        ]
        
        for stat_name, stat_value in stats_personales:
            if stat_name == '':
                row += 1
                continue
            
            ws_resp[f'A{row}'] = stat_name
            ws_resp[f'B{row}'] = stat_value
            apply_cell_style(ws_resp[f'A{row}'], get_kpi_title_style())
            
            # Resaltar el monto total
            if 'MONTO TOTAL' in stat_name:
                ws_resp[f'B{row}'].fill = PatternFill(start_color="28a745", end_color="28a745", fill_type="solid")
                ws_resp[f'B{row}'].font = Font(bold=True, size=14, color="FFFFFF")
            else:
                apply_cell_style(ws_resp[f'B{row}'], get_kpi_value_style())
            
            row += 1
        
        # Obtener órdenes del responsable.
        # EXPLICACIÓN: Si el id es 0 significa "Sin asignar" — filtramos por NULL en la BD,
        # ya que no existe ningún empleado con id=0.
        if resp_stat['id'] == 0:
            ordenes_resp = ordenes.filter(responsable_seguimiento__isnull=True)
        else:
            ordenes_resp = ordenes.filter(responsable_seguimiento__id=resp_stat['id'])
        
        # ============== SECCIÓN: ÓRDENES ACTIVAS ==============
        row += 2
        ws_resp.merge_cells(f'A{row}:P{row}')
        activas_section = ws_resp[f'A{row}']
        ordenes_activas_resp = ordenes_resp.exclude(estado__in=['entregado', 'cancelado'])
        activas_section.value = f"🔄 ÓRDENES ACTIVAS ({ordenes_activas_resp.count()})"
        activas_section.fill = PatternFill(start_color="ffc107", end_color="ffc107", fill_type="solid")
        activas_section.font = Font(bold=True, size=12, color="000000")
        activas_section.alignment = Alignment(horizontal="left", vertical="center")
        
        row += 1
        
        # Encabezados de la tabla de órdenes activas
        headers_orden = [
            'N° Orden Cliente', 'N° de Serie', 'Tipo Equipo', 'Marca',
            'Modelo', 'Estado', 'Días Hábiles', 'Días Sin Actualizar',
            'Tipo de Orden', 'Monto', 'Sucursal', 'Fecha Ingreso',
            'Última Actualización', 'Cotización', 'Observaciones'
        ]
        for col_num, header in enumerate(headers_orden, 1):
            cell = ws_resp.cell(row=row, column=col_num)
            cell.value = header
            apply_cell_style(cell, get_header_style())
        
        row += 1
        
        # Datos de órdenes activas
        for orden in ordenes_activas_resp.order_by('-fecha_ingreso'):
            ws_resp.cell(row=row, column=1).value = orden.detalle_equipo.orden_cliente
            ws_resp.cell(row=row, column=2).value = orden.detalle_equipo.numero_serie if orden.detalle_equipo.numero_serie else 'N/A'
            ws_resp.cell(row=row, column=3).value = orden.detalle_equipo.get_tipo_equipo_display()
            ws_resp.cell(row=row, column=4).value = orden.detalle_equipo.marca
            ws_resp.cell(row=row, column=5).value = orden.detalle_equipo.modelo[:30] if orden.detalle_equipo.modelo else 'N/A'
            ws_resp.cell(row=row, column=6).value = orden.get_estado_display()
            ws_resp.cell(row=row, column=7).value = orden.dias_habiles_en_servicio
            ws_resp.cell(row=row, column=8).value = orden.dias_sin_actualizacion_estado
            
            # Tipo de orden
            tipo_orden = 'Servicio Normal'
            monto = 0
            if hasattr(orden, 'venta_mostrador') and orden.venta_mostrador:
                tipo_orden = 'Venta Mostrador'
                monto = float(orden.venta_mostrador.total_venta)
            elif hasattr(orden, 'cotizacion') and orden.cotizacion:
                if orden.cotizacion.usuario_acepto:
                    tipo_orden = 'Cotización Aceptada'
                    monto = float(orden.cotizacion.costo_total_final)
                elif orden.cotizacion.usuario_acepto is False:
                    tipo_orden = 'Cotización Rechazada'
                else:
                    tipo_orden = 'Cotización Pendiente'
            
            ws_resp.cell(row=row, column=9).value = tipo_orden
            ws_resp.cell(row=row, column=10).value = f"${monto:,.2f}" if monto > 0 else 'N/A'
            ws_resp.cell(row=row, column=11).value = orden.sucursal.nombre
            ws_resp.cell(row=row, column=12).value = orden.fecha_ingreso.strftime('%d/%m/%Y')
            
            # Última actualización (del historial)
            ultima_act = orden.historial.order_by('-fecha_evento').first()
            ws_resp.cell(row=row, column=13).value = ultima_act.fecha_evento.strftime('%d/%m/%Y') if ultima_act else 'N/A'
            
            # Estado de cotización
            cotiz_estado = 'N/A'
            if hasattr(orden, 'cotizacion') and orden.cotizacion:
                if orden.cotizacion.usuario_acepto is True:
                    cotiz_estado = '✅ Aceptada'
                elif orden.cotizacion.usuario_acepto is False:
                    cotiz_estado = '❌ Rechazada'
                else:
                    cotiz_estado = '⏳ Pendiente'
            ws_resp.cell(row=row, column=14).value = cotiz_estado
            
            # Observaciones/Alertas
            alertas = []
            if orden.dias_habiles_en_servicio > 15:
                alertas.append('⚠️ RETRASADA')
            if orden.dias_sin_actualizacion_estado > 5:
                alertas.append(f'🔴 Sin actualizar {orden.dias_sin_actualizacion_estado}d')
            ws_resp.cell(row=row, column=15).value = ' | '.join(alertas) if alertas else 'OK'
            
            # Colorear estado
            color_estado = get_estado_color(orden.estado)
            ws_resp.cell(row=row, column=6).fill = PatternFill(start_color=color_estado, end_color=color_estado, fill_type="solid")
            ws_resp.cell(row=row, column=6).font = Font(bold=True, color="FFFFFF")
            
            # Colorear días si está retrasada
            if orden.dias_habiles_en_servicio > 15:
                ws_resp.cell(row=row, column=7).fill = PatternFill(start_color="dc3545", end_color="dc3545", fill_type="solid")
                ws_resp.cell(row=row, column=7).font = Font(bold=True, color="FFFFFF")
            
            # Resaltar fila completa si es candidato RHITSO (morado claro)
            if orden.es_candidato_rhitso:
                rhitso_color = "ede9fe"  # Morado claro (igual que en dashboard)
                for col in range(1, 16):  # Columnas 1-15
                    cell = ws_resp.cell(row=row, column=col)
                    # Solo aplicar si la celda no tiene ya un color especial (estado, retrasada)
                    if col not in [6, 7] or (col == 7 and orden.dias_habiles_en_servicio <= 15):
                        cell.fill = PatternFill(start_color=rhitso_color, end_color=rhitso_color, fill_type="solid")
            
            row += 1
        
        # ============== SECCIÓN: ÓRDENES CERRADAS (ENTREGADAS) ==============
        row += 2
        ws_resp.merge_cells(f'A{row}:P{row}')
        cerradas_section = ws_resp[f'A{row}']
        ordenes_cerradas_resp = ordenes_resp.filter(estado__in=['entregado', 'cancelado'])
        cerradas_section.value = f"✅ ÓRDENES CERRADAS/ENTREGADAS ({ordenes_cerradas_resp.count()})"
        cerradas_section.fill = PatternFill(start_color="28a745", end_color="28a745", fill_type="solid")
        cerradas_section.font = Font(bold=True, size=12, color="FFFFFF")
        cerradas_section.alignment = Alignment(horizontal="left", vertical="center")
        
        row += 1
        
        # Encabezados (mismos que activas)
        for col_num, header in enumerate(headers_orden, 1):
            cell = ws_resp.cell(row=row, column=col_num)
            cell.value = header
            apply_cell_style(cell, get_header_style())
        
        row += 1
        
        # Datos de órdenes cerradas
        for orden in ordenes_cerradas_resp.order_by('-fecha_ingreso'):
            ws_resp.cell(row=row, column=1).value = orden.detalle_equipo.orden_cliente
            ws_resp.cell(row=row, column=2).value = orden.detalle_equipo.numero_serie if orden.detalle_equipo.numero_serie else 'N/A'
            ws_resp.cell(row=row, column=3).value = orden.detalle_equipo.get_tipo_equipo_display()
            ws_resp.cell(row=row, column=4).value = orden.detalle_equipo.marca
            ws_resp.cell(row=row, column=5).value = orden.detalle_equipo.modelo[:30] if orden.detalle_equipo.modelo else 'N/A'
            ws_resp.cell(row=row, column=6).value = orden.get_estado_display()
            ws_resp.cell(row=row, column=7).value = orden.dias_habiles_en_servicio
            ws_resp.cell(row=row, column=8).value = orden.dias_sin_actualizacion_estado
            
            # Tipo de orden y monto
            tipo_orden = 'Servicio Normal'
            monto = 0
            if hasattr(orden, 'venta_mostrador') and orden.venta_mostrador:
                tipo_orden = 'Venta Mostrador'
                monto = float(orden.venta_mostrador.total_venta)
            elif hasattr(orden, 'cotizacion') and orden.cotizacion:
                if orden.cotizacion.usuario_acepto:
                    tipo_orden = 'Cotización Aceptada'
                    monto = float(orden.cotizacion.costo_total_final)
                elif orden.cotizacion.usuario_acepto is False:
                    tipo_orden = 'Cotización Rechazada'
                else:
                    tipo_orden = 'Cotización Pendiente'
            
            ws_resp.cell(row=row, column=9).value = tipo_orden
            ws_resp.cell(row=row, column=10).value = f"${monto:,.2f}" if monto > 0 else 'N/A'
            ws_resp.cell(row=row, column=11).value = orden.sucursal.nombre
            ws_resp.cell(row=row, column=12).value = orden.fecha_ingreso.strftime('%d/%m/%Y')
            
            ultima_act = orden.historial.order_by('-fecha_evento').first()
            ws_resp.cell(row=row, column=13).value = ultima_act.fecha_evento.strftime('%d/%m/%Y') if ultima_act else 'N/A'
            
            cotiz_estado = 'N/A'
            if hasattr(orden, 'cotizacion') and orden.cotizacion:
                if orden.cotizacion.usuario_acepto is True:
                    cotiz_estado = '✅ Aceptada'
                elif orden.cotizacion.usuario_acepto is False:
                    cotiz_estado = '❌ Rechazada'
                else:
                    cotiz_estado = '⏳ Pendiente'
            ws_resp.cell(row=row, column=14).value = cotiz_estado
            
            # Para órdenes cerradas, solo mostrar si fue cancelada
            ws_resp.cell(row=row, column=15).value = '❌ CANCELADA' if orden.estado == 'cancelado' else 'Completada'
            
            # Colorear estado
            color_estado = get_estado_color(orden.estado)
            ws_resp.cell(row=row, column=6).fill = PatternFill(start_color=color_estado, end_color=color_estado, fill_type="solid")
            ws_resp.cell(row=row, column=6).font = Font(bold=True, color="FFFFFF")
            
            # Resaltar fila completa si es candidato RHITSO (morado claro)
            if orden.es_candidato_rhitso:
                rhitso_color = "ede9fe"  # Morado claro (igual que en dashboard)
                for col in range(1, 16):  # Columnas 1-15
                    cell = ws_resp.cell(row=row, column=col)
                    # Solo aplicar si la celda no tiene ya un color especial (estado)
                    if col != 6:
                        cell.fill = PatternFill(start_color=rhitso_color, end_color=rhitso_color, fill_type="solid")
            
            row += 1
        
        auto_adjust_column_width(ws_resp)
    
    # =========================================================================
    # HOJA FINAL: TODAS LAS ÓRDENES (LISTA MAESTRA COMPLETA)
    # =========================================================================
    
    ws_all = wb.create_sheet("Todas las Órdenes")
    
    # Título
    ws_all.merge_cells('A1:Q1')
    title_cell = ws_all['A1']
    title_cell.value = f"LISTA MAESTRA - TODAS LAS ÓRDENES OOW-/FL- ({ordenes.count()} registros)"
    apply_cell_style(title_cell, get_title_style())
    ws_all.row_dimensions[1].height = 25
    
    # Encabezados completos
    headers_all = [
        'N° Orden Cliente', 'N° de Serie', 'Tipo Equipo', 'Marca',
        'Modelo', 'Estado', 'Responsable Seguimiento', 'Técnico Asignado',
        'Días Hábiles', 'Días Sin Actualizar', 'Tipo de Orden', 'Monto',
        'Sucursal', 'Fecha Ingreso', 'Última Actualización', 'Cotización',
        'Observaciones/Alertas'
    ]
    
    for col_num, header in enumerate(headers_all, 1):
        cell = ws_all.cell(row=3, column=col_num)
        cell.value = header
        apply_cell_style(cell, get_header_style())
    
    # Datos de todas las órdenes
    row = 4
    for orden in ordenes:
        ws_all.cell(row=row, column=1).value = orden.detalle_equipo.orden_cliente
        ws_all.cell(row=row, column=2).value = orden.detalle_equipo.numero_serie if orden.detalle_equipo.numero_serie else 'N/A'
        ws_all.cell(row=row, column=3).value = orden.detalle_equipo.get_tipo_equipo_display()
        ws_all.cell(row=row, column=4).value = orden.detalle_equipo.marca
        ws_all.cell(row=row, column=5).value = orden.detalle_equipo.modelo[:30] if orden.detalle_equipo.modelo else 'N/A'
        ws_all.cell(row=row, column=6).value = orden.get_estado_display()
        ws_all.cell(row=row, column=7).value = orden.responsable_seguimiento.nombre_completo if orden.responsable_seguimiento else 'Sin asignar'
        ws_all.cell(row=row, column=8).value = orden.tecnico_asignado_actual.nombre_completo if orden.tecnico_asignado_actual else 'No asignado'
        ws_all.cell(row=row, column=9).value = orden.dias_habiles_en_servicio
        ws_all.cell(row=row, column=10).value = orden.dias_sin_actualizacion_estado
        
        # Tipo de orden y monto
        tipo_orden = 'Servicio Normal'
        monto = 0
        if hasattr(orden, 'venta_mostrador') and orden.venta_mostrador:
            tipo_orden = 'Venta Mostrador'
            monto = float(orden.venta_mostrador.total_venta)
        elif hasattr(orden, 'cotizacion') and orden.cotizacion:
            if orden.cotizacion.usuario_acepto:
                tipo_orden = 'Cotización Aceptada'
                monto = float(orden.cotizacion.costo_total_final)
            elif orden.cotizacion.usuario_acepto is False:
                tipo_orden = 'Cotización Rechazada'
            else:
                tipo_orden = 'Cotización Pendiente'
        
        ws_all.cell(row=row, column=11).value = tipo_orden
        ws_all.cell(row=row, column=12).value = f"${monto:,.2f}" if monto > 0 else 'N/A'
        ws_all.cell(row=row, column=13).value = orden.sucursal.nombre
        ws_all.cell(row=row, column=14).value = orden.fecha_ingreso.strftime('%d/%m/%Y %H:%M')
        
        # Última actualización
        ultima_act = orden.historial.order_by('-fecha_evento').first()
        ws_all.cell(row=row, column=15).value = ultima_act.fecha_evento.strftime('%d/%m/%Y %H:%M') if ultima_act else 'N/A'
        
        # Estado de cotización
        cotiz_estado = 'N/A'
        if hasattr(orden, 'cotizacion') and orden.cotizacion:
            if orden.cotizacion.usuario_acepto is True:
                cotiz_estado = '✅ Aceptada'
            elif orden.cotizacion.usuario_acepto is False:
                cotiz_estado = '❌ Rechazada'
            else:
                cotiz_estado = '⏳ Pendiente'
        ws_all.cell(row=row, column=16).value = cotiz_estado
        
        # Observaciones/Alertas
        alertas = []
        if orden.estado not in ['entregado', 'cancelado']:
            if orden.dias_habiles_en_servicio > 15:
                alertas.append('⚠️ RETRASADA')
            if orden.dias_sin_actualizacion_estado > 5:
                alertas.append(f'🔴 Sin actualizar {orden.dias_sin_actualizacion_estado}d')
        else:
            if orden.estado == 'cancelado':
                alertas.append('❌ CANCELADA')
            else:
                alertas.append('✅ Completada')
        
        ws_all.cell(row=row, column=17).value = ' | '.join(alertas) if alertas else 'OK'
        
        # Colorear estado
        color_estado = get_estado_color(orden.estado)
        ws_all.cell(row=row, column=6).fill = PatternFill(start_color=color_estado, end_color=color_estado, fill_type="solid")
        ws_all.cell(row=row, column=6).font = Font(bold=True, color="FFFFFF")
        
        # Colorear días si está retrasada
        if orden.estado not in ['entregado', 'cancelado'] and orden.dias_habiles_en_servicio > 15:
            ws_all.cell(row=row, column=9).fill = PatternFill(start_color="dc3545", end_color="dc3545", fill_type="solid")
            ws_all.cell(row=row, column=9).font = Font(bold=True, color="FFFFFF")
        
        # Resaltar fila completa si es candidato RHITSO (morado claro)
        if orden.es_candidato_rhitso:
            rhitso_color = "ede9fe"  # Morado claro (igual que en dashboard)
            for col in range(1, 18):  # Columnas 1-17
                cell = ws_all.cell(row=row, column=col)
                # Solo aplicar si la celda no tiene ya un color especial (estado en col 6, días en col 9)
                es_celda_estado = (col == 6)
                es_celda_retrasada = (col == 9 and orden.estado not in ['entregado', 'cancelado'] and orden.dias_habiles_en_servicio > 15)
                if not es_celda_estado and not es_celda_retrasada:
                    cell.fill = PatternFill(start_color=rhitso_color, end_color=rhitso_color, fill_type="solid")
        
        row += 1
    
    auto_adjust_column_width(ws_all)
    
    # =========================================================================
    # GENERAR NOMBRE DEL ARCHIVO Y RESPUESTA HTTP
    # =========================================================================
    
    # Generar nombre descriptivo del archivo
    fecha_str = datetime.now().strftime('%Y-%m-%d')
    
    # Determinar si hay filtros específicos
    nombre_archivo_partes = ['Dashboard_OOW_FL']
    
    if prefijo_filtro != 'ambos':
        nombre_archivo_partes.append(f'Prefijo_{prefijo_filtro}')
    
    if responsable_id == 'sin_asignar':
        nombre_archivo_partes.append('Resp_Sin_Asignar')
    elif responsable_id:
        try:
            resp = Empleado.objects.get(id=responsable_id)
            # Limpiar nombre para usar en archivo
            nombre_limpio = resp.nombre_completo.replace(' ', '_')[:20]
            nombre_archivo_partes.append(f'Resp_{nombre_limpio}')
        except:
            pass
    
    if estado_filtro:
        nombre_archivo_partes.append(f'Estado_{estado_filtro}')
    
    if sucursal_id:
        try:
            suc = Sucursal.objects.get(id=sucursal_id)
            nombre_limpio = suc.nombre.replace(' ', '_')[:15]
            nombre_archivo_partes.append(f'Suc_{nombre_limpio}')
        except:
            pass
    
    nombre_archivo_partes.append(fecha_str)
    nombre_archivo = '_'.join(nombre_archivo_partes) + '.xlsx'
    
    # Preparar respuesta HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    
    # Guardar el workbook en la respuesta
    wb.save(response)
    
    return response


# ============================================================================
# 📊 DASHBOARD DE COTIZACIONES - ANALYTICS CON PLOTLY Y MACHINE LEARNING
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@cache_page_dashboard
def dashboard_cotizaciones(request):
    """
    Dashboard analítico completo de cotizaciones tipo Power BI.

    Esta vista es el "cerebro" del dashboard. Hace lo siguiente:

    Query Parameters (filtros en URL):
        - fecha_inicio: Fecha inicio filtro (YYYY-MM-DD)
        - fecha_fin: Fecha fin filtro (YYYY-MM-DD)
        - sucursal: ID de sucursal
        - tecnico: ID de técnico
        - gama: Gama de equipo (alta/media/baja)
        - periodo: Agrupación temporal (D/W/M/Q/Y)
    
    Returns:
        HttpResponse: Página renderizada con el dashboard completo
    
    Ejemplo de URL:
        /cotizaciones/dashboard/?fecha_inicio=2025-01-01&fecha_fin=2025-12-31&sucursal=1&periodo=M
    """
    
    from datetime import datetime, timedelta
    import pandas as pd  # Necesario para pd.DataFrame() en bloques except
    from .utils_cotizaciones import (
        obtener_dataframe_cotizaciones,
        calcular_kpis_generales,
        analizar_piezas_cotizadas,
        analizar_proveedores,
        calcular_metricas_por_tecnico,
        calcular_metricas_por_sucursal,
        calcular_metricas_por_responsable,
        calcular_kpis_aceptaciones,
        analizar_servicios_vm_aceptadas,
        analizar_seguimiento_piezas_aceptadas
    )
    from .plotly_visualizations import DashboardCotizacionesVisualizer, convertir_figura_a_html
    from .ml_predictor import PredictorAceptacionCotizacion
    
    # NUEVO: Módulos ML Avanzados (Sistema Experto)
    from .ml_advanced import (
        PredictorMotivoRechazo,
        OptimizadorPrecios,
        RecomendadorAcciones
    )
    
    # ========================================
    # 1. OBTENER Y VALIDAR FILTROS DEL REQUEST
    # ========================================
    
    # Fechas por defecto: últimos 3 meses (timezone-aware)
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # timezone.now() devuelve datetime con zona horaria (timezone-aware)
    # Esto previene warnings de Django cuando se compara con DateTimeFields
    from django.utils import timezone as tz
    fecha_fin_default = tz.now().date()
    fecha_inicio_default = (tz.now() - timedelta(days=90)).date()
    
    # Capturar parámetros GET
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    sucursal_id = request.GET.get('sucursal')
    tecnico_id = request.GET.get('tecnico')
    gama = request.GET.get('gama')
    periodo = request.GET.get('periodo', 'M')  # Default: Mensual
    
    # Validar y parsear fechas (convertir a timezone-aware datetime)
    # EXPLICACIÓN: Los DateTimeFields en Django requieren datetimes timezone-aware
    # para evitar warnings. Convertimos date → datetime → timezone-aware
    try:
        if fecha_inicio_str:
            fecha_dt = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
            fecha_inicio = tz.make_aware(fecha_dt)
        else:
            # Convertir date a datetime timezone-aware (inicio del día)
            fecha_dt = datetime.combine(fecha_inicio_default, datetime.min.time())
            fecha_inicio = tz.make_aware(fecha_dt)
    except ValueError:
        fecha_dt = datetime.combine(fecha_inicio_default, datetime.min.time())
        fecha_inicio = tz.make_aware(fecha_dt)
    
    try:
        if fecha_fin_str:
            fecha_dt = datetime.strptime(fecha_fin_str, '%Y-%m-%d')
            # Para fecha_fin, usar fin del día (23:59:59.999999)
            fecha_dt = datetime.combine(fecha_dt.date(), datetime.max.time())
            fecha_fin = tz.make_aware(fecha_dt)
        else:
            # Convertir date a datetime timezone-aware (fin del día)
            fecha_dt = datetime.combine(fecha_fin_default, datetime.max.time())
            fecha_fin = tz.make_aware(fecha_dt)
    except ValueError:
        fecha_dt = datetime.combine(fecha_fin_default, datetime.max.time())
        fecha_fin = tz.make_aware(fecha_dt)
    
    # Validar período
    if periodo not in ['D', 'W', 'M', 'Q', 'Y']:
        periodo = 'M'
    
    # Convertir IDs a enteros si existen
    try:
        sucursal_id = int(sucursal_id) if sucursal_id else None
    except (ValueError, TypeError):
        sucursal_id = None
    
    try:
        tecnico_id = int(tecnico_id) if tecnico_id else None
    except (ValueError, TypeError):
        tecnico_id = None
    
    # ========================================
    # 2. OBTENER DATOS CON FILTROS
    # ========================================
    
    try:
        # Obtener DataFrame principal de cotizaciones
        df_cotizaciones = obtener_dataframe_cotizaciones(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            sucursal_id=sucursal_id,
            tecnico_id=tecnico_id,
            gama=gama
        )
        
        # Obtener IDs de cotizaciones para análisis relacionados
        cotizacion_ids = df_cotizaciones['cotizacion_id'].tolist() if not df_cotizaciones.empty else []
        
        # Análisis de piezas
        df_piezas = analizar_piezas_cotizadas(cotizacion_ids)
        
        # Análisis de proveedores
        df_seguimientos = analizar_proveedores(cotizacion_ids)
        
    except Exception as e:
        messages.error(request, f'Error al obtener datos: {str(e)}')
        df_cotizaciones = pd.DataFrame()
        df_piezas = pd.DataFrame()
        df_seguimientos = pd.DataFrame()
    
    # ========================================
    # 3. CALCULAR KPIs Y MÉTRICAS
    # ========================================
    
    if not df_cotizaciones.empty:
        # KPIs generales
        kpis = calcular_kpis_generales(df_cotizaciones)
        
        # Métricas por técnico
        df_metricas_tecnicos = calcular_metricas_por_tecnico(df_cotizaciones)
        
        # Métricas por sucursal
        df_metricas_sucursales = calcular_metricas_por_sucursal(df_cotizaciones)
        
        # Métricas por responsable de seguimiento
        df_metricas_responsables = calcular_metricas_por_responsable(df_cotizaciones)
    else:
        kpis = {
            'total_cotizaciones': 0,
            'aceptadas': 0,
            'rechazadas': 0,
            'pendientes': 0,
            'tasa_aceptacion': 0,
            'tasa_rechazo': 0,
            'valor_total_cotizado': 0,
            'valor_total_cotizado_fmt': '$0',
            'ticket_promedio': 0,
            'ticket_promedio_fmt': '$0'
        }
        df_metricas_tecnicos = pd.DataFrame()
        df_metricas_sucursales = pd.DataFrame()
        df_metricas_responsables = pd.DataFrame()
    
    # ========================================
    # 3.5. KPIs DE ACEPTACIONES Y ANÁLISIS VM
    # ========================================
    
    kpis_aceptaciones = {}
    analisis_vm = {}
    analisis_seguimiento = {}
    
    if not df_cotizaciones.empty:
        try:
            print("\n" + "="*50)
            print("✅ ANÁLISIS DE ACEPTACIONES Y VENTAS MOSTRADOR")
            print("="*50)
            
            kpis_aceptaciones = calcular_kpis_aceptaciones(df_cotizaciones)
            print(f"   - KPIs aceptaciones calculados: {kpis_aceptaciones.get('total_aceptadas', 0)} aceptadas")
            
            analisis_vm = analizar_servicios_vm_aceptadas(
                df_cotizaciones,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                sucursal_id=sucursal_id,
                tecnico_id=tecnico_id,
                gama=gama,
            )
            print(f"   - Análisis VM: {analisis_vm.get('total_con_vm', 0)} con venta mostrador")
            
            analisis_seguimiento = analizar_seguimiento_piezas_aceptadas(df_cotizaciones)
            print(f"   - Seguimiento piezas: {analisis_seguimiento.get('total_piezas_rastreadas', 0)} piezas rastreadas")
            
            print("✅ Análisis de aceptaciones completado")
            
        except Exception as e_acept:
            print(f"⚠️ Error en análisis de aceptaciones: {str(e_acept)}")
            kpis_aceptaciones = {}
            analisis_vm = {}
            analisis_seguimiento = {}
    
    # ========================================
    # 4. GENERAR VISUALIZACIONES
    # ========================================
    
    visualizer = DashboardCotizacionesVisualizer()
    graficos = {}
    
    if not df_cotizaciones.empty:
        try:
            # Usar función orquestadora para generar todos los gráficos
            graficos = visualizer.crear_dashboard_completo(
                df=df_cotizaciones,
                df_piezas=df_piezas if not df_piezas.empty else None,
                df_seguimientos=df_seguimientos if not df_seguimientos.empty else None,
                df_metricas_tecnicos=df_metricas_tecnicos if not df_metricas_tecnicos.empty else None,
                df_metricas_sucursales=df_metricas_sucursales if not df_metricas_sucursales.empty else None,
                df_metricas_responsables=df_metricas_responsables if not df_metricas_responsables.empty else None,
                kpis=kpis,
                ml_predictor=None,  # Lo agregamos después
                periodo=periodo,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                sucursal_id=sucursal_id,
                tecnico_id=tecnico_id,
                gama=gama,
            )
        except Exception as e:
            messages.warning(request, f'Algunos gráficos no se pudieron generar: {str(e)}')
            print(f"⚠️ Error generando gráficos: {str(e)}")
    else:
        # Sin datos, mostrar mensaje
        messages.info(request, 'No hay datos de cotizaciones con los filtros aplicados.')
    
    # ========================================
    # 5. MACHINE LEARNING (Si hay datos suficientes)
    # ========================================
    
    ml_insights = {
        'modelo_disponible': False,
        'accuracy': 0,
        'sugerencias': []
    }
    
    # NUEVO: Insights avanzados (sistema experto)
    ml_insights_avanzados = {
        'disponible': False,
        'predictor_motivos_disponible': False,
        'optimizador_disponible': False,
        'recomendador_disponible': False,
        'analisis_completo': None
    }
    
    if not df_cotizaciones.empty and len(df_cotizaciones) >= 20:
        try:
            # Inicializar predictor base
            predictor = PredictorAceptacionCotizacion()
            
            # Intentar cargar modelo existente
            try:
                predictor.cargar_modelo()
                print("✅ Modelo ML base cargado exitosamente")
            except FileNotFoundError:
                # Si no existe, entrenar con datos actuales
                print("⚠️ No se encontró modelo pre-entrenado, entrenando nuevo modelo...")
                predictor.entrenar_modelo(
                    fecha_inicio=fecha_inicio.strftime('%Y-%m-%d'),
                    fecha_fin=fecha_fin.strftime('%Y-%m-%d')
                )
            
            # Obtener métricas del modelo
            metricas_ml = predictor.obtener_metricas()
            
            # Generar gráfico de factores influyentes
            feature_importance = predictor.obtener_factores_influyentes(top_n=10)
            if feature_importance:
                graficos['factores_influyentes'] = convertir_figura_a_html(
                    visualizer.grafico_factores_influyentes(feature_importance)
                )
            
            # Generar sugerencias
            sugerencias = predictor.generar_sugerencias(df_cotizaciones)
            
            ml_insights = {
                'modelo_disponible': True,
                'accuracy': metricas_ml.get('accuracy', 0) * 100,  # Convertir a porcentaje
                'precision': metricas_ml.get('precision', 0) * 100,
                'recall': metricas_ml.get('recall', 0) * 100,
                'f1_score': metricas_ml.get('f1_score', 0) * 100,
                'total_muestras': metricas_ml.get('total_muestras', 0),
                'datos_entrenamiento': metricas_ml.get('total_muestras', 0),  # Agregado para el template
                'fecha_entrenamiento': metricas_ml.get('fecha_entrenamiento', ''),
                'sugerencias': sugerencias,
                'feature_importance': feature_importance
            }
            
            # Predicción de ejemplo (última cotización pendiente)
            df_pendientes = df_cotizaciones[df_cotizaciones['aceptada'].isna()]
            if not df_pendientes.empty:
                ultima = df_pendientes.iloc[-1]
                features_ejemplo = {
                    'costo_total': ultima['costo_total'],
                    'costo_mano_obra': ultima['costo_mano_obra'],
                    'costo_total_piezas': ultima['costo_total_piezas'],
                    'total_piezas': ultima['total_piezas'],
                    'piezas_necesarias': ultima['piezas_necesarias'],
                    'porcentaje_necesarias': ultima['porcentaje_necesarias'],
                    'piezas_sugeridas_tecnico': ultima['piezas_sugeridas_tecnico'],
                    'descontar_mano_obra': ultima['descontar_mano_obra'],
                    'gama': ultima['gama'],
                    'tipo_equipo': ultima['tipo_equipo'],
                }
                
                prob_rechazo, prob_aceptacion = predictor.predecir_probabilidad(features_ejemplo)
                
                graficos['prediccion_ml_ejemplo'] = convertir_figura_a_html(
                    visualizer.grafico_prediccion_ml(prob_aceptacion, prob_rechazo)
                )
                
                # CORRECCIÓN: Cambiar 'ejemplo_prediccion' a 'prediccion_ejemplo' para que coincida con el template
                ml_insights['prediccion_ejemplo'] = {
                    'cotizacion_id': ultima['cotizacion_id'],
                    'orden': ultima['numero_orden'],
                    'orden_cliente': ultima['orden_cliente'],  # AGREGADO: Campo orden_cliente del DataFrame
                    'costo': ultima['costo_total'],
                    'prob_aceptacion': prob_aceptacion * 100,
                    'prob_rechazo': prob_rechazo * 100
                }
                
                # ========================================
                # 5.1. MÓDULOS ML AVANZADOS (Sistema Experto)
                # ========================================
                
                print("\n🔬 Iniciando análisis con módulos ML avanzados...")
                
                try:
                    # Inicializar el Recomendador (orquestador que carga todo)
                    recomendador = RecomendadorAcciones(predictor_base=predictor)
                    
                    # Análisis completo de la cotización pendiente
                    analisis_completo = recomendador.analizar_cotizacion_completa(
                        cotizacion_features=features_ejemplo,
                        incluir_optimizacion_precio=True,
                        incluir_analisis_temporal=True
                    )
                    
                    # Actualizar insights avanzados
                    ml_insights_avanzados.update({
                        'disponible': True,
                        'predictor_motivos_disponible': recomendador.predictor_motivos is not None,
                        'optimizador_disponible': recomendador.optimizador is not None,
                        'recomendador_disponible': True,
                        'analisis_completo': analisis_completo,
                        
                        # Extraer datos clave para fácil acceso en template
                        'prob_aceptacion': analisis_completo['prediccion_base']['prob_aceptacion_pct'],
                        'clasificacion': analisis_completo['prediccion_base']['clasificacion'],
                        'total_recomendaciones': len(analisis_completo['recomendaciones']),
                        'recomendaciones_criticas': len([
                            r for r in analisis_completo['recomendaciones'] 
                            if r['nivel'] <= 2
                        ]),
                        'total_alertas': len(analisis_completo['alertas_criticas']),
                        'resumen_ejecutivo': analisis_completo['resumen_ejecutivo'],
                        
                        # Datos de cotización analizada (para mostrar en UI)
                        'cotizacion_analizada': {
                            'id': ultima['cotizacion_id'],
                            'orden': ultima['numero_orden'],
                            'orden_cliente': ultima['orden_cliente'],  # AGREGADO: Campo orden_cliente
                            'costo_actual': ultima['costo_total'],
                            'total_piezas': ultima['total_piezas'],
                            'gama': ultima['gama'],
                        }
                    })
                    
                    # Si hay predicción de motivo, agregarlo
                    if analisis_completo['prediccion_motivo']:
                        # Convertir probabilidad de decimal a porcentaje (0.255 -> 25.5)
                        prob_numerica = analisis_completo['prediccion_motivo']['probabilidad'] * 100
                        
                        ml_insights_avanzados['motivo_predicho'] = {
                            'motivo': analisis_completo['prediccion_motivo']['motivo_principal'],
                            'motivo_nombre': analisis_completo['prediccion_motivo']['motivo_nombre'],
                            'probabilidad': prob_numerica,  # Valor numérico para el progress bar
                            'probabilidad_texto': analisis_completo['prediccion_motivo']['probabilidad_pct'],  # Texto formateado
                            'confianza': analisis_completo['prediccion_motivo']['confianza'],
                            'confianza_icono': analisis_completo['prediccion_motivo']['confianza_icono'],
                            'descripcion': analisis_completo['prediccion_motivo']['motivo_descripcion'],
                            'acciones': analisis_completo['prediccion_motivo']['acciones_sugeridas']
                        }
                    
                    # Si hay optimización de precio, agregarlo
                    if analisis_completo['optimizacion_precio']:
                        opt = analisis_completo['optimizacion_precio']
                        ml_insights_avanzados['optimizacion'] = {
                            'costo_actual': opt['costo_actual'],
                            'costo_optimo': opt['escenario_optimo']['costo_final'],
                            'mejora_ingreso': opt['mejora_ingreso'],
                            'mejora_probabilidad': opt['mejora_probabilidad_pct'],
                            'escenario_optimo': opt['escenario_optimo'],
                            'escenario_conservador': opt['escenario_conservador'],
                            'escenario_agresivo': opt['escenario_agresivo'],
                            'total_escenarios': opt['total_escenarios_evaluados']
                        }
                    
                    # Si hay análisis temporal, agregarlo
                    if analisis_completo['analisis_temporal']:
                        temp = analisis_completo['analisis_temporal']
                        ml_insights_avanzados['temporal'] = {
                            'dia_hoy': temp['dia_hoy'],
                            'es_dia_optimo': temp['es_dia_optimo'],
                            'mejor_dia': temp['mejor_dia'],
                            'mejora_potencial': temp['mejora_potencial'],
                            'recomendacion': temp['recomendacion'],
                            'mensaje': temp['mensaje']
                        }
                    
                    print(f"✅ Análisis ML avanzado completado:")
                    print(f"   - {ml_insights_avanzados['total_recomendaciones']} recomendaciones generadas")
                    print(f"   - {ml_insights_avanzados['total_alertas']} alertas críticas")
                    print(f"   - Estado: {ml_insights_avanzados['resumen_ejecutivo']['estado_mensaje']}")
                    
                    # Mensaje informativo para el usuario
                    if ml_insights_avanzados['total_alertas'] > 0:
                        messages.warning(
                            request,
                            f"⚠️ {ml_insights_avanzados['total_alertas']} alertas críticas detectadas en ML avanzado"
                        )
                    
                    # ========================================
                    # 5.2. GENERAR VISUALIZACIONES ML AVANZADAS
                    # ========================================
                    
                    print("📊 Generando visualizaciones ML avanzadas...")
                    
                    try:
                        # Gráfico de escenarios de precio
                        if analisis_completo['optimizacion_precio']:
                            graficos['ml_escenarios_precio'] = convertir_figura_a_html(
                                visualizer.grafico_escenarios_precio(
                                    analisis_completo['optimizacion_precio']
                                )
                            )
                            print("   ✅ Gráfico de escenarios de precio generado")
                        
                        # Matriz riesgo-beneficio
                        graficos['ml_matriz_riesgo'] = convertir_figura_a_html(
                            visualizer.grafico_matriz_riesgo_beneficio(analisis_completo)
                        )
                        print("   ✅ Matriz riesgo-beneficio generada")
                        
                        # Timeline de probabilidad por día
                        if analisis_completo['analisis_temporal']:
                            graficos['ml_probabilidad_dia'] = convertir_figura_a_html(
                                visualizer.grafico_probabilidad_por_dia(
                                    analisis_completo['analisis_temporal']
                                )
                            )
                            print("   ✅ Timeline probabilidad por día generado")
                        
                        print("✅ Todas las visualizaciones ML avanzadas generadas exitosamente")
                        
                    except Exception as e_viz:
                        print(f"⚠️ Error generando visualizaciones ML avanzadas: {str(e_viz)}")
                        # No crítico, continuar
                    
                except Exception as e_avanzado:
                    print(f"⚠️ Error en módulos ML avanzados: {str(e_avanzado)}")
                    print(f"   Stack trace: {e_avanzado.__class__.__name__}")
                    # No fallar todo el dashboard, solo deshabilitar módulos avanzados
                    ml_insights_avanzados['error'] = str(e_avanzado)
        
        except Exception as e:
            print(f"⚠️ Error en Machine Learning: {str(e)}")
            messages.warning(request, f'Machine Learning no disponible: {str(e)}')
    
    # ========================================
    # 6. PREPARAR DATOS PARA FILTROS
    # ========================================
    
    # Listas para desplegables
    sucursales = Sucursal.objects.all().order_by('nombre')
    tecnicos = Empleado.objects.filter(
        ordenes_tecnico__isnull=False
    ).distinct().order_by('nombre_completo')
    
    # Opciones de gama
    gamas = [
        ('alta', 'Alta'),
        ('media', 'Media'),
        ('baja', 'Baja')
    ]
    
    # Opciones de período
    periodos = [
        ('D', 'Diario'),
        ('W', 'Semanal'),
        ('M', 'Mensual'),
        ('Q', 'Trimestral'),
        ('Y', 'Anual')
    ]
    
    # ========================================
    # 6.5. ANÁLISIS DE TEXTO (TEXT MINING)
    # ========================================
    
    print("\n" + "="*50)
    print("📝 ANÁLISIS DE COMENTARIOS DE RECHAZO (TEXT MINING)")
    print("="*50)
    
    analisis_texto = {}
    
    try:
        from .utils_cotizaciones import analizar_comentarios_rechazo
        
        print("🔍 Analizando comentarios de rechazo...")
        
        # Llamar función de análisis de texto
        analisis_texto = analizar_comentarios_rechazo(df_cotizaciones)
        
        if analisis_texto['tiene_datos']:
            print(f"✅ Análisis de texto completado:")
            print(f"   - {analisis_texto['total_comentarios']} comentarios analizados")
            print(f"   - {analisis_texto['total_palabras_unicas']} palabras únicas encontradas")
            print(f"   - {len(analisis_texto['palabras_clave'])} palabras clave extraídas")
            print(f"   - {len(analisis_texto['frases_comunes'])} frases comunes identificadas")
            print(f"   - {len(analisis_texto['insights'])} insights generados")
            
            # Generar visualizaciones de text mining
            try:
                print("📊 Generando visualizaciones de text mining...")
                
                # Gráfico de palabras más frecuentes
                graficos['texto_palabras_frecuentes'] = convertir_figura_a_html(
                    visualizer.grafico_palabras_frecuentes(analisis_texto['palabras_clave'])
                )
                print("   ✅ Gráfico de palabras frecuentes generado")
                
                # Gráfico de frases comunes
                if analisis_texto['frases_comunes']:
                    graficos['texto_frases_comunes'] = convertir_figura_a_html(
                        visualizer.grafico_frases_comunes(analisis_texto['frases_comunes'])
                    )
                    print("   ✅ Gráfico de frases comunes generado")
                
                # Gráfico de correlación palabras → resultado
                if analisis_texto['correlaciones']:
                    graficos['texto_correlaciones'] = convertir_figura_a_html(
                        visualizer.grafico_correlacion_palabras(analisis_texto['correlaciones'])
                    )
                    print("   ✅ Gráfico de correlaciones generado")
                
                # Nube de palabras tipo burbujas
                graficos['texto_nube_palabras'] = convertir_figura_a_html(
                    visualizer.grafico_nube_palabras_simple(analisis_texto['palabras_clave'])
                )
                print("   ✅ Nube de palabras generada")
                
                print("✅ Todas las visualizaciones de text mining generadas exitosamente")
                
            except Exception as e_viz_texto:
                print(f"⚠️ Error generando visualizaciones de text mining: {str(e_viz_texto)}")
                # No crítico, continuar
        
        else:
            print("ℹ️ No hay suficientes comentarios de rechazo para análisis de texto")
            analisis_texto['mensaje'] = "No hay comentarios de rechazo suficientes para análisis"
    
    except Exception as e_texto:
        print(f"⚠️ Error en análisis de texto: {str(e_texto)}")
        analisis_texto = {
            'tiene_datos': False,
            'error': str(e_texto),
            'mensaje': 'Error al analizar comentarios'
        }
    
    # ========================================
    # 6.6. ANÁLISIS DE DIAGNÓSTICOS TÉCNICOS POR TÉCNICO
    # ========================================
    
    print("\n" + "="*50)
    print("🔬 ANÁLISIS DE DIAGNÓSTICOS TÉCNICOS POR TÉCNICO")
    print("="*50)
    
    analisis_diagnosticos = {}
    
    try:
        from .utils_cotizaciones import analizar_diagnosticos_tecnicos
        
        print("🔍 Preparando datos de órdenes de servicio para análisis...")
        
        # Obtener órdenes de servicio con diagnóstico completado
        # NOTA: Usamos tecnico_asignado_actual (siempre presente) en lugar de tecnico_diagnostico (opcional)
        ordenes_con_diagnostico = OrdenServicio.objects.filter(
            fecha_ingreso__gte=fecha_inicio,
            fecha_ingreso__lte=fecha_fin
        ).select_related('tecnico_asignado_actual', 'sucursal', 'detalle_equipo')
        
        print(f"   📋 Total órdenes en el período: {ordenes_con_diagnostico.count()}")
        
        # Aplicar filtros si existen
        if sucursal_id:
            ordenes_con_diagnostico = ordenes_con_diagnostico.filter(sucursal_id=sucursal_id)
            print(f"   🏢 Filtrado por sucursal: {ordenes_con_diagnostico.count()} órdenes")
        
        if tecnico_id:
            # Filtrar por técnico asignado actual (no por tecnico_diagnostico)
            ordenes_con_diagnostico = ordenes_con_diagnostico.filter(tecnico_asignado_actual_id=tecnico_id)
            print(f"   👨‍🔧 Filtrado por técnico: {ordenes_con_diagnostico.count()} órdenes")
        
        # Convertir a DataFrame
        if ordenes_con_diagnostico.exists():
            ordenes_data = []
            ordenes_sin_diagnostico = 0
            ordenes_sin_tecnico = 0
            
            for orden in ordenes_con_diagnostico:
                # Verificar que tenga técnico asignado (tecnico_asignado_actual es obligatorio, siempre existe)
                if not orden.tecnico_asignado_actual:
                    ordenes_sin_tecnico += 1
                    continue
                
                # Verificar que tenga detalle de equipo con diagnóstico
                if not hasattr(orden, 'detalle_equipo'):
                    ordenes_sin_diagnostico += 1
                    continue
                
                diagnostico = orden.detalle_equipo.diagnostico_sic if orden.detalle_equipo.diagnostico_sic else ''
                falla = orden.detalle_equipo.falla_principal if orden.detalle_equipo.falla_principal else ''
                
                # Solo incluir si tiene diagnóstico no vacío
                if diagnostico.strip():
                    ordenes_data.append({
                        'numero_orden': orden.numero_orden_interno,
                        'tecnico_nombre': orden.tecnico_asignado_actual.nombre_completo,
                        'diagnostico_sic': diagnostico,
                        'falla_principal': falla,
                        'fecha_diagnostico': orden.fecha_diagnostico_sic,
                    })
                else:
                    ordenes_sin_diagnostico += 1
            
            print(f"   ✅ {len(ordenes_data)} órdenes con diagnóstico válido")
            if ordenes_sin_tecnico > 0:
                print(f"   ⚠️ {ordenes_sin_tecnico} órdenes sin técnico asignado (excluidas)")
            if ordenes_sin_diagnostico > 0:
                print(f"   ⚠️ {ordenes_sin_diagnostico} órdenes sin diagnóstico escrito (excluidas)")
            
            if not ordenes_data:
                print("❌ No hay órdenes con diagnóstico válido en el período seleccionado")
                analisis_diagnosticos = {
                    'tiene_datos': False,
                    'mensaje': 'No hay órdenes con diagnóstico técnico completado en el período'
                }
            else:
                df_ordenes = pd.DataFrame(ordenes_data)
                print(f"📊 DataFrame creado con {len(df_ordenes)} registros")
                
                # Mostrar técnicos únicos encontrados
                tecnicos_unicos = df_ordenes['tecnico_nombre'].unique()
                print(f"👥 Técnicos encontrados: {', '.join(tecnicos_unicos)}")
                
                # Llamar función de análisis de diagnósticos
                analisis_diagnosticos = analizar_diagnosticos_tecnicos(df_ordenes)
                
                if analisis_diagnosticos['tiene_datos']:
                    print(f"✅ Análisis de diagnósticos completado:")
                    print(f"   - {analisis_diagnosticos['total_diagnosticos']} diagnósticos analizados")
                    print(f"   - {analisis_diagnosticos['total_tecnicos']} técnicos evaluados")
                    print(f"   - Promedio palabras: {analisis_diagnosticos['promedios_globales']['promedio_palabras']:.1f}")
                    print(f"   - Promedio tecnicidad: {analisis_diagnosticos['promedios_globales']['promedio_tecnicidad']:.1f}%")
                    print(f"   - {len(analisis_diagnosticos['insights'])} insights generados")
                    
                    # Generar visualizaciones de diagnósticos
                    try:
                        print("📊 Generando visualizaciones de análisis de diagnósticos...")
                        
                        # Gráfico: Ranking por nivel de detalle
                        graficos['diagnosticos_ranking_detalle'] = convertir_figura_a_html(
                            visualizer.grafico_ranking_tecnicos_detalle(analisis_diagnosticos['analisis_por_tecnico'])
                        )
                        print("   ✅ Ranking de detalle generado")
                        
                        # Gráfico: Ranking por tecnicidad
                        graficos['diagnosticos_ranking_tecnicidad'] = convertir_figura_a_html(
                            visualizer.grafico_ranking_tecnicos_tecnicidad(analisis_diagnosticos['analisis_por_tecnico'])
                        )
                        print("   ✅ Ranking de tecnicidad generado")
                        
                        # Gráfico: Comparativa scatter (detalle vs tecnicidad)
                        graficos['diagnosticos_comparativa_scatter'] = convertir_figura_a_html(
                            visualizer.grafico_comparativa_tecnicos_scatter(analisis_diagnosticos['analisis_por_tecnico'])
                        )
                        print("   ✅ Comparativa scatter generada")
                        
                        # Gráfico: Palabras técnicas globales
                        if analisis_diagnosticos['palabras_tecnicas_globales']:
                            graficos['diagnosticos_palabras_tecnicas'] = convertir_figura_a_html(
                                visualizer.grafico_palabras_tecnicas_globales(analisis_diagnosticos['palabras_tecnicas_globales'])
                            )
                            print("   ✅ Palabras técnicas globales generadas")
                        
                        print("✅ Todas las visualizaciones de diagnósticos generadas exitosamente")
                        
                    except Exception as e_viz_diag:
                        print(f"⚠️ Error generando visualizaciones de diagnósticos: {str(e_viz_diag)}")
                        import traceback
                        print(f"   Detalle: {traceback.format_exc()}")
                        # No crítico, continuar
                
                else:
                    print(f"ℹ️ {analisis_diagnosticos.get('mensaje', 'No hay suficientes diagnósticos')}")
        
        else:
            print("ℹ️ No se encontraron órdenes con diagnóstico en el período seleccionado")
            analisis_diagnosticos = {
                'tiene_datos': False,
                'mensaje': 'No hay órdenes con diagnóstico en el período seleccionado'
            }
    
    except Exception as e_diagnosticos:
        print(f"⚠️ Error en análisis de diagnósticos: {str(e_diagnosticos)}")
        import traceback
        print(f"   Detalle: {traceback.format_exc()}")
        analisis_diagnosticos = {
            'tiene_datos': False,
            'error': str(e_diagnosticos),
            'mensaje': 'Error al analizar diagnósticos técnicos'
        }
    
    # ========================================
    # 7. PREPARAR CONTEXTO COMPLETO
    # ========================================
    
    context = {
        # KPIs
        'kpis': kpis,
        
        # Gráficos (diccionario completo)
        'graficos': graficos,
        
        # Machine Learning (básico)
        'ml_insights': ml_insights,
        
        # Machine Learning Avanzado (Sistema Experto) - NUEVO
        'ml_insights_avanzados': ml_insights_avanzados,
        
        # Análisis de Texto (Text Mining) - NUEVO
        'analisis_texto': analisis_texto,
        
        # Análisis de Diagnósticos Técnicos por Técnico - NUEVO
        'analisis_diagnosticos': analisis_diagnosticos,
        
        # Análisis de Aceptaciones y Ventas Mostrador - NUEVO
        'kpis_aceptaciones': kpis_aceptaciones,
        'analisis_vm': analisis_vm,
        'analisis_seguimiento': analisis_seguimiento,
        
        # Filtros activos (para mantener estado en el form)
        'filtros_activos': {
            'fecha_inicio': fecha_inicio.strftime('%Y-%m-%d'),
            'fecha_fin': fecha_fin.strftime('%Y-%m-%d'),
            'sucursal': sucursal_id,
            'tecnico': tecnico_id,
            'gama': gama,
            'periodo': periodo,
        },
        
        # Datos para desplegables
        'sucursales': sucursales,
        'tecnicos': tecnicos,
        'gamas': gamas,
        'periodos': periodos,
        
        # Metadatos
        'hay_datos': not df_cotizaciones.empty,
        'total_registros': len(df_cotizaciones),
        'fecha_generacion': datetime.now()
    }
    
    # ========================================
    # 8. RENDERIZAR TEMPLATE
    # ========================================
    
    return render(request, 'servicio_tecnico/dashboard_cotizaciones.html', context)


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
def exportar_dashboard_cotizaciones(request):
    """
    Exporta el dashboard de cotizaciones a Excel con múltiples hojas.

    Reutiliza los mismos filtros que el dashboard web.
    
    Returns:
        HttpResponse: Archivo Excel para descargar
    """
    
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils.dataframe import dataframe_to_rows
    from openpyxl.utils import get_column_letter
    from datetime import datetime
    import pandas as pd  # Necesario para pd.to_datetime()
    
    from .utils_cotizaciones import (
        obtener_dataframe_cotizaciones,
        calcular_kpis_generales,
        analizar_piezas_cotizadas,
        analizar_proveedores,
        calcular_metricas_por_tecnico,
        calcular_metricas_por_sucursal
    )
    
    # Obtener filtros (mismos que dashboard)
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    sucursal_id = request.GET.get('sucursal')
    tecnico_id = request.GET.get('tecnico')
    gama = request.GET.get('gama')
    
    # Obtener datos
    df_cotizaciones = obtener_dataframe_cotizaciones(
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        sucursal_id=sucursal_id,
        tecnico_id=tecnico_id,
        gama=gama
    )
    
    if df_cotizaciones.empty:
        messages.error(request, 'No hay datos para exportar con los filtros aplicados.')
        return redirect('servicio_tecnico:dashboard_cotizaciones')
    
    # Calcular KPIs y métricas
    kpis = calcular_kpis_generales(df_cotizaciones)
    df_metricas_tecnicos = calcular_metricas_por_tecnico(df_cotizaciones)
    df_metricas_sucursales = calcular_metricas_por_sucursal(df_cotizaciones)
    
    # Obtener IDs para análisis relacionados
    cotizacion_ids = df_cotizaciones['cotizacion_id'].tolist()
    df_piezas = analizar_piezas_cotizadas(cotizacion_ids)
    df_seguimientos = analizar_proveedores(cotizacion_ids)
    
    # ========================================
    # CREAR WORKBOOK
    # ========================================
    
    wb = Workbook()
    wb.remove(wb.active)  # Remover hoja por defecto
    
    # Estilos
    header_font = Font(bold=True, color='FFFFFF', size=12)
    header_fill = PatternFill(start_color='0d6efd', end_color='0d6efd', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center')
    
    title_font = Font(bold=True, size=16, color='FFFFFF')
    title_fill = PatternFill(start_color='212529', end_color='212529', fill_type='solid')
    title_alignment = Alignment(horizontal='center', vertical='center')
    
    # ========================================
    # HOJA 1: RESUMEN GENERAL (KPIs)
    # ========================================
    
    ws_resumen = wb.create_sheet("Resumen General")
    
    # Título
    ws_resumen.merge_cells('A1:D1')
    title_cell = ws_resumen['A1']
    title_cell.value = f"DASHBOARD DE COTIZACIONES - RESUMEN GENERAL"
    title_cell.font = title_font
    title_cell.fill = title_fill
    title_cell.alignment = title_alignment
    ws_resumen.row_dimensions[1].height = 30
    
    # Subtítulo con filtros
    ws_resumen.merge_cells('A2:D2')
    subtitle_cell = ws_resumen['A2']
    filtros_texto = f"Período: {fecha_inicio or 'Inicio'} - {fecha_fin or 'Hoy'}"
    if sucursal_id:
        filtros_texto += f" | Sucursal ID: {sucursal_id}"
    if tecnico_id:
        filtros_texto += f" | Técnico ID: {tecnico_id}"
    if gama:
        filtros_texto += f" | Gama: {gama}"
    subtitle_cell.value = filtros_texto
    subtitle_cell.alignment = Alignment(horizontal='center')
    
    # Fecha de generación
    ws_resumen.merge_cells('A3:D3')
    ws_resumen['A3'].value = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    ws_resumen['A3'].alignment = Alignment(horizontal='center')
    ws_resumen['A3'].font = Font(italic=True, size=10)
    
    # Espacio
    ws_resumen.row_dimensions[4].height = 5
    
    # Encabezados KPIs
    ws_resumen['A5'].value = 'Métrica'
    ws_resumen['B5'].value = 'Valor'
    ws_resumen['C5'].value = 'Porcentaje'
    ws_resumen['D5'].value = 'Observaciones'
    
    for col in ['A5', 'B5', 'C5', 'D5']:
        ws_resumen[col].font = header_font
        ws_resumen[col].fill = header_fill
        ws_resumen[col].alignment = header_alignment
    
    # Datos de KPIs
    kpis_data = [
        ['Total Cotizaciones', kpis['total_cotizaciones'], '', ''],
        ['Aceptadas', kpis['aceptadas'], f"{kpis['tasa_aceptacion']:.1f}%", 'Verde: > 60%'],
        ['Rechazadas', kpis['rechazadas'], f"{kpis['tasa_rechazo']:.1f}%", 'Rojo: > 30%'],
        ['Pendientes', kpis['pendientes'], f"{kpis['tasa_pendiente']:.1f}%", ''],
        ['Valor Total Cotizado', f"${kpis['valor_total_cotizado']:,.2f}", '', ''],
        ['Valor Aceptado', f"${kpis['valor_aceptado']:,.2f}", '', ''],
        ['Valor Rechazado', f"${kpis['valor_rechazado']:,.2f}", '', ''],
        ['Ticket Promedio', f"${kpis['ticket_promedio']:,.2f}", '', ''],
        ['Tiempo Respuesta Promedio', f"{kpis['tiempo_respuesta_promedio']:.1f} días", '', 'Ideal: < 3 días'],
        ['Piezas Promedio', f"{kpis['piezas_promedio']:.1f}", '', ''],
    ]
    
    row = 6
    for data in kpis_data:
        ws_resumen[f'A{row}'].value = data[0]
        ws_resumen[f'B{row}'].value = data[1]
        ws_resumen[f'C{row}'].value = data[2]
        ws_resumen[f'D{row}'].value = data[3]
        
        # Colorear según métrica
        if 'Aceptadas' in data[0] and kpis['tasa_aceptacion'] > 60:
            ws_resumen[f'B{row}'].fill = PatternFill(start_color='d4edda', end_color='d4edda', fill_type='solid')
        elif 'Rechazadas' in data[0] and kpis['tasa_rechazo'] > 30:
            ws_resumen[f'B{row}'].fill = PatternFill(start_color='f8d7da', end_color='f8d7da', fill_type='solid')
        
        row += 1
    
    # Ajustar anchos
    ws_resumen.column_dimensions['A'].width = 30
    ws_resumen.column_dimensions['B'].width = 20
    ws_resumen.column_dimensions['C'].width = 15
    ws_resumen.column_dimensions['D'].width = 25
    
    # ========================================
    # HOJA 2: COTIZACIONES DETALLE
    # ========================================
    
    ws_cotiz = wb.create_sheet("Cotizaciones Detalle")
    
    # Título
    ws_cotiz.merge_cells('A1:L1')
    title_cell = ws_cotiz['A1']
    title_cell.value = f"DETALLE DE COTIZACIONES ({len(df_cotizaciones)} registros)"
    title_cell.font = title_font
    title_cell.fill = title_fill
    title_cell.alignment = title_alignment
    
    # Seleccionar columnas relevantes
    columnas_export = [
        'numero_orden', 'orden_cliente', 'numero_serie', 'fecha_envio', 
        'sucursal', 'tecnico', 'gama', 'tipo_equipo', 'marca', 'modelo', 
        'costo_total', 'aceptada'
    ]
    
    df_export = df_cotizaciones[columnas_export].copy()
    
    # Renombrar columnas para el Excel
    df_export.columns = [
        'Número de Orden',
        'Orden Cliente', 
        'Número de Serie',
        'Fecha Envío',
        'Sucursal',
        'Técnico',
        'Gama',
        'Tipo Equipo',
        'Marca',
        'Modelo',
        'Costo Total',
        'Estado'
    ]
    
    df_export['Fecha Envío'] = pd.to_datetime(df_export['Fecha Envío']).dt.strftime('%d/%m/%Y')
    df_export['Costo Total'] = df_export['Costo Total'].apply(lambda x: f'${x:,.2f}')
    df_export['Estado'] = df_export['Estado'].map({
        True: '✅ Aceptada',
        False: '❌ Rechazada',
        None: '⏳ Pendiente'
    })
    
    # Escribir con encabezados formateados
    for r_idx, row in enumerate(dataframe_to_rows(df_export, index=False, header=True), 3):
        for c_idx, value in enumerate(row, 1):
            cell = ws_cotiz.cell(row=r_idx, column=c_idx, value=value)
            
            if r_idx == 3:  # Encabezados
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment
    
    # Auto-ajustar columnas
    for col_idx, column in enumerate(ws_cotiz.columns, 1):
        max_length = 0
        column_letter = get_column_letter(col_idx)
        for cell in column:
            try:
                if cell.value and len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws_cotiz.column_dimensions[column_letter].width = adjusted_width
    
    # ========================================
    # HOJA 3: MÉTRICAS POR TÉCNICO
    # ========================================
    
    if not df_metricas_tecnicos.empty:
        ws_tecnicos = wb.create_sheet("Ranking Técnicos")
        
        ws_tecnicos.merge_cells('A1:F1')
        title_cell = ws_tecnicos['A1']
        title_cell.value = f"RANKING DE TÉCNICOS"
        title_cell.font = title_font
        title_cell.fill = title_fill
        title_cell.alignment = title_alignment
        
        for r_idx, row in enumerate(dataframe_to_rows(df_metricas_tecnicos, index=False, header=True), 3):
            for c_idx, value in enumerate(row, 1):
                cell = ws_tecnicos.cell(row=r_idx, column=c_idx, value=value)
                if r_idx == 3:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = header_alignment
    
    # ========================================
    # HOJA 4: MÉTRICAS POR SUCURSAL
    # ========================================
    
    if not df_metricas_sucursales.empty:
        ws_sucursales = wb.create_sheet("Ranking Sucursales")
        
        ws_sucursales.merge_cells('A1:F1')
        title_cell = ws_sucursales['A1']
        title_cell.value = f"RANKING DE SUCURSALES"
        title_cell.font = title_font
        title_cell.fill = title_fill
        title_cell.alignment = title_alignment
        
        for r_idx, row in enumerate(dataframe_to_rows(df_metricas_sucursales, index=False, header=True), 3):
            for c_idx, value in enumerate(row, 1):
                cell = ws_sucursales.cell(row=r_idx, column=c_idx, value=value)
                if r_idx == 3:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = header_alignment
    
    # ========================================
    # GENERAR Y RETORNAR ARCHIVO
    # ========================================
    
    # Nombre del archivo
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nombre_archivo = f'Dashboard_Cotizaciones_{timestamp}.xlsx'
    
    # Preparar respuesta HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    
    # Guardar workbook
    wb.save(response)
    
    return response


# ============================================================================
# EXPORTAR ANÁLISIS DETALLADO DE RECHAZOS A EXCEL (7 HOJAS)
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
def exportar_analisis_rechazos(request):
    """
    Exporta un análisis exhaustivo de cotizaciones rechazadas a Excel con 7 hojas.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Este Excel es el "detalle del detalle" de los rechazos. Mientras que el Excel
    general del dashboard muestra un resumen de todo, este se enfoca SOLO en rechazos
    y profundiza en cada ángulo: por motivo, por marca/modelo, tiempos, piezas, etc.
    
    Hojas:
        1. Resumen Rechazos - KPIs específicos de rechazos
        2. Detalle Rechazos - Cada cotización rechazada con todos los campos
        3. Rechazos por Motivo - Tabla pivote por motivo de rechazo
        4. Rechazos por Marca/Modelo - Análisis cruzado marca-modelo
        5. Tiempo de Respuesta - Análisis temporal de rechazos
        6. No Hay Partes - Apartado especial para rechazos por falta de partes
        7. Piezas Rechazadas - Detalle a nivel pieza individual
        8. Costo Alto - Detalle de rechazos por costo elevado con piezas desglosadas
        9. Servicios 3+ Piezas - Servicios con múltiples piezas cotizadas
    
    Returns:
        HttpResponse: Archivo Excel (.xlsx) para descargar
    """
    
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils.dataframe import dataframe_to_rows
    from openpyxl.utils import get_column_letter
    from datetime import datetime
    import pandas as pd
    
    from .utils_cotizaciones import (
        obtener_dataframe_cotizaciones,
        calcular_kpis_generales,
        analizar_piezas_cotizadas,
    )
    from config.constants import MOTIVO_RECHAZO_COTIZACION
    
    # ========================================
    # OBTENER DATOS CON MISMOS FILTROS QUE EL DASHBOARD
    # ========================================
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    sucursal_id = request.GET.get('sucursal')
    tecnico_id = request.GET.get('tecnico')
    gama = request.GET.get('gama')
    
    df_cotizaciones = obtener_dataframe_cotizaciones(
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        sucursal_id=sucursal_id,
        tecnico_id=tecnico_id,
        gama=gama
    )
    
    if df_cotizaciones.empty:
        messages.error(request, 'No hay datos para exportar con los filtros aplicados.')
        return redirect('servicio_tecnico:dashboard_cotizaciones')
    
    # Filtrar solo rechazadas
    df_rechazos = df_cotizaciones[df_cotizaciones['aceptada'] == False].copy()
    
    if df_rechazos.empty:
        messages.warning(request, 'No hay cotizaciones rechazadas en el período seleccionado.')
        return redirect('servicio_tecnico:dashboard_cotizaciones')
    
    # Diccionario de labels legibles para motivos de rechazo
    labels_motivos = dict(MOTIVO_RECHAZO_COTIZACION)
    
    # Obtener piezas de cotizaciones rechazadas
    cotizacion_ids_rechazos = df_rechazos['cotizacion_id'].tolist()
    df_piezas = analizar_piezas_cotizadas(cotizacion_ids_rechazos)
    
    # Obtener piezas con proveedor directamente del modelo
    # (analizar_piezas_cotizadas no incluye proveedor)
    from .models import PiezaCotizada
    piezas_con_proveedor = PiezaCotizada.objects.filter(
        cotizacion_id__in=cotizacion_ids_rechazos
    ).select_related(
        'componente',
        'cotizacion',
        'cotizacion__orden',
        'cotizacion__orden__detalle_equipo'
    ).values(
        'id', 'cotizacion_id', 'componente__nombre',
        'descripcion_adicional', 'sugerida_por_tecnico', 'es_necesaria',
        'cantidad', 'costo_unitario', 'proveedor',
        'aceptada_por_cliente', 'motivo_rechazo_pieza',
        'cotizacion__orden__detalle_equipo__marca',
        'cotizacion__orden__detalle_equipo__modelo',
    )
    df_piezas_proveedor = pd.DataFrame(list(piezas_con_proveedor))
    
    # KPIs generales para comparativa
    kpis = calcular_kpis_generales(df_cotizaciones)
    
    # ========================================
    # CREAR WORKBOOK
    # ========================================
    wb = Workbook()
    wb.remove(wb.active)
    
    # Estilos reutilizables
    header_font = Font(bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill(start_color='c0392c', end_color='c0392c', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    
    title_font = Font(bold=True, size=14, color='FFFFFF')
    title_fill = PatternFill(start_color='212529', end_color='212529', fill_type='solid')
    title_align = Alignment(horizontal='center', vertical='center')
    
    subtitle_font = Font(italic=True, size=10, color='666666')
    
    kpi_label_font = Font(bold=True, size=11)
    kpi_value_font = Font(bold=True, size=12, color='c0392c')
    
    green_fill = PatternFill(start_color='d4edda', end_color='d4edda', fill_type='solid')
    red_fill = PatternFill(start_color='f8d7da', end_color='f8d7da', fill_type='solid')
    yellow_fill = PatternFill(start_color='fff3cd', end_color='fff3cd', fill_type='solid')
    blue_fill = PatternFill(start_color='d1ecf1', end_color='d1ecf1', fill_type='solid')
    orange_fill = PatternFill(start_color='ffeaa7', end_color='ffeaa7', fill_type='solid')
    
    section_font = Font(bold=True, size=12, color='2c3e50')
    section_fill = PatternFill(start_color='ecf0f1', end_color='ecf0f1', fill_type='solid')
    
    # Texto de filtros para subtítulos
    filtros_texto = f"Período: {fecha_inicio or 'Inicio'} - {fecha_fin or 'Hoy'}"
    if sucursal_id:
        filtros_texto += f" | Sucursal ID: {sucursal_id}"
    if tecnico_id:
        filtros_texto += f" | Técnico ID: {tecnico_id}"
    if gama:
        filtros_texto += f" | Gama: {gama}"
    
    # Función auxiliar para escribir título y subtítulo en cada hoja
    def escribir_encabezado_hoja(ws, titulo, num_cols=8):
        ultimo_col = get_column_letter(num_cols)
        ws.merge_cells(f'A1:{ultimo_col}1')
        cell = ws['A1']
        cell.value = titulo
        cell.font = title_font
        cell.fill = title_fill
        cell.alignment = title_align
        ws.row_dimensions[1].height = 30
        
        ws.merge_cells(f'A2:{ultimo_col}2')
        ws['A2'].value = f"{filtros_texto} | Generado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        ws['A2'].font = subtitle_font
        ws['A2'].alignment = Alignment(horizontal='center')
    
    # Función auxiliar para escribir encabezados de tabla
    def escribir_headers(ws, headers, fila, fill=None):
        fill_usar = fill or header_fill
        for col_idx, header_text in enumerate(headers, 1):
            cell = ws.cell(row=fila, column=col_idx, value=header_text)
            cell.font = header_font
            cell.fill = fill_usar
            cell.alignment = header_align
    
    # Función auxiliar para auto-ajustar columnas
    def autoajustar_columnas(ws, min_width=10, max_width=45):
        for col_idx, column_cells in enumerate(ws.columns, 1):
            max_length = min_width
            col_letter = get_column_letter(col_idx)
            for cell in column_cells:
                try:
                    if cell.value and len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            ws.column_dimensions[col_letter].width = min(max_length + 2, max_width)
    
    # ========================================
    # HOJA 1: RESUMEN RECHAZOS (KPIs)
    # ========================================
    ws1 = wb.create_sheet("Resumen Rechazos")
    escribir_encabezado_hoja(ws1, "ANÁLISIS DETALLADO DE RECHAZOS - RESUMEN", 4)
    
    # Sección 1: KPIs principales
    ws1.merge_cells('A4:D4')
    ws1['A4'].value = "INDICADORES PRINCIPALES"
    ws1['A4'].font = section_font
    ws1['A4'].fill = section_fill
    
    escribir_headers(ws1, ['Métrica', 'Valor', 'Porcentaje', 'Observaciones'], 5)
    
    total_rechazos = len(df_rechazos)
    total_cotizaciones = len(df_cotizaciones)
    pct_rechazos = (total_rechazos / total_cotizaciones * 100) if total_cotizaciones > 0 else 0
    valor_perdido = df_rechazos['costo_total'].sum()
    valor_total = df_cotizaciones['costo_total'].sum()
    pct_valor_perdido = (valor_perdido / valor_total * 100) if valor_total > 0 else 0
    ticket_prom_rechazo = df_rechazos['costo_total'].mean()
    ticket_prom_aceptado = df_cotizaciones[df_cotizaciones['aceptada'] == True]['costo_total'].mean() if len(df_cotizaciones[df_cotizaciones['aceptada'] == True]) > 0 else 0
    
    # Tiempo respuesta rechazos vs aceptados
    df_rechazos_con_resp = df_rechazos[df_rechazos['fecha_respuesta'].notna()]
    tiempo_resp_rechazos = df_rechazos_con_resp['dias_sin_respuesta'].mean() if len(df_rechazos_con_resp) > 0 else 0
    
    df_aceptados = df_cotizaciones[df_cotizaciones['aceptada'] == True]
    df_aceptados_con_resp = df_aceptados[df_aceptados['fecha_respuesta'].notna()]
    tiempo_resp_aceptados = df_aceptados_con_resp['dias_sin_respuesta'].mean() if len(df_aceptados_con_resp) > 0 else 0
    
    kpis_data = [
        ['Total Cotizaciones (todas)', total_cotizaciones, '', 'Base de referencia'],
        ['Total Rechazadas', total_rechazos, f'{pct_rechazos:.1f}%', 'Objetivo: < 30%'],
        ['Total Aceptadas', kpis.get('aceptadas', 0), f"{kpis.get('tasa_aceptacion', 0):.1f}%", ''],
        ['Valor Total Perdido', f'${valor_perdido:,.2f}', f'{pct_valor_perdido:.1f}% del total', 'Oportunidad de recuperación'],
        ['Ticket Promedio (Rechazos)', f'${ticket_prom_rechazo:,.2f}', '', ''],
        ['Ticket Promedio (Aceptados)', f'${ticket_prom_aceptado:,.2f}', '', 'Comparar con rechazos'],
        ['Tiempo Resp. Prom (Rechazos)', f'{tiempo_resp_rechazos:.1f} días', '', ''],
        ['Tiempo Resp. Prom (Aceptados)', f'{tiempo_resp_aceptados:.1f} días', '', 'Comparar con rechazos'],
        ['Piezas Prom. por Rechazo', f'{df_rechazos["total_piezas"].mean():.1f}', '', ''],
    ]
    
    for i, data in enumerate(kpis_data):
        row = 6 + i
        ws1.cell(row=row, column=1, value=data[0]).font = kpi_label_font
        ws1.cell(row=row, column=2, value=data[1]).font = kpi_value_font
        ws1.cell(row=row, column=3, value=data[2])
        ws1.cell(row=row, column=4, value=data[3])
    
    # Sección 2: Top Motivos
    fila_motivos = 6 + len(kpis_data) + 2
    ws1.merge_cells(f'A{fila_motivos}:D{fila_motivos}')
    ws1[f'A{fila_motivos}'].value = "TOP MOTIVOS DE RECHAZO"
    ws1[f'A{fila_motivos}'].font = section_font
    ws1[f'A{fila_motivos}'].fill = section_fill
    
    escribir_headers(ws1, ['Motivo', 'Cantidad', '% de Rechazos', 'Valor Perdido'], fila_motivos + 1)
    
    motivos_conteo = df_rechazos['motivo_rechazo'].value_counts()
    fila = fila_motivos + 2
    for motivo, conteo in motivos_conteo.items():
        label = labels_motivos.get(motivo, str(motivo).replace('_', ' ').title()) if motivo else 'Sin motivo especificado'
        pct = (conteo / total_rechazos * 100) if total_rechazos > 0 else 0
        valor = df_rechazos[df_rechazos['motivo_rechazo'] == motivo]['costo_total'].sum()
        
        ws1.cell(row=fila, column=1, value=label)
        ws1.cell(row=fila, column=2, value=conteo)
        ws1.cell(row=fila, column=3, value=f'{pct:.1f}%')
        ws1.cell(row=fila, column=4, value=f'${valor:,.2f}')
        
        # Colorear según criticidad
        if pct >= 25:
            ws1.cell(row=fila, column=1).fill = red_fill
        elif pct >= 15:
            ws1.cell(row=fila, column=1).fill = yellow_fill
        
        fila += 1
    
    # Sección 3: Top Marcas rechazadas
    fila_marcas = fila + 2
    ws1.merge_cells(f'A{fila_marcas}:D{fila_marcas}')
    ws1[f'A{fila_marcas}'].value = "TOP MARCAS CON MÁS RECHAZOS"
    ws1[f'A{fila_marcas}'].font = section_font
    ws1[f'A{fila_marcas}'].fill = section_fill
    
    escribir_headers(ws1, ['Marca', 'Rechazos', '% del Total', 'Tasa de Rechazo'], fila_marcas + 1)
    
    marcas_rechazos = df_rechazos['marca'].value_counts().head(10)
    fila = fila_marcas + 2
    for marca, conteo in marcas_rechazos.items():
        total_marca = len(df_cotizaciones[df_cotizaciones['marca'] == marca])
        tasa = (conteo / total_marca * 100) if total_marca > 0 else 0
        pct = (conteo / total_rechazos * 100) if total_rechazos > 0 else 0
        
        ws1.cell(row=fila, column=1, value=marca or 'Sin marca')
        ws1.cell(row=fila, column=2, value=conteo)
        ws1.cell(row=fila, column=3, value=f'{pct:.1f}%')
        ws1.cell(row=fila, column=4, value=f'{tasa:.1f}%')
        
        if tasa >= 50:
            ws1.cell(row=fila, column=4).fill = red_fill
        fila += 1
    
    ws1.column_dimensions['A'].width = 40
    ws1.column_dimensions['B'].width = 22
    ws1.column_dimensions['C'].width = 18
    ws1.column_dimensions['D'].width = 30
    
    # ========================================
    # HOJA 2: DETALLE RECHAZOS (cada cotización rechazada)
    # ========================================
    ws2 = wb.create_sheet("Detalle Rechazos")
    escribir_encabezado_hoja(ws2, f"DETALLE DE COTIZACIONES RECHAZADAS ({total_rechazos} registros)", 16)
    
    headers_detalle = [
        'Orden Cliente', 'Número Serie',
        'Marca', 'Modelo', 'Tipo Equipo', 'Gama',
        'Sucursal', 'Técnico', 'Responsable',
        'Motivo Rechazo', 'Detalle Rechazo',
        'Fecha Envío', 'Fecha Respuesta', 'Días Respuesta',
        'Costo Total', 'Costo Piezas', 'Costo Mano Obra',
        'Total Piezas', 'Piezas Necesarias'
    ]
    escribir_headers(ws2, headers_detalle, 4)
    
    fila = 5
    for _, rec in df_rechazos.iterrows():
        motivo_label = labels_motivos.get(rec.get('motivo_rechazo', ''), str(rec.get('motivo_rechazo', '')).replace('_', ' ').title()) if rec.get('motivo_rechazo') else 'Sin motivo'
        
        fecha_envio_str = ''
        if pd.notna(rec.get('fecha_envio')):
            try:
                fecha_envio_str = pd.to_datetime(rec['fecha_envio']).strftime('%d/%m/%Y')
            except:
                fecha_envio_str = str(rec['fecha_envio'])
        
        fecha_resp_str = ''
        if pd.notna(rec.get('fecha_respuesta')):
            try:
                fecha_resp_str = pd.to_datetime(rec['fecha_respuesta']).strftime('%d/%m/%Y')
            except:
                fecha_resp_str = str(rec['fecha_respuesta'])
        
        valores = [
            rec.get('orden_cliente', ''),
            rec.get('numero_serie', ''),
            rec.get('marca', ''),
            rec.get('modelo', ''),
            rec.get('tipo_equipo', ''),
            rec.get('gama', ''),
            rec.get('sucursal', ''),
            rec.get('tecnico', ''),
            rec.get('responsable', ''),
            motivo_label,
            rec.get('detalle_rechazo', ''),
            fecha_envio_str,
            fecha_resp_str,
            rec.get('dias_sin_respuesta', ''),
            f"${rec.get('costo_total', 0):,.2f}",
            f"${rec.get('costo_total_piezas', 0):,.2f}",
            f"${rec.get('costo_mano_obra', 0):,.2f}",
            rec.get('total_piezas', 0),
            rec.get('piezas_necesarias', 0),
        ]
        
        for col_idx, val in enumerate(valores, 1):
            ws2.cell(row=fila, column=col_idx, value=val)
        
        fila += 1
    
    autoajustar_columnas(ws2, max_width=40)
    # Limitar ancho de la columna de detalle de rechazo
    ws2.column_dimensions['L'].width = 50
    
    # ========================================
    # HOJA 3: RECHAZOS POR MOTIVO (tabla pivote)
    # ========================================
    ws3 = wb.create_sheet("Rechazos por Motivo")
    escribir_encabezado_hoja(ws3, "ANÁLISIS DETALLADO POR MOTIVO DE RECHAZO", 10)
    
    headers_motivo = [
        'Motivo de Rechazo', 'Cantidad', '% de Rechazos',
        'Costo Promedio', 'Costo Mediana', 'Costo Mínimo', 'Costo Máximo',
        'Tiempo Resp. Prom (días)', 'Top 3 Marcas', 'Top 3 Sucursales'
    ]
    escribir_headers(ws3, headers_motivo, 4)
    
    fila = 5
    for motivo, conteo in motivos_conteo.items():
        df_motivo = df_rechazos[df_rechazos['motivo_rechazo'] == motivo]
        label = labels_motivos.get(motivo, str(motivo).replace('_', ' ').title()) if motivo else 'Sin motivo'
        pct = (conteo / total_rechazos * 100) if total_rechazos > 0 else 0
        
        costo_promedio = df_motivo['costo_total'].mean()
        costo_mediana = df_motivo['costo_total'].median()
        costo_min = df_motivo['costo_total'].min()
        costo_max = df_motivo['costo_total'].max()
        
        # Tiempo de respuesta promedio para este motivo
        df_motivo_resp = df_motivo[df_motivo['fecha_respuesta'].notna()]
        tiempo_resp = df_motivo_resp['dias_sin_respuesta'].mean() if len(df_motivo_resp) > 0 else 0
        
        # Top 3 marcas
        top_marcas = df_motivo['marca'].value_counts().head(3)
        marcas_str = ', '.join([f"{m} ({c})" for m, c in top_marcas.items()]) if len(top_marcas) > 0 else 'N/A'
        
        # Top 3 sucursales
        top_sucursales = df_motivo['sucursal'].value_counts().head(3)
        sucursales_str = ', '.join([f"{s} ({c})" for s, c in top_sucursales.items()]) if len(top_sucursales) > 0 else 'N/A'
        
        valores = [
            label, conteo, f'{pct:.1f}%',
            f'${costo_promedio:,.2f}', f'${costo_mediana:,.2f}',
            f'${costo_min:,.2f}', f'${costo_max:,.2f}',
            f'{tiempo_resp:.1f}',
            marcas_str, sucursales_str
        ]
        
        for col_idx, val in enumerate(valores, 1):
            ws3.cell(row=fila, column=col_idx, value=val)
        
        # Colorear filas críticas
        if pct >= 25:
            for col_idx in range(1, len(valores) + 1):
                ws3.cell(row=fila, column=col_idx).fill = red_fill
        elif pct >= 15:
            for col_idx in range(1, len(valores) + 1):
                ws3.cell(row=fila, column=col_idx).fill = yellow_fill
        
        fila += 1
    
    autoajustar_columnas(ws3, max_width=50)
    
    # ========================================
    # HOJA 4: RECHAZOS POR MARCA/MODELO
    # ========================================
    ws4 = wb.create_sheet("Rechazos Marca-Modelo")
    escribir_encabezado_hoja(ws4, "ANÁLISIS DE RECHAZOS POR MARCA Y MODELO", 8)
    
    headers_marca = [
        'Marca', 'Modelo', 'Total Cotizaciones', 'Rechazadas',
        'Tasa de Rechazo', 'Motivo Más Común', 'Costo Prom. Rechazado',
        'Valor Total Perdido'
    ]
    escribir_headers(ws4, headers_marca, 4)
    
    # Agrupar por marca-modelo
    marcas_modelos = df_rechazos.groupby(['marca', 'modelo']).agg(
        rechazadas=('cotizacion_id', 'count'),
        costo_promedio=('costo_total', 'mean'),
        valor_total=('costo_total', 'sum'),
    ).reset_index()
    
    # Para cada marca-modelo, calcular total cotizaciones y motivo más común
    fila = 5
    for _, row_mm in marcas_modelos.sort_values('rechazadas', ascending=False).iterrows():
        marca = row_mm['marca'] or 'Sin marca'
        modelo = row_mm['modelo'] or 'Sin modelo'
        rechazadas = row_mm['rechazadas']
        
        # Total cotizaciones (aceptadas + rechazadas + pendientes) para este marca-modelo
        total_marca_modelo = len(df_cotizaciones[
            (df_cotizaciones['marca'] == row_mm['marca']) & 
            (df_cotizaciones['modelo'] == row_mm['modelo'])
        ])
        tasa_rechazo = (rechazadas / total_marca_modelo * 100) if total_marca_modelo > 0 else 0
        
        # Motivo más común para este marca-modelo
        df_mm = df_rechazos[
            (df_rechazos['marca'] == row_mm['marca']) & 
            (df_rechazos['modelo'] == row_mm['modelo'])
        ]
        motivo_comun = df_mm['motivo_rechazo'].mode()
        motivo_label = labels_motivos.get(motivo_comun.iloc[0], str(motivo_comun.iloc[0]).replace('_', ' ').title()) if len(motivo_comun) > 0 and motivo_comun.iloc[0] else 'N/A'
        
        valores = [
            marca, modelo, total_marca_modelo, rechazadas,
            f'{tasa_rechazo:.1f}%', motivo_label,
            f'${row_mm["costo_promedio"]:,.2f}',
            f'${row_mm["valor_total"]:,.2f}'
        ]
        
        for col_idx, val in enumerate(valores, 1):
            ws4.cell(row=fila, column=col_idx, value=val)
        
        if tasa_rechazo >= 70:
            for col_idx in range(1, len(valores) + 1):
                ws4.cell(row=fila, column=col_idx).fill = red_fill
        elif tasa_rechazo >= 50:
            for col_idx in range(1, len(valores) + 1):
                ws4.cell(row=fila, column=col_idx).fill = yellow_fill
        
        fila += 1
    
    autoajustar_columnas(ws4)
    
    # ========================================
    # HOJA 5: TIEMPO DE RESPUESTA
    # ========================================
    ws5 = wb.create_sheet("Tiempo de Respuesta")
    escribir_encabezado_hoja(ws5, "ANÁLISIS DE TIEMPOS DE RESPUESTA EN RECHAZOS", 6)
    
    # Sección 1: Rangos de tiempo vs tasa de rechazo
    ws5.merge_cells('A4:F4')
    ws5[f'A4'].value = "RANGOS DE TIEMPO DE RESPUESTA vs RESULTADO"
    ws5[f'A4'].font = section_font
    ws5[f'A4'].fill = section_fill
    
    headers_tiempo = [
        'Rango (días)', 'Total Cotizaciones', 'Aceptadas', 'Rechazadas',
        'Tasa Aceptación', 'Tasa Rechazo'
    ]
    escribir_headers(ws5, headers_tiempo, 5)
    
    # Solo cotizaciones con respuesta
    df_con_respuesta = df_cotizaciones[df_cotizaciones['fecha_respuesta'].notna()].copy()
    
    rangos = [
        ('0-2 días', 0, 2),
        ('3-5 días', 3, 5),
        ('6-10 días', 6, 10),
        ('11-15 días', 11, 15),
        ('16-30 días', 16, 30),
        ('31+ días', 31, 9999),
    ]
    
    fila = 6
    for label_rango, min_dias, max_dias in rangos:
        df_rango = df_con_respuesta[
            (df_con_respuesta['dias_sin_respuesta'] >= min_dias) & 
            (df_con_respuesta['dias_sin_respuesta'] <= max_dias)
        ]
        total_rango = len(df_rango)
        aceptadas_rango = len(df_rango[df_rango['aceptada'] == True])
        rechazadas_rango = len(df_rango[df_rango['aceptada'] == False])
        tasa_acep = (aceptadas_rango / total_rango * 100) if total_rango > 0 else 0
        tasa_rech = (rechazadas_rango / total_rango * 100) if total_rango > 0 else 0
        
        ws5.cell(row=fila, column=1, value=label_rango)
        ws5.cell(row=fila, column=2, value=total_rango)
        ws5.cell(row=fila, column=3, value=aceptadas_rango)
        ws5.cell(row=fila, column=4, value=rechazadas_rango)
        ws5.cell(row=fila, column=5, value=f'{tasa_acep:.1f}%')
        ws5.cell(row=fila, column=6, value=f'{tasa_rech:.1f}%')
        
        if tasa_rech >= 60:
            ws5.cell(row=fila, column=6).fill = red_fill
        elif tasa_rech >= 40:
            ws5.cell(row=fila, column=6).fill = yellow_fill
        else:
            ws5.cell(row=fila, column=6).fill = green_fill
        
        fila += 1
    
    # Sección 2: Tiempo promedio por motivo
    fila += 2
    ws5.merge_cells(f'A{fila}:F{fila}')
    ws5[f'A{fila}'].value = "TIEMPO PROMEDIO DE RESPUESTA POR MOTIVO DE RECHAZO"
    ws5[f'A{fila}'].font = section_font
    ws5[f'A{fila}'].fill = section_fill
    fila += 1
    
    escribir_headers(ws5, ['Motivo', 'Casos con Respuesta', 'Tiempo Promedio (días)', 'Tiempo Mediana (días)', 'Tiempo Mínimo', 'Tiempo Máximo'], fila)
    fila += 1
    
    for motivo, _ in motivos_conteo.items():
        df_motivo_resp = df_rechazos[
            (df_rechazos['motivo_rechazo'] == motivo) & 
            (df_rechazos['fecha_respuesta'].notna())
        ]
        if len(df_motivo_resp) == 0:
            continue
        
        label = labels_motivos.get(motivo, str(motivo).replace('_', ' ').title()) if motivo else 'Sin motivo'
        
        ws5.cell(row=fila, column=1, value=label)
        ws5.cell(row=fila, column=2, value=len(df_motivo_resp))
        ws5.cell(row=fila, column=3, value=f'{df_motivo_resp["dias_sin_respuesta"].mean():.1f}')
        ws5.cell(row=fila, column=4, value=f'{df_motivo_resp["dias_sin_respuesta"].median():.1f}')
        ws5.cell(row=fila, column=5, value=f'{df_motivo_resp["dias_sin_respuesta"].min():.0f}')
        ws5.cell(row=fila, column=6, value=f'{df_motivo_resp["dias_sin_respuesta"].max():.0f}')
        fila += 1
    
    # Sección 3: Tiempo por sucursal (solo rechazos)
    fila += 2
    ws5.merge_cells(f'A{fila}:F{fila}')
    ws5[f'A{fila}'].value = "TIEMPO DE RESPUESTA EN RECHAZOS POR SUCURSAL"
    ws5[f'A{fila}'].font = section_font
    ws5[f'A{fila}'].fill = section_fill
    fila += 1
    
    escribir_headers(ws5, ['Sucursal', 'Total Rechazos', 'Con Respuesta', 'Tiempo Promedio (días)', 'Sin Respuesta', '% Sin Respuesta'], fila)
    fila += 1
    
    for sucursal in df_rechazos['sucursal'].unique():
        df_suc = df_rechazos[df_rechazos['sucursal'] == sucursal]
        df_suc_resp = df_suc[df_suc['fecha_respuesta'].notna()]
        sin_resp = len(df_suc) - len(df_suc_resp)
        pct_sin = (sin_resp / len(df_suc) * 100) if len(df_suc) > 0 else 0
        tiempo_prom = df_suc_resp['dias_sin_respuesta'].mean() if len(df_suc_resp) > 0 else 0
        
        ws5.cell(row=fila, column=1, value=sucursal)
        ws5.cell(row=fila, column=2, value=len(df_suc))
        ws5.cell(row=fila, column=3, value=len(df_suc_resp))
        ws5.cell(row=fila, column=4, value=f'{tiempo_prom:.1f}')
        ws5.cell(row=fila, column=5, value=sin_resp)
        ws5.cell(row=fila, column=6, value=f'{pct_sin:.1f}%')
        fila += 1
    
    # Sección 4: Tiempo por técnico (solo rechazos)
    fila += 2
    ws5.merge_cells(f'A{fila}:F{fila}')
    ws5[f'A{fila}'].value = "TIEMPO DE RESPUESTA EN RECHAZOS POR TÉCNICO"
    ws5[f'A{fila}'].font = section_font
    ws5[f'A{fila}'].fill = section_fill
    fila += 1
    
    escribir_headers(ws5, ['Técnico', 'Total Rechazos', 'Con Respuesta', 'Tiempo Promedio (días)', 'Sin Respuesta', '% Sin Respuesta'], fila)
    fila += 1
    
    for tecnico in df_rechazos['tecnico'].unique():
        df_tec = df_rechazos[df_rechazos['tecnico'] == tecnico]
        df_tec_resp = df_tec[df_tec['fecha_respuesta'].notna()]
        sin_resp = len(df_tec) - len(df_tec_resp)
        pct_sin = (sin_resp / len(df_tec) * 100) if len(df_tec) > 0 else 0
        tiempo_prom = df_tec_resp['dias_sin_respuesta'].mean() if len(df_tec_resp) > 0 else 0
        
        ws5.cell(row=fila, column=1, value=tecnico)
        ws5.cell(row=fila, column=2, value=len(df_tec))
        ws5.cell(row=fila, column=3, value=len(df_tec_resp))
        ws5.cell(row=fila, column=4, value=f'{tiempo_prom:.1f}')
        ws5.cell(row=fila, column=5, value=sin_resp)
        ws5.cell(row=fila, column=6, value=f'{pct_sin:.1f}%')
        fila += 1
    
    autoajustar_columnas(ws5)
    
    # ========================================
    # HOJA 6: NO HAY PARTES (Apartado especial)
    # ========================================
    ws6 = wb.create_sheet("No Hay Partes")
    no_hay_partes_fill = PatternFill(start_color='e74c3c', end_color='e74c3c', fill_type='solid')
    
    escribir_encabezado_hoja(ws6, "ANÁLISIS ESPECIAL: RECHAZOS POR FALTA DE PARTES EN EL MERCADO", 10)
    
    df_no_partes = df_rechazos[df_rechazos['motivo_rechazo'] == 'no_hay_partes'].copy()
    
    # KPIs de "No Hay Partes"
    ws6.merge_cells('A4:J4')
    ws6['A4'].value = "INDICADORES - NO HAY PARTES DISPONIBLES"
    ws6['A4'].font = Font(bold=True, size=12, color='FFFFFF')
    ws6['A4'].fill = no_hay_partes_fill
    ws6['A4'].alignment = Alignment(horizontal='center')
    
    total_no_partes = len(df_no_partes)
    pct_de_rechazos = (total_no_partes / total_rechazos * 100) if total_rechazos > 0 else 0
    pct_de_total = (total_no_partes / total_cotizaciones * 100) if total_cotizaciones > 0 else 0
    valor_perdido_partes = df_no_partes['costo_total'].sum() if total_no_partes > 0 else 0
    
    kpis_partes = [
        ['Casos "No Hay Partes"', total_no_partes],
        ['% de Todos los Rechazos', f'{pct_de_rechazos:.1f}%'],
        ['% del Total de Cotizaciones', f'{pct_de_total:.1f}%'],
        ['Valor Perdido por Falta de Partes', f'${valor_perdido_partes:,.2f}'],
    ]
    
    if total_no_partes > 0:
        kpis_partes.extend([
            ['Costo Promedio de Cotización', f'${df_no_partes["costo_total"].mean():,.2f}'],
            ['Piezas Promedio por Orden', f'{df_no_partes["total_piezas"].mean():.1f}'],
        ])
    
    for i, (kpi_label, kpi_val) in enumerate(kpis_partes):
        row_num = 6 + i
        ws6.cell(row=row_num, column=1, value=kpi_label).font = kpi_label_font
        ws6.cell(row=row_num, column=2, value=kpi_val).font = kpi_value_font
    
    if total_no_partes > 0:
        # Sección: Detalle de cada caso
        fila = 6 + len(kpis_partes) + 2
        ws6.merge_cells(f'A{fila}:J{fila}')
        ws6[f'A{fila}'].value = "DETALLE DE CASOS - NO HAY PARTES"
        ws6[f'A{fila}'].font = section_font
        ws6[f'A{fila}'].fill = section_fill
        fila += 1
        
        headers_np = [
            'Orden Cliente', 'Marca', 'Modelo', 'Tipo Equipo', 'Gama',
            'Sucursal', 'Técnico', 'Costo Total', 'Total Piezas', 'Detalle Rechazo'
        ]
        escribir_headers(ws6, headers_np, fila)
        fila += 1
        
        for _, rec in df_no_partes.iterrows():
            ws6.cell(row=fila, column=1, value=rec.get('orden_cliente', ''))
            ws6.cell(row=fila, column=2, value=rec.get('marca', ''))
            ws6.cell(row=fila, column=3, value=rec.get('modelo', ''))
            ws6.cell(row=fila, column=4, value=rec.get('tipo_equipo', ''))
            ws6.cell(row=fila, column=5, value=rec.get('gama', ''))
            ws6.cell(row=fila, column=6, value=rec.get('sucursal', ''))
            ws6.cell(row=fila, column=7, value=rec.get('tecnico', ''))
            ws6.cell(row=fila, column=8, value=f"${rec.get('costo_total', 0):,.2f}")
            ws6.cell(row=fila, column=9, value=rec.get('total_piezas', 0))
            ws6.cell(row=fila, column=10, value=rec.get('detalle_rechazo', ''))
            fila += 1
        
        # Sección: Top Marcas afectadas
        fila += 2
        ws6.merge_cells(f'A{fila}:J{fila}')
        ws6[f'A{fila}'].value = "MARCAS MÁS AFECTADAS POR FALTA DE PARTES"
        ws6[f'A{fila}'].font = section_font
        ws6[f'A{fila}'].fill = section_fill
        fila += 1
        
        escribir_headers(ws6, ['Marca', 'Casos', '% del Total "No Hay Partes"', 'Modelos Afectados', '', '', '', '', '', ''], fila)
        fila += 1
        
        marcas_np = df_no_partes['marca'].value_counts()
        for marca, conteo in marcas_np.items():
            modelos_afectados = df_no_partes[df_no_partes['marca'] == marca]['modelo'].unique()
            modelos_str = ', '.join([str(m) for m in modelos_afectados[:5]])
            pct = (conteo / total_no_partes * 100) if total_no_partes > 0 else 0
            
            ws6.cell(row=fila, column=1, value=marca or 'Sin marca')
            ws6.cell(row=fila, column=2, value=conteo)
            ws6.cell(row=fila, column=3, value=f'{pct:.1f}%')
            ws6.cell(row=fila, column=4, value=modelos_str)
            fila += 1
        
        # Sección: Piezas que se necesitaban (del modelo PiezaCotizada)
        if not df_piezas_proveedor.empty:
            # Filtrar piezas de cotizaciones "no hay partes"
            ids_no_partes = df_no_partes['cotizacion_id'].tolist()
            df_piezas_np = df_piezas_proveedor[
                df_piezas_proveedor['cotizacion_id'].isin(ids_no_partes)
            ]
            
            if not df_piezas_np.empty:
                fila += 2
                ws6.merge_cells(f'A{fila}:J{fila}')
                ws6[f'A{fila}'].value = "PIEZAS QUE SE NECESITABAN (No encontradas en el mercado)"
                ws6[f'A{fila}'].font = section_font
                ws6[f'A{fila}'].fill = section_fill
                fila += 1
                
                escribir_headers(ws6, ['Componente', 'Cant. Veces Solicitada', 'Marca Equipo', 'Modelo Equipo', 'Proveedor', 'Costo Unit. Promedio', 'Es Necesaria', '', '', ''], fila)
                fila += 1
                
                # Agrupar piezas por componente
                piezas_agrupadas = df_piezas_np.groupby('componente__nombre').agg(
                    veces=('id', 'count'),
                    costo_prom=('costo_unitario', 'mean'),
                    marcas=('cotizacion__orden__detalle_equipo__marca', lambda x: ', '.join(x.dropna().unique()[:3])),
                    modelos=('cotizacion__orden__detalle_equipo__modelo', lambda x: ', '.join(x.dropna().unique()[:3])),
                    proveedores=('proveedor', lambda x: ', '.join([str(p) for p in x.dropna().unique()[:3]]) if x.notna().any() else 'N/A'),
                    necesaria=('es_necesaria', 'mean'),
                ).reset_index().sort_values('veces', ascending=False)
                
                for _, pieza_row in piezas_agrupadas.iterrows():
                    ws6.cell(row=fila, column=1, value=pieza_row['componente__nombre'])
                    ws6.cell(row=fila, column=2, value=pieza_row['veces'])
                    ws6.cell(row=fila, column=3, value=pieza_row['marcas'])
                    ws6.cell(row=fila, column=4, value=pieza_row['modelos'])
                    ws6.cell(row=fila, column=5, value=pieza_row['proveedores'])
                    ws6.cell(row=fila, column=6, value=f"${pieza_row['costo_prom']:,.2f}")
                    es_nec_pct = pieza_row['necesaria'] * 100
                    ws6.cell(row=fila, column=7, value=f'{es_nec_pct:.0f}% necesaria')
                    fila += 1
        
        # Sección: Tendencia mensual
        fila += 2
        ws6.merge_cells(f'A{fila}:J{fila}')
        ws6[f'A{fila}'].value = "TENDENCIA MENSUAL: ¿ESTÁ MEJORANDO O EMPEORANDO?"
        ws6[f'A{fila}'].font = section_font
        ws6[f'A{fila}'].fill = section_fill
        fila += 1
        
        escribir_headers(ws6, ['Mes', 'Casos "No Hay Partes"', 'Total Rechazos del Mes', '% del Mes', 'Tendencia', '', '', '', '', ''], fila)
        fila += 1
        
        # Agrupar por mes
        if 'fecha_envio' in df_no_partes.columns and len(df_no_partes) > 0:
            # EXPLICACIÓN: tz_localize(None) quita el timezone antes de convertir a Period
            # Esto evita el warning de Pandas sobre pérdida de timezone
            df_no_partes['mes_periodo'] = pd.to_datetime(df_no_partes['fecha_envio']).dt.tz_localize(None).dt.to_period('M')
            df_rechazos_temp = df_rechazos.copy()
            df_rechazos_temp['mes_periodo'] = pd.to_datetime(df_rechazos_temp['fecha_envio']).dt.tz_localize(None).dt.to_period('M')
            
            meses_np = df_no_partes.groupby('mes_periodo').size()
            meses_total_rech = df_rechazos_temp.groupby('mes_periodo').size()
            
            prev_count = None
            for mes in sorted(meses_np.index):
                count = meses_np[mes]
                total_mes = meses_total_rech.get(mes, 0)
                pct_mes = (count / total_mes * 100) if total_mes > 0 else 0
                
                # Determinar tendencia
                if prev_count is not None:
                    if count > prev_count:
                        tendencia = 'EMPEORANDO'
                    elif count < prev_count:
                        tendencia = 'MEJORANDO'
                    else:
                        tendencia = 'ESTABLE'
                else:
                    tendencia = '-'
                
                ws6.cell(row=fila, column=1, value=str(mes))
                ws6.cell(row=fila, column=2, value=count)
                ws6.cell(row=fila, column=3, value=total_mes)
                ws6.cell(row=fila, column=4, value=f'{pct_mes:.1f}%')
                ws6.cell(row=fila, column=5, value=tendencia)
                
                if tendencia == 'EMPEORANDO':
                    ws6.cell(row=fila, column=5).fill = red_fill
                elif tendencia == 'MEJORANDO':
                    ws6.cell(row=fila, column=5).fill = green_fill
                
                prev_count = count
                fila += 1
    else:
        # No hay casos de "No hay partes"
        ws6.merge_cells('A6:J6')
        ws6['A6'].value = "No se encontraron cotizaciones rechazadas por falta de partes en el período seleccionado."
        ws6['A6'].font = Font(italic=True, size=12)
        ws6['A6'].alignment = Alignment(horizontal='center')
    
    autoajustar_columnas(ws6, max_width=50)
    
    # ========================================
    # HOJA 7: PIEZAS RECHAZADAS (detalle a nivel pieza)
    # ========================================
    ws7 = wb.create_sheet("Piezas Rechazadas")
    escribir_encabezado_hoja(ws7, "DETALLE DE PIEZAS EN COTIZACIONES RECHAZADAS", 12)
    
    if not df_piezas_proveedor.empty:
        headers_piezas = [
            'Componente', 'Descripción', 'Proveedor', 'Cantidad',
            'Costo Unitario', 'Costo Total', 'Es Necesaria', 'Sugerida por Técnico',
            'Marca Equipo', 'Modelo Equipo',
            'Motivo Rechazo Cotización', 'Motivo Rechazo Pieza'
        ]
        escribir_headers(ws7, headers_piezas, 4)
        
        # Enriquecer con motivo de rechazo de la cotización padre
        motivos_por_cotizacion = dict(zip(df_rechazos['cotizacion_id'], df_rechazos['motivo_rechazo']))
        
        fila = 5
        for _, pieza in df_piezas_proveedor.iterrows():
            cot_id = pieza.get('cotizacion_id')
            motivo_cot = motivos_por_cotizacion.get(cot_id, '')
            motivo_cot_label = labels_motivos.get(motivo_cot, str(motivo_cot).replace('_', ' ').title()) if motivo_cot else ''
            
            costo_unit = float(pieza.get('costo_unitario', 0))
            cantidad = int(pieza.get('cantidad', 1))
            costo_total_pieza = costo_unit * cantidad
            
            ws7.cell(row=fila, column=1, value=pieza.get('componente__nombre', ''))
            ws7.cell(row=fila, column=2, value=pieza.get('descripcion_adicional', ''))
            ws7.cell(row=fila, column=3, value=pieza.get('proveedor', ''))
            ws7.cell(row=fila, column=4, value=cantidad)
            ws7.cell(row=fila, column=5, value=f'${costo_unit:,.2f}')
            ws7.cell(row=fila, column=6, value=f'${costo_total_pieza:,.2f}')
            ws7.cell(row=fila, column=7, value='Si' if pieza.get('es_necesaria') else 'No')
            ws7.cell(row=fila, column=8, value='Si' if pieza.get('sugerida_por_tecnico') else 'No')
            ws7.cell(row=fila, column=9, value=pieza.get('cotizacion__orden__detalle_equipo__marca', ''))
            ws7.cell(row=fila, column=10, value=pieza.get('cotizacion__orden__detalle_equipo__modelo', ''))
            ws7.cell(row=fila, column=11, value=motivo_cot_label)
            ws7.cell(row=fila, column=12, value=pieza.get('motivo_rechazo_pieza', ''))
            fila += 1
        
        # Sección de resumen de piezas
        fila += 2
        ws7.merge_cells(f'A{fila}:L{fila}')
        ws7[f'A{fila}'].value = "RESUMEN: TOP COMPONENTES MÁS FRECUENTES EN RECHAZOS"
        ws7[f'A{fila}'].font = section_font
        ws7[f'A{fila}'].fill = section_fill
        fila += 1
        
        escribir_headers(ws7, ['Componente', 'Veces en Rechazos', 'Costo Unit. Promedio', 'Es Necesaria (%)', 'Top Proveedores', '', '', '', '', '', '', ''], fila)
        fila += 1
        
        resumen_componentes = df_piezas_proveedor.groupby('componente__nombre').agg(
            veces=('id', 'count'),
            costo_prom=('costo_unitario', 'mean'),
            necesaria=('es_necesaria', 'mean'),
            proveedores=('proveedor', lambda x: ', '.join([str(p) for p in x.dropna().unique()[:3]]) if x.notna().any() else 'N/A'),
        ).reset_index().sort_values('veces', ascending=False).head(20)
        
        for _, comp in resumen_componentes.iterrows():
            ws7.cell(row=fila, column=1, value=comp['componente__nombre'])
            ws7.cell(row=fila, column=2, value=comp['veces'])
            ws7.cell(row=fila, column=3, value=f"${comp['costo_prom']:,.2f}")
            ws7.cell(row=fila, column=4, value=f"{comp['necesaria'] * 100:.0f}%")
            ws7.cell(row=fila, column=5, value=comp['proveedores'])
            fila += 1
    else:
        ws7.merge_cells('A4:L4')
        ws7['A4'].value = "No hay datos de piezas para las cotizaciones rechazadas."
        ws7['A4'].font = Font(italic=True, size=12)
    
    autoajustar_columnas(ws7, max_width=45)
    
    # ========================================
    # HOJA 8: RECHAZOS POR COSTO ALTO (detalle con piezas)
    # ========================================
    ws8 = wb.create_sheet("Costo Alto")
    costo_alto_fill = PatternFill(start_color='e67e22', end_color='e67e22', fill_type='solid')
    
    escribir_encabezado_hoja(ws8, "ANÁLISIS DETALLADO: RECHAZOS POR COSTO ELEVADO", 10)
    
    df_costo_alto = df_rechazos[df_rechazos['motivo_rechazo'] == 'costo_alto'].copy()
    
    # KPIs de "Costo Alto"
    ws8.merge_cells('A4:J4')
    ws8['A4'].value = "INDICADORES - RECHAZOS POR COSTO ELEVADO"
    ws8['A4'].font = Font(bold=True, size=12, color='FFFFFF')
    ws8['A4'].fill = costo_alto_fill
    ws8['A4'].alignment = Alignment(horizontal='center')
    
    total_costo_alto = len(df_costo_alto)
    pct_de_rechazos_ca = (total_costo_alto / total_rechazos * 100) if total_rechazos > 0 else 0
    pct_de_total_ca = (total_costo_alto / total_cotizaciones * 100) if total_cotizaciones > 0 else 0
    valor_perdido_ca = df_costo_alto['costo_total'].sum() if total_costo_alto > 0 else 0
    
    kpis_ca = [
        ['Casos por Costo Elevado', total_costo_alto],
        ['% de Todos los Rechazos', f'{pct_de_rechazos_ca:.1f}%'],
        ['% del Total de Cotizaciones', f'{pct_de_total_ca:.1f}%'],
        ['Valor Perdido por Costo Alto', f'${valor_perdido_ca:,.2f}'],
    ]
    
    if total_costo_alto > 0:
        kpis_ca.extend([
            ['Costo Promedio de Cotización', f'${df_costo_alto["costo_total"].mean():,.2f}'],
            ['Costo Mediana de Cotización', f'${df_costo_alto["costo_total"].median():,.2f}'],
            ['Piezas Promedio por Orden', f'{df_costo_alto["total_piezas"].mean():.1f}'],
        ])
    
    for i, (kpi_label_ca, kpi_val_ca) in enumerate(kpis_ca):
        row_num = 6 + i
        ws8.cell(row=row_num, column=1, value=kpi_label_ca).font = kpi_label_font
        ws8.cell(row=row_num, column=2, value=kpi_val_ca).font = kpi_value_font
    
    if total_costo_alto > 0:
        # Mapeo de cotizacion_id → orden_cliente
        mapa_orden_cliente = dict(zip(df_rechazos['cotizacion_id'], df_rechazos['orden_cliente']))
        
        # Sección: Detalle por cada orden con sus piezas desglosadas
        fila = 6 + len(kpis_ca) + 2
        ws8.merge_cells(f'A{fila}:J{fila}')
        ws8[f'A{fila}'].value = "DETALLE POR ORDEN - COSTO ALTO (con piezas desglosadas)"
        ws8[f'A{fila}'].font = section_font
        ws8[f'A{fila}'].fill = section_fill
        fila += 1
        
        for _, rec_ca in df_costo_alto.sort_values('costo_total', ascending=False).iterrows():
            cot_id = rec_ca['cotizacion_id']
            orden_cli = rec_ca.get('orden_cliente', '') or 'Sin orden cliente'
            
            # Formatear fecha de envío
            fecha_envio_ca = ''
            if pd.notna(rec_ca.get('fecha_envio')):
                try:
                    fecha_envio_ca = pd.to_datetime(rec_ca['fecha_envio']).strftime('%d/%m/%Y')
                except:
                    fecha_envio_ca = str(rec_ca['fecha_envio'])
            
            # Encabezado de la orden
            ws8.merge_cells(f'A{fila}:J{fila}')
            ws8[f'A{fila}'].value = (
                f"Orden Cliente: {orden_cli}  |  "
                f"Fecha: {fecha_envio_ca}  |  "
                f"Marca: {rec_ca.get('marca', '')}  |  "
                f"Modelo: {rec_ca.get('modelo', '')}  |  "
                f"Sucursal: {rec_ca.get('sucursal', '')}  |  "
                f"Técnico: {rec_ca.get('tecnico', '')}  |  "
                f"Detalle: {rec_ca.get('detalle_rechazo', '')}"
            )
            ws8[f'A{fila}'].font = Font(bold=True, size=10, color='FFFFFF')
            ws8[f'A{fila}'].fill = costo_alto_fill
            fila += 1
            
            # Headers de piezas para esta orden
            headers_piezas_ca = [
                'Componente', 'Descripción', 'Proveedor',
                'Cantidad', 'Costo Unitario', 'Costo Total Pieza',
                'Es Necesaria', 'Sugerida por Técnico', '', ''
            ]
            escribir_headers(ws8, headers_piezas_ca, fila)
            fila += 1
            
            # Obtener piezas de esta cotización
            if not df_piezas_proveedor.empty:
                piezas_orden = df_piezas_proveedor[
                    df_piezas_proveedor['cotizacion_id'] == cot_id
                ]
            else:
                piezas_orden = pd.DataFrame()
            
            subtotal_piezas = 0
            if not piezas_orden.empty:
                for _, pieza_ca in piezas_orden.iterrows():
                    costo_unit = float(pieza_ca.get('costo_unitario', 0))
                    cantidad = int(pieza_ca.get('cantidad', 1))
                    costo_total_pieza = costo_unit * cantidad
                    subtotal_piezas += costo_total_pieza
                    
                    ws8.cell(row=fila, column=1, value=pieza_ca.get('componente__nombre', ''))
                    ws8.cell(row=fila, column=2, value=pieza_ca.get('descripcion_adicional', ''))
                    ws8.cell(row=fila, column=3, value=pieza_ca.get('proveedor', ''))
                    ws8.cell(row=fila, column=4, value=cantidad)
                    ws8.cell(row=fila, column=5, value=f'${costo_unit:,.2f}')
                    ws8.cell(row=fila, column=6, value=f'${costo_total_pieza:,.2f}')
                    ws8.cell(row=fila, column=7, value='Sí' if pieza_ca.get('es_necesaria') else 'No')
                    ws8.cell(row=fila, column=8, value='Sí' if pieza_ca.get('sugerida_por_tecnico') else 'No')
                    fila += 1
            else:
                ws8.cell(row=fila, column=1, value='(Sin piezas registradas)')
                ws8[f'A{fila}'].font = Font(italic=True, color='999999')
                fila += 1
            
            # Fila de totales para esta orden
            ws8.cell(row=fila, column=4, value='TOTAL ORDEN:').font = Font(bold=True)
            ws8.cell(row=fila, column=5, value=f'Piezas: ${subtotal_piezas:,.2f}').font = Font(bold=True)
            ws8.cell(row=fila, column=6, value=f'M.O.: ${rec_ca.get("costo_mano_obra", 0):,.2f}').font = Font(bold=True)
            ws8.cell(row=fila, column=7, value=f'Total: ${rec_ca.get("costo_total", 0):,.2f}')
            ws8[f'G{fila}'].font = Font(bold=True, size=11, color='c0392c')
            for c in range(1, 11):
                ws8.cell(row=fila, column=c).fill = orange_fill
            fila += 2  # Espacio entre órdenes
        
        # Sección: Resumen comparativo (tabla resumen)
        ws8.merge_cells(f'A{fila}:J{fila}')
        ws8[f'A{fila}'].value = "RESUMEN: TODAS LAS ÓRDENES RECHAZADAS POR COSTO ALTO"
        ws8[f'A{fila}'].font = section_font
        ws8[f'A{fila}'].fill = section_fill
        fila += 1
        
        escribir_headers(ws8, [
            'Orden Cliente', 'Fecha Cotización', 'Marca', 'Modelo', 'Sucursal', 'Técnico',
            'Total Piezas', 'Costo Piezas', 'Costo M.O.', 'Costo Total'
        ], fila)
        fila += 1
        
        for _, rec_ca in df_costo_alto.sort_values('costo_total', ascending=False).iterrows():
            fecha_envio_resumen = ''
            if pd.notna(rec_ca.get('fecha_envio')):
                try:
                    fecha_envio_resumen = pd.to_datetime(rec_ca['fecha_envio']).strftime('%d/%m/%Y')
                except:
                    fecha_envio_resumen = str(rec_ca['fecha_envio'])
            
            ws8.cell(row=fila, column=1, value=rec_ca.get('orden_cliente', ''))
            ws8.cell(row=fila, column=2, value=fecha_envio_resumen)
            ws8.cell(row=fila, column=3, value=rec_ca.get('marca', ''))
            ws8.cell(row=fila, column=4, value=rec_ca.get('modelo', ''))
            ws8.cell(row=fila, column=5, value=rec_ca.get('sucursal', ''))
            ws8.cell(row=fila, column=6, value=rec_ca.get('tecnico', ''))
            ws8.cell(row=fila, column=7, value=rec_ca.get('total_piezas', 0))
            ws8.cell(row=fila, column=8, value=f'${rec_ca.get("costo_total_piezas", 0):,.2f}')
            ws8.cell(row=fila, column=9, value=f'${rec_ca.get("costo_mano_obra", 0):,.2f}')
            ws8.cell(row=fila, column=10, value=f'${rec_ca.get("costo_total", 0):,.2f}')
            fila += 1
    else:
        ws8.merge_cells('A6:J6')
        ws8['A6'].value = "No se encontraron cotizaciones rechazadas por costo elevado en el período seleccionado."
        ws8['A6'].font = Font(italic=True, size=12)
        ws8['A6'].alignment = Alignment(horizontal='center')
    
    autoajustar_columnas(ws8, max_width=50)
    
    # ========================================
    # HOJA 9: SERVICIOS CON 3+ Y 4+ PIEZAS COTIZADAS
    # ========================================
    ws9 = wb.create_sheet("Servicios 3+ Piezas")
    multi_piezas_fill = PatternFill(start_color='8e44ad', end_color='8e44ad', fill_type='solid')
    
    escribir_encabezado_hoja(ws9, "SERVICIOS CON MÚLTIPLES PIEZAS COTIZADAS (RECHAZADAS)", 10)
    
    # Mapeo cotizacion_id → orden_cliente para esta hoja
    mapa_oc = dict(zip(df_rechazos['cotizacion_id'], df_rechazos['orden_cliente']))
    
    # ---- SECCIÓN A: Servicios con 3 o más piezas ----
    df_3_plus = df_rechazos[df_rechazos['total_piezas'] >= 3].copy()
    total_3_plus = len(df_3_plus)
    
    ws9.merge_cells('A4:J4')
    ws9['A4'].value = f"SECCIÓN A: SERVICIOS CON 3 O MÁS PIEZAS COTIZADAS ({total_3_plus} registros)"
    ws9['A4'].font = Font(bold=True, size=12, color='FFFFFF')
    ws9['A4'].fill = multi_piezas_fill
    ws9['A4'].alignment = Alignment(horizontal='center')
    
    if total_3_plus > 0:
        headers_multi = [
            'Orden Cliente', 'Fecha Cotización', 'Marca', 'Modelo', 'Sucursal', 'Técnico',
            'Motivo Rechazo', 'Total Piezas', 'Costo Piezas', 'Costo M.O.', 'Costo Total'
        ]
        escribir_headers(ws9, headers_multi, 5)
        
        fila = 6
        suma_total_3 = 0
        for _, rec_mp in df_3_plus.sort_values('total_piezas', ascending=False).iterrows():
            motivo_lab = labels_motivos.get(
                rec_mp.get('motivo_rechazo', ''),
                str(rec_mp.get('motivo_rechazo', '')).replace('_', ' ').title()
            ) if rec_mp.get('motivo_rechazo') else 'Sin motivo'
            
            costo_t = rec_mp.get('costo_total', 0)
            suma_total_3 += costo_t
            
            fecha_envio_3 = ''
            if pd.notna(rec_mp.get('fecha_envio')):
                try:
                    fecha_envio_3 = pd.to_datetime(rec_mp['fecha_envio']).strftime('%d/%m/%Y')
                except:
                    fecha_envio_3 = str(rec_mp['fecha_envio'])
            
            ws9.cell(row=fila, column=1, value=rec_mp.get('orden_cliente', ''))
            ws9.cell(row=fila, column=2, value=fecha_envio_3)
            ws9.cell(row=fila, column=3, value=rec_mp.get('marca', ''))
            ws9.cell(row=fila, column=4, value=rec_mp.get('modelo', ''))
            ws9.cell(row=fila, column=5, value=rec_mp.get('sucursal', ''))
            ws9.cell(row=fila, column=6, value=rec_mp.get('tecnico', ''))
            ws9.cell(row=fila, column=7, value=motivo_lab)
            ws9.cell(row=fila, column=8, value=rec_mp.get('total_piezas', 0))
            ws9.cell(row=fila, column=9, value=f'${rec_mp.get("costo_total_piezas", 0):,.2f}')
            ws9.cell(row=fila, column=10, value=f'${rec_mp.get("costo_mano_obra", 0):,.2f}')
            ws9.cell(row=fila, column=11, value=f'${costo_t:,.2f}')
            fila += 1
        
        # Fila de totales
        ws9.cell(row=fila, column=7, value='TOTAL:').font = Font(bold=True)
        ws9.cell(row=fila, column=8, value=f'{df_3_plus["total_piezas"].sum()} piezas').font = Font(bold=True)
        ws9.cell(row=fila, column=11, value=f'${suma_total_3:,.2f}')
        ws9[f'K{fila}'].font = Font(bold=True, size=11, color='8e44ad')
        for c in range(1, 12):
            ws9.cell(row=fila, column=c).fill = blue_fill
        fila += 1
    else:
        fila = 6
        ws9.cell(row=fila, column=1, value='No hay servicios rechazados con 3 o más piezas cotizadas.')
        ws9[f'A{fila}'].font = Font(italic=True)
        fila += 1
    
    # ---- SECCIÓN B: Servicios con 4 o más piezas ----
    fila += 2
    df_4_plus = df_rechazos[df_rechazos['total_piezas'] >= 4].copy()
    total_4_plus = len(df_4_plus)
    
    ws9.merge_cells(f'A{fila}:J{fila}')
    ws9[f'A{fila}'].value = f"SECCIÓN B: SERVICIOS CON 4 O MÁS PIEZAS COTIZADAS ({total_4_plus} registros)"
    ws9[f'A{fila}'].font = Font(bold=True, size=12, color='FFFFFF')
    ws9[f'A{fila}'].fill = multi_piezas_fill
    ws9[f'A{fila}'].alignment = Alignment(horizontal='center')
    fila += 1
    
    if total_4_plus > 0:
        escribir_headers(ws9, [
            'Orden Cliente', 'Fecha Cotización', 'Marca', 'Modelo', 'Sucursal', 'Técnico',
            'Motivo Rechazo', 'Total Piezas', 'Costo Piezas', 'Costo M.O.', 'Costo Total'
        ], fila)
        fila += 1
        
        suma_total_4 = 0
        for _, rec_mp in df_4_plus.sort_values('total_piezas', ascending=False).iterrows():
            motivo_lab = labels_motivos.get(
                rec_mp.get('motivo_rechazo', ''),
                str(rec_mp.get('motivo_rechazo', '')).replace('_', ' ').title()
            ) if rec_mp.get('motivo_rechazo') else 'Sin motivo'
            
            costo_t = rec_mp.get('costo_total', 0)
            suma_total_4 += costo_t
            
            fecha_envio_4 = ''
            if pd.notna(rec_mp.get('fecha_envio')):
                try:
                    fecha_envio_4 = pd.to_datetime(rec_mp['fecha_envio']).strftime('%d/%m/%Y')
                except:
                    fecha_envio_4 = str(rec_mp['fecha_envio'])
            
            ws9.cell(row=fila, column=1, value=rec_mp.get('orden_cliente', ''))
            ws9.cell(row=fila, column=2, value=fecha_envio_4)
            ws9.cell(row=fila, column=3, value=rec_mp.get('marca', ''))
            ws9.cell(row=fila, column=4, value=rec_mp.get('modelo', ''))
            ws9.cell(row=fila, column=5, value=rec_mp.get('sucursal', ''))
            ws9.cell(row=fila, column=6, value=rec_mp.get('tecnico', ''))
            ws9.cell(row=fila, column=7, value=motivo_lab)
            ws9.cell(row=fila, column=8, value=rec_mp.get('total_piezas', 0))
            ws9.cell(row=fila, column=9, value=f'${rec_mp.get("costo_total_piezas", 0):,.2f}')
            ws9.cell(row=fila, column=10, value=f'${rec_mp.get("costo_mano_obra", 0):,.2f}')
            ws9.cell(row=fila, column=11, value=f'${costo_t:,.2f}')
            fila += 1
        
        # Fila de totales
        ws9.cell(row=fila, column=7, value='TOTAL:').font = Font(bold=True)
        ws9.cell(row=fila, column=8, value=f'{df_4_plus["total_piezas"].sum()} piezas').font = Font(bold=True)
        ws9.cell(row=fila, column=11, value=f'${suma_total_4:,.2f}')
        ws9[f'K{fila}'].font = Font(bold=True, size=11, color='8e44ad')
        for c in range(1, 12):
            ws9.cell(row=fila, column=c).fill = blue_fill
        fila += 1
    else:
        ws9.cell(row=fila, column=1, value='No hay servicios rechazados con 4 o más piezas cotizadas.')
        ws9[f'A{fila}'].font = Font(italic=True)
        fila += 1
    
    # ---- SECCIÓN C: Desglose de piezas por orden (solo 4+) ----
    if total_4_plus > 0 and not df_piezas_proveedor.empty:
        fila += 2
        ws9.merge_cells(f'A{fila}:J{fila}')
        ws9[f'A{fila}'].value = "DESGLOSE DE PIEZAS: SERVICIOS CON 4+ PIEZAS"
        ws9[f'A{fila}'].font = section_font
        ws9[f'A{fila}'].fill = section_fill
        fila += 1
        
        for _, rec_mp in df_4_plus.sort_values('total_piezas', ascending=False).iterrows():
            cot_id = rec_mp['cotizacion_id']
            orden_cli = rec_mp.get('orden_cliente', '') or 'Sin orden cliente'
            
            # Encabezado de la orden
            ws9.merge_cells(f'A{fila}:J{fila}')
            fecha_envio_c = ''
            if pd.notna(rec_mp.get('fecha_envio')):
                try:
                    fecha_envio_c = pd.to_datetime(rec_mp['fecha_envio']).strftime('%d/%m/%Y')
                except:
                    fecha_envio_c = str(rec_mp['fecha_envio'])
            
            ws9[f'A{fila}'].value = (
                f"Orden Cliente: {orden_cli}  |  "
                f"Fecha: {fecha_envio_c}  |  "
                f"{rec_mp.get('marca', '')} {rec_mp.get('modelo', '')}  |  "
                f"Piezas: {rec_mp.get('total_piezas', 0)}  |  "
                f"Total: ${rec_mp.get('costo_total', 0):,.2f}"
            )
            ws9[f'A{fila}'].font = Font(bold=True, size=10, color='FFFFFF')
            ws9[f'A{fila}'].fill = multi_piezas_fill
            fila += 1
            
            piezas_esta_orden = df_piezas_proveedor[
                df_piezas_proveedor['cotizacion_id'] == cot_id
            ]
            
            if not piezas_esta_orden.empty:
                escribir_headers(ws9, [
                    'Componente', 'Descripción', 'Proveedor',
                    'Cantidad', 'Costo Unitario', 'Costo Total Pieza',
                    'Es Necesaria', 'Sugerida Técnico', '', ''
                ], fila)
                fila += 1
                
                sub_total = 0
                for _, pieza_mp in piezas_esta_orden.iterrows():
                    cu = float(pieza_mp.get('costo_unitario', 0))
                    cant = int(pieza_mp.get('cantidad', 1))
                    ct = cu * cant
                    sub_total += ct
                    
                    ws9.cell(row=fila, column=1, value=pieza_mp.get('componente__nombre', ''))
                    ws9.cell(row=fila, column=2, value=pieza_mp.get('descripcion_adicional', ''))
                    ws9.cell(row=fila, column=3, value=pieza_mp.get('proveedor', ''))
                    ws9.cell(row=fila, column=4, value=cant)
                    ws9.cell(row=fila, column=5, value=f'${cu:,.2f}')
                    ws9.cell(row=fila, column=6, value=f'${ct:,.2f}')
                    ws9.cell(row=fila, column=7, value='Sí' if pieza_mp.get('es_necesaria') else 'No')
                    ws9.cell(row=fila, column=8, value='Sí' if pieza_mp.get('sugerida_por_tecnico') else 'No')
                    fila += 1
                
                ws9.cell(row=fila, column=5, value='Subtotal piezas:').font = Font(bold=True)
                ws9.cell(row=fila, column=6, value=f'${sub_total:,.2f}').font = Font(bold=True)
            else:
                ws9.cell(row=fila, column=1, value='(Sin piezas registradas)')
                ws9[f'A{fila}'].font = Font(italic=True, color='999999')
            fila += 2
    
    autoajustar_columnas(ws9, max_width=50)
    
    # ========================================
    # GENERAR Y RETORNAR ARCHIVO
    # ========================================
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nombre_archivo = f'Analisis_Rechazos_{timestamp}.xlsx'
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    
    wb.save(response)
    
    return response


# ============================================================================
# EXPORTACIÓN EXCEL: ANÁLISIS DE COTIZACIONES ACEPTADAS
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
def exportar_analisis_aceptaciones(request):
    """
    Exporta un análisis exhaustivo de cotizaciones aceptadas a Excel con 9 hojas,
    incluyendo datos cruzados con VentaMostrador (servicios, paquetes, piezas).
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Este Excel es el espejo del 'Análisis de Rechazos', pero enfocado en lo positivo:
    qué se aceptó, cuánto se generó, qué servicios adicionales (VM) se vendieron,
    y cómo se comportó la cadena de suministro post-aceptación.
    
    Hojas:
        1. Resumen Aceptaciones - KPIs principales de aceptaciones + VM
        2. Detalle Aceptaciones - Cada cotización aceptada con datos completos
        3. Piezas Aceptadas - Detalle a nivel pieza individual
        4. Aceptación Parcial - Cotizaciones con piezas mixtas (aceptadas/rechazadas)
        5. Ventas Mostrador - VM asociadas a cotizaciones aceptadas
        6. Servicios Adicionales - Análisis de servicios VM (limpieza, reinstalación, etc.)
        7. Seguimiento de Piezas - Estado del tracking post-aceptación
        8. Rendimiento por Técnico - Métricas de aceptación + upsell por técnico
        9. Rendimiento por Sucursal - Métricas de aceptación + upsell por sucursal
    
    Returns:
        HttpResponse: Archivo Excel (.xlsx) para descargar
    """
    
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    from datetime import datetime
    import pandas as pd
    
    from .utils_cotizaciones import (
        obtener_dataframe_cotizaciones,
        calcular_kpis_generales,
        calcular_kpis_aceptaciones,
        analizar_piezas_cotizadas,
        analizar_servicios_vm_aceptadas,
        analizar_seguimiento_piezas_aceptadas,
    )
    
    # ========================================
    # OBTENER DATOS CON MISMOS FILTROS QUE EL DASHBOARD
    # ========================================
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    sucursal_id = request.GET.get('sucursal')
    tecnico_id = request.GET.get('tecnico')
    gama = request.GET.get('gama')
    
    df_cotizaciones = obtener_dataframe_cotizaciones(
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        sucursal_id=sucursal_id,
        tecnico_id=tecnico_id,
        gama=gama
    )
    
    if df_cotizaciones.empty:
        messages.error(request, 'No hay datos para exportar con los filtros aplicados.')
        return redirect('servicio_tecnico:dashboard_cotizaciones')
    
    # Filtrar solo aceptadas
    df_aceptadas = df_cotizaciones[df_cotizaciones['aceptada'] == True].copy()
    
    if df_aceptadas.empty:
        messages.warning(request, 'No hay cotizaciones aceptadas en el período seleccionado.')
        return redirect('servicio_tecnico:dashboard_cotizaciones')
    
    # KPIs
    kpis_generales = calcular_kpis_generales(df_cotizaciones)
    kpis_aceptaciones = calcular_kpis_aceptaciones(df_cotizaciones)
    
    # Análisis VM y seguimiento
    analisis_vm = analizar_servicios_vm_aceptadas(
        df_cotizaciones,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        sucursal_id=sucursal_id,
        tecnico_id=tecnico_id,
        gama=gama,
    )
    analisis_seguimiento = analizar_seguimiento_piezas_aceptadas(df_cotizaciones)
    
    # Piezas aceptadas
    cotizacion_ids_aceptadas = df_aceptadas['cotizacion_id'].tolist()
    
    from .models import PiezaCotizada, SeguimientoPieza, VentaMostrador, PiezaVentaMostrador
    piezas_aceptadas_qs = PiezaCotizada.objects.filter(
        cotizacion_id__in=cotizacion_ids_aceptadas
    ).select_related(
        'componente',
        'cotizacion',
        'cotizacion__orden',
        'cotizacion__orden__detalle_equipo'
    )
    
    # ========================================
    # CREAR WORKBOOK
    # ========================================
    wb = Workbook()
    wb.remove(wb.active)
    
    # Estilos reutilizables
    header_font = Font(bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill(start_color='198754', end_color='198754', fill_type='solid')  # Verde
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    
    title_font = Font(bold=True, size=14, color='FFFFFF')
    title_fill = PatternFill(start_color='212529', end_color='212529', fill_type='solid')
    title_align = Alignment(horizontal='center', vertical='center')
    
    subtitle_font = Font(italic=True, size=10, color='666666')
    
    kpi_label_font = Font(bold=True, size=11)
    kpi_value_font = Font(bold=True, size=12, color='198754')  # Verde para aceptaciones
    
    green_fill = PatternFill(start_color='d4edda', end_color='d4edda', fill_type='solid')
    blue_fill = PatternFill(start_color='d1ecf1', end_color='d1ecf1', fill_type='solid')
    yellow_fill = PatternFill(start_color='fff3cd', end_color='fff3cd', fill_type='solid')
    purple_fill = PatternFill(start_color='e2d5f1', end_color='e2d5f1', fill_type='solid')
    teal_fill = PatternFill(start_color='d1f2eb', end_color='d1f2eb', fill_type='solid')
    
    border_thin = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    number_fmt = '#,##0.00'
    pct_fmt = '0.0%'
    
    def aplicar_estilos_header(ws, fila, num_cols):
        """Aplica estilos a la fila de encabezados."""
        for col in range(1, num_cols + 1):
            cell = ws.cell(row=fila, column=col)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = border_thin
    
    def auto_ajustar_columnas(ws, max_width=50):
        """Autoajusta el ancho de las columnas."""
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            ws.column_dimensions[col_letter].width = min(max_len + 3, max_width)
    
    # ========================================================================
    # HOJA 1: RESUMEN ACEPTACIONES
    # ========================================================================
    ws1 = wb.create_sheet('Resumen Aceptaciones')
    
    # Título
    ws1.merge_cells('A1:F1')
    ws1['A1'] = 'ANÁLISIS DE COTIZACIONES ACEPTADAS'
    ws1['A1'].font = title_font
    ws1['A1'].fill = title_fill
    ws1['A1'].alignment = title_align
    
    # Subtítulo con filtros
    filtros_texto = f"Período: {fecha_inicio or 'Inicio'} - {fecha_fin or 'Actual'}"
    ws1.merge_cells('A2:F2')
    ws1['A2'] = filtros_texto
    ws1['A2'].font = subtitle_font
    ws1['A2'].alignment = Alignment(horizontal='center')
    
    # Sección: KPIs principales
    fila = 4
    ws1.merge_cells(f'A{fila}:F{fila}')
    ws1[f'A{fila}'] = 'INDICADORES PRINCIPALES'
    ws1[f'A{fila}'].font = Font(bold=True, size=12)
    ws1[f'A{fila}'].fill = green_fill
    
    fila += 1
    headers = ['Métrica', 'Valor', 'Porcentaje', 'Observaciones']
    for col, h in enumerate(headers, 1):
        ws1.cell(row=fila, column=col, value=h)
    aplicar_estilos_header(ws1, fila, len(headers))
    
    # Datos de KPIs
    metricas = [
        ('Total Cotizaciones', kpis_generales['total_cotizaciones'], '', 'Todas las cotizaciones en el período'),
        ('Total Aceptadas', kpis_aceptaciones['total_aceptadas'], f"{kpis_generales.get('tasa_aceptacion', 0)}%", 'Tasa de aceptación global'),
        ('Aceptación Total', kpis_aceptaciones['aceptacion_total_count'], f"{kpis_aceptaciones['aceptacion_total_pct']}%", 'Todas las piezas aceptadas'),
        ('Aceptación Parcial', kpis_aceptaciones['aceptacion_parcial_count'], f"{kpis_aceptaciones['aceptacion_parcial_pct']}%", 'Algunas piezas rechazadas'),
        ('Valor Total Aceptado', kpis_aceptaciones['valor_total_aceptado'], f"{kpis_aceptaciones['porcentaje_recuperacion']}% del cotizado", 'Monto final que paga el cliente'),
        ('Ticket Promedio Aceptado', kpis_aceptaciones['ticket_promedio_aceptado'], '', 'Monto promedio por cotización aceptada'),
        ('Piezas Promedio por Aceptada', kpis_aceptaciones['piezas_promedio_aceptadas'], '', 'Promedio de piezas aceptadas'),
        ('Con Descuento Mano de Obra', kpis_aceptaciones['descuento_count'], f"{kpis_aceptaciones['descuento_pct']}%", f"Ahorro total: {kpis_aceptaciones['descuento_monto_total_fmt']}"),
        ('Tiempo Respuesta Prom. (días)', kpis_aceptaciones['tiempo_respuesta_aceptadas'], '', 'Días promedio hasta respuesta positiva'),
        ('--- VENTA MOSTRADOR ---', '', '', ''),
        ('Aceptadas con VM', kpis_aceptaciones['con_vm_count'], f"{kpis_aceptaciones['con_vm_pct']}%", 'Tasa de upsell'),
        ('Valor VM Complementario', kpis_aceptaciones['valor_vm_complementario'], '', 'Ingreso adicional por VM'),
        ('Valor Combinado Total', kpis_aceptaciones['valor_combinado_total'], '', 'Cotización + VM'),
        ('Paquete Más Vendido', kpis_aceptaciones['paquete_mas_vendido'], '', ''),
        ('Servicio Más Vendido', kpis_aceptaciones['servicio_mas_vendido'], '', ''),
    ]
    
    for metrica, valor, pct, obs in metricas:
        fila += 1
        ws1.cell(row=fila, column=1, value=metrica).font = kpi_label_font
        cell_val = ws1.cell(row=fila, column=2, value=valor)
        if isinstance(valor, (int, float)) and valor > 100:
            cell_val.number_format = number_fmt
        cell_val.font = kpi_value_font
        ws1.cell(row=fila, column=3, value=pct)
        ws1.cell(row=fila, column=4, value=obs).font = Font(italic=True, color='666666')
        for col in range(1, 5):
            ws1.cell(row=fila, column=col).border = border_thin
    
    auto_ajustar_columnas(ws1)
    
    # ========================================================================
    # HOJA 2: DETALLE ACEPTACIONES
    # ========================================================================
    ws2 = wb.create_sheet('Detalle Aceptaciones')
    
    # Título
    ws2.merge_cells('A1:Y1')
    ws2['A1'] = f'DETALLE DE COTIZACIONES ACEPTADAS ({len(df_aceptadas)} registros)'
    ws2['A1'].font = title_font
    ws2['A1'].fill = title_fill
    ws2['A1'].alignment = title_align
    
    # Headers
    headers_detalle = [
        'Orden Cliente', 'Número Serie', 'Marca', 'Modelo', 'Tipo Equipo',
        'Gama', 'Sucursal', 'Técnico', 'Responsable',
        'Fecha Envío', 'Fecha Respuesta', 'Días Respuesta',
        'Costo Total Cotizado', 'Costo Piezas Aceptadas', 'Costo Piezas Rechazadas',
        'Costo Mano Obra', 'Descuento MO', 'Costo Total Final',
        'Total Piezas', 'Piezas Aceptadas', 'Piezas Rechazadas',
        'Tiene VM', 'Paquete VM', 'Total VM', 'Valor Combinado',
    ]
    
    fila = 3
    for col, h in enumerate(headers_detalle, 1):
        ws2.cell(row=fila, column=col, value=h)
    aplicar_estilos_header(ws2, fila, len(headers_detalle))
    
    # Datos
    for _, row in df_aceptadas.iterrows():
        fila += 1
        
        # Convertir fechas a string para evitar error de openpyxl con timezones
        # (openpyxl no soporta datetime con tzinfo != None)
        fecha_envio_str = ''
        if pd.notna(row.get('fecha_envio')):
            try:
                fecha_envio_str = pd.to_datetime(row['fecha_envio']).strftime('%d/%m/%Y')
            except Exception:
                fecha_envio_str = str(row['fecha_envio'])
        
        fecha_respuesta_str = ''
        if pd.notna(row.get('fecha_respuesta')):
            try:
                fecha_respuesta_str = pd.to_datetime(row['fecha_respuesta']).strftime('%d/%m/%Y')
            except Exception:
                fecha_respuesta_str = str(row['fecha_respuesta'])
        
        datos = [
            row.get('orden_cliente', ''),
            row.get('numero_serie', ''),
            row.get('marca', ''),
            row.get('modelo', ''),
            row.get('tipo_equipo', ''),
            row.get('gama', ''),
            row.get('sucursal', ''),
            row.get('tecnico', ''),
            row.get('responsable', ''),
            fecha_envio_str,
            fecha_respuesta_str,
            row.get('dias_sin_respuesta', ''),
            row.get('costo_total', 0),
            row.get('costo_piezas_aceptadas', 0),
            row.get('costo_piezas_rechazadas', 0),
            row.get('costo_mano_obra', 0),
            row.get('monto_descuento', 0),
            row.get('costo_total_final', 0),
            row.get('total_piezas', 0),
            row.get('piezas_aceptadas', 0),
            row.get('piezas_rechazadas', 0),
            'Sí' if row.get('tiene_venta_mostrador', False) else 'No',
            row.get('vm_paquete', 'ninguno').capitalize() if row.get('tiene_venta_mostrador', False) else '',
            row.get('vm_total_venta', 0) if row.get('tiene_venta_mostrador', False) else 0,
            row.get('valor_total_combinado', 0),
        ]
        for col, valor in enumerate(datos, 1):
            cell = ws2.cell(row=fila, column=col, value=valor)
            cell.border = border_thin
            if col in (13, 14, 15, 16, 17, 18, 24, 25):
                cell.number_format = number_fmt
    
    auto_ajustar_columnas(ws2)
    
    # ========================================================================
    # HOJA 3: PIEZAS ACEPTADAS
    # ========================================================================
    ws3 = wb.create_sheet('Piezas Aceptadas')
    
    ws3.merge_cells('A1:L1')
    ws3['A1'] = 'DETALLE DE PIEZAS EN COTIZACIONES ACEPTADAS'
    ws3['A1'].font = title_font
    ws3['A1'].fill = title_fill
    ws3['A1'].alignment = title_align
    
    headers_piezas = [
        'Orden', 'Componente', 'Descripción', 'Proveedor',
        'Cantidad', 'Costo Unitario', 'Costo Total',
        'Es Necesaria', 'Sugerida por Técnico',
        'Aceptada por Cliente', 'Motivo Rechazo Pieza', 'Prioridad',
    ]
    
    fila = 3
    for col, h in enumerate(headers_piezas, 1):
        ws3.cell(row=fila, column=col, value=h)
    aplicar_estilos_header(ws3, fila, len(headers_piezas))
    
    for pieza in piezas_aceptadas_qs:
        fila += 1
        detalle = pieza.cotizacion.orden.detalle_equipo if hasattr(pieza.cotizacion.orden, 'detalle_equipo') else None
        orden_cliente = detalle.orden_cliente if detalle else ''
        
        # Determinar aceptación con herencia
        aceptada = pieza.aceptada_por_cliente
        if aceptada is None:
            aceptada = pieza.cotizacion.usuario_acepto
        
        datos = [
            orden_cliente,
            pieza.componente.nombre if pieza.componente else '',
            pieza.descripcion_adicional,
            pieza.proveedor,
            pieza.cantidad,
            float(pieza.costo_unitario),
            float(pieza.costo_total),
            'Sí' if pieza.es_necesaria else 'No',
            'Sí' if pieza.sugerida_por_tecnico else 'No',
            'Sí' if aceptada else ('No' if aceptada is False else 'Pendiente'),
            pieza.motivo_rechazo_pieza or '',
            pieza.orden_prioridad,
        ]
        for col, valor in enumerate(datos, 1):
            cell = ws3.cell(row=fila, column=col, value=valor)
            cell.border = border_thin
            if col in (6, 7):
                cell.number_format = number_fmt
            # Colorear según aceptación
            if col == 10:
                if valor == 'Sí':
                    cell.fill = green_fill
                elif valor == 'No':
                    cell.fill = PatternFill(start_color='f8d7da', end_color='f8d7da', fill_type='solid')
    
    # Resumen de piezas
    fila += 2
    total_piezas_todas = piezas_aceptadas_qs.count()
    piezas_si = piezas_aceptadas_qs.filter(aceptada_por_cliente=True).count()
    piezas_no = piezas_aceptadas_qs.filter(aceptada_por_cliente=False).count()
    piezas_pendientes = total_piezas_todas - piezas_si - piezas_no
    
    ws3.cell(row=fila, column=1, value='RESUMEN').font = Font(bold=True, size=12)
    fila += 1
    ws3.cell(row=fila, column=1, value='Total piezas:').font = kpi_label_font
    ws3.cell(row=fila, column=2, value=total_piezas_todas)
    fila += 1
    ws3.cell(row=fila, column=1, value='Aceptadas:').font = kpi_label_font
    ws3.cell(row=fila, column=2, value=piezas_si).fill = green_fill
    fila += 1
    ws3.cell(row=fila, column=1, value='Rechazadas:').font = kpi_label_font
    ws3.cell(row=fila, column=2, value=piezas_no)
    fila += 1
    ws3.cell(row=fila, column=1, value='Heredan aceptación:').font = kpi_label_font
    ws3.cell(row=fila, column=2, value=piezas_pendientes)
    
    # Top componentes más aceptados
    fila += 2
    ws3.cell(row=fila, column=1, value='TOP COMPONENTES MÁS ACEPTADOS').font = Font(bold=True, size=12)
    ws3.cell(row=fila, column=1).fill = green_fill
    fila += 1
    
    from django.db.models import Sum as DjSum, Count as DjCount
    top_comp = piezas_aceptadas_qs.filter(
        aceptada_por_cliente=True
    ).values('componente__nombre').annotate(
        total=DjCount('id'),
        ingreso=DjSum('costo_unitario'),
    ).order_by('-total')[:10]
    
    headers_top = ['Componente', 'Cantidad', 'Ingreso Total']
    for col, h in enumerate(headers_top, 1):
        ws3.cell(row=fila, column=col, value=h)
    aplicar_estilos_header(ws3, fila, len(headers_top))
    
    for comp in top_comp:
        fila += 1
        ws3.cell(row=fila, column=1, value=comp['componente__nombre'] or 'Sin nombre').border = border_thin
        ws3.cell(row=fila, column=2, value=comp['total']).border = border_thin
        cell_ing = ws3.cell(row=fila, column=3, value=float(comp['ingreso'] or 0))
        cell_ing.number_format = number_fmt
        cell_ing.border = border_thin
    
    auto_ajustar_columnas(ws3)
    
    # ========================================================================
    # HOJA 4: ACEPTACIÓN PARCIAL
    # ========================================================================
    ws4 = wb.create_sheet('Aceptación Parcial')
    
    df_parcial = df_aceptadas[
        (df_aceptadas['piezas_rechazadas'] > 0) & (df_aceptadas['piezas_aceptadas'] > 0)
    ]
    
    ws4.merge_cells('A1:N1')
    ws4['A1'] = f'COTIZACIONES CON ACEPTACIÓN PARCIAL ({len(df_parcial)} registros)'
    ws4['A1'].font = title_font
    ws4['A1'].fill = title_fill
    ws4['A1'].alignment = title_align
    
    ws4.merge_cells('A2:N2')
    ws4['A2'] = 'Cotizaciones donde el cliente aceptó ALGUNAS piezas pero rechazó otras'
    ws4['A2'].font = subtitle_font
    ws4['A2'].alignment = Alignment(horizontal='center')
    
    headers_parcial = [
        'Orden Cliente', 'Marca', 'Modelo', 'Sucursal', 'Técnico',
        'Total Piezas', 'Piezas Aceptadas', 'Piezas Rechazadas',
        '% Aceptadas', 'Costo Cotizado', 'Costo Aceptado', 'Costo Rechazado',
        'Diferencia', 'Tiene VM',
    ]
    
    fila = 4
    for col, h in enumerate(headers_parcial, 1):
        ws4.cell(row=fila, column=col, value=h)
    aplicar_estilos_header(ws4, fila, len(headers_parcial))
    
    for _, row in df_parcial.iterrows():
        fila += 1
        diferencia = row.get('costo_total', 0) - row.get('costo_total_final', 0)
        datos = [
            row.get('orden_cliente', ''),
            row.get('marca', ''),
            row.get('modelo', ''),
            row.get('sucursal', ''),
            row.get('tecnico', ''),
            row.get('total_piezas', 0),
            row.get('piezas_aceptadas', 0),
            row.get('piezas_rechazadas', 0),
            row.get('porcentaje_aceptadas', 0),
            row.get('costo_total', 0),
            row.get('costo_total_final', 0),
            row.get('costo_piezas_rechazadas', 0),
            diferencia,
            'Sí' if row.get('tiene_venta_mostrador', False) else 'No',
        ]
        for col, valor in enumerate(datos, 1):
            cell = ws4.cell(row=fila, column=col, value=valor)
            cell.border = border_thin
            if col in (10, 11, 12, 13):
                cell.number_format = number_fmt
    
    # Resumen
    if len(df_parcial) > 0:
        fila += 2
        ws4.cell(row=fila, column=1, value='RESUMEN DE ACEPTACIÓN PARCIAL').font = Font(bold=True, size=12)
        ws4.cell(row=fila, column=1).fill = yellow_fill
        fila += 1
        valor_perdido = df_parcial['costo_piezas_rechazadas'].sum()
        ws4.cell(row=fila, column=1, value='Valor perdido por piezas rechazadas en parciales:').font = kpi_label_font
        cell_vp = ws4.cell(row=fila, column=2, value=float(valor_perdido))
        cell_vp.number_format = number_fmt
        cell_vp.font = Font(bold=True, color='c0392c', size=12)
        fila += 1
        prom_aceptacion = df_parcial['porcentaje_aceptadas'].mean()
        ws4.cell(row=fila, column=1, value='% promedio de aceptación en parciales:').font = kpi_label_font
        ws4.cell(row=fila, column=2, value=f"{prom_aceptacion:.1f}%")
    
    auto_ajustar_columnas(ws4)
    
    # ========================================================================
    # HOJA 5: VENTAS MOSTRADOR ASOCIADAS
    # ========================================================================
    ws5 = wb.create_sheet('Ventas Mostrador')
    
    df_con_vm = df_aceptadas[df_aceptadas['tiene_venta_mostrador'] == True]
    
    ws5.merge_cells('A1:R1')
    ws5['A1'] = f'VENTAS MOSTRADOR EN COTIZACIONES ACEPTADAS ({len(df_con_vm)} registros)'
    ws5['A1'].font = title_font
    ws5['A1'].fill = PatternFill(start_color='0dcaf0', end_color='0dcaf0', fill_type='solid')
    ws5['A1'].alignment = title_align
    
    headers_vm = [
        'Orden Cliente', 'Folio VM', 'Fecha Venta', 'Sucursal', 'Técnico',
        'Paquete', 'Costo Paquete',
        'Limpieza', 'Costo Limpieza',
        'Reinstalación SO', 'Costo Reinstalación',
        'Respaldo', 'Costo Respaldo',
        'Cambio Pieza', 'Costo Cambio',
        'Kit Limpieza', 'Costo Kit',
        'Total VM',
    ]
    
    fila = 3
    for col, h in enumerate(headers_vm, 1):
        ws5.cell(row=fila, column=col, value=h)
    # Usar fill azul info para headers de VM
    vm_header_fill = PatternFill(start_color='0dcaf0', end_color='0dcaf0', fill_type='solid')
    for col in range(1, len(headers_vm) + 1):
        cell = ws5.cell(row=fila, column=col)
        cell.font = Font(bold=True, color='000000', size=11)
        cell.fill = vm_header_fill
        cell.alignment = header_align
        cell.border = border_thin
    
    for _, row in df_con_vm.iterrows():
        fila += 1
        
        # Convertir fecha de venta a string para evitar error de openpyxl con timezones
        vm_fecha_venta_str = ''
        if pd.notna(row.get('vm_fecha_venta')):
            try:
                vm_fecha_venta_str = pd.to_datetime(row['vm_fecha_venta']).strftime('%d/%m/%Y')
            except Exception:
                vm_fecha_venta_str = str(row['vm_fecha_venta'])
        
        datos = [
            row.get('orden_cliente', ''),
            row.get('vm_folio', ''),
            vm_fecha_venta_str,
            row.get('sucursal', ''),
            row.get('tecnico', ''),
            row.get('vm_paquete', 'ninguno').capitalize(),
            row.get('vm_costo_paquete', 0),
            'Sí' if row.get('vm_incluye_limpieza', False) else 'No',
            row.get('vm_costo_limpieza', 0),
            'Sí' if row.get('vm_incluye_reinstalacion', False) else 'No',
            row.get('vm_costo_reinstalacion', 0),
            'Sí' if row.get('vm_incluye_respaldo', False) else 'No',
            row.get('vm_costo_respaldo', 0),
            'Sí' if row.get('vm_incluye_cambio_pieza', False) else 'No',
            row.get('vm_costo_cambio_pieza', 0),
            'Sí' if row.get('vm_incluye_kit_limpieza', False) else 'No',
            row.get('vm_costo_kit', 0),
            row.get('vm_total_venta', 0),
        ]
        for col, valor in enumerate(datos, 1):
            cell = ws5.cell(row=fila, column=col, value=valor)
            cell.border = border_thin
            if col in (7, 9, 11, 13, 15, 17, 18):
                cell.number_format = number_fmt
            # Colorear servicios activos
            if col in (8, 10, 12, 14, 16) and valor == 'Sí':
                cell.fill = teal_fill
    
    # Totales
    if len(df_con_vm) > 0:
        fila += 1
        ws5.cell(row=fila, column=1, value='TOTALES').font = Font(bold=True, size=12)
        ws5.cell(row=fila, column=7, value=float(df_con_vm['vm_costo_paquete'].sum())).number_format = number_fmt
        ws5.cell(row=fila, column=9, value=float(df_con_vm['vm_costo_limpieza'].sum())).number_format = number_fmt
        ws5.cell(row=fila, column=11, value=float(df_con_vm['vm_costo_reinstalacion'].sum())).number_format = number_fmt
        ws5.cell(row=fila, column=13, value=float(df_con_vm['vm_costo_respaldo'].sum())).number_format = number_fmt
        ws5.cell(row=fila, column=15, value=float(df_con_vm['vm_costo_cambio_pieza'].sum())).number_format = number_fmt
        ws5.cell(row=fila, column=17, value=float(df_con_vm['vm_costo_kit'].sum())).number_format = number_fmt
        ws5.cell(row=fila, column=18, value=float(df_con_vm['vm_total_venta'].sum())).number_format = number_fmt
        for col in range(1, len(headers_vm) + 1):
            ws5.cell(row=fila, column=col).font = Font(bold=True)
            ws5.cell(row=fila, column=col).border = border_thin
    
    auto_ajustar_columnas(ws5)
    
    # ========================================================================
    # HOJA 6: SERVICIOS ADICIONALES
    # ========================================================================
    ws6 = wb.create_sheet('Servicios Adicionales')
    
    ws6.merge_cells('A1:H1')
    ws6['A1'] = 'ANÁLISIS DE SERVICIOS ADICIONALES — VM EN ACEPTADAS vs. VM PERÍODO COMPLETO'
    ws6['A1'].font = title_font
    ws6['A1'].fill = title_fill
    ws6['A1'].alignment = title_align

    # Leyenda de columnas (fila 2)
    ws6.merge_cells('A2:H2')
    ws6['A2'] = (
        'En Aceptadas = VM cuya cotización fue aceptada  |  '
        'VM Período = Todas las VM del período (incluye órdenes FL sin cotización)  |  '
        'VM Únicas FL = Diferencia (ventas directas sin cotización previa)'
    )
    ws6['A2'].font = Font(italic=True, size=9, color='444444')
    ws6['A2'].fill = PatternFill(start_color='f0f4f8', end_color='f0f4f8', fill_type='solid')

    fila = 4
    if analisis_vm.get('tiene_datos'):
        orange_fill_light = PatternFill(start_color='fff3e0', end_color='fff3e0', fill_type='solid')

        # ----------------------------------------------------------------
        # SECCIÓN 1: Distribución de paquetes
        # ----------------------------------------------------------------
        ws6.merge_cells(f'A{fila}:H{fila}')
        ws6.cell(row=fila, column=1, value='DISTRIBUCIÓN DE PAQUETES').font = Font(bold=True, size=12)
        ws6.cell(row=fila, column=1).fill = blue_fill
        fila += 1
        headers_paq = [
            'Paquete',
            'En Aceptadas', '% Aceptadas', 'Ingreso (Aceptadas)',
            'VM Período', '% VM Período', 'Ingreso (VM Período)',
            'VM Únicas FL',
        ]
        for col, h in enumerate(headers_paq, 1):
            ws6.cell(row=fila, column=col, value=h)
        aplicar_estilos_header(ws6, fila, len(headers_paq))

        for paq in analisis_vm['distribucion_paquetes']:
            fila += 1
            ws6.cell(row=fila, column=1, value=paq['nombre']).border = border_thin
            ws6.cell(row=fila, column=2, value=paq['cantidad']).border = border_thin
            ws6.cell(row=fila, column=3, value=f"{paq['porcentaje']}%").border = border_thin
            cell_ia = ws6.cell(row=fila, column=4, value=paq['ingreso_total'])
            cell_ia.number_format = number_fmt
            cell_ia.border = border_thin
            ws6.cell(row=fila, column=5, value=paq['cantidad_vm_periodo']).border = border_thin
            ws6.cell(row=fila, column=6, value=f"{paq['porcentaje_vm_periodo']}%").border = border_thin
            cell_ir = ws6.cell(row=fila, column=7, value=paq['ingreso_vm_periodo'])
            cell_ir.number_format = number_fmt
            cell_ir.border = border_thin
            dif = paq['cantidad_vm_unicas']
            cell_dif = ws6.cell(row=fila, column=8, value=dif)
            cell_dif.border = border_thin
            if dif > 0:
                cell_dif.fill = orange_fill_light
                cell_dif.font = Font(bold=True, color='e65100')

        # ----------------------------------------------------------------
        # SECCIÓN 2: Distribución de servicios individuales
        # ----------------------------------------------------------------
        fila += 2
        ws6.merge_cells(f'A{fila}:H{fila}')
        ws6.cell(row=fila, column=1, value='DISTRIBUCIÓN DE SERVICIOS INDIVIDUALES').font = Font(bold=True, size=12)
        ws6.cell(row=fila, column=1).fill = teal_fill
        fila += 1
        headers_srv = [
            'Servicio',
            'En Aceptadas', '% En Aceptadas', 'Ingreso (Aceptadas)',
            'VM Período', '% VM Período', 'Ingreso (VM Período)',
            'VM Únicas FL',
        ]
        for col, h in enumerate(headers_srv, 1):
            ws6.cell(row=fila, column=col, value=h)
        aplicar_estilos_header(ws6, fila, len(headers_srv))

        for srv in analisis_vm['distribucion_servicios']:
            fila += 1
            ws6.cell(row=fila, column=1, value=srv['servicio']).border = border_thin
            ws6.cell(row=fila, column=2, value=srv['cantidad']).border = border_thin
            ws6.cell(row=fila, column=3, value=f"{srv['porcentaje']}%").border = border_thin
            cell_ia = ws6.cell(row=fila, column=4, value=srv['ingreso_total'])
            cell_ia.number_format = number_fmt
            cell_ia.border = border_thin
            ws6.cell(row=fila, column=5, value=srv['cantidad_vm_periodo']).border = border_thin
            ws6.cell(row=fila, column=6, value=f"{srv['porcentaje_vm_periodo']}%").border = border_thin
            cell_ir = ws6.cell(row=fila, column=7, value=srv['ingreso_vm_periodo'])
            cell_ir.number_format = number_fmt
            cell_ir.border = border_thin
            dif = srv['cantidad_vm_unicas']
            cell_dif = ws6.cell(row=fila, column=8, value=dif)
            cell_dif.border = border_thin
            if dif > 0:
                cell_dif.fill = orange_fill_light
                cell_dif.font = Font(bold=True, color='e65100')

        # ----------------------------------------------------------------
        # SECCIÓN 3: Combinaciones — tabla unificada (Aceptadas + FL)
        # ----------------------------------------------------------------
        fila += 2
        ws6.merge_cells(f'A{fila}:H{fila}')
        ws6.cell(row=fila, column=1,
                 value='COMBINACIONES DE SERVICIOS MÁS FRECUENTES').font = Font(bold=True, size=12)
        ws6.cell(row=fila, column=1).fill = purple_fill
        fila += 1
        # Nota
        ws6.merge_cells(f'A{fila}:H{fila}')
        ws6.cell(row=fila, column=1,
                 value='Incluye cotizaciones aceptadas + órdenes FL (ventas directas). '
                       'Origen "Solo FL" = combinación exclusiva de órdenes sin cotización.')
        ws6.cell(row=fila, column=1).font = Font(italic=True, size=9, color='666666')
        fila += 1
        headers_combo = [
            'Combinación', 'Origen',
            'VM Período', '% VM Período',
            'En Aceptadas', '% En Aceptadas',
            'VM Únicas FL',
        ]
        for col, h in enumerate(headers_combo, 1):
            ws6.cell(row=fila, column=col, value=h)
        aplicar_estilos_header(ws6, fila, len(headers_combo))

        fl_fill = PatternFill(start_color='ede9fe', end_color='ede9fe', fill_type='solid')
        fl_font_bold = Font(bold=True, color='5b21b6')
        for combo_t in analisis_vm.get('combinaciones_frecuentes_total', []):
            fila += 1
            es_fl = combo_t.get('exclusivo_fl', False)
            cant_acept = combo_t['cantidad_aceptadas']
            cant_total = combo_t['cantidad_total']
            cant_unicas = cant_total - cant_acept

            # Columna 1: Combinación
            cell_c = ws6.cell(row=fila, column=1, value=combo_t['combinacion'])
            cell_c.border = border_thin
            if es_fl:
                cell_c.fill = fl_fill
                cell_c.font = fl_font_bold

            # Columna 2: Origen
            origen_val = 'Solo FL' if es_fl else 'Aceptadas + FL' if cant_unicas > 0 else 'En Aceptadas'
            cell_o = ws6.cell(row=fila, column=2, value=origen_val)
            cell_o.border = border_thin
            if es_fl:
                cell_o.fill = fl_fill
                cell_o.font = fl_font_bold

            # Columna 3–4: VM Período
            cell_vp = ws6.cell(row=fila, column=3, value=cant_total)
            cell_vp.border = border_thin
            if es_fl:
                cell_vp.fill = fl_fill
            ws6.cell(row=fila, column=4,
                     value=f"{combo_t['porcentaje_total']}%").border = border_thin

            # Columna 5–6: En Aceptadas
            cell_a = ws6.cell(row=fila, column=5,
                              value=cant_acept if cant_acept > 0 else '—')
            cell_a.border = border_thin
            ws6.cell(row=fila, column=6,
                     value=f"{combo_t['porcentaje_aceptadas']}%" if cant_acept > 0 else '—').border = border_thin

            # Columna 7: VM Únicas FL
            cell_u = ws6.cell(row=fila, column=7,
                              value=cant_unicas if cant_unicas > 0 else '—')
            cell_u.border = border_thin
            if cant_unicas > 0:
                cell_u.fill = orange_fill_light
                cell_u.font = Font(bold=True, color='e65100')
        
        # Top piezas VM
        if analisis_vm.get('top_piezas_vm'):
            fila += 2
            ws6.merge_cells(f'A{fila}:H{fila}')
            ws6.cell(row=fila, column=1, value='TOP PIEZAS VENDIDAS EN VENTA MOSTRADOR').font = Font(bold=True, size=12)
            ws6.cell(row=fila, column=1).fill = blue_fill
            fila += 1
            headers_tpvm = ['Pieza', 'Cantidad', 'Ingreso Total', 'Núm. Ventas']
            for col, h in enumerate(headers_tpvm, 1):
                ws6.cell(row=fila, column=col, value=h)
            aplicar_estilos_header(ws6, fila, len(headers_tpvm))
            
            for pieza in analisis_vm['top_piezas_vm']:
                fila += 1
                ws6.cell(row=fila, column=1, value=pieza['descripcion']).border = border_thin
                ws6.cell(row=fila, column=2, value=pieza['cantidad']).border = border_thin
                cell_i = ws6.cell(row=fila, column=3, value=pieza['ingreso_total'])
                cell_i.number_format = number_fmt
                cell_i.border = border_thin
                ws6.cell(row=fila, column=4, value=pieza['num_ventas']).border = border_thin
    else:
        ws6.cell(row=fila, column=1, value='No hay ventas mostrador asociadas a cotizaciones aceptadas')
        ws6.cell(row=fila, column=1).font = Font(italic=True, color='999999', size=12)
    
    auto_ajustar_columnas(ws6)
    
    # ========================================================================
    # HOJA 7: SEGUIMIENTO DE PIEZAS
    # ========================================================================
    ws7 = wb.create_sheet('Seguimiento Piezas')
    
    ws7.merge_cells('A1:H1')
    ws7['A1'] = 'SEGUIMIENTO DE PIEZAS POST-ACEPTACIÓN'
    ws7['A1'].font = title_font
    ws7['A1'].fill = title_fill
    ws7['A1'].alignment = title_align
    
    fila = 3
    if analisis_seguimiento.get('tiene_datos'):
        # Distribución de estados
        ws7.cell(row=fila, column=1, value='DISTRIBUCIÓN DE ESTADOS').font = Font(bold=True, size=12)
        ws7.cell(row=fila, column=1).fill = green_fill
        fila += 1
        headers_est = ['Estado', 'Cantidad', 'Porcentaje', 'Tipo']
        for col, h in enumerate(headers_est, 1):
            ws7.cell(row=fila, column=col, value=h)
        aplicar_estilos_header(ws7, fila, len(headers_est))
        
        for est in analisis_seguimiento['distribucion_estados']:
            fila += 1
            ws7.cell(row=fila, column=1, value=est['label']).border = border_thin
            ws7.cell(row=fila, column=2, value=est['cantidad']).border = border_thin
            ws7.cell(row=fila, column=3, value=f"{est['porcentaje']}%").border = border_thin
            tipo = 'Problemático' if est['es_problematico'] else ('Recibido' if est['es_recibido'] else 'En proceso')
            cell_tipo = ws7.cell(row=fila, column=4, value=tipo)
            cell_tipo.border = border_thin
            if est['es_problematico']:
                cell_tipo.fill = PatternFill(start_color='f8d7da', end_color='f8d7da', fill_type='solid')
            elif est['es_recibido']:
                cell_tipo.fill = green_fill
            else:
                cell_tipo.fill = yellow_fill
        
        # Tiempos de entrega
        tiempos = analisis_seguimiento.get('tiempos_entrega', {})
        if tiempos.get('total_con_fecha', 0) > 0:
            fila += 2
            ws7.cell(row=fila, column=1, value='TIEMPOS DE ENTREGA').font = Font(bold=True, size=12)
            ws7.cell(row=fila, column=1).fill = blue_fill
            fila += 1
            metricas_tiempo = [
                ('Promedio (días)', tiempos.get('promedio', 0)),
                ('Mediana (días)', tiempos.get('mediana', 0)),
                ('Mínimo (días)', tiempos.get('minimo', 0)),
                ('Máximo (días)', tiempos.get('maximo', 0)),
                ('Con fecha de entrega', tiempos.get('total_con_fecha', 0)),
                ('Sin fecha aún', tiempos.get('total_sin_fecha', 0)),
                ('Tasa de cumplimiento', f"{analisis_seguimiento.get('tasa_cumplimiento', 0)}%"),
            ]
            for label, valor in metricas_tiempo:
                fila += 1
                ws7.cell(row=fila, column=1, value=label).font = kpi_label_font
                ws7.cell(row=fila, column=1).border = border_thin
                ws7.cell(row=fila, column=2, value=valor).border = border_thin
        
        # Ranking de proveedores
        proveedores = analisis_seguimiento.get('proveedores_ranking', [])
        if proveedores:
            fila += 2
            ws7.cell(row=fila, column=1, value='RANKING DE PROVEEDORES').font = Font(bold=True, size=12)
            ws7.cell(row=fila, column=1).fill = teal_fill
            fila += 1
            headers_prov = ['Proveedor', 'Total Pedidos', 'Recibidos', 'Problemas', 'Tasa Éxito', 'Tiempo Prom.']
            for col, h in enumerate(headers_prov, 1):
                ws7.cell(row=fila, column=col, value=h)
            aplicar_estilos_header(ws7, fila, len(headers_prov))
            
            for prov in proveedores:
                fila += 1
                ws7.cell(row=fila, column=1, value=prov['proveedor']).border = border_thin
                ws7.cell(row=fila, column=2, value=prov['total_pedidos']).border = border_thin
                ws7.cell(row=fila, column=3, value=prov['recibidos']).border = border_thin
                ws7.cell(row=fila, column=4, value=prov['problemas']).border = border_thin
                cell_tasa = ws7.cell(row=fila, column=5, value=f"{prov['tasa_exito']}%")
                cell_tasa.border = border_thin
                if prov['tasa_exito'] >= 90:
                    cell_tasa.fill = green_fill
                elif prov['tasa_exito'] < 70:
                    cell_tasa.fill = PatternFill(start_color='f8d7da', end_color='f8d7da', fill_type='solid')
                tiempo_str = f"{prov['tiempo_promedio']} días" if prov['tiempo_promedio'] else 'Sin datos'
                ws7.cell(row=fila, column=6, value=tiempo_str).border = border_thin
        
        # Problemas
        problemas = analisis_seguimiento.get('problemas_piezas', {})
        if problemas.get('total_problemas', 0) > 0:
            fila += 2
            ws7.cell(row=fila, column=1, value='PROBLEMAS EN PIEZAS').font = Font(bold=True, size=12)
            ws7.cell(row=fila, column=1).fill = PatternFill(start_color='f8d7da', end_color='f8d7da', fill_type='solid')
            fila += 1
            ws7.cell(row=fila, column=1, value='Piezas incorrectas (WPB):').font = kpi_label_font
            ws7.cell(row=fila, column=2, value=problemas.get('piezas_incorrectas', 0))
            fila += 1
            ws7.cell(row=fila, column=1, value='Piezas dañadas (DOA):').font = kpi_label_font
            ws7.cell(row=fila, column=2, value=problemas.get('piezas_danadas', 0))
            fila += 1
            ws7.cell(row=fila, column=1, value='Tasa de problemas:').font = kpi_label_font
            ws7.cell(row=fila, column=2, value=f"{problemas.get('tasa_problemas', 0)}%")
    else:
        ws7.cell(row=fila, column=1, value='No hay seguimientos de piezas en las cotizaciones aceptadas')
        ws7.cell(row=fila, column=1).font = Font(italic=True, color='999999', size=12)
    
    auto_ajustar_columnas(ws7)
    
    # ========================================================================
    # HOJA 8: RENDIMIENTO POR TÉCNICO
    # ========================================================================
    ws8 = wb.create_sheet('Por Técnico')
    
    ws8.merge_cells('A1:K1')
    ws8['A1'] = 'RENDIMIENTO DE ACEPTACIONES POR TÉCNICO'
    ws8['A1'].font = title_font
    ws8['A1'].fill = title_fill
    ws8['A1'].alignment = title_align
    
    # Calcular métricas por técnico
    tec_metrics = df_aceptadas.groupby('tecnico').agg(
        total_aceptadas=('aceptada', 'count'),
        valor_aceptado=('costo_total_final', 'sum'),
        ticket_promedio=('costo_total_final', 'mean'),
        piezas_promedio=('piezas_aceptadas', 'mean'),
        con_vm=('tiene_venta_mostrador', 'sum'),
        valor_vm=('vm_total_venta', 'sum'),
        valor_combinado=('valor_total_combinado', 'sum'),
        con_descuento=('descontar_mano_obra', 'sum'),
        tiempo_resp=('dias_sin_respuesta', 'mean'),
    ).reset_index()
    tec_metrics['tasa_upsell'] = (tec_metrics['con_vm'] / tec_metrics['total_aceptadas'] * 100).round(1)
    tec_metrics = tec_metrics.sort_values('valor_combinado', ascending=False)
    
    headers_tec = [
        'Técnico', 'Aceptadas', 'Valor Aceptado', 'Ticket Promedio',
        'Piezas Prom.', 'Con VM', 'Tasa Upsell (%)', 'Valor VM',
        'Valor Combinado', 'Con Descuento MO', 'Tiempo Resp. Prom.',
    ]
    
    fila = 3
    for col, h in enumerate(headers_tec, 1):
        ws8.cell(row=fila, column=col, value=h)
    aplicar_estilos_header(ws8, fila, len(headers_tec))
    
    for _, row in tec_metrics.iterrows():
        fila += 1
        datos = [
            row['tecnico'],
            int(row['total_aceptadas']),
            round(row['valor_aceptado'], 2),
            round(row['ticket_promedio'], 2),
            round(row['piezas_promedio'], 1),
            int(row['con_vm']),
            row['tasa_upsell'],
            round(row['valor_vm'], 2),
            round(row['valor_combinado'], 2),
            int(row['con_descuento']),
            round(row['tiempo_resp'], 1) if not pd.isna(row['tiempo_resp']) else 0,
        ]
        for col, valor in enumerate(datos, 1):
            cell = ws8.cell(row=fila, column=col, value=valor)
            cell.border = border_thin
            if col in (3, 4, 8, 9):
                cell.number_format = number_fmt
    
    auto_ajustar_columnas(ws8)
    
    # ========================================================================
    # HOJA 9: RENDIMIENTO POR SUCURSAL
    # ========================================================================
    ws9 = wb.create_sheet('Por Sucursal')
    
    ws9.merge_cells('A1:K1')
    ws9['A1'] = 'RENDIMIENTO DE ACEPTACIONES POR SUCURSAL'
    ws9['A1'].font = title_font
    ws9['A1'].fill = title_fill
    ws9['A1'].alignment = title_align
    
    # Calcular métricas por sucursal
    suc_metrics = df_aceptadas.groupby('sucursal').agg(
        total_aceptadas=('aceptada', 'count'),
        valor_aceptado=('costo_total_final', 'sum'),
        ticket_promedio=('costo_total_final', 'mean'),
        piezas_promedio=('piezas_aceptadas', 'mean'),
        con_vm=('tiene_venta_mostrador', 'sum'),
        valor_vm=('vm_total_venta', 'sum'),
        valor_combinado=('valor_total_combinado', 'sum'),
        con_descuento=('descontar_mano_obra', 'sum'),
        tiempo_resp=('dias_sin_respuesta', 'mean'),
    ).reset_index()
    suc_metrics['tasa_upsell'] = (suc_metrics['con_vm'] / suc_metrics['total_aceptadas'] * 100).round(1)
    suc_metrics = suc_metrics.sort_values('valor_combinado', ascending=False)
    
    # Agregar tasa de aceptación global por sucursal
    tasa_por_suc = df_cotizaciones.groupby('sucursal').agg(
        total_cotizaciones=('aceptada', 'count'),
        total_aceptadas_global=('aceptada', lambda x: (x == True).sum()),
    ).reset_index()
    tasa_por_suc['tasa_aceptacion'] = (tasa_por_suc['total_aceptadas_global'] / tasa_por_suc['total_cotizaciones'] * 100).round(1)
    suc_metrics = suc_metrics.merge(tasa_por_suc[['sucursal', 'tasa_aceptacion', 'total_cotizaciones']], on='sucursal', how='left')
    
    headers_suc = [
        'Sucursal', 'Total Cotizaciones', 'Aceptadas', 'Tasa Aceptación (%)',
        'Valor Aceptado', 'Ticket Promedio',
        'Con VM', 'Tasa Upsell (%)', 'Valor VM',
        'Valor Combinado', 'Tiempo Resp. Prom.',
    ]
    
    fila = 3
    for col, h in enumerate(headers_suc, 1):
        ws9.cell(row=fila, column=col, value=h)
    aplicar_estilos_header(ws9, fila, len(headers_suc))
    
    for _, row in suc_metrics.iterrows():
        fila += 1
        datos = [
            row['sucursal'],
            int(row.get('total_cotizaciones', 0)),
            int(row['total_aceptadas']),
            row.get('tasa_aceptacion', 0),
            round(row['valor_aceptado'], 2),
            round(row['ticket_promedio'], 2),
            int(row['con_vm']),
            row['tasa_upsell'],
            round(row['valor_vm'], 2),
            round(row['valor_combinado'], 2),
            round(row['tiempo_resp'], 1) if not pd.isna(row['tiempo_resp']) else 0,
        ]
        for col, valor in enumerate(datos, 1):
            cell = ws9.cell(row=fila, column=col, value=valor)
            cell.border = border_thin
            if col in (5, 6, 9, 10):
                cell.number_format = number_fmt
            # Colorear tasa de aceptación
            if col == 4:
                if valor >= 60:
                    cell.fill = green_fill
                elif valor < 40:
                    cell.fill = PatternFill(start_color='f8d7da', end_color='f8d7da', fill_type='solid')
                else:
                    cell.fill = yellow_fill
    
    auto_ajustar_columnas(ws9)
    
    # ========================================
    # GUARDAR Y RETORNAR RESPUESTA
    # ========================================
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nombre_archivo = f'Analisis_Aceptaciones_{timestamp}.xlsx'
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    
    wb.save(response)
    
    return response

# ============================================================================
# APIs DE BÚSQUEDA: viven en views_apis_busqueda.py (reexport al inicio).
# ============================================================================

# ============================================================================
# DASHBOARD DE SEGUIMIENTO DE PIEZAS EN TRÁNSITO
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def dashboard_seguimiento_piezas(request):
    """
    Dashboard dedicado para seguimiento de piezas en tránsito.

    """
    from datetime import datetime, timedelta, date
    import pandas as pd
    from .utils_cotizaciones import (
        obtener_dataframe_seguimientos_piezas,
        calcular_kpis_seguimientos_piezas
    )
    from .plotly_visualizations import DashboardCotizacionesVisualizer, convertir_figura_a_html
    import plotly.graph_objects as go
    import plotly.express as px
    
    # ========================================
    # 1. OBTENER Y VALIDAR FILTROS
    # ========================================
    
    # Fechas por defecto: últimos 6 meses (mayor ventana para seguimientos)
    fecha_fin_default = datetime.now().date()
    fecha_inicio_default = (datetime.now() - timedelta(days=180)).date()
    
    # Capturar parámetros GET
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    sucursal_id = request.GET.get('sucursal')
    proveedor_filtro = request.GET.get('proveedor')
    estado_filtro = request.GET.get('estado')
    busqueda = request.GET.get('busqueda', '').strip()
    
    # Validar y parsear fechas
    try:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date() if fecha_inicio_str else fecha_inicio_default
    except ValueError:
        fecha_inicio = fecha_inicio_default
    
    try:
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date() if fecha_fin_str else fecha_fin_default
    except ValueError:
        fecha_fin = fecha_fin_default
    
    # Convertir sucursal_id a entero
    try:
        sucursal_id = int(sucursal_id) if sucursal_id else None
    except (ValueError, TypeError):
        sucursal_id = None
    
    # ========================================
    # 2. OBTENER DATOS CON FILTROS
    # ========================================
    
    try:
        # Obtener DataFrame de seguimientos
        df_seguimientos = obtener_dataframe_seguimientos_piezas(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            sucursal_id=sucursal_id,
            proveedor=proveedor_filtro,
            estado=estado_filtro
        )
        
        # Aplicar búsqueda libre si existe
        if busqueda and not df_seguimientos.empty:
            df_seguimientos = df_seguimientos[
                df_seguimientos['orden_numero'].str.contains(busqueda, case=False, na=False) |
                df_seguimientos['proveedor'].str.contains(busqueda, case=False, na=False) |
                df_seguimientos['descripcion_piezas'].str.contains(busqueda, case=False, na=False) |
                df_seguimientos['numero_pedido'].str.contains(busqueda, case=False, na=False)
            ]
        
        # Calcular KPIs
        kpis = calcular_kpis_seguimientos_piezas(df_seguimientos)
        
    except Exception as e:
        # Si hay error, crear DataFrames vacíos
        print(f"Error al obtener datos: {e}")
        df_seguimientos = pd.DataFrame()
        kpis = calcular_kpis_seguimientos_piezas(df_seguimientos)
    
    # ========================================
    # 3. GENERAR GRÁFICOS CON PLOTLY (PYTHON)
    # ========================================
    
    graficos = {}
    
    # Gráfico 1: Distribución por Estado (Pie Chart)
    if not df_seguimientos.empty:
        try:
            estado_counts = df_seguimientos['estado_display'].value_counts()
            fig_estados = px.pie(
                values=estado_counts.values,
                names=estado_counts.index,
                title='Distribución de Seguimientos por Estado',
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_estados.update_traces(textposition='inside', textinfo='percent+label')
            fig_estados.update_layout(
                height=400,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='#1e293b',
                font=dict(color='#e2e8f0')
            )
            graficos['distribucion_estados'] = convertir_figura_a_html(fig_estados)
        except Exception as e:
            print(f"Error en gráfico de estados: {e}")
            graficos['distribucion_estados'] = None
    
    # Gráfico 2: Top Proveedores por Volumen (Bar Chart Horizontal)
    if not df_seguimientos.empty:
        try:
            top_proveedores = df_seguimientos['proveedor'].value_counts().head(10)
            fig_proveedores = go.Figure(data=[
                go.Bar(
                    y=top_proveedores.index,
                    x=top_proveedores.values,
                    orientation='h',
                    marker=dict(
                        color=top_proveedores.values,
                        colorscale='Viridis',
                        showscale=True
                    ),
                    text=top_proveedores.values,
                    textposition='auto',
                )
            ])
            fig_proveedores.update_layout(
                title='Top 10 Proveedores por Número de Pedidos',
                xaxis_title='Número de Pedidos',
                yaxis_title='Proveedor',
                height=500,
                showlegend=False,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='#1e293b',
                font=dict(color='#e2e8f0')
            )
            graficos['top_proveedores'] = convertir_figura_a_html(fig_proveedores)
        except Exception as e:
            print(f"Error en gráfico de proveedores: {e}")
            graficos['top_proveedores'] = None
    
    # Gráfico 3: Tiempos de Entrega por Proveedor (Box Plot)
    if not df_seguimientos.empty:
        try:
            # Filtrar solo piezas recibidas para análisis de tiempos
            df_recibidos = df_seguimientos[df_seguimientos['estado'] == 'recibido']
            if not df_recibidos.empty and len(df_recibidos['proveedor'].unique()) > 1:
                # Tomar top 8 proveedores por volumen
                top_prov = df_recibidos['proveedor'].value_counts().head(8).index
                df_recibidos_top = df_recibidos[df_recibidos['proveedor'].isin(top_prov)]
                
                fig_tiempos = px.box(
                    df_recibidos_top,
                    x='proveedor',
                    y='dias_desde_pedido',
                    title='Tiempos de Entrega por Proveedor (Días)',
                    color='proveedor',
                    labels={'dias_desde_pedido': 'Días desde Pedido', 'proveedor': 'Proveedor'}
                )
                fig_tiempos.update_layout(
                    height=450,
                    showlegend=False,
                    xaxis_tickangle=-45,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='#1e293b',
                    font=dict(color='#e2e8f0')
                )
                graficos['tiempos_entrega_proveedor'] = convertir_figura_a_html(fig_tiempos)
            else:
                graficos['tiempos_entrega_proveedor'] = None
        except Exception as e:
            print(f"Error en gráfico de tiempos: {e}")
            graficos['tiempos_entrega_proveedor'] = None
    
    # Gráfico 4: Timeline de Entregas Esperadas (Gantt-like)
    if not df_seguimientos.empty:
        try:
            # Filtrar solo activos con fecha estimada futura
            # ACTUALIZADO: Usar constantes para estados pendientes
            df_activos = df_seguimientos[
                (df_seguimientos['estado'].isin(ESTADOS_PIEZA_PENDIENTES)) &
                (df_seguimientos['dias_hasta_entrega'] >= -30)  # Incluir hasta 30 días de retraso
            ].copy()
            
            if not df_activos.empty:
                # Convertir columnas de fecha a datetime si son date objects
                df_activos['fecha_pedido'] = pd.to_datetime(df_activos['fecha_pedido'])
                df_activos['fecha_entrega_estimada'] = pd.to_datetime(df_activos['fecha_entrega_estimada'])
                
                # Ordenar por fecha estimada
                df_activos = df_activos.sort_values('fecha_entrega_estimada')
                
                # Tomar máximo 20 para no saturar el gráfico
                df_activos = df_activos.head(20)
                
                # Crear etiquetas descriptivas con orden_cliente y service_tag
                df_activos['etiqueta'] = df_activos.apply(
                    lambda row: f"{row['orden_cliente']} ({row['service_tag'][:15]}) - {row['proveedor'][:20]}", axis=1
                )
                
                # Asignar colores según prioridad
                color_map = {
                    'critico': 'red',
                    'alto': 'orange',
                    'medio': 'yellow',
                    'normal': 'green'
                }
                df_activos['color'] = df_activos['prioridad'].map(color_map)
                
                fig_timeline = go.Figure()
                
                for idx, row in df_activos.iterrows():
                    fig_timeline.add_trace(go.Scatter(
                        x=[row['fecha_pedido'], row['fecha_entrega_estimada']],
                        y=[row['etiqueta'], row['etiqueta']],
                        mode='lines+markers',
                        line=dict(color=row['color'], width=8),
                        marker=dict(size=10, symbol='circle'),
                        name=row['etiqueta'],
                        showlegend=False,
                        hovertemplate=(
                            f"<b>{row['etiqueta']}</b><br>" +
                            f"Pedido: {row['fecha_pedido']}<br>" +
                            f"Estimado: {row['fecha_entrega_estimada']}<br>" +
                            f"Días restantes: {row['dias_hasta_entrega']}<br>" +
                            f"Estado: {row['estado_display']}<br>" +
                            "<extra></extra>"
                        )
                    ))
                
                # Agregar línea vertical para HOY usando add_shape
                hoy = datetime.now()
                
                fig_timeline.update_layout(
                    title='Timeline de Entregas Esperadas (Próximas 20 Piezas)',
                    xaxis_title='Fecha',
                    yaxis_title='Orden - Proveedor',
                    height=600,
                    hovermode='closest',
                    yaxis=dict(autorange="reversed"),  # Más recientes arriba
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='#1e293b',
                    font=dict(color='#e2e8f0'),
                    shapes=[
                        dict(
                            type="line",
                            x0=hoy,
                            x1=hoy,
                            y0=0,
                            y1=1,
                            yref="paper",
                            line=dict(color="#38bdf8", width=2, dash="dash"),
                        )
                    ],
                    annotations=[
                        dict(
                            x=hoy,
                            y=1,
                            yref="paper",
                            text="HOY",
                            showarrow=False,
                            xanchor="center",
                            yanchor="bottom",
                            font=dict(color="#38bdf8", size=12, family="Arial Black"),
                            bgcolor="rgba(15, 23, 42, 0.8)",
                        )
                    ]
                )
                
                graficos['timeline_entregas'] = convertir_figura_a_html(fig_timeline)
            else:
                graficos['timeline_entregas'] = None
        except Exception as e:
            import traceback
            print(f"Error en gráfico timeline: {e}")
            print(traceback.format_exc())
            graficos['timeline_entregas'] = None
    
    # ========================================
    # 4. PREPARAR DATOS PARA ALERTAS
    # ========================================
    
    # ========================================
    # 4.5 PREPARAR VISTA AGRUPADA POR ORDEN
    # ========================================
    
    # Importar función de agrupación
    from .utils_cotizaciones import agrupar_seguimientos_por_orden
    
    # Generar vista agrupada
    if not df_seguimientos.empty:
        ordenes_agrupadas = agrupar_seguimientos_por_orden(df_seguimientos)
        
        # Separar agrupadas en activas y recibidas
        ordenes_activas = [o for o in ordenes_agrupadas if o['estado_general'] != 'todos_recibidos']
        ordenes_recibidas = [o for o in ordenes_agrupadas if o['estado_general'] == 'todos_recibidos']
        
        # KPIs específicos de la vista agrupada
        kpis_agrupados = {
            'total_ordenes': len(ordenes_agrupadas),
            'ordenes_activas': len(ordenes_activas),
            'ordenes_completadas': len(ordenes_recibidas),
            'ordenes_con_retrasos': len([o for o in ordenes_agrupadas if o['tiene_retrasados']]),
            'ordenes_criticas': len([o for o in ordenes_agrupadas if o['prioridad_maxima'] == 'critico']),
        }
    else:
        ordenes_agrupadas = []
        ordenes_activas = []
        ordenes_recibidas = []
        kpis_agrupados = {
            'total_ordenes': 0,
            'ordenes_activas': 0,
            'ordenes_completadas': 0,
            'ordenes_con_retrasos': 0,
            'ordenes_criticas': 0,
        }
    
    # Filtrar piezas retrasadas para alertas (solo las que NO han llegado)
    # ACTUALIZADO: Usar constantes para estados pendientes
    if not df_seguimientos.empty:
        df_retrasados = df_seguimientos[
            (df_seguimientos['esta_retrasado'] == True) &
            (df_seguimientos['estado'].isin(ESTADOS_PIEZA_PENDIENTES))  # Solo activas, no recibidas
        ]
        piezas_retrasadas = df_retrasados.to_dict('records')
    else:
        piezas_retrasadas = []
    
    # Filtrar piezas próximas a llegar (siguientes 3 días)
    # ACTUALIZADO: Usar constantes para estados pendientes
    if not df_seguimientos.empty:
        df_proximos = df_seguimientos[
            (df_seguimientos['dias_hasta_entrega'] >= 0) &
            (df_seguimientos['dias_hasta_entrega'] <= 3) &
            (df_seguimientos['estado'].isin(ESTADOS_PIEZA_PENDIENTES))
        ]
        piezas_proximas = df_proximos.to_dict('records')
    else:
        piezas_proximas = []
    
    # NUEVO: Filtrar piezas con problemas de calidad (WPB/DOA)
    # Estas piezas llegaron físicamente pero con incidencias de calidad
    if not df_seguimientos.empty:
        df_problematicos = df_seguimientos[
            df_seguimientos['estado'].isin(ESTADOS_PIEZA_PROBLEMATICOS)
        ]
        piezas_problematicas = df_problematicos.to_dict('records')
    else:
        piezas_problematicas = []
    
    # ========================================
    # 5. PREPARAR DATOS PARA FILTROS
    # ========================================
    
    # Lista de sucursales para el filtro
    sucursales = Sucursal.objects.all().order_by('nombre')
    
    # Lista de proveedores únicos para el filtro
    if not df_seguimientos.empty:
        proveedores_lista = sorted(df_seguimientos['proveedor'].unique().tolist())
    else:
        proveedores_lista = []
    
    # Estados disponibles - Ya importados al inicio del archivo
    estados_choices = ESTADO_PIEZA_CHOICES
    
    # ========================================
    # 6. PREPARAR CONTEXTO PARA EL TEMPLATE
    # ========================================
    
    context = {
        # KPIs
        'kpis': kpis,
        'kpis_agrupados': kpis_agrupados,
        
        # Alertas
        'piezas_retrasadas': piezas_retrasadas,
        'piezas_proximas': piezas_proximas,
        'piezas_problematicas': piezas_problematicas,  # NUEVO: WPB/DOA
        
        # Datos para la tabla (vista agrupada)
        'ordenes_agrupadas': ordenes_agrupadas,
        'ordenes_activas': ordenes_activas,
        'ordenes_recibidas': ordenes_recibidas,
        
        # Gráficos
        'graficos': graficos,
        
        # Filtros para el formulario
        'sucursales': sucursales,
        'proveedores': proveedores_lista,
        'estados': estados_choices,
        
        # Filtros activos (para mantener valores en el form)
        'filtros_activos': {
            'fecha_inicio': fecha_inicio.strftime('%Y-%m-%d') if fecha_inicio else '',
            'fecha_fin': fecha_fin.strftime('%Y-%m-%d') if fecha_fin else '',
            'sucursal': sucursal_id,
            'proveedor': proveedor_filtro or '',
            'estado': estado_filtro or '',
            'busqueda': busqueda,
        },
        
        # Totales
        'total_ordenes': len(ordenes_agrupadas),
    }
    
    return render(request, 'servicio_tecnico/dashboard_seguimiento_piezas.html', context)


@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def exportar_dashboard_seguimiento_piezas(request):
    """
    Exporta el dashboard de seguimiento de piezas a Excel.

    Returns:
        HttpResponse: Archivo Excel descargable
    """
    from datetime import datetime, timedelta
    import pandas as pd
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils.dataframe import dataframe_to_rows
    from django.http import HttpResponse
    from .utils_cotizaciones import (
        obtener_dataframe_seguimientos_piezas,
        calcular_kpis_seguimientos_piezas
    )
    
    # ========================================
    # 1. OBTENER MISMOS FILTROS QUE EL DASHBOARD
    # ========================================
    
    fecha_fin_default = datetime.now().date()
    fecha_inicio_default = (datetime.now() - timedelta(days=180)).date()
    
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    sucursal_id = request.GET.get('sucursal')
    proveedor_filtro = request.GET.get('proveedor')
    estado_filtro = request.GET.get('estado')
    busqueda = request.GET.get('busqueda', '').strip()
    
    try:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date() if fecha_inicio_str else fecha_inicio_default
    except ValueError:
        fecha_inicio = fecha_inicio_default
    
    try:
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date() if fecha_fin_str else fecha_fin_default
    except ValueError:
        fecha_fin = fecha_fin_default
    
    try:
        sucursal_id = int(sucursal_id) if sucursal_id else None
    except (ValueError, TypeError):
        sucursal_id = None
    
    # ========================================
    # 2. OBTENER DATOS
    # ========================================
    
    try:
        df_seguimientos = obtener_dataframe_seguimientos_piezas(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            sucursal_id=sucursal_id,
            proveedor=proveedor_filtro,
            estado=estado_filtro
        )
        
        if busqueda and not df_seguimientos.empty:
            df_seguimientos = df_seguimientos[
                df_seguimientos['orden_numero'].str.contains(busqueda, case=False, na=False) |
                df_seguimientos['proveedor'].str.contains(busqueda, case=False, na=False) |
                df_seguimientos['descripcion_piezas'].str.contains(busqueda, case=False, na=False) |
                df_seguimientos['numero_pedido'].str.contains(busqueda, case=False, na=False)
            ]
        
        kpis = calcular_kpis_seguimientos_piezas(df_seguimientos)
        
        # Generar vista agrupada (NUEVO)
        from .utils_cotizaciones import agrupar_seguimientos_por_orden
        ordenes_agrupadas = agrupar_seguimientos_por_orden(df_seguimientos) if not df_seguimientos.empty else []
        
    except Exception as e:
        messages.error(request, f'Error al obtener datos para exportación: {str(e)}')
        return redirect('servicio_tecnico:dashboard_seguimiento_piezas')
    
    # ========================================
    # 3. CREAR ARCHIVO EXCEL
    # ========================================
    
    wb = Workbook()
    wb.remove(wb.active)  # Remover hoja por defecto
    
    # Estilos
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # HOJA 1: Resumen de KPIs
    ws_resumen = wb.create_sheet("Resumen")
    ws_resumen.append(["DASHBOARD DE SEGUIMIENTO DE PIEZAS"])
    ws_resumen.append([f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
    ws_resumen.append([])
    ws_resumen.append(["Métrica", "Valor"])
    
    # Escribir KPIs
    kpis_data = [
        ["Total Seguimientos", kpis['total_seguimientos']],
        ["Total Activos", kpis['total_activos']],
        ["En Tránsito", kpis['en_transito']],
        ["Pedidos", kpis['pedidos']],
        ["Recibidos", kpis['recibidos']],
        ["Retrasados", kpis['retrasados']],
        ["Próximos a Llegar (3 días)", kpis['proximos_llegar']],
        ["Promedio Días Entrega", kpis['promedio_dias_entrega']],
        ["Promedio Días Retraso", kpis['promedio_dias_retraso']],
    ]
    
    for row in kpis_data:
        ws_resumen.append(row)
    
    # Aplicar estilos al resumen
    for row in ws_resumen.iter_rows(min_row=4, max_row=4, min_col=1, max_col=2):
        for cell in row:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
    
    # HOJA 2: Todos los Seguimientos
    if not df_seguimientos.empty:
        ws_seguimientos = wb.create_sheet("Seguimientos")
        
        # Seleccionar columnas para Excel
        columnas_excel = [
            'orden_numero', 'proveedor', 'estado_display', 'descripcion_piezas',
            'fecha_pedido', 'fecha_entrega_estimada', 'fecha_entrega_real',
            'dias_desde_pedido', 'dias_retraso', 'dias_hasta_entrega',
            'sucursal', 'responsable', 'numero_pedido'
        ]
        
        df_export = df_seguimientos[columnas_excel].copy()
        
        # Renombrar columnas para Excel
        df_export.columns = [
            'Orden', 'Proveedor', 'Estado', 'Descripción Piezas',
            'Fecha Pedido', 'Fecha Estimada', 'Fecha Real',
            'Días desde Pedido', 'Días Retraso', 'Días hasta Entrega',
            'Sucursal', 'Responsable', 'Nº Pedido'
        ]
        
        # Escribir DataFrame
        for r in dataframe_to_rows(df_export, index=False, header=True):
            ws_seguimientos.append(r)
        
        # Aplicar estilos a encabezados
        for cell in ws_seguimientos[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
    
    # HOJA 3: Solo Retrasados
    if not df_seguimientos.empty:
        df_retrasados = df_seguimientos[df_seguimientos['esta_retrasado'] == True]
        
        if not df_retrasados.empty:
            ws_retrasados = wb.create_sheet("Retrasados")
            
            df_retrasados_export = df_retrasados[columnas_excel].copy()
            df_retrasados_export.columns = df_export.columns
            
            for r in dataframe_to_rows(df_retrasados_export, index=False, header=True):
                ws_retrasados.append(r)
            
            for cell in ws_retrasados[1]:
                cell.font = header_font
                cell.fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
                cell.alignment = center_align
    
    # HOJA 4: Por Proveedor
    if not df_seguimientos.empty:
        ws_proveedores = wb.create_sheet("Por Proveedor")
        
        df_por_proveedor = df_seguimientos.groupby('proveedor').agg({
            'id': 'count',
            'esta_retrasado': 'sum',
            'dias_desde_pedido': 'mean',
            'dias_retraso': 'mean'
        }).reset_index()
        
        df_por_proveedor.columns = [
            'Proveedor', 'Total Pedidos', 'Retrasados',
            'Promedio Días Pedido', 'Promedio Días Retraso'
        ]
        
        df_por_proveedor = df_por_proveedor.sort_values('Total Pedidos', ascending=False)
        
        for r in dataframe_to_rows(df_por_proveedor, index=False, header=True):
            ws_proveedores.append(r)
        
        for cell in ws_proveedores[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
    
    # HOJA 5: Por Sucursal
    if not df_seguimientos.empty:
        ws_sucursales = wb.create_sheet("Por Sucursal")
        
        df_por_sucursal = df_seguimientos.groupby('sucursal').agg({
            'id': 'count',
            'esta_retrasado': 'sum',
            'dias_desde_pedido': 'mean'
        }).reset_index()
        
        df_por_sucursal.columns = [
            'Sucursal', 'Total Pedidos', 'Retrasados', 'Promedio Días Pedido'
        ]
        
        df_por_sucursal = df_por_sucursal.sort_values('Total Pedidos', ascending=False)
        
        for r in dataframe_to_rows(df_por_sucursal, index=False, header=True):
            ws_sucursales.append(r)
        
        for cell in ws_sucursales[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
    
    # HOJA 6: Vista Agrupada por Orden (NUEVO)
    if ordenes_agrupadas:
        ws_agrupada = wb.create_sheet("Vista Agrupada")
        
        # Encabezados
        headers = [
            'Orden Cliente', 'Service Tag', 'Sucursal', 'Total Proveedores',
            'Seguimientos Recibidos', 'Seguimientos Pendientes', 'Estado General',
            'Tiene Retrasos', 'Días Máx Retraso', 'Prioridad Máxima',
            'Fecha Pedido Más Antigua', 'Fecha Entrega Más Próxima', 'Proveedores Detalle'
        ]
        ws_agrupada.append(headers)
        
        # Datos
        for orden in ordenes_agrupadas:
            # Construir cadena de proveedores
            proveedores_str = ' | '.join([
                f"{p['proveedor']}: {p['estado_display']} ({p['descripcion'][:30]}...)"
                for p in orden['proveedores_activos']
            ])
            
            row_data = [
                orden['orden_cliente'],
                orden['service_tag'],
                orden['sucursal'],
                orden['total_proveedores'],
                orden['seguimientos_recibidos'],
                orden['seguimientos_pendientes'],
                orden['estado_general'].upper(),
                'SÍ' if orden['tiene_retrasados'] else 'NO',
                orden['dias_maximo_retraso'] if orden['tiene_retrasados'] else 0,
                orden['prioridad_maxima'].upper(),
                orden['fecha_pedido_mas_antigua'].strftime('%Y-%m-%d') if orden['fecha_pedido_mas_antigua'] else '',
                orden['fecha_entrega_mas_proxima'].strftime('%Y-%m-%d') if orden['fecha_entrega_mas_proxima'] else '',
                proveedores_str
            ]
            ws_agrupada.append(row_data)
        
        # Aplicar estilos
        for cell in ws_agrupada[1]:
            cell.font = header_font
            cell.fill = PatternFill(start_color="27ae60", end_color="27ae60", fill_type="solid")
            cell.alignment = center_align
        
        # Ajustar ancho de columnas
        ws_agrupada.column_dimensions['A'].width = 15
        ws_agrupada.column_dimensions['B'].width = 15
        ws_agrupada.column_dimensions['C'].width = 15
        ws_agrupada.column_dimensions['D'].width = 12
        ws_agrupada.column_dimensions['E'].width = 12
        ws_agrupada.column_dimensions['F'].width = 12
        ws_agrupada.column_dimensions['G'].width = 15
        ws_agrupada.column_dimensions['H'].width = 12
        ws_agrupada.column_dimensions['I'].width = 12
        ws_agrupada.column_dimensions['J'].width = 15
        ws_agrupada.column_dimensions['K'].width = 18
        ws_agrupada.column_dimensions['L'].width = 18
        ws_agrupada.column_dimensions['M'].width = 50
        
        # Colorear filas según prioridad
        for row_idx, orden in enumerate(ordenes_agrupadas, start=2):
            if orden['prioridad_maxima'] == 'critico':
                fill_color = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
                for cell in ws_agrupada[row_idx]:
                    cell.fill = fill_color
            elif orden['prioridad_maxima'] == 'alto':
                fill_color = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
                for cell in ws_agrupada[row_idx]:
                    cell.fill = fill_color
    
    # ========================================
    # 4. PREPARAR RESPUESTA HTTP
    # ========================================
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nombre_archivo = f'Dashboard_Seguimiento_Piezas_{timestamp}.xlsx'
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    wb.save(response)
    
    return response


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
