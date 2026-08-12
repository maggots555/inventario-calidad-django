"""
Envío de cotización al cliente, PDFs, respuestas de líneas y motivos de rechazo.

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
Extraído de views.py (Fase 4 de modularización Almacén).
Cuando Front/Compras envía la cotización al cliente o registra
aprobaciones/rechazos, la lógica vive aquí.

urls.py sigue usando views.api_enviar_cotizacion_cliente, etc.
porque views.py reexporta estos nombres.

Efectos secundarios:
- Dispara tareas Celery de email/PDF (enviar_cotizacion_cliente_task)
- Cambia estados de SolicitudCotizacion y sync con ST
- Genera PDF (preview/descarga) vía utils PDF
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_http_methods

from .decorators import permission_required_with_message
from .forms import RespuestaLineaCotizacionForm
from .models import LineaCotizacion, SolicitudCotizacion
from .utils.cotizacion_reacondicionado_helpers import (
    _actualizar_estado_st_esperando_aprobacion_cliente,
    _crear_o_actualizar_linea_reacondicionado,
    _extraer_datos_reacondicionado_post,
    _guardar_snapshot_reacondicionado,
    _validar_y_calcular_reacondicionado,
)

import logging

logger = logging.getLogger('almacen')


@login_required
@permission_required_with_message('almacen.change_solicitudcotizacion')
def enviar_solicitud_cliente(request, pk):
    """
    Cambiar estado de la solicitud a 'enviada_front'.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta acción marca la solicitud como lista para que Recepción la revise.
    Recepción podrá entonces enviarla al cliente y registrar las respuestas.
    
    Requisitos:
    - Estado debe ser 'borrador'
    - Debe tener al menos una línea
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if request.method == 'POST':
        if solicitud.enviar_a_front():
            messages.success(
                request,
                f'Solicitud {solicitud.numero_solicitud} enviada a Front. '
                'Recepción puede ahora revisarla y compartirla con el cliente.'
            )
        else:
            messages.error(
                request,
                'No se puede enviar la solicitud. Verifica que esté en estado '
                'borrador y tenga al menos una línea.'
            )
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
@permission_required_with_message('almacen.change_solicitudcotizacion')
def enviar_solicitud_a_cliente(request, pk):
    """
    Cambiar estado de la solicitud de 'enviada_front' a 'enviada_cliente'.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta acción la realiza Recepción (Front) cuando ya compartió la cotización
    con el cliente final. A partir de este momento:
    - El cliente puede aprobar o rechazar cada línea
    - Ya no se pueden editar líneas ni reenviar notificaciones
    - Aparecen los botones de aprobar/rechazar en el detalle
    
    Requisitos:
    - Estado debe ser 'enviada_front'
    - Debe tener al menos una línea
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if request.method == 'POST':
        if solicitud.enviar_a_cliente():
            messages.success(
                request,
                f'Solicitud {solicitud.numero_solicitud} enviada al cliente. '
                'Ahora se pueden registrar las respuestas de aprobación/rechazo.'
            )
        else:
            messages.error(
                request,
                'No se puede enviar al cliente. Verifica que la solicitud esté '
                'en estado "Enviada a Front" y tenga al menos una línea.'
            )
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


# =============================================================================
# NUEVAS VISTAS: ENVÍO DE COTIZACIÓN DIRECTAMENTE AL CLIENTE FINAL
# =============================================================================

@login_required
@permission_required_with_message('almacen.change_solicitudcotizacion')
@require_http_methods(["POST"])
def api_enviar_cotizacion_cliente(request, pk):
    """
    Envía la cotización directamente al cliente final por correo con PDF adjunto.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista es el corazón del nuevo modal "Enviar Cotización al Cliente".
    Recibe los parámetros del modal (tipo de servicio, modo de agrupación,
    email del cliente, etc.), genera los PDF necesarios y los envía al cliente.

    Flujo:
    1. Valida los datos del POST (tipo_servicio, email_cliente, modo_agrupacion)
    2. Cambia el estado de la solicitud a 'enviada_cliente'
    3. Agrupa los ítems según el modo elegido (todo junto / piezas vs servicios / etc.)
    4. Para cada grupo, dispara una tarea Celery que genera el PDF y lo envía por email
    5. Si hay orden de ST vinculada, cambia su estado a 'cotizacion'
       («Esperando Aprobación Cliente») — este es el momento real de espera al cliente
    6. Retorna JsonResponse inmediato (el email se procesa en background)

    Args:
        request: HttpRequest POST con los datos del modal.
        pk     : ID de la SolicitudCotizacion.

    Returns:
        JsonResponse con {'success': bool, 'mensaje': str}
    """
    import json as _json
    from .tasks import enviar_cotizacion_cliente_task
    from config.paises_config import get_pais_actual

    try:
        solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)

        # --- 1. VALIDACIÓN DE ESTADO ---
        # La solicitud debe estar en un estado que permita el envío al cliente
        estados_validos = ['enviada_front', 'enviada_cliente', 'parcialmente_aprobada']
        if solicitud.estado not in estados_validos:
            return JsonResponse({
                'success': False,
                'error': f'Estado "{solicitud.get_estado_display()}" no permite envío al cliente. '
                         f'La solicitud debe estar en estado "Enviada a Front", "Enviada al Cliente" '
                         f'o "Parcialmente Aprobada".'
            })

        # --- 2. EXTRAER PARÁMETROS DEL POST ---
        modo_cotizacion = request.POST.get('modo_cotizacion', 'reparacion')
        tipo_servicio  = request.POST.get('tipo_servicio', 'estandar')
        email_cliente  = request.POST.get('email_cliente', '').strip()
        modo_agrupacion = request.POST.get('modo_agrupacion', 'todo_junto')
        mensaje_personalizado = request.POST.get('mensaje_personalizado', '').strip()
        # El descuento de diagnóstico ya no aplica: reparación se abona completa.
        incluir_descuento = False

        # Asunto personalizado del correo.
        # Si el usuario lo dejó vacío o con el prefijo por defecto sin texto adicional,
        # la tarea lo generará automáticamente con el perfil y folio.
        asunto_correo = request.POST.get('asunto_correo', '').strip()
        # Normalizar: si solo enviaron el prefijo vacío, tratar como sin asunto personalizado
        from .utils.cotizacion_email_context import es_asunto_correo_vacio
        if es_asunto_correo_vacio(asunto_correo):
            asunto_correo = ''

        # Mano de obra override — el campo es informativo, se envía como 0 desde el frontend.
        # Se mantiene la lectura por compatibilidad con llamadas directas a la API.
        mano_obra_raw = request.POST.get('mano_de_obra_override', '')
        mano_de_obra_override = None
        if mano_obra_raw:
            try:
                val = float(mano_obra_raw)
                mano_de_obra_override = val if val > 0 else None
            except ValueError:
                pass

        # Emails con copia (CC) — pueden venir múltiples campos con el mismo nombre
        copia_empleados = request.POST.getlist('copia_empleados')

        # --- 3. VALIDAR EMAIL DEL CLIENTE ---
        if not email_cliente:
            return JsonResponse({'success': False, 'error': 'El email del cliente es requerido.'})

        # Validación simple de formato email
        import re as _re
        if not _re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email_cliente):
            return JsonResponse({'success': False, 'error': f'El email "{email_cliente}" no tiene formato válido.'})

        # --- 4a. MODO REACONDICIONADO (propuesta de equipo certificado) ---
        if modo_cotizacion == 'reacondicionado':
            datos_post = _extraer_datos_reacondicionado_post(request.POST)
            ok, resultado = _validar_y_calcular_reacondicionado(datos_post)
            if not ok:
                return JsonResponse({'success': False, 'error': resultado})

            if solicitud.estado == 'enviada_front':
                solicitud.enviar_a_cliente()

            _guardar_snapshot_reacondicionado(
                solicitud,
                resultado['datos_equipo'],
                resultado['costeo'],
                resultado['dias_front_desk'],
                resultado['costo_proveedor'],
            )

            ok_linea, error_linea = _crear_o_actualizar_linea_reacondicionado(
                solicitud,
                resultado['datos_equipo'],
                resultado['costeo'],
                resultado['costo_proveedor'],
            )
            if not ok_linea:
                return JsonResponse({'success': False, 'error': error_linea})

            _db = get_pais_actual()['db_alias']
            enviar_cotizacion_cliente_task.delay(
                solicitud_id=solicitud.pk,
                email_cliente=email_cliente,
                copia_empleados=copia_empleados,
                tipo_servicio='reacondicionado',
                items=[],
                titulo_propuesta='Propuesta de Equipo Reacondicionado — Certificado SIC',
                incluir_descuento_diagnostico=False,
                mano_de_obra_override=None,
                mensaje_personalizado=mensaje_personalizado,
                asunto_correo=asunto_correo,
                usuario_id=request.user.pk,
                db_alias=_db,
                modo_cotizacion='reacondicionado',
                datos_equipo_reac=resultado['datos_equipo'],
                costeo_reac=resultado['costeo'],
            )
            # Al enviar al cliente: ST pasa a «Esperando Aprobación Cliente»
            _actualizar_estado_st_esperando_aprobacion_cliente(solicitud, usuario=request.user)
            return JsonResponse({
                'success': True,
                'mensaje': (
                    f'Propuesta de equipo reacondicionado enviada a {email_cliente}. '
                    'El correo se procesa en segundo plano.'
                ),
                'grupos_enviados': 1,
            })

        # --- 4. VALIDAR TIPO DE SERVICIO (modo reparación) ---
        from .utils.parametros_cotizador import obtener_profit_config
        from .utils.profit_por_pieza import (
            aplicar_profit_overrides_a_items,
            parsear_profit_overrides,
            persistir_profit_aplicado_lineas,
            validar_profit_overrides_contra_lineas,
        )
        tipos_validos = list(obtener_profit_config().keys())
        if tipo_servicio not in tipos_validos:
            return JsonResponse({'success': False, 'error': f'Tipo de servicio "{tipo_servicio}" no válido.'})

        # Profit personalizado por pieza (JSON {linea_id: 0.36})
        try:
            profit_overrides = parsear_profit_overrides(
                request.POST.get('profit_por_pieza', '')
            )
        except ValueError as exc:
            return JsonResponse({'success': False, 'error': str(exc)})

        # --- 5. CAMBIAR ESTADO A 'enviada_cliente' (si aún no lo está) ---
        if solicitud.estado == 'enviada_front':
            # Avanzar el estado usando el método del modelo
            solicitud.enviar_a_cliente()

        # Snapshot del perfil de profit (los precios se congelan en la primera
        # respuesta del cliente: aprobar o rechazar)
        if not solicitud.fecha_precios_cliente:
            solicitud.tipo_servicio_cliente = tipo_servicio
            # Siempre False: ya no se descuenta diagnóstico en reparación
            solicitud.incluir_descuento_diagnostico_cliente = False
            solicitud.save(update_fields=[
                'tipo_servicio_cliente',
                'incluir_descuento_diagnostico_cliente',
            ])

        # --- 6. CONSTRUIR GRUPOS DE ÍTEMS (solo pendiente + aprobada; excluye rechazadas) ---
        from .utils.cotizacion_items_cliente import (
            construir_grupos_cotizacion,
            obtener_lineas_cotizables,
            obtener_servicios_cotizables,
            serializar_linea_cotizacion,
            serializar_servicio_cotizacion,
            solicitud_tiene_items_cotizables,
        )

        if not solicitud_tiene_items_cotizables(solicitud):
            return JsonResponse({
                'success': False,
                'error': (
                    'No hay piezas ni servicios pendientes o aprobados para cotizar. '
                    'Las líneas rechazadas no se incluyen.'
                ),
            })

        lineas_cotizables = list(obtener_lineas_cotizables(solicitud))
        # Validar mínimos del tipo elegido (Mostrador ≠ Estándar, etc.)
        ok_profit, error_profit = validar_profit_overrides_contra_lineas(
            lineas_cotizables,
            profit_overrides,
            perfil=tipo_servicio,
        )
        if not ok_profit:
            return JsonResponse({'success': False, 'error': error_profit})

        # Persistir % efectivo por pieza ANTES de armar el PDF (Celery lo lee)
        if not solicitud.fecha_precios_cliente:
            profit_perfil = obtener_profit_config()[tipo_servicio]['profit_target']
            persistir_profit_aplicado_lineas(
                lineas_cotizables,
                profit_perfil,
                overrides=profit_overrides,
                perfil=tipo_servicio,
            )
            # Releer líneas para que serializar vea profit_aplicado fresco
            lineas_cotizables = list(obtener_lineas_cotizables(solicitud))

        items_piezas_todos = [
            serializar_linea_cotizacion(l) for l in lineas_cotizables
        ]
        # Si aún hay overrides en el request, asegurar que el motor los use
        items_piezas_todos = aplicar_profit_overrides_a_items(
            items_piezas_todos,
            profit_overrides,
        )
        items_servicios = [
            serializar_servicio_cotizacion(s) for s in obtener_servicios_cotizables(solicitud)
        ]
        grupos = construir_grupos_cotizacion(
            items_piezas_todos, items_servicios, modo_agrupacion
        )

        if not grupos:
            return JsonResponse({
                'success': False,
                'error': (
                    'No hay piezas ni servicios pendientes o aprobados para cotizar. '
                    'Las líneas rechazadas no se incluyen.'
                ),
            })

        # --- 8. DISPARAR TAREA CELERY PARA CADA GRUPO ---
        _db = get_pais_actual()['db_alias']
        usuario_id = request.user.pk

        for grupo in grupos:
            enviar_cotizacion_cliente_task.delay(
                solicitud_id=solicitud.pk,
                email_cliente=email_cliente,
                copia_empleados=copia_empleados,
                tipo_servicio=tipo_servicio,
                items=grupo['items'],
                titulo_propuesta=grupo['titulo'],
                incluir_descuento_diagnostico=incluir_descuento,
                mano_de_obra_override=mano_de_obra_override,
                mensaje_personalizado=mensaje_personalizado,
                asunto_correo=asunto_correo,
                usuario_id=usuario_id,
                db_alias=_db,
            )

        # Al enviar al cliente: orden ST → «Esperando Aprobación Cliente»
        # (si hay orden vinculada y aún no estaba en ese estado)
        _actualizar_estado_st_esperando_aprobacion_cliente(solicitud, usuario=request.user)

        # Mensaje de éxito según cuántos grupos se enviaron
        n_grupos = len(grupos)
        if n_grupos == 1:
            mensaje = f'Cotización enviada al cliente {email_cliente}. El correo se procesa en segundo plano.'
        else:
            mensaje = (
                f'{n_grupos} cotizaciones separadas enviadas a {email_cliente}. '
                f'Los correos se procesan en segundo plano.'
            )

        return JsonResponse({'success': True, 'mensaje': mensaje, 'grupos_enviados': n_grupos})

    except Exception as e:
        import traceback as _tb
        logger.error(f"[API_COTIZACION_CLIENTE] Error: {e}\n{_tb.format_exc()}")
        return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}'})


@login_required
@permission_required_with_message('almacen.view_solicitudcotizacion')
@require_http_methods(["GET"])
@xframe_options_sameorigin
def preview_pdf_cotizacion(request, pk):
    """
    Genera y devuelve un PDF de previsualización para el modal de envío al cliente.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista es la que llama el botón "Ver Previsualización" del modal.
    Genera el PDF con los parámetros actuales del modal (tipo de servicio,
    modo de agrupación) y lo devuelve directamente como respuesta PDF
    para mostrarlo en el iframe del modal.

    Args:
        request: HttpRequest GET con parámetros:
                 - tipo_servicio: str
                 - modo_agrupacion: str
                 - grupo_idx: int (0=primero, 1=segundo — para modo separado)
        pk     : ID de la SolicitudCotizacion.

    Returns:
        HttpResponse con content_type='application/pdf'
    """
    from django.http import HttpResponse
    from .utils.pdf_cotizacion_cliente import PDFCotizacionCliente
    from config.paises_config import get_pais_actual

    try:
        solicitud = get_object_or_404(
            SolicitudCotizacion.objects.select_related(
                'orden_servicio',
                'orden_servicio__detalle_equipo',
                'orden_servicio__sucursal',
                'creado_por',
                'creado_por__empleado__sucursal',
            ).prefetch_related('lineas__producto', 'servicios_adicionales'),
            pk=pk
        )

        tipo_servicio     = request.GET.get('tipo_servicio', 'estandar')
        modo_cotizacion   = request.GET.get('modo_cotizacion', 'reparacion')
        modo_agrupacion   = request.GET.get('modo_agrupacion', 'todo_junto')
        grupo_idx         = int(request.GET.get('grupo_idx', 0))

        _pais = get_pais_actual()

        # Preview de propuesta reacondicionada (motor distinto al de reparación)
        if modo_cotizacion == 'reacondicionado':
            from .utils.pdf_cotizacion_reacondicionado import PDFCotizacionReacondicionado

            datos_post = {
                'costo_proveedor': request.GET.get('reac_costo_proveedor', ''),
                'dias_front_desk': request.GET.get('reac_dias_front_desk', '1'),
                'marca': request.GET.get('reac_marca', ''),
                'modelo': request.GET.get('reac_modelo', ''),
                'procesador': request.GET.get('reac_procesador', ''),
                'ram': request.GET.get('reac_ram', ''),
                'sistema_operativo': request.GET.get('reac_sistema_operativo', ''),
                'incluye_cargador': request.GET.get('reac_incluye_cargador', '0'),
                'especificaciones': request.GET.get('reac_especificaciones', ''),
            }
            datos_post['incluye_cargador'] = datos_post['incluye_cargador'] == '1'
            ok, resultado = _validar_y_calcular_reacondicionado(datos_post)
            if not ok:
                return HttpResponse(resultado.encode(), content_type='text/plain', status=400)

            generador_reac = PDFCotizacionReacondicionado(
                solicitud=solicitud,
                datos_equipo=resultado['datos_equipo'],
                costeo=resultado['costeo'],
                pais_config=_pais,
            )
            resultado_pdf = generador_reac.generar_pdf()
            if not resultado_pdf['success']:
                return HttpResponse(
                    f'Error al generar PDF: {resultado_pdf.get("error", "desconocido")}'.encode(),
                    content_type='text/plain',
                    status=500,
                )
            pdf_bytes = resultado_pdf['buffer'].getvalue()
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = (
                f'inline; filename="{resultado_pdf["nombre_archivo"]}"'
            )
            return response

        from .utils.cotizacion_items_cliente import (
            construir_grupos_cotizacion,
            obtener_lineas_cotizables,
            obtener_servicios_cotizables,
            serializar_linea_cotizacion,
            serializar_servicio_cotizacion,
        )
        from .utils.profit_por_pieza import (
            aplicar_profit_overrides_a_items,
            parsear_profit_overrides,
            validar_profit_overrides_contra_lineas,
        )

        # Overrides del modal para que el preview coincida con la calculadora
        try:
            profit_overrides = parsear_profit_overrides(
                request.GET.get('profit_por_pieza', '')
            )
        except ValueError as exc:
            return HttpResponse(str(exc).encode(), content_type='text/plain', status=400)

        lineas_cotizables = list(obtener_lineas_cotizables(solicitud))
        # Preview: mismos mínimos que el envío según tipo_servicio del GET
        ok_profit, error_profit = validar_profit_overrides_contra_lineas(
            lineas_cotizables,
            profit_overrides,
            perfil=tipo_servicio,
        )
        if not ok_profit:
            return HttpResponse(
                error_profit.encode(),
                content_type='text/plain',
                status=400,
            )

        items_todos_piezas = [
            serializar_linea_cotizacion(l) for l in lineas_cotizables
        ]
        items_todos_piezas = aplicar_profit_overrides_a_items(
            items_todos_piezas,
            profit_overrides,
        )
        items_servicios = [
            serializar_servicio_cotizacion(s) for s in obtener_servicios_cotizables(solicitud)
        ]
        grupos = construir_grupos_cotizacion(
            items_todos_piezas, items_servicios, modo_agrupacion
        )

        if not grupos:
            return HttpResponse(
                b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n'
                b'2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n'
                b'3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n'
                b'xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n'
                b'0000000058 00000 n \n0000000115 00000 n \n'
                b'trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF',
                content_type='application/pdf'
            )

        # Elegir el grupo según el índice (para modo separado)
        grupo_idx = min(grupo_idx, len(grupos) - 1)
        grupo = grupos[grupo_idx]

        generador = PDFCotizacionCliente(
            solicitud=solicitud,
            tipo_servicio=tipo_servicio,
            items=grupo['items'],
            titulo_propuesta=grupo['titulo'],
            incluir_descuento_diagnostico=False,
            pais_config=_pais,
        )

        resultado = generador.generar_pdf()
        if not resultado['success']:
            return HttpResponse(
                f'Error al generar PDF: {resultado.get("error", "desconocido")}'.encode(),
                content_type='text/plain',
                status=500
            )

        pdf_bytes = resultado['buffer'].getvalue()
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="{resultado["nombre_archivo"]}"'
        )
        return response

    except Exception as e:
        import traceback as _tb
        logger.error(f"[PREVIEW_PDF_COTIZACION] Error: {e}\n{_tb.format_exc()}")
        return HttpResponse(f'Error: {str(e)}'.encode(), content_type='text/plain', status=500)


@login_required
@permission_required_with_message('almacen.view_solicitudcotizacion')
@require_http_methods(["GET"])
def descargar_pdf_cotizacion_final(request, pk):
    """
    Genera y descarga el PDF final con piezas/servicios aceptados y precios persistidos.

    Si solo se aceptó el equipo reacondicionado (línea P0125), genera el PDF de
    propuesta reacondicionada en lugar del PDF de piezas de reparación.

    Args:
        request: HttpRequest GET.
        pk     : ID de la SolicitudCotizacion.

    Returns:
        HttpResponse PDF inline o error en texto plano.
    """
    from django.http import HttpResponse
    from .utils.pdf_cotizacion_cliente import PDFCotizacionCliente
    from .utils.cotizacion_items_cliente import (
        construir_items_cotizacion_final,
        solicitud_puede_descargar_pdf_final,
        solicitud_pdf_final_es_solo_reacondicionado,
        extraer_datos_equipo_desde_solicitud,
    )
    from .utils.cotizacion_precios_cliente import obtener_tipo_servicio_solicitud
    from config.paises_config import get_pais_actual

    try:
        solicitud = get_object_or_404(
            SolicitudCotizacion.objects.select_related(
                'orden_servicio',
                'orden_servicio__detalle_equipo',
            ).prefetch_related('lineas__producto', 'servicios_adicionales'),
            pk=pk,
        )

        if not solicitud_puede_descargar_pdf_final(solicitud):
            return HttpResponse(
                'No hay ítems aceptados con precios guardados para generar el PDF final.'.encode(),
                content_type='text/plain',
                status=400,
            )

        _pais = get_pais_actual()

        # PDF final de equipo reacondicionado (solo línea P0125 aceptada)
        if solicitud_pdf_final_es_solo_reacondicionado(solicitud):
            from .utils.pdf_cotizacion_reacondicionado import PDFCotizacionReacondicionado
            from .utils.cotizacion_items_cliente import obtener_lineas_aceptadas_final

            linea_reac = obtener_lineas_aceptadas_final(solicitud).filter(
                es_linea_reacondicionado=True,
            ).first()

            generador_reac = PDFCotizacionReacondicionado(
                solicitud=solicitud,
                datos_equipo=extraer_datos_equipo_desde_solicitud(solicitud),
                costeo=solicitud.resultado_costeo_reac or {},
                pais_config=_pais,
                opcion_pago_aceptada=linea_reac.opcion_pago_reac if linea_reac else 'contado',
                modo_final=True,
            )
            resultado = generador_reac.generar_pdf()
            if not resultado['success']:
                return HttpResponse(
                    f'Error al generar PDF: {resultado.get("error", "desconocido")}'.encode(),
                    content_type='text/plain',
                    status=500,
                )
            pdf_bytes = resultado['buffer'].getvalue()
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = (
                f'inline; filename="{resultado["nombre_archivo"]}"'
            )
            return response

        items = construir_items_cotizacion_final(solicitud)
        if not items:
            return HttpResponse(
                'No se encontraron líneas aceptadas con precio al cliente.'.encode(),
                content_type='text/plain',
                status=400,
            )

        tipo_servicio = obtener_tipo_servicio_solicitud(solicitud)

        generador = PDFCotizacionCliente(
            solicitud=solicitud,
            tipo_servicio=tipo_servicio,
            items=items,
            incluir_descuento_diagnostico=False,
            pais_config=_pais,
            modo_final=True,
        )

        resultado = generador.generar_pdf()
        if not resultado['success']:
            return HttpResponse(
                f'Error al generar PDF: {resultado.get("error", "desconocido")}'.encode(),
                content_type='text/plain',
                status=500,
            )

        pdf_bytes = resultado['buffer'].getvalue()
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="{resultado["nombre_archivo"]}"'
        )
        return response

    except Exception as e:
        import traceback as _tb
        logger.error(f"[PDF_COTIZACION_FINAL] Error: {e}\n{_tb.format_exc()}")
        return HttpResponse(f'Error: {str(e)}'.encode(), content_type='text/plain', status=500)


@login_required
@permission_required_with_message('almacen.change_solicitudcotizacion')
@require_http_methods(["POST"])
def notificar_front(request, pk):
    """
    Enviar notificación de cotización a recepción (FRONTDESK) por correo.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista reemplaza el antiguo "Enviar a Cliente". En lugar de cambiar
    solo el estado, ahora envía un correo HTML a los empleados de FRONTDESK
    con el detalle de la cotización (piezas, costos, imágenes) para que
    recepción la comparta con el cliente.
    
    Flujo:
    1. Valida que la solicitud esté en borrador o enviada_front y tenga líneas
    2. Lee ``tipo_plantilla`` (cotización lista vs partes no disponibles / PNC)
    3. Cambia el estado de la solicitud a 'enviada_front' (si estaba en borrador)
    4. Sincroniza la orden ST según la plantilla (recibida proveedores o PNC)
    5. Dispara la tarea Celery para enviar el correo en segundo plano
    6. Devuelve JsonResponse inmediato
    
    Args:
        request: HttpRequest con datos POST del formulario
        pk: ID de la SolicitudCotizacion
    
    Returns:
        JsonResponse — el correo se procesa en background via Celery
    """
    from .tasks import notificar_front_cotizacion_task
    from .utils.sincronizar_estado_st import (
        TIPO_PLANTILLA_COTIZACION_LISTA,
        TIPO_PLANTILLA_PARTES_NO_DISPONIBLES,
        TIPOS_PLANTILLA_NOTIFICAR_FRONT,
        sincronizar_estado_st_al_notificar_front,
    )
    
    try:
        solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
        
        # Validar estado: permitir envío inicial (borrador) o reenvío (enviada_front)
        if solicitud.estado not in ['borrador', 'enviada_front']:
            return JsonResponse({
                'success': False,
                'error': 'Solo se puede notificar cuando la solicitud está en borrador o ya enviada a front.'
            }, status=400)
        
        # Validar que tenga al menos una línea
        if not solicitud.lineas.exists():
            return JsonResponse({
                'success': False,
                'error': 'La solicitud debe tener al menos una línea para notificar.'
            }, status=400)

        # EXPLICACIÓN: el modal envía radios; si falta o es inválido, usamos cotización lista
        tipo_plantilla = (
            request.POST.get('tipo_plantilla', TIPO_PLANTILLA_COTIZACION_LISTA) or ''
        ).strip()
        if tipo_plantilla not in TIPOS_PLANTILLA_NOTIFICAR_FRONT:
            return JsonResponse({
                'success': False,
                'error': (
                    'Tipo de plantilla inválido. Elige «Cotización lista» '
                    'o «Partes no disponibles (PNC)».'
                ),
            }, status=400)
        
        # Obtener destinatarios del formulario (los seleccionados en el modal)
        copia_empleados = request.POST.getlist('copia_empleados', [])
        copia_tecnico = request.POST.getlist('copia_tecnico', [])
        
        # Los destinatarios principales son los que el usuario seleccionó
        destinatarios = list(set(copia_empleados + copia_tecnico))
        
        if not destinatarios:
            return JsonResponse({
                'success': False,
                'error': 'Debes seleccionar al menos un destinatario.'
            }, status=400)
        
        mensaje_personalizado = request.POST.get('mensaje_personalizado', '').strip()
        
        # Cambiar estado de la solicitud a 'enviada_front' solo si está en borrador
        if solicitud.estado == 'borrador':
            solicitud.enviar_a_front(usuario=request.user)

        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Guardamos si Front recibió plantilla PNC (fuente única en el modelo).
        # Así el botón y la API usan la misma regla, no solo ocultar en HTML.
        solicitud.actualizar_plantilla_pnc_front(tipo_plantilla)

        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Cotización lista → ST a «cotización recibida». Plantilla PNC a Front
        # NO cambia ST (el PNC en ST lo pone solo el aviso al cliente).
        # También se intenta en reenvíos por si la orden se vinculó después.
        sincronizar_estado_st_al_notificar_front(
            solicitud,
            usuario=request.user,
            tipo_plantilla=tipo_plantilla,
        )
        
        # Disparar tarea Celery
        usuario_id = request.user.pk if request.user.is_authenticated else None
        from config.paises_config import get_pais_actual

        tarea = notificar_front_cotizacion_task.delay(
            solicitud_id=pk,
            destinatarios=destinatarios,
            mensaje_personalizado=mensaje_personalizado,
            usuario_id=usuario_id,
            tipo_plantilla=tipo_plantilla,
            db_alias=get_pais_actual()['db_alias'],
        )

        # Mensaje distinto para que Front sepa si es cotización o PNC
        if tipo_plantilla == TIPO_PLANTILLA_PARTES_NO_DISPONIBLES:
            mensaje_ok = (
                f'Notificación PNC (partes no disponibles) en proceso de envío '
                f'a {len(destinatarios)} destinatario(s).'
            )
        else:
            mensaje_ok = (
                f'Notificación en proceso de envío a {len(destinatarios)} '
                f'destinatario(s).'
            )
        
        return JsonResponse({
            'success': True,
            'message': mensaje_ok,
            'data': {
                'task_id': tarea.id,
                'destinatario': ', '.join(destinatarios),
                'solicitud': solicitud.numero_solicitud,
                'tipo_plantilla': tipo_plantilla,
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'Error al procesar la solicitud: {str(e)}'
        }, status=500)


@login_required
@permission_required_with_message('almacen.change_lineacotizacion')
def responder_linea_cotizacion(request, solicitud_pk, linea_pk):
    """
    Registrar la respuesta del cliente para una línea específica.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta vista permite a Recepción registrar si el cliente aprobó o
    rechazó una línea específica de la cotización.
    
    Si el cliente aprueba: La línea queda marcada para generar compra.
    Si el cliente rechaza: Se debe indicar el motivo.
    
    Después de cada respuesta, se actualiza automáticamente el estado
    general de la solicitud.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=solicitud_pk)
    linea = get_object_or_404(LineaCotizacion, pk=linea_pk, solicitud=solicitud)
    
    # Solo se puede responder si la solicitud está enviada
    if solicitud.estado not in ['enviada_cliente', 'parcialmente_aprobada']:
        messages.error(
            request,
            'Solo se pueden registrar respuestas en solicitudes enviadas al cliente.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud_pk)
    
    if request.method == 'POST':
        form = RespuestaLineaCotizacionForm(request.POST)
        
        if form.is_valid():
            decision = form.cleaned_data['decision']
            motivo = form.cleaned_data.get('motivo_rechazo', '')

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
                        'de aprobar líneas.',
                    )
                    return redirect(
                        'almacen:detalle_solicitud_cotizacion',
                        pk=solicitud_pk,
                    )
            
            if decision == 'aprobar':
                if linea.es_linea_reacondicionado:
                    opcion = form.cleaned_data.get('opcion_pago_reac', '')
                    if not opcion:
                        messages.error(
                            request,
                            'Debes seleccionar la forma de pago del equipo reacondicionado.',
                        )
                        return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud_pk)
                    aprobado = linea.aprobar(opcion_pago_reac=opcion)
                else:
                    aprobado = linea.aprobar()
                if aprobado:
                    messages.success(
                        request,
                        f'Línea #{linea.numero_linea} aprobada por el cliente.'
                    )
                else:
                    if linea.es_linea_reacondicionado:
                        messages.error(
                            request,
                            'No se pudo aprobar el equipo reacondicionado. '
                            'Verifica el costeo guardado y la forma de pago.',
                        )
                    else:
                        messages.error(request, 'No se pudo aprobar la línea.')
            else:  # rechazar
                if linea.rechazar(motivo=motivo):
                    messages.warning(
                        request,
                        f'Línea #{linea.numero_linea} rechazada por el cliente.'
                    )
                    solicitud.refresh_from_db()
                    if solicitud.estado == 'totalmente_rechazada':
                        from almacen.utils.sincronizar_rechazo_cotizacion_st import (
                            mensaje_flash_tras_rechazo_total,
                        )
                        messages.info(
                            request,
                            mensaje_flash_tras_rechazo_total(solicitud),
                        )
                else:
                    messages.error(request, 'No se pudo rechazar la línea.')
        else:
            messages.error(request, 'Por favor corrige los errores.')
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud_pk)


