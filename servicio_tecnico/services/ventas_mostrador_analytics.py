"""
Analytics auxiliares de Venta Mostrador (Fase 8 modularización).

EXPLICACIÓN PARA PRINCIPIANTES:
Antes vivían al inicio de views.py. El dashboard OOW/FL las usa para
clasificar ventas y armar el top de productos. Viven en services/ para
no acoplar lógica de negocio al monolito HTTP.
"""

# ============================================================================
# FUNCIONES AUXILIARES PARA ANÁLISIS DE VENTAS MOSTRADOR
# ============================================================================

def determinar_categoria_venta(venta_mostrador):
    """
    Determina la categoría principal de una VentaMostrador.

    PARÁMETROS:
    - venta_mostrador: Instancia de VentaMostrador
    
    RETORNA:
    dict con keys:
        'categoria': str (ej: "Paquete Premium", "Piezas (3 unidades)")
        'icono': str (emoji para visual)
    """
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Estamos dentro de services/, no junto a views.py.
    # Por eso NO usamos "from .models" (buscaría services/models.py).
    # Usamos el import absoluto, igual que historial.py y multimedia.py.
    from servicio_tecnico.models import VentaMostrador
    
    # OPCIÓN 1: Si hay paquete (premium/oro/plata)
    if venta_mostrador.paquete != 'ninguno':
        paquete_nombre = venta_mostrador.paquete.capitalize()
        return {
            'categoria': f'Paquete {paquete_nombre}',
            'icono': '📦'
        }
    
    # OPCIÓN 2: Si hay piezas individuales vendidas
    cantidad_piezas = venta_mostrador.piezas_vendidas.count()
    if cantidad_piezas > 0:
        plural = "unidad" if cantidad_piezas == 1 else "unidades"
        return {
            'categoria': f'Piezas ({cantidad_piezas} {plural})',
            'icono': '⚙️'
        }
    
    # OPCIÓN 3: Si hay servicios adicionales
    if venta_mostrador.incluye_cambio_pieza:
        return {
            'categoria': 'Cambio de Pieza',
            'icono': '🔧'
        }
    
    if venta_mostrador.incluye_limpieza:
        return {
            'categoria': 'Limpieza & Mantenimiento',
            'icono': '🧹'
        }
    
    if venta_mostrador.incluye_kit_limpieza:
        return {
            'categoria': 'Kit Limpieza',
            'icono': '🧽'
        }
    
    if venta_mostrador.incluye_reinstalacion_so:
        return {
            'categoria': 'Reinstalación SO',
            'icono': '💾'
        }
    
    # OPCIÓN 4: Si nada de lo anterior
    return {
        'categoria': 'Otros Servicios',
        'icono': '📝'
    }


def obtener_top_productos_vendidos(ordenes, limite=5):
    """
    Obtiene los TOP N productos más vendidos en las órdenes dadas.

    RETORNA:
    list de dicts con keys:
        'descripcion': str (nombre de la pieza)
        'cantidad': int (total vendidas)
        'subtotal': Decimal (monto total generado)
    """
    from collections import defaultdict
    from decimal import Decimal
    # Misma regla: desde services/ el paquete padre es servicio_tecnico.
    from servicio_tecnico.models import VentaMostrador
    
    # Diccionario para acumular datos por pieza
    piezas_vendidas = defaultdict(lambda: {'cantidad': 0, 'subtotal': Decimal('0.00')})
    
    # Recorrer todas las órdenes con venta mostrador
    for orden in ordenes:
        if hasattr(orden, 'venta_mostrador') and orden.venta_mostrador:
            venta = orden.venta_mostrador
            # Contar cada pieza vendida
            for pieza in venta.piezas_vendidas.all():
                clave = pieza.descripcion_pieza
                piezas_vendidas[clave]['cantidad'] += pieza.cantidad
                piezas_vendidas[clave]['subtotal'] += pieza.subtotal
    
    # Convertir a lista y ordenar por cantidad descendente
    piezas_lista = [
        {
            'descripcion': desc,
            'cantidad': data['cantidad'],
            'subtotal': data['subtotal']
        }
        for desc, data in piezas_vendidas.items()
    ]
    
    piezas_lista.sort(key=lambda x: x['cantidad'], reverse=True)
    
    # Retornar solo los top N
    return piezas_lista[:limite]


