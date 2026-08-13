"""
Handlers POST de detalle_orden: mano de obra y cotización (Fase C).

EXPLICACIÓN PARA PRINCIPIANTES:
guardar MO, generar cotización, editar MO/fecha y aceptar/rechazar.
El rechazo puede dejar feedback_* en session para modales de confirmación.
"""

from decimal import Decimal

from django.contrib import messages
from django.shortcuts import redirect

from .forms import GuardarManoObraForm, GestionarCotizacionForm
from .models import Cotizacion, HistorialOrden


def handle_guardar_mano_obra(request, orden, empleado_actual):
    """
    Handler POST form_type in ('guardar_mano_obra').

    Args:
        request: HttpRequest Django.
        orden: OrdenServicio ya cargada.
        empleado_actual: Empleado del usuario o None.

    Returns:
        HttpResponse si el flujo terminó (redirect/JSON); None para
        continuar al render GET (form inválido con messages).
    """
    form_guardar_mo = GuardarManoObraForm(request.POST, instance=orden)
    if form_guardar_mo.is_valid():
        from servicio_tecnico.utils_gama import (
            aplicar_gama_por_mano_obra,
            etiqueta_gama,
        )

        costo_anterior = orden.costo_mano_obra
        # Gama previa (estimado por modelo) para el mensaje al usuario
        gama_antes = getattr(
            getattr(orden, 'detalle_equipo', None), 'gama', None
        )
        orden_actualizada = form_guardar_mo.save()
        nuevo_costo = orden_actualizada.costo_mano_obra

        # Si ya hay cotización, mantener ambos valores alineados
        if hasattr(orden_actualizada, 'cotizacion'):
            cotizacion_mo = orden_actualizada.cotizacion
            cotizacion_mo.costo_mano_obra = nuevo_costo
            cotizacion_mo.save(update_fields=['costo_mano_obra'])

        # Cascada: MO > 0 redefine la gama del equipo (fuente de verdad)
        gama_aplicada = aplicar_gama_por_mano_obra(
            orden_actualizada,
            nuevo_costo,
            usuario=empleado_actual,
        )

        msg_mo = (
            f'✅ Mano de obra guardada: ${costo_anterior} → ${nuevo_costo}. '
            f'La cotización no se crea automáticamente.'
        )
        if gama_aplicada:
            msg_mo += (
                f' Gama actualizada: {etiqueta_gama(gama_antes)} → '
                f'{etiqueta_gama(gama_aplicada)} (según costo).'
            )
        messages.success(request, msg_mo)
        HistorialOrden.objects.create(
            orden=orden_actualizada,
            tipo_evento='cotizacion',
            comentario=(
                f'Mano de obra guardada en la orden: '
                f'${costo_anterior} → ${nuevo_costo} (sin crear cotización)'
            ),
            usuario=empleado_actual,
            es_sistema=False,
        )
    else:
        messages.error(request, '❌ Error al guardar la mano de obra. Revisa el valor ingresado.')

    return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

