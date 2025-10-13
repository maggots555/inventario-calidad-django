"""
Filtros personalizados para templates del sistema RHITSO
Sistema de Seguimiento de Reparación Especializada

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Este archivo contiene "filtros" que se pueden usar en los templates de Django.
Un filtro modifica cómo se muestra un valor en el template.

Por ejemplo:
    {{ estado_rhitso|color_estado_rhitso }}
    
Esto toma el valor de 'estado_rhitso' y lo pasa por el filtro 'color_estado_rhitso'
que retorna un color hexadecimal según el owner del estado.

¿Por qué usar esto en lugar de colores de Bootstrap?
- Colores consistentes en toda la aplicación
- Fácil de mantener (un solo lugar para cambiar colores)
- Colores específicos por responsable (SIC, RHITSO, CLIENTE, etc.)
- Mejor contraste automático de texto sobre fondo coloreado
"""
from django import template

register = template.Library()


# =============================================================================
# DICCIONARIO DE COLORES PARA ESTADOS RHITSO POR OWNER
# =============================================================================

COLORES_ESTADO_RHITSO = {
    # Estados bajo responsabilidad de SIC (Centro de Servicio Interno)
    'SIC': '#17a2b8',              # Cian - Responsabilidad del centro de servicio
    
    # Estados bajo responsabilidad de RHITSO (Centro de Reparación Externa)
    'RHITSO': '#6610f2',           # Índigo/Morado - En manos del especialista externo
    
    # Estados bajo responsabilidad del CLIENTE
    'CLIENTE': '#ffc107',          # Amarillo - Esperando decisión/acción del cliente
    
    # Estados bajo responsabilidad de COMPRAS
    'COMPRAS': '#fd7e14',          # Naranja - Esperando adquisición de piezas
    
    # Estados CERRADOS (finalizados)
    'CERRADO': '#198754',          # Verde - Proceso completado exitosamente
    
    # Color por defecto para estados no categorizados
    'default': '#6c757d',          # Gris - Sin categorizar
}


# =============================================================================
# DICCIONARIO DE COLORES PARA COMPLEJIDAD
# =============================================================================

COLORES_COMPLEJIDAD = {
    'BAJA': '#198754',        # Verde - Reparación simple
    'MEDIA': '#17a2b8',       # Cian - Complejidad moderada
    'ALTA': '#fd7e14',        # Naranja - Reparación compleja
    'CRITICA': '#dc3545',     # Rojo - Máxima complejidad
    
    # Color por defecto
    'default': '#6c757d',     # Gris
}


# =============================================================================
# DICCIONARIO DE COLORES PARA GRAVEDAD DE INCIDENCIAS
# =============================================================================

COLORES_GRAVEDAD_INCIDENCIA = {
    'BAJA': '#198754',        # Verde - Impacto mínimo
    'MEDIA': '#17a2b8',       # Cian - Impacto moderado
    'ALTA': '#fd7e14',        # Naranja - Impacto significativo
    'CRITICA': '#dc3545',     # Rojo - Impacto crítico, requiere atención inmediata
    
    # Color por defecto
    'default': '#6c757d',     # Gris
}


# =============================================================================
# DICCIONARIO DE COLORES PARA ESTADO DE INCIDENCIAS
# =============================================================================

COLORES_ESTADO_INCIDENCIA = {
    'ABIERTA': '#dc3545',         # Rojo - Requiere atención
    'EN_PROCESO': '#ffc107',      # Amarillo - En resolución
    'EN_REVISION': '#17a2b8',     # Cian - Bajo revisión
    'RESUELTA': '#198754',        # Verde - Completada exitosamente
    'CERRADA': '#6c757d',         # Gris - Archivada
    
    # Color por defecto
    'default': '#6c757d',         # Gris
}


# =============================================================================
# DICCIONARIO DE COLORES PARA PRIORIDAD
# =============================================================================

COLORES_PRIORIDAD = {
    'BAJA': '#198754',        # Verde - No urgente
    'MEDIA': '#17a2b8',       # Cian - Atención normal
    'ALTA': '#fd7e14',        # Naranja - Urgente
    'CRITICA': '#dc3545',     # Rojo - Máxima urgencia
    
    # Color por defecto
    'default': '#6c757d',     # Gris
}


# =============================================================================
# DICCIONARIO DE COLORES PARA IMPACTO AL CLIENTE
# =============================================================================

