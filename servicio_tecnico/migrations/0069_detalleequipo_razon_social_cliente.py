# Generated manually — razón social aparte del nombre de contacto (import OOW)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('servicio_tecnico', '0068_formato_venta_mostrador'),
    ]

    operations = [
        migrations.AddField(
            model_name='detalleequipo',
            name='razon_social_cliente',
            field=models.CharField(
                blank=True,
                help_text=(
                    'Razón social / empresa (opcional). '
                    'En import OOW viene de SICSER nombre_cliente.'
                ),
                max_length=200,
            ),
        ),
        migrations.AlterField(
            model_name='detalleequipo',
            name='nombre_cliente',
            field=models.CharField(
                blank=True,
                help_text=(
                    'Nombre de la persona de contacto (opcional). '
                    'En import OOW viene de SICSER contacto.'
                ),
                max_length=200,
            ),
        ),
    ]
