"""
Módulo de Lógica de Negocio: Concentrado Semanal de CIS
=======================================================

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Este archivo contiene todas las funciones que calculan los datos del
"Concentrado Semanal". Un concentrado semanal es un reporte de cuántos
equipos entraron y salieron del CIS (Centro de Servicio) en una semana,
agrupados por sitio y tipo de equipo.

Las 3 secciones del concentrado son:
  1. INGRESO DE EQUIPOS  → usa OrdenServicio.fecha_ingreso
  2. ASIGNACIÓN A INGENIERÍA → usa OrdenServicio.tecnico_asignado_actual
  3. EGRESO DE EQUIPOS   → usa OrdenServicio.fecha_entrega

CLASIFICACIÓN DE EQUIPOS:
  - LENOVO        → marca == 'Lenovo' y NO es MIS y NO es OOW/FL
  - DELL          → marca == 'Dell' y NO es MIS y NO es OOW/FL
  - OOW           → orden_cliente empieza con 'OOW-' o 'FL-'
  - MIS DELL      → es_mis == True y marca == 'Dell'
  - MIS LENOVO    → es_mis == True y marca == 'Lenovo'

CLASIFICACIÓN DE SITIOS:
  - DROP OFF      → sucursal.nombre contiene 'Drop' (case insensitive)
  - SATELITE      → sucursal.nombre contiene 'Satelit' (cubre Satélite / Satelite)
"""

from datetime import date, timedelta
from collections import defaultdict

from django.db.models import Q

from .models import OrdenServicio


# ===========================================================================
# CONSTANTES DE CLASIFICACIÓN
# ===========================================================================

# Días de la semana en español (indexados como Python: 0=Lunes ... 4=Viernes)
DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']

# Tipos de equipo que se muestran en el concentrado (en orden)
TIPOS_EQUIPO = ['LENOVO', 'DELL', 'OOW', 'MIS DELL', 'MIS LENOVO']

# Sitios (sucursales) del concentrado
SITIOS = ['DROP OFF', 'SATELITE']

# Quarters del año
QUARTERS = {
    'Q1': {'nombre': 'Q1 (Ene - Mar)', 'meses': [1, 2, 3]},
    'Q2': {'nombre': 'Q2 (Abr - Jun)', 'meses': [4, 5, 6]},
    'Q3': {'nombre': 'Q3 (Jul - Sep)', 'meses': [7, 8, 9]},
    'Q4': {'nombre': 'Q4 (Oct - Dic)', 'meses': [10, 11, 12]},
}


# ===========================================================================
# FUNCIONES AUXILIARES DE SEMANA
# ===========================================================================

def obtener_semana_actual():
    """
    Retorna el lunes de la semana actual.

    EXPLICACIÓN: Usa la fecha de hoy y retrocede hasta el lunes más reciente.
    Esto sirve para mostrar la semana actual por defecto al cargar la página.

    Returns:
        date: Fecha del lunes de la semana actual
    """
    hoy = date.today()
    return hoy - timedelta(days=hoy.weekday())


def obtener_rango_semana(lunes):
    """
    Dado un lunes, calcula el viernes de esa semana.

    Args:
        lunes (date): Fecha del lunes de la semana

    Returns:
        tuple: (lunes, viernes) como objetos date
    """
    viernes = lunes + timedelta(days=4)
    return lunes, viernes


def obtener_numero_semana(lunes):
    """
    Retorna el número de semana ISO del año para un lunes dado.

    Args:
        lunes (date): Fecha del lunes

    Returns:
        int: Número de semana ISO (1-53)
    """
    return lunes.isocalendar()[1]


def lunes_desde_numero_semana(año, numero_semana):
    """
    Dado un año y número de semana ISO, retorna la fecha del lunes.

    EXPLICACIÓN: El input type="week" del navegador envía valores como "2025-W18".
    Esta función convierte eso a una fecha de Python.

    Args:
        año (int): Año (ej: 2025)
        numero_semana (int): Número de semana ISO (1-53)

    Returns:
        date: Fecha del lunes de esa semana
    """
    # El día 1 de la semana ISO 1 del año
    primer_dia = date.fromisocalendar(año, numero_semana, 1)
    return primer_dia


# ===========================================================================
# CLASIFICACIÓN DE ÓRDENES
# ===========================================================================

