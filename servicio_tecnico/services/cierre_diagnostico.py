"""
Cierre automático del diagnóstico al guardar Diagnóstico SIC.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cuando el técnico guarda un Diagnóstico SIC con texto, el sistema puede:
1) Llenar "Fin Diagnóstico" con la fecha de hoy (si estaba vacío).
2) Pasar la orden a "Equipo Diagnosticado" la primera vez que aparece esa fecha.

Así Configuración, mejora con IA y RHITSO se comportan igual, sin duplicar
reglas en cada vista.
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from servicio_tecnico.services.historial import registrar_historial


def aplicar_fecha_fin_al_guardar_diagnostico_sic(
    detalle: Any,
    orden: Any,
    empleado: Any = None,
    *,
    fecha_fin_anterior: Any = None,
) -> dict[str, Any]:
    """
    Auto-llena fecha_fin_diagnostico y, si es la primera vez, cierra el estado.

    Objetivo de negocio:
        Al guardar Diagnóstico SIC, marcar el fin del diagnóstico sin que el
        técnico tenga que capturar la fecha a mano. Conserva la regla histórica:
        primera vez que existe fecha de fin → estado Equipo Diagnosticado.

    Args:
        detalle: DetalleEquipo ya persistido (con diagnostico_sic actual).
        orden: OrdenServicio asociada.
        empleado: Empleado que guarda, o None si es proceso automático.
        fecha_fin_anterior: Valor de fecha_fin ANTES del guardado del formulario
            (None = no había fecha). Permite detectar "primera vez" aunque el
            técnico la haya puesto a mano en el mismo POST.

    Returns:
        dict con:
            - fecha_fin_aplicada (bool): True si se auto-llenó desde el SIC.
            - estado_cambiado (bool): True si pasó a equipo_diagnosticado.
            - fecha_fin: date | None resultante en el detalle.

    Efectos secundarios:
        Puede actualizar DetalleEquipo.fecha_fin_diagnostico, OrdenServicio.estado
        e insertar filas en HistorialOrden.
    """
    resultado: dict[str, Any] = {
        'fecha_fin_aplicada': False,
        'estado_cambiado': False,
        'fecha_fin': detalle.fecha_fin_diagnostico,
    }

    # EXPLICACIÓN: Venta Mostrador no pasa por el ciclo de diagnóstico clásico.
    if getattr(orden, 'tipo_servicio', None) == 'venta_mostrador':
        return resultado

    diagnostico = (getattr(detalle, 'diagnostico_sic', None) or '').strip()
    fecha_fin_aplicada = False

    # Paso 1: si hay SIC con texto y aún no hay fin → fecha de hoy.
    if diagnostico and detalle.fecha_fin_diagnostico is None:
        fecha_hoy = timezone.localdate()
        detalle.fecha_fin_diagnostico = fecha_hoy
        detalle.save(update_fields=['fecha_fin_diagnostico'])
        fecha_fin_aplicada = True
        resultado['fecha_fin_aplicada'] = True
        resultado['fecha_fin'] = fecha_hoy

        registrar_historial(
            orden=orden,
            tipo_evento='sistema',
            usuario=empleado,
            comentario=(
                'Fin de diagnóstico registrado automáticamente '
                f'({fecha_hoy.strftime("%d/%m/%Y")}) al guardar Diagnóstico SIC'
            ),
            es_sistema=True,
        )

    # Paso 2: primera vez que existe fecha_fin → Equipo Diagnosticado.
    # Aplica tanto si se auto-llenó como si el técnico la puso a mano en el form.
    fecha_fin_actual = detalle.fecha_fin_diagnostico
    resultado['fecha_fin'] = fecha_fin_actual

    if fecha_fin_anterior is None and fecha_fin_actual is not None:
        if orden.estado != 'equipo_diagnosticado':
            estado_anterior = orden.estado
            orden.estado = 'equipo_diagnosticado'
            orden.save(update_fields=['estado'])
            resultado['estado_cambiado'] = True

            etiqueta_anterior = dict(
                orden._meta.get_field('estado').choices
            ).get(estado_anterior, estado_anterior)
            motivo = (
                'Diagnóstico SIC guardado'
                if fecha_fin_aplicada
                else 'Diagnóstico finalizado'
            )
            registrar_historial(
                orden=orden,
                tipo_evento='estado',
                usuario=empleado,
                comentario=(
                    f"Estado cambiado automáticamente: '{etiqueta_anterior}' → "
                    f"'Equipo Diagnosticado' ({motivo})"
                ),
                es_sistema=True,
            )

    return resultado