COLORES_IMPACTO_CLIENTE = {
    'BAJO': '#198754',        # Verde - Mínimo impacto
    'MEDIO': '#ffc107',       # Amarillo - Impacto moderado
    'ALTO': '#fd7e14',        # Naranja - Impacto significativo
    'CRITICO': '#dc3545',     # Rojo - Impacto crítico en experiencia del cliente
    
    # Color por defecto
    'default': '#6c757d',     # Gris
}


# =============================================================================
# DICCIONARIO DE COLORES PARA ESTADOS ESPECÍFICOS DE RHITSO
# =============================================================================

# PALETA DE COLORES PERSONALIZADA RHITSO
# Definición de códigos hexadecimales para cada nombre de color
PALETA_COLORES_RHITSO = {
    'rosa-claro': '#FFB6C1',          # Light Pink
    'rhitso-rosa-claro': '#FFC0CB',   # Rosa específico RHITSO
    'azul-cian': '#00CED1',           # Dark Turquoise / Cian
    'verde-lima': '#32CD32',          # Lime Green
    'rojo-intenso': '#DC143C',        # Crimson
    'naranja-claro': '#FFB347',       # Light Orange
    'naranja': '#FF8C00',             # Dark Orange
    'verde-fuerte': '#228B22',        # Forest Green
    'azul-electrico': '#0080FF',      # Electric Blue
    'morado-claro': '#B19CD9',        # Light Purple
    'azul-claro': '#87CEEB',          # Sky Blue
    'amarillo-claro': '#FFE66D',      # Light Yellow
    'morado-fuerte': '#8B00FF',       # Violet / Purple
    'rojo': '#FF0000',                # Red
    'verde-agua': '#40E0D0',          # Turquoise
    'verde': '#00FF00',               # Lime / Green
    'verde-claro': '#90EE90',         # Light Green
    'magenta': '#FF00FF',             # Magenta / Fuchsia
    'marron-claro': '#D2B48C',        # Tan / Light Brown
    'azul-marino': "#0C0C68",         # Navy Blue
    'coral': '#FF7F50',               # Coral
    'gris': '#808080',                # Gray
}

COLORES_ESTADO_ESPECIFICO = {
    # ===== ESTADOS SIC - INICIO DEL PROCESO =====
    'CANDIDATO RHITSO': PALETA_COLORES_RHITSO['rhitso-rosa-claro'],
    'PENDIENTE DE CONFIRMAR ENVIO A RHITSO': PALETA_COLORES_RHITSO['azul-cian'],
    'USUARIO ACEPTA ENVIO A RHITSO': PALETA_COLORES_RHITSO['verde-lima'],
    'USUARIO NO ACEPTA ENVIO A RHITSO': PALETA_COLORES_RHITSO['rojo-intenso'],
    'EN ESPERA DE ENTREGAR EQUIPO A RHITSO': PALETA_COLORES_RHITSO['rosa-claro'],
    
    # ===== INCIDENCIAS Y COTIZACIONES SIC =====
    'INCIDENCIA SIC': PALETA_COLORES_RHITSO['rojo-intenso'],
    'COTIZACIÓN ENVIADA A SIC': PALETA_COLORES_RHITSO['naranja-claro'],
    'EN ESPERA DE PIEZA POR SIC': PALETA_COLORES_RHITSO['naranja'],
    'PIEZA DE SIC ENVIADA A RHITSO': PALETA_COLORES_RHITSO['naranja'],
    
    # ===== RETORNO Y PRUEBAS EN SIC =====
    'EQUIPO RETORNADO A SIC': PALETA_COLORES_RHITSO['verde-fuerte'],
    'EN PRUEBAS SIC': PALETA_COLORES_RHITSO['azul-electrico'],
    
    # ===== ESTADOS RHITSO - INGRESO Y DIAGNÓSTICO =====
    'EN ESPERA DE CONFIRMAR INGRESO': PALETA_COLORES_RHITSO['azul-cian'],
    'EQUIPO EN RHITSO': PALETA_COLORES_RHITSO['morado-claro'],
    'QR COMPARTIDO (EN DIAGNOSTICO)': PALETA_COLORES_RHITSO['azul-electrico'],
    'DIAGNOSTICO FINAL': PALETA_COLORES_RHITSO['azul-claro'],
    
    # ===== PROCESOS TÉCNICOS RHITSO =====
    'EN PROCESO DE RESPALDO': PALETA_COLORES_RHITSO['amarillo-claro'],
    'EN PROCESO DE REBALLING': PALETA_COLORES_RHITSO['morado-fuerte'],
    'EN PRUEBAS (DE DIAGNOSTICO)': PALETA_COLORES_RHITSO['amarillo-claro'],
    'NO APTO PARA REPARACIÓN': PALETA_COLORES_RHITSO['rojo'],
    
    # ===== ESPERAS Y REPARACIÓN RHITSO =====
    'EN ESPERA DE PARTES/COMPONENTE': PALETA_COLORES_RHITSO['verde-agua'],
    'EN PRUEBAS (REPARADO)': PALETA_COLORES_RHITSO['verde'],
    'EQUIPO REPARADO': PALETA_COLORES_RHITSO['verde-claro'],
    'INCIDENCIA RHITSO': PALETA_COLORES_RHITSO['magenta'],
    'EN ESPERA DEL RETORNO DEL EQUIPO': PALETA_COLORES_RHITSO['marron-claro'],
    
    # ===== ESTADOS CLIENTE =====
    'CLIENTE ACEPTA COTIZACIÓN': PALETA_COLORES_RHITSO['verde-lima'],
    'COTIZACIÓN ENVIADA AL CLIENTE': PALETA_COLORES_RHITSO['morado-claro'],
    'CLIENTE NO ACEPTA COTIZACIÓN': PALETA_COLORES_RHITSO['rojo-intenso'],  # Cambiado de 'rojo-claro'
    'PETICIÓN AL USUARIO': PALETA_COLORES_RHITSO['azul-marino'],
    
    # ===== ESTADOS COMPRAS Y PIEZAS =====
    'EN ESPERA DE LA OC': PALETA_COLORES_RHITSO['marron-claro'],
    'PIEZA DOA': PALETA_COLORES_RHITSO['coral'],
    'PIEZA WPB': PALETA_COLORES_RHITSO['coral'],
    
    # ===== ESTADO FINAL =====
    'CERRADO': PALETA_COLORES_RHITSO['gris'],
    
    # Color por defecto para estados no definidos
    'default': '#6c757d',                                # Gris neutro
}