def clasificar_tipo_equipo(detalle):
    """
    Clasifica un equipo en una de las 5 categorías del concentrado.

    EXPLICACIÓN PARA PRINCIPIANTES:
    La función revisa los campos del equipo en este orden de prioridad:
      1. Si es OOW/FL → categoría OOW (aunque sea Dell o Lenovo)
      2. Si es MIS + Dell → MIS DELL
      3. Si es MIS + Lenovo → MIS LENOVO
      4. Si la marca es Dell → DELL
      5. Si la marca es Lenovo → LENOVO
      6. Todo lo demás → OOW (otras marcas que no son OOW/FL ni MIS)

    Args:
        detalle (DetalleEquipo): Objeto con marca, es_mis y orden_cliente

    Returns:
        str: Uno de los valores en TIPOS_EQUIPO, o None si no aplica
    """
    orden_cliente = (detalle.orden_cliente or '').upper().strip()
    es_oow_fl = orden_cliente.startswith('OOW-') or orden_cliente.startswith('FL-')
    es_mis = getattr(detalle, 'es_mis', False)
    marca = (detalle.marca or '').strip()

    # Las órdenes OOW/FL tienen prioridad sobre marca
    if es_oow_fl:
        return 'OOW'

    # MIS tiene prioridad sobre marca normal
    if es_mis and marca == 'Dell':
        return 'MIS DELL'
    if es_mis and marca == 'Lenovo':
        return 'MIS LENOVO'

    # Marcas principales (sin MIS)
    if marca == 'Lenovo':
        return 'LENOVO'
    if marca == 'Dell':
        return 'DELL'

    # Cualquier otra marca (HP, Asus, etc.) va a OOW
    return 'OOW'


def clasificar_sitio(nombre_sucursal):
    """
    Clasifica una sucursal en DROP OFF o SATELITE.

    EXPLICACIÓN: Revisa si el nombre de la sucursal contiene palabras clave.
    Es case-insensitive (no importa si tiene mayúsculas o minúsculas).
    Si no coincide con ninguna, retorna None (se ignora en el conteo).

    Args:
        nombre_sucursal (str): Nombre de la sucursal

    Returns:
        str: 'DROP OFF', 'SATELITE', o None
    """
    nombre = (nombre_sucursal or '').lower()

    if 'drop' in nombre:
        return 'DROP OFF'
    if 'satelit' in nombre:
        return 'SATELITE'

    return None


# ===========================================================================
# ESTRUCTURA DE DATOS VACÍA (PLANTILLA)
# ===========================================================================

def crear_estructura_vacia():
    """
    Crea la estructura de datos vacía para el concentrado.

    EXPLICACIÓN: Antes de llenar los datos reales, necesitamos una estructura
    con todos los contadores en cero. Así no tenemos que manejar errores por
    claves que no existen.

    La estructura es:
        {
          'DROP OFF': {
            'LENOVO': {'Lunes': 0, 'Martes': 0, ..., 'total': 0},
            'DELL':   {'Lunes': 0, ...},
            ...
          },
          'SATELITE': { ... }
        }

    Returns:
        dict: Estructura anidada con contadores en cero
    """
    estructura = {}
    for sitio in SITIOS:
        estructura[sitio] = {}
        for tipo in TIPOS_EQUIPO:
            estructura[sitio][tipo] = {dia: 0 for dia in DIAS_SEMANA}
            estructura[sitio][tipo]['total'] = 0

    return estructura


def crear_estructura_ingenieros_vacia(ingenieros):
    """
    Crea la estructura de datos vacía para la sección de asignación a ingeniería.

    Args:
        ingenieros (list): Lista de objetos Empleado

    Returns:
        dict: {empleado_id: {'nombre': str, 'Lunes': 0, ..., 'total': 0}}
    """
    estructura = {}
    for ing in ingenieros:
        estructura[ing.id] = {
            'nombre': ing.nombre_completo,
            'Lunes': 0,
            'Martes': 0,
            'Miércoles': 0,
            'Jueves': 0,
            'Viernes': 0,
            'total': 0,
        }
    return estructura


# ===========================================================================
# CONSULTA PRINCIPAL: CONCENTRADO SEMANAL
# ===========================================================================

