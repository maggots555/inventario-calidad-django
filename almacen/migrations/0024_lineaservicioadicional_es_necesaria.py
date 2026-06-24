# Generated manually — campo es_necesaria para clasificar servicios en PDF cotizador

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('almacen', '0023_add_es_necesaria_sugerida_por_tecnico_to_lineacotizacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='lineaservicioadicional',
            name='es_necesaria',
            field=models.BooleanField(
                default=False,
                help_text='Marcar si el servicio es indispensable. Desmarcado = opcional (ej. limpieza)',
                verbose_name='¿Es necesaria?',
            ),
        ),
    ]
