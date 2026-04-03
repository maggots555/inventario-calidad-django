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
from django.views.decorators.cache import cache_page
from django_ratelimit.decorators import ratelimit
from django.conf import settings
from django.urls import reverse
from functools import wraps
from PIL import Image
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
    EstadoRHITSO,
    SeguimientoRHITSO,
    IncidenciaRHITSO,
    TipoIncidenciaRHITSO,
    CategoriaDiagnostico,
    ConfiguracionRHITSO,
)
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
    EditarInformacionEquipoForm,
    CrearCotizacionForm,
    GestionarCotizacionForm,
    ActualizarEstadoRHITSOForm,
    RegistrarIncidenciaRHITSOForm,
    ResolverIncidenciaRHITSOForm,
    EditarDiagnosticoSICForm,
)


# ===== CACHE DE DASHBOARDS (Redis) =====
# EXPLICACIÓN PARA PRINCIPIANTES:
# cache_page() guarda la respuesta HTML completa en Redis durante X segundos.
# La segunda vez que alguien abre la misma URL, Django la sirve desde Redis
# sin ejecutar la vista (sin consultar BD, sin generar gráficas Plotly).
#
# cache_page cachea POR URL COMPLETA, así que:
#   /dashboard/?fecha_inicio=2025-01-01  → cache separado
#   /dashboard/?fecha_inicio=2025-06-01  → otro cache separado
#
# IMPORTANTE: cache_page debe ir DESPUÉS de @login_required para que
# cada usuario autenticado tenga su propio cache (no mezclar datos).
#
# CACHE_TTL_DASHBOARD viene de settings.py (10 minutos por defecto).
# Si necesitas forzar actualización, puedes limpiar cache desde Django shell:
#   from django.core.cache import cache
#   cache.clear()  # Limpia TODO el cache

cache_page_dashboard = cache_page(getattr(settings, 'CACHE_TTL_DASHBOARD', 600))


# ===== DECORADORES DE PERMISOS =====
def permission_required_with_message(perm, message=None):
    """
    Decorador personalizado que verifica permisos de Django y redirige a página de acceso denegado
    
    Args:
        perm (str): Permiso requerido en formato 'app.codename' (ej: 'servicio_tecnico.add_ordenservicio')
        message (str): Mensaje personalizado de error (opcional)
    
    Uso:
        @login_required
        @permission_required_with_message('servicio_tecnico.add_ordenservicio')
        def crear_orden(request):
            # Solo usuarios con permiso add_ordenservicio pueden ejecutar esto
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.has_perm(perm):
                error_msg = message or f'No tienes permisos para realizar esta acción.'
                # Redirigir a página de acceso denegado con el mensaje
                return redirect(f"{reverse('servicio_tecnico:acceso_denegado_servicio_tecnico')}?mensaje={error_msg}&permiso={perm}")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def registrar_historial(orden, tipo_evento, usuario, comentario='', es_sistema=False):
    """
    Función helper para registrar eventos en el historial de la orden.

    """
    HistorialOrden.objects.create(
        orden=orden,
        tipo_evento=tipo_evento,
        comentario=comentario,
        usuario=usuario,
        es_sistema=es_sistema
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
                            enviar_seguimiento_cliente_task.delay(
                                orden_id=orden.id,
                                usuario_id=request.user.id,
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
                            enviar_seguimiento_cliente_task.delay(
                                orden_id=orden.id,
                                usuario_id=request.user.id,
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
            import logging
            logger = logging.getLogger(__name__)
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
                                enviar_seguimiento_cliente_task.delay(
                                    orden_id=orden.id,
                                    usuario_id=request.user.id,
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
                
                # ================================================================
                # CAMBIO AUTOMÁTICO DE ESTADO: Esperando Aprobación Cliente
                # ================================================================
                # Al crear una nueva cotización, cambiar automáticamente el estado
                # de la orden a "Esperando Aprobación Cliente" (estado: 'cotizacion')
                # para reflejar que está pendiente de respuesta del cliente.
                estado_anterior = orden.estado
                
                # Solo cambiar si NO está ya en ese estado
                if estado_anterior != 'cotizacion':
                    orden.estado = 'cotizacion'
                    orden.save()
                    
                    # Mensaje informativo al usuario
                    messages.info(
                        request,
                        '📋 Estado actualizado automáticamente a: "Esperando Aprobación Cliente"'
                    )
                    
                    # Registrar el cambio automático en el historial
                    HistorialOrden.objects.create(
                        orden=orden,
                        tipo_evento='cambio_estado',
                        estado_anterior=estado_anterior,
                        estado_nuevo='cotizacion',
                        comentario=(
                            f'Cambio automático de estado: '
                            f'{dict(ESTADO_ORDEN_CHOICES).get(estado_anterior, estado_anterior)} → '
                            f'Esperando Aprobación Cliente (cotización creada)'
                        ),
                        usuario=empleado_actual,
                        es_sistema=True  # Marcar como evento del sistema
                    )
                
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
            else:
                messages.error(request, '❌ Error al crear la cotización.')
        
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
        # FORMULARIO 8.6: Editar Costo de Mano de Obra
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
                    cotizacion.costo_mano_obra = nuevo_costo
                    cotizacion.save(update_fields=['costo_mano_obra'])
                    
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
    
    # Verificar si ya se enviaron correos de imágenes (para el estado de los botones)
    egreso_correo_ya_enviado = orden.historial.filter(
        tipo_evento='email',
        comentario__icontains='imágenes de egreso'
    ).exists()
    ingreso_correo_ya_enviado = orden.historial.filter(
        tipo_evento='email',
        comentario__icontains='imágenes de ingreso'
    ).exists()
    
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
        
        # Historial y comentarios - ACTUALIZADO: Cargar todos (Opción A - Marzo 2026)
        'historial_automatico': historial_automatico,  # Todos los eventos
        'comentarios': comentarios[:20],  # Últimos 20 (comentarios siguen limitados)
        'total_eventos_historial': historial_automatico.count(),
        
        # Imágenes
        'imagenes_por_tipo': imagenes_por_tipo,
        'total_imagenes': total_imagenes,
        'egreso_correo_ya_enviado': egreso_correo_ya_enviado,
        'ingreso_correo_ya_enviado': ingreso_correo_ya_enviado,
        
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
            enviar_feedback_rechazo_task.delay(feedback_id=feedback.pk, usuario_id=usuario_id)
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
        enviar_vigencia_vencida_task.delay(orden_id=orden.pk, usuario_id=usuario_id)
        email_cl = orden.detalle_equipo.email_cliente if orden.detalle_equipo else '(sin email)'
        messages.success(
            request,
            f'📧 Correo de cotización vencida enviado a {email_cl}.'
        )
    else:
        messages.info(request, 'ℹ️ Envío de correo cancelado.')

    return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)


# ============================================================================
# VISTA PÚBLICA: seguimiento_orden_cliente
# Página accesible sin autenticación. El cliente abre el link desde el correo
# de seguimiento y ve la información de su equipo, timeline de estados y
# datos de contacto de su responsable de seguimiento.
# ============================================================================

@ratelimit(key='ip', rate='20/m', method=['GET', 'POST'])
def seguimiento_orden_cliente(request, token):
    """
    Vista pública de seguimiento de orden para el cliente.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista NO usa @login_required porque la abre el cliente desde su correo.
    Valida el token antes de mostrar cualquier información.
    States del template:
      - 'tracking': Orden activa con timeline
      - 'finalizado': Orden finalizada, esperando confirmación de entrega
      - 'entregado': Agradecimiento + link a encuesta si existe
      - 'invalido': Token no existe, orden cancelada o link expirado
    """
    from .models import EnlaceSeguimientoCliente, FeedbackCliente
    from config.constants import ESTADO_ORDEN_CHOICES
    from config.paises_config import PAISES_CONFIG

    TEMPLATE = 'servicio_tecnico/seguimiento_cliente.html'

    # ── Obtener IP del cliente para logging de seguridad ──
    _xfwd = request.META.get('HTTP_X_FORWARDED_FOR')
    _ip = _xfwd.split(',')[0].strip() if _xfwd else request.META.get('REMOTE_ADDR')

    # ── Buscar el enlace por token ──
    try:
        enlace = EnlaceSeguimientoCliente.objects.select_related(
            'orden__detalle_equipo',
            'orden__sucursal',
            'orden__responsable_seguimiento',
        ).get(token=token)
    except EnlaceSeguimientoCliente.DoesNotExist:
        logger.warning(
            "[SEGURIDAD] Seguimiento con token inexistente | IP: %s | token: %s...",
            _ip, token[:8]
        )
        return render(request, TEMPLATE, {'estado': 'invalido'})

    orden = enlace.orden
    detalle = orden.detalle_equipo

    # ── Verificar disponibilidad (expirado, cancelado o desactivado) ──
    if not enlace.esta_disponible:
        return render(request, TEMPLATE, {'estado': 'invalido'})

    # ── Registrar acceso del cliente ──
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    ip_cliente = (
        x_forwarded.split(',')[0].strip() if x_forwarded
        else request.META.get('REMOTE_ADDR')
    )
    enlace.registrar_acceso(ip=ip_cliente)

    # ── Construir timeline de cambios de estado ──
    historial_estados = HistorialOrden.objects.filter(
        orden=orden,
        tipo_evento='cambio_estado',
    ).order_by('fecha_evento').values(
        'estado_nuevo', 'fecha_evento'
    )

    estado_dict = dict(ESTADO_ORDEN_CHOICES)
    ahora = timezone.now()

    # ── Estados que son "hitos completados" (ya sucedieron, no son procesos activos) ──
    # Si el estado actual de la orden es uno de estos, TODOS los nodos del timeline
    # van con palomita ✓ y se agrega un nodo auxiliar indicando qué sigue.
    ESTADOS_HITO = {
        'equipo_diagnosticado',
        'diagnostico_enviado_cliente',
        'cotizacion_enviada_proveedor',
        'cotizacion_recibida_proveedor',
        'cliente_acepta_cotizacion',
        'rechazada',
        'partes_solicitadas_proveedor',
        'piezas_recibidas',
        'wpb_pieza_incorrecta',
        'doa_pieza_danada',
        'pnc_parte_no_disponible',
        'finalizado',
        'entregado',
    }

    # Texto que describe qué viene después de cada hito
    SIGUIENTE_PASO = {
        'equipo_diagnosticado': 'El diagnóstico será enviado para tu revisión',
        'diagnostico_enviado_cliente': 'Envío de Cotización a Proveedor',
        'cotizacion_enviada_proveedor': 'En espera de cotización del proveedor',
        'cotizacion_recibida_proveedor': 'Tu cotización está siendo preparada',
        'cliente_acepta_cotizacion': 'Gestionando las piezas necesarias para tu equipo',
        'rechazada': 'En espera de indicaciones',
        'partes_solicitadas_proveedor': 'En espera de llegada de piezas',
        'piezas_recibidas': 'Tu equipo entrará a reparación próximamente',
        'wpb_pieza_incorrecta': 'Gestionando reemplazo de pieza',
        'doa_pieza_danada': 'Gestionando reemplazo de pieza dañada',
        'pnc_parte_no_disponible': 'Buscando alternativas de disponibilidad',
    }

    # Nombres alternativos para el cliente en la vista pública
    # (no modifica los nombres internos usados en el panel de administración)
    NOMBRES_PUBLICOS = {
        'cotizacion': 'Cotización enviada, en espera de aprobación',
        'control_calidad': 'Equipo reparado, en control de calidad',
    }

    timeline_raw = []
    for h in historial_estados:
        codigo = h['estado_nuevo']
        if not codigo:
            continue
        fecha = h['fecha_evento']
        delta = ahora - fecha
        if delta.days > 0:
            hace = f"Hace {delta.days} día{'s' if delta.days != 1 else ''}"
        elif delta.seconds >= 3600:
            horas = delta.seconds // 3600
            hace = f"Hace {horas} hora{'s' if horas != 1 else ''}"
        else:
            hace = "Hace unos minutos"

        timeline_raw.append({
            'codigo': codigo,
            'nombre': NOMBRES_PUBLICOS.get(codigo, estado_dict.get(codigo, codigo)),
            'fecha': fecha,
            'hace': hace,
        })

    # ── Eliminar estados duplicados consecutivos ──
    timeline = []
    for paso in timeline_raw:
        if timeline and timeline[-1]['codigo'] == paso['codigo']:
            continue
        timeline.append(paso)

    # ── Determinar si el estado actual es un hito o un proceso activo ──
    # Si es hito → todos completados + nodo "siguiente paso" con pulse
    # Si es proceso activo → el último nodo tiene pulse (está en progreso)
    estado_orden = orden.estado
    estado_es_hito = estado_orden in ESTADOS_HITO
    siguiente_paso_texto = SIGUIENTE_PASO.get(estado_orden) if estado_es_hito else None

    # Marcar cada nodo del timeline como completado o actual
    for i, paso in enumerate(timeline):
        es_ultimo = (i == len(timeline) - 1)
        if estado_es_hito:
            # Hito: TODOS los nodos son completados (ya sucedieron)
            paso['completado'] = True
            paso['es_actual'] = False
        else:
            # Proceso activo: el último nodo es "actual" (en progreso)
            paso['completado'] = not es_ultimo
            paso['es_actual'] = es_ultimo

    if estado_orden == 'cancelado':
        return render(request, TEMPLATE, {'estado': 'invalido'})

    # ── Datos del responsable de seguimiento ──
    responsable = orden.responsable_seguimiento
    whatsapp_url = None
    email_responsable = None
    nombre_responsable = None

    if responsable:
        nombre_responsable = responsable.nombre_completo
        email_responsable = responsable.email

        # Construir link de WhatsApp
        if responsable.numero_whatsapp:
            pais_code = getattr(orden.sucursal, 'pais', 'mexico') if orden.sucursal else 'mexico'
            pais_conf = PAISES_CONFIG.get(pais_code, PAISES_CONFIG.get('mexico', {}))
            codigo_tel = pais_conf.get('codigo_telefonico', '52')
            numero = responsable.numero_whatsapp
            folio = detalle.orden_cliente or orden.numero_orden_interno
            service_tag = detalle.numero_serie or ''
            msg = (
                f"Hola, me puedes ayudar con el seguimiento de mi orden "
                f"\"{folio}\" / \"{service_tag}\", por favor."
            )
            from urllib.parse import quote
            whatsapp_url = f"https://wa.me/{codigo_tel}{numero}?text={quote(msg)}"

    # Folio visible para el cliente
    folio_display = detalle.orden_cliente or orden.numero_orden_interno

    # ── Imágenes del equipo para la galería pública ──
    # Solo se muestran los tipos relevantes para el cliente (no autorizacion/packing).
    _TIPO_LABEL_GALERIA = {
        'ingreso':     'Ingreso',
        'diagnostico': 'Diagnóstico',
        'reparacion':  'Reparación',
        'egreso':      'Egreso',
    }
    imagenes_galeria = [
        {
            'url':        img.imagen.url,
            'tipo':       img.tipo,
            'tipo_label': _TIPO_LABEL_GALERIA.get(img.tipo, img.tipo.capitalize()),
            'descripcion': img.descripcion,
        }
        for img in ImagenOrden.objects.filter(
            orden=orden,
            tipo__in=['ingreso', 'diagnostico', 'reparacion', 'egreso'],
        ).order_by('tipo', 'fecha_subida')
    ]

    # ── Seguimientos de piezas (solo cuando el estado es 'esperando_piezas') ──
    # Solo se exponen al cliente: nombre del componente, descripción, timeline y fechas.
    # No se incluyen: proveedor, número de pedido, notas internas ni costos.
    seguimientos_piezas = []
    if estado_orden == 'esperando_piezas':
        # Flujo normal de estados en orden de progresion visual
        _PASOS_NORMALES = [
            ('pedido',     'Pedido'),
            ('confirmado', 'Confirmado'),
            ('transito',   'En Tránsito'),
            ('recibido',   'Recibido'),
        ]
        _IDX_NORMAL = {c: i for i, (c, _) in enumerate(_PASOS_NORMALES)}
        try:
            for s in orden.cotizacion.seguimientos_piezas.prefetch_related(
                'piezas__componente'
            ).order_by('fecha_pedido'):
                nombres = [p.componente.nombre for p in s.piezas.all()]
                estado_actual = s.estado

                # Construir timeline visual (lista de pasos con tipo para CSS)
                # Tipos: 'completado' | 'actual' | 'alerta' | 'pendiente' | 'problema'
                _timeline = []
                if estado_actual in ('incorrecto', 'danado'):
                    # Todos los pasos normales completados + paso final de problema
                    for _, nombre in _PASOS_NORMALES:
                        _timeline.append({'nombre': nombre, 'tipo': 'completado'})
                    _nombres_problema = {
                        'incorrecto': 'P. Incorrecta',
                        'danado':     'P. Dañada',
                    }
                    _timeline.append({
                        'nombre': _nombres_problema.get(estado_actual, estado_actual),
                        'tipo': 'problema',
                    })
                elif estado_actual == 'retrasado':
                    # Pedido/Confirmado completados, Retrasado como alerta, Recibido pendiente
                    _timeline.extend([
                        {'nombre': 'Pedido',     'tipo': 'completado'},
                        {'nombre': 'Confirmado', 'tipo': 'completado'},
                        {'nombre': 'Retrasado',  'tipo': 'alerta'},
                        {'nombre': 'Recibido',   'tipo': 'pendiente'},
                    ])
                else:
                    idx_actual = _IDX_NORMAL.get(estado_actual, 0)
                    # 'recibido' es el último paso y ya está finalizado: todos completados
                    es_ultimo_completado = (estado_actual == 'recibido')
                    for i, (_, nombre) in enumerate(_PASOS_NORMALES):
                        if i < idx_actual or es_ultimo_completado:
                            tipo = 'completado'
                        elif i == idx_actual:
                            tipo = 'actual'
                        else:
                            tipo = 'pendiente'
                        _timeline.append({'nombre': nombre, 'tipo': tipo})

                seguimientos_piezas.append({
                    'nombre':         ', '.join(nombres) if nombres else '',
                    'descripcion':    s.descripcion_piezas,
                    'estado':         estado_actual,
                    'estado_nombre':  s.get_estado_display(),
                    'fecha_pedido':   s.fecha_pedido,
                    'fecha_estimada': s.fecha_entrega_estimada,
                    'fecha_real':     s.fecha_entrega_real,
                    'timeline':       _timeline,
                })
        except Exception:
            pass

    # ── Construir contexto según estado ──
    context = {
        'orden': orden,
        'detalle': detalle,
        'timeline': timeline,
        'estado_actual_nombre': estado_dict.get(estado_orden, estado_orden),
        'folio_display': folio_display,
        'nombre_responsable': nombre_responsable,
        'email_responsable': email_responsable,
        'whatsapp_url': whatsapp_url,
        'dias_restantes': enlace.dias_restantes,
        'siguiente_paso': siguiente_paso_texto,
        'imagenes_galeria': imagenes_galeria,
        'seguimientos_piezas': seguimientos_piezas,
    }

    if estado_orden == 'entregado':
        # Buscar encuesta de satisfacción activa
        encuesta_url = None
        try:
            from django.conf import settings as _settings
            fb = FeedbackCliente.objects.filter(
                orden=orden,
                tipo='satisfaccion',
                correo_enviado=True,
            ).first()
            if fb and fb.es_valido:
                site_url = getattr(_settings, 'SITE_URL', 'http://localhost:8000')
                encuesta_url = f"{site_url}/feedback-satisfaccion/{fb.token}/"
        except Exception:
            pass

        context['estado'] = 'entregado'
        context['encuesta_url'] = encuesta_url
        context['encuesta_dias_restantes'] = fb.dias_restantes if fb and fb.es_valido else None
    elif estado_orden == 'finalizado':
        context['estado'] = 'finalizado'
    else:
        context['estado'] = 'tracking'

    return render(request, TEMPLATE, context)


# ============================================================================
# VISTA PÚBLICA: feedback_rechazo_view
# Página accesible sin autenticación. El cliente abre el link desde el correo,
# ve la información de su equipo y piezas, y puede escribir su comentario.
# ============================================================================

@ratelimit(key='ip', rate='20/m', method=['GET', 'POST'])
def feedback_rechazo_view(request, token):
    """
    Vista pública para que el cliente deje su comentario de rechazo.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista NO usa @login_required porque la abre el cliente desde su correo.
    Valida el token antes de mostrar cualquier información.
    Si el token ya fue usado o expiró, muestra un mensaje genérico
    (no revelar si el token existió, expiró o fue usado — prevención de enumeración).
    """
    from django.core.signing import BadSignature, SignatureExpired
    from .models import FeedbackCliente
    from .forms import FeedbackRechazoClienteForm

    # ── Obtener IP para logging de seguridad ──
    _xfwd = request.META.get('HTTP_X_FORWARDED_FOR')
    _ip = _xfwd.split(',')[0].strip() if _xfwd else request.META.get('REMOTE_ADDR')

    # ── Buscar el feedback por token ──
    try:
        feedback = FeedbackCliente.objects.select_related(
            'cotizacion__orden__detalle_equipo',
        ).get(token=token)
    except FeedbackCliente.DoesNotExist:
        logger.warning(
            "[SEGURIDAD] Feedback rechazo con token inexistente | IP: %s | token: %s...",
            _ip, token[:8]
        )
        return render(request, 'servicio_tecnico/feedback_rechazo.html', {
            'estado': 'invalido',
            'mensaje': 'El enlace no es válido o ya no existe.',
        })

    # ── Validar estado del token ──
    # SEGURIDAD: Mensajes diferenciados en el template (ya_respondido, expirado)
    # son aceptables porque el atacante necesitaría un token válido de 256 bits
    # para llegar aquí. La protección real está en DoesNotExist (arriba).
    if feedback.utilizado:
        return render(request, 'servicio_tecnico/feedback_rechazo.html', {
            'estado': 'ya_respondido',
            'mensaje': 'Ya enviaste tu comentario. ¡Gracias por tu tiempo!',
        })

    if feedback.esta_expirado:
        return render(request, 'servicio_tecnico/feedback_rechazo.html', {
            'estado': 'expirado',
            'mensaje': 'Este enlace ha expirado. Los links son válidos por 7 días.',
        })

    orden = feedback.cotizacion.orden
    detalle = orden.detalle_equipo
    piezas = feedback.cotizacion.piezas_cotizadas.filter(aceptada_por_cliente=False)

    # ── Calcular monto total rechazado ──
    monto_piezas = sum(
        (p.costo_unitario or 0) * (p.cantidad or 1) for p in piezas
    )
    monto_mano_obra = feedback.cotizacion.costo_mano_obra or 0

    if request.method == 'POST':
        form = FeedbackRechazoClienteForm(request.POST)
        if form.is_valid():
            # ── Honeypot: Si el campo oculto tiene valor, es un bot ──
            if form.cleaned_data.get('website'):
                logger.warning(
                    "[SEGURIDAD] Honeypot activado en feedback rechazo | IP: %s",
                    _ip
                )
                # Simular éxito para no alertar al bot
                return render(request, 'servicio_tecnico/feedback_rechazo.html', {
                    'estado': 'gracias',
                    'mensaje': '¡Gracias por tu comentario! Tu opinión nos ayuda a mejorar.',
                })

            feedback.comentario_cliente = form.cleaned_data['comentario_cliente']
            feedback.utilizado = True
            feedback.fecha_respuesta = timezone.now()
            # Guardar IP del cliente para trazabilidad
            feedback.ip_respuesta = _ip
            feedback.save(update_fields=[
                'comentario_cliente', 'utilizado', 'fecha_respuesta', 'ip_respuesta'
            ])

            # Registrar en historial de la orden
            try:
                HistorialOrden.objects.create(
                    orden=orden,
                    tipo_evento='cotizacion',
                    comentario=(
                        f'💬 Cliente dejó comentario de rechazo (feedback)\n'
                        f'   {feedback.comentario_cliente[:200]}'
                    ),
                    usuario=None,
                    es_sistema=True
                )
            except Exception:
                pass

            return render(request, 'servicio_tecnico/feedback_rechazo.html', {
                'estado': 'gracias',
                'mensaje': '¡Gracias por tu comentario! Tu opinión nos ayuda a mejorar.',
            })
    else:
        form = FeedbackRechazoClienteForm()

    context = {
        'estado': 'formulario',
        'form': form,
        'feedback': feedback,
        'orden': orden,
        'detalle': detalle,
        'piezas': piezas,
        'monto_piezas': monto_piezas,
        'monto_mano_obra': monto_mano_obra,
        'monto_total': monto_piezas + monto_mano_obra,
        'motivo_rechazo': feedback.cotizacion.get_motivo_rechazo_display(),
        'dias_restantes': feedback.dias_restantes,
    }
    return render(request, 'servicio_tecnico/feedback_rechazo.html', context)

def comprimir_y_guardar_imagen(orden, imagen_file, tipo, descripcion, empleado):
    """
    Comprime y guarda una imagen con la estructura de carpetas solicitada.

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
@permission_required_with_message('servicio_tecnico.view_imagenorden')
def descargar_imagen_original(request, imagen_id):
    """
    Descarga la imagen original (alta resolución) de una orden.

    Args:
        request: Objeto HttpRequest
        imagen_id: ID de la ImagenOrden
    
    Returns:
        HttpResponse con el archivo de imagen para descargar
    """
    from django.http import FileResponse, Http404, HttpResponseForbidden
    from pathlib import Path
    
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
    
    # Verificar que tenemos una ruta de archivo
    if not archivo_imagen:
        raise Http404("No hay archivo de imagen asociado.")
    
    # EXPLICACIÓN: Usar imagen.path que incluye automáticamente el prefijo del país
    # Esto funciona tanto para imágenes antiguas como nuevas (compatibilidad multi-país)
    try:
        archivo_path = Path(archivo_imagen.path)
        
        # Verificar que el archivo existe físicamente
        if not archivo_path.exists():
            print(f"[DESCARGA] ❌ Archivo no existe: {archivo_path}")
            raise Http404("El archivo de imagen no existe en el sistema de almacenamiento.")
        
        if not archivo_path.is_file():
            print(f"[DESCARGA] ❌ La ruta no es un archivo: {archivo_path}")
            raise Http404("La ruta de imagen no corresponde a un archivo válido.")
        
        print(f"[DESCARGA] ✅ Imagen encontrada: {archivo_path}")
        
    except Exception as e:
        print(f"[DESCARGA] ❌ Error al acceder a la imagen: {e}")
        raise Http404(f"Error al acceder a la imagen: {str(e)}")
    
    # Obtener el nombre del archivo original
    nombre_archivo = os.path.basename(archivo_imagen.name)
    
    # Crear nombre descriptivo para descarga
    tipo_texto = imagen.get_tipo_display()
    orden_numero = imagen.orden.numero_orden_interno
    service_tag = imagen.orden.detalle_equipo.numero_serie
    nombre_descarga = f"{orden_numero}_{service_tag}_{tipo_texto}_{nombre_archivo}"
    
    # Abrir archivo desde la ruta encontrada y crear respuesta
    # IMPORTANTE: Usamos archivo_path (Path object) en lugar de archivo_imagen.open()
    # porque archivo_path ya contiene la ubicación correcta (disco principal o alterno)
    archivo = archivo_path.open('rb')
    response = FileResponse(archivo, content_type='image/jpeg')
    response['Content-Disposition'] = f'attachment; filename="{nombre_descarga}"'
    
    return response


