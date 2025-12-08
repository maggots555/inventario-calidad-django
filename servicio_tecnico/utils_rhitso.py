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


# ============================================================================
# FUNCIONES PARA DASHBOARD DE SEGUIMIENTO OOW-/FL-
# ============================================================================

def calcular_dias_por_estatus(orden):
    """
    Calcula cuántos días hábiles ha permanecido la orden en cada estado.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Esta función analiza el historial completo de una orden y calcula
    cuánto tiempo (en días hábiles) estuvo en cada estado del proceso.
    
    ¿Para qué sirve?
    - Identificar cuellos de botella en el proceso
    - Medir eficiencia de cada etapa
    - Comparar tiempos entre diferentes órdenes
    - Generar promedios por estado
    
    ¿Cómo funciona?
    1. Obtiene todos los eventos de cambio de estado del historial
    2. Para cada estado, calcula días hábiles desde que entró hasta que salió
    3. Si aún está en un estado, calcula hasta hoy
    
    Args:
        orden (OrdenServicio): Instancia del modelo OrdenServicio
    
    Returns:
        dict: Diccionario con estado como key y días hábiles como value
              Ejemplo: {'espera': 1, 'diagnostico': 3, 'reparacion': 5}
    
    Ejemplo de uso:
        orden = OrdenServicio.objects.get(pk=1)
        dias_por_estado = calcular_dias_por_estatus(orden)
        
        print(f"En diagnóstico: {dias_por_estado.get('diagnostico', 0)} días")
        print(f"En reparación: {dias_por_estado.get('reparacion', 0)} días")
    
    Nota:
        - Solo cuenta días hábiles (lunes a viernes)
        - Si no hay historial, usa el estado actual con días desde ingreso
        - Requiere que el modelo HistorialOrden esté correctamente poblado
    """
    from servicio_tecnico.models import HistorialOrden
    
    # Diccionario para almacenar días por estado
    dias_por_estado = {}
    
    # Obtener todos los cambios de estado ordenados cronológicamente
    cambios_estado = orden.historial.filter(
        tipo_evento='cambio_estado'
    ).order_by('fecha_evento')
    
    if not cambios_estado.exists():
        # Si no hay historial de cambios, usar el estado actual
        # y calcular días desde ingreso
        dias_habiles = calcular_dias_habiles(orden.fecha_ingreso)
        dias_por_estado[orden.estado] = dias_habiles
        return dias_por_estado
    
    # Recorrer cada cambio de estado
    fecha_entrada_estado = orden.fecha_ingreso
    estado_actual = cambios_estado.first().estado_anterior or orden.estado
    
    for cambio in cambios_estado:
        # Calcular días en el estado anterior
        if estado_actual:
            dias = calcular_dias_habiles(fecha_entrada_estado, cambio.fecha_evento)
            if estado_actual in dias_por_estado:
                dias_por_estado[estado_actual] += dias
            else:
                dias_por_estado[estado_actual] = dias
        
        # Actualizar para el siguiente estado
        estado_actual = cambio.estado_nuevo
        fecha_entrada_estado = cambio.fecha_evento
    
    # Calcular días en el estado actual (desde último cambio hasta ahora)
    if estado_actual:
        dias = calcular_dias_habiles(fecha_entrada_estado)
        if estado_actual in dias_por_estado:
            dias_por_estado[estado_actual] += dias
        else:
            dias_por_estado[estado_actual] = dias
    
    return dias_por_estado


def formatear_nombre_estado(estado_codigo):
    """
    Convierte el código interno de estado a un nombre legible para mostrar.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    En la base de datos, los estados se guardan como códigos con guiones bajos
    (por ejemplo: 'equipo_diagnosticado', 'control_calidad'). Esta función
    los convierte a texto legible para mostrar en la interfaz de usuario.
    
    Ejemplos:
        'equipo_diagnosticado' → 'Equipo Diagnosticado'
        'control_calidad' → 'Control Calidad'
        'espera' → 'Espera'
        'cotizacion_enviada_proveedor' → 'Cotización Enviada Proveedor'
    
    Args:
        estado_codigo (str): Código interno del estado (ej: 'control_calidad')
    
    Returns:
        str: Nombre formateado para mostrar (ej: 'Control Calidad')
    """
    if not estado_codigo:
        return 'Sin Estado'
    
    # Reemplazar guiones bajos por espacios y capitalizar cada palabra
    nombre_formateado = estado_codigo.replace('_', ' ').title()
    
    return nombre_formateado


# Estados finales que no deberían contarse en métricas de tiempo de proceso
# ya que representan el cierre de la orden, no una etapa activa del servicio
ESTADOS_FINALES = ['entregado', 'cancelado']


