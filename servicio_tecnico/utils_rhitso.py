"""
Utilidades para el módulo de Servicio Técnico
==============================================

Este archivo contiene funciones auxiliares reutilizables para cálculos
y operaciones comunes en el módulo de servicio técnico.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Un archivo utils.py (utilities = utilidades) es un patrón común en Django
para almacenar funciones que se usan en múltiples partes del código.

¿Por qué separar estas funciones?
- Reutilización: Puedes usarlas en views, models, templates, etc.
- Mantenimiento: Si necesitas cambiar la lógica, solo cambias un lugar
- Testing: Es más fácil probar funciones independientes
- Organización: Mantiene views.py y models.py más limpios

Autor: Sistema Integral de Gestión
Fecha: Octubre 2025
"""

from datetime import datetime, date, timedelta
from django.utils import timezone


def calcular_dias_habiles(fecha_inicio, fecha_fin=None):
    """
    Calcula los días hábiles TRANSCURRIDOS entre dos fechas.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Los "días hábiles" son días laborables (lunes a viernes), excluyendo
    fines de semana (sábado y domingo). Esta función cuenta cuántos días
    hábiles COMPLETOS han transcurrido entre dos fechas.
    
    IMPORTANTE - Lógica de Conteo:
    -------------------------------
    - NO cuenta el día de inicio (solo días posteriores)
    - SÍ cuenta el día final (si es día hábil)
    - Si ambas fechas son el mismo día, retorna 0
    
    Esto es intuitivo para medir "tiempo transcurrido":
    - "La orden ingresó hoy" → 0 días transcurridos
    - "La orden ingresó ayer" → 1 día transcurrido (hoy)
    
    ¿Por qué usar días hábiles en lugar de días naturales?
    - Es más realista para medir tiempos de trabajo
    - Los técnicos no trabajan fines de semana
    - Permite métricas más precisas de rendimiento
    
    Args:
        fecha_inicio (date, datetime, str): Fecha inicial del período
        fecha_fin (date, datetime, str, None): Fecha final del período
                                               Si es None, usa la fecha actual
    
    Returns:
        int: Número de días hábiles transcurridos (no incluye día de inicio)
    
    Ejemplos:
        # Orden creada el viernes 11/10/2025, hoy es lunes 14/10/2025
        dias = calcular_dias_habiles('2025-10-11')
        # Resultado: 1 día hábil (solo lunes 14, no cuenta viernes 11)
        
        # Orden creada el miércoles 09/10/2025, hoy es lunes 14/10/2025
        dias = calcular_dias_habiles('2025-10-09')
        # Resultado: 3 días hábiles (jueves 10, viernes 11, lunes 14)
        # No cuenta: miércoles 9 (inicio), sábado 12, domingo 13
        
        # Orden creada y cerrada el mismo día
        dias = calcular_dias_habiles('2025-10-14', '2025-10-14')
        # Resultado: 0 días (no ha transcurrido tiempo)
    
    Detalles de implementación:
        - weekday() retorna: 0=Lunes, 1=Martes, ..., 6=Domingo
        - Días hábiles: 0-4 (Lunes a Viernes)
        - Fin de semana: 5-6 (Sábado y Domingo)
        - Comienza a contar desde fecha_inicio + 1 día
    
    Notas:
        - NO considera días festivos (puedes agregar esa funcionalidad después)
        - Asume semana laboral estándar de lunes a viernes
        - Si fecha_inicio > fecha_fin, retorna 0
    """
    # Convertir fecha_inicio a objeto date
    if isinstance(fecha_inicio, str):
        fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
    elif isinstance(fecha_inicio, datetime):
        fecha_inicio = fecha_inicio.date()
    
    # Convertir fecha_fin a objeto date (o usar hoy)
    if fecha_fin is None:
        fecha_fin = timezone.now().date()
    elif isinstance(fecha_fin, str):
        fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
    elif isinstance(fecha_fin, datetime):
        fecha_fin = fecha_fin.date()
    
    # Si fecha_inicio es mayor que fecha_fin, retornar 0
    if fecha_inicio > fecha_fin:
        return 0
    
    # Si son el mismo día, retornar 0 (no ha transcurrido tiempo completo)
    if fecha_inicio == fecha_fin:
        return 0
    
    # Contador de días hábiles
    dias_habiles = 0
    # IMPORTANTE: Empezamos desde el día SIGUIENTE al inicio
    # Esto cuenta días TRANSCURRIDOS, no el día de inicio
    fecha_actual = fecha_inicio + timedelta(days=1)
    
    # Iterar día por día desde el día siguiente al inicio hasta fecha_fin (inclusive)
    while fecha_actual <= fecha_fin:
        # weekday(): 0=Lunes, 1=Martes, 2=Miércoles, 3=Jueves, 4=Viernes, 5=Sábado, 6=Domingo
        # Días hábiles son de 0 a 4 (Lunes a Viernes)
        if fecha_actual.weekday() < 5:
            dias_habiles += 1
        
        # Avanzar al siguiente día
        fecha_actual += timedelta(days=1)
    
    return dias_habiles


