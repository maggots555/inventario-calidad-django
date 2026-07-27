# Generated manually — fecha real de importación SICSER → SIGMA

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('servicio_tecnico', '0057_aviso_recepcion_equipo_disponible'),
    ]

    operations = [
        migrations.AddField(
            model_name='detalleequipo',
            name='fecha_importacion_sicser',
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text=(
                    'Momento en que se importó el registro desde SICSER a SIGMA. '
                    'Independiente de fecha_ingreso (fecha SICSER / recepción).'
                ),
                null=True,
            ),
        ),
    ]