def obtener_concentrado_semanal(lunes, sucursal_id=None, sucursal_ids=None):
    """
    Calcula los datos completos del concentrado para una semana.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta es la función principal. Recibe la fecha del lunes de la semana
    que queremos analizar y devuelve todos los datos necesarios para
    mostrar el concentrado en pantalla.

    El proceso:
      1. Calcula el rango de fechas (lunes a viernes)
      2. Consulta la BD filtrando órdenes en ese rango
      3. Clasifica cada orden por sitio y tipo de equipo
      4. Cuenta por día de la semana
      5. Calcula totales y promedios
      6. Repite el proceso para ingresos, asignaciones y egresos

    Args:
        lunes (date): Fecha del lunes de la semana a analizar
        sucursal_id (int, optional): Filtrar por sucursal específica. Si es None, muestra todas.
        sucursal_ids (list, optional): Lista de IDs para filtrar por grupo de sucursales.

    Returns:
        dict: Diccionario completo con todos los datos del concentrado:
            - ingreso: tabla de ingresos por sitio/tipo/día
            - asignacion: tabla de asignaciones por ingeniero/día
            - egreso: tabla de egresos por sitio/tipo/día
            - resumen_ingreso: totales de carry-in, MIS, etc.
            - totales_ingreso: fila de totales generales
            - totales_egreso: fila de totales generales
            - lunes, viernes: fechas del rango
            - numero_semana: número ISO de la semana
            - año: año de la semana
    """
    lunes, viernes = obtener_rango_semana(lunes)
    numero_semana = obtener_numero_semana(lunes)
    año = lunes.year

    # -----------------------------------------------------------------------
    # BASE QUERIES: Órdenes en el rango de la semana
    # -----------------------------------------------------------------------
    base_qs = OrdenServicio.objects.select_related(
        'detalle_equipo',
        'sucursal',
        'tecnico_asignado_actual',
    ).filter(
        # Solo ordenes de días hábiles (Lun-Vie)
        # date__range incluye ambos extremos
        fecha_ingreso__date__range=(lunes, viernes),
        fecha_ingreso__week_day__in=[2, 3, 4, 5, 6],  # Django: 1=Dom, 2=Lun, ..., 6=Vie
    )

    qs_egreso = OrdenServicio.objects.select_related(
        'detalle_equipo',
        'sucursal',
        'tecnico_asignado_actual',
    ).filter(
        fecha_entrega__date__range=(lunes, viernes),
        fecha_entrega__week_day__in=[2, 3, 4, 5, 6],
    )

    # Filtro adicional por sucursal (individual o grupo)
    if sucursal_ids:
        base_qs = base_qs.filter(sucursal_id__in=sucursal_ids)
        qs_egreso = qs_egreso.filter(sucursal_id__in=sucursal_ids)
    elif sucursal_id:
        base_qs = base_qs.filter(sucursal_id=sucursal_id)
        qs_egreso = qs_egreso.filter(sucursal_id=sucursal_id)

    # Excluir órdenes canceladas del conteo
    base_qs = base_qs.exclude(estado='cancelado')
    qs_egreso = qs_egreso.exclude(estado='cancelado')

    # -----------------------------------------------------------------------
    # SECCIÓN 1: INGRESO DE EQUIPOS
    # -----------------------------------------------------------------------
    datos_ingreso = crear_estructura_vacia()

    # Contadores para la fila de resumen inferior
    carry_in_dropoff = 0
    carry_in_sic = 0
    mail_in_service = 0

    for orden in base_qs:
        if not hasattr(orden, 'detalle_equipo') or orden.detalle_equipo is None:
            continue

        detalle = orden.detalle_equipo
        sitio = clasificar_sitio(orden.sucursal.nombre)
        if sitio is None:
            continue

        tipo = clasificar_tipo_equipo(detalle)
        if tipo is None:
            continue

        # Día de la semana (weekday() retorna 0=Lunes, ..., 4=Viernes)
        dia_idx = orden.fecha_ingreso.weekday()
        if dia_idx > 4:  # Ignorar sábado y domingo
            continue
        dia_nombre = DIAS_SEMANA[dia_idx]

        # Incrementar contador
        datos_ingreso[sitio][tipo][dia_nombre] += 1
        datos_ingreso[sitio][tipo]['total'] += 1

        # Clasificar para resumen carry-in / mail-in
        es_mis = getattr(detalle, 'es_mis', False)
        if es_mis:
            mail_in_service += 1
        elif sitio == 'DROP OFF':
            carry_in_dropoff += 1
        elif sitio == 'SATELITE':
            carry_in_sic += 1

    # Calcular promedios de ingreso
    for sitio in SITIOS:
        for tipo in TIPOS_EQUIPO:
            dias_con_datos = sum(
                1 for dia in DIAS_SEMANA
                if datos_ingreso[sitio][tipo][dia] > 0
            )
            total = datos_ingreso[sitio][tipo]['total']
            datos_ingreso[sitio][tipo]['promedio'] = (
                round(total / 5, 1)  # Siempre sobre 5 días hábiles
            )

    # Totales por día y general para ingreso
    totales_ingreso = {dia: 0 for dia in DIAS_SEMANA}
    totales_ingreso['total'] = 0
    for sitio in SITIOS:
        for tipo in TIPOS_EQUIPO:
            for dia in DIAS_SEMANA:
                totales_ingreso[dia] += datos_ingreso[sitio][tipo][dia]
            totales_ingreso['total'] += datos_ingreso[sitio][tipo]['total']
    totales_ingreso['promedio'] = round(totales_ingreso['total'] / 5, 1)

    # -----------------------------------------------------------------------
    # SECCIÓN 2: ASIGNACIÓN DE EQUIPOS A INGENIERÍA
    # -----------------------------------------------------------------------
    # Obtenemos todos los técnicos que tienen órdenes en esa semana
    from inventario.models import Empleado

    tecnicos_ids = base_qs.values_list(
        'tecnico_asignado_actual_id', flat=True
    ).distinct()
    tecnicos = Empleado.objects.filter(id__in=tecnicos_ids).order_by('nombre_completo')

    datos_asignacion = crear_estructura_ingenieros_vacia(tecnicos)

    for orden in base_qs:
        tec = orden.tecnico_asignado_actual
        if tec is None or tec.id not in datos_asignacion:
            continue

        dia_idx = orden.fecha_ingreso.weekday()
        if dia_idx > 4:
            continue
        dia_nombre = DIAS_SEMANA[dia_idx]

        datos_asignacion[tec.id][dia_nombre] += 1
        datos_asignacion[tec.id]['total'] += 1

    # Agregar fila de "Candidatos RHITSO" (órdenes marcadas como candidatas a laboratorio externo)
    rhitso_fila = {dia: 0 for dia in DIAS_SEMANA}
    rhitso_fila['nombre'] = 'Candidatos RHITSO'
    rhitso_fila['total'] = 0
    candidatos_rhitso = base_qs.filter(es_candidato_rhitso=True)
    for orden in candidatos_rhitso:
        dia_idx = orden.fecha_ingreso.weekday()
        if dia_idx > 4:
            continue
        dia_nombre = DIAS_SEMANA[dia_idx]
        rhitso_fila[dia_nombre] += 1
        rhitso_fila['total'] += 1

    # Convertir diccionario a lista ordenada por total (desc)
    lista_asignacion = sorted(
        datos_asignacion.values(),
        key=lambda x: x['total'],
        reverse=True
    )
    lista_asignacion.append(rhitso_fila)

    # Total general de asignación (total global y por día)
    total_asignados = sum(row['total'] for row in lista_asignacion)
    totales_asignacion = {dia: sum(row[dia] for row in lista_asignacion) for dia in DIAS_SEMANA}
    totales_asignacion['total'] = total_asignados

    # -----------------------------------------------------------------------
    # SECCIÓN 3: EGRESO DE EQUIPOS
    # -----------------------------------------------------------------------
    datos_egreso = crear_estructura_vacia()

    for orden in qs_egreso:
        if not hasattr(orden, 'detalle_equipo') or orden.detalle_equipo is None:
            continue

        detalle = orden.detalle_equipo
        sitio = clasificar_sitio(orden.sucursal.nombre)
        if sitio is None:
            continue

        tipo = clasificar_tipo_equipo(detalle)
        if tipo is None:
            continue

        dia_idx = orden.fecha_entrega.weekday()
        if dia_idx > 4:
            continue
        dia_nombre = DIAS_SEMANA[dia_idx]

        datos_egreso[sitio][tipo][dia_nombre] += 1
        datos_egreso[sitio][tipo]['total'] += 1

    # Promedios de egreso
    for sitio in SITIOS:
        for tipo in TIPOS_EQUIPO:
            total = datos_egreso[sitio][tipo]['total']
            datos_egreso[sitio][tipo]['promedio'] = round(total / 5, 1)

    # Totales por día y general para egreso
    totales_egreso = {dia: 0 for dia in DIAS_SEMANA}
    totales_egreso['total'] = 0
    for sitio in SITIOS:
        for tipo in TIPOS_EQUIPO:
            for dia in DIAS_SEMANA:
                totales_egreso[dia] += datos_egreso[sitio][tipo][dia]
            totales_egreso['total'] += datos_egreso[sitio][tipo]['total']
    totales_egreso['promedio'] = round(totales_egreso['total'] / 5, 1)

    # Determinar qué tipos mostrar por sitio:
    # DROP OFF: ocultar MIS DELL y MIS LENOVO si no tienen datos en la semana
    # SATELITE: siempre mostrar todos los tipos
    TIPOS_MIS = {'MIS DELL', 'MIS LENOVO'}
    tipos_visibles_por_sitio = {}
    for sitio in SITIOS:
        if sitio == 'DROP OFF':
            tipos_visibles_por_sitio[sitio] = [
                tipo for tipo in TIPOS_EQUIPO
                if tipo not in TIPOS_MIS or datos_ingreso[sitio][tipo]['total'] > 0
            ]
        else:
            tipos_visibles_por_sitio[sitio] = list(TIPOS_EQUIPO)

    return {
        'ingreso': datos_ingreso,
        'asignacion': lista_asignacion,
        'egreso': datos_egreso,
        'totales_ingreso': totales_ingreso,
        'totales_egreso': totales_egreso,
        'total_asignados': total_asignados,
        'totales_asignacion': totales_asignacion,
        'carry_in_dropoff': carry_in_dropoff,
        'carry_in_sic': carry_in_sic,
        'mail_in_service': mail_in_service,
        'lunes': lunes,
        'viernes': viernes,
        'numero_semana': numero_semana,
        'año': año,
        'dias_semana': DIAS_SEMANA,
        'sitios': SITIOS,
        'tipos_equipo': TIPOS_EQUIPO,
        'tipos_visibles_por_sitio': tipos_visibles_por_sitio,
    }