def calcular_dias_en_estatus(fecha_ultimo_cambio, fecha_fin=None):
    """
    Calcula los días hábiles desde el último cambio de estado hasta ahora (o fecha_fin).
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Esta función es similar a calcular_dias_habiles, pero está optimizada
    para medir "tiempo sin actualización" en el dashboard RHITSO.
    
    ¿Cuándo usarla?
    - Para saber cuántos días hábiles lleva una orden sin actualizarse
    - Para alertar sobre órdenes "estancadas"
    - Para métricas de tiempo de respuesta
    
    Args:
        fecha_ultimo_cambio (date, datetime, str): Fecha del último cambio
        fecha_fin (date, datetime, str, None): Fecha final (default: hoy)
    
    Returns:
        int: Número de días hábiles sin actualización
    
    Ejemplos:
        # Calcular días sin actualización desde último comentario
        orden = OrdenServicio.objects.get(pk=1)
        ultimo_seguimiento = orden.ultimo_seguimiento_rhitso
        if ultimo_seguimiento:
            dias = calcular_dias_en_estatus(ultimo_seguimiento.fecha_actualizacion)
        else:
            # Si no hay seguimiento, contar desde fecha de ingreso
            dias = calcular_dias_en_estatus(orden.fecha_ingreso)
    
    Nota:
        Esta es simplemente un alias de calcular_dias_habiles para mayor claridad
        en el código. El nombre es más descriptivo del propósito.
    """
    return calcular_dias_habiles(fecha_ultimo_cambio, fecha_fin)


def obtener_color_por_dias_rhitso(dias):
    """
    Determina el color del badge según los días transcurridos en RHITSO.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Esta función implementa un sistema de "semáforo" visual:
    - Verde: Todo bien (0-6 días)
    - Amarillo: Atención (7-12 días)
    - Rojo: Urgente (>12 días)
    - Gris: Sin datos
    
    ¿Por qué usar colores por rangos?
    - Facilita identificar problemas rápidamente
    - Establece SLAs (Service Level Agreements) visuales
    - Ayuda a priorizar trabajo
    
    Args:
        dias (int): Número de días en RHITSO
    
    Returns:
        str: Clase CSS de Bootstrap ('success', 'warning', 'danger', 'secondary')
    
    Ejemplos:
        # En una vista
        orden = OrdenServicio.objects.get(pk=1)
        dias = orden.dias_en_rhitso
        color_clase = obtener_color_por_dias_rhitso(dias)
        # color_clase = 'success' si días <= 6
        
        # En un template (usando template tag)
        <span class="badge bg-{{ orden.dias_en_rhitso|color_dias_rhitso }}">
            {{ orden.dias_en_rhitso }} días
        </span>
    
    Rangos establecidos:
        0 días       → 'secondary' (gris) - Sin enviar aún
        1-6 días     → 'success' (verde) - Dentro de lo esperado
        7-12 días    → 'warning' (amarillo) - Requiere atención
        >12 días     → 'danger' (rojo) - Crítico, muy retrasado
    
    Nota:
        Estos rangos se basan en SLAs estándar de la industria.
        Puedes ajustarlos según las necesidades de tu empresa.
    """
    if dias == 0:
        return 'secondary'  # Gris - Sin enviar
    elif dias <= 6:
        return 'success'    # Verde - OK
    elif dias <= 12:
        return 'warning'    # Amarillo - Atención
    else:
        return 'danger'     # Rojo - Crítico


