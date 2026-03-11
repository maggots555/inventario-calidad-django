"""
Constantes compartidas entre aplicaciones Django
Mantiene consistencia en choices y valores entre diferentes apps
"""

# ============================================================================
# TIPOS DE EQUIPO - Usado por ScoreCard y Servicio Técnico
# ============================================================================
TIPO_EQUIPO_CHOICES = [
    ('', '-- Seleccione un tipo de equipo --'),  # Opción vacía para validación
    ('PC', 'PC'),
    ('Laptop', 'Laptop'),
    ('AIO', 'AIO (All-in-One)'),
]

# ============================================================================
# MARCAS COMUNES DE EQUIPOS - Para dropdown obligatorio
# ============================================================================
MARCAS_EQUIPOS_CHOICES = [
    ('', '-- Seleccione una marca --'),  # Opción vacía para validación
    ('Acer', 'Acer'),
    ('Apple', 'Apple'),
    ('Asus', 'Asus'),
    ('Compaq', 'Compaq'),
    ('Dell', 'Dell'),
    ('Gateway', 'Gateway'),
    ('Gigabyte', 'Gigabyte'),
    ('HP', 'HP'),
    ('Huawei', 'Huawei'),
    ('Lenovo', 'Lenovo'),
    ('MSI', 'MSI'),
    ('Samsung', 'Samsung'),
    ('Sony', 'Sony'),
    ('Toshiba', 'Toshiba'),
    ('Otra', 'Otra Marca'),
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
# Actualizado: Diciembre 2025 - Agregado estado 'almacen' para órdenes creadas desde Almacén
# ============================================================================
ESTADO_ORDEN_CHOICES = [
    # === FASE 0: ORIGEN ESPECIAL ===
    ('almacen', 'Proveniente de Almacén'),  # Orden creada automáticamente desde módulo Almacén
    
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
    'plata': 3870.00,    # SSD 1TB
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
    
    'oro': '''🥇 SOLUCIÓN ORO - $3,250 IVA incluido
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
# COMPONENTES PARA DIAGNÓSTICO - Orden del formato PDF de diagnóstico SIC
# ============================================================================
# EXPLICACIÓN PARA PRINCIPIANTES:
# Esta lista define los componentes que aparecen en el PDF de diagnóstico y en
# el modal de envío de diagnóstico al cliente. Cada tupla tiene:
#   - 'componente_db': Nombre del componente como está en ComponenteEquipo (BD)
#   - 'label_pdf': Nombre que se muestra en el PDF (formato oficial SIC)
#   - 'orden': Número de orden para la tabla del PDF
#
# El mapeo permite reutilizar el catálogo de ComponenteEquipo que ya existe
# pero mostrando los nombres en el formato oficial que el cliente espera.
COMPONENTES_DIAGNOSTICO_ORDEN = [
    {'componente_db': 'Motherboard',          'label_pdf': 'TARJETA (MOTHERBOARD)',  'orden': 1},
    {'componente_db': 'Pantalla',             'label_pdf': 'LCD Ó DISPLAY',          'orden': 2},
    {'componente_db': 'Disco Duro / SSD',     'label_pdf': 'DISCO DURO Ó SSD',       'orden': 3},
    {'componente_db': 'Teclado',              'label_pdf': 'TECLADO/PALMREST',       'orden': 4},
    {'componente_db': 'Cargador',             'label_pdf': 'ELIMINADOR(CARGADOR)',   'orden': 5},
    {'componente_db': 'Batería',              'label_pdf': 'BATERIA',                'orden': 6},
    {'componente_db': 'DC-IN',                'label_pdf': 'DC-IN',                  'orden': 7},
    {'componente_db': 'Botón',                'label_pdf': 'BOTÓN',                  'orden': 8},
    {'componente_db': 'WiFi / Bluetooth',     'label_pdf': 'ANTENAS',                'orden': 9},
    {'componente_db': 'Touchpad',             'label_pdf': 'TOUCH PAD',              'orden': 10},
    {'componente_db': 'Sistema Operativo',    'label_pdf': 'SISTEMA OPERATIVO',      'orden': 11},
    {'componente_db': 'Bisagras',             'label_pdf': 'BISAGRAS',               'orden': 12},
    {'componente_db': 'RAM',                  'label_pdf': 'MEMORIA RAM',            'orden': 13},
    {'componente_db': 'Ventilador / Cooling', 'label_pdf': 'VENTILADOR',             'orden': 14},
    {'componente_db': 'Carcasa / Chasis',     'label_pdf': 'PLASTICOS / BISEL',      'orden': 15},
    {'componente_db': 'Cable',                'label_pdf': 'CABLE',                  'orden': 16},
    {'componente_db': 'Webcam',               'label_pdf': 'CAMARA',                 'orden': 17},
    {'componente_db': 'Limpieza y mantenimiento', 'label_pdf': 'LIMPIEZA Y MANTENIMIENTO', 'orden': 18},
]

# ============================================================================
# TIPO DE IMÁGENES - Para clasificación de evidencias
# ============================================================================
TIPO_IMAGEN_CHOICES = [
    ('ingreso', 'Ingreso - Estado Inicial'),
    ('diagnostico', 'Durante Diagnóstico'),
    ('reparacion', 'Durante Reparación'),
    ('egreso', 'Egreso - Estado Final'),
    ('autorizacion', 'Autorización/Pass - RHITSO'),
    ('packing', 'Imágenes Packing'),
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
    ('no_apto', 'Equipo no apto para diagnóstico o reparación'),
    ('rechazo_sin_decision', 'Cliente desea evaluar las opciones sin tomar decisión inmediata'),
    ('no_especifica_motivo', 'Cliente no especifica motivo, únicamente rechaza la cotización'),
    ('no_autorizado_por_empresa', 'Cliente informa que su empresa no autoriza la reparación'),
    ('otro', 'Otro motivo'),
]

# ============================================================================
# ESTADOS DE SEGUIMIENTO DE PIEZAS
# Actualizado: Noviembre 2025 - Agregados estados para piezas problemáticas
# ============================================================================
ESTADO_PIEZA_CHOICES = [
    ('pedido', 'Pedido Realizado'),
    ('confirmado', 'Pedido Confirmado'),
    ('transito', 'En Tránsito'),
    ('retrasado', 'Retrasado'),
    ('recibido', 'Recibido en Sucursal'),
    ('incorrecto', 'WPB - Pieza Incorrecta'),  # Wrong Part Boxed
    ('danado', 'DOA - Pieza Dañada/No Funcional'),  # Dead On Arrival
]

# Clasificación de estados de piezas para lógica de seguimiento
# ESTADOS RECIBIDOS: Piezas que ya llegaron físicamente al centro (correctas o con problemas)
ESTADOS_PIEZA_RECIBIDOS = ['recibido', 'incorrecto', 'danado']

# ESTADOS PENDIENTES: Piezas que aún no han llegado físicamente
ESTADOS_PIEZA_PENDIENTES = ['pedido', 'confirmado', 'transito', 'retrasado']

# ESTADOS PROBLEMÁTICOS: Piezas recibidas pero con incidencias de calidad
ESTADOS_PIEZA_PROBLEMATICOS = ['incorrecto', 'danado']

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
    ('no_hay_piezas', 'No hay partes en el mercado'),
    ('daño_profundo_mobo', 'Daño profundo en placa madre'),
    ('sin_POST', 'No cumple protocolo POST básico'),
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

# ============================================================================
# PROVEEDORES DE PIEZAS - Lista predefinida para cotizaciones (Noviembre 2025)
# ============================================================================
# Lista de proveedores comunes para selección en cotizaciones de piezas
# Esta lista aparece como dropdown en el formulario de PiezaCotizada
# permitiendo al técnico indicar con qué proveedor se cotizó cada pieza
PROVEEDORES_CHOICES = [
    ('', '-- Seleccionar proveedor (opcional) --'),  # Opción vacía
    ('AMAZON', 'AMAZON'),
    ('AMERICANSTOCK', 'AMERICANSTOCK'),
    ('FRANCISCO RUIZ', 'FRANCISCO RUIZ'),
    ('GJJ TECNOLOGIA', 'GJJ TECNOLOGIA'),
    ('MERCADO LIBRE', 'MERCADO LIBRE'),
    ('RHITSO', 'RHITSO'),
    ('DAVID CASTAÑEDA', 'DAVID CASTAÑEDA'),
    ('SIC STOCK', 'SIC STOCK'),
    ('SOL SATA', 'SOL SATA'),
    ('SUREM', 'SUREM'),
    ('TECNOCITY', 'TECNOCITY'),
    ('TIENDA LENOVO', 'TIENDA LENOVO'),
    ('ULRA', 'ULTRA'),
    ('OTRO', 'Otro proveedor'),  # Opción para proveedor no listado
]


# ============================================================================
# MÓDULO ALMACÉN - Sistema de Inventario de Almacén Central
# Agregado: Diciembre 2025
# ============================================================================

# TIPOS DE PRODUCTO EN ALMACÉN
# Determina el comportamiento del producto respecto a stock y alertas
TIPO_PRODUCTO_ALMACEN_CHOICES = [
    ('resurtible', 'Resurtible (Stock Permanente)'),
    ('unico', 'Único (Compra Específica)'),
]

# CATEGORÍAS DE PRODUCTOS DE ALMACÉN
# Clasificación general de productos
CATEGORIA_ALMACEN_CHOICES = [
    ('repuesto', 'Repuesto/Pieza'),
    ('consumible', 'Consumible'),
    ('herramienta', 'Herramienta'),
    ('accesorio', 'Accesorio'),
    ('quimico', 'Químico/Limpieza'),
    ('paquete', 'Paquete/Kit'),
    ('otro', 'Otro'),
]

# TIPOS DE MOVIMIENTO EN ALMACÉN
# Entrada: incrementa stock, Salida: decrementa stock, Transferencia: stock neutro
TIPO_MOVIMIENTO_ALMACEN_CHOICES = [
    ('entrada', 'Entrada'),
    ('salida', 'Salida'),
    ('transferencia', 'Transferencia'),  # No afecta stock, solo cambia ubicación
]

# TIPOS DE SOLICITUD DE BAJA
# Define el propósito de la salida de producto
TIPO_SOLICITUD_ALMACEN_CHOICES = [
    ('consumo_interno', 'Consumo Interno'),
    ('servicio_tecnico', 'Servicio Técnico'),
    ('venta_mostrador', 'Venta Mostrador'),
    ('transferencia', 'Transferencia entre Sucursales'),
]

# ESTADOS DE SOLICITUD DE BAJA
# Workflow de aprobación de salidas
ESTADO_SOLICITUD_BAJA_CHOICES = [
    ('pendiente', 'Pendiente'),
    ('aprobada', 'Aprobada'),
    ('rechazada', 'Rechazada'),
    ('en_espera', 'En Espera - Producto no Disponible'),
]

# TIPOS DE AUDITORÍA DE INVENTARIO
# Diferentes enfoques de auditoría según necesidad
TIPO_AUDITORIA_CHOICES = [
    ('completa', 'Auditoría Completa'),
    ('ciclica', 'Auditoría Cíclica'),
    ('diferencias', 'Auditoría por Diferencias'),
    ('abc', 'Auditoría ABC (Alto Valor)'),
]

# ESTADOS DE AUDITORÍA
# Progreso de la auditoría
ESTADO_AUDITORIA_CHOICES = [
    ('en_proceso', 'En Proceso'),
    ('completada', 'Completada'),
    ('con_diferencias', 'Completada con Diferencias'),
]

# RAZONES DE DIFERENCIA EN AUDITORÍA
# Catalogar causas de discrepancias entre sistema y físico
RAZON_DIFERENCIA_AUDITORIA_CHOICES = [
    ('merma_natural', 'Merma Natural'),
    ('dano', 'Producto Dañado'),
    ('robo', 'Robo/Pérdida'),
    ('error_sistema', 'Error de Sistema'),
    ('error_recepcion', 'Error al Recibir'),
    ('error_despacho', 'Error al Despachar'),
    ('desconocida', 'Razón Desconocida'),
]

# CLASIFICACIÓN DE ESTADOS PARA LÓGICA DE SOLICITUDES
# Útil para filtros y validaciones en código
ESTADOS_SOLICITUD_PENDIENTES = ['pendiente', 'en_espera']
ESTADOS_SOLICITUD_FINALIZADOS = ['aprobada', 'rechazada']


# ============================================================================
# COMPRAS DE PRODUCTO - Sistema de Cotizaciones y Compras
# Agregado: Diciembre 2025
# ============================================================================

# TIPO DE REGISTRO DE COMPRA
# Diferencia entre cotización (pendiente de aprobación) y compra formal
TIPO_COMPRA_CHOICES = [
    ('cotizacion', 'Cotización'),
    ('compra', 'Compra Formal'),
]

# ESTADOS DE COMPRA/COTIZACIÓN
# Flujo completo: cotización → aprobación → llegada → problemas/devolución
ESTADO_COMPRA_CHOICES = [
    # Estados de cotización
    ('pendiente_aprobacion', 'Pendiente de Aprobación'),
    ('aprobada', 'Aprobada por Cliente'),
    ('rechazada', 'Rechazada por Cliente'),
    # Estados de compra
    ('pendiente_llegada', 'Pendiente de Llegada'),
    ('recibida', 'Recibida'),
    # Estados de problema
    ('wpb', 'WPB - Wrong Part (Pieza Incorrecta)'),
    ('doa', 'DOA - Dead On Arrival (Dañada al Llegar)'),
    # Estados de devolución
    ('devolucion_garantia', 'En Devolución (Garantía)'),
    ('devuelta', 'Devuelta al Proveedor'),
    # Estado cancelado
    ('cancelada', 'Cancelada'),
]

# ESTADOS DE UNIDAD EN COMPRA (para cada pieza individual)
# Permite tracking por unidad dentro de una compra
ESTADO_UNIDAD_COMPRA_CHOICES = [
    ('pendiente', 'Pendiente de Recibir'),
    ('recibida', 'Recibida OK'),
    ('wpb', 'WPB - Pieza Incorrecta'),
    ('doa', 'DOA - Dañada al Llegar'),
    ('devolucion', 'En Devolución'),
    ('devuelta', 'Devuelta'),
]

# CLASIFICACIÓN DE ESTADOS PARA LÓGICA DE COMPRAS
ESTADOS_COMPRA_COTIZACION = ['pendiente_aprobacion', 'aprobada', 'rechazada']
ESTADOS_COMPRA_ACTIVOS = ['aprobada', 'pendiente_llegada']
ESTADOS_COMPRA_PROBLEMAS = ['wpb', 'doa', 'devolucion_garantia']
ESTADOS_COMPRA_FINALIZADOS = ['recibida', 'devuelta', 'cancelada', 'rechazada']


# ============================================================================
# CONSTANTES PARA SOLICITUD DE COTIZACIÓN (MULTI-PROVEEDOR)
# Sistema que permite agrupar múltiples líneas de cotización con diferentes
# proveedores bajo una sola solicitud vinculada a una orden de servicio.
# Agregado: Diciembre 2025
# ============================================================================

# ESTADOS DE LA SOLICITUD DE COTIZACIÓN (cabecera)
# Flujo: borrador → enviada_cliente → respuesta del cliente → procesamiento
ESTADO_SOLICITUD_COTIZACION_CHOICES = [
    ('borrador', 'Borrador'),                          # Compras está preparando
    ('enviada_cliente', 'Enviada a Cliente'),          # Recepción puede compartir con cliente
    ('parcialmente_aprobada', 'Parcialmente Aprobada'),# Cliente aprobó algunas líneas
    ('totalmente_aprobada', 'Totalmente Aprobada'),    # Cliente aprobó todas las líneas
    ('totalmente_rechazada', 'Totalmente Rechazada'),  # Cliente rechazó todas las líneas
    ('en_proceso', 'En Proceso de Compra'),            # Se están generando las compras
    ('completada', 'Completada'),                      # Todas las compras generadas
    ('cancelada', 'Cancelada'),                        # Solicitud cancelada
]

# ESTADOS DE LÍNEA DE COTIZACIÓN (cada producto/proveedor)
# Permite aprobación/rechazo individual por línea
ESTADO_LINEA_COTIZACION_CHOICES = [
    ('pendiente', 'Pendiente de Respuesta'),    # Esperando decisión del cliente
    ('aprobada', 'Aprobada por Cliente'),       # Cliente quiere esta pieza
    ('rechazada', 'Rechazada por Cliente'),     # Cliente no quiere esta pieza
    ('compra_generada', 'Compra Generada'),     # Ya se creó CompraProducto
]

# CLASIFICACIÓN DE ESTADOS PARA LÓGICA DE SOLICITUD DE COTIZACIÓN
ESTADOS_SOLICITUD_ACTIVOS = ['borrador', 'enviada_cliente', 'parcialmente_aprobada', 'totalmente_aprobada', 'en_proceso']
ESTADOS_SOLICITUD_FINALIZADOS = ['completada', 'totalmente_rechazada', 'cancelada']


# ============================================================================
# FUNCIONES DE UTILIDAD - MÓDULO ALMACÉN
# ============================================================================

def obtener_nombre_tipo_producto(codigo_tipo):
    """
    Retorna el nombre legible de un tipo de producto de almacén
    
    Args:
        codigo_tipo (str): Código del tipo ('resurtible', 'unico')
    
    Returns:
        str: Nombre del tipo
    """
    for codigo, nombre in TIPO_PRODUCTO_ALMACEN_CHOICES:
        if codigo == codigo_tipo:
            return nombre
    return 'Tipo Desconocido'


def obtener_nombre_estado_solicitud(codigo_estado):
    """
    Retorna el nombre legible de un estado de solicitud de baja
    
    Args:
        codigo_estado (str): Código del estado
    
    Returns:
        str: Nombre del estado
    """
    for codigo, nombre in ESTADO_SOLICITUD_BAJA_CHOICES:
        if codigo == codigo_estado:
            return nombre
    return 'Estado Desconocido'


def es_solicitud_pendiente(codigo_estado):
    """
    Verifica si una solicitud está en estado pendiente
    
    Args:
        codigo_estado (str): Código del estado
    
    Returns:
        bool: True si está pendiente
    """
    return codigo_estado in ESTADOS_SOLICITUD_PENDIENTES


# ============================================================================
# UNIDAD DE INVENTARIO - Rastreo Individual de Piezas/Productos
# Agregado: Diciembre 2025
# ============================================================================

# ESTADO DE LA UNIDAD INDIVIDUAL
# Representa la condición física/funcional de cada pieza
ESTADO_UNIDAD_CHOICES = [
    ('nuevo', 'Nuevo'),
    ('usado_bueno', 'Usado - Buen Estado'),
    ('usado_regular', 'Usado - Estado Regular'),
    ('reparado', 'Reparado'),
    ('defectuoso', 'Defectuoso'),
    ('para_revision', 'Para Revisión'),
]

# ORIGEN DE LA UNIDAD
# De dónde proviene esta pieza específica
ORIGEN_UNIDAD_CHOICES = [
    ('compra', 'Compra Directa'),
    ('orden_servicio', 'Recuperada de Orden de Servicio'),
    ('devolucion_cliente', 'Devolución de Cliente'),
    ('transferencia', 'Transferencia entre Sucursales'),
    ('inventario_inicial', 'Inventario Inicial'),
    ('donacion', 'Donación'),
    ('otro', 'Otro'),
]

# DISPONIBILIDAD DE LA UNIDAD
# Estado operativo actual
DISPONIBILIDAD_UNIDAD_CHOICES = [
    ('disponible', 'Disponible'),
    ('reservada', 'Reservada'),
    ('asignada', 'Asignada a Orden'),
    ('vendida', 'Vendida'),
    ('descartada', 'Descartada/Baja'),
]

# MARCAS COMUNES DE COMPONENTES
# Para autocompletado y estandarización
MARCAS_COMPONENTES_CHOICES = [
    ('', '-- Seleccionar marca --'),
    # Almacenamiento
    ('Samsung', 'Samsung'),
    ('Kingston', 'Kingston'),
    ('Crucial', 'Crucial'),
    ('Western Digital', 'Western Digital'),
    ('Seagate', 'Seagate'),
    ('SanDisk', 'SanDisk'),
    ('SK Hynix', 'SK Hynix'),
    ('Toshiba', 'Toshiba'),
    # RAM
    ('Corsair', 'Corsair'),
    ('G.Skill', 'G.Skill'),
    ('ADATA', 'ADATA'),
    ('TeamGroup', 'TeamGroup'),
    # Tarjetas Madre / Componentes
    ('Asus', 'Asus'),
    ('MSI', 'MSI'),
    ('Gigabyte', 'Gigabyte'),
    ('ASRock', 'ASRock'),
    ('Intel', 'Intel'),
    ('AMD', 'AMD'),
    ('Nvidia', 'Nvidia'),
    # Laptops / OEM
    ('Dell', 'Dell'),
    ('HP', 'HP'),
    ('Lenovo', 'Lenovo'),
    ('Acer', 'Acer'),
    ('Apple', 'Apple'),
    # Genérico
    ('Genérico', 'Genérico / Sin Marca'),
    ('Otra', 'Otra Marca'),
]

# CLASIFICACIÓN DE ESTADOS PARA LÓGICA DE UNIDADES
ESTADOS_UNIDAD_USABLES = ['nuevo', 'usado_bueno', 'reparado']
ESTADOS_UNIDAD_DISPONIBLES = ['disponible']
DISPONIBILIDADES_ACTIVAS = ['disponible', 'reservada', 'asignada']


# ============================================================================
# FUNCIONES DE UTILIDAD - UNIDADES DE INVENTARIO
# ============================================================================

def obtener_nombre_estado_unidad(codigo_estado):
    """
    Retorna el nombre legible de un estado de unidad
    
    Args:
        codigo_estado (str): Código del estado
    
    Returns:
        str: Nombre del estado
    """
    for codigo, nombre in ESTADO_UNIDAD_CHOICES:
        if codigo == codigo_estado:
            return nombre
    return 'Estado Desconocido'


def obtener_nombre_origen_unidad(codigo_origen):
    """
    Retorna el nombre legible del origen de una unidad
    
    Args:
        codigo_origen (str): Código del origen
    
    Returns:
        str: Nombre del origen
    """
    for codigo, nombre in ORIGEN_UNIDAD_CHOICES:
        if codigo == codigo_origen:
            return nombre
    return 'Origen Desconocido'


def es_unidad_usable(codigo_estado):
    """
    Verifica si una unidad está en estado usable para asignar
    
    Args:
        codigo_estado (str): Código del estado
    
    Returns:
        bool: True si está en buen estado para usar
    """
    return codigo_estado in ESTADOS_UNIDAD_USABLES


def es_unidad_disponible(codigo_disponibilidad):
    """
    Verifica si una unidad está disponible para asignar
    
    Args:
        codigo_disponibilidad (str): Código de disponibilidad
    
    Returns:
        bool: True si está disponible
    """
    return codigo_disponibilidad in ESTADOS_UNIDAD_DISPONIBLES
