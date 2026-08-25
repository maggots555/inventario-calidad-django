"""
Handlers POST de detalle_orden: subir imágenes y videos (Fase C).

EXPLICACIÓN PARA PRINCIPIANTES:
Incluyen Celery con db_alias y compresión. En tests, mockear .delay() / IO.
"""

import logging
import os

from django.conf import settings
from django.http import JsonResponse

from config.constants import ESTADO_ORDEN_CHOICES

from .forms import SubirImagenesForm, SubirVideoForm
from .models import HistorialOrden
from .services.multimedia import comprimir_y_guardar_imagen

# EXPLICACIÓN PARA PRINCIPIANTES:
# Al sacar este handler de views_detalle_orden.py, los nombres que antes
# venían del import global del monolito DEBEN declararse aquí. Si falta
# HistorialOrden / ESTADO_ORDEN_CHOICES / settings, subes fotos y revienta
# con NameError (el front muestra "Error inesperado al procesar imágenes").

logger = logging.getLogger(__name__)


def handle_subir_imagenes(request, orden, empleado_actual):
    """
    Handler POST form_type in ('subir_imagenes').

    Args:
        request: HttpRequest Django.
        orden: OrdenServicio ya cargada.
        empleado_actual: Empleado del usuario o None.

    Returns:
        HttpResponse si el flujo terminó (redirect/JSON); None para
        continuar al render GET (form inválido con messages).
    """
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

                    # ============================================================
                    # FECHA INICIO DIAGNÓSTICO (solo órdenes normales, no VM)
                    # ============================================================
                    # EXPLICACIÓN PARA PRINCIPIANTES:
                    # Al subir fotos de ingreso el técnico ya está arrancando el
                    # diagnóstico. Si "Inicio Diagnóstico" está vacío, lo llenamos
                    # con la fecha de hoy. NO tocamos fecha_fin_diagnostico: esa
                    # marca el fin y dispara "Equipo Diagnosticado".
                    # Tampoco sobrescribimos una fecha ya capturada a mano.
                    if orden.tipo_servicio != 'venta_mostrador':
                        from django.utils import timezone as tz_fecha

                        detalle_equipo = orden.detalle_equipo
                        if detalle_equipo.fecha_inicio_diagnostico is None:
                            # Paso 1: fecha local del servidor (no UTC crudo)
                            fecha_hoy = tz_fecha.localdate()
                            # Paso 2: guardar solo ese campo (no reescribe el resto)
                            detalle_equipo.fecha_inicio_diagnostico = fecha_hoy
                            detalle_equipo.save(
                                update_fields=['fecha_inicio_diagnostico']
                            )
                            HistorialOrden.objects.create(
                                orden=orden,
                                tipo_evento='sistema',
                                comentario=(
                                    'Inicio de diagnóstico registrado automáticamente '
                                    f'({fecha_hoy.strftime("%d/%m/%Y")}) al subir '
                                    'imágenes de ingreso'
                                ),
                                usuario=empleado_actual,
                                es_sistema=True,
                            )
                            # Paso 3: aviso en el mensaje JSON al frontend
                            if mensaje_estado:
                                mensaje_estado += (
                                    f'; Inicio Diagnóstico: {fecha_hoy.strftime('%d/%m/%Y')}'
                                )
                            else:
                                mensaje_estado = (
                                    'Inicio Diagnóstico registrado: '
                                    f'{fecha_hoy.strftime("%d/%m/%Y")}'
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

                # Aviso a recepción: fotos de egreso (anti-dup con finalizado).
                # EXPLICACIÓN: Si el save() anterior ya pasó a finalizado, el
                # signal pudo haber avisado; el flag evita el duplicado.
                # Si la orden YA estaba finalizada, solo este disparo avisa.
                if tipo_imagen == 'egreso':
                    from servicio_tecnico.services.notificaciones_recepcion import (
                        notificar_recepcion_equipo_listo,
                    )
                    notificar_recepcion_equipo_listo(orden, motivo='egreso')

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


def handle_subir_video(request, orden, empleado_actual):
    """
    Handler POST form_type in ('subir_video').

    Args:
        request: HttpRequest Django.
        orden: OrdenServicio ya cargada.
        empleado_actual: Empleado del usuario o None.

    Returns:
        HttpResponse si el flujo terminó (redirect/JSON); None para
        continuar al render GET (form inválido con messages).
    """
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
    # EXPLICACIÓN: sin perfil Empleado no hay PK para la tarea; evitar AttributeError.
    if empleado_actual is None:
        try:
            os.remove(archivo_tmp_path)
        except OSError:
            pass
        return JsonResponse({
            'success': False,
            'error': 'Tu usuario no tiene perfil de empleado asociado. No se puede subir el video.',
        }, status=403)

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

