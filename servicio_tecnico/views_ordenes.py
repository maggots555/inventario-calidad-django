"""
Vistas de órdenes: inicio, crear, listas y cierre (Fase 9 modularización).

EXPLICACIÓN PARA PRINCIPIANTES:
Home de Servicio Técnico, alta de órdenes (diagnóstico / venta mostrador),
listas activas/finalizadas y acciones de cerrar.
urls.py sigue usando views.<nombre> porque views.py reexporta estos símbolos.
NO incluye detalle_orden (eso es Fase 10 — alto riesgo).
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from inventario.models import Empleado

from config.constants import ESTADO_ORDEN_CHOICES

from .decorators import permission_required_with_message
from .forms import NuevaOrdenForm, NuevaOrdenVentaMostradorForm
from .models import HistorialOrden, IncidenciaRHITSO, OrdenServicio


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


