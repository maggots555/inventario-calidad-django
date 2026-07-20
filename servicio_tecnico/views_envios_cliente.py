"""
Vistas de envíos al cliente (Fase 7 modularización).

EXPLICACIÓN PARA PRINCIPIANTES:
Confirmaciones de feedback/vigencia, imágenes ingreso/egreso, rewind,
evidencia video, diagnóstico PDF y destinatarios.
urls.py sigue usando views.<nombre> porque views.py reexporta estos símbolos.
Las tareas Celery reales viven en tasks.py; aquí solo se validan y se encolan.
"""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_http_methods

from .decorators import permission_required_with_message
from .models import HistorialOrden, ImagenOrden, OrdenServicio, VideoOrden


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


