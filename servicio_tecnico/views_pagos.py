"""
Bandeja de pagos por validar en la cuenta de la empresa.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Recepción registra transferencias/tarjetas. Facturación (y gerencia)
entra aquí para ver TODOS los abonos pendientes, no orden por orden.

GET: lista filtrada (pendiente / no_aparece / abiertos).
POST: los mismos botones del detalle (Ya aparece / No aparece).
El cerebro sigue en services/pagos_orden.py.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.urls import reverse

from servicio_tecnico.forms import ValidarPagoOrdenForm
from servicio_tecnico.models import PagoOrden
from servicio_tecnico.services.pagos_orden import (
    FILTROS_BANDEJA_VALIDACION,
    contar_pagos_abiertos_validacion,
    listar_pagos_abiertos_validacion,
    usuario_puede_validar_pago,
    validar_pago_en_cuenta,
)

PAGOS_POR_PAGINA = 25


def _redirigir_acceso_denegado():
    """
    Misma puerta que el decorador de permisos (página amigable).

    Returns:
        HttpResponseRedirect a acceso_denegado de ST.
    """
    mensaje = (
        'Solo Facturación, supervisor y gerencia pueden abrir '
        'la bandeja de pagos por validar.'
    )
    return redirect(
        f"{reverse('servicio_tecnico:acceso_denegado_servicio_tecnico')}"
        f"?mensaje={mensaje}&permiso=validar_pago_cuenta"
    )


def _filtro_bandeja(request) -> str:
    """
    Lee ?filtro= y lo normaliza a una clave válida.

    Args:
        request: HttpRequest (GET o POST).

    Returns:
        'pendiente', 'no_aparece' o 'abiertos'.
    """
    # POST manda el filtro en hidden para no perder la pestaña al confirmar.
    crudo = (request.POST.get('filtro') or request.GET.get('filtro') or '').strip()
    if crudo in FILTROS_BANDEJA_VALIDACION:
        return crudo
    return 'pendiente'


def _url_bandeja(filtro: str) -> str:
    """
    URL de la bandeja conservando el filtro activo.

    Args:
        filtro: clave ya normalizada.

    Returns:
        Ruta relativa con query string si no es el default.
    """
    ruta = reverse('servicio_tecnico:bandeja_pagos_validacion')
    if filtro and filtro != 'pendiente':
        return f'{ruta}?filtro={filtro}'
    return ruta


@login_required
def bandeja_pagos_validacion(request):
    """
    Lista de abonos pendientes de conciliar + acción de validar.

    Args:
        request: GET para consultar; POST form_type=validar_pago.

    Returns:
        Html de la bandeja, o redirect (denegado / post-validar).

    Efectos secundarios:
        POST llama validar_pago_en_cuenta (historial + avisos).
    """
    if not usuario_puede_validar_pago(request.user):
        return _redirigir_acceso_denegado()

    filtro = _filtro_bandeja(request)

    if request.method == 'POST':
        return _procesar_validacion_bandeja(request, filtro)

    pagos = listar_pagos_abiertos_validacion(filtro)
    paginator = Paginator(pagos, PAGOS_POR_PAGINA)
    pagina = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'servicio_tecnico/bandeja_pagos_validacion.html',
        {
            'pagina_pagos': pagina,
            'filtro': filtro,
            'conteos': contar_pagos_abiertos_validacion(),
        },
    )


def _procesar_validacion_bandeja(request, filtro: str):
    """
    POST de la bandeja: marca un pago y vuelve a la misma pestaña.

    Args:
        request: HttpRequest con ValidarPagoOrdenForm.
        filtro: pestaña actual (para el redirect).

    Returns:
        Redirect a la bandeja (éxito o error con messages).
    """
    empleado_actual = getattr(request.user, 'empleado', None)
    form = ValidarPagoOrdenForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'No se pudo leer la decisión de validación.')
        return redirect(_url_bandeja(filtro))

    pago = PagoOrden.objects.filter(pk=form.cleaned_data['pago_id']).first()
    if pago is None:
        messages.error(request, 'No se encontró el pago a validar.')
        return redirect(_url_bandeja(filtro))

    # Paso: mismos botones que en el detalle de la orden.
    aparece = form.cleaned_data['decision'] == 'validado'
    try:
        validar_pago_en_cuenta(
            pago=pago,
            empleado=empleado_actual,
            aparece=aparece,
            nota=form.cleaned_data.get('nota_validacion') or '',
        )
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
        return redirect(_url_bandeja(filtro))

    if aparece:
        messages.success(
            request,
            f'Pago de ${pago.monto} marcado como validado en la cuenta.',
        )
    else:
        messages.warning(
            request,
            f'Pago de ${pago.monto} marcado como no aparece en la cuenta. '
            f'Se avisó a quien lo registró.',
        )
    return redirect(_url_bandeja(filtro))
