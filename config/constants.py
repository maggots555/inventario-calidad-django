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
# NORMALIZACIÓN PRODUCTO ALMACÉN → ComponenteEquipo (cotizaciones / ST)
# ============================================================================
# EXPLICACIÓN PARA PRINCIPIANTES:
# Los productos del catálogo de almacén tienen nombres largos como
# "BATERÍA / PILA DELL 40 W". Al sincronizar con Servicio Técnico necesitamos
# mapearlos al nombre canónico de ComponenteEquipo ("Batería", "Cargador", etc.)
# para que reportes y consultas usen categorías normalizadas.
#
# Cada tupla: (lista de palabras clave en MAYÚSCULAS, nombre exacto en ComponenteEquipo)
# IMPORTANTE: las keywords más largas deben ir primero en la lista global
# (el resolver las ordena por longitud antes de evaluar).
NOMBRE_COMPONENTE_EQUIPO_REACONDICIONADO = 'Equipo reacondicionado'

PALABRAS_CLAVE_COMPONENTE = [
    (['SSD M.2', 'SSD M2', 'M.2 SSD', 'M2 SSD', 'NVME', 'NVME SSD'], 'SSD M.2'),
    (['KEYBOARD WITH PALMREST', 'TECLADO CON PALMREST', 'KEYBOARD PALMREST'], 'Keyboard with Palmrest Assy'),
    (['FUENTE DE PODER', 'FUENTE DE ALIMENTACION', 'FUENTE DE ALIMENTACIÓN', 'POWER SUPPLY', 'PSU'], 'Fuente de Poder'),
    (['TARJETA GRAFICA', 'TARJETA GRÁFICA', 'TARJETA DE VIDEO', 'GRAPHICS CARD', 'GPU'], 'Tarjeta Gráfica (GPU)'),
    (['DISCO DURO', 'HARD DRIVE', 'UNIDAD DE ESTADO SOLIDO', 'SOLID STATE'], 'Disco Duro / SSD'),
    (['DISCO', 'SSD', 'HDD', 'STORAGE'], 'Disco Duro / SSD'),
    (['TARJETA MADRE', 'MOTHERBOARD', 'MAINBOARD', 'MOBO', 'PLACA MADRE'], 'Motherboard'),
    (['MEMORIA RAM', 'SODIMM', 'SO-DIMM', 'MODULO DE MEMORIA', 'MÓDULO DE MEMORIA'], 'RAM'),
    (['VENTILADOR', 'COOLER', 'COOLING', 'SISTEMA DE ENFRIAMIENTO'], 'Ventilador / Cooling'),
    (['DISIPADOR DE CALOR', 'HEATSINK', 'HEAT SINK', 'PASTA TERMICA', 'PASTA TÉRMICA'], 'Disipador de calor'),
    (['REFRIGERACION LIQUIDA', 'REFRIGERACIÓN LIQUIDA', 'LIQUID COOLING', 'WATER COOLING'], 'Refrigeración liquida'),
    (['SISTEMA OPERATIVO', 'WINDOWS', 'REINSTALACION', 'REINSTALACIÓN', 'FORMATEO'], 'Sistema Operativo'),
    (['LIMPIEZA Y MANTENIMIENTO', 'KIT DE LIMPIEZA', 'MANTENIMIENTO'], 'Limpieza y mantenimiento'),
    (['CARGADOR', 'ADAPTADOR', 'ELIMINADOR', 'AC ADAPTER', 'POWER ADAPTER', 'CHARGER'], 'Cargador'),
    (['BATERÍA', 'BATERIA', 'PILA', 'BATTERY', 'ACUMULADOR'], 'Batería'),
    (['PANTALLA', 'LCD', 'DISPLAY', 'SCREEN', 'PANEL LCD', 'PANEL LED', 'MONITOR'], 'Pantalla'),
    (['TECLADO USB', 'USB KEYBOARD'], 'Teclado USB'),
    (['TECLADO', 'KEYBOARD', 'PALMREST'], 'Teclado'),
    (['TOUCHPAD', 'TOUCH PAD', 'TRACKPAD', 'TRACK PAD'], 'Touchpad'),
    (['PROCESADOR', 'CPU', 'PROCESSOR', 'MICROPROCESADOR'], 'Procesador (CPU)'),
    (['CABLE DE VIDEO', 'CABLE LVDS', 'LVDS', 'VIDEO CABLE', 'EDP CABLE'], 'Cable de video/LVDS'),
    (['CABLE FLEX', 'FLEX CABLE', 'FLAT CABLE', 'RIBBON'], 'Cable Flex'),
    (['CABLE DE BATERIA', 'CABLE DE BATERÍA', 'BATTERY CABLE'], 'Cable de Batería'),
    (['CABLE DE IO', 'CABLE IO BOARD', 'CABLE I/O', 'I/O CABLE'], 'Cable de I/O Board'),
    (['CABLE LECTOR DE HUELLAS', 'FINGERPRINT CABLE'], 'Cable lector de huellas'),
    (['PUERTO DE RED', 'ETHERNET', 'RJ45', 'LAN PORT', 'NETWORK PORT'], 'Puerto de Red (Ethernet)'),
    (['PUERTO HDMI', 'HDMI PORT', 'CONECTOR HDMI'], 'Puerto HDMI'),
    (['PUERTO USB', 'USB PORT', 'CONECTOR USB'], 'Puerto USB'),
    (['LECTOR DE HUELLAS', 'FINGERPRINT READER', 'HUELLA DIGITAL'], 'Lector de huellas'),
    (['LECTOR DE TARJETAS', 'CARD READER', 'LECTOR SD', 'SD READER'], 'Lector de Tarjetas'),
    (['WIRELESS ANTENNAS', 'ANTENAS WIRELESS', 'ANTENAS WIFI'], 'Wireless Antennas'),
    (['TARJETA WIFI', 'TARJETA INALAMBRICA', 'TARJETA INALÁMBRICA', 'WLAN', 'MODULO WIFI', 'MÓDULO WIFI'], 'WiFi / Bluetooth'),
    (['WIFI', 'WI-FI', 'BLUETOOTH', 'WIRELESS'], 'WiFi / Bluetooth'),
    (['BOTON DE ENCENDIDO', 'BOTÓN DE ENCENDIDO', 'POWER BUTTON', 'BUTTON POWER'], 'Button Power'),
    (['BOTON', 'BOTÓN', 'BUTTON'], 'Botón'),
    (['DC-IN', 'DCIN', 'DC IN', 'JACK DE CARGA', 'POWER JACK', 'CONECTOR DE CARGA'], 'DC-IN cable'),
    (['PILA CMOS', 'CMOS BATTERY', 'BIOS BATTERY', 'COIN CELL'], 'Pila CMOS'),
    (['BISEL LCD', 'LCD BEZEL', 'BEZEL LCD', 'MARCO LCD'], 'Bisel LCD'),
    (['BOTTOM COVER', 'BOTTOM CASE', 'TAPA INFERIOR', 'BASE INFERIOR'], 'Bottom Cover/Case'),
    (['TOP COVER', 'LCD COVER', 'BACK LID', 'TAPA SUPERIOR'], 'Top Cover'),
    (['CUBRE BISAGRAS', 'HINGE COVER', 'TAPA BISAGRAS'], 'Cubre Bisagras'),
    (['CARCASA', 'CHASIS', 'HOUSING', 'CUBIERTA', 'PLASTICOS', 'PLÁSTICOS'], 'Carcasa / Chasis'),
    (['BASE DE COMPUTADORA', 'DESKTOP BASE', 'COMPUTER BASE'], 'Base de computadora'),
    (['BISAGRA', 'BISAGRAS', 'HINGE', 'HINGES', 'CHARNELA'], 'Bisagras'),
    (['BOCINA', 'BOCINAS', 'SPEAKER', 'SPEAKERS', 'ALTAVOZ', 'PARLANTE'], 'Bocinas / Audio'),
    (['MICROFONO', 'MICRÓFONO', 'MICROPHONE'], 'Micrófono'),
    (['CAMARA', 'CÁMARA', 'WEBCAM', 'WEB CAM'], 'Webcam'),
    (['MOUSE', 'RATON', 'RATÓN'], 'Mouse'),
    (['I/O BOARD', 'IO BOARD', 'PLACA IO'], 'I/O Board'),
    (['CABLE', 'BUS', 'HUB', 'CONVERTIDOR'], 'Cable'),
    (['RAM', 'MEMORIA', 'DIMM'], 'RAM'),
    (['ANTENA', 'ANTENAS', 'ANTENNA'], 'Wireless Antennas'),
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
    # Formato Digital OOW (identificación oficial + escaneo PC Audit)
    ('identificacion_oow', 'Identificación oficial — Formato OOW'),
    ('escaneo_oow', 'Resultado de escaneo — Formato OOW'),
    # Formato Digital Garantía Dell (solo escaneo PC Audit; sin INE)
    ('escaneo_garantia', 'Resultado de escaneo — Formato Garantía Dell'),
]