# =============================================================================
# FILTRO 1: COLOR SEGÚN OWNER DEL ESTADO RHITSO
# =============================================================================

@register.filter(name='color_estado_rhitso')
def color_estado_rhitso(owner):
    """
    Retorna el color hexadecimal apropiado según el owner del estado RHITSO.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Este filtro recibe el owner de un EstadoRHITSO (SIC, RHITSO, CLIENTE, etc.)
    y retorna un color específico para ese responsable.
    
    ¿Por qué es útil?
    - Identificación visual rápida de quién es responsable
    - Colores consistentes en toda la aplicación
    - Un solo lugar para cambiar la paleta de colores
    
    Args:
        owner (str): Responsable del estado ('SIC', 'RHITSO', 'CLIENTE', 'COMPRAS', 'CERRADO')
    
    Returns:
        str: Color hexadecimal (ej: '#17a2b8')
    
    Ejemplo de uso en template:
        {% load rhitso_filters %}
        <span class="badge" 
              style="background-color: {{ estado.owner|color_estado_rhitso }}; 
                     color: {{ estado.owner|color_estado_rhitso|text_color_for_bg }};">
            {{ estado.estado }}
        </span>
    """
    if not owner:
        return COLORES_ESTADO_RHITSO['default']
    
    # Convertir a mayúsculas y limpiar espacios
    owner_clean = str(owner).upper().strip()
    
    # Buscar el color correspondiente
    return COLORES_ESTADO_RHITSO.get(owner_clean, COLORES_ESTADO_RHITSO['default'])


# =============================================================================
# FILTRO 2: COLOR SEGÚN COMPLEJIDAD
# =============================================================================

@register.filter(name='color_complejidad')
def color_complejidad(complejidad):
    """
    Retorna el color hexadecimal según el nivel de complejidad.
    
    Args:
        complejidad (str): Nivel de complejidad ('BAJA', 'MEDIA', 'ALTA', 'CRITICA')
    
    Returns:
        str: Color hexadecimal
    """
    if not complejidad:
        return COLORES_COMPLEJIDAD['default']
    
    complejidad_clean = str(complejidad).upper().strip()
    return COLORES_COMPLEJIDAD.get(complejidad_clean, COLORES_COMPLEJIDAD['default'])