# ============================================================================
# VISTA: Eliminar Imagen de Orden
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.delete_imagenorden')
@require_http_methods(["POST"])
def eliminar_imagen(request, imagen_id):
    """
    Elimina una imagen de una orden de servicio.

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
        # EXPLICACIÓN: Usar imagen.path que incluye el prefijo del país automáticamente
        from pathlib import Path
        
        archivos_eliminados = []
        
        # Eliminar imagen comprimida
        if imagen.imagen:
            try:
                archivo_path = Path(imagen.imagen.path)
                
                if archivo_path.exists() and archivo_path.is_file():
                    os.remove(str(archivo_path))
                    archivos_eliminados.append('imagen comprimida')
                    print(f"[ELIMINAR] ✅ Imagen comprimida eliminada: {archivo_path.name}")
                else:
                    print(f"[ELIMINAR] ⚠️ Imagen comprimida no encontrada: {archivo_path}")
                    
            except Exception as e:
                print(f"[ELIMINAR] ⚠️ Error al eliminar archivo comprimido: {str(e)}")
        
        # Eliminar imagen original
        if imagen.imagen_original:
            try:
                archivo_path = Path(imagen.imagen_original.path)
                
                if archivo_path.exists() and archivo_path.is_file():
                    os.remove(str(archivo_path))
                    archivos_eliminados.append('imagen original')
                    print(f"[ELIMINAR] ✅ Imagen original eliminada: {archivo_path.name}")
                else:
                    print(f"[ELIMINAR] ⚠️ Imagen original no encontrada: {archivo_path}")
                    
            except Exception as e:
                print(f"[ELIMINAR] ⚠️ Error al eliminar archivo original: {str(e)}")
        
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
@permission_required_with_message('servicio_tecnico.view_referenciagamaequipo')
def lista_referencias_gama(request):
    """
    Lista todas las referencias de gama de equipos con filtros de búsqueda.

    """
    from .models import ReferenciaGamaEquipo
    from django.core.paginator import Paginator
    
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
    
    # Paginación: 25 registros por página
    total_referencias = referencias.count()
    paginator = Paginator(referencias, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'referencias': page_obj,
        'page_obj': page_obj,
        'busqueda': busqueda,
        'filtro_marca': filtro_marca,
        'filtro_gama': filtro_gama,
        'mostrar_inactivos': mostrar_inactivos,
        'marcas_disponibles': marcas_disponibles,
        'total_referencias': total_referencias,
        'orden': orden,
        'gamas_choices': [
            ('alta', 'Alta'),
            ('media', 'Media'),
            ('baja', 'Baja'),
        ],
    }
    
    return render(request, 'servicio_tecnico/referencias_gama/lista.html', context)


@login_required
@permission_required_with_message('servicio_tecnico.add_referenciagamaequipo')
def crear_referencia_gama(request):
    """
    Crea una nueva referencia de gama de equipo.

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
@permission_required_with_message('servicio_tecnico.change_referenciagamaequipo')
def editar_referencia_gama(request, referencia_id):
    """
    Edita una referencia de gama existente.

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
@permission_required_with_message('servicio_tecnico.delete_referenciagamaequipo')
def eliminar_referencia_gama(request, referencia_id):
    """
    Desactiva (soft delete) una referencia de gama.

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
@permission_required_with_message('servicio_tecnico.change_referenciagamaequipo')
def reactivar_referencia_gama(request, referencia_id):
    """
    Reactiva una referencia previamente desactivada.

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
@permission_required_with_message('servicio_tecnico.add_piezacotizada')
@require_http_methods(["POST"])
def agregar_pieza_cotizada(request, orden_id):
    """
    Agrega una nueva pieza a una cotización existente.

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
@permission_required_with_message('servicio_tecnico.view_piezacotizada')
@require_http_methods(["GET"])
def obtener_pieza_cotizada(request, pieza_id):
    """
    Obtiene los datos de una pieza cotizada para edición
    
    Returns:
        JsonResponse: Datos de la pieza en formato JSON
    """
    from django.http import JsonResponse
    from .models import PiezaCotizada
    
    try:
        pieza = get_object_or_404(PiezaCotizada, id=pieza_id)
        
        # Construir diccionario con los datos de la pieza
        datos_pieza = {
            'id': pieza.id,
            'componente_id': pieza.componente_id,
            'componente_nombre': pieza.componente.nombre,
            'descripcion_adicional': pieza.descripcion_adicional or '',
            'proveedor': pieza.proveedor or '',  # ← NUEVO CAMPO (Noviembre 2025)
            'cantidad': pieza.cantidad,
            'costo_unitario': str(pieza.costo_unitario),
            'orden_prioridad': pieza.orden_prioridad,
            'es_necesaria': pieza.es_necesaria,
            'sugerida_por_tecnico': pieza.sugerida_por_tecnico,
        }
        
        return JsonResponse({
            'success': True,
            'pieza': datos_pieza
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error al obtener pieza: {str(e)}'
        }, status=500)


@login_required
@permission_required_with_message('servicio_tecnico.change_piezacotizada')
@require_http_methods(["POST"])
def editar_pieza_cotizada(request, pieza_id):
    """
    Edita una pieza cotizada existente.

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
@permission_required_with_message('servicio_tecnico.delete_piezacotizada')
@require_http_methods(["POST"])
def eliminar_pieza_cotizada(request, pieza_id):
    """
    Elimina una pieza de la cotización.

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
@permission_required_with_message('servicio_tecnico.view_seguimientopieza')
@require_http_methods(["GET"])
def obtener_seguimiento_pieza(request, seguimiento_id):
    """
    Obtiene los datos de un seguimiento en formato JSON.

    """
    from django.http import JsonResponse
    from .models import SeguimientoPieza
    
    try:
        seguimiento = get_object_or_404(SeguimientoPieza, id=seguimiento_id)
        
        # Preparar datos en formato JSON
        data = {
            'success': True,
            'seguimiento': {
                'id': seguimiento.id,
                'proveedor': seguimiento.proveedor,
                'descripcion_piezas': seguimiento.descripcion_piezas,
                'numero_pedido': seguimiento.numero_pedido or '',
                'fecha_pedido': seguimiento.fecha_pedido.isoformat(),  # Formato: YYYY-MM-DD
                'fecha_entrega_estimada': seguimiento.fecha_entrega_estimada.isoformat(),
                'fecha_entrega_real': seguimiento.fecha_entrega_real.isoformat() if seguimiento.fecha_entrega_real else '',
                'estado': seguimiento.estado,
                'notas_seguimiento': seguimiento.notas_seguimiento or '',
                # Piezas relacionadas (IDs)
                'piezas': list(seguimiento.piezas.values_list('id', flat=True))
            }
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error al obtener seguimiento: {str(e)}'
        }, status=500)


