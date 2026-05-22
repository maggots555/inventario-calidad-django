"""
Signals para el Módulo RHITSO - Sistema de Seguimiento Especializado

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Los "signals" (señales) en Django son como detectores automáticos que observan
cuando algo cambia en la base de datos y ejecutan acciones automáticamente.

Es como tener un asistente que está siempre atento y hace tareas por ti cuando
detecta ciertos eventos.

Ejemplo:
    Cuando cambias el estado_rhitso de una orden, el signal detecta ese cambio
    y automáticamente crea un registro en la tabla SeguimientoRHITSO con toda
    la información del cambio (quién lo hizo, cuándo, qué estado anterior tenía, etc.)

Beneficios:
    - No tienes que recordar crear registros manualmente en cada vista
    - El historial es completo y confiable
    - El código está en un solo lugar (más fácil de mantener)
    - Funciona automáticamente sin importar dónde se haga el cambio

Este archivo contiene 2 signals principales:
    1. tracking_cambio_estado_rhitso - Detecta cambios en estado_rhitso
    2. registrar_incidencia_critica - Detecta incidencias con gravedad CRITICA
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from .models import (
    OrdenServicio,
    IncidenciaRHITSO,
    SeguimientoRHITSO,
    EstadoRHITSO,
    HistorialOrden
)


# ============================================================================
# SIGNAL 1: TRACKING AUTOMÁTICO DE CAMBIOS EN ESTADO_RHITSO
# ============================================================================

# EXPLICACIÓN TÉCNICA: ¿Por qué necesitamos pre_save Y post_save?
# =================================================================
# pre_save: Se ejecuta ANTES de guardar. Aquí guardamos el valor anterior
#           en una variable temporal del objeto (instance._estado_rhitso_anterior)
# post_save: Se ejecuta DESPUÉS de guardar. Aquí usamos ese valor guardado
#            para crear el registro de seguimiento

@receiver(pre_save, sender=OrdenServicio)
def guardar_estado_rhitso_anterior(sender, instance, **kwargs):
    """
    PRE-SAVE: Guarda el valor anterior de estado_rhitso antes de guardar.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Este signal se ejecuta ANTES (pre_save) de que se guarde la OrdenServicio.
    
    ¿Qué hace?
        Busca el valor actual de estado_rhitso en la base de datos y lo guarda
        en una variable temporal del objeto (_estado_rhitso_anterior).
        
        Esto es necesario porque en post_save ya no podemos saber qué valor
        tenía antes, porque ya se guardó el nuevo valor.
    
    ¿Por qué usar una variable temporal?
        Django nos permite agregar atributos temporales a un objeto con el
        prefijo underscore (_). Estos no se guardan en la BD, solo existen
        durante la ejecución.
    """
    # Si la orden ya existe en la BD (tiene pk), buscar el valor anterior
    if instance.pk:
        try:
            orden_anterior = OrdenServicio.objects.get(pk=instance.pk)
            # Guardar el valor anterior en una variable temporal
            instance._estado_rhitso_anterior = orden_anterior.estado_rhitso
        except OrdenServicio.DoesNotExist:
            # Si no existe (raro), marcar como None
            instance._estado_rhitso_anterior = None
    else:
        # Si es una orden nueva, no hay estado anterior
        instance._estado_rhitso_anterior = None


@receiver(post_save, sender=OrdenServicio)
def tracking_cambio_estado_rhitso(sender, instance, created, **kwargs):
    """
    POST-SAVE: Detecta cambios en estado_rhitso y crea registro de seguimiento.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Este signal se ejecuta DESPUÉS (post_save) de que se guarda una OrdenServicio.
    
    ¿Qué hace?
        1. Obtiene el valor anterior de estado_rhitso (guardado en pre_save)
        2. Compara con el valor actual
        3. Si cambió, crea un registro en SeguimientoRHITSO con toda la info
        4. También registra el cambio en el HistorialOrden general
    
    Parámetros:
        sender: La clase del modelo (OrdenServicio)
        instance: La orden que se acaba de guardar
        created: True si es una orden nueva, False si se está actualizando
        **kwargs: Otros parámetros que Django pasa automáticamente
    """
    
    # Si la orden se acaba de crear Y tiene estado_rhitso
    if created:
        if instance.estado_rhitso:
            try:
                estado_obj = EstadoRHITSO.objects.get(estado=instance.estado_rhitso)
                SeguimientoRHITSO.objects.create(
                    orden=instance,
                    estado=estado_obj,
                    estado_anterior='',
                    observaciones='Estado RHITSO inicial al crear la orden',
                    usuario_actualizacion=None,  # Sistema
                    tiempo_en_estado_anterior=None,
                    notificado_cliente=False,
                    es_cambio_automatico=True  # 🔧 MARCADO COMO AUTOMÁTICO
                )
                
                # Registrar en historial general
                HistorialOrden.objects.create(
                    orden=instance,
                    tipo_evento='sistema',
                    comentario=f'🆕 Estado RHITSO inicial: {instance.estado_rhitso}',
                    es_sistema=True
                )
            except EstadoRHITSO.DoesNotExist:
                pass
        return
    
    # Para órdenes que se están actualizando, verificar si cambió estado_rhitso
    estado_anterior = getattr(instance, '_estado_rhitso_anterior', None)
    estado_actual = instance.estado_rhitso
    
    # Si no cambió o está vacío, no hacer nada
    if not estado_actual or estado_actual == estado_anterior:
        return
    
    # ¡El estado cambió! Vamos a registrarlo
    
    # 1. Buscar el último seguimiento para calcular tiempo en estado anterior
    ultimo_seguimiento = SeguimientoRHITSO.objects.filter(
        orden=instance
    ).order_by('-fecha_actualizacion').first()
    
    tiempo_en_estado_anterior = None
    if ultimo_seguimiento:
        # Calcular días desde el último cambio hasta ahora
        delta = timezone.now() - ultimo_seguimiento.fecha_actualizacion
        tiempo_en_estado_anterior = delta.days
    
    # 2. Buscar el objeto EstadoRHITSO correspondiente
    try:
        estado_obj = EstadoRHITSO.objects.get(estado=estado_actual)
    except EstadoRHITSO.DoesNotExist:
        # Si el estado no existe en el catálogo, no podemos crear el seguimiento
        return
    
    # 3. Crear el registro de seguimiento
    SeguimientoRHITSO.objects.create(
        orden=instance,
        estado=estado_obj,
        estado_anterior=estado_anterior or '(Sin estado previo)',
        observaciones=f'Cambio automático de estado detectado por el sistema',
        usuario_actualizacion=None,  # None = Sistema automático
        tiempo_en_estado_anterior=tiempo_en_estado_anterior,
        notificado_cliente=False,
        es_cambio_automatico=True  # 🔧 MARCADO COMO AUTOMÁTICO
    )
    
    # 4. Registrar también en el HistorialOrden general
    HistorialOrden.objects.create(
        orden=instance,
        tipo_evento='sistema',
        comentario=f'🔄 Estado RHITSO cambiado: {estado_anterior or "(ninguno)"} → {estado_actual}',
        es_sistema=True
    )
    
    # 5. Limpiar la variable temporal (buena práctica)
    if hasattr(instance, '_estado_rhitso_anterior'):
        delattr(instance, '_estado_rhitso_anterior')


# ============================================================================
# SIGNAL 2: ALERTAR CUANDO SE REGISTRA UNA INCIDENCIA CRÍTICA
# ============================================================================

@receiver(post_save, sender=IncidenciaRHITSO)
def registrar_incidencia_critica(sender, instance, created, **kwargs):
    """
    Signal que detecta cuando se crea una incidencia con gravedad CRITICA.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Este signal se ejecuta DESPUÉS (post_save) de que se guarda una IncidenciaRHITSO.
    
    ¿Qué hace?
        Solo cuando se CREA una incidencia nueva (no al actualizarla) y si su
        tipo_incidencia tiene gravedad CRITICA, registra automáticamente un evento
        en el HistorialOrden para que todos vean que hay un problema grave.
    
    ¿Por qué es útil?
        Las incidencias críticas (como daño adicional causado por RHITSO o retrasos
        graves) deben ser visibles inmediatamente en el historial principal de la
        orden, no solo en la sección de incidencias.
    
    Parámetros:
        sender: La clase del modelo (IncidenciaRHITSO)
        instance: La incidencia que se acaba de guardar
        created: True si es nueva, False si se está actualizando
        **kwargs: Otros parámetros de Django
    """
    
    # Solo procesar cuando se CREA una incidencia nueva
    if not created:
        return
    
    # Verificar si la incidencia es de gravedad CRITICA
    # El campo tipo_incidencia es una ForeignKey a TipoIncidenciaRHITSO
    # que tiene el campo gravedad
    if instance.tipo_incidencia.gravedad == 'CRITICA':
        # Crear un evento en el historial de la orden
        HistorialOrden.objects.create(
            orden=instance.orden,
            tipo_evento='sistema',
            comentario=f'⚠️ INCIDENCIA CRÍTICA REGISTRADA: {instance.titulo}\n'
                      f'Impacto al cliente: {instance.get_impacto_cliente_display()}\n'
                      f'Prioridad: {instance.get_prioridad_display()}',
            es_sistema=True
        )
        
        # NOTA: Aquí podrías agregar más lógica como:
        # - Enviar un email al responsable
        # - Crear una notificación en el sistema
        # - Actualizar algún indicador de alerta
        # Por ahora solo registramos en el historial


# ============================================================================
# SIGNAL 3 (OPCIONAL): PRE-SAVE PARA VALIDACIONES ADICIONALES
# ============================================================================

# Este es un ejemplo de cómo usar pre_save si necesitas hacer algo
# ANTES de que se guarde el objeto en la base de datos

# @receiver(pre_save, sender=OrdenServicio)
# def validar_antes_guardar(sender, instance, **kwargs):
#     """
#     Este signal se ejecutaría ANTES de guardar la orden.
#     Útil para validaciones o cálculos que afectan el objeto mismo.
#     """
#     pass


