"""
Paso 1 de 3: Schema changes for FeedbackCliente.

- Add 'orden' FK (nullable temporalmente para permitir data migration).
- Make 'cotizacion' FK nullable (VentaMostrador no tiene cotización).
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('servicio_tecnico', '0027_populate_costo_paquete_historico'),
    ]

    operations = [
        # 1. cotizacion → nullable
        migrations.AlterField(
            model_name='feedbackcliente',
            name='cotizacion',
            field=models.ForeignKey(
                blank=True,
                help_text='Cotización asociada (nullable para VentaMostrador).',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='feedbacks',
                to='servicio_tecnico.cotizacion',
                verbose_name='Cotización',
            ),
        ),
        # 2. orden FK → nullable (temporal)
        migrations.AddField(
            model_name='feedbackcliente',
            name='orden',
            field=models.ForeignKey(
                help_text='Orden de servicio a la que pertenece este feedback (siempre presente).',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='feedbacks_directos',
                to='servicio_tecnico.ordenservicio',
                verbose_name='Orden',
            ),
            preserve_default=False,
        ),
    ]