@login_required
@permission_required_with_message('servicio_tecnico.add_seguimientopieza')
@require_http_methods(["POST"])
def agregar_seguimiento_pieza(request, orden_id):
    """
    Agrega un nuevo seguimiento de pedido a proveedor.

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
            
            # ===================================================================
            # NUEVA FUNCIONALIDAD: Cambiar estado automáticamente si es el primer seguimiento
            # ===================================================================
            # Contar cuántos seguimientos tiene esta cotización (incluyendo el recién agregado)
            total_seguimientos = cotizacion.seguimientos_piezas.count()
            
            if total_seguimientos == 1:
                # Es el PRIMER seguimiento → Cambiar estado a "esperando_piezas"
                estado_anterior = orden.estado
                orden.estado = 'esperando_piezas'
                orden.save()
                
                # Registrar el cambio de estado en el historial
                registrar_historial(
                    orden=orden,
                    tipo_evento='estado',
                    usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
                    comentario=f"🔄 Estado cambiado automáticamente: '{dict(orden._meta.get_field('estado').choices).get(estado_anterior)}' → 'Esperando Llegada de Piezas' (Primer seguimiento agregado)",
                    es_sistema=True
                )
            # ===================================================================
            
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
@permission_required_with_message('servicio_tecnico.change_seguimientopieza')
@require_http_methods(["POST"])
def editar_seguimiento_pieza(request, seguimiento_id):
    """
    Edita un seguimiento existente.

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
@permission_required_with_message('servicio_tecnico.delete_seguimientopieza')
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
@permission_required_with_message('servicio_tecnico.change_seguimientopieza')
@require_http_methods(["POST"])
def marcar_pieza_recibida(request, seguimiento_id):
    """
    Marca una pieza como recibida y envía notificación al técnico.

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
        
        # =================================================================
        # NUEVO (Enero 2026): Verificar si el usuario desea enviar email
        # =================================================================
        enviar_email_param = request.POST.get('enviar_email', 'true')
        debe_enviar_email = enviar_email_param.lower() == 'true'
        
        # Variable para rastrear si el email fue omitido por decisión del usuario
        email_omitido = False
        
        # Enviar notificación solo si el usuario lo solicitó
        if debe_enviar_email:
            resultado_email = _enviar_notificacion_pieza_recibida(orden, seguimiento)
        else:
            # Usuario decidió NO enviar email
            email_omitido = True
            resultado_email = {
                'success': False,
                'message': 'Email omitido por decisión del usuario',
                'destinatarios': [],
                'destinatarios_copia': []
            }
        
        # =================================================================
        # REGISTRAR EN HISTORIAL CON DETALLES DEL ENVÍO
        # =================================================================
        if email_omitido:
            # Usuario decidió NO enviar email
            mensaje_historial = f"📬 Pieza recibida - {seguimiento.proveedor}\n"
            mensaje_historial += f"📭 Email omitido por decisión del usuario\n"
            mensaje_historial += f"ℹ️ El técnico deberá ser notificado manualmente"
        elif resultado_email['success']:
            # Email enviado exitosamente
            destinatarios_str = ', '.join(resultado_email['destinatarios'])
            mensaje_historial = f"📬 Pieza recibida - {seguimiento.proveedor}\n"
            mensaje_historial += f"✉️ Email enviado a: {destinatarios_str}"
            
            if resultado_email['destinatarios_copia']:
                cc_str = ', '.join(resultado_email['destinatarios_copia'])
                mensaje_historial += f"\n📧 Con copia a: {cc_str}"
        else:
            # Error al enviar email
            mensaje_historial = f"📬 Pieza recibida - {seguimiento.proveedor}\n"
            mensaje_historial += f"❌ Error al enviar email: {resultado_email['message']}\n"
            mensaje_historial += f"⚠️ El técnico NO fue notificado automáticamente"
        
        # Registrar en historial
        registrar_historial(
            orden=orden,
            tipo_evento='cotizacion',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=mensaje_historial,
            es_sistema=False
        )
        
        # =================================================================
        # RESPUESTA JSON CON INFORMACIÓN DEL ENVÍO
        # =================================================================
        mensaje_respuesta = '✅ Pieza marcada como recibida.'
        
        if email_omitido:
            mensaje_respuesta += ' Email omitido por decisión del usuario.'
        elif resultado_email['success']:
            mensaje_respuesta += ' Email enviado al técnico.'
        else:
            mensaje_respuesta += f" ⚠️ No se pudo enviar el email: {resultado_email['message']}"
        
        return JsonResponse({
            'success': True,
            'message': mensaje_respuesta,
            'email_enviado': resultado_email['success'],
            'email_omitido': email_omitido,  # NUEVO: Indicador de email omitido
            'seguimiento_html': _render_seguimiento_card(seguimiento)
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)


@login_required
@permission_required_with_message('servicio_tecnico.change_seguimientopieza')
@require_http_methods(["POST"])
def reenviar_notificacion_pieza(request, seguimiento_id):
    """
    Reenvía la notificación de pieza recibida al técnico.

    Args:
        request: HttpRequest con el usuario autenticado
        seguimiento_id: ID del seguimiento de la pieza
    
    Returns:
        JsonResponse con el resultado del reenvío
    """
    from django.http import JsonResponse
    from .models import SeguimientoPieza
    
    try:
        # Obtener el seguimiento
        seguimiento = get_object_or_404(SeguimientoPieza, id=seguimiento_id)
        cotizacion = seguimiento.cotizacion
        orden = cotizacion.orden
        
        # =================================================================
        # VALIDACIÓN: Solo se puede reenviar si está marcado como recibido
        # =================================================================
        if seguimiento.estado != 'recibido':
            return JsonResponse({
                'success': False,
                'error': '❌ Solo se pueden reenviar notificaciones de piezas marcadas como recibidas'
            }, status=400)
        
        # =================================================================
        # NUEVO (Enero 2026): Verificar si el usuario desea enviar email
        # En reenvíos normalmente siempre se quiere enviar, pero mantenemos
        # consistencia con la función marcar_recibido()
        # =================================================================
        enviar_email_param = request.POST.get('enviar_email', 'true')
        debe_enviar_email = enviar_email_param.lower() == 'true'
        
        email_omitido = False
        
        # =================================================================
        # INTENTAR ENVIAR EL EMAIL NUEVAMENTE (si el usuario lo solicitó)
        # =================================================================
        if debe_enviar_email:
            resultado_email = _enviar_notificacion_pieza_recibida(orden, seguimiento)
        else:
            # Usuario decidió NO reenviar
            email_omitido = True
            resultado_email = {
                'success': False,
                'message': 'Reenvío omitido por decisión del usuario',
                'destinatarios': [],
                'destinatarios_copia': []
            }
        
        # =================================================================
        # REGISTRAR EN HISTORIAL EL INTENTO DE REENVÍO
        # =================================================================
        if email_omitido:
            # Usuario decidió NO reenviar
            mensaje_historial = f"🔄 Reenvío de notificación - {seguimiento.proveedor}\n"
            mensaje_historial += f"📭 Email omitido por decisión del usuario\n"
            mensaje_historial += f"ℹ️ El técnico deberá ser notificado manualmente si es necesario"
            
            mensaje_respuesta = '✓ Reenvío omitido por decisión del usuario'
        elif resultado_email['success']:
            # Éxito en el reenvío
            destinatarios_str = ', '.join(resultado_email['destinatarios'])
            mensaje_historial = f"🔄 Notificación reenviada - {seguimiento.proveedor}\n"
            mensaje_historial += f"✉️ Email enviado a: {destinatarios_str}"
            
            if resultado_email['destinatarios_copia']:
                cc_str = ', '.join(resultado_email['destinatarios_copia'])
                mensaje_historial += f"\n📧 Con copia a: {cc_str}"
            
            mensaje_respuesta = '✅ Notificación reenviada exitosamente al técnico'
        else:
            # Error en el reenvío
            mensaje_historial = f"🔄 Intento de reenvío - {seguimiento.proveedor}\n"
            mensaje_historial += f"❌ Error al enviar email: {resultado_email['message']}\n"
            mensaje_historial += f"⚠️ El técnico NO fue notificado"
            
            mensaje_respuesta = f"❌ Error al reenviar: {resultado_email['message']}"
        
        # Registrar en historial
        registrar_historial(
            orden=orden,
            tipo_evento='cotizacion',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=mensaje_historial,
            es_sistema=False
        )
        
        # =================================================================
        # RETORNAR RESPUESTA
        # =================================================================
        return JsonResponse({
            'success': True,  # Siempre True porque la operación se completó (con o sin email)
            'message': mensaje_respuesta,
            'email_enviado': resultado_email['success'],
            'email_omitido': email_omitido  # NUEVO: Indicador de email omitido
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)


@login_required
@permission_required_with_message('servicio_tecnico.change_seguimientopieza')
@require_http_methods(["POST"])
def marcar_pieza_incorrecta(request, seguimiento_id):
    """
    Marca una pieza como incorrecta (WPB - Wrong Part Boxed).

    IMPORTANTE:
    - Solo se puede marcar como incorrecta si está en estado 'recibido'
    - El seguimiento queda cerrado con estado 'incorrecto'
    - Se debe crear un NUEVO seguimiento para el reemplazo
    
    Args:
        request: HttpRequest con el usuario autenticado
        seguimiento_id: ID del seguimiento de la pieza
    
    Returns:
        JsonResponse con el resultado de la operación
    """
    from django.http import JsonResponse
    from django.utils import timezone
    from .models import SeguimientoPieza
    
    try:
        seguimiento = get_object_or_404(SeguimientoPieza, id=seguimiento_id)
        cotizacion = seguimiento.cotizacion
        orden = cotizacion.orden
        
        # =================================================================
        # VALIDACIÓN: Solo se puede marcar si está recibido
        # =================================================================
        if seguimiento.estado != 'recibido':
            return JsonResponse({
                'success': False,
                'error': '❌ Solo se pueden marcar como incorrectas las piezas que ya fueron recibidas'
            }, status=400)
        
        # =================================================================
        # ACTUALIZAR ESTADO A INCORRECTO
        # =================================================================
        seguimiento.estado = 'incorrecto'
        seguimiento.save()
        
        # =================================================================
        # REGISTRAR EN HISTORIAL
        # =================================================================
        mensaje_historial = f"❌ PIEZA INCORRECTA (WPB) - {seguimiento.proveedor}\n"
        mensaje_historial += f"Descripción: {seguimiento.descripcion_piezas}\n"
        mensaje_historial += f"⚠️ La pieza recibida NO es la correcta o NO es compatible\n"
        mensaje_historial += f"📝 Acción requerida: Crear nuevo pedido de la pieza correcta"
        
        registrar_historial(
            orden=orden,
            tipo_evento='pieza',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=mensaje_historial,
            es_sistema=False
        )
        
        # =================================================================
        # RESPUESTA JSON
        # =================================================================
        return JsonResponse({
            'success': True,
            'message': '❌ Pieza marcada como INCORRECTA. Crea un nuevo pedido para la pieza correcta.',
            'seguimiento_html': _render_seguimiento_card(seguimiento)
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)


@login_required
@permission_required_with_message('servicio_tecnico.change_seguimientopieza')
@require_http_methods(["POST"])
def marcar_pieza_danada(request, seguimiento_id):
    """
    Marca una pieza como dañada o no funcional (DOA - Dead On Arrival).

    Args:
        request: HttpRequest con el usuario autenticado
        seguimiento_id: ID del seguimiento de la pieza
    
    Returns:
        JsonResponse con el resultado de la operación
    """
    from django.http import JsonResponse
    from django.utils import timezone
    from .models import SeguimientoPieza
    
    try:
        seguimiento = get_object_or_404(SeguimientoPieza, id=seguimiento_id)
        cotizacion = seguimiento.cotizacion
        orden = cotizacion.orden
        
        # =================================================================
        # VALIDACIÓN: Solo se puede marcar si está recibido
        # =================================================================
        if seguimiento.estado != 'recibido':
            return JsonResponse({
                'success': False,
                'error': '❌ Solo se pueden marcar como dañadas las piezas que ya fueron recibidas'
            }, status=400)
        
        # =================================================================
        # ACTUALIZAR ESTADO A DAÑADO
        # =================================================================
        seguimiento.estado = 'danado'
        seguimiento.save()
        
        # =================================================================
        # REGISTRAR EN HISTORIAL
        # =================================================================
        mensaje_historial = f"⚠️ PIEZA DAÑADA/NO FUNCIONAL (DOA) - {seguimiento.proveedor}\n"
        mensaje_historial += f"Descripción: {seguimiento.descripcion_piezas}\n"
        mensaje_historial += f"❌ La pieza llegó dañada o no funciona correctamente\n"
        mensaje_historial += f"📝 Acción requerida: Solicitar reemplazo al proveedor/garantía"
        
        registrar_historial(
            orden=orden,
            tipo_evento='pieza',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=mensaje_historial,
            es_sistema=False
        )
        
        # =================================================================
        # RESPUESTA JSON
        # =================================================================
        return JsonResponse({
            'success': True,
            'message': '⚠️ Pieza marcada como DAÑADA/NO FUNCIONAL. Solicita reemplazo al proveedor.',
            'seguimiento_html': _render_seguimiento_card(seguimiento)
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)


@login_required
@permission_required_with_message('servicio_tecnico.change_seguimientopieza')
def cambiar_estado_seguimiento(request, seguimiento_id):
    """
    Cambia el estado de un seguimiento de pieza de forma rápida.

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
            {f'<span class="badge bg-secondary" style="font-size: 0.75rem;">🏪 {pieza.proveedor}</span>' if pieza.proveedor else '<span class="text-muted">-</span>'}
        </td>
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
    
    # Definir estilos según estado (ACTUALIZADOS según ESTADO_PIEZA_CHOICES - Nov 2025)
    estado_badges = {
        'pedido': 'bg-primary',
        'confirmado': 'bg-info',
        'transito': 'bg-warning text-dark',
        'retrasado': 'bg-danger',
        'recibido': 'bg-success',
        'incorrecto': 'bg-danger',      # NUEVO: Pieza incorrecta (WPB)
        'danado': 'bg-warning text-dark',  # NUEVO: Pieza dañada (DOA)
    }
    
    estado_nombres = {
        'pedido': '📋 Pedido Realizado',
        'confirmado': '✅ Confirmado',
        'transito': '🚚 En Tránsito',
        'retrasado': '⚠️ Retrasado',
        'recibido': '📬 Recibido',
        'incorrecto': '❌ Pieza Incorrecta (WPB)',  # NUEVO
        'danado': '⚠️ Pieza Dañada (DOA)',          # NUEVO
    }
    
    border_class = ''
    if seguimiento.estado == 'recibido':
        border_class = 'border-success'
    elif seguimiento.estado in ['incorrecto', 'danado']:  # NUEVO: Borde rojo para problemas
        border_class = 'border-danger'
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
                ''' if seguimiento.estado not in ['recibido', 'incorrecto', 'danado'] else ''}
                
                <!-- Fila 2: Reportar problemas con pieza recibida (NUEVO Nov 2025) -->
                {f'''
                <div class="btn-group btn-group-sm w-100 mb-2" role="group">
                    <button type="button" class="btn btn-outline-danger" onclick="marcarIncorrecto({seguimiento.id})" title="La pieza recibida es incorrecta">
                        ❌ Pieza Incorrecta
                    </button>
                    <button type="button" class="btn btn-outline-warning" onclick="marcarDanado({seguimiento.id})" title="La pieza recibida está dañada o no funciona">
                        ⚠️ Pieza Dañada
                    </button>
                </div>
                ''' if seguimiento.estado == 'recibido' else ''}
                
                <!-- Fila 3: Editar, Eliminar y Reenviar -->
                <div class="btn-group btn-group-sm w-100" role="group">
                    <button type="button" class="btn btn-outline-primary" onclick="editarSeguimiento({seguimiento.id})" title="Editar">
                        📝 Editar
                    </button>
                    <button type="button" class="btn btn-outline-danger" onclick="eliminarSeguimiento({seguimiento.id})" title="Eliminar">
                        🗑️ Eliminar
                    </button>
                    {f'<button type="button" class="btn btn-outline-info" onclick="reenviarNotificacion({seguimiento.id})" title="Reenviar notificación al técnico">📧 Reenviar</button>' if seguimiento.estado == 'recibido' else ''}
                </div>
            </div>
        </div>
    </div>
    '''
    
    return html.strip()


def _enviar_notificacion_pieza_recibida(orden, seguimiento):
    """
    Envía email al técnico notificando que una pieza fue recibida
    
    RETORNA:
    dict con 'success': True/False, 'message': str, 'destinatarios': list
    
    Args:
        orden (OrdenServicio): Orden de servicio
        seguimiento (SeguimientoPieza): Seguimiento de la pieza recibida
    
    Returns:
        dict: Estado del envío con detalles
            {
                'success': True,
                'message': 'Email enviado correctamente',
                'destinatarios': ['tecnico@sic.com', 'jefe@sic.com'],
                'destinatarios_copia': ['calidad@sic.com']
            }
    """
    from django.core.mail import EmailMessage
    from django.conf import settings
    import os
    
    try:
        # =================================================================
        # VALIDACIÓN 1: Verificar que hay técnico asignado con email
        # =================================================================
        if not orden.tecnico_asignado_actual:
            return {
                'success': False,
                'message': '⚠️ La orden no tiene técnico asignado',
                'destinatarios': [],
                'destinatarios_copia': []
            }
        
        if not orden.tecnico_asignado_actual.email:
            return {
                'success': False,
                'message': f'⚠️ El técnico {orden.tecnico_asignado_actual.nombre_completo} no tiene email configurado',
                'destinatarios': [],
                'destinatarios_copia': []
            }
        
        # =================================================================
        # CONSTRUCCIÓN DE DESTINATARIOS
        # =================================================================
        destinatarios_principales = [orden.tecnico_asignado_actual.email]
        destinatarios_copia = []
        
        # Agregar jefe directo del técnico (si existe y tiene email)
        if (orden.tecnico_asignado_actual.jefe_directo and 
            orden.tecnico_asignado_actual.jefe_directo.email):
            destinatarios_copia.append(orden.tecnico_asignado_actual.jefe_directo.email)
        
        # IMPORTANTE: Agregar Jefe de Calidad desde .env
        # Este email SIEMPRE debe estar en copia
        jefe_calidad_email = config('JEFE_CALIDAD_EMAIL', default='').strip()
        if jefe_calidad_email:
            # Evitar duplicados (por si el jefe directo es el mismo que el jefe de calidad)
            if jefe_calidad_email not in destinatarios_copia:
                destinatarios_copia.append(jefe_calidad_email)
                print(f"🔔 Agregando Jefe de Calidad en CC: {jefe_calidad_email}")
        else:
            print("⚠️ ADVERTENCIA: JEFE_CALIDAD_EMAIL no está configurado en .env")
        
        # =================================================================
        # CONSTRUCCIÓN DEL EMAIL
        # =================================================================
        # Obtener nombre del técnico (solo primer nombre)
        nombre_tecnico = orden.tecnico_asignado_actual.nombre_completo.split()[0]
        
        # Obtener información del equipo
        detalle = orden.detalle_equipo
        orden_cliente = detalle.orden_cliente if detalle.orden_cliente else 'Sin orden de cliente'
        
        # =================================================================
        # CONSULTAR PIEZAS PENDIENTES DE OTROS PROVEEDORES
        # =================================================================
        # NUEVA FUNCIONALIDAD (Octubre 2025):
        # Consultar TODOS los seguimientos de la misma cotización
        # y filtrar solo los que NO estén recibidos (estados pendientes)
        from django.utils import timezone
        
        cotizacion = seguimiento.cotizacion
        seguimientos_pendientes = cotizacion.seguimientos_piezas.exclude(
            estado='recibido'
        ).exclude(
            id=seguimiento.id  # Excluir el seguimiento actual (que acaba de ser recibido)
        )
        
        # Construir sección de piezas pendientes si existen
        seccion_piezas_pendientes = ""
        
        if seguimientos_pendientes.exists():
            seccion_piezas_pendientes = "\n\n⚠️ PIEZAS PENDIENTES DE OTROS PROVEEDORES\n"
            seccion_piezas_pendientes += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            hoy = timezone.now().date()
            
            for seg_pendiente in seguimientos_pendientes:
                # Calcular días de retraso (si aplica)
                info_retraso = ""
                if seg_pendiente.fecha_entrega_estimada:
                    if hoy > seg_pendiente.fecha_entrega_estimada:
                        dias_retraso = (hoy - seg_pendiente.fecha_entrega_estimada).days
                        info_retraso = f" ⏰ RETRASADO {dias_retraso} días"
                    else:
                        dias_restantes = (seg_pendiente.fecha_entrega_estimada - hoy).days
                        info_retraso = f" (Estimado en {dias_restantes} días)"
                
                # Obtener estado legible
                estado_display = seg_pendiente.get_estado_display()
                
                # Obtener piezas vinculadas a este seguimiento
                piezas_vinculadas = seg_pendiente.piezas.all()
                if piezas_vinculadas.exists():
                    descripcion_piezas = ", ".join([f"{p.componente.nombre} × {p.cantidad}" for p in piezas_vinculadas])
                else:
                    descripcion_piezas = seg_pendiente.descripcion_piezas
                
                seccion_piezas_pendientes += f"\n• Proveedor: {seg_pendiente.proveedor}\n"
                seccion_piezas_pendientes += f"  Estado: {estado_display}{info_retraso}\n"
                seccion_piezas_pendientes += f"  Descripción: {descripcion_piezas}\n"
                if seg_pendiente.fecha_entrega_estimada:
                    seccion_piezas_pendientes += f"  Fecha estimada: {seg_pendiente.fecha_entrega_estimada.strftime('%d/%m/%Y')}\n"
            
            seccion_piezas_pendientes += "\n💡 NOTA: Aún hay piezas en camino. Te notificaremos cuando lleguen.\n"
        
        # Construir asunto
        asunto = f'📬 Pieza Recibida - Orden Cliente: {orden_cliente}'
        
        # Construir cuerpo del mensaje
        mensaje = f'''Hola {nombre_tecnico},

Te informamos que ha llegado una pieza para la orden que tienes asignada:

📋 INFORMACIÓN DE LA ORDEN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Orden Cliente: {orden_cliente}
• Orden Interna: {orden.numero_orden_interno}
• Equipo: {detalle.get_tipo_equipo_display()} {detalle.marca} {detalle.modelo}
• N° Serie: {detalle.numero_serie}
• Estado actual: {orden.get_estado_display()}

📦 PIEZA RECIBIDA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Proveedor: {seguimiento.proveedor}
• Descripción: {seguimiento.descripcion_piezas}
• Fecha de recepción: {seguimiento.fecha_entrega_real.strftime('%d/%m/%Y')}
{f'• Número de pedido: {seguimiento.numero_pedido}' if seguimiento.numero_pedido else ''}{seccion_piezas_pendientes}

✅ PRÓXIMOS PASOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Recoge la pieza en almacén
2. {"Verifica si puedes proceder con esta pieza o espera las pendientes" if seguimientos_pendientes.exists() else "Actualiza el estado de la orden a 'En reparación'"}
3. Instala y verifica la pieza
4. Actualiza el progreso en el sistema

---
Sistema de Servicio Técnico SIC
Este es un mensaje automático. Si tienes dudas, contacta al responsable del seguimiento.
Hecho por Jorge Magos todos los derechos reservados.
'''
        
        # =================================================================
        # ENVÍO DEL EMAIL
        # =================================================================
        # Usar remitente personalizado para Servicio Técnico (si existe)
        # Si no existe, usar el remitente por defecto del sistema
        # IMPORTANTE: Usar config() de python-decouple, NO os.getenv()
        # os.getenv() solo lee variables del sistema, NO del archivo .env
        from_email = config('SERVICIO_TECNICO_FROM_EMAIL', default=settings.DEFAULT_FROM_EMAIL)
        
        email = EmailMessage(
            subject=asunto,
            body=mensaje,
            from_email=from_email,
            to=destinatarios_principales,
            cc=destinatarios_copia if destinatarios_copia else None,
        )
        
        email.send(fail_silently=False)
        
        # Log exitoso
        print(f"✅ Email enviado correctamente")
        print(f"   TO: {', '.join(destinatarios_principales)}")
        if destinatarios_copia:
            print(f"   CC: {', '.join(destinatarios_copia)}")
        
        return {
            'success': True,
            'message': 'Email enviado correctamente',
            'destinatarios': destinatarios_principales,
            'destinatarios_copia': destinatarios_copia
        }
    
    except Exception as e:
        # Log de error
        print(f"❌ Error al enviar email de notificación: {str(e)}")
        
        return {
            'success': False,
            'message': f'Error al enviar email: {str(e)}',
            'destinatarios': [],
            'destinatarios_copia': [],
            'error_detalle': str(e)
        }