def handle_crear_cotizacion(request, orden, empleado_actual):
    """
    Handler POST form_type in ('crear_cotizacion', 'generar_cotizacion').

    Args:
        request: HttpRequest Django.
        orden: OrdenServicio ya cargada.
        empleado_actual: Empleado del usuario o None.

    Returns:
        HttpResponse si el flujo terminó (redirect/JSON); None para
        continuar al render GET (form inválido con messages).
    """
    if hasattr(orden, 'cotizacion'):
        messages.warning(
            request,
            '⚠️ Esta orden ya tiene una cotización. Puedes agregar piezas o editar la mano de obra.'
        )
        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

    # Si el usuario envió un valor de MO en el mismo POST, lo guardamos
    # en la orden antes de crear la cotización (opcional, por comodidad).
    from servicio_tecnico.utils_gama import (
        aplicar_gama_por_mano_obra,
        etiqueta_gama,
    )

    costo_mo_post = request.POST.get('costo_mano_obra', '').strip()
    if costo_mo_post:
        form_mo_previo = GuardarManoObraForm(request.POST, instance=orden)
        if form_mo_previo.is_valid():
            orden = form_mo_previo.save()
        else:
            messages.error(request, '❌ Valor de mano de obra inválido. No se generó la cotización.')
            return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

    # Cascada: si hay MO > 0 (recién enviada o ya en la orden), actualizar gama
    gama_antes = getattr(
        getattr(orden, 'detalle_equipo', None), 'gama', None
    )
    gama_aplicada = aplicar_gama_por_mano_obra(
        orden,
        orden.costo_mano_obra,
        usuario=empleado_actual,
    )

    # Crear Cotizacion copiando la MO ya registrada en la orden
    cotizacion = Cotizacion.objects.create(
        orden=orden,
        costo_mano_obra=orden.costo_mano_obra or Decimal('0.00'),
    )

    msg_cot = (
        f'✅ Cotización generada con mano de obra: ${cotizacion.costo_mano_obra}. '
        f'Ahora puedes agregar piezas. El estado de la orden no se cambió automáticamente.'
    )
    if gama_aplicada:
        msg_cot += (
            f' Gama actualizada: {etiqueta_gama(gama_antes)} → '
            f'{etiqueta_gama(gama_aplicada)} (según costo).'
        )
    messages.success(request, msg_cot)
    HistorialOrden.objects.create(
        orden=orden,
        tipo_evento='cotizacion',
        comentario=(
            f'Cotización generada - Mano de obra copiada de la orden: '
            f'${cotizacion.costo_mano_obra} (sin cambio automático de estado)'
        ),
        usuario=empleado_actual,
        es_sistema=False,
    )
    return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

def handle_editar_fecha_envio(request, orden, empleado_actual):
    """
    Handler POST form_type in ('editar_fecha_envio').

    Args:
        request: HttpRequest Django.
        orden: OrdenServicio ya cargada.
        empleado_actual: Empleado del usuario o None.

    Returns:
        HttpResponse si el flujo terminó (redirect/JSON); None para
        continuar al render GET (form inválido con messages).
    """
    if not hasattr(orden, 'cotizacion'):
        messages.error(request, '❌ No existe una cotización para esta orden.')
        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

    fecha_envio_str = request.POST.get('fecha_envio', '').strip()
    if fecha_envio_str:
        try:
            from datetime import datetime as dt
            nueva_fecha = dt.strptime(fecha_envio_str, '%Y-%m-%dT%H:%M')
            from django.utils import timezone
            if timezone.is_naive(nueva_fecha):
                nueva_fecha = timezone.make_aware(nueva_fecha)

            cotizacion = orden.cotizacion
            fecha_anterior = cotizacion.fecha_envio
            cotizacion.fecha_envio = nueva_fecha
            cotizacion.save(update_fields=['fecha_envio'])

            messages.success(request, f'✅ Fecha de envío actualizada a: {nueva_fecha.strftime("%d/%m/%Y %H:%M")}')

            HistorialOrden.objects.create(
                orden=orden,
                tipo_evento='cotizacion',
                comentario=f'Fecha de envío de cotización editada: {fecha_anterior.strftime("%d/%m/%Y %H:%M") if fecha_anterior else "N/A"} → {nueva_fecha.strftime("%d/%m/%Y %H:%M")}',
                usuario=empleado_actual,
                es_sistema=False
            )
        except (ValueError, TypeError) as e:
            messages.error(request, f'❌ Formato de fecha inválido: {str(e)}')
    else:
        messages.error(request, '❌ No se proporcionó una fecha válida.')

    return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)


