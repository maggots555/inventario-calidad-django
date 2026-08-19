"""
Vigencia de la cotización al cliente (5 días hábiles)
======================================================

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cuando Compras termina de cotizar y libera la solicitud a Front (recepción),
arranca un reloj: el cliente tiene **5 días hábiles** para contestar. Los días
hábiles son de lunes a viernes; sábados y domingos no cuentan.

¿Por qué existe ese plazo? Porque los proveedores cambian precios y las piezas
se agotan. Si el cliente contesta al día 12, el costo que le dimos ya no sirve
y podríamos vender perdiendo dinero.

Este archivo es el "cerebro" del cálculo. No toca HTTP ni templates: solo
recibe una solicitud y responde preguntas como "¿ya venció?" o "¿cuántos días
le quedan?". Las vistas y los templates consultan estas funciones.

Regla del proyecto: la lógica de negocio NO vive en models.py (que ya está muy
grande). El modelo solo expone una fachada de 3 líneas que llama aquí.

LIMITACIÓN CONOCIDA (a propósito):
Solo se descartan sábados y domingos. NO hay calendario de días festivos, así
que el 16 de septiembre o el 25 de diciembre cuentan como días hábiles y el
plazo corre igual. Agregar festivos implicaría un calendario por país (México,
Argentina, Chile y Colombia tienen fechas distintas), y eso es un proyecto
aparte. Si algún día se hace, el único punto a tocar es ``sumar_dias_habiles``
y ``contar_dias_habiles_restantes``: todo lo demás los consume.

Autor: Sistema Integral de Gestión (SIGMA)
Fecha: Agosto 2026
"""

from datetime import date, datetime, timedelta
from typing import Literal, Optional

from django.utils import timezone

from config.constants import (
    DIAS_HABILES_ALERTA_URGENTE_COTIZACION,
    DIAS_HABILES_VIGENCIA_COTIZACION,
    ESTADOS_SOLICITUD_CON_VIGENCIA,
)

# Valores que el Panel de Cotizaciones usa para pintar fila y KPIs.
# 'vencida' = pasaron los 5 días hábiles; 'urgente' = queda 1 día o menos.
AlertaVigenciaPanel = Literal['vencida', 'urgente', 'ok']


# ============================================================================
# CÁLCULO DE DÍAS HÁBILES
# ============================================================================

def a_hora_local(momento):
    """
    Convierte un datetime a la hora local del país activo (México, Chile...).

    Objetivo principal (contexto de negocio):
        El servidor guarda todo en UTC, pero "¿es sábado?" hay que responderlo
        con el calendario de quien opera. En México (UTC-6), a las 6 de la
        tarde en UTC ya es el día siguiente: si preguntáramos el día de la
        semana sobre la hora UTC, un jueves por la noche contaría como viernes
        y el plazo se correría un día.

    Args:
        momento (datetime | date): Fecha a convertir. Si no es un datetime con
            zona horaria, se devuelve tal cual (no hay nada que convertir).

    Returns:
        datetime | date: El mismo instante expresado en la hora local del país.

    Efectos secundarios:
        Ninguno. Si la configuración de país no está disponible (por ejemplo en
        un test aislado), cae al huso por defecto de Django sin romper.
    """
    if not isinstance(momento, datetime) or timezone.is_naive(momento):
        return momento

    try:
        from config.paises_config import fecha_local_pais, get_pais_actual
        return fecha_local_pais(momento, get_pais_actual())
    except Exception:
        # Fallback: huso configurado en settings. Nunca dejamos que un
        # problema de configuración tumbe el cálculo de la vigencia.
        return timezone.localtime(momento)


