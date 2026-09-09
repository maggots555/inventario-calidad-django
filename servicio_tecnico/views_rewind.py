"""
Vista HTTP del envío masivo de video rewind al cliente.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El rewind individual vive en views_envios_cliente.py (JSON, una orden).
Este archivo es el gemelo de "Cerrar Finalizados": un POST desde la lista
de Órdenes Activas que encola TODAS las pendientes.

La vista es delgada a propósito (regla de no hinchar views_*.py gordos):
el cerebro está en services/rewind_egreso.py. urls.py sigue usando
views.enviar_rewinds_pendientes gracias al reexport en views.py.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .decorators import permission_required_with_message
from .services.rewind_egreso import (
    encolar_rewinds_pendientes,
    usuario_es_gerencia,
)


@login_required
@permission_required_with_message('servicio_tecnico.change_ordenservicio')
def enviar_rewinds_pendientes(request):
    """
    Encola el video rewind de todas las órdenes disponibles y no enviadas.

    Objetivo de negocio:
        Gerencia manda de un clic los rewind que el detalle ya podría enviar
        uno por uno: finalizadas + entregadas recientes (30 días), con fotos
        completas, email válido y sin historial de 'video rewind'.

    Args:
        request: HttpRequest. Solo POST dispara el lote; GET avisa y redirige.

    Returns:
        Redirect a lista de órdenes activas (siempre).

    Efectos secundarios:
        Encola N chains Celery (generar video → correo) y escribe historial
        por cada orden. No espera a FFmpeg: el worker lo hace en segundo plano.
    """
    if request.method != 'POST':
        messages.warning(
            request,
            'Método no permitido. Use el botón "Mandar Rewind".',
        )
        return redirect('servicio_tecnico:lista_activas')

    # El template ya oculta el botón, pero alguien podría POST-ear la URL a mano.
    if not usuario_es_gerencia(request.user):
        messages.error(
            request,
            'Solo gerencia puede enviar rewind masivo.',
        )
        return redirect('servicio_tecnico:lista_activas')

    from config.paises_config import get_pais_actual

    # db_alias viaja a Celery: sin él el worker escribiría siempre en México.
    db_alias = get_pais_actual()['db_alias']
    # El service filtra, encola chains y escribe historial; aquí solo contamos.
    cantidad = encolar_rewinds_pendientes(request.user, db_alias)

    if cantidad > 0:
        messages.success(
            request,
            f'Se encolaron {cantidad} video(s) rewind. '
            'La generación y el correo siguen en segundo plano; '
            'cada video puede tardar varios minutos.',
        )
    else:
        messages.info(
            request,
            'No hay rewind pendientes por enviar.',
        )

    return redirect('servicio_tecnico:lista_activas')
