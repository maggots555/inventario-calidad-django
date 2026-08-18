"""
Tareas Celery de vigencia de cotización y recotización
=======================================================

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Aquí viven dos tipos de tareas:

1. UNA TAREA PROGRAMADA (Celery Beat) que corre sola cada mañana y revisa qué
   cotizaciones cumplieron sus 5 días hábiles sin respuesta del cliente.

2. TAREAS DISPARADAS POR EL USUARIO cuando presiona "Solicitar Recotización".

MULTI-PAÍS (importante):
El sistema tiene una base de datos por país (México, Argentina, Chile,
Colombia). Los workers de Celery NO pasan por el middleware que detecta el país
a partir del subdominio, así que hay que decirles explícitamente en qué base
trabajar con el parámetro ``db_alias``.

La tarea del Beat no puede recibir un solo ``db_alias`` (debe revisar TODOS los
países), así que hace "fan-out": recorre la lista de países y encola una tarea
hija por cada uno, ya con su ``db_alias``. Así el ORM se enruta solo y no hay
que escribir ``.using()`` en cada consulta.

Este archivo NO se registra solo en Celery: al final de ``almacen/tasks.py``
hay un import que lo trae, porque Celery únicamente autodescubre el módulo
``tasks`` de cada aplicación.

Autor: Sistema Integral de Gestión (SIGMA)
Fecha: Agosto 2026
"""

from __future__ import annotations

import logging
import traceback

from celery import shared_task

logger = logging.getLogger('almacen')


# ============================================================================
# TAREA PROGRAMADA: REVISIÓN DIARIA DE VIGENCIAS
# ============================================================================

@shared_task(
    name='almacen.verificar_vigencia_cotizaciones',
    ignore_result=True,
)
def verificar_vigencia_cotizaciones():
    """
    Revisa todos los países y encola la revisión de vigencias de cada uno.

    Objetivo principal (contexto de negocio):
        Que ninguna cotización se quede olvidada. Corre una vez al día desde
        Celery Beat y reparte el trabajo por país.

    Returns:
        dict: Países procesados, para que quede en los logs de Celery.

    Efectos secundarios:
        Encola una ``procesar_vigencias_pais_task`` por cada país configurado.
        No toca la base de datos directamente.
    """
    from config.paises_config import PAISES_CONFIG

    paises_encolados = []

    # EXPLICACIÓN: cada país tiene su propia base de datos. Encolamos una tarea
    # hija por país en lugar de hacer .using() manual en cada consulta, así
    # task_prerun configura el enrutamiento y el ORM funciona normal.
    for subdominio, pais_config in PAISES_CONFIG.items():
        db_alias = pais_config['db_alias']
        try:
            procesar_vigencias_pais_task.delay(db_alias=db_alias)
            paises_encolados.append(subdominio)
        except Exception as exc:
            # Si un país falla al encolar, los demás deben seguir
            logger.error(
                '[VIGENCIA] No se pudo encolar la revisión de %s: %s',
                subdominio,
                exc,
            )

    logger.info(
        '[VIGENCIA] Revisión diaria encolada para %s país(es): %s',
        len(paises_encolados),
        ', '.join(paises_encolados) or 'ninguno',
    )

    return {'paises_encolados': paises_encolados}


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='almacen.procesar_vigencias_pais',
)
def procesar_vigencias_pais_task(self, db_alias='default'):
    """
    Notifica las cotizaciones vencidas de un país concreto.

    Objetivo principal (contexto de negocio):
        Avisar a Recepción y Compras que hay cotizaciones que ya perdieron
        vigencia, para que llamen al cliente antes de que el caso se enfríe.

    Args:
        db_alias (str): Base de datos del país (Celery multi-tenant). El hook
            ``task_prerun`` de ``config/celery.py`` lo aplica al hilo del worker
            antes de que corra este código.

    Returns:
        dict: Cuántas cotizaciones se revisaron y cuántas se notificaron.

    Efectos secundarios:
        Push, campanita y actualización de ``aviso_vencimiento_enviado``.
    """
    from almacen.utils.notificar_vigencia_cotizacion import (
        procesar_solicitudes_vencidas,
    )

    log_prefix = f'[VIGENCIA][{db_alias}]'

    try:
        resultado = procesar_solicitudes_vencidas()
        logger.info(
            '%s Revisadas %s, notificadas %s',
            log_prefix,
            resultado['revisadas'],
            resultado['notificadas'],
        )
        return {'success': True, 'db_alias': db_alias, **resultado}

    except Exception as e:
        logger.error('%s Error en la revisión: %s', log_prefix, e)
        logger.error(traceback.format_exc())
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {
                'success': False,
                'mensaje': f'Error tras {self.max_retries} reintentos: {e}',
            }


