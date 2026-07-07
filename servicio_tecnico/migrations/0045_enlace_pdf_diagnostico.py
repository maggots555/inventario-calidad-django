from django.db import migrations, models
import servicio_tecnico.models


class Migration(migrations.Migration):
    """
    Agrega almacenamiento persistente del PDF de diagnóstico en el enlace
    público del cliente y un nuevo tipo de evento para métricas de apertura.
    """

    dependencies = [
        ('servicio_tecnico', '0044_recordatorio_imagen_orden'),
    ]

    operations = [
        migrations.AddField(
            model_name='enlaceseguimientocliente',
            name='folio_diagnostico',
            field=models.CharField(
                blank=True,
                help_text='Folio usado al generar el PDF que se compartió con el cliente.',
                max_length=120,
                verbose_name='Folio del diagnóstico enviado',
            ),
        ),
        migrations.AddField(
            model_name='enlaceseguimientocliente',
            name='pdf_diagnostico',
            field=models.FileField(
                blank=True,
                help_text='Copia persistente del PDF enviado al cliente por correo.',
                max_length=255,
                null=True,
                upload_to=servicio_tecnico.models.diagnostico_pdf_upload_path,
                verbose_name='PDF de diagnóstico',
            ),
        ),
        migrations.AlterField(
            model_name='eventoseguimientocliente',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('visita_pagina', 'Visita a la página'),
                    ('pwa_banner_mostrado', 'Banner PWA mostrado'),
                    ('pwa_banner_cerrado', 'Banner PWA cerrado'),
                    ('pwa_prompt_aceptado', 'Prompt PWA aceptado'),
                    ('pwa_prompt_rechazado', 'Prompt PWA rechazado'),
                    ('pwa_instalada', 'PWA instalada'),
                    ('pwa_modo_standalone', 'Página abierta como app instalada'),
                    ('push_activado', 'Push activado'),
                    ('push_desactivado', 'Push desactivado'),
                    ('push_permiso_denegado', 'Permiso push denegado'),
                    ('chat_abierto', 'Chat abierto'),
                    ('chat_mensaje_enviado', 'Mensaje de chat enviado'),
                    ('diagnostico_pdf_abierto', 'PDF de diagnóstico abierto'),
                ],
                db_index=True,
                max_length=40,
                verbose_name='Tipo de evento',
            ),
        ),
    ]