def calcular_promedio_dias_por_estatus(ordenes_queryset, incluir_estados_finales=False):
    """
    Calcula el promedio de días hábiles por estado para un conjunto de órdenes.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Esta función toma varias órdenes y calcula el promedio de tiempo que
    han permanecido en cada estado del proceso.
    
    ¿Para qué sirve?
    - Dashboard de métricas generales
    - Identificar estados problemáticos (cuellos de botella)
    - Establecer benchmarks de tiempo esperado
    - Comparar rendimiento entre diferentes períodos
    
    ¿Cómo funciona?
    1. Para cada orden, obtiene sus días por estado
    2. Suma todos los días de cada estado
    3. Divide entre el número de órdenes que pasaron por ese estado
    4. NUEVO: Excluye estados finales (entregado/cancelado) del resultado principal
    5. NUEVO: Devuelve estadísticas de estados finales por separado
    
    IMPORTANTE - Estados Finales:
    -----------------------------
    Los estados 'entregado' y 'cancelado' son estados de CIERRE de la orden.
    No deben mezclarse con los estados de proceso porque:
    - No representan una etapa activa del servicio
    - Distorsionan los promedios de tiempo de proceso
    - Su tiempo refleja "días desde finalización", no tiempo de trabajo
    
    Por eso esta función los separa en un diccionario aparte llamado
    'estados_finales' para que puedan mostrarse en una sección diferente
    del dashboard si es necesario.
    
    Args:
        ordenes_queryset (QuerySet): Conjunto de órdenes a analizar
        incluir_estados_finales (bool): Si True, incluye entregado/cancelado
                                        en el resultado principal. Default: False
    
    Returns:
        dict: Diccionario con dos secciones:
            - 'estados_proceso': Estados activos del proceso (sin entregado/cancelado)
            - 'estados_finales': Estadísticas de entregado y cancelado por separado
            
            Estructura de cada estado:
            {
                'nombre_estado': {
                    'promedio': 1.5,      # Promedio de días hábiles
                    'total_ordenes': 10,  # Cuántas órdenes pasaron por este estado
                    'min': 0,             # Mínimo de días
                    'max': 3              # Máximo de días
                }
            }
    
    Ejemplo de uso:
        ordenes = OrdenServicio.objects.filter(...)
        resultado = calcular_promedio_dias_por_estatus(ordenes)
        
        # Acceder a estados de proceso
        for estado, stats in resultado['estados_proceso'].items():
            print(f"{estado}: {stats['promedio']} días promedio")
        
        # Acceder a estados finales (si existen)
        if resultado['estados_finales']:
            for estado, stats in resultado['estados_finales'].items():
                print(f"Cierre - {estado}: {stats['promedio']} días promedio")
    
    Nota:
        - Solo incluye estados por los que al menos una orden ha pasado
        - El promedio es redondeado a 1 decimal
        - Incluye min/max para ver el rango completo
        - Los nombres de estados se formatean automáticamente (sin guiones bajos)
    """
    # Diccionarios para acumular estadísticas por estado
    acumulado_por_estado = {}
    contador_por_estado = {}
    min_por_estado = {}
    max_por_estado = {}
    
    # Recorrer cada orden y acumular días por estado
    for orden in ordenes_queryset:
        dias_por_estado = calcular_dias_por_estatus(orden)
        
        for estado, dias in dias_por_estado.items():
            # Acumular estadísticas para este estado
            if estado in acumulado_por_estado:
                acumulado_por_estado[estado] += dias
                contador_por_estado[estado] += 1
                min_por_estado[estado] = min(min_por_estado[estado], dias)
                max_por_estado[estado] = max(max_por_estado[estado], dias)
            else:
                acumulado_por_estado[estado] = dias
                contador_por_estado[estado] = 1
                min_por_estado[estado] = dias
                max_por_estado[estado] = dias
    
    # Calcular promedios y separar estados de proceso vs estados finales
    estados_proceso = {}
    estados_finales = {}
    
    for estado_codigo in acumulado_por_estado:
        if contador_por_estado[estado_codigo] > 0:
            promedio = acumulado_por_estado[estado_codigo] / contador_por_estado[estado_codigo]
            
            # Formatear el nombre del estado para mostrar (sin guiones bajos)
            nombre_formateado = formatear_nombre_estado(estado_codigo)
            
            # Crear diccionario de estadísticas
            stats = {
                'promedio': round(promedio, 1),
                'total_ordenes': contador_por_estado[estado_codigo],
                'min': min_por_estado[estado_codigo],
                'max': max_por_estado[estado_codigo],
                'codigo': estado_codigo,  # Guardar código original por si se necesita
            }
            
            # Separar estados finales de estados de proceso
            if estado_codigo in ESTADOS_FINALES:
                estados_finales[nombre_formateado] = stats
            else:
                estados_proceso[nombre_formateado] = stats
    
    # Si se solicita incluir estados finales en el resultado principal
    # (para compatibilidad con código existente)
    if incluir_estados_finales:
        estados_proceso.update(estados_finales)
        return estados_proceso
    
    # Retornar estructura separada (comportamiento por defecto)
    return {
        'estados_proceso': estados_proceso,
        'estados_finales': estados_finales,
    }


