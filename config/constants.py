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
# Actualizado: Octubre 2025 - Nuevos paquetes Premium/Oro/Plata
# ============================================================================
PAQUETES_CHOICES = [
    ('premium', 'Solución Premium'),
    ('oro', 'Solución Oro'),
    ('plata', 'Solución Plata'),
    ('ninguno', 'Sin Paquete'),
]

# Precios fijos de paquetes (en pesos mexicanos, IVA incluido)
PRECIOS_PAQUETES = {
    'premium': 5500.00,  # RAM 16GB DDR5 + SSD 1TB + Kit Limpieza
    'oro': 3850.00,      # RAM 8GB DDR5 + SSD 1TB
    'plata': 2900.00,    # SSD 1TB
    'ninguno': 0.00,
}

# Descripción técnica detallada de cada paquete
DESCRIPCION_PAQUETES = {
    'premium': '''🏆 SOLUCIÓN PREMIUM - $5,500 IVA incluido
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ RAM 16GB DDR5 Samsung (4800-5600 MHz)
✅ SSD 1TB de alta velocidad
✅ Kit de Limpieza Profesional de REGALO
✅ Instalación y configuración incluida

*Ideal para gaming, diseño gráfico y edición de video''',
    
    'oro': '''🥇 SOLUCIÓN ORO - $3,850 IVA incluido
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ RAM 8GB DDR5 Samsung (3200 MHz)
✅ SSD 1TB de alta velocidad
✅ Instalación y configuración incluida

*Perfecto para trabajo de oficina y multitarea''',
    
    'plata': '''🥈 SOLUCIÓN PLATA - $2,900 IVA incluido
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ SSD 1TB de alta velocidad
✅ Instalación y configuración incluida

*Mejora el rendimiento general de tu equipo''',
    
    'ninguno': 'Sin paquete adicional - Servicios individuales',
}

# Componentes incluidos en cada paquete (para referencia de inventario)
# Usado para tracking de qué incluye cada paquete sin desglosa en ventas
COMPONENTES_PAQUETES = {
    'premium': [
        {'tipo': 'RAM', 'capacidad': '16GB', 'tecnologia': 'DDR5', 'velocidad': '4800-5600 MHz', 'marca': 'Samsung'},
        {'tipo': 'SSD', 'capacidad': '1TB', 'interfaz': 'NVMe/SATA'},
        {'tipo': 'Kit Limpieza', 'descripcion': 'Kit profesional de limpieza'},
    ],
    'oro': [
        {'tipo': 'RAM', 'capacidad': '8GB', 'tecnologia': 'DDR5', 'velocidad': '3200 MHz', 'marca': 'Samsung'},
        {'tipo': 'SSD', 'capacidad': '1TB', 'interfaz': 'NVMe/SATA'},
    ],
    'plata': [
        {'tipo': 'SSD', 'capacidad': '1TB', 'interfaz': 'NVMe/SATA'},
    ],
    'ninguno': [],
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


def obtener_componentes_paquete(codigo_paquete):
    """
    Retorna la lista de componentes incluidos en un paquete
    
    Args:
        codigo_paquete (str): Código del paquete ('premium', 'oro', 'plata', 'ninguno')
    
    Returns:
        list: Lista de diccionarios con información de componentes
    """
    return COMPONENTES_PAQUETES.get(codigo_paquete, [])


def paquete_genera_comision(codigo_paquete):
    """
    Determina si un paquete genera comisión para el responsable
    
    Args:
        codigo_paquete (str): Código del paquete
    
    Returns:
        bool: True si el paquete genera comisión (premium, oro, plata)
    """
    # Los paquetes premium, oro y plata siempre generan comisión
    return codigo_paquete in ['premium', 'oro', 'plata']
