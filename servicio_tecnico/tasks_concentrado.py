"""
Tarea Celery: enviar el concentrado semanal por correo.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Armar el Excel y el PDF tarda. Si la página lo hiciera en el momento
de apretar «Enviar», el navegador se quedaría esperando. Por eso la
vista solo encola esta tarea y el worker la corre después.

Celery no pasa por el middleware de país. La firma lleva db_alias
para que las órdenes se lean de la base correcta.

Esta tarea se reexporta al FINAL de tasks.py para que el worker la vea.
"""

from __future__ import annotations

import io
import logging
from datetime import date, timedelta

from celery import shared_task

logger = logging.getLogger('servicio_tecnico')


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='servicio_tecnico.enviar_concentrado_semanal',
)
def enviar_concentrado_semanal_task(
    self,
    lunes_iso,
    destinatarios,
    sucursal_id=None,
    sucursal_ids=None,
    alcance='Todas las sucursales',
    db_alias='default',
):
    """
    Genera Excel y PDF de la semana y los manda a los contactos elegidos.

    Objetivo de negocio:
        El correo que confirma el modal debe traer los mismos archivos
        que los botones de descarga, más el resumen de la semana.

    Args:
        lunes_iso (str): Lunes de la semana, formato AAAA-MM-DD.
        destinatarios (list[str]): Correos ya validados por la vista.
        sucursal_id (int | None): Una sucursal, o None.
        sucursal_ids (list[int] | None): Grupo CIS o foráneas.
        alcance (str): Texto que dice qué sucursales cubre el corte.
        db_alias (str): País de la base. El worker lo lee antes de entrar.

    Returns:
        dict con success y la cantidad de correos (0 o 1).

    Efectos secundarios:
        Lee órdenes, arma dos archivos en memoria y envía un correo.
        Si el envío falla, reintenta hasta 2 veces.
    """
    from django.utils import timezone

    from servicio_tecnico.concentrado_semanal import (
        comparar_concentrado_con_semana_anterior,
        cortes_excel_concentrado,
        nombre_archivo_concentrado,
        obtener_concentrado_semanal,
    )
    from servicio_tecnico.excel_exporters_concentrado import generar_excel_concentrado
    from servicio_tecnico.pdf_concentrado import generar_pdf_concentrado
    from servicio_tecnico.services.concentrado_correo import (
        enviar_correo_concentrado,
        signo_variacion,
    )

    logger.info(
        '[CONCENTRADO] Preparando envío lunes=%s db=%s',
        lunes_iso,
        db_alias,
    )
    if not destinatarios:
        logger.warning('[CONCENTRADO] Sin destinatarios; no se envía.')
        return {'success': False, 'enviados': 0}

    # Una fecha imposible no se arregla reintentando. Se descarta.
    try:
        lunes = date.fromisoformat(lunes_iso)
    except (TypeError, ValueError):
        logger.error('[CONCENTRADO] Fecha inválida: %s', lunes_iso)
        return {'success': False, 'enviados': 0}

    try:
        # Mismos cuatro cortes que el botón de Excel, más la semana previa del PDF.
        cortes = cortes_excel_concentrado(
            lunes,
            sucursal_id=sucursal_id,
            sucursal_ids=sucursal_ids,
        )
        datos = cortes['semana']
        anterior = obtener_concentrado_semanal(
            lunes - timedelta(days=7),
            sucursal_id=sucursal_id,
            sucursal_ids=sucursal_ids,
        )
        comparacion = comparar_concentrado_con_semana_anterior(datos, anterior)

        libro = generar_excel_concentrado(
            datos,
            cortes['trimestral'],
            cortes['tendencia'],
            cortes['mensual'],
        )
        buffer_excel = io.BytesIO()
        libro.save(buffer_excel)
        pdf_buffer = generar_pdf_concentrado(datos, anterior)

        contexto = {
            'numero_semana': datos['numero_semana'],
            'año': datos['año'],
            'lunes': datos['lunes'].strftime('%d/%m/%Y'),
            'viernes': datos['viernes'].strftime('%d/%m/%Y'),
            'alcance': alcance,
            'ingresaron': comparacion['ingresaron'],
            'salieron': comparacion['salieron'],
            'balance': signo_variacion(comparacion['balance']),
            'candidatos_rhitso': comparacion['candidatos_rhitso'],
            'variacion_ingresaron': signo_variacion(comparacion['variacion_ingresaron']),
            'variacion_salieron': signo_variacion(comparacion['variacion_salieron']),
            'variacion_balance': signo_variacion(comparacion['variacion_balance']),
            'variacion_rhitso': signo_variacion(comparacion['variacion_rhitso']),
            'ahora_local': timezone.localtime(),
        }
        enviados = enviar_correo_concentrado(
            destinatarios=list(destinatarios),
            contexto=contexto,
            excel_bytes=buffer_excel.getvalue(),
            pdf_bytes=pdf_buffer.getvalue(),
            nombre_excel=nombre_archivo_concentrado(datos, 'xlsx'),
            nombre_pdf=nombre_archivo_concentrado(datos, 'pdf'),
        )
        if not enviados:
            return {'success': False, 'enviados': 0}
        return {'success': True, 'enviados': enviados}
    except Exception as exc:
        logger.error('[CONCENTRADO] Error al enviar: %s', exc, exc_info=True)
        raise self.retry(exc=exc)
