"""
Armado del context GET de detalle_orden (Fase C).

EXPLICACIÓN PARA PRINCIPIANTES:
La vista ya no construye el dict enorme inline. Esta función concentra
formularios, historial, multimedia, cotización, VM y flags de UI.

Efectos secundarios:
- Consultas ORM (querysets al template).
- session.pop de feedback_pendiente_* / vigencia / satisfacción.
"""

import json

from django.conf import settings
from django.db.models import Q
from django.utils.safestring import mark_safe

from inventario.models import Empleado
from scorecard.models import ComponenteEquipo
from config.constants import COMPONENTES_DIAGNOSTICO_ORDEN

from servicio_tecnico.forms import (
    AsignarResponsablesForm,
    CambioEstadoForm,
    ComentarioForm,
    ConfiguracionAdicionalForm,
    EditarInformacionEquipoForm,
    GuardarManoObraForm,
    GestionarCotizacionForm,
    ReingresoRHITSOForm,
    SubirImagenesForm,
    SubirVideoForm,
)
from servicio_tecnico.services.formato_garantia import orden_es_candidata_formato_garantia
from servicio_tecnico.services.formato_oow import orden_es_candidata_formato_oow


def build_detalle_orden_context(request, orden):
    """
    Construye el context del template detalle_orden.html.

    Args:
        request: HttpRequest (user + session.pop de feedback).
        orden: OrdenServicio con select_related/prefetch aplicados.

    Returns:
        dict con las claves que esperan el orquestador y los partials.
    """
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
    # EXPLICACIÓN: en services/ NO usar from .forms (sería services.forms).
    from servicio_tecnico.forms import PiezaCotizadaForm, SeguimientoPiezaForm
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

    # Botón "Notificar equipo disponible": solo en Finalizado / Listo para Entrega
    equipo_disponible_ya_notificado = (
        orden.fecha_notificacion_equipo_disponible is not None
    )
    email_cliente_valido_notificar = bool(
        orden.detalle_equipo
        and orden.detalle_equipo.email_cliente
        and orden.detalle_equipo.email_cliente != 'cliente@ejemplo.com'
    )

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

    # Técnicos activos por rol (mismo criterio que AsignarResponsablesForm).
    # EXPLICACIÓN: las alertas de carga deben coincidir con quien sale en el select.
    tecnicos_laboratorio = Empleado.objects.filter(
        activo=True,
        rol=AsignarResponsablesForm.ROL_TECNICO_ASIGNADO,
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

    from servicio_tecnico.forms import VentaMostradorForm, PiezaVentaMostradorForm

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
        # Botones de formato digital en el encabezado
        'mostrar_formato_oow': orden_es_candidata_formato_oow(orden),
        'mostrar_formato_garantia': orden_es_candidata_formato_garantia(orden),

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
        'equipo_disponible_ya_notificado': equipo_disponible_ya_notificado,
        'email_cliente_valido_notificar': email_cliente_valido_notificar,

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
        # Formato: "[Proveedor] nombre_modelo" — ej: "[Gemini] gemini-3.6-flash"
        'ollama_models': getattr(settings, 'AI_MODELS', []),
    }
    return context
