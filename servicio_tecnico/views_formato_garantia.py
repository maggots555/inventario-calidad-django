"""
Vistas del Formato Digital Garantía Dell (wizard iPad + APIs + PDF).

EXPLICACIÓN PARA PRINCIPIANTES:
------------------------------------------------
Módulo hermano del formato OOW: wizard, guardado AJAX, finalización,
preview PDF y puente desde Consultar SICSER (tab garantía).
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
def formato_garantia_wizard(request, orden_id: int):
    """
    Pantalla wizard del Formato Digital Garantía Dell (iPad/PWA).

    Args:
        request: HttpRequest autenticado
        orden_id: PK de OrdenServicio

    Efectos secundarios:
        Puede crear un borrador FormatoServicioGarantia si no existe.
    """
    from config.constants import (
        COMO_ENTERASTE_GARANTIA_CHOICES,
        ACTIVIDADES_NO_INCLUIDAS_GARANTIA_DELL,
        VISTAS_DANO_ESTETICO_AIO,
        VISTAS_DANO_ESTETICO_ESCRITORIO,
        VISTAS_DANO_ESTETICO_LAPTOP,
    )
    from .services.formato_garantia import (
        datos_orden_para_wizard,
        obtener_o_crear_borrador,
        orden_es_candidata_formato_garantia,
        serializar_formato,
        texto_aviso_privacidad_actual,
    )

    orden = get_object_or_404(
        OrdenServicio.objects.select_related('detalle_equipo', 'tecnico_asignado_actual'),
        pk=orden_id,
    )
    if not orden_es_candidata_formato_garantia(orden):
        messages.warning(
            request,
            'Esta orden no es candidata a Formato Digital Garantía Dell '
            '(solo órdenes importadas desde SICSER garantía).',
        )
        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

    try:
        formato = obtener_o_crear_borrador(orden, usuario=request.user)
    except Exception as exc:
        logger.exception('Error creando borrador formato Garantía: %s', exc)
        messages.error(request, f'No se pudo abrir el formato Garantía: {exc}')
        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

    version_aviso, texto_aviso = texto_aviso_privacidad_actual()

    evidencias = ImagenOrden.objects.filter(
        orden=orden,
        tipo='escaneo_garantia',
    ).order_by('-fecha_subida')[:20]

    context = {
        'page_title': f'Formato Garantía — {orden.numero_orden_interno}',
        'orden': orden,
        'formato': formato,
        'formato_json': serializar_formato(formato),
        'orden_json': datos_orden_para_wizard(orden),
        'aviso_privacidad_texto': texto_aviso,
        'aviso_privacidad_version': version_aviso,
        # Aviso Dell (solo informativo): aparece en el PDF; NO se guarda aceptación en BD.
        'actividades_no_incluidas': ACTIVIDADES_NO_INCLUIDAS_GARANTIA_DELL,
        'como_enteraste_choices': COMO_ENTERASTE_GARANTIA_CHOICES,
        'vistas_laptop': VISTAS_DANO_ESTETICO_LAPTOP,
        'vistas_escritorio': VISTAS_DANO_ESTETICO_ESCRITORIO,
        'vistas_aio': VISTAS_DANO_ESTETICO_AIO,
        'evidencias': evidencias,
        'url_guardar': reverse('servicio_tecnico:formato_garantia_guardar', args=[orden.pk]),
        'url_finalizar': reverse('servicio_tecnico:formato_garantia_finalizar', args=[orden.pk]),
        'url_reenviar': reverse(
            'servicio_tecnico:formato_garantia_reenviar_email', args=[orden.pk],
        ),
        'url_pdf': reverse('servicio_tecnico:formato_garantia_pdf', args=[orden.pk]),
        'url_detalle': reverse('servicio_tecnico:detalle_orden', args=[orden.pk]),
    }
    return render(request, 'servicio_tecnico/formato_garantia.html', context)


@login_required
@permission_required_with_message('servicio_tecnico.change_ordenservicio')
@require_http_methods(['POST'])
def formato_garantia_guardar(request, orden_id: int):
    """
    Guarda borrador del formato Garantía vía AJAX (JSON).

    Body JSON: campos del formulario + firmas/vistas en data URL base64.

    Returns:
        JsonResponse con formato serializado
    """
    from .services.formato_garantia import (
        FormatoGarantiaError,
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
        formato = aplicar_payload_borrador(
            formato,
            payload,
            usuario=request.user,
            permitir_finalizado=(formato.estado == 'finalizado'),
        )
    except FormatoGarantiaError as exc:
        return _json_error(str(exc))
    except Exception as exc:
        logger.exception('Error guardando formato Garantía: %s', exc)
        return _json_error(f'Error al guardar: {exc}', status=500)

    return JsonResponse({
        'success': True,
        'mensaje': (
            'Datos guardados. Usa “Regenerar PDF” para actualizar el documento.'
            if formato.estado == 'finalizado'
            else 'Borrador guardado'
        ),
        'formato': serializar_formato(formato),
    })


@login_required
@permission_required_with_message('servicio_tecnico.change_ordenservicio')
@require_http_methods(['POST'])
def formato_garantia_finalizar(request, orden_id: int):
    """
    Guarda (si viene payload), valida, genera PDF y marca finalizado.

    Body JSON opcional: mismos campos que guardar + enviar_email (bool).

    Efectos secundarios:
        PDF en media; opcionalmente encola task de correo con db_alias.
    """
    from config.paises_config import get_pais_actual
    from .services.formato_garantia import (
        FormatoGarantiaError,
        aplicar_payload_borrador,
        finalizar_formato,
        lista_emails_envio,
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
        solo_regenerar = bool(payload.get('solo_regenerar'))
        forzar = bool(payload.get('forzar_regenerar')) or solo_regenerar or (
            formato.estado == 'finalizado'
        )
        if payload:
            formato = aplicar_payload_borrador(
                formato,
                payload,
                usuario=request.user,
                permitir_finalizado=True,
            )
        formato = finalizar_formato(
            formato,
            usuario=request.user,
            forzar_regenerar=forzar,
        )
    except FormatoGarantiaError as exc:
        return _json_error(str(exc))
    except Exception as exc:
        logger.exception('Error finalizando formato Garantía: %s', exc)
        return _json_error(f'Error al finalizar: {exc}', status=500)

    emails = lista_emails_envio(formato)
    enviar = bool(payload.get('enviar_email')) and not solo_regenerar
    if enviar and emails and formato.pdf:
        try:
            from .tasks import enviar_formato_garantia_email_task
            enviar_formato_garantia_email_task.delay(
                formato_id=formato.pk,
                usuario_id=request.user.pk,
                db_alias=get_pais_actual()['db_alias'],
            )
        except Exception as exc:
            logger.warning('No se pudo encolar email formato Garantía: %s', exc)

    return JsonResponse({
        'success': True,
        'mensaje': (
            'PDF regenerado (sin reenviar correo)'
            if solo_regenerar
            else 'Formato finalizado y PDF generado'
        ),
        'formato': serializar_formato(formato),
        'pdf_url': reverse('servicio_tecnico:formato_garantia_pdf', args=[orden.pk]),
    })


@login_required
@permission_required_with_message('servicio_tecnico.change_ordenservicio')
@require_http_methods(['POST'])
def formato_garantia_reenviar_email(request, orden_id: int):
    """
    Reenvía el PDF del formato Garantía por correo (sin regenerar el PDF).

    Body JSON opcional:
        emails_envio: lista de hasta 3 correos
        email_envio: correo único (compatibilidad)

    Efectos secundarios:
        Puede actualizar emails_envio; encola Celery con db_alias.
    """
    from config.paises_config import get_pais_actual
    from .models import FormatoServicioGarantia
    from .services.formato_garantia import (
        aplicar_emails_al_formato,
        lista_emails_envio,
        serializar_formato,
    )

    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    try:
        formato = FormatoServicioGarantia.objects.get(orden=orden)
    except FormatoServicioGarantia.DoesNotExist:
        return _json_error('No hay formato Garantía para esta orden.')

    if formato.estado != 'finalizado' or not formato.pdf:
        return _json_error(
            'Primero debes finalizar el formato y generar el PDF '
            'antes de reenviar el correo.'
        )

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return _json_error('JSON inválido')

    if 'emails_envio' in payload or 'email_envio' in payload:
        raw = payload.get('emails_envio', payload.get('email_envio'))
        aplicar_emails_al_formato(formato, raw)
        formato.save(update_fields=['emails_envio', 'email_envio', 'fecha_actualizacion'])

    emails = lista_emails_envio(formato)
    if not emails:
        return _json_error(
            'Captura al menos un correo en “Email(s) para recibir el formato”.'
        )

    try:
        from .tasks import enviar_formato_garantia_email_task
        enviar_formato_garantia_email_task.delay(
            formato_id=formato.pk,
            usuario_id=request.user.pk,
            db_alias=get_pais_actual()['db_alias'],
        )
    except Exception as exc:
        logger.exception('No se pudo encolar reenvío formato Garantía: %s', exc)
        return _json_error(f'No se pudo encolar el correo: {exc}', status=500)

    destinarios_txt = ', '.join(emails)
    return JsonResponse({
        'success': True,
        'mensaje': f'Correo encolado para: {destinarios_txt}',
        'emails': emails,
        'formato': serializar_formato(formato),
    })


@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def formato_garantia_pdf(request, orden_id: int):
    """
    Descarga o previsualiza el PDF del formato Garantía finalizado.

    Query:
        inline=1 → Content-Disposition inline (visor del navegador)
    """
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    formato = getattr(orden, 'formato_garantia', None)
    if not formato or not formato.pdf:
        messages.warning(request, 'Aún no hay PDF generado para este formato.')
        return redirect('servicio_tecnico:formato_garantia_wizard', orden_id=orden.pk)

    inline = request.GET.get('inline') == '1'
    disposition = 'inline' if inline else 'attachment'
    dps = (
        orden.detalle_equipo.orden_cliente
        or orden.detalle_equipo.folio_sicser
        or orden.numero_orden_interno
    )
    response = FileResponse(
        formato.pdf.open('rb'),
        content_type='application/pdf',
    )
    response['Content-Disposition'] = (
        f'{disposition}; filename="FormatoGarantia_{dps}.pdf"'
    )
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Tras “Regenerar PDF” el archivo cambia pero la URL es la misma. Sin estos
    # headers el navegador puede seguir mostrando el PDF viejo en caché.
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    return response


@login_required
@permission_required_with_message('servicio_tecnico.add_ordenservicio')
@require_http_methods(['POST'])
def abrir_formato_garantia_desde_sicser(request):
    """
    Desde Consultar SICSER: importa la orden garantía si falta y abre el wizard.

    POST:
        id_externo: numero_dps SICSER
        sucursal_id: opcional
        q / tab: para mensajes de error / regreso

    Efectos secundarios:
        Puede crear OrdenServicio vía sicser_import; redirige al wizard.
    """
    from config.paises_config import get_pais_actual
    from .sicser_client import SicserAPIError, buscar_registro_garantia_por_dps
    from .sicser_import import (
        SicserImportError,
        importar_orden_garantia_desde_sicser,
        mapa_importaciones_sicser,
    )
    from .services.formato_garantia import obtener_o_crear_borrador

    id_externo = request.POST.get('id_externo', '').strip()
    texto_busqueda = request.POST.get('q', '').strip()
    sucursal_id_raw = request.POST.get('sucursal_id', '').strip()
    sucursal_id = int(sucursal_id_raw) if sucursal_id_raw.isdigit() else None

    redirect_listado = reverse('servicio_tecnico:consultar_sicser') + '?tab=garantia'
    if texto_busqueda:
        redirect_listado += f'&q={quote(texto_busqueda)}'

    if not id_externo:
        messages.error(request, 'Falta el número DPS de la orden SICSER.')
        return redirect(redirect_listado)

    codigo_pais = get_pais_actual().get('codigo', 'MX')
    _, mapa_garantia = mapa_importaciones_sicser()

    try:
        if id_externo in mapa_garantia:
            orden_id = mapa_garantia[id_externo]['orden_id']
            orden = OrdenServicio.objects.get(pk=orden_id)
            obtener_o_crear_borrador(orden, usuario=request.user)
            return redirect('servicio_tecnico:formato_garantia_wizard', orden_id=orden.pk)

        registro = buscar_registro_garantia_por_dps(int(id_externo), codigo_pais)
        if not registro:
            raise SicserImportError(
                'No se encontró la garantía en SICSER. Actualice el listado e intente de nuevo.'
            )
        resultado = importar_orden_garantia_desde_sicser(
            registro,
            request.user,
            sucursal_id=sucursal_id,
        )
        obtener_o_crear_borrador(resultado.orden, usuario=request.user)
        messages.success(
            request,
            f'{resultado.mensaje} Abriendo Formato Digital Garantía Dell…',
        )
        return redirect(
            'servicio_tecnico:formato_garantia_wizard',
            orden_id=resultado.orden.pk,
        )
    except (SicserImportError, SicserAPIError, ValueError, OrdenServicio.DoesNotExist) as exc:
        messages.error(request, f'No se pudo abrir el formato Garantía: {exc}')
        return redirect(redirect_listado)


@login_required
@permission_required_with_message('servicio_tecnico.change_ordenservicio')
@require_http_methods(['POST'])
def formato_garantia_subir_evidencia(request, orden_id: int):
    """
    Sube foto de resultado de escaneo PC Audit (Formato Garantía).

    POST multipart:
        tipo: 'escaneo_garantia'
        imagen: archivo de imagen
        descripcion: texto opcional

    Efectos secundarios:
        Crea ImagenOrden comprimida vía services.multimedia.
    """
    from .services.formato_garantia import _empleado_desde_usuario
    from .services.multimedia import comprimir_y_guardar_imagen

    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    tipo = request.POST.get('tipo', '').strip()
    if tipo != 'escaneo_garantia':
        return _json_error('Tipo de evidencia inválido (solo escaneo PC Audit)')

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
        logger.exception('Error subiendo evidencia Garantía: %s', exc)
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


@login_required
@permission_required_with_message('servicio_tecnico.change_ordenservicio')
@require_http_methods(['POST'])
def formato_garantia_eliminar_evidencia(request, orden_id: int, imagen_id: int):
    """
    Elimina una foto de escaneo PC Audit del Formato Garantía.

    Objetivo de negocio:
        Si el técnico se equivoca al subir el resultado de PC Audit, puede
        borrarlo desde la miniatura del wizard (sin ir a la galería general).

    Args:
        request: HttpRequest POST (AJAX)
        orden_id: PK de OrdenServicio
        imagen_id: PK de ImagenOrden

    Efectos secundarios:
        Borra archivos en disco/storage y el registro ImagenOrden.
        Solo permite tipo ``escaneo_garantia`` de esa orden (seguridad).
    """
    from pathlib import Path

    from .models import HistorialOrden
    from .services.formato_garantia import _empleado_desde_usuario

    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    empleado = _empleado_desde_usuario(request.user)
    if not empleado:
        return _json_error('Tu usuario no tiene perfil de empleado', status=403)

    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Filtramos por orden + tipo para que nadie borre fotos de otra orden
    # ni evidencias que no sean del formato Garantía.
    imagen = ImagenOrden.objects.filter(
        pk=imagen_id,
        orden=orden,
        tipo='escaneo_garantia',
    ).first()
    if not imagen:
        return _json_error('Evidencia no encontrada o no es de escaneo Garantía', status=404)

    descripcion = imagen.descripcion or imagen.nombre_archivo or f'#{imagen.pk}'

    for campo in ('imagen', 'imagen_original'):
        archivo = getattr(imagen, campo, None)
        if not archivo:
            continue
        try:
            ruta = Path(archivo.path)
            if ruta.is_file():
                ruta.unlink()
        except Exception as exc:
            logger.warning(
                '[FORMATO_GARANTIA] No se pudo borrar archivo %s de imagen %s: %s',
                campo, imagen_id, exc,
            )

    imagen.delete()

    try:
        HistorialOrden.objects.create(
            orden=orden,
            tipo_evento='imagen',
            comentario=(
                f'Escaneo PC Audit (Formato Garantía) eliminado: {descripcion} '
                f'(por {empleado.nombre_completo})'
            ),
            usuario=empleado,
            es_sistema=False,
        )
    except Exception as exc:
        logger.warning('[FORMATO_GARANTIA] Historial al eliminar evidencia: %s', exc)

    return JsonResponse({
        'success': True,
        'mensaje': 'Foto eliminada',
        'imagen_id': imagen_id,
    })