# ===========================================================================
# DATOS PARA GRÁFICOS: TENDENCIA SEMANAL
# ===========================================================================

def obtener_tendencia_semanal(año, sucursal_id=None, sucursal_ids=None):
    """
    Calcula los totales de ingresos y egresos por semana para todo el año.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta función genera los datos para los dos gráficos de línea:
    "Ingresos por semana" y "Egresos por semana".
    Recorre todas las semanas del año y cuenta cuántos equipos entraron/salieron.

    Args:
        año (int): Año a analizar (ej: 2025)
        sucursal_id (int, optional): Filtrar por sucursal individual.
        sucursal_ids (list, optional): Lista de IDs para filtrar por grupo de sucursales.

    Returns:
        dict: {
            'semanas': [1, 2, 3, ...],
            'etiquetas': ['S1', 'S2', ...],
            'ingresos': [12, 8, 15, ...],
            'egresos': [10, 9, 14, ...],
        }
    """
    # Rango del año completo
    inicio_año = date(año, 1, 1)
    fin_año = date(año, 12, 31)

    # Query base de ingresos
    qs_ingresos = OrdenServicio.objects.filter(
        fecha_ingreso__year=año,
        fecha_ingreso__week_day__in=[2, 3, 4, 5, 6],
    ).exclude(estado='cancelado')

    # Query base de egresos
    qs_egresos = OrdenServicio.objects.filter(
        fecha_entrega__year=año,
        fecha_entrega__week_day__in=[2, 3, 4, 5, 6],
    ).exclude(estado='cancelado')

    if sucursal_ids:
        qs_ingresos = qs_ingresos.filter(sucursal_id__in=sucursal_ids)
        qs_egresos = qs_egresos.filter(sucursal_id__in=sucursal_ids)
    elif sucursal_id:
        qs_ingresos = qs_ingresos.filter(sucursal_id=sucursal_id)
        qs_egresos = qs_egresos.filter(sucursal_id=sucursal_id)

    # Contar por semana usando anotación
    from django.db.models.functions import ExtractWeek
    from django.db.models import Count

    ingresos_por_semana = dict(
        qs_ingresos.annotate(semana_num=ExtractWeek('fecha_ingreso'))
        .values('semana_num')
        .annotate(total=Count('id'))
        .values_list('semana_num', 'total')
    )

    egresos_por_semana = dict(
        qs_egresos.annotate(semana_num=ExtractWeek('fecha_entrega'))
        .values('semana_num')
        .annotate(total=Count('id'))
        .values_list('semana_num', 'total')
    )

    # Generar lista de semanas del año
    semanas = []
    etiquetas = []
    ingresos = []
    egresos = []

    semana_actual = inicio_año
    while semana_actual <= fin_año:
        num_semana = semana_actual.isocalendar()[1]
        # Evitar duplicar la semana 1 del año siguiente
        if semana_actual.month == 1 and num_semana > 50:
            semana_actual += timedelta(days=7)
            continue

        semanas.append(num_semana)
        etiquetas.append(f'S{num_semana}')
        ingresos.append(ingresos_por_semana.get(num_semana, 0))
        egresos.append(egresos_por_semana.get(num_semana, 0))

        # Avanzar a la siguiente semana (cada 7 días)
        semana_actual += timedelta(days=7)

    return {
        'semanas': semanas,
        'etiquetas': etiquetas,
        'ingresos': ingresos,
        'egresos': egresos,
    }


