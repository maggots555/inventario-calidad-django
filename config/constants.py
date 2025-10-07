"""
Constantes compartidas entre aplicaciones Django
Mantiene consistencia en choices y valores entre diferentes apps
"""

# ============================================================================
# TIPOS DE EQUIPO - Usado por ScoreCard y Servicio Técnico
# ============================================================================
TIPO_EQUIPO_CHOICES = [
    ('pc', 'PC'),
    ('laptop', 'Laptop'),
    ('aio', 'AIO (All-in-One)'),
]

# ============================================================================
# MARCAS COMUNES DE EQUIPOS - Para autocompletado y estandarización
# ============================================================================
MARCAS_EQUIPOS = [
    'HP',
    'Dell',
    'Lenovo',
    'Acer',
    'Asus',
    'MSI',
    'Apple',
    'Samsung',
    'Toshiba',
    'Sony',
    'Compaq',
    'Gateway',
    'Alienware',
]

# ============================================================================
# GAMAS DE EQUIPOS - Clasificación por calidad/precio
# ============================================================================
GAMA_EQUIPO_CHOICES = [
    ('alta', 'Gama Alta'),
    ('media', 'Gama Media'),
    ('baja', 'Gama Baja'),
]

# ============================================================================
# ESTADOS DE ORDEN DE SERVICIO - Workflow completo
# ============================================================================
ESTADO_ORDEN_CHOICES = [
    ('espera', 'En Espera'),
    ('recepcion', 'En Recepción'),
    ('diagnostico', 'En Diagnóstico'),
    ('cotizacion', 'Esperando Aprobación Cliente'),
    ('rechazada', 'Cotización Rechazada'),
    ('esperando_piezas', 'Esperando Llegada de Piezas'),
    ('reparacion', 'En Reparación'),
    ('control_calidad', 'Control de Calidad'),
    ('finalizado', 'Finalizado - Listo para Entrega'),
    ('entregado', 'Entregado al Cliente'),
    ('cancelado', 'Cancelado'),
]

# ============================================================================
# PAQUETES DE VENTA MOSTRADOR - Servicios adicionales
# ============================================================================
PAQUETES_CHOICES = [
    ('oro', 'Paquete Oro'),
    ('plata', 'Paquete Plata'),
    ('bronce', 'Paquete Bronce'),
    ('ninguno', 'Sin Paquete'),
]

# Precios fijos de paquetes (en pesos mexicanos)
PRECIOS_PAQUETES = {
    'oro': 1500.00,
    'plata': 1000.00,
    'bronce': 500.00,
    'ninguno': 0.00,
}

# Descripción de cada paquete
DESCRIPCION_PAQUETES = {
    'oro': 'Limpieza profunda + Aplicación de pasta térmica premium + Optimización de sistema + Garantía extendida 6 meses',
    'plata': 'Limpieza profunda + Aplicación de pasta térmica + Optimización de sistema + Garantía 3 meses',
    'bronce': 'Limpieza básica + Aplicación de pasta térmica + Garantía 1 mes',
    'ninguno': 'Sin paquete adicional',
}

# ============================================================================
# TIPO DE IMÁGENES - Para clasificación de evidencias
# ============================================================================
TIPO_IMAGEN_CHOICES = [
    ('ingreso', 'Ingreso - Estado Inicial'),
    ('diagnostico', 'Durante Diagnóstico'),
    ('reparacion', 'Durante Reparación'),
    ('egreso', 'Egreso - Estado Final'),
    ('otras', 'Otras'),
]

# ============================================================================
# TIPO DE EVENTOS EN HISTORIAL - Para tracking de cambios
# ============================================================================
TIPO_EVENTO_CHOICES = [
    ('creacion', 'Creación de Orden'),
    ('cambio_estado', 'Cambio de Estado'),
    ('cambio_tecnico', 'Cambio de Técnico Asignado'),
    ('comentario', 'Comentario de Usuario'),
    ('sistema', 'Evento del Sistema'),
    ('imagen', 'Subida de Imagen'),
    ('cotizacion', 'Evento de Cotización'),
    ('pieza', 'Evento de Pieza'),
]

# ============================================================================
# MOTIVOS DE RECHAZO - Para cotizaciones rechazadas
# ============================================================================
MOTIVO_RECHAZO_COTIZACION = [
    ('costo_alto', 'Costo muy elevado'),
    ('muchas_piezas', 'Demasiadas piezas a cambiar'),
    ('tiempo_largo', 'Tiempo de reparación muy largo'),
    ('falta_justificacion', 'Falta de justificación en diagnóstico'),
    ('no_vale_pena', 'No vale la pena reparar'),
    ('otro', 'Otro motivo'),
]

# ============================================================================
# ESTADOS DE SEGUIMIENTO DE PIEZAS
# ============================================================================
ESTADO_PIEZA_CHOICES = [
    ('pedido', 'Pedido Realizado'),
    ('confirmado', 'Pedido Confirmado'),
    ('transito', 'En Tránsito'),
    ('retrasado', 'Retrasado'),
    ('recibido', 'Recibido en Sucursal'),
]

# ============================================================================
# MOTIVOS PARA RHITSO (Reparación Especializada)
# ============================================================================
MOTIVO_RHITSO_CHOICES = [
    ('reballing', 'Requiere Reballing de GPU/CPU'),
    ('soldadura', 'Soldadura especializada en placa'),
    ('componente_smd', 'Reemplazo de componentes SMD'),
    ('corrosion', 'Corrosión severa en placa'),
    ('cortocircuito', 'Cortocircuito en circuitería'),
    ('diagnostico_profundo', 'Requiere diagnóstico más profundo'),
    ('otro', 'Otro motivo especializado'),
]

# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def obtener_precio_paquete(codigo_paquete):
    """
    Retorna el precio de un paquete dado su código
    
    Args:
        codigo_paquete (str): Código del paquete ('oro', 'plata', 'bronce', 'ninguno')
    
    Returns:
        float: Precio del paquete
    """
    return PRECIOS_PAQUETES.get(codigo_paquete, 0.00)


def obtener_descripcion_paquete(codigo_paquete):
    """
    Retorna la descripción de un paquete dado su código
    
    Args:
        codigo_paquete (str): Código del paquete
    
    Returns:
        str: Descripción del paquete
    """
    return DESCRIPCION_PAQUETES.get(codigo_paquete, 'Sin descripción')


def obtener_nombre_estado(codigo_estado):
    """
    Retorna el nombre legible de un estado de orden
    
    Args:
        codigo_estado (str): Código del estado
    
    Returns:
        str: Nombre del estado
    """
    for codigo, nombre in ESTADO_ORDEN_CHOICES:
        if codigo == codigo_estado:
            return nombre
    return 'Estado Desconocido'
