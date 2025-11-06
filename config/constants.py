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
# MARCAS COMUNES DE EQUIPOS - Para dropdown obligatorio
# ============================================================================
MARCAS_EQUIPOS_CHOICES = [
    ('', '-- Seleccione una marca --'),  # Opción vacía para validación
    ('acer', 'Acer'),
    ('apple', 'Apple'),
    ('asus', 'Asus'),
    ('compaq', 'Compaq'),
    ('dell', 'Dell'),
    ('gateway', 'Gateway'),
    ('hp', 'HP'),
    ('huawei', 'Huawei'),
    ('lenovo', 'Lenovo'),
    ('msi', 'MSI'),
    ('samsung', 'Samsung'),
    ('sony', 'Sony'),
    ('toshiba', 'Toshiba'),
    ('otra', 'Otra Marca'),
]

# Lista simple de marcas (para compatibilidad con código existente)
MARCAS_EQUIPOS = [marca[1] for marca in MARCAS_EQUIPOS_CHOICES if marca[0]]

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
# Actualizado: Octubre 2025 - Se agregaron 10 nuevos estados (de 11 a 21)
# ============================================================================
ESTADO_ORDEN_CHOICES = [
    # === FASE 1: INGRESO Y DIAGNÓSTICO ===
    ('espera', 'En Espera'),
    ('recepcion', 'En Recepción'),
    ('diagnostico', 'En Diagnóstico'),
    ('equipo_diagnosticado', 'Equipo Diagnosticado'),  # NUEVO - Oct 2025
    ('diagnostico_enviado_cliente', 'Diagnóstico Enviado al Cliente'),  # NUEVO - Oct 2025
    
    # === FASE 2: COTIZACIÓN Y APROBACIÓN ===
    ('cotizacion_enviada_proveedor', 'Envío de Cotización al Proveedor'),  # NUEVO - Oct 2025
    ('cotizacion_recibida_proveedor', 'Se Recibe Cotización de Proveedores'),  # NUEVO - Oct 2025
    ('cotizacion', 'Esperando Aprobación Cliente'),
    ('cliente_acepta_cotizacion', 'Cliente Acepta Cotización'),  # NUEVO - Oct 2025
    ('rechazada', 'Cotización Rechazada'),
    
    # === FASE 3: GESTIÓN DE PIEZAS Y COMPONENTES ===
    ('partes_solicitadas_proveedor', 'Partes Solicitadas a Proveedor'),  # NUEVO - Oct 2025
    ('esperando_piezas', 'Esperando Llegada de Piezas'),
    ('piezas_recibidas', 'Piezas Recibidas'),  # NUEVO - Oct 2025
    ('wpb_pieza_incorrecta', 'WPB - Pieza Incorrecta'),  # NUEVO - Oct 2025
    ('doa_pieza_danada', 'DOA - Pieza Dañada'),  # NUEVO - Oct 2025
    ('pnc_parte_no_disponible', 'PNC - Parte No Disponible'),  # NUEVO - Oct 2025
    
    # === FASE 4: REPARACIÓN Y ENTREGA ===
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
    ('autorizacion', 'Autorización/Pass - RHITSO'),
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
    ('no_hay_partes', 'No hay partes en el mercado'),
    ('solo_venta_mostrador', 'Solo está interesado en la propuesta de venta mostrador'),
    ('falta_de_respuesta', 'Se cierra cotización por vigencia y falta de respuesta del cliente'),
    ('rechazo_sin_decision', 'Cliente desea evaluar las opciones sin tomar decisión inmediata'),
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


# ============================================================================
# MÓDULO RHITSO - Sistema de Seguimiento Especializado
# ============================================================================

# RESPONSABLES DE ESTADOS RHITSO
OWNER_RHITSO_CHOICES = [
    ('SIC', 'SIC - Sistema de Información del Cliente'),
    ('RHITSO', 'RHITSO - Centro de Reparación Especializada'),
    ('CLIENTE', 'Cliente - Usuario Final'),
    ('COMPRAS', 'Compras - Departamento de Adquisiciones'),
    ('CERRADO', 'Cerrado - Proceso Finalizado'),
]

# COMPLEJIDAD DE REPARACIONES
COMPLEJIDAD_CHOICES = [
    ('BAJA', 'Baja - Reparación simple'),
    ('MEDIA', 'Media - Complejidad moderada'),
    ('ALTA', 'Alta - Requiere experiencia especializada'),
    ('CRITICA', 'Crítica - Máxima complejidad técnica'),
]

# GRAVEDAD DE INCIDENCIAS
GRAVEDAD_INCIDENCIA_CHOICES = [
    ('BAJA', 'Baja - Sin impacto significativo'),
    ('MEDIA', 'Media - Impacto moderado'),
    ('ALTA', 'Alta - Impacto considerable'),
    ('CRITICA', 'Crítica - Requiere atención inmediata'),
]

# ESTADO DE INCIDENCIAS
ESTADO_INCIDENCIA_CHOICES = [
    ('ABIERTA', 'Abierta - Sin resolver'),
    ('EN_REVISION', 'En Revisión - Siendo analizada'),
    ('RESUELTA', 'Resuelta - Acción completada'),
    ('CERRADA', 'Cerrada - Finalizada'),
]

# IMPACTO AL CLIENTE
IMPACTO_CLIENTE_CHOICES = [
    ('NINGUNO', 'Ninguno - Sin impacto'),
    ('BAJO', 'Bajo - Impacto mínimo'),
    ('MEDIO', 'Medio - Impacto moderado'),
    ('ALTO', 'Alto - Impacto significativo'),
]

# PRIORIDAD DE INCIDENCIAS
PRIORIDAD_CHOICES = [
    ('BAJA', 'Baja - Puede esperar'),
    ('MEDIA', 'Media - Atención normal'),
    ('ALTA', 'Alta - Requiere prioridad'),
    ('URGENTE', 'Urgente - Atención inmediata'),
]

# TIPOS DE CONFIGURACIÓN RHITSO
TIPO_CONFIG_CHOICES = [
    ('STRING', 'Texto'),
    ('INTEGER', 'Número Entero'),
    ('BOOLEAN', 'Booleano (Sí/No)'),
    ('JSON', 'JSON - Datos estructurados'),
]