# ===========================================================================
# DATOS PARA REPORTE TRIMESTRAL
# ===========================================================================

def obtener_reporte_trimestral(año, sucursal_id=None):
    """
    Calcula el concentrado acumulado por quarter (Q1, Q2, Q3, Q4).

    EXPLICACIÓN PARA PRINCIPIANTES:
    En lugar de ver una semana, este reporte muestra los totales acumulados
    de todo el trimestre. La estructura es la misma que el concentrado semanal
    pero los números representan todo el período Q1 (Ene-Mar), etc.

    Args:
        año (int): Año a analizar (ej: 2025)
        sucursal_id (int, optional): Filtrar por sucursal

    Returns:
        dict: {
            'Q1': {'nombre': 'Q1 (Ene - Mar)', 'ingreso': {...}, 'egreso': {...}, 'total_ingreso': N, 'total_egreso': N},
            'Q2': {...},
            'Q3': {...},
            'Q4': {...},
        }
    """
    resultado = {}

    for q_key, q_info in QUARTERS.items():
        meses = q_info['meses']

        # Órdenes ingresadas en los meses del quarter
        qs_ingreso = OrdenServicio.objects.select_related(
            'detalle_equipo', 'sucursal'
        ).filter(
            fecha_ingreso__year=año,
            fecha_ingreso__month__in=meses,
        ).exclude(estado='cancelado')

        # Órdenes egresadas en los meses del quarter
        qs_egreso = OrdenServicio.objects.select_related(
            'detalle_equipo', 'sucursal'
        ).filter(
            fecha_entrega__year=año,
            fecha_entrega__month__in=meses,
        ).exclude(estado='cancelado')

        if sucursal_id:
            qs_ingreso = qs_ingreso.filter(sucursal_id=sucursal_id)
            qs_egreso = qs_egreso.filter(sucursal_id=sucursal_id)

        # Conteos de ingreso por sitio y tipo
        ingreso_q = _contar_por_sitio_tipo(qs_ingreso)
        egreso_q = _contar_por_sitio_tipo(qs_egreso)

        # Total general del quarter
        total_ingreso = sum(
            ingreso_q[s][t]
            for s in SITIOS
            for t in TIPOS_EQUIPO
        )
        total_egreso = sum(
            egreso_q[s][t]
            for s in SITIOS
            for t in TIPOS_EQUIPO
        )

        resultado[q_key] = {
            'nombre': q_info['nombre'],
            'ingreso': ingreso_q,
            'egreso': egreso_q,
            'total_ingreso': total_ingreso,
            'total_egreso': total_egreso,
        }

    return resultado