def handle_editar_mano_obra(request, orden, empleado_actual):
    """
    Handler POST form_type in ('editar_mano_obra').

    Args:
        request: HttpRequest Django.
        orden: OrdenServicio ya cargada.
        empleado_actual: Empleado del usuario o None.

    Returns:
        HttpResponse si el flujo terminó (redirect/JSON); None para
        continuar al render GET (form inválido con messages).
    """
    if not hasattr(orden, 'cotizacion'):
        messages.error(request, '❌ No existe una cotización para esta orden.')
        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

    costo_mano_obra_str = request.POST.get('costo_mano_obra', '').strip()
    if costo_mano_obra_str:
        try:
            from decimal import Decimal, InvalidOperation
            nuevo_costo = Decimal(costo_mano_obra_str)
            if nuevo_costo < 0:
                messages.error(request, '❌ El costo de mano de obra no puede ser negativo.')
                return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

            cotizacion = orden.cotizacion
            costo_anterior = cotizacion.costo_mano_obra
            gama_antes = getattr(
                getattr(orden, 'detalle_equipo', None), 'gama', None
            )
            # Sincronizar ambos: cotización y orden (fuente de verdad de la MO)
            cotizacion.costo_mano_obra = nuevo_costo
            cotizacion.save(update_fields=['costo_mano_obra'])
            orden.costo_mano_obra = nuevo_costo
            orden.save(update_fields=['costo_mano_obra'])

            # Cascada: MO redefine la gama del equipo
            from servicio_tecnico.utils_gama import (
                aplicar_gama_por_mano_obra,
                etiqueta_gama,
            )
            gama_aplicada = aplicar_gama_por_mano_obra(
                orden,
                nuevo_costo,
                usuario=empleado_actual,
            )

            msg_edit = (
                f'✅ Mano de obra actualizada: ${costo_anterior} → ${nuevo_costo}'
            )
            if gama_aplicada:
                msg_edit += (
                    f'. Gama actualizada: {etiqueta_gama(gama_antes)} → '
                    f'{etiqueta_gama(gama_aplicada)} (según costo).'
                )
            messages.success(request, msg_edit)

            HistorialOrden.objects.create(
                orden=orden,
                tipo_evento='cotizacion',
                comentario=f'Costo de mano de obra editado: ${costo_anterior} → ${nuevo_costo}',
                usuario=empleado_actual,
                es_sistema=False
            )
        except (InvalidOperation, ValueError, TypeError) as e:
            messages.error(request, f'❌ Valor de mano de obra inválido: {str(e)}')
    else:
        messages.error(request, '❌ No se proporcionó un valor válido para mano de obra.')

    return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)