def sumar_dias_habiles(fecha_inicio, dias_habiles: int):
    """
    Proyecta una fecha hacia adelante saltando sábados y domingos.

    Objetivo principal (contexto de negocio):
        Calcular la fecha límite de una cotización. Es la contraparte de
        ``calcular_dias_habiles()`` de Servicio Técnico, que solo cuenta días
        ya transcurridos hacia atrás; aquí necesitamos proyectar el futuro.

    Args:
        fecha_inicio (datetime | date): Momento en que arranca el plazo.
        dias_habiles (int): Cuántos días laborables sumar (ej. 5).

    Returns:
        datetime | date: Misma clase que ``fecha_inicio``, corrida N días
        hábiles. Conserva la hora original si se recibió un datetime.

    Efectos secundarios:
        Ninguno: función pura, no toca la base de datos.

    Ejemplos:
        Viernes + 5 días hábiles = viernes de la semana siguiente
        (sábado y domingo se saltan, no consumen plazo).
    """
    # EXPLICACIÓN: primero pasamos a hora local del país. El día de la semana
    # solo tiene sentido en el calendario de quien opera, no en UTC.
    referencia = a_hora_local(fecha_inicio)

    # Trabajamos sobre la parte de fecha (sin hora) para poder preguntar el
    # día de la semana; al final le devolvemos su hora original.
    es_datetime = isinstance(referencia, datetime)
    fecha_cursor: date = referencia.date() if es_datetime else referencia

    # Contador de días laborables que ya sumamos
    dias_sumados = 0

    # Avanzamos día por día. Solo los lunes-viernes descuentan plazo.
    # weekday(): 0=Lunes ... 4=Viernes, 5=Sábado, 6=Domingo
    while dias_sumados < dias_habiles:
        fecha_cursor += timedelta(days=1)
        if fecha_cursor.weekday() < 5:
            dias_sumados += 1

    # Si nos dieron un datetime, devolvemos datetime conservando la hora local.
    # Sigue siendo "aware", así que Django lo guardará convertido a UTC solo.
    if es_datetime:
        return referencia.replace(
            year=fecha_cursor.year,
            month=fecha_cursor.month,
            day=fecha_cursor.day,
        )

    return fecha_cursor


def contar_dias_habiles_restantes(fecha_vencimiento, desde=None) -> int:
    """
    Cuenta cuántos días hábiles faltan para la fecha de vencimiento.

    Objetivo principal (contexto de negocio):
        Alimentar el badge de la UI ("Vence en 3 días hábiles") para que
        recepción sepa cuándo insistirle al cliente.

    Args:
        fecha_vencimiento (datetime): Fecha límite de la cotización.
        desde (datetime | None): Momento de referencia; por defecto, ahora.

    Returns:
        int: Días hábiles restantes. 0 si ya venció o vence hoy.

    Efectos secundarios:
        Ninguno.
    """
    if not fecha_vencimiento:
        return 0

    referencia = desde or timezone.now()

    # Si ya pasamos la fecha límite, no quedan días
    if referencia >= fecha_vencimiento:
        return 0

    # EXPLICACIÓN: contamos día por día desde mañana hasta el vencimiento,
    # sumando solo los laborables. El día de hoy no se cuenta como "restante"
    # porque ya se está consumiendo. Ambas fechas se pasan a hora local para
    # que el corte del día sea el de la sucursal y no la medianoche UTC.
    dia_cursor = a_hora_local(referencia).date()
    dia_limite = a_hora_local(fecha_vencimiento).date()
    dias = 0

    while dia_cursor < dia_limite:
        dia_cursor += timedelta(days=1)
        if dia_cursor.weekday() < 5:
            dias += 1

    return dias


# ============================================================================
# ARRANQUE DEL RELOJ
# ============================================================================

def iniciar_vigencia(solicitud, guardar: bool = True):
    """
    Arranca el plazo de 5 días hábiles de la ronda actual.

    Objetivo principal (contexto de negocio):
        Se llama cuando Compras libera la cotización a Front. A partir de ese
        momento el cliente tiene la ventana para decidir.

    Args:
        solicitud (SolicitudCotizacion): Cotización que arranca su plazo.
        guardar (bool): Si True, persiste los dos campos en la base de datos.
            Se pasa False cuando quien llama va a hacer su propio ``save()``
            (evita escribir dos veces en la misma operación).

    Returns:
        datetime: La fecha de vencimiento calculada.

    Efectos secundarios:
        Escribe ``fecha_inicio_vigencia`` y ``fecha_vencimiento_vigencia``.
        Si ``guardar=True``, hace un UPDATE de esos dos campos.
    """
    ahora = timezone.now()

    # El vencimiento es "ahora + 5 días hábiles" (constante configurable)
    vencimiento = sumar_dias_habiles(ahora, DIAS_HABILES_VIGENCIA_COTIZACION)

    solicitud.fecha_inicio_vigencia = ahora
    solicitud.fecha_vencimiento_vigencia = vencimiento
    # Nueva ronda = nuevo plazo, así que el aviso automático vuelve a estar
    # disponible (la tarea diaria podrá avisar otra vez cuando venza).
    solicitud.aviso_vencimiento_enviado = False

    if guardar:
        solicitud.save(update_fields=[
            'fecha_inicio_vigencia',
            'fecha_vencimiento_vigencia',
            'aviso_vencimiento_enviado',
        ])

    return vencimiento