# ===========================================================================
# DATOS PARA REPORTE MENSUAL
# ===========================================================================

# Nombres de mes en español
NOMBRES_MESES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}


def obtener_reporte_mensual(año, sucursal_id=None, sucursal_ids=None):
    """
    Calcula totales de ingreso y egreso por cada mes del año, agrupados por quarter.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Mientras que el reporte trimestral agrupa todo un quarter (3 meses) en un solo número,
    este reporte desglosa mes a mes para que se pueda ver la tendencia dentro del quarter.
    Sirve para construir la hoja 'Reporte Mensual' del Excel con tabla + gráficas.

    Args:
        año (int): Año a analizar (ej: 2025)
        sucursal_id (int, optional): Filtrar por una sucursal específica
        sucursal_ids (list, optional): Filtrar por lista de sucursales (grupos)

    Returns:
        dict: {
            'año': int,
            'Q1': {
                'nombre': 'Q1 (Ene - Mar)',
                'color': '0d6efd',
                'meses': [
                    {'mes': 1, 'nombre': 'Enero',   'ingreso': N, 'egreso': N},
                    {'mes': 2, 'nombre': 'Febrero',  'ingreso': N, 'egreso': N},
                    {'mes': 3, 'nombre': 'Marzo',    'ingreso': N, 'egreso': N},
                ],
                'total_ingreso': N,
                'total_egreso':  N,
            },
            'Q2': { ... },
            'Q3': { ... },
            'Q4': { ... },
            'meses_lista': [
                # lista plana de los 12 meses (para construir la gráfica fácilmente)
                {'mes': 1, 'nombre': 'Enero', 'ingreso': N, 'egreso': N},
                ...
            ],
        }
    """
    # Colores por quarter (mismos que en la hoja trimestral del Excel)
    COLORES_QUARTER = {
        'Q1': '0d6efd',   # Azul
        'Q2': '198754',   # Verde
        'Q3': 'dc3545',   # Rojo
        'Q4': 'fd7e14',   # Naranja
    }

    resultado = {'año': año}
    meses_lista = []

    for q_key, q_info in QUARTERS.items():
        meses_del_quarter = []
        total_ingreso_q = 0
        total_egreso_q = 0

        for mes in q_info['meses']:
            # ----- Ingreso del mes -----
            qs_ingreso = OrdenServicio.objects.filter(
                fecha_ingreso__year=año,
                fecha_ingreso__month=mes,
            ).exclude(estado='cancelado')

            # ----- Egreso del mes -----
            qs_egreso = OrdenServicio.objects.filter(
                fecha_entrega__year=año,
                fecha_entrega__month=mes,
            ).exclude(estado='cancelado')

            # ----- Aplicar filtros de sucursal -----
            if sucursal_ids:
                qs_ingreso = qs_ingreso.filter(sucursal_id__in=sucursal_ids)
                qs_egreso = qs_egreso.filter(sucursal_id__in=sucursal_ids)
            elif sucursal_id:
                qs_ingreso = qs_ingreso.filter(sucursal_id=sucursal_id)
                qs_egreso = qs_egreso.filter(sucursal_id=sucursal_id)

            conteo_ingreso = qs_ingreso.count()
            conteo_egreso = qs_egreso.count()

            total_ingreso_q += conteo_ingreso
            total_egreso_q += conteo_egreso

            dato_mes = {
                'mes': mes,
                'nombre': NOMBRES_MESES[mes],
                'ingreso': conteo_ingreso,
                'egreso': conteo_egreso,
            }
            meses_del_quarter.append(dato_mes)
            meses_lista.append(dato_mes)

        resultado[q_key] = {
            'nombre': q_info['nombre'],
            'color': COLORES_QUARTER[q_key],
            'meses': meses_del_quarter,
            'total_ingreso': total_ingreso_q,
            'total_egreso': total_egreso_q,
        }

    resultado['meses_lista'] = meses_lista
    return resultado


def _contar_por_sitio_tipo(queryset):
    """
    Función auxiliar: cuenta órdenes agrupadas por sitio y tipo de equipo.

    EXPLICACIÓN: Itera el queryset y acumula contadores en una estructura
    {sitio: {tipo: conteo}}. Se usa tanto para el reporte trimestral como
    para otras funciones que necesiten este agrupamiento sin desglose diario.

    Args:
        queryset: QuerySet de OrdenServicio con select_related a detalle_equipo y sucursal

    Returns:
        dict: {sitio: {tipo: total}}
    """
    conteos = {sitio: {tipo: 0 for tipo in TIPOS_EQUIPO} for sitio in SITIOS}

    for orden in queryset:
        if not hasattr(orden, 'detalle_equipo') or orden.detalle_equipo is None:
            continue

        detalle = orden.detalle_equipo
        sitio = clasificar_sitio(orden.sucursal.nombre)
        if sitio is None:
            continue

        tipo = clasificar_tipo_equipo(detalle)
        if tipo is None:
            continue

        conteos[sitio][tipo] += 1

    return conteos
