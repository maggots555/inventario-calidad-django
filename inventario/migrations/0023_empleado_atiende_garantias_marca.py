"""
Casillas para saber qué dispatcher atiende garantías Dell y cuáles Lenovo.

EXPLICACIÓN PARA PRINCIPIANTES:
El aviso de "equipo listo" en una orden dentro de garantía ya no va a todos
los dispatchers. Cada persona marca la marca que atiende. Por defecto quedan
apagadas: después de migrar hay que entrar al empleado y activarlas.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0022_poblar_prefijo_facturacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='empleado',
            name='atiende_garantias_dell',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Si está activo, este dispatcher recibe el aviso de equipo listo '
                    'cuando la orden en garantía es marca Dell. Solo aplica al rol Dispatcher.'
                ),
                verbose_name='Atiende garantías Dell',
            ),
        ),
        migrations.AddField(
            model_name='empleado',
            name='atiende_garantias_lenovo',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Si está activo, este dispatcher recibe el aviso de equipo listo '
                    'cuando la orden en garantía es marca Lenovo. Solo aplica al rol Dispatcher.'
                ),
                verbose_name='Atiende garantías Lenovo',
            ),
        ),
    ]
