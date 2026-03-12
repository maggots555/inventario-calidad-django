"""
Migración de datos: Poblar es_fuera_garantia en órdenes existentes.

Recorre todas las órdenes que tienen DetalleEquipo con orden_cliente
que empieza con 'OOW-' o 'FL-' y les activa es_fuera_garantia=True.
"""

from django.db import migrations, models


def poblar_es_fuera_garantia(apps, schema_editor):
    """
    Activa es_fuera_garantia=True en órdenes existentes cuyo
    DetalleEquipo.orden_cliente empiece con 'OOW-' o 'FL-'.
    """
    OrdenServicio = apps.get_model('servicio_tecnico', 'OrdenServicio')
    
    # Actualizar en batch usando update() — más eficiente que recorrer fila por fila
    actualizadas = OrdenServicio.objects.filter(
        models.Q(detalle_equipo__orden_cliente__istartswith='OOW-') |
        models.Q(detalle_equipo__orden_cliente__istartswith='FL-')
    ).update(es_fuera_garantia=True)
    
    if actualizadas:
        print(f"\n  → {actualizadas} órdenes marcadas como fuera de garantía (OOW-/FL-)")


def revertir_es_fuera_garantia(apps, schema_editor):
    """Revierte: pone todas las órdenes en es_fuera_garantia=False."""
    OrdenServicio = apps.get_model('servicio_tecnico', 'OrdenServicio')
    OrdenServicio.objects.filter(es_fuera_garantia=True).update(es_fuera_garantia=False)


class Migration(migrations.Migration):

    dependencies = [
        ('servicio_tecnico', '0031_add_es_fuera_garantia'),
    ]

    operations = [
        migrations.RunPython(
            poblar_es_fuera_garantia,
            revertir_es_fuera_garantia,
        ),
    ]