def handle_gestionar_cotizacion(request, orden, empleado_actual):
    """
    Handler POST form_type in ('gestionar_cotizacion').

    Args:
        request: HttpRequest Django.
        orden: OrdenServicio ya cargada.
        empleado_actual: Empleado del usuario o None.

    Returns:
        HttpResponse si el flujo terminó (redirect/JSON); None para
        continuar al render GET (form inválido con messages).
    """
    # Verificar que existe cotización
    if not hasattr(orden, 'cotizacion'):
        messages.error(request, '❌ No existe una cotización para esta orden.')
        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

    form_gestionar_cotizacion = GestionarCotizacionForm(
        request.POST,
        instance=orden.cotizacion
    )

    if form_gestionar_cotizacion.is_valid():
        accion = form_gestionar_cotizacion.cleaned_data.get('accion')

        # NUEVO: Obtener las piezas seleccionadas desde el POST
        piezas_seleccionadas_ids = request.POST.getlist('piezas_seleccionadas')

        # Guardar la cotización
        cotizacion_actualizada = form_gestionar_cotizacion.save()

        # NUEVO: Actualizar el estado de cada pieza según la decisión
        todas_las_piezas = cotizacion_actualizada.piezas_cotizadas.all()
        piezas_aceptadas_count = 0
        piezas_rechazadas_count = 0

        if accion == 'aceptar':
            # Si acepta, actualizar cada pieza según si fue seleccionada
            # NOTA: Solo procesar piezas si existen en la cotización
            if todas_las_piezas.exists():
                for pieza in todas_las_piezas:
                    if str(pieza.id) in piezas_seleccionadas_ids:
                        pieza.aceptada_por_cliente = True
                        piezas_aceptadas_count += 1
                    else:
                        pieza.aceptada_por_cliente = False
                        pieza.motivo_rechazo_pieza = 'Cliente decidió no incluir esta pieza'
                        piezas_rechazadas_count += 1
                    pieza.save()

                # ============================================================
                # ✨ NUEVO: CREACIÓN AUTOMÁTICA DE SEGUIMIENTOS (Nov 2025)
                # ============================================================
                # Después de marcar las piezas como aceptadas, crear automáticamente
                # los registros de SeguimientoPieza agrupados por proveedor
                # para facilitar el tracking de pedidos.

                from .models import SeguimientoPieza
                from collections import defaultdict
                from datetime import date, timedelta

                # Obtener solo las piezas aceptadas que tienen proveedor
                piezas_aceptadas_con_proveedor = todas_las_piezas.filter(
                    aceptada_por_cliente=True
                ).exclude(proveedor='').exclude(proveedor__isnull=True)

                if piezas_aceptadas_con_proveedor.exists():
                    # Agrupar piezas por proveedor
                    piezas_por_proveedor = defaultdict(list)
                    for pieza in piezas_aceptadas_con_proveedor:
                        piezas_por_proveedor[pieza.proveedor].append(pieza)

                    # Crear un SeguimientoPieza por cada proveedor
                    seguimientos_creados = 0
                    for proveedor, piezas_grupo in piezas_por_proveedor.items():
                        # EXPLICACIÓN PARA PRINCIPIANTES:
                        # Solo nombre y cantidad: el costo vive en la cotización,
                        # no en el texto del seguimiento de pedido.
                        descripcion_piezas = '\n'.join([
                            f"• {pieza.componente.nombre} × {pieza.cantidad}"
                            for pieza in piezas_grupo
                        ])

                        # Crear el seguimiento (orden = ancla; cotizacion = OOW)
                        seguimiento = SeguimientoPieza.objects.create(
                            orden=orden,
                            cotizacion=cotizacion_actualizada,
                            proveedor=proveedor,
                            descripcion_piezas=descripcion_piezas,
                            fecha_pedido=date.today(),
                            fecha_entrega_estimada=date.today() + timedelta(days=7),  # 7 días por defecto
                            estado='pedido',
                            notas_seguimiento=f'Seguimiento creado automáticamente al aceptar cotización'
                        )

                        # Asociar las piezas al seguimiento
                        seguimiento.piezas.set(piezas_grupo)
                        seguimientos_creados += 1

                    # Notificar al usuario que se crearon seguimientos
                    if seguimientos_creados > 0:
                        messages.info(
                            request,
                            f'📦 Se crearon automáticamente {seguimientos_creados} registro(s) de seguimiento '
                            f'de piezas agrupados por proveedor. Puedes editarlos para agregar número de pedido '
                            f'y ajustar fechas.'
                        )

                        # Registrar en historial
                        HistorialOrden.objects.create(
                            orden=orden,
                            tipo_evento='cotizacion',
                            comentario=f'📦 Sistema creó automáticamente {seguimientos_creados} seguimiento(s) de piezas agrupados por proveedor',
                            usuario=empleado_actual,
                            es_sistema=True
                        )
                # Fin de creación automática de seguimientos
                # ============================================================
        elif accion == 'rechazar':
            # Si rechaza toda la cotización, todas las piezas se rechazan
            for pieza in todas_las_piezas:
                pieza.aceptada_por_cliente = False
                pieza.motivo_rechazo_pieza = cotizacion_actualizada.get_motivo_rechazo_display()
                pieza.save()
                piezas_rechazadas_count += 1

        # Mensaje según la decisión
        if accion == 'aceptar':
            # Obtener información del descuento
            se_aplico_descuento = cotizacion_actualizada.descontar_mano_obra

            # Construir mensaje según si hay piezas o solo mano de obra
            if todas_las_piezas.exists():
                mensaje_piezas = f'{piezas_aceptadas_count} pieza(s) aceptada(s)'
                if piezas_rechazadas_count > 0:
                    mensaje_piezas += f' y {piezas_rechazadas_count} pieza(s) rechazada(s)'

                # Agregar información de descuento si aplica
                if se_aplico_descuento:
                    mensaje_completo = f'✅ Cotización ACEPTADA por el cliente ({mensaje_piezas}). 🎁 Mano de obra DESCONTADA como beneficio (ahorro: ${cotizacion_actualizada.costo_mano_obra}).'
                else:
                    mensaje_completo = f'✅ Cotización ACEPTADA por el cliente ({mensaje_piezas}). Continúa con la reparación.'
            else:
                # Solo hay mano de obra
                if se_aplico_descuento:
                    mensaje_completo = f'✅ Cotización ACEPTADA por el cliente (Solo mano de obra). 🎁 Diagnóstico GRATUITO como beneficio (ahorro: ${cotizacion_actualizada.costo_mano_obra}).'
                else:
                    mensaje_completo = f'✅ Cotización ACEPTADA por el cliente (Solo mano de obra: ${cotizacion_actualizada.costo_mano_obra}). Continúa con la reparación.'

            messages.success(request, mensaje_completo)

            # 🆕 ACTUALIZACIÓN (Oct 2025): Cambiar estado a "Cliente Acepta Cotización"
            # Independientemente de si hay piezas pendientes o no, el flujo ahora
            # requiere que primero pase por este estado antes de ir a reparación
            nuevo_estado = 'cliente_acepta_cotizacion'
            mensaje_estado = 'Cliente Acepta Cotización'

            if orden.estado != nuevo_estado:
                estado_anterior = orden.estado
                orden.estado = nuevo_estado
                orden.save()

                messages.info(
                    request,
                    f'ℹ️ Estado actualizado automáticamente a: {mensaje_estado}'
                )

                HistorialOrden.objects.create(
                    orden=orden,
                    tipo_evento='cambio_estado',
                    estado_anterior=estado_anterior,
                    estado_nuevo=nuevo_estado,
                    comentario=f'Cambio automático: cotización aceptada por el cliente',
                    usuario=empleado_actual,
                    es_sistema=True
                )

            # Registrar en historial con detalle
            if todas_las_piezas.exists():
                # Construir comentario con información de descuento
                if cotizacion_actualizada.descontar_mano_obra:
                    comentario_historial = (
                        f'✅ Cliente ACEPTÓ la cotización - {piezas_aceptadas_count} pieza(s) aceptada(s)\n'
                        f'   💰 Piezas: ${cotizacion_actualizada.costo_piezas_aceptadas}\n'
                        f'   🎁 Mano de obra DESCONTADA: ${cotizacion_actualizada.costo_mano_obra} (GRATIS)\n'
                        f'   📊 Total a pagar: ${cotizacion_actualizada.costo_total_final} (ahorro de ${cotizacion_actualizada.monto_descuento_mano_obra})'
                    )
                else:
                    comentario_historial = (
                        f'✅ Cliente ACEPTÓ la cotización - {piezas_aceptadas_count} pieza(s) aceptada(s)\n'
                        f'   💰 Total: ${cotizacion_actualizada.costo_piezas_aceptadas + cotizacion_actualizada.costo_mano_obra}'
                    )
            else:
                # Solo mano de obra
                if cotizacion_actualizada.descontar_mano_obra:
                    comentario_historial = (
                        f'✅ Cliente ACEPTÓ la cotización - Solo mano de obra\n'
                        f'   🎁 Diagnóstico GRATUITO como beneficio (ahorro: ${cotizacion_actualizada.costo_mano_obra})\n'
                        f'   📊 Total a pagar: $0.00'
                    )
                else:
                    comentario_historial = f'Cliente ACEPTÓ la cotización - Solo mano de obra - Total: ${cotizacion_actualizada.costo_mano_obra}'

            HistorialOrden.objects.create(
                orden=orden,
                tipo_evento='cotizacion',
                comentario=comentario_historial,
                usuario=empleado_actual,
                es_sistema=False
            )

        elif accion == 'rechazar':
            motivo = cotizacion_actualizada.get_motivo_rechazo_display()
            motivo_clave = cotizacion_actualizada.motivo_rechazo
            detalle_rechazo = cotizacion_actualizada.detalle_rechazo

            messages.warning(
                request,
                f'⚠️ Cotización RECHAZADA por el cliente. Motivo: {motivo} ({piezas_rechazadas_count} pieza(s) rechazada(s))'
            )

            # Cambiar estado a "Cotización Rechazada"
            if orden.estado != 'rechazada':
                estado_anterior = orden.estado
                orden.estado = 'rechazada'
                orden.save()

                messages.info(
                    request,
                    'ℹ️ Estado actualizado automáticamente a: Cotización Rechazada'
                )

                HistorialOrden.objects.create(
                    orden=orden,
                    tipo_evento='cambio_estado',
                    estado_anterior=estado_anterior,
                    estado_nuevo='rechazada',
                    comentario=f'Cambio automático: cotización rechazada',
                    usuario=empleado_actual,
                    es_sistema=True
                )

            # Registrar en historial
            comentario_historial = f'Cliente RECHAZÓ la cotización - Motivo: {motivo} ({piezas_rechazadas_count} pieza(s) rechazada(s))'
            if detalle_rechazo:
                comentario_historial += f' | Detalle: {detalle_rechazo}'

            HistorialOrden.objects.create(
                orden=orden,
                tipo_evento='cotizacion',
                comentario=comentario_historial,
                usuario=empleado_actual,
                es_sistema=False
            )

            # ── SISTEMA DE FEEDBACK DE RECHAZO ──────────────────────────
            # Sets centralizados en config.constants (paridad Almacén/ST)
            from config.constants import (
                MOTIVOS_RECHAZO_CON_FEEDBACK,
                MOTIVOS_RECHAZO_VIGENCIA_VENCIDA,
            )

            email_cliente_actual = (
                orden.detalle_equipo.email_cliente
                if orden.detalle_equipo else None
            )

            if motivo_clave in MOTIVOS_RECHAZO_CON_FEEDBACK and email_cliente_actual:
                # Crear token de feedback usando django.core.signing
                from django.core.signing import TimestampSigner
                from .models import FeedbackCliente
                import uuid

                signer = TimestampSigner()
                # El token es la firma de un UUID único
                token_raw = str(uuid.uuid4())
                token_firmado = signer.sign(token_raw)

                feedback_obj = FeedbackCliente.objects.create(
                    orden=cotizacion_actualizada.orden,
                    cotizacion=cotizacion_actualizada,
                    token=token_firmado,
                    tipo='rechazo',
                    motivo_rechazo_snapshot=motivo_clave,
                    enviado_por=empleado_actual,
                )
                # Guardar feedback_id en sesión para que el modal en detalle_orden lo lea
                request.session['feedback_pendiente_id'] = feedback_obj.pk
                request.session['feedback_pendiente_email'] = email_cliente_actual

            elif motivo_clave in MOTIVOS_RECHAZO_VIGENCIA_VENCIDA and email_cliente_actual:
                # Marcar en sesión que se debe enviar correo de vigencia vencida
                request.session['vigencia_vencida_orden_id'] = orden.pk
                request.session['vigencia_vencida_email'] = email_cliente_actual
            # ────────────────────────────────────────────────────────────

        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
    else:
        messages.error(request, '❌ Error al procesar la decisión de cotización.')

