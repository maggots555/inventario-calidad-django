"""
Montos del feedback de rechazo que sí puede ver el cliente.

EXPLICACIÓN PARA PRINCIPIANTES:
costo_unitario es lo que la pieza le costó a SIC. precio_unitario_cliente
es lo que se le cotizó a la persona. En el correo y en la página pública
solo puede aparecer el segundo. Si aún no hay precio de cliente, esa
línea no suma: no rellenamos el hueco con el costo interno.
"""

from decimal import Decimal


def precio_unitario_para_cliente(pieza):
    """
    Precio unitario que se le cotizó al cliente, o None si no existe.

    Objetivo de negocio:
        Separar el precio de venta del costo interno. Un None significa
        "todavía no hay precio para el cliente", no "cuesta cero".

    Args:
        pieza: PiezaCotizada, o un dict con la clave
            ``precio_unitario_cliente``.

    Returns:
        Decimal, número, o None.

    Efectos secundarios:
        Ninguno.
    """
    if isinstance(pieza, dict):
        return pieza.get('precio_unitario_cliente')
    return getattr(pieza, 'precio_unitario_cliente', None)


def monto_rechazo_visible_cliente(piezas) -> Decimal:
    """
    Suma lo que el cliente vio en la cotización (precio × cantidad).

    Objetivo de negocio:
        El total del correo y de la página de "por qué rechazaste"
        debe coincidir con el precio cotizado, no con el costo de SIC.

    Args:
        piezas: Iterable de piezas (modelo o dict) con
            ``precio_unitario_cliente`` y ``cantidad``.

    Returns:
        Decimal: Total. Las piezas sin precio de cliente no suman.

    Efectos secundarios:
        Ninguno. No guarda nada.
    """
    total = Decimal('0.00')
    for pieza in piezas:
        precio = precio_unitario_para_cliente(pieza)
        # Sin precio de cliente no inventamos el monto con el costo interno.
        if precio is None:
            continue
        if isinstance(pieza, dict):
            cantidad = pieza.get('cantidad') or 1
        else:
            cantidad = pieza.cantidad or 1
        total += Decimal(precio) * Decimal(cantidad)
    return total