# ============================================================================
# VISTAS AJAX PARA VENTA MOSTRADOR - FASE 3
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.add_ventamostrador')
@require_http_methods(["POST"])
def crear_venta_mostrador(request, orden_id):
    """
    Crea una nueva venta mostrador asociada a una orden.

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
@permission_required_with_message('servicio_tecnico.add_piezaventamostrador')
@require_http_methods(["POST"])
def agregar_pieza_venta_mostrador(request, orden_id):
    """
    Agrega una nueva pieza a una venta mostrador existente.

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
@permission_required_with_message('servicio_tecnico.change_piezaventamostrador')
@require_http_methods(["POST"])
def editar_pieza_venta_mostrador(request, pieza_id):
    """
    Edita una pieza de venta mostrador existente.

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
@permission_required_with_message('servicio_tecnico.delete_piezaventamostrador')
@require_http_methods(["POST"])
def eliminar_pieza_venta_mostrador(request, pieza_id):
    """
    Elimina una pieza de venta mostrador.

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

        tarea = enviar_correo_rhitso_task.delay(
            orden_id=orden_id,
            destinatarios_principales=destinatarios_principales,
            copia_empleados=copia_empleados,
            usuario_id=usuario_id,
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
        
        # =======================================================================
        # PASO 4: DISPARAR TAREA CELERY EN SEGUNDO PLANO
        # =======================================================================
        usuario_id = request.user.pk if request.user.is_authenticated else None
        
        # Convertir IDs a lista de strings (JSON serializable)
        imagenes_ids_str = [str(i) for i in imagenes_ids]
        
        tarea = enviar_imagenes_cliente_task.delay(
            orden_id=orden_id,
            imagenes_ids=imagenes_ids_str,
            destinatarios_copia=destinatarios_copia,
            mensaje_personalizado=mensaje_personalizado,
            usuario_id=usuario_id,
        )
        
        # ── Disparar envío de enlace de seguimiento (solo fuera de garantía) ──
        if orden.es_fuera_garantia:
            from .tasks import enviar_seguimiento_cliente_task
            enviar_seguimiento_cliente_task.delay(
                orden_id=orden_id,
                usuario_id=usuario_id,
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

        tarea = enviar_imagenes_egreso_cliente_task.delay(
            orden_id=orden_id,
            destinatarios_copia=destinatarios_copia,
            usuario_id=usuario_id,
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
    # =======================================================================
    # PASO 1: CONSULTA OPTIMIZADA DE CANDIDATOS RHITSO
    # =======================================================================

    # Esto evita el "N+1 problem" (hacer una consulta por cada relación)
    candidatos_rhitso = OrdenServicio.objects.filter(
        es_candidato_rhitso=True
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
    candidatos_rhitso = OrdenServicio.objects.filter(
        es_candidato_rhitso=True
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
        calcular_metricas_por_responsable
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
                periodo=periodo
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
# API ENDPOINT: AUTOCOMPLETADO DE ÓRDENES PARA BÚSQUEDA INTELIGENTE
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
@require_http_methods(["GET"])
def api_buscar_ordenes_autocomplete(request):
    """
    API endpoint para autocompletado de búsqueda en lista de órdenes.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Este endpoint recibe lo que el usuario va tecleando en el buscador
    y devuelve las órdenes que coinciden, mostrando la orden del cliente
    y el service tag como complemento. Responde en formato JSON para
    que el frontend pueda mostrar las sugerencias sin recargar la página.
    
    Parámetros GET:
        q (str): Texto de búsqueda (mínimo 2 caracteres)
        tipo (str): 'activas' o 'finalizadas' para filtrar según la vista
    
    Returns:
        JsonResponse con lista de coincidencias (máximo 10)
    """
    query = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', 'activas').strip()
    
    # Requerir mínimo 2 caracteres para buscar
    if len(query) < 2:
        return JsonResponse({'resultados': []})
    
    # Construir queryset base según el tipo de vista
    if tipo == 'finalizadas':
        ordenes = OrdenServicio.objects.filter(
            estado__in=['entregado', 'cancelado']
        )
    else:
        ordenes = OrdenServicio.objects.exclude(
            estado__in=['entregado', 'cancelado']
        )
    
    # Aplicar filtro de búsqueda en los 3 campos relevantes
    ordenes = ordenes.filter(
        Q(detalle_equipo__orden_cliente__icontains=query) |
        Q(detalle_equipo__numero_serie__icontains=query) |
        Q(numero_orden_interno__icontains=query)
    ).select_related(
        'detalle_equipo', 'sucursal'
    ).order_by('-fecha_ingreso')[:10]
    
    # Construir respuesta JSON con la información relevante
    resultados = []
    for orden in ordenes:
        detalle = orden.detalle_equipo
        resultados.append({
            'id': orden.id,
            'orden_cliente': detalle.orden_cliente or '',
            'numero_serie': detalle.numero_serie or '',
            'numero_orden_interno': orden.numero_orden_interno or '',
            'marca': detalle.marca or '',
            'modelo': detalle.modelo or '',
            'estado': orden.get_estado_display(),
            'url_detalle': reverse('servicio_tecnico:detalle_orden', args=[orden.id]),
        })
    
    return JsonResponse({'resultados': resultados})


# ============================================================================
# API ENDPOINT: AUTOCOMPLETADO PARA SELECTOR DE ORDEN ORIGINAL (REINGRESO)
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
@require_http_methods(["GET"])
def api_buscar_ordenes_reingreso(request):
    """
    API endpoint para el selector inteligente de "Orden Original" en el módulo
    de Reingreso de la vista detalle_orden.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Cuando el usuario marca una orden como "Reingreso", necesita indicar cuál fue
    la orden original (la primera vez que se reparó ese equipo). Esta API permite
    buscar esa orden original de forma inteligente, mostrando sugerencias mientras
    el usuario escribe la orden del cliente, el número de serie, etc.

    Solo busca en órdenes con estado='entregado' porque:
    - Un reingreso implica que el equipo YA fue reparado y devuelto al cliente
    - Si el equipo sigue en servicio activo, no puede ser una "orden original" de un reingreso

    Parámetros GET:
        q (str): Texto de búsqueda (mínimo 2 caracteres) — para búsqueda typeahead
        id (int): ID exacto de una orden — para restaurar la selección guardada
        excluir (int): ID de la orden actual (para no mostrarse a sí misma)

    Returns:
        JsonResponse con lista de coincidencias (máximo 15)
        Cada resultado incluye: id, orden_cliente, numero_serie, numero_orden_interno,
        marca, modelo, fecha_entrega (para identificar cuándo fue entregada)
    """
    query = request.GET.get('q', '').strip()
    buscar_por_id = request.GET.get('id', '').strip()
    excluir_id = request.GET.get('excluir', '').strip()

    # ── MODO RESTAURACIÓN: búsqueda por ID exacto ──────────────────────────────
    # Cuando el usuario ya guardó la selección, al recargar la página llamamos
    # a este API con ?id=<pk> para recuperar los datos del chip sin necesidad de
    # hacer una búsqueda de texto (que fallaría con un número como "47").
    if buscar_por_id and buscar_por_id.isdigit():
        try:
            orden = OrdenServicio.objects.select_related('detalle_equipo').get(
                pk=int(buscar_por_id)
            )
            detalle = orden.detalle_equipo
            resultado = {
                'id': orden.id,
                'orden_cliente': detalle.orden_cliente or '',
                'numero_serie': detalle.numero_serie or '',
                'numero_orden_interno': orden.numero_orden_interno or '',
                'marca': detalle.marca or '',
                'modelo': detalle.modelo or '',
                'fecha_entrega': orden.fecha_entrega.strftime('%d/%m/%Y') if orden.fecha_entrega else '',
            }
            return JsonResponse({'resultados': [resultado]})
        except OrdenServicio.DoesNotExist:
            return JsonResponse({'resultados': []})

    # ── MODO BÚSQUEDA: typeahead por texto ────────────────────────────────────
    # Requerir mínimo 2 caracteres para buscar
    if len(query) < 2:
        return JsonResponse({'resultados': []})

    # Base: solo órdenes entregadas (la única fuente válida para "orden original")
    ordenes = OrdenServicio.objects.filter(estado='entregado')

    # Excluir la orden actual para evitar auto-referencia
    if excluir_id and excluir_id.isdigit():
        ordenes = ordenes.exclude(pk=int(excluir_id))

    # Filtro de búsqueda en los campos más relevantes para identificar una orden
    ordenes = ordenes.filter(
        Q(detalle_equipo__orden_cliente__icontains=query) |
        Q(detalle_equipo__numero_serie__icontains=query) |
        Q(numero_orden_interno__icontains=query) |
        Q(detalle_equipo__marca__icontains=query) |
        Q(detalle_equipo__modelo__icontains=query)
    ).select_related(
        'detalle_equipo', 'sucursal'
    ).order_by('-fecha_entrega')[:15]

    # Construir respuesta JSON con información suficiente para identificar el equipo
    resultados = []
    for orden in ordenes:
        detalle = orden.detalle_equipo
        resultados.append({
            'id': orden.id,
            'orden_cliente': detalle.orden_cliente or '',
            'numero_serie': detalle.numero_serie or '',
            'numero_orden_interno': orden.numero_orden_interno or '',
            'marca': detalle.marca or '',
            'modelo': detalle.modelo or '',
            'fecha_entrega': orden.fecha_entrega.strftime('%d/%m/%Y') if orden.fecha_entrega else '',
        })

    return JsonResponse({'resultados': resultados})


# ============================================================================
# API ENDPOINT: BUSCAR ORDEN POR NÚMERO DE SERIE
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
@require_http_methods(["GET"])
def api_buscar_orden_por_serie(request):
    """
    API para buscar órdenes de servicio por número de serie o orden del cliente.

    Este endpoint busca órdenes de servicio de manera inteligente:

    USO:
    /servicio-tecnico/api/buscar-orden-por-serie/?numero_serie=ABC123
    /servicio-tecnico/api/buscar-orden-por-serie/?orden_cliente=OOW-12345
    """
    from django.db.models import Q
    
    # Obtener parámetros de búsqueda
    numero_serie = request.GET.get('numero_serie', '').strip().upper()
    orden_cliente = request.GET.get('orden_cliente', '').strip().upper()
    
    # Validar que al menos uno de los parámetros venga
    if not numero_serie and not orden_cliente:
        return JsonResponse({
            'success': False,
            'error': 'Debe proporcionar al menos número de serie o orden del cliente'
        })
    
    # ========================================================================
    # LÓGICA DE BÚSQUEDA INTELIGENTE
    # ========================================================================
    
    # Lista de palabras que indican que el número de serie no es válido
    SERIES_INVALIDAS = [
        'NO VISIBLE',
        'NO IDENTIFICADO',
        'NO LEGIBLE',
        'SIN SERIE',
        'N/A',
        'NA',
        'NO APLICA',
        'DESCONOCIDO',
        'NO SE VE',
    ]
    
    # Determinar si el número de serie es inválido
    serie_invalida = any(keyword in numero_serie for keyword in SERIES_INVALIDAS) if numero_serie else True
    
    try:
        # CASO 1: Si la serie es inválida o no existe, buscar por orden_cliente
        if serie_invalida and orden_cliente:
            detalle = DetalleEquipo.objects.select_related('orden').get(
                orden_cliente__iexact=orden_cliente
            )
        
        # CASO 2: Si hay orden_cliente explícita, buscar por ella (prioridad)
        elif orden_cliente and not numero_serie:
            detalle = DetalleEquipo.objects.select_related('orden').get(
                orden_cliente__iexact=orden_cliente
            )
        
        # CASO 3: Buscar por número de serie normal
        elif numero_serie and not serie_invalida:
            detalle = DetalleEquipo.objects.select_related('orden').get(
                numero_serie__iexact=numero_serie
            )
        
        # CASO 4: Última opción - buscar por cualquiera de los dos
        else:
            detalle = DetalleEquipo.objects.select_related('orden').filter(
                Q(numero_serie__iexact=numero_serie) | Q(orden_cliente__iexact=orden_cliente)
            ).first()
            
            if not detalle:
                raise DetalleEquipo.DoesNotExist
        
        # Si encontramos el detalle, extraer información de la orden
        orden = detalle.orden
        
        # Preparar respuesta con todos los datos relevantes
        return JsonResponse({
            'success': True,
            'encontrado': True,
            'orden': {
                # Identificadores
                'id': orden.id,
                'numero_orden_interno': orden.numero_orden_interno,
                'orden_cliente': detalle.orden_cliente,
                
                # Información del equipo
                'tipo_equipo': detalle.tipo_equipo,
                'tipo_equipo_display': detalle.get_tipo_equipo_display(),
                'marca': detalle.marca,
                'modelo': detalle.modelo,
                'numero_serie': detalle.numero_serie,
                'gama': detalle.gama,
                'gama_display': detalle.get_gama_display(),
                
                # Información de la orden
                'fecha_ingreso': orden.fecha_ingreso.strftime('%d/%m/%Y %H:%M'),
                'fecha_ingreso_corta': orden.fecha_ingreso.strftime('%d/%m/%Y'),
                'estado': orden.estado,
                'estado_display': orden.get_estado_display(),
                'dias_en_servicio': orden.dias_en_servicio,
                
                # Responsables
                'tecnico_responsable': orden.tecnico_asignado_actual.nombre_completo,
                'tecnico_id': orden.tecnico_asignado_actual.id,
                'responsable_seguimiento': orden.responsable_seguimiento.nombre_completo if orden.responsable_seguimiento else 'Sin asignar',
                'responsable_id': orden.responsable_seguimiento.id if orden.responsable_seguimiento else 0,
                
                # Ubicación
                'sucursal': orden.sucursal.nombre,
                'sucursal_id': orden.sucursal.id,
                
                # Información adicional
                'falla_principal': detalle.falla_principal,
                'equipo_enciende': detalle.equipo_enciende,
                'es_mis': detalle.es_mis,
                'es_reingreso': orden.es_reingreso,
                'es_candidato_rhitso': orden.es_candidato_rhitso,
            },
            'mensaje': f'Orden {orden.numero_orden_interno} encontrada exitosamente'
        })
        
    except DetalleEquipo.DoesNotExist:
        # No se encontró ninguna orden con los criterios proporcionados
        criterio_busqueda = f"número de serie '{numero_serie}'" if numero_serie and not serie_invalida else f"orden del cliente '{orden_cliente}'"
        
        return JsonResponse({
            'success': True,
            'encontrado': False,
            'orden': None,
            'mensaje': f'No se encontró ninguna orden con {criterio_busqueda} en el sistema'
        })
        
    except DetalleEquipo.MultipleObjectsReturned:
        # Se encontraron múltiples órdenes (no debería pasar, pero por si acaso)
        return JsonResponse({
            'success': False,
            'encontrado': False,
            'orden': None,
            'error': f'Se encontraron múltiples órdenes con los criterios proporcionados. Por favor, sea más específico.'
        })
        
    except Exception as e:
        # Error inesperado
        return JsonResponse({
            'success': False,
            'encontrado': False,
            'orden': None,
            'error': f'Error al buscar la orden: {str(e)}'
        })


# ============================================================================
# API ENDPOINT: BUSCAR MODELOS POR MARCA (AUTOCOMPLETADO)
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_referenciagamaequipo')
@require_http_methods(["GET"])
def api_buscar_modelos_por_marca(request):
    """
    API endpoint para buscar modelos de equipos disponibles según la marca.
    
    Este endpoint se usa para el autocompletado del campo "Modelo" en los
    formularios de creación de órdenes. Busca en la tabla ReferenciaGamaEquipo
    y retorna los modelos disponibles para la marca seleccionada.
    
    PARÁMETROS GET:
    - marca: str (requerido) - Marca del equipo (DELL, LENOVO, HP, etc.)
    - q: str (opcional) - Término de búsqueda para filtrar modelos (Select2 usa 'q')
    
    RETORNA:
    JSON con formato compatible con Select2:
    {
        'results': [
            {'id': 'Inspiron 3000', 'text': 'Inspiron 3000 - Gama Baja', 'gama': 'baja'},
            {'id': 'XPS 13', 'text': 'XPS 13 - Gama Alta', 'gama': 'alta'},
            ...
        ]
    }
    
    EJEMPLO DE USO:
    /servicio-tecnico/api/buscar-modelos-por-marca/?marca=DELL&q=inspiron
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    - Esta función se ejecuta cuando el usuario escribe en el campo "Modelo"
    - Busca en la base de datos los modelos que coincidan con la marca seleccionada
    - Retorna un JSON que Select2 puede entender y mostrar como opciones
    - Si el usuario escribe algo (parámetro 'q'), filtra los resultados
    """
    from .models import ReferenciaGamaEquipo
    
    # Obtener parámetros de la URL
    marca = request.GET.get('marca', '').strip()
    query = request.GET.get('q', '').strip()  # Select2 usa 'q' por defecto para el término de búsqueda
    
    # Validar que la marca esté presente
    if not marca:
        return JsonResponse({
            'results': [],
            'mensaje': 'Debe seleccionar una marca primero'
        })
    
    try:
        # ====================================================================
        # BÚSQUEDA EN LA BASE DE DATOS
        # ====================================================================
        
        # Buscar referencias de gama para la marca seleccionada
        # iexact = case-insensitive exact match (DELL = dell = DeLl)
        referencias = ReferenciaGamaEquipo.objects.filter(
            marca__iexact=marca,
            activo=True
        )
        
        # Si hay término de búsqueda, filtrar por modelo_base
        # icontains = case-insensitive contains (busca coincidencias parciales)
        if query:
            referencias = referencias.filter(
                modelo_base__icontains=query
            )
        
        # Ordenar alfabéticamente por modelo
        referencias = referencias.order_by('modelo_base')
        
        # ====================================================================
        # FORMATEAR RESULTADOS PARA SELECT2
        # ====================================================================
        
        # Select2 espera un formato específico:
        # - 'id': El valor que se guardará en el formulario
        # - 'text': El texto que se mostrará al usuario
        resultados = []
        
        for ref in referencias:
            resultados.append({
                'id': ref.modelo_base,  # Valor que se guardará
                'text': ref.modelo_base,  # Solo el nombre del modelo (sin gama)
                'gama': ref.gama,  # Información adicional (opcional, no se muestra)
                'rango_costo': f"${ref.rango_costo_min} - ${ref.rango_costo_max}"  # Info adicional
            })
        
        # Retornar JSON en formato Select2
        return JsonResponse({
            'results': resultados,
            'total': len(resultados)
        })
        
    except Exception as e:
        # Si hay algún error, retornar respuesta vacía con mensaje de error
        return JsonResponse({
            'results': [],
            'error': f'Error al buscar modelos: {str(e)}'
        })


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


# ==========================================
# VISTA DE ACCESO DENEGADO
# ==========================================

@login_required
def acceso_denegado(request):
    """
    Vista para mostrar página de acceso denegado cuando el usuario no tiene permisos.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista se muestra cuando un usuario intenta acceder a una funcionalidad
    para la cual no tiene los permisos necesarios según su grupo/rol.
    
    Args:
        request: Objeto HttpRequest con los parámetros GET
            - mensaje: Mensaje personalizado de error
            - permiso: Nombre del permiso requerido
    
    Returns:
        HttpResponse: Renderiza el template acceso_denegado.html
    """
    mensaje = request.GET.get('mensaje', 'No tienes permisos para acceder a esta sección.')
    permiso = request.GET.get('permiso', 'N/A')
    
    # Obtener grupos del usuario para mostrarle sus roles actuales
    grupos = request.user.groups.all()
    
    context = {
        'mensaje': mensaje,
        'permiso_requerido': permiso,
        'grupos_usuario': grupos,
    }
    
    return render(request, 'servicio_tecnico/acceso_denegado.html', context)


# ========================================================================
# API: ACTUALIZAR EMAIL DEL CLIENTE (Febrero 2026)
# ========================================================================
@login_required
@require_http_methods(["POST"])
def actualizar_email_cliente(request, detalle_id):
    """
    Vista AJAX para actualizar el email del cliente desde el modal de diagnóstico.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    - Esta vista recibe un POST con el nuevo email del cliente
    - Valida que el email sea válido y lo guarda en la base de datos
    - Retorna un JSON con el resultado (éxito o error)
    - Se usa desde el botón "Editar" en la sección de destinatario del modal
    
    Args:
        request: Petición HTTP con el nuevo email en el body
        detalle_id: ID del DetalleEquipo a actualizar
        
    Returns:
        JsonResponse: JSON con success=True/False y mensaje
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        detalle = get_object_or_404(DetalleEquipo, pk=detalle_id)
        
        # Obtener el nuevo email del body (JSON)
        try:
            body = json.loads(request.body)
            nuevo_email = body.get('email', '').strip()
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Formato de datos inválido.'
            }, status=400)
        
        # Validar que el email no esté vacío
        if not nuevo_email:
            return JsonResponse({
                'success': False,
                'error': 'El email no puede estar vacío.'
            }, status=400)
        
        # Validar formato básico del email
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_email(nuevo_email)
        except DjangoValidationError:
            return JsonResponse({
                'success': False,
                'error': 'El formato del email no es válido. Ejemplo: usuario@dominio.com'
            }, status=400)
        
        # Validar que no sea el email por defecto
        if nuevo_email == 'cliente@ejemplo.com':
            return JsonResponse({
                'success': False,
                'error': 'No puedes usar el email por defecto. Ingresa un email real.'
            }, status=400)
        
        # Guardar el email anterior para el log
        email_anterior = detalle.email_cliente
        
        # Actualizar el email
        detalle.email_cliente = nuevo_email
        detalle.save(update_fields=['email_cliente'])
        
        # Log del cambio
        nombre_empleado = ''
        if hasattr(request.user, 'empleado') and request.user.empleado:
            nombre_empleado = request.user.empleado.nombre_completo
        
        logger.info(
            f'Email del cliente actualizado por {nombre_empleado} ({request.user.username}): '
            f'"{email_anterior}" → "{nuevo_email}" | '
            f'Orden: {detalle.orden.numero_orden_interno if hasattr(detalle, "orden") else "N/A"} | '
            f'DetalleEquipo PK: {detalle.pk}'
        )
        
        return JsonResponse({
            'success': True,
            'mensaje': f'Email actualizado correctamente.',
            'email': nuevo_email,
            'email_anterior': email_anterior,
        })
        
    except Exception as e:
        logger.error(f'Error al actualizar email del cliente: {e}', exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Error inesperado: {str(e)}'
        }, status=500)


# ============================================================================
# CONCENTRADO SEMANAL DE CIS
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
def concentrado_semanal(request):
    """
    Página principal del Concentrado Semanal de CIS.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista genera el reporte semanal de ingresos, asignaciones y egresos
    de equipos en el CIS. El usuario puede navegar entre semanas usando el
    parámetro GET 'semana' (formato ISO: 'YYYY-WNN', ej: '2025-W18').

    También calcula:
      - Los gráficos de tendencia anual de ingresos y egresos por semana
      - La lista de sucursales para el filtro

    Parámetros GET:
        semana (str): Semana ISO seleccionada, ej: '2025-W18'. Default: semana actual.
        sucursal_id (int): Filtrar por sucursal. Default: todas.

    Returns:
        HttpResponse: Template con el concentrado completo
    """
    import json as _json
    import plotly.graph_objects as go
    import plotly.io as pio
    from datetime import date
    from .concentrado_semanal import (
        obtener_semana_actual,
        lunes_desde_numero_semana,
        obtener_concentrado_semanal,
        obtener_tendencia_semanal,
        DIAS_SEMANA,
        SITIOS,
        TIPOS_EQUIPO,
    )

    # ------------------------------------------------------------------
    # Leer parámetros GET
    # ------------------------------------------------------------------
    semana_param = request.GET.get('semana', '')
    sucursal_param = request.GET.get('sucursal_id', None)

    # sucursal_id puede ser:
    #   - None / '' → todas las sucursales
    #   - 'grupo_cis'     → Drop Off + Satélite (se resuelve a lista de IDs más abajo)
    #   - 'grupo_foranea' → MTY + GDL (ídem)
    #   - Un número entero → sucursal individual
    sucursal_id = None          # valor que se pasa a las funciones de negocio (int o None)
    sucursal_ids_grupo = None   # lista de IDs cuando es un grupo

    if sucursal_param in ('grupo_cis', 'grupo_foranea'):
        # Se resuelve después de cargar las sucursales (ver más abajo)
        sucursal_id = None
    elif sucursal_param:
        try:
            sucursal_id = int(sucursal_param)
        except ValueError:
            sucursal_id = None

    # ------------------------------------------------------------------
    # Determinar la semana seleccionada
    # ------------------------------------------------------------------
    lunes_seleccionado = obtener_semana_actual()

    if semana_param:
        # Formato esperado: "2025-W18"
        try:
            partes = semana_param.split('-W')
            año_param = int(partes[0])
            num_semana_param = int(partes[1])
            lunes_seleccionado = lunes_desde_numero_semana(año_param, num_semana_param)
        except (ValueError, IndexError):
            lunes_seleccionado = obtener_semana_actual()

    # ------------------------------------------------------------------
    # Lista de sucursales para el filtro + resolución de grupos
    # (debe hacerse ANTES de llamar a las funciones del concentrado)
    # ------------------------------------------------------------------
    sucursales = Sucursal.objects.filter(activa=True).order_by('nombre')

    # Clasificamos cada sucursal en un grupo según su nombre.
    # Grupo "CIS"     → nombre contiene 'drop' o 'satelit'
    # Grupo "Foránea" → cualquier otra (MTY, GDL, etc.)
    grupo_cis_ids = []
    grupo_foranea_ids = []
    for suc in sucursales:
        nombre_lower = suc.nombre.lower()
        if 'drop' in nombre_lower or 'satelit' in nombre_lower:
            grupo_cis_ids.append(suc.id)
        else:
            grupo_foranea_ids.append(suc.id)

    # Resolver grupos: convertir 'grupo_cis'/'grupo_foranea' a lista de IDs
    if sucursal_param == 'grupo_cis':
        sucursal_ids_grupo = grupo_cis_ids
    elif sucursal_param == 'grupo_foranea':
        sucursal_ids_grupo = grupo_foranea_ids

    # Estructura de grupos para renderizar optgroup en el template
    grupos_sucursales = []
    if grupo_cis_ids:
        grupos_sucursales.append({
            'label': 'CIS (Drop Off + Satélite)',
            'value': 'grupo_cis',
        })
    if grupo_foranea_ids:
        grupos_sucursales.append({
            'label': 'Foráneas (MTY + GDL)',
            'value': 'grupo_foranea',
        })

    # ------------------------------------------------------------------
    # Calcular datos del concentrado
    # ------------------------------------------------------------------
    datos = obtener_concentrado_semanal(
        lunes_seleccionado,
        sucursal_id=sucursal_id,
        sucursal_ids=sucursal_ids_grupo,
    )

    # ------------------------------------------------------------------
    # Calcular semana anterior y siguiente para navegación
    # ------------------------------------------------------------------
    from datetime import timedelta
    lunes_anterior = lunes_seleccionado - timedelta(days=7)
    lunes_siguiente = lunes_seleccionado + timedelta(days=7)

    def _formatear_semana_iso(lunes):
        num = lunes.isocalendar()[1]
        año = lunes.year
        return f"{año}-W{num:02d}"

    semana_anterior_iso = _formatear_semana_iso(lunes_anterior)
    semana_siguiente_iso = _formatear_semana_iso(lunes_siguiente)
    semana_actual_iso = _formatear_semana_iso(lunes_seleccionado)

    # ------------------------------------------------------------------
    # Gráficos de tendencia anual (Plotly)
    # ------------------------------------------------------------------
    año_actual = lunes_seleccionado.year
    tendencia = obtener_tendencia_semanal(
        año_actual,
        sucursal_id=sucursal_id,
        sucursal_ids=sucursal_ids_grupo,
    )

    # Gráfico de Ingresos por semana
    fig_ingresos = go.Figure()
    fig_ingresos.add_trace(go.Bar(
        x=tendencia['etiquetas'],
        y=tendencia['ingresos'],
        name='Ingresos',
        marker_color='#0d6efd',
        hovertemplate='<b>%{x}</b><br>Ingresos: %{y}<extra></extra>',
    ))
    fig_ingresos.add_trace(go.Scatter(
        x=tendencia['etiquetas'],
        y=tendencia['ingresos'],
        name='Tendencia',
        mode='lines+markers',
        line=dict(color='#0a58ca', width=2),
        marker=dict(size=5),
        hoverinfo='skip',
    ))
    fig_ingresos.update_layout(
        title=dict(text=f'Ingresos de Equipos por Semana — {año_actual}', font=dict(size=14)),
        xaxis_title='Semana',
        yaxis_title='Equipos Ingresados',
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(l=40, r=20, t=60, b=40),
        height=320,
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(showgrid=False, tickangle=-45 if len(tendencia['etiquetas']) > 30 else 0),
        yaxis=dict(showgrid=True, gridcolor='#f0f0f0'),
    )
    # Resaltar la semana seleccionada
    semana_label_actual = f"S{datos['numero_semana']}"
    if semana_label_actual in tendencia['etiquetas']:
        idx = tendencia['etiquetas'].index(semana_label_actual)
        fig_ingresos.add_vline(
            x=idx,
            line_dash='dash',
            line_color='#dc3545',
            annotation_text='Semana actual',
            annotation_position='top right',
            annotation_font_size=10,
        )

    grafico_ingresos_html = pio.to_html(
        fig_ingresos,
        full_html=False,
        include_plotlyjs=False,
        config={'responsive': True, 'displayModeBar': False},
    )

    # Gráfico de Egresos por semana
    fig_egresos = go.Figure()
    fig_egresos.add_trace(go.Bar(
        x=tendencia['etiquetas'],
        y=tendencia['egresos'],
        name='Egresos',
        marker_color='#198754',
        hovertemplate='<b>%{x}</b><br>Egresos: %{y}<extra></extra>',
    ))
    fig_egresos.add_trace(go.Scatter(
        x=tendencia['etiquetas'],
        y=tendencia['egresos'],
        name='Tendencia',
        mode='lines+markers',
        line=dict(color='#146c43', width=2),
        marker=dict(size=5),
        hoverinfo='skip',
    ))
    fig_egresos.update_layout(
        title=dict(text=f'Egresos de Equipos por Semana — {año_actual}', font=dict(size=14)),
        xaxis_title='Semana',
        yaxis_title='Equipos Egresados',
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(l=40, r=20, t=60, b=40),
        height=320,
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(showgrid=False, tickangle=-45 if len(tendencia['etiquetas']) > 30 else 0),
        yaxis=dict(showgrid=True, gridcolor='#f0f0f0'),
    )
    if semana_label_actual in tendencia['etiquetas']:
        fig_egresos.add_vline(
            x=idx,
            line_dash='dash',
            line_color='#dc3545',
            annotation_text='Semana actual',
            annotation_position='top right',
            annotation_font_size=10,
        )

    grafico_egresos_html = pio.to_html(
        fig_egresos,
        full_html=False,
        include_plotlyjs=False,
        config={'responsive': True, 'displayModeBar': False},
    )

    # ------------------------------------------------------------------
    # Construir el contexto para el template
    # ------------------------------------------------------------------
    context = {
        # Datos del concentrado
        **datos,

        # Navegación
        'semana_actual_iso': semana_actual_iso,
        'semana_anterior_iso': semana_anterior_iso,
        'semana_siguiente_iso': semana_siguiente_iso,
        'sucursal_id_seleccionada': sucursal_param,  # puede ser int, 'grupo_cis', 'grupo_foranea' o None
        'sucursales': sucursales,
        'grupos_sucursales': grupos_sucursales,

        # Gráficos Plotly
        'grafico_ingresos_html': grafico_ingresos_html,
        'grafico_egresos_html': grafico_egresos_html,

        # Constantes para el template
        'dias_semana': DIAS_SEMANA,
        'sitios': SITIOS,
        'tipos_equipo': TIPOS_EQUIPO,

        # Metadatos de la página
        'page_title': (
            f'Concentrado Semanal — Semana {datos["numero_semana"]}, {datos["año"]}'
        ),
    }

    return render(request, 'servicio_tecnico/concentrado_semanal.html', context)


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
def exportar_concentrado_excel(request):
    """
    Exporta el concentrado semanal a un archivo Excel (.xlsx) con 4 hojas:
      1. Concentrado Semanal (datos de la semana seleccionada)
      2. Reporte Trimestral (Q1-Q4 del año)
      3. Gráfico de Ingresos por semana
      4. Gráfico de Egresos por semana

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista no renderiza una página HTML. En cambio, genera un archivo Excel
    y lo envía directamente al navegador para descargarlo.
    Usa la misma lógica de 'concentrado_semanal' para obtener los datos,
    y luego llama a las funciones del módulo excel_exporters para crear el Excel.

    Parámetros GET:
        semana (str): Semana ISO (ej: '2025-W18')
        sucursal_id (int): Filtrar por sucursal
        año (int): Año para el reporte trimestral (default: año de la semana)

    Returns:
        HttpResponse: Archivo Excel como descarga
    """
    import openpyxl
    from django.http import HttpResponse
    from .concentrado_semanal import (
        obtener_semana_actual,
        lunes_desde_numero_semana,
        obtener_concentrado_semanal,
        obtener_reporte_trimestral,
        obtener_tendencia_semanal,
        obtener_reporte_mensual,
    )
    from .excel_exporters_concentrado import generar_excel_concentrado

    # Leer parámetros
    semana_param = request.GET.get('semana', '')
    sucursal_id = request.GET.get('sucursal_id', None)
    if sucursal_id:
        try:
            sucursal_id = int(sucursal_id)
        except ValueError:
            sucursal_id = None

    lunes_seleccionado = obtener_semana_actual()
    if semana_param:
        try:
            partes = semana_param.split('-W')
            lunes_seleccionado = lunes_desde_numero_semana(int(partes[0]), int(partes[1]))
        except (ValueError, IndexError):
            lunes_seleccionado = obtener_semana_actual()

    año = lunes_seleccionado.year

    # Obtener datos
    datos_semana = obtener_concentrado_semanal(lunes_seleccionado, sucursal_id=sucursal_id)
    datos_trimestral = obtener_reporte_trimestral(año, sucursal_id=sucursal_id)
    datos_tendencia = obtener_tendencia_semanal(año, sucursal_id=sucursal_id)
    datos_mensual = obtener_reporte_mensual(año, sucursal_id=sucursal_id)

    # Generar el archivo Excel
    wb = generar_excel_concentrado(datos_semana, datos_trimestral, datos_tendencia, datos_mensual)

    # Preparar respuesta HTTP para descarga
    num_semana = datos_semana['numero_semana']
    filename = f'Concentrado_Semanal_S{num_semana:02d}_{año}.xlsx'

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)

    return response


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
def exportar_concentrado_pdf(request):
    """
    Exporta el concentrado semanal a un PDF con las 3 tablas del reporte.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Usa la librería ReportLab para generar un PDF en orientación horizontal
    (landscape) con las 3 tablas del concentrado semanal:
      1. Ingreso de Equipos
      2. Asignación a Ingeniería
      3. Egreso de Equipos

    Parámetros GET:
        semana (str): Semana ISO (ej: '2025-W18')
        sucursal_id (int): Filtrar por sucursal

    Returns:
        HttpResponse: Archivo PDF como descarga
    """
    from .concentrado_semanal import (
        obtener_semana_actual,
        lunes_desde_numero_semana,
        obtener_concentrado_semanal,
        DIAS_SEMANA,
        SITIOS,
        TIPOS_EQUIPO,
    )
    from .pdf_concentrado import generar_pdf_concentrado

    # Leer parámetros
    semana_param = request.GET.get('semana', '')
    sucursal_id = request.GET.get('sucursal_id', None)
    if sucursal_id:
        try:
            sucursal_id = int(sucursal_id)
        except ValueError:
            sucursal_id = None

    lunes_seleccionado = obtener_semana_actual()
    if semana_param:
        try:
            partes = semana_param.split('-W')
            lunes_seleccionado = lunes_desde_numero_semana(int(partes[0]), int(partes[1]))
        except (ValueError, IndexError):
            lunes_seleccionado = obtener_semana_actual()

    # Obtener datos
    datos = obtener_concentrado_semanal(lunes_seleccionado, sucursal_id=sucursal_id)

    # Generar PDF
    pdf_buffer = generar_pdf_concentrado(datos)

    # Preparar respuesta
    num_semana = datos['numero_semana']
    año = datos['año']
    filename = f'Concentrado_Semanal_S{num_semana:02d}_{año}.pdf'

    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


# ============================================================================
# VISTA: confirmar_feedback_satisfaccion
# El operador acepta o cancela el envío de la encuesta de satisfacción.
# Se llama vía POST desde el modal en detalle_orden.html.
# ============================================================================

@login_required
@require_http_methods(['POST'])
def confirmar_feedback_satisfaccion(request, feedback_id):
    """
    Recibe la decisión del operador sobre si enviar o no la encuesta de satisfacción.

    Si acepta → encola enviar_feedback_satisfaccion_task.
    Si cancela → no hace nada (el token queda guardado pero sin correo enviado).
    """
    from .models import FeedbackCliente
    from .tasks import enviar_feedback_satisfaccion_task

    feedback = get_object_or_404(FeedbackCliente, pk=feedback_id)
    accion   = request.POST.get('accion', 'cancelar')
    orden_id = feedback.orden.pk

    if accion == 'enviar':
        if feedback.correo_enviado:
            messages.warning(request, '⚠️ La encuesta de satisfacción ya fue enviada anteriormente.')
        else:
            usuario_id = request.user.pk if request.user.is_authenticated else None
            enviar_feedback_satisfaccion_task.delay(feedback_id=feedback.pk, usuario_id=usuario_id)
            messages.success(
                request,
                f'⭐ Encuesta de satisfacción enviada a '
                f'{feedback.orden.detalle_equipo.email_cliente}. '
                f'El cliente tiene 12 días para responder.'
            )
    else:
        messages.info(request, 'ℹ️ Envío de encuesta de satisfacción cancelado.')

    return redirect('servicio_tecnico:detalle_orden', orden_id=orden_id)


# ============================================================================
# VISTA PÚBLICA: feedback_satisfaccion_cliente
# El cliente llena la encuesta desde el link del correo de entrega.
# NO requiere autenticación.
# ============================================================================

@ratelimit(key='ip', rate='20/m', method=['GET', 'POST'])
def feedback_satisfaccion_cliente(request, token):
    """
    Vista pública para la encuesta de satisfacción post-entrega.
    Valida el token, muestra el formulario interactivo y guarda la respuesta.
    """
    from .models import FeedbackCliente
    from .forms import FeedbackSatisfaccionClienteForm

    TEMPLATE = 'servicio_tecnico/feedback_satisfaccion.html'

    # ── Obtener IP para logging de seguridad ──
    _xfwd = request.META.get('HTTP_X_FORWARDED_FOR')
    _ip = _xfwd.split(',')[0].strip() if _xfwd else request.META.get('REMOTE_ADDR')

    # ── Buscar feedback por token y tipo ──────────────────────────────────
    try:
        feedback = FeedbackCliente.objects.select_related(
            'orden__detalle_equipo',
        ).get(token=token, tipo='satisfaccion')
    except FeedbackCliente.DoesNotExist:
        logger.warning(
            "[SEGURIDAD] Feedback satisfacción con token inexistente | IP: %s | token: %s...",
            _ip, token[:8]
        )
        return render(request, TEMPLATE, {'estado': 'invalido'})

    # ── Validar estado del token ──────────────────────────────────────────
    # SEGURIDAD: Mensajes 'ya_respondido' y 'expirado' son seguros aquí porque
    # el atacante necesitaría adivinar un token de 256 bits para llegar a este punto.
    if feedback.utilizado:
        return render(request, TEMPLATE, {'estado': 'ya_respondido'})

    if feedback.esta_expirado:
        return render(request, TEMPLATE, {'estado': 'expirado'})

    orden   = feedback.orden
    detalle = orden.detalle_equipo

    if request.method == 'POST':
        form = FeedbackSatisfaccionClienteForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data

            # ── Honeypot: Si el campo oculto tiene valor, es un bot ──
            if d.get('website'):
                logger.warning(
                    "[SEGURIDAD] Honeypot activado en feedback satisfacción | IP: %s",
                    _ip
                )
                # Simular éxito para no alertar al bot
                return render(request, TEMPLATE, {
                    'estado': 'gracias',
                    'calificacion': 5,
                })

            feedback.calificacion_general  = d['calificacion_general']
            feedback.nps                   = d['nps']
            feedback.recomienda            = d['recomienda']
            feedback.calificacion_atencion = d.get('calificacion_atencion')
            feedback.calificacion_tiempo   = d.get('calificacion_tiempo')
            feedback.comentario_cliente    = d.get('comentario_cliente', '')
            feedback.utilizado             = True
            feedback.fecha_respuesta       = timezone.now()
            feedback.ip_respuesta          = _ip
            feedback.save(update_fields=[
                'calificacion_general', 'nps', 'recomienda',
                'calificacion_atencion', 'calificacion_tiempo',
                'comentario_cliente', 'utilizado', 'fecha_respuesta', 'ip_respuesta',
            ])

            # Notificar a responsable de seguimiento y superusers
            try:
                from notificaciones.utils import notificar_info
                responsable = orden.responsable_seguimiento
                if responsable and responsable.usuario:
                    notificar_info(
                        titulo="Encuesta de satisfacción respondida",
                        mensaje=(
                            f"Orden {orden.numero_orden_interno} — "
                            f"Calificación: {d['calificacion_general']}/5 | "
                            f"NPS: {d['nps']}/10 | "
                            f"Recomienda: {'Sí' if d['recomienda'] else 'No'}"
                        ),
                        usuario=responsable.usuario,
                        app_origen='servicio_tecnico',
                    )
            except Exception:
                pass

            # Registrar en historial de la orden
            try:
                HistorialOrden.objects.create(
                    orden=orden,
                    tipo_evento='cotizacion',
                    comentario=(
                        f'⭐ Cliente completó encuesta de satisfacción\n'
                        f'   Calificación: {d["calificacion_general"]}/5 | '
                        f'NPS: {d["nps"]}/10 | '
                        f'Recomienda: {"Sí" if d["recomienda"] else "No"}'
                    ),
                    usuario=None,
                    es_sistema=True,
                )
            except Exception:
                pass

            return render(request, TEMPLATE, {
                'estado': 'gracias',
                'calificacion': d['calificacion_general'],
            })
    else:
        form = FeedbackSatisfaccionClienteForm()

    return render(request, TEMPLATE, {
        'estado': 'formulario',
        'form': form,
        'feedback': feedback,
        'orden': orden,
        'detalle': detalle,
        'dias_restantes': feedback.dias_restantes,
    })


# ============================================================================
# DASHBOARD DE ENCUESTAS DE SATISFACCIÓN (Marzo 2026)
# Panel analítico para visualizar encuestas enviadas, respondidas, pendientes
# y expiradas. Incluye KPIs, gráficos Chart.js y análisis por responsable.
# ============================================================================


def _filtrar_encuestas_satisfaccion(request):
    """
    Helper: construye queryset base de FeedbackCliente tipo 'satisfaccion'
    aplicando los filtros GET comunes (fecha, responsable, sucursal, tipo_orden).
    Retorna el queryset con annotate de fecha_expiracion.
    """
    from .models import FeedbackCliente
    from django.db.models import F, ExpressionWrapper, DateTimeField
    from datetime import timedelta

    qs = FeedbackCliente.objects.filter(tipo='satisfaccion').select_related(
        'orden__responsable_seguimiento',
        'orden__sucursal',
        'orden__detalle_equipo',
    )

    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    responsable_id = request.GET.get('responsable_id')
    sucursal_id = request.GET.get('sucursal_id')
    tipo_orden = request.GET.get('tipo_orden')

    if fecha_desde:
        qs = qs.filter(fecha_creacion__date__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha_creacion__date__lte=fecha_hasta)
    if responsable_id:
        qs = qs.filter(orden__responsable_seguimiento_id=responsable_id)
    if sucursal_id:
        qs = qs.filter(orden__sucursal_id=sucursal_id)
    if tipo_orden and tipo_orden in ('diagnostico', 'venta_mostrador'):
        qs = qs.filter(orden__tipo_servicio=tipo_orden)

    qs = qs.annotate(
        fecha_expiracion=ExpressionWrapper(
            F('fecha_creacion') + timedelta(days=7),
            output_field=DateTimeField()
        )
    )
    return qs


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
def dashboard_encuestas(request):
    """
    Vista principal del panel de encuestas de satisfacción.
    Renderiza el template con filtros; la data se carga vía AJAX.
    """
    empleados = Empleado.objects.filter(activo=True).order_by('nombre_completo')
    sucursales = Sucursal.objects.filter(activa=True).order_by('nombre')

    return render(request, 'servicio_tecnico/dashboard_encuestas.html', {
        'empleados': empleados,
        'sucursales': sucursales,
    })


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_encuestas_kpis(request):
    """
    API JSON: KPIs globales del dashboard de encuestas.
    """
    from django.db.models import Avg

    now = timezone.now()
    qs = _filtrar_encuestas_satisfaccion(request)

    total_enviadas = qs.filter(correo_enviado=True).count()
    total_respondidas = qs.filter(utilizado=True).count()
    total_pendientes = qs.filter(
        utilizado=False, correo_enviado=True, fecha_expiracion__gte=now
    ).count()
    total_expiradas = qs.filter(
        utilizado=False, fecha_expiracion__lt=now
    ).count()

    tasa_respuesta = round(
        (total_respondidas / total_enviadas * 100) if total_enviadas > 0 else 0, 1
    )

    respondidas_qs = qs.filter(utilizado=True)
    avgs = respondidas_qs.aggregate(
        nps_promedio=Avg('nps'),
        calificacion_promedio=Avg('calificacion_general'),
        calificacion_atencion_promedio=Avg('calificacion_atencion'),
        calificacion_tiempo_promedio=Avg('calificacion_tiempo'),
    )

    total_con_recomendacion = respondidas_qs.filter(recomienda__isnull=False).count()
    total_recomiendan = respondidas_qs.filter(recomienda=True).count()
    tasa_recomendacion = round(
        (total_recomiendan / total_con_recomendacion * 100) if total_con_recomendacion > 0 else 0, 1
    )

    # NPS Score = % promotores (9-10) - % detractores (0-6)
    respondidas_con_nps = respondidas_qs.filter(nps__isnull=False).count()
    promotores = respondidas_qs.filter(nps__gte=9).count()
    detractores = respondidas_qs.filter(nps__lte=6).count()
    nps_score = round(
        ((promotores - detractores) / respondidas_con_nps * 100) if respondidas_con_nps > 0 else 0, 1
    )

    return JsonResponse({
        'total_enviadas': total_enviadas,
        'total_respondidas': total_respondidas,
        'total_pendientes': total_pendientes,
        'total_expiradas': total_expiradas,
        'tasa_respuesta': tasa_respuesta,
        'nps_promedio': round(avgs['nps_promedio'] or 0, 1),
        'calificacion_promedio': round(avgs['calificacion_promedio'] or 0, 1),
        'calificacion_atencion_promedio': round(avgs['calificacion_atencion_promedio'] or 0, 1),
        'calificacion_tiempo_promedio': round(avgs['calificacion_tiempo_promedio'] or 0, 1),
        'tasa_recomendacion': tasa_recomendacion,
        'nps_score': nps_score,
    })


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_encuestas_tendencia(request):
    """
    API JSON: tendencia temporal de métricas (agrupado por semana).
    """
    from django.db.models import Avg
    from django.db.models.functions import TruncWeek

    qs = _filtrar_encuestas_satisfaccion(request).filter(correo_enviado=True)

    datos_por_semana = (
        qs.annotate(semana=TruncWeek('fecha_creacion'))
        .values('semana')
        .annotate(
            total_enviadas=Count('id'),
            total_respondidas=Count('id', filter=Q(utilizado=True)),
            calificacion_promedio=Avg('calificacion_general', filter=Q(utilizado=True)),
            nps_promedio=Avg('nps', filter=Q(utilizado=True)),
        )
        .order_by('semana')
    )

    labels = []
    datasets = {
        'calificacion_promedio': [],
        'nps_promedio': [],
        'tasa_respuesta': [],
        'total_enviadas': [],
        'total_respondidas': [],
    }

    for row in datos_por_semana:
        semana = row['semana']
        labels.append(semana.strftime('%d/%m/%Y'))
        datasets['total_enviadas'].append(row['total_enviadas'])
        datasets['total_respondidas'].append(row['total_respondidas'])
        datasets['calificacion_promedio'].append(
            round(row['calificacion_promedio'] or 0, 1)
        )
        datasets['nps_promedio'].append(
            round(row['nps_promedio'] or 0, 1)
        )
        tasa = round(
            (row['total_respondidas'] / row['total_enviadas'] * 100)
            if row['total_enviadas'] > 0 else 0, 1
        )
        datasets['tasa_respuesta'].append(tasa)

    return JsonResponse({'labels': labels, 'datasets': datasets})


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_encuestas_por_responsable(request):
    """
    API JSON: métricas agrupadas por responsable de seguimiento.
    """
    from django.db.models import Avg

    qs = _filtrar_encuestas_satisfaccion(request).filter(correo_enviado=True)

    datos = (
        qs.values(
            'orden__responsable_seguimiento__id',
            'orden__responsable_seguimiento__nombre_completo',
        )
        .annotate(
            total_enviadas=Count('id'),
            total_respondidas=Count('id', filter=Q(utilizado=True)),
            calificacion_promedio=Avg('calificacion_general', filter=Q(utilizado=True)),
            nps_promedio=Avg('nps', filter=Q(utilizado=True)),
            total_recomiendan=Count('id', filter=Q(utilizado=True, recomienda=True)),
            total_con_recomendacion=Count('id', filter=Q(utilizado=True, recomienda__isnull=False)),
            promotores=Count('id', filter=Q(utilizado=True, nps__gte=9)),
            detractores=Count('id', filter=Q(utilizado=True, nps__lte=6)),
            respondidas_con_nps=Count('id', filter=Q(utilizado=True, nps__isnull=False)),
        )
        .order_by('-calificacion_promedio')
    )

    responsables = []
    for row in datos:
        nombre = row['orden__responsable_seguimiento__nombre_completo'] or ''
        tasa_rec = round(
            (row['total_recomiendan'] / row['total_con_recomendacion'] * 100)
            if row['total_con_recomendacion'] > 0 else 0, 1
        )
        nps_s = round(
            ((row['promotores'] - row['detractores']) / row['respondidas_con_nps'] * 100)
            if row['respondidas_con_nps'] > 0 else 0, 1
        )
        responsables.append({
            'id': row['orden__responsable_seguimiento__id'],
            'nombre': nombre,
            'total_enviadas': row['total_enviadas'],
            'total_respondidas': row['total_respondidas'],
            'calificacion_promedio': round(row['calificacion_promedio'] or 0, 1),
            'nps_promedio': round(row['nps_promedio'] or 0, 1),
            'tasa_recomendacion': tasa_rec,
            'nps_score': nps_s,
        })

    return JsonResponse({'responsables': responsables})


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_encuestas_distribucion_nps(request):
    """
    API JSON: distribución NPS (Promotores 9-10 / Pasivos 7-8 / Detractores 0-6).
    """
    qs = _filtrar_encuestas_satisfaccion(request).filter(
        utilizado=True, nps__isnull=False
    )

    datos = qs.aggregate(
        promotores=Count('id', filter=Q(nps__gte=9)),
        pasivos=Count('id', filter=Q(nps__gte=7, nps__lte=8)),
        detractores=Count('id', filter=Q(nps__lte=6)),
        total=Count('id'),
    )

    total = datos['total'] or 0
    nps_score = round(
        ((datos['promotores'] - datos['detractores']) / total * 100)
        if total > 0 else 0, 1
    )

    return JsonResponse({
        'promotores': datos['promotores'],
        'pasivos': datos['pasivos'],
        'detractores': datos['detractores'],
        'total': total,
        'nps_score': nps_score,
    })


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_encuestas_lista(request):
    """
    API JSON: lista paginada de encuestas con búsqueda y filtro por estado.
    """
    from config.paises_config import fecha_local_pais, get_pais_actual
    pais = get_pais_actual()
    now = timezone.now()
    qs = _filtrar_encuestas_satisfaccion(request)

    # Filtro por estado (tab)
    estado = request.GET.get('estado', 'todas')
    if estado == 'respondidas':
        qs = qs.filter(utilizado=True)
    elif estado == 'pendientes':
        qs = qs.filter(utilizado=False, correo_enviado=True, fecha_expiracion__gte=now)
    elif estado == 'expiradas':
        qs = qs.filter(utilizado=False, fecha_expiracion__lt=now)

    # Búsqueda
    busqueda = request.GET.get('busqueda', '').strip()
    if busqueda:
        qs = qs.filter(
            Q(orden__numero_orden_interno__icontains=busqueda) |
            Q(orden__detalle_equipo__orden_cliente__icontains=busqueda) |
            Q(orden__detalle_equipo__email_cliente__icontains=busqueda) |
            Q(orden__detalle_equipo__marca__icontains=busqueda) |
            Q(orden__detalle_equipo__modelo__icontains=busqueda)
        )

    qs = qs.order_by('-fecha_creacion')

    # Paginación
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 15))
    paginator = Paginator(qs, page_size)

    try:
        pagina = paginator.page(page)
    except (EmptyPage, PageNotAnInteger):
        pagina = paginator.page(1)

    encuestas = []
    for fb in pagina.object_list:
        orden = fb.orden
        detalle = getattr(orden, 'detalle_equipo', None)

        if fb.utilizado:
            estado_encuesta = 'respondida'
        elif not fb.correo_enviado:
            estado_encuesta = 'no_enviada'
        elif fb.fecha_expiracion < now:
            estado_encuesta = 'expirada'
        else:
            estado_encuesta = 'pendiente'

        encuestas.append({
            'id': fb.id,
            'orden_numero': detalle.orden_cliente if detalle and detalle.orden_cliente else orden.numero_orden_interno,
            'orden_id': orden.id,
            'equipo': f"{detalle.marca} {detalle.get_tipo_equipo_display()} {detalle.modelo}" if detalle else '',
            'email_cliente': detalle.email_cliente if detalle else '',
            'responsable': str(orden.responsable_seguimiento) if orden.responsable_seguimiento else '',
            'sucursal': str(orden.sucursal) if orden.sucursal else '',
            'tipo_orden': orden.get_tipo_servicio_display(),
            'fecha_envio': fecha_local_pais(fb.fecha_creacion, pais).strftime('%d/%m/%Y %H:%M'),
            'fecha_respuesta': fecha_local_pais(fb.fecha_respuesta, pais).strftime('%d/%m/%Y %H:%M') if fb.fecha_respuesta else None,
            'dias_restantes': fb.dias_restantes,
            'estado': estado_encuesta,
            'calificacion_general': fb.calificacion_general,
            'nps': fb.nps,
            'recomienda': fb.recomienda,
            'calificacion_atencion': fb.calificacion_atencion,
            'calificacion_tiempo': fb.calificacion_tiempo,
            'comentario_cliente': fb.comentario_cliente,
        })

    return JsonResponse({
        'encuestas': encuestas,
        'total': paginator.count,
        'paginas': paginator.num_pages,
        'pagina_actual': pagina.number,
    })


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_encuestas_comentarios(request):
    """
    API JSON: últimos comentarios de clientes con calificación.
    """
    from config.paises_config import fecha_local_pais, get_pais_actual
    pais = get_pais_actual()
    qs = _filtrar_encuestas_satisfaccion(request).filter(
        utilizado=True,
    ).exclude(
        comentario_cliente=''
    ).order_by('-fecha_respuesta')[:10]

    comentarios = []
    for fb in qs:
        comentarios.append({
            'orden_numero': (
                fb.orden.detalle_equipo.orden_cliente
                if hasattr(fb.orden, 'detalle_equipo') and fb.orden.detalle_equipo.orden_cliente
                else fb.orden.numero_orden_interno
            ),
            'orden_id': fb.orden.id,
            'responsable': str(fb.orden.responsable_seguimiento) if fb.orden.responsable_seguimiento else '',
            'calificacion': fb.calificacion_general,
            'nps': fb.nps,
            'recomienda': fb.recomienda,
            'comentario': fb.comentario_cliente,
            'fecha': fecha_local_pais(fb.fecha_respuesta, pais).strftime('%d/%m/%Y') if fb.fecha_respuesta else '',
        })

    return JsonResponse({'comentarios': comentarios})


@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def exportar_encuestas_excel(request):
    """
    Exporta las encuestas de satisfacción filtradas a un archivo Excel.
    Genera 3 hojas: Resumen KPIs, Encuestas detalladas, Por Responsable.
    """
    from openpyxl import Workbook
    from django.db.models import Avg

    now = timezone.now()
    qs = _filtrar_encuestas_satisfaccion(request).filter(correo_enviado=True)

    # Estilos
    header_font = Font(bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    wb = Workbook()

    # ── HOJA 1: Resumen KPIs ──────────────────────────────────────────
    ws_resumen = wb.active
    ws_resumen.title = 'Resumen KPIs'

    total_enviadas = qs.count()
    total_respondidas = qs.filter(utilizado=True).count()
    total_pendientes = qs.filter(utilizado=False, fecha_expiracion__gte=now).count()
    total_expiradas = qs.filter(utilizado=False, fecha_expiracion__lt=now).count()
    tasa_respuesta = round((total_respondidas / total_enviadas * 100) if total_enviadas > 0 else 0, 1)

    respondidas_qs = qs.filter(utilizado=True)
    avgs = respondidas_qs.aggregate(
        cal_prom=Avg('calificacion_general'),
        nps_prom=Avg('nps'),
        cal_atencion=Avg('calificacion_atencion'),
        cal_tiempo=Avg('calificacion_tiempo'),
    )

    kpis = [
        ('Métrica', 'Valor'),
        ('Total Encuestas Enviadas', total_enviadas),
        ('Total Respondidas', total_respondidas),
        ('Total Pendientes', total_pendientes),
        ('Total Expiradas', total_expiradas),
        ('Tasa de Respuesta (%)', f'{tasa_respuesta}%'),
        ('Calificación General Promedio', round(avgs['cal_prom'] or 0, 2)),
        ('NPS Promedio', round(avgs['nps_prom'] or 0, 2)),
        ('Calificación Atención Promedio', round(avgs['cal_atencion'] or 0, 2)),
        ('Calificación Tiempo Promedio', round(avgs['cal_tiempo'] or 0, 2)),
    ]

    for row_idx, (metrica, valor) in enumerate(kpis, 1):
        ws_resumen.cell(row=row_idx, column=1, value=metrica)
        ws_resumen.cell(row=row_idx, column=2, value=valor)
        if row_idx == 1:
            for col in (1, 2):
                cell = ws_resumen.cell(row=1, column=col)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment
                cell.border = thin_border
        else:
            for col in (1, 2):
                ws_resumen.cell(row=row_idx, column=col).border = thin_border

    ws_resumen.column_dimensions['A'].width = 35
    ws_resumen.column_dimensions['B'].width = 20

    # ── HOJA 2: Encuestas Detalladas ──────────────────────────────────
    ws_encuestas = wb.create_sheet('Encuestas')
    headers = [
        'Orden', 'Equipo', 'Email Cliente', 'Responsable', 'Sucursal',
        'Tipo Orden', 'Fecha Envío', 'Fecha Respuesta', 'Estado',
        'Calificación General', 'NPS', 'Recomienda',
        'Calificación Atención', 'Calificación Tiempo', 'Comentario'
    ]
    for col_idx, header in enumerate(headers, 1):
        cell = ws_encuestas.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    for row_idx, fb in enumerate(qs.order_by('-fecha_creacion'), 2):
        orden = fb.orden
        detalle = getattr(orden, 'detalle_equipo', None)

        if fb.utilizado:
            estado_str = 'Respondida'
        elif fb.fecha_expiracion < now:
            estado_str = 'Expirada'
        else:
            estado_str = 'Pendiente'

        valores = [
            detalle.orden_cliente if detalle and detalle.orden_cliente else orden.numero_orden_interno,
            f"{detalle.marca} {detalle.get_tipo_equipo_display()} {detalle.modelo}" if detalle else '',
            detalle.email_cliente if detalle else '',
            str(orden.responsable_seguimiento) if orden.responsable_seguimiento else '',
            str(orden.sucursal) if orden.sucursal else '',
            orden.get_tipo_servicio_display(),
            fb.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
            fb.fecha_respuesta.strftime('%d/%m/%Y %H:%M') if fb.fecha_respuesta else '',
            estado_str,
            fb.calificacion_general or '',
            fb.nps or '',
            'Sí' if fb.recomienda is True else ('No' if fb.recomienda is False else ''),
            fb.calificacion_atencion or '',
            fb.calificacion_tiempo or '',
            fb.comentario_cliente,
        ]
        for col_idx, valor in enumerate(valores, 1):
            cell = ws_encuestas.cell(row=row_idx, column=col_idx, value=valor)
            cell.border = thin_border

    for col_idx in range(1, len(headers) + 1):
        ws_encuestas.column_dimensions[get_column_letter(col_idx)].width = 18

    # ── HOJA 3: Por Responsable ───────────────────────────────────────
    ws_resp = wb.create_sheet('Por Responsable')
    headers_resp = [
        'Responsable', 'Enviadas', 'Respondidas', 'Tasa Respuesta (%)',
        'Calificación Promedio', 'NPS Promedio', 'NPS Score', 'Tasa Recomendación (%)'
    ]
    for col_idx, header in enumerate(headers_resp, 1):
        cell = ws_resp.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    datos_resp = (
        qs.values(
            'orden__responsable_seguimiento__nombre_completo',
        )
        .annotate(
            total_enviadas=Count('id'),
            total_respondidas=Count('id', filter=Q(utilizado=True)),
            calificacion_promedio=Avg('calificacion_general', filter=Q(utilizado=True)),
            nps_promedio=Avg('nps', filter=Q(utilizado=True)),
            promotores=Count('id', filter=Q(utilizado=True, nps__gte=9)),
            detractores=Count('id', filter=Q(utilizado=True, nps__lte=6)),
            resp_con_nps=Count('id', filter=Q(utilizado=True, nps__isnull=False)),
            total_recomiendan=Count('id', filter=Q(utilizado=True, recomienda=True)),
            total_con_rec=Count('id', filter=Q(utilizado=True, recomienda__isnull=False)),
        )
        .order_by('-calificacion_promedio')
    )

    for row_idx, row in enumerate(datos_resp, 2):
        nombre = row['orden__responsable_seguimiento__nombre_completo'] or ''
        tasa_r = round((row['total_respondidas'] / row['total_enviadas'] * 100) if row['total_enviadas'] > 0 else 0, 1)
        nps_s = round(((row['promotores'] - row['detractores']) / row['resp_con_nps'] * 100) if row['resp_con_nps'] > 0 else 0, 1)
        tasa_rec = round((row['total_recomiendan'] / row['total_con_rec'] * 100) if row['total_con_rec'] > 0 else 0, 1)

        valores = [
            nombre,
            row['total_enviadas'],
            row['total_respondidas'],
            f'{tasa_r}%',
            round(row['calificacion_promedio'] or 0, 2),
            round(row['nps_promedio'] or 0, 2),
            nps_s,
            f'{tasa_rec}%',
        ]
        for col_idx, valor in enumerate(valores, 1):
            cell = ws_resp.cell(row=row_idx, column=col_idx, value=valor)
            cell.border = thin_border

    for col_idx in range(1, len(headers_resp) + 1):
        ws_resp.column_dimensions[get_column_letter(col_idx)].width = 22

    # Generar respuesta
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    fecha_str = now.strftime('%Y%m%d')
    response['Content-Disposition'] = f'attachment; filename=Encuestas_Satisfaccion_{fecha_str}.xlsx'
    wb.save(response)
    return response


# ============================================================================
# DASHBOARD DE FEEDBACK DE RECHAZO DE COTIZACIÓN (Marzo 2026)
# ============================================================================

def _filtrar_feedback_rechazo(request):
    """
    Helper: construye queryset base de FeedbackCliente tipo 'rechazo'
    aplicando los filtros GET comunes (fecha, responsable, sucursal, motivo).
    Retorna el queryset con annotate de fecha_expiracion.
    """
    from .models import FeedbackCliente
    from django.db.models import F, ExpressionWrapper, DateTimeField
    from datetime import timedelta

    qs = FeedbackCliente.objects.filter(tipo='rechazo').select_related(
        'orden__responsable_seguimiento',
        'orden__sucursal',
        'orden__detalle_equipo',
        'cotizacion',
    )

    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    responsable_id = request.GET.get('responsable_id')
    sucursal_id = request.GET.get('sucursal_id')
    motivo_rechazo = request.GET.get('motivo_rechazo')

    if fecha_desde:
        qs = qs.filter(fecha_creacion__date__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha_creacion__date__lte=fecha_hasta)
    if responsable_id:
        qs = qs.filter(orden__responsable_seguimiento_id=responsable_id)
    if sucursal_id:
        qs = qs.filter(orden__sucursal_id=sucursal_id)
    if motivo_rechazo:
        qs = qs.filter(motivo_rechazo_snapshot=motivo_rechazo)

    qs = qs.annotate(
        fecha_expiracion=ExpressionWrapper(
            F('fecha_creacion') + timedelta(days=7),
            output_field=DateTimeField()
        )
    )
    return qs


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
def dashboard_feedback_rechazo(request):
    """
    Vista principal del panel de feedback de rechazo.
    Renderiza el template; la data se carga vía AJAX.
    """
    from config.constants import MOTIVO_RECHAZO_COTIZACION

    empleados = Empleado.objects.filter(activo=True).order_by('nombre_completo')
    sucursales = Sucursal.objects.filter(activa=True).order_by('nombre')

    return render(request, 'servicio_tecnico/dashboard_feedback_rechazo.html', {
        'empleados': empleados,
        'sucursales': sucursales,
        'motivos_rechazo': MOTIVO_RECHAZO_COTIZACION,
    })


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_feedback_rechazo_kpis(request):
    """
    API JSON: KPIs globales del dashboard de feedback de rechazo.
    """
    now = timezone.now()
    qs = _filtrar_feedback_rechazo(request)

    total_enviados = qs.filter(correo_enviado=True).count()
    total_respondidos = qs.filter(utilizado=True).count()
    total_pendientes = qs.filter(
        utilizado=False, correo_enviado=True, fecha_expiracion__gte=now
    ).count()
    total_expirados = qs.filter(
        utilizado=False, fecha_expiracion__lt=now
    ).count()

    tasa_respuesta = round(
        (total_respondidos / total_enviados * 100) if total_enviados > 0 else 0, 1
    )

    # Motivo más frecuente
    motivo_top = (
        qs.filter(correo_enviado=True)
        .values('motivo_rechazo_snapshot')
        .annotate(total=Count('id'))
        .order_by('-total')
        .first()
    )

    from config.constants import MOTIVO_RECHAZO_COTIZACION
    motivos_dict = dict(MOTIVO_RECHAZO_COTIZACION)

    motivo_label = ''
    motivo_porcentaje = 0
    if motivo_top and total_enviados > 0:
        motivo_label = motivos_dict.get(motivo_top['motivo_rechazo_snapshot'], motivo_top['motivo_rechazo_snapshot'])
        motivo_porcentaje = round(motivo_top['total'] / total_enviados * 100, 1)

    return JsonResponse({
        'total_enviados': total_enviados,
        'total_respondidos': total_respondidos,
        'total_pendientes': total_pendientes,
        'total_expirados': total_expirados,
        'tasa_respuesta': tasa_respuesta,
        'motivo_mas_frecuente': motivo_label,
        'motivo_mas_frecuente_porcentaje': motivo_porcentaje,
    })


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_feedback_rechazo_por_motivo(request):
    """
    API JSON: distribución por motivo de rechazo.
    """
    qs = _filtrar_feedback_rechazo(request).filter(correo_enviado=True)

    from config.constants import MOTIVO_RECHAZO_COTIZACION
    motivos_dict = dict(MOTIVO_RECHAZO_COTIZACION)

    datos = (
        qs.values('motivo_rechazo_snapshot')
        .annotate(
            total=Count('id'),
            respondidos=Count('id', filter=Q(utilizado=True)),
        )
        .order_by('-total')
    )

    motivos = []
    for row in datos:
        clave = row['motivo_rechazo_snapshot']
        motivos.append({
            'motivo': clave,
            'label': motivos_dict.get(clave, clave or 'Sin motivo'),
            'total': row['total'],
            'respondidos': row['respondidos'],
        })

    return JsonResponse({'motivos': motivos})


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_feedback_rechazo_tendencia(request):
    """
    API JSON: tendencia temporal semanal de feedbacks de rechazo.
    """
    from django.db.models.functions import TruncWeek
    from config.paises_config import fecha_local_pais, get_pais_actual
    pais = get_pais_actual()

    qs = _filtrar_feedback_rechazo(request).filter(correo_enviado=True)

    datos_por_semana = (
        qs.annotate(semana=TruncWeek('fecha_creacion'))
        .values('semana')
        .annotate(
            total_enviados=Count('id'),
            total_respondidos=Count('id', filter=Q(utilizado=True)),
        )
        .order_by('semana')
    )

    labels = []
    datasets = {
        'total_enviados': [],
        'total_respondidos': [],
        'tasa_respuesta': [],
    }

    for row in datos_por_semana:
        labels.append(fecha_local_pais(row['semana'], pais).strftime('%d/%m/%Y'))
        datasets['total_enviados'].append(row['total_enviados'])
        datasets['total_respondidos'].append(row['total_respondidos'])
        tasa = round(
            (row['total_respondidos'] / row['total_enviados'] * 100)
            if row['total_enviados'] > 0 else 0, 1
        )
        datasets['tasa_respuesta'].append(tasa)

    return JsonResponse({'labels': labels, 'datasets': datasets})


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_feedback_rechazo_lista(request):
    """
    API JSON: lista paginada de feedbacks de rechazo.
    """
    from config.constants import MOTIVO_RECHAZO_COTIZACION
    from config.paises_config import fecha_local_pais, get_pais_actual
    motivos_dict = dict(MOTIVO_RECHAZO_COTIZACION)
    pais = get_pais_actual()

    now = timezone.now()
    qs = _filtrar_feedback_rechazo(request)

    # Filtro por estado (tab)
    estado = request.GET.get('estado', 'todos')
    if estado == 'respondidos':
        qs = qs.filter(utilizado=True)
    elif estado == 'pendientes':
        qs = qs.filter(utilizado=False, correo_enviado=True, fecha_expiracion__gte=now)
    elif estado == 'expirados':
        qs = qs.filter(utilizado=False, fecha_expiracion__lt=now)

    # Búsqueda
    busqueda = request.GET.get('busqueda', '').strip()
    if busqueda:
        qs = qs.filter(
            Q(orden__numero_orden_interno__icontains=busqueda) |
            Q(orden__detalle_equipo__orden_cliente__icontains=busqueda) |
            Q(orden__detalle_equipo__email_cliente__icontains=busqueda) |
            Q(orden__detalle_equipo__marca__icontains=busqueda) |
            Q(orden__detalle_equipo__modelo__icontains=busqueda) |
            Q(comentario_cliente__icontains=busqueda)
        )

    qs = qs.order_by('-fecha_creacion')

    # Paginación
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 15))
    paginator = Paginator(qs, page_size)

    try:
        pagina = paginator.page(page)
    except (EmptyPage, PageNotAnInteger):
        pagina = paginator.page(1)

    feedbacks = []
    for fb in pagina.object_list:
        orden = fb.orden
        detalle = getattr(orden, 'detalle_equipo', None)

        if fb.utilizado:
            estado_fb = 'respondido'
        elif not fb.correo_enviado:
            estado_fb = 'no_enviado'
        elif fb.fecha_expiracion < now:
            estado_fb = 'expirado'
        else:
            estado_fb = 'pendiente'

        feedbacks.append({
            'id': fb.id,
            'orden_numero': detalle.orden_cliente if detalle and detalle.orden_cliente else orden.numero_orden_interno,
            'orden_id': orden.id,
            'equipo': f"{detalle.marca} {detalle.get_tipo_equipo_display()} {detalle.modelo}" if detalle else '',
            'email_cliente': detalle.email_cliente if detalle else '',
            'responsable': str(orden.responsable_seguimiento) if orden.responsable_seguimiento else '',
            'sucursal': str(orden.sucursal) if orden.sucursal else '',
            'motivo_rechazo': motivos_dict.get(fb.motivo_rechazo_snapshot, fb.motivo_rechazo_snapshot or 'Sin motivo'),
            'fecha_envio': fecha_local_pais(fb.fecha_creacion, pais).strftime('%d/%m/%Y %H:%M'),
            'fecha_respuesta': fecha_local_pais(fb.fecha_respuesta, pais).strftime('%d/%m/%Y %H:%M') if fb.fecha_respuesta else None,
            'dias_restantes': fb.dias_restantes,
            'estado': estado_fb,
            'comentario_cliente': fb.comentario_cliente,
        })

    return JsonResponse({
        'feedbacks': feedbacks,
        'total': paginator.count,
        'paginas': paginator.num_pages,
        'pagina_actual': pagina.number,
    })


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_feedback_rechazo_comentarios(request):
    """
    API JSON: últimos comentarios de clientes en feedbacks de rechazo.
    """
    from config.constants import MOTIVO_RECHAZO_COTIZACION
    from config.paises_config import fecha_local_pais, get_pais_actual
    motivos_dict = dict(MOTIVO_RECHAZO_COTIZACION)
    pais = get_pais_actual()

    qs = _filtrar_feedback_rechazo(request).filter(
        utilizado=True,
    ).exclude(
        comentario_cliente=''
    ).order_by('-fecha_respuesta')[:10]

    comentarios = []
    for fb in qs:
        detalle = getattr(fb.orden, 'detalle_equipo', None)
        comentarios.append({
            'orden_numero': detalle.orden_cliente if detalle and detalle.orden_cliente else fb.orden.numero_orden_interno,
            'orden_id': fb.orden.id,
            'responsable': str(fb.orden.responsable_seguimiento) if fb.orden.responsable_seguimiento else '',
            'motivo_rechazo': motivos_dict.get(fb.motivo_rechazo_snapshot, fb.motivo_rechazo_snapshot or 'Sin motivo'),
            'comentario': fb.comentario_cliente,
            'fecha': fecha_local_pais(fb.fecha_respuesta, pais).strftime('%d/%m/%Y') if fb.fecha_respuesta else '',
        })

    return JsonResponse({'comentarios': comentarios})


@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def exportar_feedback_rechazo_excel(request):
    """
    Exporta los feedbacks de rechazo filtrados a un archivo Excel.
    Genera 3 hojas: Resumen KPIs, Feedbacks detallados, Por Motivo.
    """
    from openpyxl import Workbook
    from config.constants import MOTIVO_RECHAZO_COTIZACION

    motivos_dict = dict(MOTIVO_RECHAZO_COTIZACION)
    now = timezone.now()
    qs = _filtrar_feedback_rechazo(request).filter(correo_enviado=True)

    # Estilos
    header_font = Font(bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill(start_color='C0392B', end_color='C0392B', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    wb = Workbook()

    # ── HOJA 1: Resumen KPIs ──────────────────────────────────────────
    ws_resumen = wb.active
    ws_resumen.title = 'Resumen KPIs'

    total_enviados = qs.count()
    total_respondidos = qs.filter(utilizado=True).count()
    total_pendientes = qs.filter(utilizado=False, fecha_expiracion__gte=now).count()
    total_expirados = qs.filter(utilizado=False, fecha_expiracion__lt=now).count()
    tasa_respuesta = round((total_respondidos / total_enviados * 100) if total_enviados > 0 else 0, 1)

    kpis = [
        ('Métrica', 'Valor'),
        ('Total Feedbacks Enviados', total_enviados),
        ('Total Respondidos', total_respondidos),
        ('Total Pendientes', total_pendientes),
        ('Total Expirados', total_expirados),
        ('Tasa de Respuesta (%)', f'{tasa_respuesta}%'),
    ]

    for row_idx, (metrica, valor) in enumerate(kpis, 1):
        ws_resumen.cell(row=row_idx, column=1, value=metrica)
        ws_resumen.cell(row=row_idx, column=2, value=valor)
        if row_idx == 1:
            for col in (1, 2):
                cell = ws_resumen.cell(row=1, column=col)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment
                cell.border = thin_border
        else:
            for col in (1, 2):
                ws_resumen.cell(row=row_idx, column=col).border = thin_border

    ws_resumen.column_dimensions['A'].width = 35
    ws_resumen.column_dimensions['B'].width = 20

    # ── HOJA 2: Feedbacks Detallados ──────────────────────────────────
    ws_feedbacks = wb.create_sheet('Feedbacks')
    headers = [
        'Orden', 'Equipo', 'Email Cliente', 'Responsable', 'Sucursal',
        'Motivo de Rechazo', 'Fecha Envío', 'Fecha Respuesta', 'Estado', 'Comentario'
    ]
    for col_idx, header in enumerate(headers, 1):
        cell = ws_feedbacks.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    for row_idx, fb in enumerate(qs.order_by('-fecha_creacion'), 2):
        orden = fb.orden
        detalle = getattr(orden, 'detalle_equipo', None)

        if fb.utilizado:
            estado_str = 'Respondido'
        elif fb.fecha_expiracion < now:
            estado_str = 'Expirado'
        else:
            estado_str = 'Pendiente'

        valores = [
            detalle.orden_cliente if detalle and detalle.orden_cliente else orden.numero_orden_interno,
            f"{detalle.marca} {detalle.get_tipo_equipo_display()} {detalle.modelo}" if detalle else '',
            detalle.email_cliente if detalle else '',
            str(orden.responsable_seguimiento) if orden.responsable_seguimiento else '',
            str(orden.sucursal) if orden.sucursal else '',
            motivos_dict.get(fb.motivo_rechazo_snapshot, fb.motivo_rechazo_snapshot or 'Sin motivo'),
            fb.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
            fb.fecha_respuesta.strftime('%d/%m/%Y %H:%M') if fb.fecha_respuesta else '',
            estado_str,
            fb.comentario_cliente,
        ]
        for col_idx, valor in enumerate(valores, 1):
            cell = ws_feedbacks.cell(row=row_idx, column=col_idx, value=valor)
            cell.border = thin_border

    for col_idx in range(1, len(headers) + 1):
        ws_feedbacks.column_dimensions[get_column_letter(col_idx)].width = 20

    # ── HOJA 3: Por Motivo de Rechazo ─────────────────────────────────
    ws_motivos = wb.create_sheet('Por Motivo')
    headers_mot = ['Motivo de Rechazo', 'Total', 'Respondidos', 'Tasa Respuesta (%)']
    for col_idx, header in enumerate(headers_mot, 1):
        cell = ws_motivos.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    datos_motivos = (
        qs.values('motivo_rechazo_snapshot')
        .annotate(
            total=Count('id'),
            respondidos=Count('id', filter=Q(utilizado=True)),
        )
        .order_by('-total')
    )

    for row_idx, row in enumerate(datos_motivos, 2):
        clave = row['motivo_rechazo_snapshot']
        tasa = round((row['respondidos'] / row['total'] * 100) if row['total'] > 0 else 0, 1)
        valores = [
            motivos_dict.get(clave, clave or 'Sin motivo'),
            row['total'],
            row['respondidos'],
            f'{tasa}%',
        ]
        for col_idx, valor in enumerate(valores, 1):
            cell = ws_motivos.cell(row=row_idx, column=col_idx, value=valor)
            cell.border = thin_border

    for col_idx in range(1, len(headers_mot) + 1):
        ws_motivos.column_dimensions[get_column_letter(col_idx)].width = 30

    # Generar respuesta
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    fecha_str = now.strftime('%Y%m%d')
    response['Content-Disposition'] = f'attachment; filename=Feedback_Rechazo_{fecha_str}.xlsx'
    wb.save(response)
    return response


# ============================================================================
# DASHBOARD DE MÉTRICAS DE SEGUIMIENTO DE CLIENTES (Marzo 2026)
# Monitorea el uso de los enlaces públicos EnlaceSeguimientoCliente:
# cuántos se generaron, cuántos visitan los clientes, cuáles son los más consultados.
# ============================================================================

def _filtrar_enlaces_seguimiento(request):
    """
    Helper: construye queryset base de EnlaceSeguimientoCliente
    aplicando los filtros GET comunes (fecha, responsable, sucursal, tipo_orden).
    """
    from .models import EnlaceSeguimientoCliente

    qs = EnlaceSeguimientoCliente.objects.select_related(
        'orden__responsable_seguimiento',
        'orden__sucursal',
        'orden__detalle_equipo',
    )

    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    responsable_id = request.GET.get('responsable_id')
    sucursal_id = request.GET.get('sucursal_id')
    tipo_orden = request.GET.get('tipo_orden')

    if fecha_desde:
        qs = qs.filter(fecha_creacion__date__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha_creacion__date__lte=fecha_hasta)
    if responsable_id:
        qs = qs.filter(orden__responsable_seguimiento_id=responsable_id)
    if sucursal_id:
        qs = qs.filter(orden__sucursal_id=sucursal_id)
    if tipo_orden and tipo_orden in ('diagnostico', 'venta_mostrador'):
        qs = qs.filter(orden__tipo_servicio=tipo_orden)

    return qs


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
def dashboard_seguimiento_enlaces(request):
    """
    Vista principal del panel de métricas de seguimiento de clientes.
    Renderiza el template con lookups; la data se carga vía AJAX.
    """
    empleados = Empleado.objects.filter(activo=True).order_by('nombre_completo')
    sucursales = Sucursal.objects.filter(activa=True).order_by('nombre')

    return render(request, 'servicio_tecnico/dashboard_seguimiento_enlaces.html', {
        'empleados': empleados,
        'sucursales': sucursales,
    })


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_seguimiento_enlaces_kpis(request):
    """
    API JSON: KPIs del dashboard de seguimiento de clientes.
    """
    from django.db.models import Sum, Avg, Count

    qs = _filtrar_enlaces_seguimiento(request)

    total_enlaces = qs.count()
    agregados = qs.aggregate(
        total_accesos=Sum('accesos_count'),
        promedio_accesos=Avg('accesos_count'),
    )
    total_accesos = agregados['total_accesos'] or 0
    promedio_accesos = round(agregados['promedio_accesos'] or 0, 1)

    sin_visitas = qs.filter(accesos_count=0).count()
    correos_enviados = qs.filter(correo_enviado=True).count()
    correos_no_enviados = qs.filter(correo_enviado=False).count()

    tasa_apertura = round(
        ((total_enlaces - sin_visitas) / total_enlaces * 100) if total_enlaces > 0 else 0, 1
    )

    return JsonResponse({
        'total_enlaces': total_enlaces,
        'total_accesos': total_accesos,
        'promedio_accesos': promedio_accesos,
        'sin_visitas': sin_visitas,
        'correos_enviados': correos_enviados,
        'correos_no_enviados': correos_no_enviados,
        'tasa_apertura': tasa_apertura,
    })


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_seguimiento_enlaces_tendencia(request):
    """
    API JSON: tendencia de accesos agrupados por día (últimos 60 días).
    Retorna dos series: enlaces creados y suma de accesos por día de creación.
    """
    from django.db.models.functions import TruncDate
    from django.db.models import Sum, Count

    qs = _filtrar_enlaces_seguimiento(request)

    # Nuevos enlaces creados por día
    creados_por_dia = (
        qs
        .annotate(dia=TruncDate('fecha_creacion'))
        .values('dia')
        .annotate(total=Count('id'))
        .order_by('dia')
    )

    # Accesos registrados por día de último acceso (solo enlaces con accesos)
    accesos_por_dia = (
        qs
        .filter(fecha_ultimo_acceso__isnull=False)
        .annotate(dia=TruncDate('fecha_ultimo_acceso'))
        .values('dia')
        .annotate(total=Sum('accesos_count'))
        .order_by('dia')
    )

    return JsonResponse({
        'creados': [
            {'dia': str(r['dia']), 'total': r['total']}
            for r in creados_por_dia
        ],
        'accesos': [
            {'dia': str(r['dia']), 'total': r['total']}
            for r in accesos_por_dia
        ],
    })


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_seguimiento_enlaces_top(request):
    """
    API JSON: top 15 órdenes más consultadas por los clientes.
    """
    from config.paises_config import fecha_local_pais, get_pais_actual
    pais = get_pais_actual()

    qs = _filtrar_enlaces_seguimiento(request)

    top = (
        qs
        .filter(accesos_count__gt=0)
        .select_related('orden__detalle_equipo', 'orden__sucursal')
        .order_by('-accesos_count')[:15]
    )

    data = []
    for enlace in top:
        de = getattr(enlace.orden, 'detalle_equipo', None)
        equipo = f"{de.marca} {de.modelo}".strip() if de else '—'
        orden_cliente = de.orden_cliente if de else enlace.orden.numero_orden_interno
        data.append({
            'folio': orden_cliente,
            'equipo': equipo,
            'accesos': enlace.accesos_count,
            'ultimo_acceso': fecha_local_pais(enlace.fecha_ultimo_acceso, pais).strftime('%d/%m/%Y %H:%M') if enlace.fecha_ultimo_acceso else '—',
        })

    return JsonResponse({'top': data})


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_seguimiento_enlaces_tabla(request):
    """
    API JSON: lista paginada de enlaces de seguimiento con datos de la orden.
    """
    from django.core.paginator import Paginator
    from config.paises_config import fecha_local_pais, get_pais_actual
    pais = get_pais_actual()

    qs = _filtrar_enlaces_seguimiento(request).order_by('-fecha_creacion')

    # Ordenamiento
    order_by = request.GET.get('order_by', '-fecha_creacion')
    campos_validos = {'fecha_creacion', '-fecha_creacion', 'accesos_count', '-accesos_count'}
    if order_by in campos_validos:
        qs = qs.order_by(order_by)

    paginator = Paginator(qs, 50)
    page_num = request.GET.get('page', 1)
    page = paginator.get_page(page_num)

    filas = []
    for enlace in page.object_list:
        de = getattr(enlace.orden, 'detalle_equipo', None)
        equipo = f"{de.marca} {de.modelo}".strip() if de else '—'
        orden_cliente = de.orden_cliente if de else '—'
        email = de.email_cliente if de else '—'
        sucursal = enlace.orden.sucursal.nombre if enlace.orden.sucursal else '—'
        responsable = ''
        if enlace.orden.responsable_seguimiento:
            responsable = enlace.orden.responsable_seguimiento.nombre_completo

        filas.append({
            'folio': orden_cliente or enlace.orden.numero_orden_interno,
            'orden_id': enlace.orden.id,
            'orden_cliente': orden_cliente,
            'numero_serie': de.numero_serie if de else '—',
            'equipo': equipo,
            'email': email,
            'sucursal': sucursal,
            'responsable': responsable,
            'estado': enlace.orden.get_estado_display(),
            'accesos': enlace.accesos_count,
            'correo_enviado': enlace.correo_enviado,
            'fecha_creacion': enlace.fecha_creacion.strftime('%d/%m/%Y'),
            'ultimo_acceso': fecha_local_pais(enlace.fecha_ultimo_acceso, pais).strftime('%d/%m/%Y %H:%M') if enlace.fecha_ultimo_acceso else '—',
        })

    return JsonResponse({
        'filas': filas,
        'total': paginator.count,
        'pagina': page.number,
        'total_paginas': paginator.num_pages,
        'tiene_siguiente': page.has_next(),
        'tiene_anterior': page.has_previous(),
    })


# ============================================================================
# FUNCIONES AUXILIARES PARA PERFIL DE EMPLEADO (Marzo 2026)
# ============================================================================

def _calcular_metricas_empleado(empleado):
    """
    Calcula métricas de desempeño y rating para un empleado dado.
    Reutilizable por mi_perfil y perfil_empleado (vista gerencial).

    Retorna: (metricas: dict, rating: int, rol: str, rol_display: str)
    """
    from django.db.models import Avg, Sum, Count, Q
    from decimal import Decimal
    from datetime import timedelta
    from .models import Cotizacion, VentaMostrador, FeedbackCliente

    rol = empleado.rol
    ahora = timezone.now()
    inicio_mes = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    hace_90_dias = ahora - timedelta(days=90)

    # Métricas comunes a todos los roles
    ordenes_activas_count = OrdenServicio.objects.filter(
        Q(tecnico_asignado_actual=empleado) | Q(responsable_seguimiento=empleado)
    ).exclude(estado__in=['entregado', 'cancelado']).distinct().count()

    ordenes_entregadas_mes = OrdenServicio.objects.filter(
        Q(tecnico_asignado_actual=empleado) | Q(responsable_seguimiento=empleado),
        estado='entregado',
        fecha_entrega__gte=inicio_mes
    ).distinct().count()

    dias_en_sistema = (ahora - empleado.fecha_ingreso).days if empleado.fecha_ingreso else 0

    metricas = {
        'ordenes_activas': ordenes_activas_count,
        'ordenes_entregadas_mes': ordenes_entregadas_mes,
        'dias_en_sistema': dias_en_sistema,
    }

    # Métricas para recepcionista
    if rol == 'recepcionista':
        ordenes_con_cotizacion = OrdenServicio.objects.filter(
            responsable_seguimiento=empleado,
            cotizacion__isnull=False,
        ).select_related('cotizacion')

        cotizaciones_ordenes = ordenes_con_cotizacion.filter(
            cotizacion__fecha_envio__gte=hace_90_dias
        )

        total_cotizaciones = cotizaciones_ordenes.count()
        cotizaciones_aceptadas = cotizaciones_ordenes.filter(cotizacion__usuario_acepto=True).count()
        cotizaciones_rechazadas = cotizaciones_ordenes.filter(cotizacion__usuario_acepto=False).count()
        cotizaciones_pendientes = cotizaciones_ordenes.filter(cotizacion__usuario_acepto__isnull=True).count()

        tasa_aceptacion = round(
            (cotizaciones_aceptadas / total_cotizaciones * 100) if total_cotizaciones > 0 else 0, 1
        )

        valor_cotizado = Decimal('0.00')
        valor_aceptado = Decimal('0.00')
        for orden in cotizaciones_ordenes.select_related('cotizacion'):
            cot = orden.cotizacion
            valor_cotizado += cot.costo_total
            if cot.usuario_acepto:
                valor_aceptado += cot.costo_total_final

        ventas_mostrador_qs = OrdenServicio.objects.filter(
            responsable_seguimiento=empleado,
            venta_mostrador__isnull=False,
            venta_mostrador__fecha_venta__gte=hace_90_dias,
        ).select_related('venta_mostrador')

        total_ventas_mostrador = ventas_mostrador_qs.count()
        monto_ventas_mostrador = Decimal('0.00')
        for orden in ventas_mostrador_qs:
            monto_ventas_mostrador += orden.venta_mostrador.total_venta

        encuestas_qs = FeedbackCliente.objects.filter(
            tipo='satisfaccion',
            orden__responsable_seguimiento=empleado,
            utilizado=True,
        )
        total_encuestas_respondidas = encuestas_qs.count()
        encuestas_avgs = encuestas_qs.aggregate(
            nps_promedio=Avg('nps'),
            calificacion_promedio=Avg('calificacion_general'),
        )
        nps_promedio = round(encuestas_avgs['nps_promedio'] or 0, 1)
        calificacion_promedio = round(encuestas_avgs['calificacion_promedio'] or 0, 1)

        con_recomendacion = encuestas_qs.filter(recomienda__isnull=False).count()
        recomiendan = encuestas_qs.filter(recomienda=True).count()
        tasa_recomendacion = round(
            (recomiendan / con_recomendacion * 100) if con_recomendacion > 0 else 0, 1
        )

        # Últimos 15 comentarios escritos por clientes (solo si tienen texto)
        comentarios_clientes = list(
            FeedbackCliente.objects.filter(
                tipo='satisfaccion',
                orden__responsable_seguimiento=empleado,
                utilizado=True,
                comentario_cliente__gt='',
            ).select_related('orden__detalle_equipo').order_by('-fecha_respuesta')[:15]
        )

        metricas.update({
            'total_cotizaciones': total_cotizaciones,
            'cotizaciones_aceptadas': cotizaciones_aceptadas,
            'cotizaciones_rechazadas': cotizaciones_rechazadas,
            'cotizaciones_pendientes': cotizaciones_pendientes,
            'tasa_aceptacion': tasa_aceptacion,
            'valor_cotizado': valor_cotizado,
            'valor_aceptado': valor_aceptado,
            'total_ventas_mostrador': total_ventas_mostrador,
            'monto_ventas_mostrador': monto_ventas_mostrador,
            'total_encuestas_respondidas': total_encuestas_respondidas,
            'nps_promedio': nps_promedio,
            'calificacion_promedio': calificacion_promedio,
            'tasa_recomendacion': tasa_recomendacion,
            'comentarios_clientes': comentarios_clientes,
        })

    # Métricas para técnico
    elif rol == 'tecnico':
        stats_activas = empleado.obtener_estadisticas_ordenes_activas()

        ordenes_tecnico_cot = OrdenServicio.objects.filter(
            tecnico_asignado_actual=empleado,
            cotizacion__isnull=False,
            cotizacion__fecha_envio__gte=hace_90_dias,
        ).select_related('cotizacion')

        total_cotizaciones = ordenes_tecnico_cot.count()
        cotizaciones_aceptadas = ordenes_tecnico_cot.filter(cotizacion__usuario_acepto=True).count()
        cotizaciones_rechazadas = ordenes_tecnico_cot.filter(cotizacion__usuario_acepto=False).count()

        tasa_aceptacion = round(
            (cotizaciones_aceptadas / total_cotizaciones * 100) if total_cotizaciones > 0 else 0, 1
        )

        valor_cotizado = Decimal('0.00')
        valor_aceptado = Decimal('0.00')
        for orden in ordenes_tecnico_cot:
            cot = orden.cotizacion
            valor_cotizado += cot.costo_total
            if cot.usuario_acepto:
                valor_aceptado += cot.costo_total_final

        ordenes_completadas_mes = OrdenServicio.objects.filter(
            tecnico_asignado_actual=empleado,
            estado='entregado',
            fecha_entrega__gte=inicio_mes,
        ).count()

        ordenes_rhitso = OrdenServicio.objects.filter(
            tecnico_asignado_actual=empleado,
            es_candidato_rhitso=True,
        ).exclude(estado__in=['cancelado']).count()

        encuestas_qs = FeedbackCliente.objects.filter(
            tipo='satisfaccion',
            orden__tecnico_asignado_actual=empleado,
            utilizado=True,
        )
        total_encuestas_respondidas = encuestas_qs.count()
        encuestas_avgs = encuestas_qs.aggregate(
            nps_promedio=Avg('nps'),
            calificacion_promedio=Avg('calificacion_general'),
        )
        nps_promedio = round(encuestas_avgs['nps_promedio'] or 0, 1)
        calificacion_promedio = round(encuestas_avgs['calificacion_promedio'] or 0, 1)

        metricas.update({
            'ordenes_activas_tecnico': stats_activas['ordenes_activas'],
            'equipos_no_encienden': stats_activas['equipos_no_encienden'],
            'tiene_sobrecarga': stats_activas['tiene_sobrecarga'],
            'total_cotizaciones': total_cotizaciones,
            'cotizaciones_aceptadas': cotizaciones_aceptadas,
            'cotizaciones_rechazadas': cotizaciones_rechazadas,
            'tasa_aceptacion': tasa_aceptacion,
            'valor_cotizado': valor_cotizado,
            'valor_aceptado': valor_aceptado,
            'ordenes_completadas_mes': ordenes_completadas_mes,
            'ordenes_rhitso': ordenes_rhitso,
            'total_encuestas_respondidas': total_encuestas_respondidas,
            'nps_promedio': nps_promedio,
            'calificacion_promedio': calificacion_promedio,
        })

    # Rating de desempeño (1-99)
    rating = 50
    if metricas.get('tasa_aceptacion', 0) > 0:
        rating += min(30, int(metricas['tasa_aceptacion'] * 0.3))
    if metricas.get('calificacion_promedio', 0) > 0:
        rating += min(15, int(metricas['calificacion_promedio'] * 3))
    if metricas.get('total_ventas_mostrador', 0) > 0:
        rating += min(4, int(metricas['total_ventas_mostrador'] * 0.5))
    rating = max(1, min(99, rating))

    rol_display = dict(empleado.ROL_CHOICES).get(rol, rol)
    return metricas, rating, rol, rol_display


def _calcular_rating_rapido(empleado):
    """
    Cálculo rápido del rating para las mini-cards del directorio.
    Evita consultas pesadas: solo usa tasa de aceptación y órdenes activas.
    Retorna un int entre 1 y 99.
    """
    from django.db.models import Q
    from datetime import timedelta
    from .models import Cotizacion

    ahora = timezone.now()
    hace_90_dias = ahora - timedelta(days=90)
    rol = empleado.rol
    rating = 50

    if rol == 'recepcionista':
        ordenes_cot = OrdenServicio.objects.filter(
            responsable_seguimiento=empleado,
            cotizacion__isnull=False,
            cotizacion__fecha_envio__gte=hace_90_dias,
        )
        total = ordenes_cot.count()
        aceptadas = ordenes_cot.filter(cotizacion__usuario_acepto=True).count()
        if total > 0:
            rating += min(30, int((aceptadas / total * 100) * 0.3))
        # Ventas mostrador
        ventas = OrdenServicio.objects.filter(
            responsable_seguimiento=empleado,
            venta_mostrador__isnull=False,
            venta_mostrador__fecha_venta__gte=hace_90_dias,
        ).count()
        rating += min(4, int(ventas * 0.5))

    elif rol == 'tecnico':
        ordenes_cot = OrdenServicio.objects.filter(
            tecnico_asignado_actual=empleado,
            cotizacion__isnull=False,
            cotizacion__fecha_envio__gte=hace_90_dias,
        )
        total = ordenes_cot.count()
        aceptadas = ordenes_cot.filter(cotizacion__usuario_acepto=True).count()
        if total > 0:
            rating += min(30, int((aceptadas / total * 100) * 0.3))

    return max(1, min(99, rating))


# ============================================================================
# MI PERFIL — MÉTRICAS PERSONALES DEL EMPLEADO (Marzo 2026)
# ============================================================================

@login_required
def mi_perfil(request):
    """
    Página "Mi Perfil" con tarjeta de métricas personales.
    Muestra métricas personalizadas según el rol del empleado:
      - Recepcionista: cotizaciones gestionadas, ventas mostrador, encuestas
      - Técnico: órdenes asignadas, cotizaciones donde participó, RHITSO
    """
    empleado = getattr(request.user, 'empleado', None)
    if not empleado:
        messages.warning(request, 'Tu cuenta no tiene un perfil de empleado asociado.')
        return redirect('servicio_tecnico:inicio')

    metricas, rating, rol, rol_display = _calcular_metricas_empleado(empleado)

    context = {
        'empleado': empleado,
        'rol': rol,
        'rol_display': rol_display,
        'metricas': metricas,
        'rating': rating,
    }

    return render(request, 'servicio_tecnico/mi_perfil.html', context)


# ============================================================================
# DIRECTORIO DE EMPLEADOS — VISTA GERENCIAL (Marzo 2026)
# ============================================================================

ROLES_GERENCIALES = ('gerente_general', 'gerente_operacional', 'supervisor')


@login_required
def directorio_empleados(request):
    """
    Vista gerencial: muestra una cuadrícula de mini-cards con todos los
    empleados activos. Cada card muestra avatar, nombre, rol y rating rápido.
    Solo accesible para roles gerenciales.
    """
    empleado_actual = getattr(request.user, 'empleado', None)
    if not empleado_actual or empleado_actual.rol not in ROLES_GERENCIALES:
        messages.error(request, 'No tienes permiso para acceder al directorio de empleados.')
        return redirect('servicio_tecnico:inicio')

    # Filtros opcionales (GET params)
    filtro_rol = request.GET.get('rol', '')
    filtro_sucursal = request.GET.get('sucursal', '')
    busqueda = request.GET.get('q', '').strip()

    empleados_qs = Empleado.objects.filter(
        activo=True
    ).select_related('user', 'sucursal').order_by('nombre_completo')

    if filtro_rol:
        empleados_qs = empleados_qs.filter(rol=filtro_rol)
    if filtro_sucursal:
        empleados_qs = empleados_qs.filter(sucursal_id=filtro_sucursal)
    if busqueda:
        empleados_qs = empleados_qs.filter(
            Q(nombre_completo__icontains=busqueda) |
            Q(cargo__icontains=busqueda)
        )

    # Calcular rating rápido para cada empleado
    empleados_data = []
    from .models import FeedbackCliente
    for emp in empleados_qs:
        rating = _calcular_rating_rapido(emp)
        # Comentarios de clientes — solo para recepcionistas
        comentarios_clientes = []
        if emp.rol == 'recepcionista':
            comentarios_clientes = list(
                FeedbackCliente.objects.filter(
                    tipo='satisfaccion',
                    orden__responsable_seguimiento=emp,
                    utilizado=True,
                    comentario_cliente__gt='',
                ).select_related('orden__detalle_equipo').order_by('-fecha_respuesta')[:15]
            )
        empleados_data.append({
            'empleado': emp,
            'rating': rating,
            'rol_display': dict(Empleado.ROL_CHOICES).get(emp.rol, emp.rol),
            'comentarios_clientes': comentarios_clientes,
        })

    # Datos para filtros
    roles_disponibles = Empleado.ROL_CHOICES
    sucursales_disponibles = Sucursal.objects.filter(activa=True).order_by('nombre')

    context = {
        'empleados_data': empleados_data,
        'total_empleados': len(empleados_data),
        'roles_disponibles': roles_disponibles,
        'sucursales_disponibles': sucursales_disponibles,
        'filtro_rol': filtro_rol,
        'filtro_sucursal': filtro_sucursal,
        'busqueda': busqueda,
    }

    return render(request, 'servicio_tecnico/directorio_empleados.html', context)


@login_required
def perfil_empleado(request, empleado_id):
    """
    Vista gerencial: muestra la tarjeta completa de un empleado específico.
    Reutiliza la misma template de mi_perfil con contexto adicional.
    Solo accesible para roles gerenciales.
    """
    empleado_actual = getattr(request.user, 'empleado', None)
    if not empleado_actual or empleado_actual.rol not in ROLES_GERENCIALES:
        messages.error(request, 'No tienes permiso para ver perfiles de otros empleados.')
        return redirect('servicio_tecnico:inicio')

    empleado = get_object_or_404(Empleado, pk=empleado_id, activo=True)
    metricas, rating, rol, rol_display = _calcular_metricas_empleado(empleado)

    context = {
        'empleado': empleado,
        'rol': rol,
        'rol_display': rol_display,
        'metricas': metricas,
        'rating': rating,
        'es_vista_directorio': True,
    }

    return render(request, 'servicio_tecnico/mi_perfil.html', context)
