"""
Handlers POST de detalle_orden: estado, config, responsables, comentarios.

EXPLICACIÓN PARA PRINCIPIANTES (Fase C):
Salieron de views_detalle_orden.py. La vista solo despacha según form_type.
urls.py no cambia. Misma lógica de negocio.
"""

from django.contrib import messages
from django.shortcuts import redirect

from .forms import (
    AsignarResponsablesForm,
    CambioEstadoForm,
    ComentarioForm,
    ConfiguracionAdicionalForm,
    EditarInformacionEquipoForm,
    ReingresoRHITSOForm,
)
from .models import EstadoRHITSO, HistorialOrden
from .services.cierre_diagnostico import (
    aplicar_fecha_fin_al_guardar_diagnostico_sic,
)
from .services.historial import registrar_historial


def handle_configuracion(request, orden, empleado_actual):
    """
    Handler POST form_type in ('configuracion').

    Args:
        request: HttpRequest Django.
        orden: OrdenServicio ya cargada.
        empleado_actual: Empleado del usuario o None.

    Returns:
        HttpResponse si el flujo terminó (redirect/JSON); None para
        continuar al render GET (form inválido con messages).
    """
    # Obtener el valor ANTES de crear el formulario
    # Hacemos una consulta directa a la BD para tener el valor real
    from .models import DetalleEquipo
    detalle_bd = DetalleEquipo.objects.get(pk=orden.detalle_equipo.pk)
    fecha_fin_anterior = detalle_bd.fecha_fin_diagnostico
    diagnostico_sic_anterior = detalle_bd.diagnostico_sic or ''

    form_config = ConfiguracionAdicionalForm(
        request.POST,
        instance=orden.detalle_equipo
    )

    if form_config.is_valid():
        # ===============================================================
        # Guardar configuración adicional
        # ===============================================================
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # El texto del diagnóstico (diagnostico_sic) se guarda tal cual
        # lo escribió el técnico, sin modificaciones. La detección de
        # piezas y números de parte la hace el TypeScript en el navegador
        # cuando el usuario da clic en "Detectar Piezas" en el modal.
        detalle_actualizado = form_config.save()

        # ===================================================================
        # Fin diagnóstico + Equipo Diagnosticado (helper compartido)
        # ===================================================================
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Si hay Diagnóstico SIC y la fecha de fin estaba vacía, el helper
        # la llena con hoy. Si la fecha de fin aparece por primera vez
        # (auto o a mano), también pasa el estado a Equipo Diagnosticado.
        resultado_cierre = aplicar_fecha_fin_al_guardar_diagnostico_sic(
            detalle_actualizado,
            orden,
            empleado_actual,
            fecha_fin_anterior=fecha_fin_anterior,
            diagnostico_sic_anterior=diagnostico_sic_anterior,
        )

        if resultado_cierre['estado_cambiado']:
            messages.info(
                request,
                'Estado actualizado automáticamente a: "Equipo Diagnosticado"',
            )
        # ===================================================================

        messages.success(request, '✅ Configuración actualizada correctamente.')

        # Registrar en historial
        HistorialOrden.objects.create(
            orden=orden,
            tipo_evento='actualizacion',
            comentario='Configuración adicional actualizada (diagnóstico, fechas)',
            usuario=empleado_actual,
            es_sistema=False
        )

        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
    else:
        messages.error(request, '❌ Error al actualizar la configuración.')


