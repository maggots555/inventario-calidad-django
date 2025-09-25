from django.core.management.base import BaseCommand
from django.db import transaction
from inventario.models import Producto, Movimiento


def total_from_state(units, actual, unit_size):
    """Calcula el total disponible en la misma forma que Producto.cantidad_total_disponible"""
    try:
        unit_size = float(unit_size)
    except Exception:
        unit_size = 0
    if unit_size == 0:
        return float(units)
    if units > 0:
        unidades_completas = max(0, units - 1) * unit_size
    else:
        unidades_completas = 0
    return unidades_completas + float(actual or 0)


def unpack_total(total, unit_size):
    """Dado un total en la unidad base, devuelve (units, cantidad_actual) siguiendo la lógica del modelo."""
    total = max(0.0, float(total or 0))
    unit_size = float(unit_size) if unit_size else 0.0
    if unit_size == 0:
        # No fraccionable, treat total as units
        return int(total), 0.0
    if total == 0:
        return 0, 0.0
    unidades_completas = int(total // unit_size)
    remainder = total % unit_size
    if remainder > 0:
        return unidades_completas + 1, remainder
    else:
        if unidades_completas > 0:
            return unidades_completas, unit_size
        else:
            return 0, 0.0


class Command(BaseCommand):
    help = 'Recalcula y guarda los campos fraccionarios resultantes en movimientos históricos'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando recalculo de movimientos fraccionarios...')
        productos = Producto.objects.all()
        total_movimientos_actualizados = 0
        for producto in productos:
            unit_size = producto.cantidad_unitaria
            # iniciar desde el estado final del producto
            post_units = producto.cantidad
            post_actual = producto.cantidad_actual

            movimientos = Movimiento.objects.filter(producto=producto).order_by('-fecha_movimiento')
            for mov in movimientos:
                # Guardar los valores resultantes (son el estado POSTERIOR al movimiento)
                if mov.es_movimiento_fraccionario and producto.es_fraccionable:
                    pct = None
                    try:
                        if unit_size and unit_size > 0:
                            pct = (float(post_actual) / float(unit_size)) * 100
                            pct = max(0.0, min(100.0, pct))
                    except Exception:
                        pct = None

                    # Update movimiento fields
                    mov.cantidad_fraccionaria_resultante = float(post_actual or 0)
                    mov.porcentaje_resultante = pct
                    mov.save(update_fields=['cantidad_fraccionaria_resultante', 'porcentaje_resultante'])
                    total_movimientos_actualizados += 1

                    # Reverse apply the movement to get the PRE state
                    q = float(mov.cantidad_fraccionaria or 0)
                    post_total = total_from_state(post_units, post_actual, unit_size)
                    if mov.tipo == 'salida':
                        pre_total = post_total + q
                    elif mov.tipo in ['entrada', 'devolucion']:
                        pre_total = post_total - q
                    else:
                        pre_total = post_total

                    pre_units, pre_actual = unpack_total(pre_total, unit_size)
                    post_units, post_actual = pre_units, pre_actual

                else:
                    # No fraccionario: ajustar unidades al revertir
                    if mov.tipo in ['entrada', 'devolucion']:
                        pre_units = max(0, post_units - (mov.cantidad or 0))
                    elif mov.tipo == 'salida':
                        pre_units = post_units + (mov.cantidad or 0)
                    else:
                        pre_units = post_units

                    # Si no quedan unidades, el actual debe ser 0
                    if pre_units == 0:
                        pre_actual = 0.0
                    else:
                        # Mantener post_actual como aproximación
                        pre_actual = post_actual

                    post_units, post_actual = pre_units, pre_actual

        self.stdout.write(self.style.SUCCESS(f'Recalculo completo. Movimientos actualizados: {total_movimientos_actualizados}'))