# =============================================================================
# FILTRO 3: COLOR SEGÚN GRAVEDAD DE INCIDENCIA
# =============================================================================

@register.filter(name='color_gravedad_incidencia')
def color_gravedad_incidencia(gravedad):
    """
    Retorna el color hexadecimal según la gravedad de una incidencia RHITSO.
    
    Args:
        gravedad (str): Gravedad ('BAJA', 'MEDIA', 'ALTA', 'CRITICA')
    
    Returns:
        str: Color hexadecimal
    """
    if not gravedad:
        return COLORES_GRAVEDAD_INCIDENCIA['default']
    
    gravedad_clean = str(gravedad).upper().strip()
    return COLORES_GRAVEDAD_INCIDENCIA.get(gravedad_clean, COLORES_GRAVEDAD_INCIDENCIA['default'])


# =============================================================================
# FILTRO 4: COLOR SEGÚN ESTADO DE INCIDENCIA
# =============================================================================

@register.filter(name='color_estado_incidencia')
def color_estado_incidencia(estado):
    """
    Retorna el color hexadecimal según el estado de una incidencia RHITSO.
    
    Args:
        estado (str): Estado de la incidencia ('ABIERTA', 'EN_PROCESO', etc.)
    
    Returns:
        str: Color hexadecimal
    """
    if not estado:
        return COLORES_ESTADO_INCIDENCIA['default']
    
    estado_clean = str(estado).upper().strip()
    return COLORES_ESTADO_INCIDENCIA.get(estado_clean, COLORES_ESTADO_INCIDENCIA['default'])


# =============================================================================
# FILTRO 5: COLOR SEGÚN PRIORIDAD
# =============================================================================

@register.filter(name='color_prioridad')
def color_prioridad(prioridad):
    """
    Retorna el color hexadecimal según la prioridad.
    
    Args:
        prioridad (str): Prioridad ('BAJA', 'MEDIA', 'ALTA', 'CRITICA')
    
    Returns:
        str: Color hexadecimal
    """
    if not prioridad:
        return COLORES_PRIORIDAD['default']
    
    prioridad_clean = str(prioridad).upper().strip()
    return COLORES_PRIORIDAD.get(prioridad_clean, COLORES_PRIORIDAD['default'])


# =============================================================================
# FILTRO 6: COLOR SEGÚN IMPACTO AL CLIENTE
# =============================================================================

@register.filter(name='color_impacto_cliente')
def color_impacto_cliente(impacto):
    """
    Retorna el color hexadecimal según el impacto al cliente.
    
    Args:
        impacto (str): Impacto ('BAJO', 'MEDIO', 'ALTO', 'CRITICO')
    
    Returns:
        str: Color hexadecimal
    """
    if not impacto:
        return COLORES_IMPACTO_CLIENTE['default']
    
    impacto_clean = str(impacto).upper().strip()
    return COLORES_IMPACTO_CLIENTE.get(impacto_clean, COLORES_IMPACTO_CLIENTE['default'])


# =============================================================================
# FILTRO 7: COLOR SEGÚN ESTADO ESPECÍFICO DE RHITSO
# =============================================================================

@register.filter(name='color_estado_especifico')
def color_estado_especifico(estado):
    """
    Retorna el color hexadecimal según el estado específico de RHITSO.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Este filtro es diferente al filtro 'color_estado_rhitso' porque:
    
    - color_estado_rhitso: Usa el OWNER (SIC, RHITSO, CLIENTE, etc.)
    - color_estado_especifico: Usa el NOMBRE COMPLETO del estado
    
    ¿Por qué necesitamos ambos?
    ---------------------------
    El filtro por OWNER agrupa estados por responsable (útil para dashboards).
    Este filtro da un color único a cada estado específico (útil para detalles).
    
    Por ejemplo:
    - "USUARIO ACEPTA ENVIO A RHITSO" → Verde (#198754)
    - "USUARIO NO ACEPTA ENVIO A RHITSO" → Rojo (#dc3545)
    - "INCIDENCIA RHITSO" → Rojo (#dc3545)
    - "DIAGNOSTICO FINAL" → Púrpura (#6610f2)
    
    Esto permite identificar visualmente el estado exacto sin leer el texto.
    
    Categorías de colores:
    ----------------------
    🟢 Verde: Éxitos, aceptaciones, completado
    🔴 Rojo: Rechazos, problemas, incidencias
    🟡 Amarillo/Naranja: Esperas, advertencias
    🔵 Azul: Información, estados normales
    🟣 Púrpura: Procesos especiales de RHITSO
    ⚫ Gris oscuro: Cerrado
    
    Args:
        estado (str): Nombre completo del estado (ej: 'EQUIPO EN RHITSO')
    
    Returns:
        str: Color hexadecimal (ej: '#198754')
    
    Ejemplo de uso en template:
        {% load rhitso_filters %}
        <span class="badge" 
              style="background-color: {{ orden.estado_rhitso.estado|color_estado_especifico }}; 
                     color: {{ orden.estado_rhitso.estado|color_estado_especifico|text_color_for_bg }};">
            {{ orden.estado_rhitso.estado }}
        </span>
    """
    if not estado:
        return COLORES_ESTADO_ESPECIFICO['default']
    
    # Convertir a mayúsculas y limpiar espacios
    estado_clean = str(estado).upper().strip()
    
    # Buscar el color correspondiente al estado específico
    return COLORES_ESTADO_ESPECIFICO.get(estado_clean, COLORES_ESTADO_ESPECIFICO['default'])


