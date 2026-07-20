"""
Vistas del Formato Digital OOW (wizard iPad + APIs + PDF).

EXPLICACIÓN PARA PRINCIPIANTES:
------------------------------------------------
Módulo hermano (no monolito): concentra el wizard, guardado AJAX,
finalización, preview PDF y el puente desde Consultar SICSER
(importar si hace falta y abrir el formato en SIGMA).

urls.py usa views.* gracias a los reexports en views.py.
"""

from __future__ import annotations

import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from urllib.parse import quote

from .decorators import permission_required_with_message
from .models import ImagenOrden, OrdenServicio

logger = logging.getLogger(__name__)


def _json_error(mensaje: str, status: int = 400) -> JsonResponse:
    return JsonResponse({'success': False, 'error': mensaje}, status=status)


@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def formato_oow_wizard(request, orden_id: int):
    """
    Pantalla wizard del Formato Digital OOW (optimizada para iPad/PWA).

    Args:
        request: HttpRequest autenticado
        orden_id: PK de OrdenServicio

    Efectos secundarios:
        Puede crear un borrador FormatoServicioOOW si no existe.
    """
    from config.constants import (
        COMO_ENTERASTE_OOW_CHOICES,
        VISTAS_DANO_ESTETICO_ESCRITORIO,
        VISTAS_DANO_ESTETICO_LAPTOP,
    )
    from .services.formato_oow import (
        FormatoOOWError,
        datos_orden_para_wizard,
        obtener_o_crear_borrador,
        orden_es_candidata_formato_oow,
        serializar_formato,
        texto_aviso_privacidad_actual,
    )

    orden = get_object_or_404(
        OrdenServicio.objects.select_related('detalle_equipo', 'tecnico_asignado_actual'),
        pk=orden_id,
    )
    if not orden_es_candidata_formato_oow(orden):
        messages.warning(
            request,
            'Esta orden no es candidata a Formato Digital OOW (fuera de garantía).',
        )
        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

    try:
        formato = obtener_o_crear_borrador(orden, usuario=request.user)
    except Exception as exc:
        logger.exception('Error creando borrador formato OOW: %s', exc)
        messages.error(request, f'No se pudo abrir el formato OOW: {exc}')
        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

    version_aviso, texto_aviso = texto_aviso_privacidad_actual()

    # Evidencias ya subidas (tipos OOW)
    evidencias = ImagenOrden.objects.filter(
        orden=orden,
        tipo__in=('identificacion_oow', 'escaneo_oow', 'evidencia_danos_oow'),
    ).order_by('-fecha_subida')[:20]

    context = {
        'page_title': f'Formato OOW — {orden.numero_orden_interno}',
        'orden': orden,
        'formato': formato,
        'formato_json': serializar_formato(formato),
        'orden_json': datos_orden_para_wizard(orden),
        'aviso_privacidad_texto': texto_aviso,
        'aviso_privacidad_version': version_aviso,
        'como_enteraste_choices': COMO_ENTERASTE_OOW_CHOICES,
        'vistas_laptop': VISTAS_DANO_ESTETICO_LAPTOP,
        'vistas_escritorio': VISTAS_DANO_ESTETICO_ESCRITORIO,
        'evidencias': evidencias,
        'url_guardar': reverse('servicio_tecnico:formato_oow_guardar', args=[orden.pk]),
        'url_finalizar': reverse('servicio_tecnico:formato_oow_finalizar', args=[orden.pk]),
        'url_pdf': reverse('servicio_tecnico:formato_oow_pdf', args=[orden.pk]),
        'url_detalle': reverse('servicio_tecnico:detalle_orden', args=[orden.pk]),
    }
    return render(request, 'servicio_tecnico/formato_oow.html', context)


