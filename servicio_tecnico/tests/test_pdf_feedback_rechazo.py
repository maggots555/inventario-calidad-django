"""
Tests del PDF ejecutivo de feedback de rechazo.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
1) El generador ReportLab debe devolver bytes que empiezan con %PDF
   (con y sin análisis IA mock).
2) La vista GET debe responder content_type application/pdf
   (mockeamos queryset y el generador para aislar la vista).
"""

from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, SimpleTestCase, TestCase

from servicio_tecnico.pdf_feedback_rechazo import generar_pdf_reporte_rechazo
from servicio_tecnico.views_feedback_rechazo_dash import exportar_feedback_rechazo_pdf


def _datos_pdf_minimos(con_ia: bool = False) -> dict:
    """
    Payload mínimo válido para el generador PDF.

    Args:
        con_ia: si True, incluye un objeto tipo AnalisisSentimientoEncuesta
    """
    analisis = None
    if con_ia:
        # SimpleNamespace basta: _seccion_analisis_ia solo lee atributos
        analisis = SimpleNamespace(
            sentimiento_general='negativo',
            resumen_ejecutivo='Los clientes rechazan por costo elevado.',
            temas_positivos=['Atención amable'],
            temas_negativos=['Precio alto', 'Tiempo de entrega'],
            recomendacion_ia='Revisar márgenes en cotizaciones premium.',
            total_encuestas=3,
            modelo_usado='test-mock',
            fecha_analisis=datetime(2026, 7, 31, 12, 0),
        )

    return {
        'kpis': {
            'total_enviados': 10,
            'total_respondidos': 4,
            'total_pendientes': 3,
            'total_expirados': 3,
            'tasa_respuesta': 40.0,
            'motivo_mas_frecuente': 'Costo muy elevado',
            'motivo_mas_frecuente_porcentaje': 50.0,
        },
        'motivos': [
            {
                'motivo': 'costo',
                'label': 'Costo muy elevado',
                'total': 5,
                'respondidos': 2,
            },
            {
                'motivo': 'tiempo',
                'label': 'Tiempo de reparación',
                'total': 3,
                'respondidos': 1,
            },
        ],
        'tendencia': {
            'labels': ['01/07/2026', '08/07/2026'],
            'datasets': {
                'total_enviados': [4, 6],
                'total_respondidos': [1, 3],
                'tasa_respuesta': [25.0, 50.0],
            },
        },
        'responsables': [
            {
                'id': 1,
                'nombre': 'Ana Pérez',
                'total_enviados': 6,
                'total_respondidos': 3,
                'tasa_respuesta': 50.0,
            },
        ],
        'comentarios': [
            {
                'orden_numero': 'FL-100',
                'orden_id': 1,
                'responsable': 'Ana Pérez',
                'motivo_rechazo': 'Costo muy elevado',
                'comentario': 'Muy caro para el presupuesto.',
                'fecha': '15/07/2026',
            },
        ],
        'periodo': 'Todos los registros',
        'filtros_activos': False,
        'analisis_ia': analisis,
    }


def _queryset_vacio_mock() -> MagicMock:
    """
    QuerySet encadenable vacío para la vista PDF.

    EXPLICACIÓN PARA PRINCIPIANTES:
    filter/annotate/values/order_by se encadenan devolviendo el mismo mock;
    count()→0, first()→None, iterar/listar → vacío, slice → [].
    """
    qs = MagicMock(name='FeedbackRechazoQS')
    qs.filter.return_value = qs
    qs.exclude.return_value = qs
    qs.annotate.return_value = qs
    qs.values.return_value = qs
    qs.order_by.return_value = qs
    qs.select_related.return_value = qs
    qs.count.return_value = 0
    qs.first.return_value = None
    qs.__iter__ = lambda self: iter([])
    qs.__getitem__ = lambda self, item: []
    return qs


class GenerarPdfReporteRechazoTest(SimpleTestCase):
    """El generador produce un PDF válido (%PDF)."""

    def test_genera_pdf_sin_ia(self):
        buf = generar_pdf_reporte_rechazo(_datos_pdf_minimos(con_ia=False))
        self.assertIsInstance(buf, BytesIO)
        contenido = buf.getvalue()
        self.assertTrue(contenido.startswith(b'%PDF'), msg='Debe ser un PDF')
        self.assertGreater(len(contenido), 500)

    def test_genera_pdf_con_analisis_ia_mock(self):
        buf = generar_pdf_reporte_rechazo(_datos_pdf_minimos(con_ia=True))
        contenido = buf.getvalue()
        self.assertTrue(contenido.startswith(b'%PDF'))
        self.assertGreater(len(contenido), 500)


class ExportarFeedbackRechazoPdfVistaTest(TestCase):
    """
    Vista exportar_feedback_rechazo_pdf con RequestFactory.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Mockeamos _filtrar_feedback_rechazo (queryset vacío) y el generador PDF
    para aislar permisos + content_type sin armar órdenes reales.
    Sin IA cacheada también debe devolver 200 PDF.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='pdf_rechazo_tester',
            password='testpass123',
        )
        perm = Permission.objects.get(
            codename='view_dashboard_gerencial',
            content_type__app_label='servicio_tecnico',
        )
        self.user.user_permissions.add(perm)
        self.factory = RequestFactory()

    def _request_get(self):
        request = self.factory.get(
            '/servicio-tecnico/feedback-rechazo/dashboard/exportar-pdf/',
        )
        request.user = self.user
        # messages middleware no está en RequestFactory
        setattr(request, 'session', {})
        setattr(request, '_messages', FallbackStorage(request))
        return request

    @patch('servicio_tecnico.pdf_feedback_rechazo.generar_pdf_reporte_rechazo')
    @patch('servicio_tecnico.views_feedback_rechazo_dash._filtrar_feedback_rechazo')
    def test_vista_devuelve_pdf_sin_ia_cacheada(self, mock_filtrar, mock_generar):
        mock_filtrar.return_value = _queryset_vacio_mock()
        mock_generar.return_value = BytesIO(b'%PDF-1.4 fake-rechazo')

        resp = exportar_feedback_rechazo_pdf(self._request_get())

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn(
            'Reporte_Feedback_Rechazo_',
            resp['Content-Disposition'],
        )
        self.assertTrue(resp.content.startswith(b'%PDF'))
        mock_generar.assert_called_once()
        # Sin feedbacks respondidos → analisis_ia debe ir None
        datos = mock_generar.call_args[0][0]
        self.assertIsNone(datos.get('analisis_ia'))