# =============================================================================
# FILTRO 8: CALCULAR COLOR DE TEXTO ÓPTIMO PARA CONTRASTE
# =============================================================================

@register.filter(name='text_color_for_bg')
def text_color_for_bg(hex_color):
    """
    Calcula el color de texto óptimo (blanco o negro) para un color de fondo dado.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Este filtro es crucial para la accesibilidad y legibilidad.
    
    ¿Qué hace?
    Recibe un color de fondo (ej: #FF5733) y decide si el texto debe ser
    blanco o negro para tener el mejor contraste posible.
    
    ¿Cómo funciona?
    1. Convierte el color hexadecimal a valores RGB (Rojo, Verde, Azul)
    2. Calcula la "luminosidad" del color usando una fórmula estándar
    3. Si el color es claro (luminosidad > 128), usa texto negro
    4. Si el color es oscuro (luminosidad <= 128), usa texto blanco
    
    La fórmula de luminosidad pondera los colores según cómo el ojo humano
    los percibe: el verde afecta más que el rojo, y el rojo más que el azul.
    
    Args:
        hex_color (str): Color en formato hexadecimal (ej: #FF5733 o FF5733)
    
    Returns:
        str: Color de texto recomendado ('#ffffff' para blanco o '#000000' para negro)
    
    Ejemplo de uso en template:
        {% load rhitso_filters %}
        <span style="background-color: {{ estado.owner|color_estado_rhitso }}; 
                     color: {{ estado.owner|color_estado_rhitso|text_color_for_bg }};">
            {{ estado.estado }}
        </span>
    """
    # Si el color no está definido o está vacío, retornar blanco por defecto
    if not hex_color:
        return '#ffffff'
    
    # Remover el símbolo # si está presente
    hex_color = str(hex_color).lstrip('#')
    
    # Validar que sea un color hexadecimal válido (6 caracteres)
    if len(hex_color) != 6:
        return '#ffffff'
    
    try:
        # Convertir valores hexadecimales a RGB
        # hex_color[0:2] = Rojo (Red)
        # hex_color[2:4] = Verde (Green)
        # hex_color[4:6] = Azul (Blue)
        r = int(hex_color[0:2], 16)  # Convertir los primeros 2 caracteres de hex a decimal
        g = int(hex_color[2:4], 16)  # Convertir los siguientes 2 caracteres de hex a decimal
        b = int(hex_color[4:6], 16)  # Convertir los últimos 2 caracteres de hex a decimal
        
        # Calcular luminosidad usando la fórmula estándar de percepción humana
        # Esta fórmula pondera los colores de forma similar a cómo el ojo humano
        # percibe el brillo: el verde afecta más que el rojo, y el rojo más que el azul
        luminosidad = (0.299 * r + 0.587 * g + 0.114 * b)
        
        # Si la luminosidad es mayor a 128 (escala de 0-255), el fondo es claro
        # entonces usamos texto negro para mejor contraste
        # Si es menor o igual a 128, el fondo es oscuro, usamos texto blanco
        return '#000000' if luminosidad > 128 else '#ffffff'
    
    except (ValueError, TypeError):
        # Si hay algún error al procesar el color, retornar blanco por seguridad
        return '#ffffff'
