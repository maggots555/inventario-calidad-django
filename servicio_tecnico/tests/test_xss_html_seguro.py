"""
El HTML del admin y el JSON del detalle no ejecutan texto guardado.

EXPLICACIÓN PARA PRINCIPIANTES:
format_html solo escapa lo que va en {}. Si le pasas una cadena ya
armada, el navegador la trata como página. json.dumps deja pasar
</script>, que cierra la etiqueta antes de tiempo. Estas pruebas
clavan esos dos casos.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.contrib import admin
from django.test import SimpleTestCase

from servicio_tecnico.admin import AnalisisSentimientoEncuestaAdmin, OrdenServicioAdmin
from servicio_tecnico.models import AnalisisSentimientoEncuesta, OrdenServicio
from servicio_tecnico.services.detalle_orden_context import json_seguro_para_script


class XssHtmlSeguroTest(SimpleTestCase):
    """Sin base de datos: solo el HTML que arman los métodos."""

    def test_estado_rhitso_no_deja_pasar_script(self):
        """Un estado con <script> se ve como texto, no como código."""
        pantalla = OrdenServicioAdmin(OrdenServicio, admin.site)
        orden = SimpleNamespace(
            es_candidato_rhitso=True,
            estado_rhitso='<script>alert(1)</script>',
            fecha_envio_rhitso=None,
            fecha_recepcion_rhitso=None,
        )
        html = str(pantalla.estado_rhitso_display(orden))
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_tema_de_encuesta_no_deja_pasar_script(self):
        """Un tema de la IA con HTML no se pinta como etiqueta."""
        pantalla = AnalisisSentimientoEncuestaAdmin(
            AnalisisSentimientoEncuesta,
            admin.site,
        )
        analisis = SimpleNamespace(temas_positivos=['<img src=x onerror=alert(1)>'])
        html = str(pantalla.temas_positivos_display(analisis))
        self.assertNotIn('<img', html)
        self.assertIn('&lt;img', html)

    def test_json_del_script_no_cierra_la_etiqueta(self):
        """</script> dentro del JSON queda en escapes unicode."""
        texto = str(json_seguro_para_script({
            'nombre': '</script><script>alert(1)',
            'nota': 'a & b > c',
            'cuando': date(2026, 10, 9),
            'monto': Decimal('570.00'),
        }))
        self.assertNotIn('</script>', texto)
        self.assertNotIn('<', texto)
        self.assertNotIn('>', texto)
        self.assertNotIn('&', texto)
        self.assertIn('2026-10-09', texto)
        self.assertIn('570.00', texto)
