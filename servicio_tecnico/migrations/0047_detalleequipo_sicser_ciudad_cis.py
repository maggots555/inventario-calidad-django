# Generated manually — ciudad/estado/CIS SICSER en DetalleEquipo (histórico Importadas)

from django.db import migrations, models


def rellenar_cis_oow_desde_folio(apps, schema_editor):
    """
    Rellena sicser_cis en órdenes OOW ya importadas parseando el folio SICSER.
    Ej: MX_CIS_MX_DROPOFF_11954 → DROP
    """
    DetalleEquipo = apps.get_model('servicio_tecnico', 'DetalleEquipo')

    # Mapeo local (no importamos sicser_client en migraciones para evitar dependencias).
    segmento_a_cis = {
        'DROPOFF': 'DROP',
        'DROP': 'DROP',
        'SIC': 'SAT',
        'SATELITE': 'SAT',
        'SAT': 'SAT',
        'MONTERREY': 'MTR',
        'MTR': 'MTR',
        'GUADALAJARA': 'GDL',
        'GDL': 'GDL',
        'BUENOS': 'BUA',
        'BUA': 'BUA',
        'BOGOTA': 'BOG',
        'BOG': 'BOG',
        'MEDELLIN': 'MED',
        'MED': 'MED',
        'SANTIAGO': 'SAN',
        'SAN': 'SAN',
    }

    for detalle in DetalleEquipo.objects.filter(
        sicser_origen='oow',
        folio_sicser__gt='',
        sicser_cis='',
    ).iterator():
        folio = (detalle.folio_sicser or '').upper()
        codigo = ''
        for parte in folio.split('_'):
            if parte in segmento_a_cis:
                codigo = segmento_a_cis[parte]
                break
        if codigo:
            detalle.sicser_cis = codigo
            detalle.save(update_fields=['sicser_cis'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('servicio_tecnico', '0046_detalleequipo_sicser_importacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='detalleequipo',
            name='sicser_ciudad',
            field=models.CharField(
                blank=True,
                help_text='Ciudad reportada por SICSER al importar (útil en garantías Dell)',
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name='detalleequipo',
            name='sicser_estado',
            field=models.CharField(
                blank=True,
                help_text='Estado/provincia reportado por SICSER al importar',
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name='detalleequipo',
            name='sicser_cis',
            field=models.CharField(
                blank=True,
                help_text='Código CIS (DROP, SAT, GDL, MTR…) del folio OOW o inferido por ciudad en garantías',
                max_length=10,
            ),
        ),
        migrations.RunPython(rellenar_cis_oow_desde_folio, noop_reverse),
    ]
