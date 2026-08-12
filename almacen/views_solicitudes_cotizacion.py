"""
Solicitudes de cotización multi-proveedor: CRUD, detalle, servicios e imágenes.

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
Extraído de views.py (Fase 4 de modularización Almacén).
Aquí se crea/edita la SolicitudCotizacion y se gestionan líneas,
servicios adicionales e imágenes. El envío al cliente y el sync ST
viven en módulos hermanos.

urls.py sigue usando views.lista_solicitudes_cotizacion, etc.
porque views.py reexporta estos nombres.

Efectos secundarios:
- CRUD SolicitudCotizacion / LineaCotizacion / LineaServicioAdicional
- Imágenes de línea (upload/delete)
- Push/notificaciones al crear solicitud (via tasks)
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from inventario.models import Empleado

from .decorators import permission_required_with_message
from .forms import (
    ImagenLineaCotizacionForm,
    LineaCotizacionFormSet,
    LineaCotizacionFormSetCreacion,
    LineaServicioAdicionalForm,
    SolicitudCotizacionFiltroForm,
    SolicitudCotizacionForm,
)
from .models import (
    ImagenLineaCotizacion,
    ImagenSolicitudCotizacion,
    LineaCotizacion,
    LineaServicioAdicional,
    ProductoAlmacen,
    Proveedor,
    SolicitudCotizacion,
)
from .utils.cotizacion_reacondicionado_helpers import (
    _opciones_servicios_adicionales,
    _serializar_costeo_reacondicionado_config,
    _serializar_profit_config,
)

import logging

logger = logging.getLogger('almacen')


# ============================================================================
# SOLICITUDES DE COTIZACIÓN (MULTI-PROVEEDOR)
# ============================================================================

@login_required
@permission_required_with_message('almacen.view_solicitudcotizacion')
def lista_solicitudes_cotizacion(request):
    """
    Lista todas las solicitudes de cotización con filtros.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista muestra todas las solicitudes de cotización en una tabla.
    Permite filtrar por:
    - Estado (borrador, enviada, aprobada, etc.)
    - Fecha de creación
    - Búsqueda por número de solicitud u orden
    
    También muestra un resumen con contadores por estado para una
    visión rápida del flujo de trabajo.
    """
    # Obtener todas las solicitudes
    solicitudes = SolicitudCotizacion.objects.select_related(
        'orden_servicio',
        'creado_por'
    ).prefetch_related('lineas').order_by('-fecha_creacion')
    
    # Aplicar filtros
    filtro_form = SolicitudCotizacionFiltroForm(request.GET)
    
    if filtro_form.is_valid():
        estado = filtro_form.cleaned_data.get('estado')
        fecha_desde = filtro_form.cleaned_data.get('fecha_desde')
        fecha_hasta = filtro_form.cleaned_data.get('fecha_hasta')
        buscar = filtro_form.cleaned_data.get('buscar')
        
        if estado:
            solicitudes = solicitudes.filter(estado=estado)
        
        if fecha_desde:
            solicitudes = solicitudes.filter(fecha_creacion__date__gte=fecha_desde)
        
        if fecha_hasta:
            solicitudes = solicitudes.filter(fecha_creacion__date__lte=fecha_hasta)
        
        if buscar:
            solicitudes = solicitudes.filter(
                Q(numero_solicitud__icontains=buscar) |
                Q(numero_orden_cliente__icontains=buscar)
            )
    
    # Contadores por estado para el resumen
    contadores = SolicitudCotizacion.objects.values('estado').annotate(
        total=Count('id')
    )
    contadores_dict = {c['estado']: c['total'] for c in contadores}
    
    # Paginación
    paginator = Paginator(solicitudes, 20)
    page = request.GET.get('page', 1)
    solicitudes_page = paginator.get_page(page)
    
    context = {
        'solicitudes': solicitudes_page,
        'filtro_form': filtro_form,
        'contadores': contadores_dict,
        'titulo': 'Solicitudes de Cotización',
        # Para resaltar el KPI activo y mostrar el total en el encabezado
        'estado_filtro': request.GET.get('estado', ''),
        'total_general': sum(contadores_dict.values()),
    }
    
    return render(request, 'almacen/cotizaciones/lista_solicitudes.html', context)


@login_required
@permission_required_with_message('almacen.add_solicitudcotizacion')
def crear_solicitud_cotizacion(request):
    """
    Crear una nueva solicitud de cotización con múltiples líneas.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista maneja la creación de una solicitud de cotización.
    
    El proceso tiene tres partes:
    1. El formulario principal (SolicitudCotizacionForm) captura:
       - Número de orden del cliente (para vincular con servicio técnico)
       - O modo sin orden: datos del cliente + service tag + marca/modelo
       - Observaciones internas
    
    2. El formset (LineaCotizacionFormSet) captura las líneas:
       - Cada línea tiene: producto, descripción, proveedor, cantidad, costo
       - Se pueden agregar múltiples líneas dinámicamente con JavaScript
    
    3. Las imágenes de referencia (request.FILES):
       - Hasta 6 imágenes del equipo/piezas que el cliente quiere cotizar
       - Se procesan después de guardar la solicitud
    
    Flujo:
    1. GET: Muestra formularios vacíos
    2. POST: Valida ambos formularios
       - Si válidos: Guarda solicitud, líneas e imágenes, redirige a detalle
       - Si inválidos: Muestra errores

    Efectos secundarios:
    - Sin orden activa: push/campanita/email a Compras
    - Con orden vinculada: sync ST → cotizacion_enviada_proveedor
      (no aplica al vincular/crear FL después; es otro hilo)
    """
    if request.method == 'POST':
        form = SolicitudCotizacionForm(request.POST)
        formset = LineaCotizacionFormSetCreacion(request.POST)
        
        if form.is_valid() and formset.is_valid():
            # Guardar la solicitud (cabecera)
            solicitud = form.save(commit=False)
            solicitud.creado_por = request.user
            solicitud.save()
            
            # Guardar las líneas (detalle)
            formset.instance = solicitud
            formset.save()
            
            # Procesar imágenes de referencia (hasta 6)
            imagenes = request.FILES.getlist('imagenes_referencia')
            descripciones = request.POST.getlist('descripcion_imagen')
            imagenes_guardadas = 0
            
            for i, imagen in enumerate(imagenes):
                if imagenes_guardadas >= ImagenSolicitudCotizacion.MAX_IMAGENES_POR_SOLICITUD:
                    break
                try:
                    descripcion = descripciones[i] if i < len(descripciones) else ''
                    ImagenSolicitudCotizacion.objects.create(
                        solicitud=solicitud,
                        imagen=imagen,
                        descripcion=descripcion,
                        subido_por=request.user,
                    )
                    imagenes_guardadas += 1
                except (ValueError, Exception) as e:
                    messages.warning(request, f'Error al subir imagen: {str(e)}')
            
            if imagenes_guardadas > 0:
                messages.info(request, f'{imagenes_guardadas} imagen(es) de referencia subidas.')

            # =================================================================
            # NOTIFICAR A COMPRAS cuando la solicitud es "Sin Orden Activa"
            # =================================================================
            # EXPLICACIÓN PARA PRINCIPIANTES:
            # Cuando una solicitud se crea sin una orden de servicio vinculada
            # (modo "sin orden activa"), el área de Compras necesita saberlo
            # de inmediato para procesar la cotización. Les enviamos:
            #   1. Push al dispositivo (notificación en tiempo real)
            #   2. Campanita interna (notificación del sistema)
            #   3. Email en segundo plano vía Celery (no bloquea al usuario)
            if solicitud.sin_orden_activa:
                try:
                    from notificaciones.push_service import enviar_push_a_usuario
                    from notificaciones.utils import notificar_info
                    from .tasks import notificar_compras_nueva_cotizacion_task

                    # Buscar todos los empleados con rol "Compras" que tengan
                    # usuario activo en el sistema (pueden recibir notificaciones)
                    compradores = Empleado.objects.filter(
                        rol='compras',
                        user__is_active=True,
                    ).select_related('user')

                    if compradores.exists():
                        # Construir la URL al detalle de la solicitud para que
                        # al hacer clic en la notificación los lleve directamente
                        url_solicitud = reverse(
                            'almacen:detalle_solicitud_cotizacion',
                            kwargs={'pk': solicitud.pk}
                        )

                        # Texto de la notificación — incluye el nombre del
                        # cliente y el service tag para identificación rápida
                        titulo_push = f'📋 Nueva cotización sin orden: {solicitud.numero_solicitud}'
                        mensaje_push = (
                            f'Cliente: {solicitud.nombre_cliente or "Sin nombre"} — '
                            f'S/T: {solicitud.service_tag or "N/A"}. '
                            f'Requiere atención para procesar la cotización.'
                        )

                        # Enviar push + campanita a cada empleado de Compras
                        for comprador in compradores:
                            try:
                                enviar_push_a_usuario(
                                    usuario=comprador.user,
                                    titulo=titulo_push,
                                    mensaje=mensaje_push,
                                    url=url_solicitud,
                                )
                            except Exception as push_err:
                                logger.warning(
                                    f"[COTIZACION] Error enviando push a {comprador.nombre_completo}: {push_err}"
                                )

                            try:
                                notificar_info(
                                    titulo=titulo_push,
                                    mensaje=mensaje_push,
                                    usuario=comprador.user,
                                    url=url_solicitud,
                                    app_origen='almacen',
                                )
                            except Exception as notif_err:
                                logger.warning(
                                    f"[COTIZACION] Error creando notificación para {comprador.nombre_completo}: {notif_err}"
                                )

                        # Enviar email en segundo plano vía Celery (no bloquea)
                        from config.paises_config import get_pais_actual
                        notificar_compras_nueva_cotizacion_task.delay(
                            solicitud.pk,
                            request.user.pk,
                            get_pais_actual()['db_alias'],
                        )
                        logger.info(
                            f"[COTIZACION] Notificaciones enviadas a {compradores.count()} "
                            f"empleado(s) de Compras para solicitud {solicitud.numero_solicitud}"
                        )
                except Exception as e:
                    # Si falla la notificación, NO debe impedir que la solicitud
                    # se haya creado correctamente. Solo registramos el error.
                    logger.error(f"[COTIZACION] Error al notificar a Compras: {e}")

            # =================================================================
            # SYNC ST: con orden vinculada → «Envío de Cotización al Proveedor»
            # =================================================================
            # EXPLICACIÓN PARA PRINCIPIANTES:
            # Si la solicitud nace YA ligada a una OrdenServicio (no es modo
            # sin_orden_activa), el primer hito en ST es avisar que se pidió
            # cotización a proveedores. El util tiene guardias anti-regresión
            # (no pisa reparación, esperando piezas, etc.).
            # NO se aplica al vincular/crear orden FL después: es otro hilo.
            elif solicitud.orden_servicio_id:
                try:
                    from .utils.sincronizar_estado_st import (
                        sincronizar_estado_st_al_crear_solicitud,
                    )
                    sincronizar_estado_st_al_crear_solicitud(
                        solicitud,
                        usuario=request.user,
                    )
                except Exception as e:
                    # Si falla el sync de estado, la solicitud ya existe;
                    # solo registramos el error para no perder el alta.
                    logger.error(
                        f"[COTIZACION] Error al sincronizar estado ST al crear "
                        f"solicitud {solicitud.numero_solicitud}: {e}"
                    )

            messages.success(
                request,
                f'Solicitud de cotización {solicitud.numero_solicitud} creada exitosamente.'
            )
            return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud.pk)
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = SolicitudCotizacionForm()
        formset = LineaCotizacionFormSetCreacion()

    # Obtener la sucursal del usuario logueado para mostrarla en el formulario
    # cuando se usa el modo "sin orden activa". Se muestra como dato informativo
    # (solo lectura) para que el técnico sepa desde qué sucursal está cotizando.
    sucursal_usuario = None
    try:
        sucursal_usuario = request.user.empleado.sucursal
    except Exception:
        # El usuario puede no tener perfil de empleado o sucursal asignada — es válido
        pass

    context = {
        'form': form,
        'formset': formset,
        'titulo': 'Nueva Solicitud de Cotización',
        'es_creacion': True,
        'max_imagenes_referencia': ImagenSolicitudCotizacion.MAX_IMAGENES_POR_SOLICITUD,
        # Sucursal del usuario actual, para pre-mostrar en modo sin orden activa
        'sucursal_usuario': sucursal_usuario,
    }
    
    return render(request, 'almacen/cotizaciones/form_solicitud.html', context)


@login_required
@permission_required_with_message('almacen.change_solicitudcotizacion')
def editar_solicitud_cotizacion(request, pk):
    """
    Editar una solicitud de cotización existente.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Similar a crear, pero carga los datos existentes en los formularios.
    
    Solo se puede editar si la solicitud está en estado 'borrador'.
    Una vez enviada al cliente, no se puede modificar.
    
    También permite agregar más imágenes de referencia.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    # Solo se puede editar en estado borrador
    if solicitud.estado != 'borrador':
        messages.error(
            request,
            'Solo se pueden editar solicitudes en estado borrador.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
    
    if request.method == 'POST':
        form = SolicitudCotizacionForm(request.POST, instance=solicitud)
        formset = LineaCotizacionFormSet(request.POST, instance=solicitud)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            
            # Procesar imágenes de referencia nuevas (hasta el límite)
            imagenes = request.FILES.getlist('imagenes_referencia')
            descripciones = request.POST.getlist('descripcion_imagen')
            imagenes_guardadas = 0
            
            for i, imagen in enumerate(imagenes):
                if not ImagenSolicitudCotizacion.puede_agregar_imagen(solicitud):
                    messages.warning(
                        request,
                        f'Se alcanzó el límite de {ImagenSolicitudCotizacion.MAX_IMAGENES_POR_SOLICITUD} imágenes.'
                    )
                    break
                try:
                    descripcion = descripciones[i] if i < len(descripciones) else ''
                    ImagenSolicitudCotizacion.objects.create(
                        solicitud=solicitud,
                        imagen=imagen,
                        descripcion=descripcion,
                        subido_por=request.user,
                    )
                    imagenes_guardadas += 1
                except (ValueError, Exception) as e:
                    messages.warning(request, f'Error al subir imagen: {str(e)}')
            
            if imagenes_guardadas > 0:
                messages.info(request, f'{imagenes_guardadas} imagen(es) de referencia agregadas.')
            
            messages.success(request, 'Solicitud actualizada exitosamente.')
            return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = SolicitudCotizacionForm(instance=solicitud)
        formset = LineaCotizacionFormSet(instance=solicitud)
    
    # Calcular imágenes restantes
    imagenes_actuales = ImagenSolicitudCotizacion.objects.filter(solicitud=solicitud).count()
    imagenes_restantes = max(0, ImagenSolicitudCotizacion.MAX_IMAGENES_POR_SOLICITUD - imagenes_actuales)
    
    context = {
        'form': form,
        'formset': formset,
        'solicitud': solicitud,
        'titulo': f'Editar Solicitud {solicitud.numero_solicitud}',
        'es_creacion': False,
        'max_imagenes_referencia': ImagenSolicitudCotizacion.MAX_IMAGENES_POR_SOLICITUD,
        'imagenes_referencia_actuales': imagenes_actuales,
        'imagenes_referencia_restantes': imagenes_restantes,
    }
    
    return render(request, 'almacen/cotizaciones/form_solicitud.html', context)


@login_required
@permission_required_with_message('almacen.change_lineacotizacion')
def editar_lineas_cotizacion(request, pk):
    """
    Editar líneas de cotización cuando la solicitud está en estado 'enviada_front'.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista permite modificar ciertos campos de las líneas de cotización
    DESPUÉS de que la solicitud fue enviada a Front, pero ANTES de que el
    cliente apruebe o se genere la compra.
    
    ¿Qué se puede editar?
    - Proveedor (si el original no tiene stock)
    - Costo unitario (si cambió el precio)
    - Cantidad (si el cliente pide más/menos)
    - Tiempo de entrega estimado
    - Notas adicionales
    
    ¿Qué NO se puede editar?
    - Producto (ya fue definido)
    - Descripción de la pieza (es la identidad)
    
    ¿Qué líneas se pueden editar?
    - Solo las que tienen estado 'pendiente' o 'rechazada'
    - Las líneas 'aprobada' o 'compra_generada' se muestran como solo lectura
    
    IMPORTANTE: El formset solo incluye las líneas editables.
    Las líneas bloqueadas se muestran como texto plano fuera del formset.
    """
    from .forms import EditarLineaCotizacionFormSet
    from .models import LineaCotizacion
    
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    # Se puede editar líneas en enviada_front o enviada_cliente (por si se necesita recotizar)
    if solicitud.estado not in ['enviada_front', 'enviada_cliente']:
        messages.error(
            request,
            'Solo se pueden editar líneas cuando la solicitud está en estado "Enviada a Front" o "Enviada a Cliente".'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
    
    # Filtrar solo líneas editables (pendiente o rechazada)
    lineas_editables_qs = solicitud.lineas.filter(
        estado_cliente__in=['pendiente', 'rechazada']
    ).order_by('numero_linea')
    
    # Líneas bloqueadas (aprobada o compra_generada) - solo para mostrar
    lineas_bloqueadas = solicitud.lineas.filter(
        estado_cliente__in=['aprobada', 'compra_generada']
    ).order_by('numero_linea')
    
    if request.method == 'POST':
        # El formset solo procesa líneas editables
        formset = EditarLineaCotizacionFormSet(
            request.POST,
            instance=solicitud,
            queryset=lineas_editables_qs
        )
        
        if formset.is_valid():
            # Guardar cambios y contar cuántas líneas se modificaron
            lineas_modificadas = 0
            
            for form in formset.forms:
                if form.has_changed():
                    form.save()
                    lineas_modificadas += 1
            
            if lineas_modificadas > 0:
                messages.success(
                    request,
                    f'Se actualizaron {lineas_modificadas} línea(s) de la cotización.'
                )
            else:
                messages.info(request, 'No se realizaron cambios en las líneas.')
            
            return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        formset = EditarLineaCotizacionFormSet(
            instance=solicitud,
            queryset=lineas_editables_qs
        )
    
    # Preparar información para el template
    lineas_editables_info = []
    for form, linea in zip(formset.forms, lineas_editables_qs):
        lineas_editables_info.append({
            'form': form,
            'linea': linea,
        })
    
    context = {
        'formset': formset,
        'solicitud': solicitud,
        'lineas_editables_info': lineas_editables_info,
        'lineas_bloqueadas': lineas_bloqueadas,
        'titulo': f'Editar Líneas - {solicitud.numero_solicitud}',
    }
    
    return render(request, 'almacen/cotizaciones/editar_lineas.html', context)


@login_required
@permission_required_with_message('almacen.view_solicitudcotizacion')
def detalle_solicitud_cotizacion(request, pk):
    """
    Ver detalle completo de una solicitud de cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista muestra toda la información de una solicitud:
    - Datos de la cabecera (número, orden vinculada, estado)
    - Sugerencias de piezas del diagnóstico (si la orden ya las tiene)
    - Tabla con todas las líneas y sus estados
    - Imágenes de referencia de cada línea
    - Totales y resúmenes
    - Acciones disponibles según el estado
    
    Las acciones cambian según el estado:
    - Borrador: Editar, Enviar a cliente, Cancelar, Subir imágenes
    - Enviada: Registrar respuestas del cliente
    - Aprobada: Generar compras
    - Completada: Solo visualización
    
    También permite subir imágenes a las líneas cuando está en borrador.
    """
    solicitud = get_object_or_404(
        SolicitudCotizacion.objects.select_related(
            'orden_servicio',
            'orden_servicio__sucursal',        # Sucursal de la orden vinculada
            'orden_servicio__detalle_equipo',  # Detalle (incluye sugerencias de diagnóstico)
            'creado_por',
            'creado_por__empleado',            # Perfil de empleado del creador
            'creado_por__empleado__sucursal',  # Sucursal del creador (para sin_orden_activa)
        ).prefetch_related(
            'lineas__producto',
            'lineas__proveedor',
            'lineas__compra_generada',
            'lineas__imagenes',  # Incluir imágenes de cada línea
            'imagenes_referencia',  # Incluir imágenes de referencia de la solicitud
        ),
        pk=pk
    )
    
    # Información del equipo desde DetalleEquipo si está vinculada la orden
    info_orden = None
    if solicitud.orden_servicio:
        try:
            info_orden = solicitud.orden_servicio.detalle_equipo
        except Exception:
            pass

    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Al enviar el diagnóstico en ST se guardan piezas_sugeridas_diagnostico (JSON).
    # Front las ve aquí para comparar vs lo que cotizó Compras. No se editan desde Almacén.
    piezas_sugeridas_diagnostico = []
    if info_orden:
        sugerencias_raw = getattr(info_orden, 'piezas_sugeridas_diagnostico', None) or []
        if isinstance(sugerencias_raw, list):
            for item in sugerencias_raw:
                if not isinstance(item, dict):
                    continue
                componente = (item.get('componente_db') or '').strip()
                if not componente:
                    continue
                piezas_sugeridas_diagnostico.append({
                    'componente_db': componente,
                    'dpn': (item.get('dpn') or '').strip(),
                    'es_necesaria': bool(item.get('es_necesaria', True)),
                })

    # --- Datos extra para el modal de envío de cotización al cliente ---
    # Obtenemos gama, mano de obra y email del cliente para pre-llenar el modal

    # Gama del equipo (alta/media/baja) — solo disponible si hay orden vinculada
    gama_equipo = ''
    if info_orden:
        gama_equipo = getattr(info_orden, 'gama', '') or ''

    # Costo de mano de obra desde la Cotizacion de Servicio Técnico
    # (el usuario puede sobreescribirlo en el modal si lo desea)
    costo_mano_obra = None
    if solicitud.orden_servicio:
        try:
            # La Cotizacion está vinculada 1:1 a la OrdenServicio
            cotizacion_st = solicitud.orden_servicio.cotizacion
            costo_mano_obra = float(cotizacion_st.costo_mano_obra)
        except Exception:
            # La orden puede no tener cotización aún — es normal
            pass

    # Email del cliente para el campo "Destinatario" del modal
    email_cliente_modal = ''
    if info_orden:
        email_raw = getattr(info_orden, 'email_cliente', '') or ''
        # Excluir el email placeholder que usa ST cuando no hay email real
        if email_raw and email_raw != 'cliente@ejemplo.com':
            email_cliente_modal = email_raw
    elif solicitud.email_cliente:
        email_cliente_modal = solicitud.email_cliente

    # Asunto sugerido para el modal: prefijo + orden cliente o service tag
    from .utils.cotizacion_email_context import construir_asunto_correo_default
    asunto_correo_modal = construir_asunto_correo_default(solicitud, info_orden=info_orden)
    
    # Procesar subida de imagen (solo en estado borrador)
    mensaje_imagen = None
    if request.method == 'POST' and solicitud.estado == 'borrador':
        linea_pk = request.POST.get('linea_pk')
        if linea_pk and 'imagen' in request.FILES:
            try:
                linea = solicitud.lineas.get(pk=linea_pk)
                form = ImagenLineaCotizacionForm(
                    request.POST,
                    request.FILES,
                    linea=linea
                )
                if form.is_valid():
                    imagen = form.save(commit=False)
                    imagen.linea = linea
                    imagen.subido_por = request.user
                    imagen.save()
                    messages.success(
                        request,
                        f'Imagen subida exitosamente a la línea #{linea.numero_linea}.'
                    )
                else:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f'{error}')
            except LineaCotizacion.DoesNotExist:
                messages.error(request, 'Línea no encontrada.')
            except ValueError as e:
                messages.error(request, str(e))
            
            # Redirigir para evitar reenvío del formulario
            return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
    
    # Verificar si se puede subir imágenes
    puede_subir_imagenes = solicitud.estado == 'borrador'
    
    # Imágenes de referencia de la solicitud
    imagenes_referencia = solicitud.imagenes_referencia.all()
    max_imagenes_referencia = ImagenSolicitudCotizacion.MAX_IMAGENES_POR_SOLICITUD
    
    # Empleados disponibles para copia en notificación a front
    empleados_copia = Empleado.objects.filter(
        Q(area='CALIDAD') | Q(area='FRONTDESK') | Q(area='CARRY IN'),
        activo=True,
        email__isnull=False
    ).exclude(
        email=''
    ).order_by('area', 'nombre_completo')
    
    # Verificar si el usuario actual está en la lista de CC
    usuario_en_lista_cc = False
    if hasattr(request.user, 'empleado') and request.user.empleado:
        usuario_en_lista_cc = empleados_copia.filter(id=request.user.empleado.id).exists()

    # --- Sucursal para mostrar en el encabezado de la solicitud ---
    # Con orden: se obtiene directamente de la FK orden_servicio → sucursal
    sucursal_orden = None
    if solicitud.orden_servicio:
        sucursal_orden = solicitud.orden_servicio.sucursal

    # Sin orden activa: se obtiene del perfil de empleado de quien creó la solicitud.
    # El select_related ya cargó el camino creado_por → empleado → sucursal,
    # por lo que esto no genera queries adicionales.
    sucursal_creador = None
    try:
        sucursal_creador = solicitud.creado_por.empleado.sucursal
    except Exception:
        # El usuario puede no tener perfil de empleado o sucursal asignada — es válido
        pass

    from .utils.cotizacion_items_cliente import (
        puede_mostrar_enviar_cotizacion_cliente,
        solicitud_permite_aprobar_lineas,
        solicitud_puede_descargar_pdf_final,
        solicitud_tiene_items_cotizables,
    )
    from config.constants import (
        MOTIVO_RECHAZO_COTIZACION,
        MOTIVOS_RECHAZO_CON_FEEDBACK,
        MOTIVOS_RECHAZO_VIGENCIA_VENCIDA,
    )
    from .utils.sincronizar_rechazo_cotizacion_st import (
        admite_motivo_rechazo_almacen,
        armar_detalle_rechazo_desde_items,
        label_motivo_rechazo,
        orden_admite_cotizacion_st,
        solicitud_requiere_motivo_rechazo_almacen,
        solicitud_requiere_motivo_rechazo_st,
    )
    import json as _json_motivos
    from almacen.utils.profit_por_pieza import (
        rangos_profit_minimo_para_frontend,
        rangos_profit_minimo_por_perfil_para_frontend,
    )

    mostrar_modal_motivo_rechazo_st = solicitud_requiere_motivo_rechazo_st(solicitud)
    admite_motivo_rechazo_st = orden_admite_cotizacion_st(solicitud.orden_servicio)

    # Flujo paralelo: rechazo total SIN orden ST → tipificar en SolicitudCotizacion
    mostrar_modal_motivo_rechazo_almacen = solicitud_requiere_motivo_rechazo_almacen(
        solicitud,
    )
    admite_motivo_rechazo_almacen_flag = admite_motivo_rechazo_almacen(solicitud)

    # Valores ya guardados en Cotizacion ST (para precargar "Ver / editar")
    motivo_rechazo_st_actual = ''
    detalle_rechazo_st_actual = ''
    motivo_rechazo_st_etiqueta = ''
    if solicitud.orden_servicio_id and admite_motivo_rechazo_st:
        from servicio_tecnico.models import Cotizacion

        try:
            cotizacion_st_rechazo = Cotizacion.objects.get(
                orden_id=solicitud.orden_servicio_id,
            )
            motivo_rechazo_st_actual = cotizacion_st_rechazo.motivo_rechazo or ''
            detalle_rechazo_st_actual = cotizacion_st_rechazo.detalle_rechazo or ''
            if motivo_rechazo_st_actual:
                motivo_rechazo_st_etiqueta = label_motivo_rechazo(motivo_rechazo_st_actual)
        except Cotizacion.DoesNotExist:
            pass

    # Cabecera Almacén: motivo guardado o prefill desde piezas/servicios
    motivo_rechazo_solicitud_actual = ''
    detalle_rechazo_solicitud_actual = ''
    motivo_rechazo_solicitud_etiqueta = ''
    if admite_motivo_rechazo_almacen_flag:
        motivo_rechazo_solicitud_actual = solicitud.motivo_rechazo or ''
        if motivo_rechazo_solicitud_actual:
            motivo_rechazo_solicitud_etiqueta = label_motivo_rechazo(
                motivo_rechazo_solicitud_actual,
            )
        # EXPLICACIÓN: si aún no hay detalle guardado, armamos resumen de ítems
        detalle_guardado = (solicitud.detalle_rechazo or '').strip()
        if detalle_guardado:
            detalle_rechazo_solicitud_actual = detalle_guardado
        else:
            detalle_rechazo_solicitud_actual = armar_detalle_rechazo_desde_items(
                solicitud,
            )

    context = {
        'solicitud': solicitud,
        'info_orden': info_orden,
        'piezas_sugeridas_diagnostico': piezas_sugeridas_diagnostico,
        'titulo': f'Solicitud {solicitud.numero_solicitud}',
        'puede_subir_imagenes': puede_subir_imagenes,
        'max_imagenes_por_linea': ImagenLineaCotizacion.MAX_IMAGENES_POR_LINEA,
        'imagenes_referencia': imagenes_referencia,
        'max_imagenes_referencia': max_imagenes_referencia,
        'empleados_copia': empleados_copia,
        'usuario_en_lista_cc': usuario_en_lista_cc,
        # Sucursal del encabezado: con orden → de la orden; sin orden → del creador
        'sucursal_orden': sucursal_orden,
        'sucursal_creador': sucursal_creador,
        # Datos para el modal "Enviar Cotización al Cliente"
        'gama_equipo': gama_equipo,
        'costo_mano_obra': costo_mano_obra,
        'email_cliente_modal': email_cliente_modal,
        'asunto_correo_modal': asunto_correo_modal,
        # Configuración de profit serializada como JSON para inyectarla en el
        # template y leerla desde TypeScript. Los valores vienen del .env
        # (nunca del código fuente), así que no aparecen en el repositorio.
        'profit_config_json': _serializar_profit_config(),
        # Rangos de margen mínimo: semilla (fallback) + mapa por perfil (BD)
        'rangos_profit_minimo_json': _json_motivos.dumps(
            rangos_profit_minimo_para_frontend()
        ),
        'rangos_profit_minimo_por_perfil_json': _json_motivos.dumps(
            rangos_profit_minimo_por_perfil_para_frontend()
        ),
        'costeo_reac_config_json': _serializar_costeo_reacondicionado_config(),
        # Opciones del dropdown "Agregar Servicio Adicional" (precios desde constants.py)
        'servicios_adicionales_opciones': _opciones_servicios_adicionales(),
        # Modal motivo catálogo ST
        'mostrar_modal_motivo_rechazo_st': mostrar_modal_motivo_rechazo_st,
        'admite_motivo_rechazo_st': admite_motivo_rechazo_st,
        'motivos_rechazo_cotizacion': MOTIVO_RECHAZO_COTIZACION,
        'email_cliente_rechazo': email_cliente_modal,
        'motivos_rechazo_con_feedback_json': _json_motivos.dumps(
            sorted(MOTIVOS_RECHAZO_CON_FEEDBACK | MOTIVOS_RECHAZO_VIGENCIA_VENCIDA)
        ),
        'motivo_rechazo_st_actual': motivo_rechazo_st_actual,
        'detalle_rechazo_st_actual': detalle_rechazo_st_actual,
        'motivo_rechazo_st_etiqueta': motivo_rechazo_st_etiqueta,
        # Modal motivo cabecera Almacén (sin orden / FL-)
        'mostrar_modal_motivo_rechazo_almacen': mostrar_modal_motivo_rechazo_almacen,
        'admite_motivo_rechazo_almacen': admite_motivo_rechazo_almacen_flag,
        'motivo_rechazo_solicitud_actual': motivo_rechazo_solicitud_actual,
        'detalle_rechazo_solicitud_actual': detalle_rechazo_solicitud_actual,
        'motivo_rechazo_solicitud_etiqueta': motivo_rechazo_solicitud_etiqueta,
    }

    context['puede_descargar_pdf_final'] = solicitud_puede_descargar_pdf_final(solicitud)
    context['tiene_items_cotizables'] = solicitud_tiene_items_cotizables(solicitud)
    # EXPLICACIÓN: tras PNC (costos en $0) con orden, igual hay que poder abrir
    # el modal para mandar alternativa REAC.
    context['mostrar_enviar_cotizacion_cliente'] = puede_mostrar_enviar_cotizacion_cliente(
        solicitud,
        tiene_items_cotizables=context['tiene_items_cotizables'],
    )
    # EXPLICACIÓN: tras aviso PNC, ocultar botones de aprobar hasta cotización/REAC
    context['permite_aprobar_lineas'] = solicitud_permite_aprobar_lineas(solicitud)
    # EXPLICACIÓN: misma fuente de verdad que notificar_cliente_pnc (métodos modelo)
    context['mostrar_notificar_cliente_pnc'] = solicitud.puede_notificar_cliente_pnc()
    context['mostrar_reenviar_aviso_pnc'] = solicitud.puede_reenviar_aviso_pnc()
    context['mostrar_modal_notificar_cliente_pnc'] = (
        context['mostrar_notificar_cliente_pnc']
        or context['mostrar_reenviar_aviso_pnc']
    )

    return render(request, 'almacen/cotizaciones/detalle_solicitud.html', context)


# ============================================================================
# VISTAS PARA SERVICIOS ADICIONALES (Venta Mostrador en Cotizaciones)
# ============================================================================

@login_required
@permission_required_with_message('almacen.add_lineaservicioadicional')
def agregar_servicio_adicional(request, solicitud_pk):
    """
    Agregar un servicio adicional a una solicitud de cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista permite agregar servicios de Venta Mostrador (limpieza,
    reinstalación de SO, paquetes, etc.) a una cotización existente.
    
    Los servicios adicionales aparecen debajo de las líneas de cotización
    y el cliente puede aprobarlos/rechazarlos por separado.
    
    Cuando el cliente aprueba y se generan las compras, estos servicios
    se crean automáticamente en el VentaMostrador de la orden.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=solicitud_pk)
    
    # Solo se pueden agregar servicios en estados iniciales
    if solicitud.estado not in ['borrador', 'enviada_front', 'enviada_cliente']:
        messages.error(
            request,
            'No se pueden agregar servicios adicionales en este estado de la solicitud.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud_pk)
    
    if request.method == 'POST':
        form = LineaServicioAdicionalForm(request.POST)
        
        if form.is_valid():
            servicio = form.save(commit=False)
            servicio.solicitud = solicitud
            servicio.save()
            
            messages.success(
                request,
                f'Servicio "{servicio.get_tipo_servicio_display()}" agregado a la cotización.'
            )
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        # GET: redirigir al detalle
        pass
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud_pk)


@login_required
@permission_required_with_message('almacen.delete_lineaservicioadicional')
def eliminar_servicio_adicional(request, solicitud_pk, servicio_pk):
    """
    Eliminar un servicio adicional de una solicitud de cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Elimina un servicio adicional que fue agregado por error o que el
    cliente ya no quiere. Solo se puede eliminar si aún no ha sido
    aprobado/rechazado por el cliente.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=solicitud_pk)
    servicio = get_object_or_404(
        LineaServicioAdicional,
        pk=servicio_pk,
        solicitud=solicitud
    )
    
    # Solo se pueden eliminar servicios pendientes
    if servicio.estado_cliente != 'pendiente':
        messages.error(
            request,
            'No se puede eliminar un servicio que ya fue respondido por el cliente.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud_pk)
    
    if request.method == 'POST':
        nombre_servicio = servicio.get_tipo_servicio_display()
        servicio.delete()
        messages.success(
            request,
            f'Servicio "{nombre_servicio}" eliminado de la cotización.'
        )
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud_pk)


