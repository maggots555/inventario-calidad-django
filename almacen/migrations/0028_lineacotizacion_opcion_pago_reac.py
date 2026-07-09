# Migración: forma de pago al aprobar equipo reacondicionado

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('almacen', '0027_lineacotizacion_es_linea_reacondicionado'),
    ]

    operations = [
        migrations.AddField(
            model_name='lineacotizacion',
            name='opcion_pago_reac',
            field=models.CharField(
                blank=True,
                choices=[
                    ('contado', 'Pago de contado'),
                    ('diferido_3_meses', 'Financiamiento 3 meses'),
                    ('diferido_6_meses', 'Financiamiento 6 meses'),
                    ('diferido_12_meses', 'Financiamiento 12 meses'),
                ],
                default='',
                help_text='Opción de pago elegida por el cliente al aprobar la línea reac (contado o meses)',
                max_length=20,
                verbose_name='Forma de pago reacondicionado',
            ),
        ),
    ]
