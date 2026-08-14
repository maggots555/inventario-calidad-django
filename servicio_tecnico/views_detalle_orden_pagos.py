"""
Handlers POST de detalle_orden: pagos y datos de factura.

EXPLICACIÓN PARA PRINCIPIANTES (Fase C):
La vista detalle_orden solo despacha según form_type. Este módulo
recibe el cobro (abono + comprobante) y los flags de factura fiscal.
La lógica de dinero vive en services/pagos_orden.py.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect

from servicio_tecnico.forms import DatosFacturaOrdenForm, RegistrarPagoOrdenForm
from servicio_tecnico.services.historial import registrar_historial
from servicio_tecnico.services.pagos_orden import (
    eliminar_pago,
    registrar_pago,
    usuario_puede_registrar_pago,
)
from servicio_tecnico.models import PagoOrden


def handle_registrar_pago(request, orden, empleado_actual):
    """
    Handler POST form_type='registrar_pago'.

    Args:
        request: HttpRequest con POST y opcionalmente FILES.
        orden: OrdenServicio ya cargada.
        empleado_actual: Empleado del usuario o None.

    Returns:
        HttpResponse redirect si terminó; None si el form es inválido
        (se re-renderiza el GET con messages).

    Efectos secundarios:
        Crea PagoOrden, comprime comprobante, escribe HistorialOrden.
    """
    if not usuario_puede_registrar_pago(request.user):
        messages.error(
            request,
            'No tienes permiso para registrar pagos. '
            'Solo Facturación, Recepción y gerencia pueden cobrar.',
        )
        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

    form = RegistrarPagoOrdenForm(request.POST, request.FILES)
    if not form.is_valid():
        for campo, errores in form.errors.items():
            for error in errores:
                messages.error(request, f'{campo}: {error}')
        return None

    try:
        pago = registrar_pago(
            orden=orden,
            empleado=empleado_actual,
            monto=form.cleaned_data['monto'],
            tipo=form.cleaned_data['tipo'],
            metodo=form.cleaned_data['metodo'],
            notas=form.cleaned_data.get('notas') or '',
            comprobante_file=form.cleaned_data.get('comprobante'),
        )
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
        return None

    messages.success(
        request,
        f'Pago de ${pago.monto} registrado ({pago.get_tipo_display()}).',
    )
    return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)


def handle_actualizar_datos_factura(request, orden, empleado_actual):
    """
    Handler POST form_type='actualizar_datos_factura'.

    Args:
        request: HttpRequest con POST.
        orden: OrdenServicio ya cargada.
        empleado_actual: Empleado del usuario o None.

    Returns:
        HttpResponse redirect o None si el form es inválido.

    Efectos secundarios:
        Actualiza requiere_factura / factura_emitida / motivo_no_factura
        y deja un evento en el historial.
    """
    if not usuario_puede_registrar_pago(request.user):
        messages.error(
            request,
            'No tienes permiso para actualizar los datos de factura.',
        )
        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

    form = DatosFacturaOrdenForm(request.POST, instance=orden)
    if not form.is_valid():
        for campo, errores in form.errors.items():
            for error in errores:
                messages.error(request, f'{campo}: {error}')
        return None

    form.save()
    registrar_historial(
        orden=orden,
        tipo_evento='sistema',
        usuario=empleado_actual,
        comentario=(
            'Datos de factura actualizados: '
            f"requiere={orden.requiere_factura}, "
            f"emitida={orden.factura_emitida}."
        ),
        es_sistema=True,
    )
    messages.success(request, 'Datos de factura guardados.')
    return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)


def handle_eliminar_pago(request, orden, empleado_actual):
    """
    Handler POST form_type='eliminar_pago' (corrección de captura).

    Args:
        request: HttpRequest; espera pago_id en POST.
        orden: OrdenServicio ya cargada.
        empleado_actual: Empleado del usuario o None.

    Returns:
        HttpResponse redirect siempre (éxito o error con message).

    Efectos secundarios:
        Borra el PagoOrden si pertenece a esta orden.
    """
    if not usuario_puede_registrar_pago(request.user):
        messages.error(request, 'No tienes permiso para eliminar pagos.')
        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

    pago_id = request.POST.get('pago_id')
    pago = PagoOrden.objects.filter(pk=pago_id, orden=orden).first()
    if pago is None:
        messages.error(request, 'No se encontró el pago a eliminar.')
        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

    try:
        eliminar_pago(pago, empleado_actual)
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

    messages.success(request, 'Pago eliminado. El saldo se recalculó.')
    return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
