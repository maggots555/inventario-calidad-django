# Generated manually — campo horario_atencion en Sucursal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0017_alter_empleado_foto_perfil'),
    ]

    operations = [
        migrations.AddField(
            model_name='sucursal',
            name='horario_atencion',
            field=models.TextField(
                blank=True,
                help_text='Horario público para clientes. Ej: Lunes a viernes 9:00 - 18:00, Sábados 9:00 - 14:00',
                verbose_name='Horario de atención',
            ),
        ),
    ]