@login_required
@permission_required_with_message('servicio_tecnico.change_ordenservicio')
@require_http_methods(['POST'])
def formato_oow_guardar(request, orden_id: int):
    """
    Guarda borrador del formato OOW vía AJAX (JSON).

    Body JSON: campos del formulario + firmas/vistas en data URL base64.

    Returns:
        JsonResponse con formato serializado
    """
    from .services.formato_oow import (
        FormatoOOWError,
        aplicar_payload_borrador,
        obtener_o_crear_borrador,
        serializar_formato,
    )

    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return _json_error('JSON inválido')

    try:
        formato = obtener_o_crear_borrador(orden, usuario=request.user)
        formato = aplicar_payload_borrador(formato, payload, usuario=request.user)
    except FormatoOOWError as exc:
        return _json_error(str(exc))
    except Exception as exc:
        logger.exception('Error guardando formato OOW: %s', exc)
        return _json_error(f'Error al guardar: {exc}', status=500)

    return JsonResponse({
        'success': True,
        'mensaje': 'Borrador guardado',
        'formato': serializar_formato(formato),
    })


@login_required
@permission_required_with_message('servicio_tecnico.change_ordenservicio')
@require_http_methods(['POST'])
def formato_oow_finalizar(request, orden_id: int):
    """
    Guarda (si viene payload), valida, genera PDF y marca finalizado.

    Body JSON opcional: mismos campos que guardar + enviar_email (bool).

    Efectos secundarios:
        PDF en media; opcionalmente encola task de correo con db_alias.
    """
    from config.paises_config import get_pais_actual
    from .services.formato_oow import (
        FormatoOOWError,
        aplicar_payload_borrador,
        finalizar_formato,
        obtener_o_crear_borrador,
        serializar_formato,
    )

    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return _json_error('JSON inválido')

    try:
        formato = obtener_o_crear_borrador(orden, usuario=request.user)
        if payload:
            formato = aplicar_payload_borrador(formato, payload, usuario=request.user)
        forzar = bool(payload.get('forzar_regenerar'))
        formato = finalizar_formato(
            formato,
            usuario=request.user,
            forzar_regenerar=forzar,
        )
    except FormatoOOWError as exc:
        return _json_error(str(exc))
    except Exception as exc:
        logger.exception('Error finalizando formato OOW: %s', exc)
        return _json_error(f'Error al finalizar: {exc}', status=500)

    # Envío de correo opcional
    if payload.get('enviar_email') and formato.email_envio and formato.pdf:
        try:
            from .tasks import enviar_formato_oow_email_task
            enviar_formato_oow_email_task.delay(
                formato_id=formato.pk,
                usuario_id=request.user.pk,
                db_alias=get_pais_actual()['db_alias'],
            )
        except Exception as exc:
            logger.warning('No se pudo encolar email formato OOW: %s', exc)

    return JsonResponse({
        'success': True,
        'mensaje': 'Formato finalizado y PDF generado',
        'formato': serializar_formato(formato),
        'pdf_url': reverse('servicio_tecnico:formato_oow_pdf', args=[orden.pk]),
    })


@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def formato_oow_pdf(request, orden_id: int):
    """
    Descarga o previsualiza el PDF del formato OOW finalizado.

    Query:
        inline=1 → Content-Disposition inline (visor del navegador)
    """
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    formato = getattr(orden, 'formato_oow', None)
    if not formato or not formato.pdf:
        messages.warning(request, 'Aún no hay PDF generado para este formato.')
        return redirect('servicio_tecnico:formato_oow_wizard', orden_id=orden.pk)

    inline = request.GET.get('inline') == '1'
    disposition = 'inline' if inline else 'attachment'
    response = FileResponse(
        formato.pdf.open('rb'),
        content_type='application/pdf',
    )
    response['Content-Disposition'] = (
        f'{disposition}; filename="FormatoOOW_{orden.numero_orden_interno}.pdf"'
    )
    return response