# ============================================================================
# CONSULTAS DE ESTADO
# ============================================================================

def vigencia_aplica(solicitud) -> bool:
    """
    True si esta solicitud está dentro de la etapa donde el reloj corre.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Solo tiene sentido hablar de vigencia mientras esperamos respuesta del
    cliente (``enviada_front`` / ``enviada_cliente``). En borrador todavía no
    se cotiza, y una vez que el cliente respondió ya no importa el plazo.

    Args:
        solicitud (SolicitudCotizacion): Cotización a evaluar.

    Returns:
        bool: True si el estado es uno de los que tienen vigencia activa.

    Efectos secundarios:
        Ninguno.
    """
    return (
        solicitud.estado in ESTADOS_SOLICITUD_CON_VIGENCIA
        and solicitud.fecha_vencimiento_vigencia is not None
    )


def esta_vencida(solicitud) -> bool:
    """
    True si ya pasaron los 5 días hábiles sin respuesta del cliente.

    Objetivo principal (contexto de negocio):
        Es la pregunta que dispara el bloqueo duro: si está vencida, nadie
        puede aprobar piezas con precios viejos.

    Args:
        solicitud (SolicitudCotizacion): Cotización a evaluar.

    Returns:
        bool: True si venció el plazo; False si sigue viva o no aplica.

    Efectos secundarios:
        Ninguno.
    """
    if not vigencia_aplica(solicitud):
        return False

    return timezone.now() >= solicitud.fecha_vencimiento_vigencia


def dias_habiles_restantes(solicitud) -> Optional[int]:
    """
    Días hábiles que le quedan al cliente para responder.

    Args:
        solicitud (SolicitudCotizacion): Cotización a evaluar.

    Returns:
        int | None: Días restantes (0 si venció) o None si no aplica vigencia
        en el estado actual (por ejemplo, en borrador).

    Efectos secundarios:
        Ninguno.
    """
    if not vigencia_aplica(solicitud):
        return None

    return contar_dias_habiles_restantes(solicitud.fecha_vencimiento_vigencia)


def alerta_vigencia_panel(solicitud) -> AlertaVigenciaPanel:
    """
    Clasifica una cotización para el Panel (fila + KPI Por vencer / Vencidas).

    Objetivo principal (contexto de negocio):
        El panel no debe alertar a los 3 días calendario (regla vieja). Debe
        usar el mismo reloj de 5 días hábiles que el detalle: si venció,
        hay que recotizar; si queda 1 día hábil o menos, hay que insistir.

    Args:
        solicitud (SolicitudCotizacion): Cotización a evaluar. Solo necesita
            ``estado`` y ``fecha_vencimiento_vigencia``.

    Returns:
        str: ``'vencida'`` si pasaron los 5 días hábiles; ``'urgente'`` si
        aún no vence y quedan ``DIAS_HABILES_ALERTA_URGENTE_COTIZACION``
        días hábiles o menos; ``'ok'`` en cualquier otro caso (incluye
        borrador o sin fecha de vigencia).

    Efectos secundarios:
        Ninguno. Reutiliza ``esta_vencida`` y ``dias_habiles_restantes``.
    """
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Primero preguntamos si YA venció. Si preguntáramos solo los días
    # restantes, una vencida devolvería 0 y se pintaría como «por vencer»
    # en lugar de «vencida».
    if esta_vencida(solicitud):
        return 'vencida'

    # Si no hay fecha de vigencia, restantes es None → no alertamos.
    restantes = dias_habiles_restantes(solicitud)
    # 1 día hábil o 0 (vence hoy) cuenta como urgente, igual que el detalle.
    if (
        restantes is not None
        and restantes <= DIAS_HABILES_ALERTA_URGENTE_COTIZACION
    ):
        return 'urgente'

    return 'ok'


def puede_aprobar_por_vigencia(solicitud) -> bool:
    """
    True si todavía se pueden APROBAR piezas/servicios de esta cotización.

    Objetivo principal (contexto de negocio):
        Bloqueo duro. Si la cotización venció, aprobar significaría comprar a
        un precio que ya no existe. Rechazar y tipificar sí siguen permitidos,
        porque cerrar un caso viejo no cuesta dinero.

    Args:
        solicitud (SolicitudCotizacion): Cotización a evaluar.

    Returns:
        bool: False solo cuando la vigencia venció.

    Efectos secundarios:
        Ninguno.
    """
    return not esta_vencida(solicitud)


