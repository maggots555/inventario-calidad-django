"""
Paso 3 de 3: Enforce NOT NULL on orden FK.

All existing rows now have orden_id populated (from 0029).
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('servicio_tecnico', '0029_feedback_populate_orden'),
    ]

    operations = [
        migrations.AlterField(
            model_name='feedbackcliente',
            name='orden',
            field=models.ForeignKey(
                help_text='Orden de servicio a la que pertenece este feedback (siempre presente).',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='feedbacks_directos',
                to='servicio_tecnico.ordenservicio',
                verbose_name='Orden',
            ),
        ),
    ]
