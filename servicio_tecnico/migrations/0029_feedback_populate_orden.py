"""
Paso 2 de 3: Data migration — populate orden_id from cotizacion_id.

Cotizacion uses OneToOneField(OrdenServicio, primary_key=True), so
cotizacion_id IS the orden_id. Safe direct copy.
"""

from django.db import migrations, models


def populate_orden(apps, schema_editor):
    FeedbackCliente = apps.get_model('servicio_tecnico', 'FeedbackCliente')
    FeedbackCliente.objects.filter(
        orden__isnull=True,
        cotizacion__isnull=False,
    ).update(orden_id=models.F('cotizacion_id'))


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('servicio_tecnico', '0028_feedback_add_orden_fk_nullable_cotizacion'),
    ]

    operations = [
        migrations.RunPython(populate_orden, reverse_noop),
    ]