def formatear_tiempo_transcurrido(dias_habiles_sic, dias_habiles_rhitso=0, fecha_recepcion=None):
    """
    Formatea el texto descriptivo del tiempo transcurrido en SIC y RHITSO.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Esta función genera un texto legible que describe cuánto tiempo ha
    estado un equipo en el proceso de reparación.
    
    ¿Por qué formatear texto?
    - Mejor UX: Los usuarios entienden mejor "5 días en SIC" que solo "5"
    - Contexto: Diferencia claramente entre tiempo en SIC y en RHITSO
    - Completitud: Indica si el proceso RHITSO ya terminó
    
    Args:
        dias_habiles_sic (int): Días hábiles en SIC (desde ingreso)
        dias_habiles_rhitso (int): Días hábiles en RHITSO (default: 0)
        fecha_recepcion (date, datetime, None): Si hay fecha, RHITSO completado
    
    Returns:
        str: Texto formateado describiendo el tiempo transcurrido
    
    Ejemplos:
        # Caso 1: Solo en SIC (no enviado a RHITSO)
        texto = formatear_tiempo_transcurrido(5, 0, None)
        # Retorna: "5 días hábiles"
        
        # Caso 2: En SIC y actualmente en RHITSO
        texto = formatear_tiempo_transcurrido(10, 3, None)
        # Retorna: "10 días hábiles (3 días hábiles en RHITSO)"
        
        # Caso 3: RHITSO completado
        texto = formatear_tiempo_transcurrido(15, 5, date(2025, 10, 1))
        # Retorna: "15 días hábiles (5 días hábiles en RHITSO - Completado)"
    
    Uso en templates:
        <td>{{ orden|formatear_tiempo }}</td>
    """
    texto = f"{dias_habiles_sic} días hábiles"
    
    if dias_habiles_rhitso > 0:
        if fecha_recepcion:
            texto += f" ({dias_habiles_rhitso} días hábiles en RHITSO - Completado)"
        else:
            texto += f" ({dias_habiles_rhitso} días hábiles en RHITSO)"
    
    return texto


def obtener_estado_proceso_rhitso(orden):
    """
    Determina el estado del proceso RHITSO para una orden.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Esta función clasifica una orden en uno de tres estados posibles:
    - "Solo SIC": No se ha enviado a RHITSO aún
    - "En RHITSO": Enviado pero no ha regresado
    - "Completado": Ya regresó de RHITSO
    
    ¿Para qué sirve?
    - Filtrado: Permite generar reportes de órdenes "En RHITSO"
    - Visualización: Muestra badges con estado actual
    - Analytics: Métricas sobre cuántas órdenes están en cada etapa
    
    Args:
        orden (OrdenServicio): Instancia del modelo OrdenServicio
    
    Returns:
        str: 'Solo SIC', 'En RHITSO', o 'Completado'
    
    Ejemplos:
        # En una vista
        orden = OrdenServicio.objects.get(pk=1)
        estado = obtener_estado_proceso_rhitso(orden)
        
        if estado == 'En RHITSO':
            # Incluir en reporte de órdenes activas en RHITSO
            pass
    
    Lógica de decisión:
        1. Si dias_en_rhitso == 0 → "Solo SIC" (nunca enviado)
        2. Si dias_en_rhitso > 0 Y hay fecha_recepcion → "Completado"
        3. Si dias_en_rhitso > 0 Y NO hay fecha_recepcion → "En RHITSO"
    """
    if orden.dias_en_rhitso == 0:
        return 'Solo SIC'
    elif orden.fecha_recepcion_rhitso:
        return 'Completado'
    else:
        return 'En RHITSO'