@login_required
@permission_required_with_message('almacen.change_lineaservicioadicional')
def responder_servicio_adicional(request, solicitud_pk, servicio_pk):
    """
    Registrar la respuesta del cliente para un servicio adicional.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Similar a responder_linea_cotizacion, pero para servicios adicionales.
    Permite registrar si el cliente aprobó o rechazó el servicio.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=solicitud_pk)
    servicio = get_object_or_404(
        LineaServicioAdicional,
        pk=servicio_pk,
        solicitud=solicitud
    )
    
    # Solo se puede responder si la solicitud está enviada
    if solicitud.estado not in ['enviada_cliente', 'parcialmente_aprobada']:
        messages.error(
            request,
            'Solo se pueden registrar respuestas en solicitudes enviadas al cliente.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud_pk)
    
    if request.method == 'POST':
        decision = request.POST.get('decision', '')
        motivo = request.POST.get('motivo_rechazo', '')

        # Tras PNC sin cotización/REAC: se puede rechazar, no aprobar
        if decision == 'aprobar':
            from almacen.utils.cotizacion_items_cliente import (
                solicitud_permite_aprobar_lineas,
            )
            if not solicitud_permite_aprobar_lineas(solicitud):
                messages.error(
                    request,
                    'Tras el aviso PNC al cliente, primero envía una '
                    'cotización o propuesta reacondicionado (REAC) antes '
                    'de aprobar servicios.',
                )
                return redirect(
                    'almacen:detalle_solicitud_cotizacion',
                    pk=solicitud_pk,
                )
        
        if decision == 'aprobar':
            if servicio.aprobar():
                messages.success(
                    request,
                    f'Servicio "{servicio.get_tipo_servicio_display()}" aprobado por el cliente.'
                )
            else:
                messages.error(request, 'No se pudo aprobar el servicio.')
        elif decision == 'rechazar':
            if servicio.rechazar(motivo=motivo):
                messages.warning(
                    request,
                    f'Servicio "{servicio.get_tipo_servicio_display()}" rechazado por el cliente.'
                )
            else:
                messages.error(request, 'No se pudo rechazar el servicio.')
        else:
            messages.error(request, 'Decisión no válida.')
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud_pk)


@login_required
@permission_required_with_message('almacen.change_lineaservicioadicional')
def aprobar_todos_servicios(request, pk):
    """
    Aprobar todos los servicios adicionales pendientes de una solicitud.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Atajo para cuando el cliente aprueba todos los servicios adicionales.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if request.method == 'POST':
        from almacen.utils.cotizacion_items_cliente import (
            solicitud_permite_aprobar_lineas,
        )
        if not solicitud_permite_aprobar_lineas(solicitud):
            messages.error(
                request,
                'Tras el aviso PNC al cliente, primero envía una cotización '
                'o propuesta reacondicionado (REAC) antes de aprobar servicios.',
            )
            return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

        servicios_pendientes = solicitud.servicios_adicionales.filter(estado_cliente='pendiente')
        aprobados = 0
        
        for servicio in servicios_pendientes:
            if servicio.aprobar():
                aprobados += 1
        
        if aprobados > 0:
            messages.success(
                request,
                f'Se aprobaron {aprobados} servicio(s) adicional(es).'
            )
        else:
            messages.info(request, 'No había servicios pendientes por aprobar.')
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
@permission_required_with_message('almacen.change_lineaservicioadicional')
def rechazar_todos_servicios(request, pk):
    """
    Rechazar todos los servicios adicionales pendientes de una solicitud.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if request.method == 'POST':
        motivo = request.POST.get('motivo', 'Rechazado por el cliente')
        servicios_pendientes = solicitud.servicios_adicionales.filter(estado_cliente='pendiente')
        rechazados = 0
        
        for servicio in servicios_pendientes:
            if servicio.rechazar(motivo=motivo):
                rechazados += 1
        
        if rechazados > 0:
            messages.warning(
                request,
                f'Se rechazaron {rechazados} servicio(s) adicional(es).'
            )
        else:
            messages.info(request, 'No había servicios pendientes por rechazar.')
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
@permission_required_with_message('almacen.change_solicitudcotizacion')
def cancelar_solicitud_cotizacion(request, pk):
    """
    Cancelar una solicitud de cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cancela la solicitud completa. Solo se puede cancelar si no está
    completada (es decir, si aún no se generaron todas las compras).
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if request.method == 'POST':
        motivo = request.POST.get('motivo', '')
        
        if solicitud.cancelar(motivo=motivo):
            messages.success(
                request,
                f'Solicitud {solicitud.numero_solicitud} cancelada.'
            )
        else:
            messages.error(
                request,
                'No se puede cancelar esta solicitud (ya está completada o cancelada).'
            )
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
@permission_required_with_message('almacen.delete_solicitudcotizacion')
def eliminar_solicitud_cotizacion(request, pk):
    """
    Eliminar una solicitud de cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Elimina permanentemente la solicitud y todas sus líneas.
    Solo se puede eliminar si está en estado 'borrador' o 'cancelada'.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if solicitud.estado not in ['borrador', 'cancelada']:
        messages.error(
            request,
            'Solo se pueden eliminar solicitudes en estado borrador o canceladas.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
    
    if request.method == 'POST':
        numero = solicitud.numero_solicitud
        solicitud.delete()
        messages.success(request, f'Solicitud {numero} eliminada.')
        return redirect('almacen:lista_solicitudes_cotizacion')
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


# ============================================================================
# GESTIÓN DE IMÁGENES DE LÍNEAS DE COTIZACIÓN
# ============================================================================

@login_required
@permission_required_with_message('almacen.change_lineacotizacion')
def gestionar_imagenes_linea(request, solicitud_pk, linea_pk):
    """
    Gestionar imágenes de referencia de una línea de cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista permite ver, subir y eliminar imágenes de referencia
    para una línea específica de cotización.
    
    ¿Por qué es útil?
    - El proveedor ve exactamente qué pieza se necesita
    - El cliente puede verificar las especificaciones
    - Queda evidencia visual para trazabilidad
    
    Restricciones:
    - Solo se pueden gestionar imágenes si la solicitud está en estado 'borrador'
    - Máximo 5 imágenes por línea
    - Las imágenes mayores a 2MB se comprimen automáticamente
    
    Args:
        request: Solicitud HTTP
        solicitud_pk: ID de la SolicitudCotizacion
        linea_pk: ID de la LineaCotizacion
    
    Returns:
        Renderizado del template con el formulario y las imágenes actuales
    """
    # Obtener la solicitud y validar acceso
    solicitud = get_object_or_404(
        SolicitudCotizacion.objects.select_related('orden_servicio'),
        pk=solicitud_pk
    )
    
    # Obtener la línea y validar que pertenece a la solicitud
    linea = get_object_or_404(
        LineaCotizacion.objects.select_related('producto', 'proveedor'),
        pk=linea_pk,
        solicitud=solicitud
    )
    
    # Solo se pueden gestionar imágenes en estado borrador
    puede_editar = solicitud.estado == 'borrador'
    
    # Obtener imágenes existentes
    imagenes = linea.imagenes.all().order_by('fecha_subida')
    
    # Calcular información de límites
    imagenes_restantes = ImagenLineaCotizacion.imagenes_restantes(linea)
    puede_agregar = imagenes_restantes > 0 and puede_editar
    
    # Procesar formulario de subida
    if request.method == 'POST' and puede_agregar:
        form = ImagenLineaCotizacionForm(
            request.POST,
            request.FILES,
            linea=linea
        )
        
        if form.is_valid():
            try:
                # Guardar la imagen asociándola a la línea y al usuario
                imagen = form.save(commit=False)
                imagen.linea = linea
                imagen.subido_por = request.user
                imagen.save()
                
                messages.success(
                    request,
                    f'Imagen subida exitosamente. '
                    f'Quedan {ImagenLineaCotizacion.imagenes_restantes(linea)} espacios disponibles.'
                )
                
                # Redirigir para evitar reenvío del formulario
                return redirect(
                    'almacen:gestionar_imagenes_linea',
                    solicitud_pk=solicitud_pk,
                    linea_pk=linea_pk
                )
                
            except ValueError as e:
                messages.error(request, str(e))
        else:
            # Mostrar errores de validación
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = ImagenLineaCotizacionForm(linea=linea) if puede_agregar else None
    
    context = {
        'solicitud': solicitud,
        'linea': linea,
        'imagenes': imagenes,
        'form': form,
        'puede_editar': puede_editar,
        'puede_agregar': puede_agregar,
        'imagenes_restantes': imagenes_restantes,
        'max_imagenes': ImagenLineaCotizacion.MAX_IMAGENES_POR_LINEA,
        'titulo': f'Imágenes - Línea #{linea.numero_linea}',
    }
    
    return render(request, 'almacen/cotizaciones/gestionar_imagenes_linea.html', context)


@login_required
@permission_required_with_message('almacen.change_lineacotizacion')
def eliminar_imagen_linea(request, solicitud_pk, linea_pk, imagen_pk):
    """
    Eliminar una imagen de una línea de cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista elimina una imagen específica de una línea de cotización.
    
    Validaciones:
    - La imagen debe pertenecer a la línea indicada
    - La solicitud debe estar en estado 'borrador'
    - Solo se procesa si es una solicitud POST (para evitar eliminaciones accidentales)
    
    Args:
        request: Solicitud HTTP
        solicitud_pk: ID de la SolicitudCotizacion
        linea_pk: ID de la LineaCotizacion
        imagen_pk: ID de la ImagenLineaCotizacion a eliminar
    
    Returns:
        Redirección a la vista de gestión de imágenes
    """
    # Validar la cadena completa: solicitud → línea → imagen
    solicitud = get_object_or_404(SolicitudCotizacion, pk=solicitud_pk)
    linea = get_object_or_404(LineaCotizacion, pk=linea_pk, solicitud=solicitud)
    imagen = get_object_or_404(ImagenLineaCotizacion, pk=imagen_pk, linea=linea)
    
    # Solo se pueden eliminar imágenes en estado borrador
    if solicitud.estado != 'borrador':
        messages.error(
            request,
            'Solo se pueden eliminar imágenes cuando la solicitud está en borrador.'
        )
        return redirect(
            'almacen:detalle_solicitud_cotizacion',
            pk=solicitud_pk
        )
    
    # Solo procesar eliminación con método POST
    if request.method == 'POST':
        nombre_archivo = imagen.nombre_archivo
        imagen.delete()
        messages.success(
            request,
            f'Imagen "{nombre_archivo}" eliminada correctamente.'
        )
    
    return redirect(
        'almacen:detalle_solicitud_cotizacion',
        pk=solicitud_pk
    )


@login_required
@permission_required_with_message('almacen.view_lineacotizacion')
def api_imagenes_linea(request, linea_pk):
    """
    API para obtener las imágenes de una línea en formato JSON.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista retorna las imágenes de una línea en formato JSON,
    útil para actualizar la interfaz con JavaScript sin recargar la página.
    
    La respuesta incluye:
    - Lista de imágenes con su URL, descripción y metadata
    - Información sobre cuántas imágenes más se pueden subir
    - Si se puede agregar más imágenes
    
    Args:
        request: Solicitud HTTP
        linea_pk: ID de la LineaCotizacion
    
    Returns:
        JsonResponse con la información de las imágenes
    """
    linea = get_object_or_404(
        LineaCotizacion.objects.select_related('solicitud'),
        pk=linea_pk
    )
    
    imagenes = linea.imagenes.all().order_by('fecha_subida')
    
    imagenes_data = []
    for img in imagenes:
        imagenes_data.append({
            'id': img.pk,
            'url': img.imagen.url,
            'nombre': img.nombre_archivo,
            'descripcion': img.descripcion or '',
            'fecha_subida': img.fecha_subida.strftime('%d/%m/%Y %H:%M'),
            'fue_comprimida': img.fue_comprimida,
            'tamano_kb': img.tamano_final_kb,
        })
    
    return JsonResponse({
        'success': True,
        'imagenes': imagenes_data,
        'total_imagenes': len(imagenes_data),
        'imagenes_restantes': ImagenLineaCotizacion.imagenes_restantes(linea),
        'puede_agregar': ImagenLineaCotizacion.puede_agregar_imagen(linea),
        'max_imagenes': ImagenLineaCotizacion.MAX_IMAGENES_POR_LINEA,
        'puede_editar': linea.solicitud.estado == 'borrador',
    })

