"""
Tests de humo tras extraer concentrado, IA diagnóstico y perfil (Fase 2).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No abrimos Excel/PDF reales ni llamamos a Ollama/Gemini. Solo confirmamos que:
1) urls.py sigue resolviendo a los callables nuevos.
2) views.py reexporta los mismos nombres.
3) chat_seguimiento_cliente SIGUE en views.py (Fase 3 — no lo movimos).
4) Smoke mínimo de concentrado: sin permiso redirige a acceso denegado.
"""

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import resolve, reverse

from servicio_tecnico import views as st_views
from servicio_tecnico import views_concentrado
from servicio_tecnico import views_ia_diagnostico
from servicio_tecnico import views_perfil


User = get_user_model()


class CompatibilidadFase2ReexportsTest(SimpleTestCase):
    """
    Verifica reexports y resolve de URLs sin tocar BD.

    Objetivo: si alguien borra un import por error, urls.py dejaría de ver
    views.concentrado_semanal / views.mi_perfil / views.pulir_diagnostico_sic_ia.
    """

    def test_views_reexporta_concentrado_ia_perfil(self):
        """Los símbolos públicos de Fase 2 siguen en el módulo views."""
        self.assertIs(
            st_views.concentrado_semanal,
            views_concentrado.concentrado_semanal,
        )
        self.assertIs(
            st_views.exportar_concentrado_excel,
            views_concentrado.exportar_concentrado_excel,
        )
        self.assertIs(
            st_views.exportar_concentrado_pdf,
            views_concentrado.exportar_concentrado_pdf,
        )
        self.assertIs(
            st_views.pulir_diagnostico_sic_ia,
            views_ia_diagnostico.pulir_diagnostico_sic_ia,
        )
        self.assertIs(
            st_views.transcribir_audio_diagnostico,
            views_ia_diagnostico.transcribir_audio_diagnostico,
        )
        self.assertIs(st_views.mi_perfil, views_perfil.mi_perfil)
        self.assertIs(
            st_views.exportar_excel_mi_perfil,
            views_perfil.exportar_excel_mi_perfil,
        )
        self.assertIs(
            st_views.directorio_empleados,
            views_perfil.directorio_empleados,
        )
        self.assertIs(st_views.perfil_empleado, views_perfil.perfil_empleado)

    def test_chat_seguimiento_no_esta_en_ia_diagnostico(self):
        """
        chat_seguimiento_cliente NO pertenece a views_ia_diagnostico.

        EXPLICACIÓN PARA PRINCIPIANTES:
        En Fase 2 el chat seguía en el monolito (entre pulir y transcribir).
        En Fase 3 se movió a views_seguimiento_cliente.py. En ambos casos
        NO debe mezclarse con las vistas de pulir/transcribir diagnóstico.
        """
        self.assertTrue(callable(st_views.chat_seguimiento_cliente))
        self.assertFalse(
            hasattr(views_ia_diagnostico, 'chat_seguimiento_cliente'),
            msg='chat_seguimiento_cliente no debe estar en views_ia_diagnostico',
        )

    def test_urls_fase2_resuelven_modulos_nuevos(self):
        """reverse/resolve apuntan a concentrado / ia / perfil."""
        casos = [
            (
                'servicio_tecnico:concentrado_semanal',
                None,
                views_concentrado.concentrado_semanal,
            ),
            (
                'servicio_tecnico:exportar_concentrado_excel',
                None,
                views_concentrado.exportar_concentrado_excel,
            ),
            (
                'servicio_tecnico:exportar_concentrado_pdf',
                None,
                views_concentrado.exportar_concentrado_pdf,
            ),
            (
                'servicio_tecnico:pulir_diagnostico_sic_ia',
                None,
                views_ia_diagnostico.pulir_diagnostico_sic_ia,
            ),
            (
                'servicio_tecnico:transcribir_audio_diagnostico',
                None,
                views_ia_diagnostico.transcribir_audio_diagnostico,
            ),
            ('servicio_tecnico:mi_perfil', None, views_perfil.mi_perfil),
            (
                'servicio_tecnico:exportar_excel_mi_perfil',
                None,
                views_perfil.exportar_excel_mi_perfil,
            ),
            (
                'servicio_tecnico:directorio_empleados',
                None,
                views_perfil.directorio_empleados,
            ),
            (
                'servicio_tecnico:perfil_empleado',
                {'empleado_id': 1},
                views_perfil.perfil_empleado,
            ),
        ]
        for name, kwargs, expected in casos:
            url = reverse(name, kwargs=kwargs) if kwargs else reverse(name)
            match = resolve(url)
            self.assertIs(match.func, expected, msg=f'Fallo en {name}')


class ConcentradoPermisoSmokeTest(TestCase):
    """
    Smoke: usuario sin permiso de dashboard gerencial no entra al concentrado.

    Efectos secundarios: crea User en la BD de pruebas.
    """

    def setUp(self):
        """Crea usuario autenticado SIN el permiso view_dashboard_gerencial."""
        self.user = User.objects.create_user(
            username='test_concentrado',
            password='testpass123',
        )
        self.factory = RequestFactory()

    def test_sin_permiso_redirige_a_acceso_denegado(self):
        """
        El decorador permission_required_with_message debe redirigir.

        EXPLICACIÓN PARA PRINCIPIANTES:
        No necesitamos generar el reporte real: solo comprobar que la vista
        modularizada sigue protegida igual que cuando vivía en el monolito.
        """
        request = self.factory.get('/servicio-tecnico/concentrado-semanal/')
        request.user = self.user

        response = views_concentrado.concentrado_semanal(request)

        # Redirect a acceso denegado (302) — no ejecuta la lógica del concentrado
        self.assertEqual(response.status_code, 302)
        self.assertIn('acceso-denegado', response.url)

    def test_modulo_importa_sucursal(self):
        """
        Regresión: Sucursal debe estar importado en views_concentrado.

        EXPLICACIÓN PARA PRINCIPIANTES:
        En el monolito Sucursal venía del import global de views.py.
        Al mover la vista, hay que importarlo en el módulo nuevo o falla
        con NameError al abrir /concentrado-semanal/.
        """
        self.assertTrue(
            hasattr(views_concentrado, 'Sucursal'),
            msg='Falta: from inventario.models import Sucursal en views_concentrado',
        )