def handle_reingreso_rhitso(request, orden, empleado_actual):
    """
    Handler POST form_type in ('reingreso_rhitso').

    Args:
        request: HttpRequest Django.
        orden: OrdenServicio ya cargada.
        empleado_actual: Empleado del usuario o None.

    Returns:
        HttpResponse si el flujo terminó (redirect/JSON); None para
        continuar al render GET (form inválido con messages).
    """
    form_reingreso = ReingresoRHITSOForm(request.POST, instance=orden)

    if form_reingreso.is_valid():
        orden_actualizada = form_reingreso.save(commit=False)

        # ===================================================================
        # ASIGNAR ESTADO RHITSO AUTOMÁTICO SI ES CANDIDATO
        # ===================================================================
        # EXPLICACIÓN: Si se marca como candidato RHITSO y NO tiene estado
        # asignado, le ponemos automáticamente el primer estado
        if orden_actualizada.es_candidato_rhitso and not orden_actualizada.estado_rhitso:
            try:
                primer_estado = EstadoRHITSO.objects.filter(orden=1).first()
                if primer_estado:
                    orden_actualizada.estado_rhitso = primer_estado.estado
                    messages.info(
                        request,
                        f'🎯 Estado RHITSO asignado automáticamente: {primer_estado.estado}'
                    )
            except EstadoRHITSO.DoesNotExist:
                pass  # Si no hay estados, continuar sin asignar

        # Guardar la orden con el estado asignado
        orden_actualizada.save()

        # Si se marcó como reingreso, crear incidencia de ScoreCard
        if orden_actualizada.es_reingreso and not orden_actualizada.incidencia_scorecard:
            incidencia = orden_actualizada.crear_incidencia_reingreso(usuario=empleado_actual)
            if incidencia:
                messages.success(
                    request,
                    f'✅ Orden marcada como reingreso. Incidencia creada: {incidencia.folio}'
                )
            else:
                messages.warning(
                    request,
                    '⚠️ Orden marcada como reingreso, pero no se pudo crear la incidencia de ScoreCard '
                    'porque no hay inspector de calidad ni técnico asignado. Asigna un responsable y vuelve a guardar.'
                )

        messages.success(request, '✅ Información de reingreso/RHITSO actualizada.')

        # Registrar en historial
        comentario_historial = []
        if orden_actualizada.es_reingreso:
            comentario_historial.append('Marcada como REINGRESO')
        if orden_actualizada.es_candidato_rhitso:
            comentario_historial.append(f'Candidato a RHITSO: {orden_actualizada.get_motivo_rhitso_display()}')

        if comentario_historial:
            HistorialOrden.objects.create(
                orden=orden,
                tipo_evento='actualizacion',
                comentario=' | '.join(comentario_historial),
                usuario=empleado_actual,
                es_sistema=False
            )

        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
    else:
        messages.error(request, '❌ Error al actualizar reingreso/RHITSO.')


def handle_cambio_estado(request, orden, empleado_actual):
    """
    Handler POST form_type in ('cambio_estado').

    Args:
        request: HttpRequest Django.
        orden: OrdenServicio ya cargada.
        empleado_actual: Empleado del usuario o None.

    Returns:
        HttpResponse si el flujo terminó (redirect/JSON); None para
        continuar al render GET (form inválido con messages).
    """
    form_estado = CambioEstadoForm(request.POST, instance=orden)

    if form_estado.is_valid():
        estado_anterior = orden.estado

        # El formulario maneja automáticamente las fechas en su método save()
        orden_actualizada = form_estado.save()

        # Agregar comentario adicional si existe
        comentario_cambio = form_estado.cleaned_data.get('comentario_cambio', '')
        if comentario_cambio:
            HistorialOrden.objects.create(
                orden=orden,
                tipo_evento='comentario',
                comentario=f'[Cambio de estado] {comentario_cambio}',
                usuario=empleado_actual,
                es_sistema=False
            )

        messages.success(
            request,
            f'✅ Estado cambiado a: {orden_actualizada.get_estado_display()}'
        )

        # Inicio de reparación si el hito es Piezas Recibidas o En Reparación
        # y la fecha todavía está vacía (no pisa una fecha previa).
        if orden_actualizada.estado in ('piezas_recibidas', 'reparacion'):
            from servicio_tecnico.services.fechas_reparacion import (
                aplicar_inicio_reparacion_si_vacia,
            )
            etiqueta = orden_actualizada.get_estado_display()
            aplicar_inicio_reparacion_si_vacia(
                orden_actualizada,
                empleado_actual,
                motivo=f'cambio de estado a {etiqueta}',
            )

        # Alerta de cobro (no bloquea): 50% al iniciar / 100% al entregar.
        from servicio_tecnico.services.pagos_orden import (
            mensaje_alerta_pago_por_estado,
        )
        alerta_pago = mensaje_alerta_pago_por_estado(
            orden_actualizada,
            orden_actualizada.estado,
        )
        if alerta_pago:
            messages.warning(request, alerta_pago)

        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
    else:
        # DEPURACIÓN: Mostrar errores específicos del formulario
        errores_detallados = []
        for campo, errores in form_estado.errors.items():
            for error in errores:
                errores_detallados.append(f"{campo}: {error}")

        if errores_detallados:
            messages.error(
                request, 
                f'❌ Error al cambiar el estado: {" | ".join(errores_detallados)}'
            )
        else:
            messages.error(request, '❌ Error al cambiar el estado.')


