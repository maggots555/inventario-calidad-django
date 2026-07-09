# Migración: flag para líneas de equipo reacondicionado (P0125)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('almacen', '0026_reacondicionado_cotizacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='lineacotizacion',
            name='es_linea_reacondicionado',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'True si esta línea representa una propuesta de equipo reacondicionado (P0125). '
                    'No se sincroniza a PiezaCotizada; al aprobar va a PiezaVentaMostrador en ST.'
                ),
                verbose_name='¿Es equipo reacondicionado?',
            ),
        ),
    ]