@login_required
@permission_required_with_message('servicio_tecnico.add_ordenservicio')
@require_http_methods(['POST'])
def abrir_formato_oow_desde_sicser(request):
    """
    Desde Consultar SICSER: importa la orden OOW si falta y abre el wizard SIGMA.

    POST:
        id_externo: id_orden SICSER
        sucursal_id: opcional
        q / tab: para mensajes de error / regreso

    Efectos secundarios:
        Puede crear OrdenServicio vía sicser_import; redirige al wizard.
    """
    from config.paises_config import get_pais_actual
    from .sicser_client import SicserAPIError, buscar_registro_oow_por_id
    from .sicser_import import (
        SicserImportError,
        importar_orden_oow_desde_sicser,
        mapa_importaciones_sicser,
    )
    from .services.formato_oow import obtener_o_crear_borrador

    id_externo = request.POST.get('id_externo', '').strip()
    texto_busqueda = request.POST.get('q', '').strip()
    sucursal_id_raw = request.POST.get('sucursal_id', '').strip()
    sucursal_id = int(sucursal_id_raw) if sucursal_id_raw.isdigit() else None

    redirect_listado = reverse('servicio_tecnico:consultar_sicser') + '?tab=oow'
    if texto_busqueda:
        redirect_listado += f'&q={quote(texto_busqueda)}'

    if not id_externo:
        messages.error(request, 'Falta el id de la orden SICSER.')
        return redirect(redirect_listado)

    codigo_pais = get_pais_actual().get('codigo', 'MX')
    mapa_oow, _ = mapa_importaciones_sicser()

    try:
        # Si ya está importada, abrir wizard directo
        if id_externo in mapa_oow:
            orden_id = mapa_oow[id_externo]['orden_id']
            orden = OrdenServicio.objects.get(pk=orden_id)
            obtener_o_crear_borrador(orden, usuario=request.user)
            return redirect('servicio_tecnico:formato_oow_wizard', orden_id=orden.pk)

        registro = buscar_registro_oow_por_id(int(id_externo), codigo_pais)
        if not registro:
            raise SicserImportError(
                'No se encontró la orden OOW en SICSER. Actualice el listado e intente de nuevo.'
            )
        resultado = importar_orden_oow_desde_sicser(
            registro,
            request.user,
            sucursal_id=sucursal_id,
        )
        obtener_o_crear_borrador(resultado.orden, usuario=request.user)
        messages.success(
            request,
            f'{resultado.mensaje} Abriendo Formato Digital OOW…',
        )
        return redirect(
            'servicio_tecnico:formato_oow_wizard',
            orden_id=resultado.orden.pk,
        )
    except (SicserImportError, SicserAPIError, ValueError, OrdenServicio.DoesNotExist) as exc:
        messages.error(request, f'No se pudo abrir el formato OOW: {exc}')
        return redirect(redirect_listado)


@login_required
@permission_required_with_message('servicio_tecnico.change_ordenservicio')
@require_http_methods(['POST'])
def formato_oow_subir_evidencia(request, orden_id: int):
    """
    Sube foto de evidencia de daños o resultado de escaneo (Formato OOW).

    POST multipart:
        tipo: 'identificacion_oow' | 'escaneo_oow'
        imagen: archivo de imagen
        descripcion: texto opcional

    Efectos secundarios:
        Crea ImagenOrden comprimida vía services.multimedia.
    """
    from .services.formato_oow import _empleado_desde_usuario
    from .services.multimedia import comprimir_y_guardar_imagen

    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    tipo = request.POST.get('tipo', '').strip()
    if tipo not in ('identificacion_oow', 'escaneo_oow'):
        return _json_error('Tipo de evidencia inválido')

    archivo = request.FILES.get('imagen')
    if not archivo:
        return _json_error('No se recibió ninguna imagen')

    empleado = _empleado_desde_usuario(request.user)
    if not empleado:
        return _json_error('Tu usuario no tiene perfil de empleado', status=403)

    descripcion = (request.POST.get('descripcion') or '')[:200]
    try:
        imagen = comprimir_y_guardar_imagen(
            orden=orden,
            imagen_file=archivo,
            tipo=tipo,
            descripcion=descripcion,
            empleado=empleado,
        )
    except Exception as exc:
        logger.exception('Error subiendo evidencia OOW: %s', exc)
        return _json_error(f'Error al subir imagen: {exc}', status=500)

    return JsonResponse({
        'success': True,
        'mensaje': 'Evidencia guardada',
        'imagen': {
            'id': imagen.pk,
            'tipo': imagen.tipo,
            'url': imagen.imagen.url if imagen.imagen else '',
            'descripcion': imagen.descripcion,
        },
    })