def handle_asignar_responsables(request, orden, empleado_actual):
    """
    Handler POST form_type in ('asignar_responsables').

    Args:
        request: HttpRequest Django.
        orden: OrdenServicio ya cargada.
        empleado_actual: Empleado del usuario o None.

    Returns:
        HttpResponse si el flujo terminó (redirect/JSON); None para
        continuar al render GET (form inválido con messages).
    """
    # IMPORTANTE: Refrescar el objeto desde la base de datos PRIMERO
    # Esto previene que se use una versión en caché del objeto
    orden.refresh_from_db()

    # Guardar los valores actuales DESPUÉS del refresh
    tecnico_anterior_id = orden.tecnico_asignado_actual.id if orden.tecnico_asignado_actual else None
    responsable_anterior_id = orden.responsable_seguimiento.id if orden.responsable_seguimiento else None
    tecnico_anterior_obj = orden.tecnico_asignado_actual
    responsable_anterior_obj = orden.responsable_seguimiento

    form_responsables = AsignarResponsablesForm(request.POST, instance=orden)

    if form_responsables.is_valid():
        # Obtener los NUEVOS valores del formulario sin guardar
        orden_actualizada = form_responsables.save(commit=False)
        tecnico_nuevo_id = orden_actualizada.tecnico_asignado_actual.id if orden_actualizada.tecnico_asignado_actual else None
        responsable_nuevo_id = orden_actualizada.responsable_seguimiento.id if orden_actualizada.responsable_seguimiento else None

        # Guardar SOLO los campos del formulario para evitar triggers del modelo
        # Esto previene que el método save() del modelo registre el cambio automáticamente
        orden_actualizada.save(update_fields=['tecnico_asignado_actual', 'responsable_seguimiento'])

        # Ahora registramos los cambios MANUALMENTE en el historial
        cambios = []

        # Cambio de técnico
        if tecnico_anterior_id != tecnico_nuevo_id:
            cambios.append(
                f'Técnico: {tecnico_anterior_obj.nombre_completo if tecnico_anterior_obj else "Sin asignar"} → {orden_actualizada.tecnico_asignado_actual.nombre_completo if orden_actualizada.tecnico_asignado_actual else "Sin asignar"}'
            )
            HistorialOrden.objects.create(
                orden=orden,
                tipo_evento='cambio_tecnico',
                comentario=f'Técnico reasignado de {tecnico_anterior_obj.nombre_completo if tecnico_anterior_obj else "Sin asignar"} a {orden_actualizada.tecnico_asignado_actual.nombre_completo if orden_actualizada.tecnico_asignado_actual else "Sin asignar"}',
                usuario=empleado_actual,
                tecnico_anterior=tecnico_anterior_obj,
                tecnico_nuevo=orden_actualizada.tecnico_asignado_actual,
                es_sistema=False
            )

        # Cambio de responsable
        if responsable_anterior_id != responsable_nuevo_id:
            cambios.append(
                f'Responsable: {responsable_anterior_obj.nombre_completo if responsable_anterior_obj else "Sin asignar"} → {orden_actualizada.responsable_seguimiento.nombre_completo if orden_actualizada.responsable_seguimiento else "Sin asignar"}'
            )
            HistorialOrden.objects.create(
                orden=orden,
                tipo_evento='actualizacion',
                comentario=f'Responsable de seguimiento cambiado de {responsable_anterior_obj.nombre_completo if responsable_anterior_obj else "Sin asignar"} a {orden_actualizada.responsable_seguimiento.nombre_completo if orden_actualizada.responsable_seguimiento else "Sin asignar"}',
                usuario=empleado_actual,
                es_sistema=False
            )

        if cambios:
            messages.success(
                request,
                f'[OK] Responsables actualizados: {" | ".join(cambios)}'
            )
        else:
            messages.info(request, 'ℹ️ No se realizaron cambios en los responsables.')

        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
    else:
        messages.error(request, '❌ Error al asignar responsables.')