@login_required
@permission_required_with_message('almacen.change_lineacotizacion')
def aprobar_todas_lineas(request, pk):
    """
    Aprobar todas las líneas pendientes de una solicitud.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Atajo para cuando el cliente aprueba toda la cotización.
    En lugar de aprobar línea por línea, se aprueban todas a la vez.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if request.method == 'POST':
        from almacen.utils.cotizacion_items_cliente import (
            solicitud_permite_aprobar_lineas,
        )
        # EXPLICACIÓN: bloqueo tras PNC hasta que exista cotización/REAC
        if not solicitud_permite_aprobar_lineas(solicitud):
            messages.error(
                request,
                'Tras el aviso PNC al cliente, primero envía una cotización '
                'o propuesta reacondicionado (REAC) antes de aprobar líneas.',
            )
            return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

        lineas_pendientes = solicitud.lineas.filter(
            estado_cliente='pendiente',
            es_linea_reacondicionado=False,
        )
        aprobadas = 0
        
        for linea in lineas_pendientes:
            if linea.aprobar():
                aprobadas += 1
        
        if aprobadas > 0:
            messages.success(
                request,
                f'Se aprobaron {aprobadas} línea(s) de la cotización.'
            )
        reac_pendientes = solicitud.lineas.filter(
            estado_cliente='pendiente',
            es_linea_reacondicionado=True,
        ).count()
        if reac_pendientes > 0:
            messages.info(
                request,
                f'Quedan {reac_pendientes} equipo(s) reacondicionado(s) pendiente(s). '
                'Apruébalos uno por uno para elegir la forma de pago.',
            )
        elif aprobadas == 0:
            messages.info(request, 'No había líneas pendientes por aprobar.')
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
@permission_required_with_message('almacen.change_lineacotizacion')
def rechazar_todas_lineas(request, pk):
    """
    Rechazar todas las líneas pendientes de una solicitud.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Atajo para marcar todas las líneas pendientes como rechazadas
    (texto libre por línea, igual que rechazar una sola).

    Cuando el estado pase a ``totalmente_rechazada``, al volver al detalle
    se abrirá el modal de motivo de catálogo ST (si aún no está registrado).
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)

    if request.method == 'POST':
        motivo = request.POST.get('motivo', 'Rechazado por el cliente')
        lineas_pendientes = solicitud.lineas.filter(estado_cliente='pendiente')
        rechazadas = 0

        for linea in lineas_pendientes:
            if linea.rechazar(motivo=motivo):
                rechazadas += 1

        if rechazadas > 0:
            messages.warning(
                request,
                f'Se rechazaron {rechazadas} línea(s) de la cotización.',
            )
            solicitud.refresh_from_db()
            if solicitud.estado == 'totalmente_rechazada':
                from almacen.utils.sincronizar_rechazo_cotizacion_st import (
                    mensaje_flash_tras_rechazo_total,
                )
                messages.info(
                    request,
                    mensaje_flash_tras_rechazo_total(solicitud),
                )
        else:
            messages.info(request, 'No había líneas pendientes por rechazar.')

    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