# ============================================================================
# TIPO DE VIDEOS - Para clasificación de evidencias en video
# Mismos tipos que imágenes para consistencia de flujo de trabajo
# ============================================================================
TIPO_VIDEO_CHOICES = [
    ('ingreso', 'Ingreso - Estado Inicial'),
    ('diagnostico', 'Durante Diagnóstico'),
    ('reparacion', 'Durante Reparación'),
    ('egreso', 'Egreso - Estado Final'),
    ('autorizacion', 'Autorización/Pass - RHITSO'),
    ('packing', 'Packing'),
    ('resumen', 'Video Resumen - Galería'),           # Generado automáticamente por Celery
    ('resumen_comprimido', 'Video Resumen Comprimido'),  # Versión comprimida para descarga
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
    ('video', 'Subida de Video'),
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
# Flujo: borrador → enviada_front → enviada_cliente → respuesta del cliente → procesamiento
ESTADO_SOLICITUD_COTIZACION_CHOICES = [
    ('borrador', 'Borrador'),                          # Compras está preparando
    ('enviada_front', 'Enviada a Front'),              # Notificación enviada a recepción
    ('enviada_cliente', 'Enviada a Cliente'),          # Recepción compartió con el cliente
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

# Estados incluidos en cotización activa (reenvío / preview / calculadora modal)
ESTADOS_LINEA_COTIZACION_ACTIVA = ('pendiente', 'aprobada')

# Estados incluidos en el PDF final (solo lo que el cliente aceptó)
ESTADOS_LINEA_COTIZACION_ACEPTADA = ('aprobada', 'compra_generada')

# Forma de pago al aceptar equipo reacondicionado (línea P0125)
OPCION_PAGO_REAC_CHOICES = [
    ('contado', 'Pago de contado'),
    ('diferido_3_meses', 'Financiamiento 3 meses'),
    ('diferido_6_meses', 'Financiamiento 6 meses'),
    ('diferido_12_meses', 'Financiamiento 12 meses'),
]

# CLASIFICACIÓN DE ESTADOS PARA LÓGICA DE SOLICITUD DE COTIZACIÓN
ESTADOS_SOLICITUD_ACTIVOS = ['borrador', 'enviada_front', 'enviada_cliente', 'parcialmente_aprobada', 'totalmente_aprobada', 'en_proceso']
ESTADOS_SOLICITUD_FINALIZADOS = ['completada', 'totalmente_rechazada', 'cancelada']

# TIPOS DE SERVICIO ADICIONAL (para LíneaServicioAdicional en cotizaciones)
# Mapea directamente a los campos de VentaMostrador en servicio_tecnico
TIPO_SERVICIO_ADICIONAL_CHOICES = [
    ('paquete_premium', 'Solución Premium'),
    ('paquete_oro', 'Solución Oro'),
    ('paquete_plata', 'Solución Plata'),
    ('cambio_pieza', 'Cambio de Pieza (sin diagnóstico)'),
    ('limpieza', 'Limpieza y Mantenimiento'),
    ('kit_limpieza', 'Kit de Limpieza Profesional'),
    ('reinstalacion_so', 'Reinstalación de Sistema Operativo'),
    ('respaldo', 'Respaldo de Información'),
]

# Precios sugeridos para servicios adicionales (IVA incluido)
# Estos son valores por defecto, el usuario puede modificarlos en cada línea
PRECIOS_SERVICIOS_ADICIONALES = {
    'paquete_premium': 00.00, # Producto descontinuado, se mantiene precio en 0 para evitar confusión
    'paquete_oro': 00.00,     # Producto descontinuado, se mantiene precio en 0 para evitar confusión
    'paquete_plata': 4295.00,
    'cambio_pieza': 589.00,
    'limpieza': 1050.00,
    'kit_limpieza': 589.00,
    'reinstalacion_so': 589.00,
    'respaldo': 400.00,
}

# Mapeo de tipo_servicio_adicional → campo booleano en VentaMostrador
# Usado para crear/actualizar VentaMostrador al aprobar servicios adicionales
MAPEO_SERVICIO_A_VENTA_MOSTRADOR = {
    'paquete_premium': {'campo_paquete': 'premium', 'campo_costo': 'costo_paquete'},
    'paquete_oro': {'campo_paquete': 'oro', 'campo_costo': 'costo_paquete'},
    'paquete_plata': {'campo_paquete': 'plata', 'campo_costo': 'costo_paquete'},
    'cambio_pieza': {'campo_incluye': 'incluye_cambio_pieza', 'campo_costo': 'costo_cambio_pieza'},
    'limpieza': {'campo_incluye': 'incluye_limpieza', 'campo_costo': 'costo_limpieza'},
    'kit_limpieza': {'campo_incluye': 'incluye_kit_limpieza', 'campo_costo': 'costo_kit'},
    'reinstalacion_so': {'campo_incluye': 'incluye_reinstalacion_so', 'campo_costo': 'costo_reinstalacion'},
    'respaldo': {'campo_incluye': 'incluye_respaldo', 'campo_costo': 'costo_respaldo'},
}

# ============================================================================
# INCLUSIONES DE SERVICIOS ADICIONALES (cotización al cliente — México)
# ============================================================================
# EXPLICACIÓN PARA PRINCIPIANTES:
# Estas listas alimentan el PDF/email de cotización de Almacén cuando se ofrece
# un paquete (ej. Solución Plata). Son independientes de DESCRIPCION_PAQUETES
# (Venta Mostrador), porque precios e inclusiones pueden diferir.
# Solo se usan cuando el país activo es México (codigo ISO 'MX').

INCLUSIONES_SERVICIO_ADICIONAL = {
    'paquete_plata': [
        'SSD 1 TB',
        'Mantenimiento',
        'Limpieza',
        'Respaldo de información',
        'Instalación de S.O. y drivers',
        'Transferencia de datos',
    ],
}

# Aviso comercial cuando el documento (PDF/email) es solo de servicios.
# El cálculo ya omite el descuento de diagnóstico; este texto lo explica al cliente.
AVISO_DIAGNOSTICO_SOLO_SERVICIOS = (
    'Este documento no incluye descuento de diagnóstico. '
    'El descuento de diagnóstico aplica únicamente para el reemplazo de piezas.'
)

# Países donde aplican inclusiones de paquetes y el aviso de diagnóstico.
PAISES_INCLUSIONES_SERVICIO_ADICIONAL = ('MX',)

# ============================================================================
# FUNCIONES DE UTILIDAD - MÓDULO ALMACÉN
# ============================================================================

def obtener_inclusiones_servicio_adicional(tipo_servicio, pais_codigo='MX'):
    """
    Devuelve la lista de inclusiones de un servicio adicional para cotización.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Solo México muestra estas inclusiones en el PDF. Si el tipo no tiene
    catálogo (ej. limpieza suelta) o el país no es MX, regresa None.

    Args:
        tipo_servicio (str): Código del choice (ej. 'paquete_plata').
        pais_codigo (str): Código ISO del país activo (ej. 'MX', 'AR').

    Returns:
        list[str] | None: Bullets a mostrar, o None si no aplica.
    """
    # Paso 1: fuera de México no mostramos inclusiones de paquetes de cotización
    if pais_codigo not in PAISES_INCLUSIONES_SERVICIO_ADICIONAL:
        return None
    # Paso 2: buscar en el catálogo; si no hay entrada, no enriquecer descripción
    inclusiones = INCLUSIONES_SERVICIO_ADICIONAL.get(tipo_servicio)
    if not inclusiones:
        return None
    return list(inclusiones)


def formatear_descripcion_servicio_con_inclusiones(
    nombre_display,
    tipo_servicio,
    pais_codigo='MX',
):
    """
    Arma el texto HTML de descripción para ReportLab (PDF de cotización).

    Args:
        nombre_display (str): Label visible (ej. 'Solución Plata').
        tipo_servicio (str): Código interno (ej. 'paquete_plata').
        pais_codigo (str): Código ISO del país activo.

    Returns:
        str: Solo el nombre, o nombre + bullets con <br/> si hay inclusiones.
    """
    inclusiones = obtener_inclusiones_servicio_adicional(tipo_servicio, pais_codigo)
    if not inclusiones:
        return nombre_display
    # ReportLab Paragraph acepta HTML básico: negrita en el título + bullets
    lineas = [f'<b>{nombre_display}</b>']
    for item in inclusiones:
        lineas.append(f'• {item}')
    return '<br/>'.join(lineas)


def debe_mostrar_aviso_diagnostico_solo_servicios(pais_codigo, solo_servicios):
    """
    Indica si el PDF/email debe mostrar el aviso de diagnóstico (solo servicios).

    Args:
        pais_codigo (str): Código ISO del país (ej. 'MX').
        solo_servicios (bool): True si el documento no tiene piezas.

    Returns:
        bool: True solo en México y cuando el envío es únicamente servicios.
    """
    return (
        bool(solo_servicios)
        and pais_codigo in PAISES_INCLUSIONES_SERVICIO_ADICIONAL
    )


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


# ============================================================================
# CONFIGURACIÓN DE FFMPEG — Rutas del sistema
# ============================================================================

# Ruta a la fuente TrueType usada por el filtro drawtext de FFmpeg.
# Candidatos en orden de preferencia para Ubuntu/Debian.
# La función _resolver_fuente_ffmpeg() busca la primera que exista en disco.
_FFMPEG_FONT_CANDIDATES = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',        # Ubuntu/Debian estándar
    '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',  # Alternativa común
    '/usr/share/fonts/truetype/freefont/FreeSans.ttf',         # freefont-ttf
    '/usr/share/fonts/dejavu/DejaVuSans.ttf',                  # Algunas distros sin subdirectorio
]


def _resolver_fuente_ffmpeg() -> str:
    """
    Devuelve la primera ruta de fuente TTF disponible en disco.
    Si ninguna existe, devuelve la ruta estándar de Ubuntu como fallback
    (FFmpeg mostrará un error descriptivo si tampoco existe).
    """
    import os
    for ruta in _FFMPEG_FONT_CANDIDATES:
        if os.path.isfile(ruta):
            return ruta
    return _FFMPEG_FONT_CANDIDATES[0]


# Ruta resuelta al iniciar. Se evalúa una sola vez al importar constants.py.
FFMPEG_DRAWTEXT_FONT = _resolver_fuente_ffmpeg()


# ============================================================================
# FORMATO DIGITAL OOW — Aviso de privacidad México
# ============================================================================
# EXPLICACIÓN PARA PRINCIPIANTES:
# Este texto legal se muestra en el wizard del Formato Digital OOW (iPad) y se
# imprime íntegro en la(s) última(s) página(s) del PDF. La versión permite
# auditar qué texto aceptó el cliente si el aviso cambia en el futuro.

AVISO_PRIVACIDAD_OOW_VERSION_MX = 'mx-2016-09-06'

AVISO_PRIVACIDAD_OOW_MX = """
Aviso de privacidad
SIC COMERCIALIZACIÓN Y SERVICIOS.

RESPONSABLE

SIC COMERCIALIZACIÓN Y SERVICIOS como responsable en el tratamiento de sus datos personales, le informa que es una persona moral con residencia en Naucalpan de Juárez, con domicilio ubicado en Cto. Economistas 15 A, Ciudad Satélite, Naucalpan de Juárez. Edo. Mex. 53100, Estado de México lugar donde de manera totalmente profesional se resguardan los datos personales, sensibles, que se recaben a través de nuestro personal o bien en la base de datos de la página de internet que usted ha accesado puede ser contactada al teléfono (52-55) 53660900, en donde con gusto nuestra área de administración quien también puede ser contactado a través de correo electrónico en : atencionaclientes@sic.com.mx le atenderá para mayor información con relación a nuestro aviso de privacidad. Una de las prioridades en SIC COMERCIALIZACIÓN Y SERVICIOS, en adelante, “SIC” es respetar la privacidad y confidencialidad de sus usuarios así como mantener segura la información y los datos personales que recolecta a fin de no ser transmitidos a terceros a excepción de mandamientos judiciales o su autorización para tal efecto.

El presente Aviso tiene como finalidad que usted esté en posibilidad de conocer los alcances de este, y oponerse al uso, tratamiento y/o transferencia de datos.

La información recabada por “SIC”, corresponde principalmente a los datos recabados con motivo del ingreso de equipo de su propiedad a servicio “fuera de garantía”, diagnóstico y cualquier otro esquema de servicio que la propia empresa requiera al ingresar el equipo.

La información personal recabada por “SIC” será utilizada para los siguientes propósitos: con fines publicitarios, hacer llegar novedades y promociones, proveer los servicios y productos que usted ha solicitado, informarle sobre cambios en los mismos, evaluar la calidad del servicio que le brindamos, procurar un servicio eficiente, informar sobre nuevos productos o servicios que estén relacionados con el contratado o adquirido por el cliente, dar cumplimiento a obligaciones contraídas con nuestros clientes, informar sobre cambios de nuestros productos o servicios, proveer una mejor atención al usuario, procesar solicitudes de pago electrónico, ofrecerle prórrogas o beneficios adicionales a los contratados con “SIC”, dar cumplimiento a requerimientos legales así como realizar análisis estadísticos dentro de “SIC”, mantener actualizados nuestros registros para poder responder eficientemente a sus necesidades, gestión de cobranza, requerimientos de pago, y otras campañas que en beneficio de usted se puedan realizar, muy independientemente de que en caso de ser requerido “SIC” por autoridades judiciales sobre su información personal, en términos de ley esta información se proporcionará de manera directa al órgano jurisdiccional que lo solicite. Para las finalidades antes mencionadas, requerimos obtener de usted datos personales que los usuarios de este sitio capturan de manera voluntaria en nuestros formularios de captura. DATOS PERSONALES: En el sitio de internet usted proporciona información desde varias áreas de nuestros propios sitios web. Para cada uno de estos sitios, la información que se solicita es distinta y se almacena en bases de datos separadas dentro de la misma empresa sin ser proporcionados a terceros. La información que usted proporciona, deberá ser veraz y completa, por lo cual usted responderá en todo momento por los datos proporcionados y en ningún caso “SIC” será responsable de los mismos. Entre la información solicitada a usted podría incluirse:

Datos de Cliente:
• Nombre de cliente o empresa
• RFC
• Correo electrónico
• Teléfono

Datos del equipo de cómputo:
• Nombre de cliente o empresa
• Marca
• Modelo
• Service Tag
• Contraseña del equipo de cómputo
• Firma electrónica y Fotografía del INE

QUÉ SON LOS COOKIES Y CÓMO SE UTILIZAN
Algunos de nuestros sitios podrían utilizar herramientas como los cookies, web beacons o similares que son pequeñas piezas de información que son transmitidas por el sitio Web y se utilizan para determinar sus preferencias cuando se conecta a los servicios de nuestros sitios, así como para rastrear determinados comportamientos o actividades llevadas a cabo por usted dentro de nuestros sitios. En algunas secciones de nuestro sitio requerimos que el cliente tenga habilitados los cookies ya que algunas de las funcionalidades requieren de éstas para trabajar. Los cookies nos permiten: a) reconocerlo al momento de entrar a nuestros sitios y ofrecerle de una experiencia personalizada, b) conocer la configuración personal del sitio especificada por usted, por ejemplo, los cookies nos permiten determinar el ancho de banda que usted ha seleccionado al momento de ingresar al home page de nuestros sitios, de tal forma que podremos sugerir qué tipo de información es aconsejable descargar, c) calcular el tamaño de nuestra audiencia y medir algunos parámetros de tráfico, pues cada navegador que obtiene acceso a nuestros sitios adquiere un cookie que se usa para determinar la frecuencia de uso y las secciones de los sitios visitadas, reflejando así sus hábitos y preferencias, información que nos es útil para mejorar el contenido, los titulares y las promociones para los usuarios. Los cookies también nos ayudan a determinar algunas actividades, por ejemplo, en algunas de las encuestas que lanzamos en línea, podemos utilizar cookies para determinar si el usuario ya ha llenado la encuesta y evitar desplegarla nuevamente, en caso de que lo haya hecho. Las cookies le permitirán tomar ventaja de las características más benéficas que le ofrecemos, por lo que le recomendamos que las deje activadas. La utilización de cookies no será utilizada para identificar a los usuarios, con excepción de los casos en que se investiguen posibles actividades fraudulentas así como por mandamiento judicial o ministerial.

USO DE LA INFORMACIÓN
La información solicitada permite a “SIC” contactar a los usuarios cuando sea necesario así como completar los datos necesarios para proveerles acceso restringido a ciertas secciones de información de nuestros sitios, en los casos de sitios en donde hacemos venta en línea, algunos de estos datos permiten identificar al usuario/comprador para enviar sus datos hacia la entidad que procesa el pago, como puede ser un banco nacional o un servicio de pago en línea como Paypal aclarando que dicha información no se resguarda en ningún sitio pues usted es quien la proporciona a momento de realizar el pago.

LIMITACIÓN DE USO Y DIVULGACIÓN DE INFORMACIÓN
En nuestro programa de notificación de promociones, ofertas y servicios a través de correo electrónico, sólo “SIC” tiene acceso a la información recabada la cual no es compartida con ninguna entidad externa a la empresa. Cuando llegamos a enviar mensajes promocionales por correo electrónico, sólo serán enviados a usted y a aquellos contactos registrados para tal propósito, esta indicación podrá usted modificarla en cualquier momento. En los correos electrónicos enviados, pueden incluirse ofertas de terceras partes que sean nuestros socios comerciales. En el caso de empleo de cookies, el botón de “ayuda” que se encuentra en la barra de herramientas de la mayoría de los navegadores, le dirá cómo evitar aceptar nuevos cookies, cómo hacer que el navegador le notifique cuando recibe un nuevo cookie o cómo deshabilitar todos los cookies.

DERECHOS ARCO (ACCESO, RECTIFICACIÓN, CANCELACIÓN Y OPOSICIÓN)
Los datos personales proporcionados por usted formarán parte de un archivo que contendrá su perfil. El usuario puede acceder o modificar su perfil en cualquier momento utilizando su número de usuario/socio o enviándonos un correo a atencionaclientes@sic.com.mx. Asimismo podrá notificarnos la cancelación del tratamiento de información y la cancelación de su expediente, por medio escrito ya sea impreso en nuestras oficinas o bien por correo electrónico el cual deberá ser enviado desde el mismo correo que usted proporcionó, toda vez que la cancelación requiere de un medio escrito e identificación oficial, “SIC” por el mismo medio le dará respuesta a su solicitud en el término establecido en la Ley para la Protección de Datos Personales en Posesión de Particulares o bien cuando los mismos datos proporcionados se actualicen o éstos sufran alguna modificación, ya que esto permitirá brindarle un servicio más personalizado.

TRANSFERENCIAS DE INFORMACIÓN CON TERCEROS y PROTECCIÓN
“SIC” únicamente realiza transferencias de información con las empresas de procesamiento de pagos como bancos o procesadores independientes como Paypal y únicamente lo hace en los sitios que tienen una opción para compra en línea y bajo los estándares de seguridad establecidos por las instituciones financieras. La seguridad y la confidencialidad de los datos que los usuarios proporcionen al contratar un servicio o comprar un producto en línea estarán protegidos por un servidor seguro bajo el protocolo Secure Socket Layer (SSL), de tal forma que los datos enviados se transmitirán encriptados para asegurar su resguardo. Para verificar que se encuentra en un entorno protegido asegúrese de que aparezca una S en la barra de navegación. Ejemplo: https://. En los sitios en los que no se incluye una opción de cobro en línea de ningún servicio, no existe tal transferencia de información.

CAMBIOS EN EL AVISO DE PRIVACIDAD
“SIC” se reserva el derecho de efectuar en cualquier momento modificaciones o actualizaciones al presente aviso de privacidad, para la atención de novedades legislativas o jurisprudenciales, políticas internas, nuevos requerimientos para la prestación u ofrecimiento de nuestros servicios o productos y prácticas del mercado. Estas modificaciones estarán disponibles al público a través de esta página de Internet en la sección de privacidad. La fecha de la última actualización al presente aviso de privacidad: 06 de Septiembre de 2016.

ACEPTACIÓN DE LOS TÉRMINOS
El presente Aviso de Privacidad está sujeto a los términos y condiciones de todos los sitios web de “SIC”, lo cual constituye un acuerdo legal entre el usuario y “SIC” en su aceptación tácita.

Al aceptar el usuario los términos y condiciones a que está sujeto el Aviso de privacidad, acepta que el proveedor del servicio pueda enviar vía correo electrónico o mediante cualquier otro medio de comunicación, información del servicio, publicidad relacionada con este, promoción, difusión o actualización que el proveedor considere importante para mantener informado al usuario sobre la innovación y prestación del servicio que haga más eficaz la interacción entre ambos.

Respecto a lo considerado anteriormente, y cuando sea voluntad del usuario dejar de recibir la información por parte del proveedor, lo hará saber por medio de correo electrónico para que a su vez el proveedor cancele el envío de publicidad y la misma será enviada cuando de nueva cuenta el usuario reciba un servicio y acepte nuevamente los términos y condiciones de este. Si el usuario utiliza los servicios en cualquiera de los sitios de “SIC” significa que ha leído, entendido y acordado los términos antes expuestos. Si no está de acuerdo con ellos, el usuario no deberá proporcionar ninguna información personal, ni utilizar los servicios de los sitios de “SIC”. De conformidad con lo previsto en los artículos 8, 9, 13 y 36 de la Ley para la Protección de Datos Personales en Posesión de Particulares, por medio del presente exteriorizó que he leído y entendido el contenido, los alcances del Aviso de Privacidad de “SIC” y autorizo de manera expresa a “SIC” a recabar y tratar mis datos personales para los fines establecidos.

Por otra parte informamos a usted, que sus datos personales no serán compartidos con ninguna autoridad, empresa, organización o persona distinta a “SIC” y serán utilizados exclusivamente para los fines señalados.

Usted tiene en todo momento el derecho a conocer qué datos personales tenemos de usted, para que los utilizamos y las condiciones de uso que les damos. Asimismo es su derecho solicitar la corrección de su información personal en caso de que esté desactualizada, sea inexacta o incompleta; de alguna manera, tiene derecho a que su información se elimine de nuestros registros o bases de datos cuando considere que la misma no está siendo utilizada adecuadamente; así como también oponerse al uso de sus datos personales para fines específicos.
""".strip()

# Texto corto para tenants que aún no tienen aviso local (AR/CL/CO).
AVISO_PRIVACIDAD_OOW_PLACEHOLDER_OTROS = (
    'Consulte el aviso de privacidad vigente de su centro de servicio SIC. '
    'Al marcar la casilla de aceptación, confirma que ha leído y acepta el '
    'tratamiento de sus datos personales conforme a la normativa local aplicable.'
)

# Vistas del diagrama de daños estéticos (laptop).
VISTAS_DANO_ESTETICO_LAPTOP = [
    ('pantalla', 'Pantalla'),
    ('top_cover', 'Top Cover'),
    ('palm', 'Palm / Teclado'),
    ('bottom', 'Bottom Case'),
    ('lat_izq', 'Lateral Izquierdo'),
    ('lat_der', 'Lateral Derecho'),
]

VISTAS_DANO_ESTETICO_ESCRITORIO = [
    ('frente', 'Frente'),
    ('trasera', 'Trasera'),
    ('esc_lat_izq', 'Lateral Izquierdo'),
    ('esc_lat_der', 'Lateral Derecho'),
    ('superior', 'Superior'),
]

# All-in-One: monitor integrado (frente/pantalla, trasera, laterales y base).
VISTAS_DANO_ESTETICO_AIO = [
    ('aio_pantalla', 'Pantalla / Frente'),
    ('aio_trasera', 'Trasera'),
    ('aio_lat_izq', 'Lateral Izquierdo'),
    ('aio_lat_der', 'Lateral Derecho'),
    ('aio_base', 'Base / Soporte'),
]

COMO_ENTERASTE_OOW_CHOICES = [
    ('google', 'Google'),
    ('facebook', 'Facebook'),
    ('instagram', 'Instagram'),
    ('referencia', 'Referencia personal'),
    ('dell', 'DELL'),
    ('ventas', 'Ventas'),
]

ESTADO_FORMATO_OOW_CHOICES = [
    ('borrador', 'Borrador'),
    ('finalizado', 'Finalizado'),
]

TIPO_DIAGRAMA_OOW_CHOICES = [
    ('laptop', 'Laptop'),
    ('escritorio', 'Escritorio'),
    ('aio', 'All in One'),
]

# Reutilizamos las mismas opciones de estado/diagrama/cómo te enteraste
# para el Formato Digital de Garantía Dell (mismo flujo wizard).
ESTADO_FORMATO_GARANTIA_CHOICES = ESTADO_FORMATO_OOW_CHOICES
TIPO_DIAGRAMA_GARANTIA_CHOICES = TIPO_DIAGRAMA_OOW_CHOICES
COMO_ENTERASTE_GARANTIA_CHOICES = COMO_ENTERASTE_OOW_CHOICES

# Accesorios del formato papel Dell / SICSER garantías.
ACCESORIOS_FORMATO_GARANTIA = [
    ('accesorio_cargador', 'Cargador'),
    ('accesorio_teclado', 'Teclado'),
    ('accesorio_pluma', 'Pluma'),
    ('accesorio_mouse', 'Mouse'),
    ('accesorio_monitor', 'Monitor'),
    ('accesorio_caja', 'Caja'),
    ('accesorio_bateria', 'Batería'),
    ('accesorio_docking', 'Docking'),
    ('accesorio_microsd_sim', 'MicroSD / SIM'),
    ('accesorio_otros', 'Otros'),
]

# Textos legales fijos de la página 1 del formato Dell (plantilla SIGMA).
# Se muestran en 2 columnas como el papel Dell/SICSER.
TEXTOS_LEGALES_FORMATO_GARANTIA_IZQ = [
    '*Recuperación/pérdida de datos no está cubierto bajo la garantía DELL',
    '* Luego de reinstalación de OS y controladores no se instalan Aplicaciones / Software ___',
]
TEXTOS_LEGALES_FORMATO_GARANTIA_DER = [
    '*Baterías poseen garantía limitada de 1 año ___',
    '* Los daños accidentales requieren cobertura Complete Care ___',
]
# Compatibilidad: lista plana por si algún código aún la importa.
TEXTOS_LEGALES_FORMATO_GARANTIA = (
    TEXTOS_LEGALES_FORMATO_GARANTIA_IZQ + TEXTOS_LEGALES_FORMATO_GARANTIA_DER
)

TEXTO_TIEMPO_RESPUESTA_GARANTIA = (
    'Tiempo de Respuesta: Una vez que el computador se haya recibido en nuestro '
    'centro de servicio, el tiempo estimado de reparación está sujeto a la '
    'disponibilidad en país de piezas requeridas para la reparación, en el caso '
    'de requerir partes. En este caso se solicitará la parte(s) a nuestro almacén '
    'en el extranjero por lo cual la llegada de las partes al país puede '
    'extenderse un numero indefinido de días ya que las partes son fabricadas '
    'en el extranjero lo que implica un tiempo de tránsito, y deben pasar '
    'aduanas, al recibirse en nuestro centro de servicio se procederá a la '
    'reparación. Siempre haremos el mejor esfuerzo en completar el proceso de '
    'diagnóstico y reparación a la brevedad posible, pero estamos dependientes '
    'de situaciones ajenas a nuestro control.'
)

TEXTO_PC_AUDIT_FORMATO_GARANTIA = (
    'NO SE UTILIZÓ EL APLICATIVO PC AUDIT PARA IDENTIFICAR LAS CARACTERÍSTICAS '
    'DEL HARDWARE Y SOFTWARE INSTALADO DEBIDO A QUE EL EQUIPO NO ENCIENDE, NO '
    'TIENE SISTEMA OPERATIVO WINDOWS O SU FALLA NO PERMITE UTILIZAR LA HERRAMIENTA.'
)

# Página final Dell: ACTIVIDADES NO INCLUIDAS EN EL SERVICIO DE GARANTÍA
# (sustituye el aviso de privacidad SIC en el PDF de garantía).
ACTIVIDADES_NO_INCLUIDAS_GARANTIA_DELL = [
    'Servidores y equipos de almacenamiento.',
    (
        'Equipos enviados por paquetería o mensajería hacia el Centro de Servicio. '
        'Desinstalación o reinstalación de productos y/o aplicaciones que no haya '
        'estado instalada cuando se compró el equipo.'
    ),
    (
        'El cliente acepta eximirnos de responsabilidad por la pérdida de información '
        'contenida en el disco duro y acepta que es su responsabilidad única respaldar '
        'su información personal contenida en el disco duro antes de entregarnos el '
        'equipo para diagnóstico y reparación.'
    ),
    'Recuperación de particiones en caso de cambio de Disco Duro.',
    'Ayuda o servicio de garantía para equipos/sistemas de terceros.',
    (
        'Análisis de fallas a nivel de Software de Microsoft o de Linux, '
        'compatibilidad de aplicaciones, o eliminación de virus/spyware.'
    ),
    'Configuración de servidores, impresoras, o Routers.',
    (
        'Configuración de usuarios finales de MS - Windows o Linux, incluyendo '
        'iconos del escritorio, carpetas y la configuración de cualquier aplicación.'
    ),
    'Cualquier actividad que no específicamente indicada en esta descripción de servicio de garantía.',
    (
        'Almacenaje del equipo en nuestras instalaciones por más de 5 días hábiles '
        'después de haber sido reparado y el cliente notificado.'
    ),
    (
        'Instalación y configuración de Sistema(s) Operativo(s) diferente al de fábrica. '
        'Así como no serán soportadas las actualizaciones a otros Sistema(s) Operativo(s) '
        'que hayan sido realizadas posteriormente.'
    ),
    (
        'Las baterías tienen una garantía limitada de hardware de 1 año de base cuando '
        'están incluidas como parte de una configuración portátil estándar, '
        'independientemente de la duración de la garantía aplicable al Producto cubierto.'
    ),
    (
        'Reparación de los Productos cubiertos que tengan daños o defectos estéticos '
        'y que no afecten el funcionamiento del equipo.'
    ),
    (
        'Soporte de equipos dañados por eventos causados por eventos de la naturaleza '
        '(relámpagos, inundaciones, tornados, terremotos y huracanes, entre otros), '
        'uso indebido, accidentes, maltrato del Producto cubierto o de sus componentes, '
        'traslado indebido del Producto, extracción o alteración del equipo o de las '
        'etiquetas de identificación de las piezas, o fallas causadas por un producto '
        'del que Dell no es responsable.'
    ),
    (
        'Los equipos con plaga (cucarachas, hormigas, arañas, etc.) de acuerdo a las '
        'políticas de fabricante, se inhabilita la garantía; para los casos fuera de '
        'garantía, de igual forma nos reservamos el derecho de admisión.'
    ),
]

# Checklist del auditor de calidad (página SERVICIO FINAL).
# Tuplas: (categoría, ítem). Categoría vacía = misma categoría que la fila anterior.
CHECKLIST_AUDITOR_GARANTIA_DELL = [
    ('Pruebas básicas', 'Prueba de encendido'),
    ('', '¿Falla reportada?'),
    ('Sistema Operativo', '¿Versión de Fábrica?'),
    ('', '¿Actualizado?'),
    ('Capacidades básicas', '¿Disco duro?'),
    ('', '¿Pantalla?'),
    ('', '¿Touch screen?'),
    ('', '¿Touch pad?'),
    ('', '¿Mouse?'),
    ('Energía', 'Batería'),
    ('', '¿AC Adapter?'),
    ('Conectividad', 'Wireless'),
    ('', 'Bluetooth'),
    ('', 'RJ45'),
    ('Drivers / Lectores / Extras', 'CD / DVD / ODD'),
    ('', 'SD / SIM'),
    ('', "USB's"),
    ('', '¿VGA?'),
    ('', 'Audífono'),
    ('', 'Pluma / Tablets'),
    ('', 'Teclado Externo'),
    ('', 'Mouse Externo'),
    ('', 'Bocinas'),
    ('Funcionalidades', 'Hibernación'),
    ('', 'Suspensión'),
]

# Pie de página WhatsApp (formato Dell SERVICIO FINAL).
WHATSAPP_FORMATO_GARANTIA_NUMEROS = ('55 1133 1295', '55 1137 5629')
WHATSAPP_FORMATO_GARANTIA_TEXTO = (
    'Estimado Usuario, cualquier duda referente a la reparación o seguimiento '
    'de su equipo estamos para servirle y ayudarle por Whatsapp en los números '
    '{n1} y {n2}'
).format(
    n1=WHATSAPP_FORMATO_GARANTIA_NUMEROS[0],
    n2=WHATSAPP_FORMATO_GARANTIA_NUMEROS[1],
)