# ============================================================================
# ELEGIBILIDAD PARA RECOTIZAR
# ============================================================================

def solicitud_sin_respuesta_cliente(solicitud) -> bool:
    """
    True si el cliente no ha contestado absolutamente nada.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    "Sin respuesta" significa que TODAS las piezas y TODOS los servicios siguen
    en estado ``pendiente``. Basta con que el cliente haya aprobado o rechazado
    una sola línea para que ya no cuente como "sin respuesta": en ese caso los
    precios ya se congelaron y puede haber compras generadas, así que reciclar
    la solicitud rompería el histórico.

    Args:
        solicitud (SolicitudCotizacion): Cotización a evaluar.

    Returns:
        bool: True si no hay ni una sola respuesta registrada.

    Efectos secundarios:
        Ninguno (dos consultas de solo lectura a la base de datos).
    """
    # ¿Alguna pieza dejó de estar pendiente? (aprobada, rechazada o con compra)
    hay_piezas_respondidas = solicitud.lineas.exclude(
        estado_cliente='pendiente'
    ).exists()
    if hay_piezas_respondidas:
        return False

    # Mismo chequeo para los servicios adicionales (venta mostrador)
    hay_servicios_respondidos = solicitud.servicios_adicionales.exclude(
        estado_cliente='pendiente'
    ).exists()

    return not hay_servicios_respondidos


def puede_recotizar(solicitud) -> bool:
    """
    True si se puede abrir una ronda nueva de cotización.

    Objetivo principal (contexto de negocio):
        Controla que el botón "Solicitar Recotización" solo aparezca en el caso
        real de negocio: la cotización venció, el cliente nunca contestó, y
        ahora quiere continuar. Compras debe confirmar disponibilidad y precio.

    Condiciones (las tres deben cumplirse):
        1. Estado con vigencia activa (``enviada_front`` / ``enviada_cliente``).
        2. Vigencia vencida (pasaron los 5 días hábiles).
        3. Cero respuestas del cliente (ni una pieza ni un servicio).

    Args:
        solicitud (SolicitudCotizacion): Cotización a evaluar.

    Returns:
        bool: True si la UI y la vista pueden iniciar una ronda nueva.

    Efectos secundarios:
        Ninguno.
    """
    if not esta_vencida(solicitud):
        return False

    return solicitud_sin_respuesta_cliente(solicitud)


def motivo_bloqueo_envio_cliente(solicitud) -> str:
    """
    Texto explicativo de por qué no se puede enviar/reenviar la cotización.

    Objetivo principal (contexto de negocio):
        Reenviar una cotización vencida le prometería al cliente un precio que
        quizá ya no podemos sostener. Este texto se muestra en el modal y en la
        respuesta de la API para que quede claro que hay que recotizar primero.

    Args:
        solicitud (SolicitudCotizacion): Cotización bloqueada.

    Returns:
        str: Mensaje listo para mostrar al usuario. Cadena vacía si no hay
        bloqueo por vigencia.

    Efectos secundarios:
        Ninguno.
    """
    if not esta_vencida(solicitud):
        return ''

    fecha = solicitud.fecha_vencimiento_vigencia.strftime('%d/%m/%Y')
    return (
        f'La vigencia de esta cotización venció el {fecha} '
        f'({DIAS_HABILES_VIGENCIA_COTIZACION} días hábiles sin respuesta). '
        'No es posible enviarla ni reenviarla al cliente porque los costos del '
        'proveedor pueden haber cambiado. Solicita una recotización a Compras '
        'para confirmar disponibilidad y precio actualizado.'
    )


def motivo_bloqueo_aprobacion(solicitud) -> str:
    """
    Texto explicativo de por qué no se puede aprobar (para messages y UI).

    Args:
        solicitud (SolicitudCotizacion): Cotización bloqueada.

    Returns:
        str: Mensaje listo para mostrar al usuario. Cadena vacía si no hay
        bloqueo por vigencia.

    Efectos secundarios:
        Ninguno.
    """
    if not esta_vencida(solicitud):
        return ''

    fecha = solicitud.fecha_vencimiento_vigencia.strftime('%d/%m/%Y')
    return (
        f'La vigencia de esta cotización venció el {fecha} '
        f'({DIAS_HABILES_VIGENCIA_COTIZACION} días hábiles sin respuesta). '
        'Los costos del proveedor pueden haber cambiado, por lo que no es '
        'posible aprobar. Solicita una recotización a Compras para confirmar '
        'disponibilidad y precio actualizado.'
    )
