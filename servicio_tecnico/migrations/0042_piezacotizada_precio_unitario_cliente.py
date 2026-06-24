# Generated manually — precio al cliente en PiezaCotizada (sync desde Almacén)

import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('servicio_tecnico', '0041_detalleequipo_nombre_cliente_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='piezacotizada',
            name='precio_unitario_cliente',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Precio cotizado al cliente por unidad (sin IVA), sincronizado desde Almacén',
                max_digits=10,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal('0.00'))],
            ),
        ),
    ]