@permission_required_with_message('almacen.change_lineacotizacion')
def registrar_motivo_rechazo_st(request, pk):
    """
    Registra motivo/detalle de catálogo ST tras un rechazo total.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Se llama desde el modal que aparece solo cuando la solicitud está
    en ``totalmente_rechazada`` y aún falta `Cotizacion.motivo_rechazo`.

    No vuelve a rechazar líneas: solo escribe la cabecera ST y, si el
    checkbox lo pide, encola el correo de feedback.
    """
    from almacen.utils.sincronizar_rechazo_cotizacion_st import (
        motivo_rechazo_es_valido,
        procesar_feedback_rechazo_desde_almacen,
        sincronizar_cabecera_rechazo_st,
        label_motivo_rechazo,
    )

    solicitud = get_object_or_404(
        SolicitudCotizacion.objects.select_related(
            'orden_servicio',
            'orden_servicio__detalle_equipo',
        ),
        pk=pk,
    )

    if request.method != 'POST':
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    if solicitud.estado != 'totalmente_rechazada':
        messages.error(
            request,
            'Solo puedes registrar el motivo de catálogo ST cuando la '
            'solicitud está totalmente rechazada.',
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    motivo_clave = (request.POST.get('motivo_rechazo') or '').strip()
    detalle_rechazo = (request.POST.get('detalle_rechazo') or '').strip()

    if not motivo_rechazo_es_valido(motivo_clave):
        messages.error(
            request,
            'Debes seleccionar un motivo de rechazo del catálogo.',
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    # Si ya había motivo, igual permitimos actualizar (reabrir modal manual).
    empleado_actual = getattr(request.user, 'empleado', None)
    cotizacion = sincronizar_cabecera_rechazo_st(
        solicitud,
        motivo_clave=motivo_clave,
        detalle_rechazo=detalle_rechazo,
        empleado=empleado_actual,
    )
    if cotizacion is None:
        messages.warning(
            request,
            'No se pudo guardar el motivo en ST (sin orden válida o es venta mostrador).',
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    label = label_motivo_rechazo(motivo_clave)
    messages.success(
        request,
        f'Motivo de rechazo registrado en ST: {label}.',
    )

    enviar_feedback = request.POST.get('enviar_feedback') in (
        'on', '1', 'true', 'True',
    )
    resultado_fb = procesar_feedback_rechazo_desde_almacen(
        solicitud,
        motivo_clave,
        enviar_feedback=enviar_feedback,
        empleado=empleado_actual,
        usuario_id=request.user.pk if request.user.is_authenticated else None,
    )
    if enviar_feedback and resultado_fb.get('enviado'):
        messages.success(request, f"📧 {resultado_fb['mensaje']}")
    elif enviar_feedback and resultado_fb.get('mensaje'):
        messages.warning(request, resultado_fb['mensaje'])

    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
@permission_required_with_message('almacen.change_lineacotizacion')
def registrar_motivo_rechazo_solicitud(request, pk):
    """
    Registra motivo/detalle de rechazo en la cabecera de Almacén (sin orden ST).

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cuando la cotización queda ``totalmente_rechazada`` sin orden vinculada
    (o con orden FL- venta_mostrador), tipificamos en SolicitudCotizacion
    con el mismo catálogo que ST, pero:
    - No se crea OrdenServicio
    - No se crea Cotizacion ST
    - No se envía FeedbackCliente (exige orden)

    Args:
        request: POST con motivo_rechazo y detalle_rechazo.
        pk: PK de SolicitudCotizacion.

    Efectos secundarios:
        Actualiza motivo_rechazo / detalle_rechazo de la solicitud.
    """
    from almacen.utils.sincronizar_rechazo_cotizacion_st import (
        admite_motivo_rechazo_almacen,
        guardar_motivo_rechazo_solicitud,
        label_motivo_rechazo,
        motivo_rechazo_es_valido,
    )

    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)

    if request.method != 'POST':
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    if solicitud.estado != 'totalmente_rechazada':
        messages.error(
            request,
            'Solo puedes registrar el motivo cuando la solicitud '
            'está totalmente rechazada.',
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    # EXPLICACIÓN: si hay camino ST, este endpoint no aplica
    if not admite_motivo_rechazo_almacen(solicitud):
        messages.error(
            request,
            'Esta cotización tiene orden de Servicio Técnico: '
            'usa el registro de motivo ST.',
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    motivo_clave = (request.POST.get('motivo_rechazo') or '').strip()
    detalle_rechazo = (request.POST.get('detalle_rechazo') or '').strip()

    if not motivo_rechazo_es_valido(motivo_clave):
        messages.error(
            request,
            'Debes seleccionar un motivo de rechazo del catálogo.',
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    try:
        guardar_motivo_rechazo_solicitud(
            solicitud,
            motivo_clave=motivo_clave,
            detalle=detalle_rechazo,
        )
    except ValueError:
        messages.error(
            request,
            'Debes seleccionar un motivo de rechazo del catálogo.',
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    label = label_motivo_rechazo(motivo_clave)
    messages.success(
        request,
        f'Motivo de rechazo registrado en la cotización: {label}.',
    )
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