def agrupar_ordenes_por_mes(ordenes_queryset):
    """
    Agrupa órdenes por mes y calcula estadísticas.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Esta función organiza las órdenes por mes de ingreso y calcula
    estadísticas para cada mes (cantidad, ingresos, promedios, etc.)
    
    ¿Para qué sirve?
    - Gráficos de evolución mensual
    - Comparar rendimiento mes a mes
    - Identificar tendencias y patrones
    - Reportes ejecutivos mensuales
    
    Args:
        ordenes_queryset (QuerySet): Conjunto de órdenes a analizar
    
    Returns:
        list: Lista de diccionarios, uno por mes, ordenados cronológicamente
              Ejemplo: [
                  {
                      'mes': 'Enero 2025',
                      'año': 2025,
                      'mes_numero': 1,
                      'total_ordenes': 45,
                      'ordenes_finalizadas': 38,
                      'ventas_mostrador': 15,
                      'monto_total': 125000.00,
                      'dias_promedio': 8.5
                  },
                  ...
              ]
    
    Ejemplo de uso:
        ordenes = OrdenServicio.objects.filter(
            fecha_ingreso__year=2025
        )
        
        datos_mensuales = agrupar_ordenes_por_mes(ordenes)
        
        for mes_data in datos_mensuales:
            print(f"{mes_data['mes']}: {mes_data['total_ordenes']} órdenes")
    """
    from django.db.models import Count, Sum, Avg
    from decimal import Decimal
    
    # Diccionario para acumular datos por mes
    meses_data = {}
    
    for orden in ordenes_queryset.select_related('detalle_equipo', 'venta_mostrador', 'cotizacion'):
        # Obtener mes y año
        mes_numero = orden.fecha_ingreso.month
        año = orden.fecha_ingreso.year
        mes_key = f"{año}-{mes_numero:02d}"
        
        # Inicializar si no existe
        if mes_key not in meses_data:
            meses_nombres = [
                'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
            ]
            meses_data[mes_key] = {
                'mes': f"{meses_nombres[mes_numero - 1]} {año}",
                'año': año,
                'mes_numero': mes_numero,
                'mes_key': mes_key,
                'total_ordenes': 0,
                'ordenes_finalizadas': 0,
                'ordenes_entregadas': 0,
                'ventas_mostrador': 0,
                'con_cotizacion': 0,
                'cotizaciones_aceptadas': 0,
                'monto_ventas_mostrador': Decimal('0.00'),
                'monto_cotizaciones': Decimal('0.00'),
                'dias_acumulados': 0,
            }
        
        # Acumular estadísticas
        meses_data[mes_key]['total_ordenes'] += 1
        
        if orden.estado == 'finalizado':
            meses_data[mes_key]['ordenes_finalizadas'] += 1
        
        if orden.estado == 'entregado':
            meses_data[mes_key]['ordenes_entregadas'] += 1
        
        # Venta mostrador
        if hasattr(orden, 'venta_mostrador') and orden.venta_mostrador:
            meses_data[mes_key]['ventas_mostrador'] += 1
            meses_data[mes_key]['monto_ventas_mostrador'] += orden.venta_mostrador.total_venta
        
        # Cotización
        if hasattr(orden, 'cotizacion') and orden.cotizacion:
            meses_data[mes_key]['con_cotizacion'] += 1
            if orden.cotizacion.usuario_acepto:
                meses_data[mes_key]['cotizaciones_aceptadas'] += 1
                meses_data[mes_key]['monto_cotizaciones'] += orden.cotizacion.costo_total_final
        
        # Acumular días en servicio (para calcular promedio)
        meses_data[mes_key]['dias_acumulados'] += orden.dias_habiles_en_servicio
    
    # Convertir a lista y calcular promedios
    resultado = []
    for mes_key in sorted(meses_data.keys()):
        mes_data = meses_data[mes_key]
        
        # Calcular promedio de días
        if mes_data['total_ordenes'] > 0:
            mes_data['dias_promedio'] = round(
                mes_data['dias_acumulados'] / mes_data['total_ordenes'], 
                1
            )
        else:
            mes_data['dias_promedio'] = 0
        
        # Calcular monto total
        mes_data['monto_total'] = mes_data['monto_ventas_mostrador'] + mes_data['monto_cotizaciones']
        
        # Calcular porcentajes
        if mes_data['total_ordenes'] > 0:
            mes_data['porcentaje_finalizadas'] = round(
                (mes_data['ordenes_finalizadas'] / mes_data['total_ordenes']) * 100, 
                1
            )
        else:
            mes_data['porcentaje_finalizadas'] = 0
        
        # Eliminar campo temporal
        del mes_data['dias_acumulados']
        
        resultado.append(mes_data)
    
    return resultado