def handle_comentario(request, orden, empleado_actual):
    """
    Handler POST form_type in ('comentario').

    Args:
        request: HttpRequest Django.
        orden: OrdenServicio ya cargada.
        empleado_actual: Empleado del usuario o None.

    Returns:
        HttpResponse si el flujo terminó (redirect/JSON); None para
        continuar al render GET (form inválido con messages).
    """
    form_comentario = ComentarioForm(request.POST)

    if form_comentario.is_valid():
        form_comentario.save(orden=orden, usuario=empleado_actual)
        messages.success(request, '✅ Comentario agregado correctamente.')
        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
    else:
        messages.error(request, '❌ Error al agregar el comentario.')


def handle_editar_info_equipo(request, orden, empleado_actual):
    """
    Handler POST form_type in ('editar_info_equipo').

    Args:
        request: HttpRequest Django.
        orden: OrdenServicio ya cargada.
        empleado_actual: Empleado del usuario o None.

    Returns:
        HttpResponse si el flujo terminó (redirect/JSON); None para
        continuar al render GET (form inválido con messages).
    """
    # Capturar el email actual ANTES de guardar el formulario,
    # para poder detectar si cambió después de guardar.
    email_anterior = (
        orden.detalle_equipo.email_cliente
        if orden.detalle_equipo and orden.detalle_equipo.email_cliente
        else None
    )

    form_editar_info = EditarInformacionEquipoForm(
        request.POST,
        instance=orden.detalle_equipo
    )

    if form_editar_info.is_valid():
        detalle_actualizado = form_editar_info.save()
        messages.success(request, '✅ Información del equipo actualizada correctamente.')

        # Registrar en historial
        HistorialOrden.objects.create(
            orden=orden,
            tipo_evento='actualizacion',
            comentario='Información principal del equipo actualizada (marca, modelo, número de serie, etc.)',
            usuario=empleado_actual,
            es_sistema=False
        )

        # ── Reenviar enlace de seguimiento si el email cambió ──────────
        # Solo aplica a órdenes fuera de garantía que ya tienen enlace.
        # Lógica:
        #   1. Si el correo nunca se envió y hay email nuevo → enviar.
        #   2. Si el correo ya se envió, extraemos a qué dirección
        #      se envió del historial. Si el email nuevo es diferente
        #      → resetear correo_enviado y reenviar al nuevo destino.
        try:
            if orden.es_fuera_garantia:
                email_nuevo = detalle_actualizado.email_cliente or ''
                if email_nuevo:
                    from .models import EnlaceSeguimientoCliente
                    enlace_qs = EnlaceSeguimientoCliente.objects.filter(orden=orden)
                    enlace_obj = enlace_qs.first()

                    debe_enviar = False

                    if enlace_obj is None or not enlace_obj.correo_enviado:
                        # Caso 1: nunca se envió (o no existe enlace aún)
                        debe_enviar = True
                    else:
                        # Caso 2: ya se envió — buscar el email destino en historial
                        import re as _re
                        historial_envio = HistorialOrden.objects.filter(
                            orden=orden,
                            tipo_evento='email',
                            comentario__icontains='Enlace de seguimiento público enviado',
                        ).order_by('fecha_evento').first()

                        email_enviado_previo = None
                        if historial_envio:
                            _match = _re.search(
                                r'enviado al cliente \((.+?)\)',
                                historial_envio.comentario,
                            )
                            if _match:
                                email_enviado_previo = _match.group(1).strip().lower()

                        if email_enviado_previo and email_nuevo.lower() != email_enviado_previo:
                            # El email cambió respecto al que ya recibió el link
                            EnlaceSeguimientoCliente.objects.filter(orden=orden).update(
                                correo_enviado=False
                            )
                            debe_enviar = True

                    if debe_enviar:
                        from .tasks import enviar_seguimiento_cliente_task
                        from config.paises_config import get_pais_actual
                        enviar_seguimiento_cliente_task.delay(
                            orden_id=orden.id,
                            usuario_id=request.user.id,
                            db_alias=get_pais_actual()['db_alias'],
                        )
                        messages.info(
                            request,
                            f'📧 Enlace de seguimiento enviado a {email_nuevo}.'
                        )
        except Exception:
            pass  # No bloquear la actualización si falla el reenvío

        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)
    else:
        messages.error(request, '❌ Error al actualizar la información del equipo.')