# ============================================================================
# NOTAS PARA EL FUTURO
# ============================================================================

"""
POSIBLES MEJORAS A IMPLEMENTAR:

1. Notificaciones Automáticas:
   - Cuando cambia estado_rhitso, enviar email/SMS al cliente
   - Integrar con sistema de notificaciones del proyecto
   
2. Webhooks:
   - Notificar a sistemas externos cuando hay cambios importantes
   - Integrar con API de RHITSO para sincronización
   
3. Métricas Automáticas:
   - Calcular KPIs en tiempo real
   - Actualizar dashboards automáticamente
   
4. Validaciones Complejas:
   - Verificar que los cambios de estado sigan un flujo lógico
   - Prevenir cambios no autorizados
   
5. Auditoría Avanzada:
   - Registrar IP del usuario que hace el cambio
   - Guardar snapshot completo del objeto antes del cambio
"""


# ============================================================================
# SIGNAL 3: NOTIFICACIONES WEB PUSH — TÉCNICO ASIGNADO
# ============================================================================

import logging

logger_push = logging.getLogger('notificaciones')


@receiver(post_save, sender=HistorialOrden)
def enviar_push_tecnico(sender, instance: HistorialOrden, created: bool, **kwargs):
    """
    Envía una notificación push al técnico asignado cuando:
      - Cambia el estado de su orden
      - Es reasignado (nuevo técnico) o removido (técnico anterior)
      - Alguien comenta en una orden que tiene asignada

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta señal se dispara cada vez que se crea un nuevo registro en HistorialOrden.
    HistorialOrden registra todos los eventos de una orden: cambios de estado,
    cambios de técnico, comentarios, etc.

    Por qué usar post_save de HistorialOrden en vez de tocar OrdenServicio.save():
    - Evita importar 'notificaciones' desde 'servicio_tecnico/models.py'
      (lo que causaría un "import circular" que rompe Django al iniciar)
    - HistorialOrden ya tiene TODA la info que necesitamos (tipo_evento,
      tecnico_anterior, tecnico_nuevo, orden con su técnico asignado)
    - El código queda en un solo lugar y no hay que modificar models.py

    Solo se procesa si la fila fue CREADA (created=True).
    Las actualizaciones de HistorialOrden existentes no disparan push.
    """
    if not created:
        return

    tipo = instance.tipo_evento
    orden = instance.orden

    # Importamos aquí (lazy) para evitar import circular al cargar el módulo
    from notificaciones.push_service import enviar_push_a_usuario  # noqa

    # URL de destino al tocar la notificación — generada con reverse()
    # para que nunca se desincronice si cambia el prefijo de la app.
    url_orden = reverse('servicio_tecnico:detalle_orden', kwargs={'orden_id': orden.pk})

    # Etiqueta legible de la orden: usar orden_cliente si existe,
    # sino el número interno del sistema (fallback).
    # La relación es: OrdenServicio → detalle_equipo (related_name) → orden_cliente
    try:
        etiqueta_orden = orden.detalle_equipo.orden_cliente or orden.numero_orden_interno
    except Exception:
        etiqueta_orden = orden.numero_orden_interno

    # ── CAMBIO DE ESTADO ─────────────────────────────────────────────────────
    if tipo == 'cambio_estado':
        tecnico = orden.tecnico_asignado_actual
        if tecnico and tecnico.user:
            estado_nuevo_label = instance.estado_nuevo or orden.estado
            _push_seguro(
                enviar_push_a_usuario,
                usuario=tecnico.user,
                titulo=f'Orden {etiqueta_orden}',
                mensaje=f'Estado actualizado → {estado_nuevo_label}',
                url=url_orden,
            )

    # ── CAMBIO DE TÉCNICO ────────────────────────────────────────────────────
    elif tipo == 'cambio_tecnico':
        # Técnico nuevo → notificación de asignación
        tecnico_nuevo = instance.tecnico_nuevo
        if tecnico_nuevo and tecnico_nuevo.user:
            _push_seguro(
                enviar_push_a_usuario,
                usuario=tecnico_nuevo.user,
                titulo=f'Te asignaron la orden {etiqueta_orden}',
                mensaje='Ahora eres el técnico responsable de esta orden.',
                url=url_orden,
            )

        # Técnico anterior → notificación de remoción
        tecnico_anterior = instance.tecnico_anterior
        if tecnico_anterior and tecnico_anterior.user:
            _push_seguro(
                enviar_push_a_usuario,
                usuario=tecnico_anterior.user,
                titulo=f'Orden {etiqueta_orden}',
                mensaje='Fuiste removido como técnico de esta orden.',
                url=url_orden,
            )

    # ── NUEVO COMENTARIO ─────────────────────────────────────────────────────
    elif tipo == 'comentario':
        tecnico = orden.tecnico_asignado_actual
        if tecnico and tecnico.user:
            # No notificar al técnico si él mismo fue quien comentó
            comentarista = instance.usuario
            if comentarista and comentarista.pk == tecnico.pk:
                return

            autor = comentarista.nombre_completo if comentarista else 'Alguien'
            _push_seguro(
                enviar_push_a_usuario,
                usuario=tecnico.user,
                titulo=f'Nuevo comentario en {etiqueta_orden}',
                mensaje=f'{autor} dejó un comentario en tu orden.',
                url=url_orden,
            )


def _push_seguro(fn, **kwargs):
    """
    Llama a enviar_push_a_usuario envuelto en try/except para que
    un error de push nunca rompa el flujo principal de la aplicación.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Si el servidor de push de Google está caído o hay un error de red,
    no queremos que eso haga fallar el guardado de la orden. Por eso
    capturamos cualquier error aquí y solo lo registramos en el log.
    """
    try:
        fn(**kwargs)
    except Exception as exc:
        logger_push.error(
            f'[PUSH] Error en _push_seguro: {exc}',
            exc_info=True,
        )