# ============================================================================
# TAREA MANUAL: AVISO DE RECOTIZACIÓN A COMPRAS
# ============================================================================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='almacen.notificar_recotizacion_solicitada',
)
def notificar_recotizacion_solicitada_task(
    self,
    solicitud_id,
    usuario_id=None,
    db_alias='default',
):
    """
    Avisa a Compras que una cotización entró a una ronda nueva.

    Objetivo principal (contexto de negocio):
        El cliente reapareció después del vencimiento y quiere continuar.
        Compras debe confirmar si la pieza sigue disponible y a qué costo.

    Args:
        solicitud_id (int): PK de la SolicitudCotizacion recotizada.
        usuario_id (int | None): Quien pidió la recotización (para el texto).
        db_alias (str): Base de datos del país (Celery multi-tenant).

    Returns:
        dict: Resultado para los logs de Celery.

    Efectos secundarios:
        - Push y campanita a los empleados con rol Compras.
        - Un correo HTML con el resumen de la cotización a recotizar.
    """
    from django.contrib.auth.models import User
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone

    from almacen.models import SolicitudCotizacion
    from almacen.tasks import (
        _adjuntar_logo_e_iconos_email,
        _remitente_sistema_compras,
    )
    from almacen.utils.cotizacion_email_context import url_base_pais_email
    from almacen.utils.notificar_vigencia_cotizacion import (
        armar_destinatarios_email_recotizacion,
        notificar_recotizacion_a_compras,
    )
    from config.paises_config import fecha_local_pais, get_pais_actual

    log_prefix = '[RECOTIZACION-NOTIF]'

    try:
        # ---- Paso 1: recuperar la solicitud y el usuario ----
        try:
            solicitud = SolicitudCotizacion.objects.select_related(
                'orden_servicio',
                'creado_por',
            ).get(pk=solicitud_id)
        except SolicitudCotizacion.DoesNotExist:
            logger.error(
                '%s Solicitud ID %s no encontrada.', log_prefix, solicitud_id
            )
            return {'success': False, 'mensaje': 'Solicitud no encontrada.'}

        usuario = None
        if usuario_id:
            usuario = User.objects.filter(pk=usuario_id).first()

        # ---- Paso 2: push + campanita (aviso inmediato dentro del sistema) ----
        notificados = notificar_recotizacion_a_compras(solicitud, usuario)

        # ---- Paso 3: correo con el resumen para Compras ----
        destinatarios = armar_destinatarios_email_recotizacion(solicitud)
        if not destinatarios:
            logger.info('%s Sin correos de Compras; solo push.', log_prefix)
            return {
                'success': True,
                'mensaje': 'Notificados por push, sin correo.',
                'notificados': notificados,
            }

        pais = get_pais_actual()
        ahora_local = fecha_local_pais(timezone.now(), pais)

        # La ronda que se cerró es la anterior a la actual
        ronda_cerrada = max((solicitud.ronda_cotizacion or 1) - 1, 1)
        ultima_ronda = solicitud.rondas.order_by('-numero_ronda').first()

        context = {
            'solicitud': solicitud,
            'ronda_nueva': solicitud.ronda_cotizacion,
            'ronda_cerrada': ronda_cerrada,
            'ronda_anterior': ultima_ronda,
            'lineas': solicitud.lineas.all().order_by('numero_linea'),
            'solicitado_por': (
                usuario.get_full_name() or usuario.username
                if usuario else 'Sistema'
            ),
            'fecha_envio_texto': ahora_local.strftime('%d/%m/%Y'),
            'hora_envio_texto': ahora_local.strftime('%H:%M'),
            'empresa_nombre': pais['empresa_nombre_corto'],
            'pais_nombre': pais['nombre'],
            'url_solicitud': (
                f"{url_base_pais_email()}"
                f"/almacen/solicitudes-cotizacion/{solicitud.pk}/"
            ),
        }

        html_content = render_to_string(
            'almacen/emails/recotizacion_solicitada.html',
            context,
        )

        referencia = (
            solicitud.numero_orden_cliente
            or solicitud.service_tag
            or solicitud.numero_solicitud
        )
        asunto = (
            f'🔄 Recotización solicitada — {solicitud.numero_solicitud} '
            f'({referencia})'
        )

        email_msg = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=_remitente_sistema_compras(),
            to=destinatarios,
        )
        email_msg.content_subtype = 'html'
        _adjuntar_logo_e_iconos_email(email_msg, log_prefix)
        email_msg.send(fail_silently=False)

        logger.info(
            '%s Correo enviado a %s destinatario(s) para %s',
            log_prefix,
            len(destinatarios),
            solicitud.numero_solicitud,
        )

        return {
            'success': True,
            'mensaje': f'Notificados {notificados}, correo a {len(destinatarios)}.',
            'solicitud_id': solicitud.pk,
        }

    except Exception as e:
        logger.error('%s Error en tarea: %s', log_prefix, e)
        logger.error(traceback.format_exc())
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {
                'success': False,
                'mensaje': f'Error tras {self.max_retries} reintentos: {e}',
            }
