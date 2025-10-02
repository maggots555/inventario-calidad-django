# Generated manually for atribuibilidad feature

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0011_empleado_jefe_directo'),
        ('scorecard', '0004_incidencia_area_tecnico'),
    ]

    operations = [
        # Agregar campos de atribuibilidad a Incidencia
        migrations.AddField(
            model_name='incidencia',
            name='es_atribuible',
            field=models.BooleanField(default=True, help_text='¿Esta incidencia es atribuible al técnico responsable?'),
        ),
        migrations.AddField(
            model_name='incidencia',
            name='justificacion_no_atribuible',
            field=models.TextField(blank=True, help_text='Justificación de por qué no es atribuible al técnico'),
        ),
        migrations.AddField(
            model_name='incidencia',
            name='fecha_marcado_no_atribuible',
            field=models.DateTimeField(blank=True, help_text='Fecha en que se marcó como no atribuible', null=True),
        ),
        migrations.AddField(
            model_name='incidencia',
            name='marcado_no_atribuible_por',
            field=models.ForeignKey(blank=True, help_text='Usuario que marcó la incidencia como no atribuible', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='incidencias_marcadas_no_atribuibles', to='inventario.empleado'),
        ),
        
        # Actualizar modelo NotificacionIncidencia
        migrations.AddField(
            model_name='notificacionincidencia',
            name='tipo_notificacion',
            field=models.CharField(choices=[('manual', 'Notificación Manual'), ('no_atribuible', 'Marcada como No Atribuible'), ('cierre', 'Cierre de Incidencia'), ('cierre_no_atribuible', 'Cierre de Incidencia No Atribuible')], default='manual', help_text='Tipo de notificación enviada', max_length=30),
        ),
        migrations.AddField(
            model_name='notificacionincidencia',
            name='destinatarios_json',
            field=models.TextField(default='[]', help_text='Lista de destinatarios (JSON con nombres y emails)'),
        ),
        migrations.AddField(
            model_name='notificacionincidencia',
            name='enviado_exitoso',
            field=models.BooleanField(default=True, help_text='Si el envío fue exitoso'),
        ),
        migrations.AlterField(
            model_name='notificacionincidencia',
            name='destinatarios',
            field=models.TextField(blank=True, default='', help_text='Lista de destinatarios (JSON con nombres y emails) - legacy'),
        ),
    ]
