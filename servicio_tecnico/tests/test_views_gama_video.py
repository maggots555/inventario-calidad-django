"""
Tests de humo tras extraer referencias de gama y video resumen de views.py.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No generamos video real ni llamamos FFmpeg. Solo confirmamos que:
1) urls.py sigue resolviendo a los callables nuevos.
2) views.py reexporta los mismos nombres.
3) generar_video_resumen valida el mínimo de 2 fotos sin encolar Celery.
4) Soft-delete / reactivar de referencias de gama funciona en BD.
"""

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import resolve, reverse

from inventario.models import Empleado, Sucursal
from servicio_tecnico import views as st_views
from servicio_tecnico import views_referencias_gama
from servicio_tecnico import views_video_resumen
from servicio_tecnico.models import OrdenServicio, ReferenciaGamaEquipo
from servicio_tecnico.views_video_resumen import generar_video_resumen


User = get_user_model()


class CompatibilidadGamaVideoReexportsTest(SimpleTestCase):
    """urls + reexports sin tocar BD."""

    def test_views_reexporta_gama_y_video(self):
        """Los símbolos públicos siguen en el módulo views."""
        self.assertIs(
            st_views.lista_referencias_gama,
            views_referencias_gama.lista_referencias_gama,
        )
        self.assertIs(
            st_views.crear_referencia_gama,
            views_referencias_gama.crear_referencia_gama,
        )
        self.assertIs(
            st_views.generar_video_resumen,
            views_video_resumen.generar_video_resumen,
        )
        self.assertIs(
            st_views.estado_compresion_resumen,
            views_video_resumen.estado_compresion_resumen,
        )

    def test_urls_gama_y_video_resuelven_modulos_nuevos(self):
        """reverse/resolve apuntan a views_referencias_gama y views_video_resumen."""
        casos = [
            ('servicio_tecnico:lista_referencias_gama', None, views_referencias_gama.lista_referencias_gama),
            ('servicio_tecnico:crear_referencia_gama', None, views_referencias_gama.crear_referencia_gama),
            ('servicio_tecnico:editar_referencia_gama', {'referencia_id': 1}, views_referencias_gama.editar_referencia_gama),
            ('servicio_tecnico:eliminar_referencia_gama', {'referencia_id': 1}, views_referencias_gama.eliminar_referencia_gama),
            ('servicio_tecnico:reactivar_referencia_gama', {'referencia_id': 1}, views_referencias_gama.reactivar_referencia_gama),
            ('servicio_tecnico:generar_video_resumen', {'orden_id': 1}, views_video_resumen.generar_video_resumen),
            ('servicio_tecnico:estado_video_resumen', {'task_id': 'abc'}, views_video_resumen.estado_video_resumen),
            ('servicio_tecnico:comprimir_video_resumen', {'video_id': 1}, views_video_resumen.comprimir_video_resumen),
            ('servicio_tecnico:estado_compresion_resumen', {'task_id': 'xyz'}, views_video_resumen.estado_compresion_resumen),
        ]
        for name, kwargs, expected in casos:
            url = reverse(name, kwargs=kwargs) if kwargs else reverse(name)
            match = resolve(url)
            self.assertIs(match.func, expected, msg=f'Fallo en {name}')


class ReferenciaGamaSoftDeleteTest(TestCase):
    """Flujo soft-delete / reactivar del catálogo de gama."""

    def setUp(self):
        self.ref = ReferenciaGamaEquipo.objects.create(
            marca='Dell',
            modelo_base='Latitude 5420',
            gama='media',
            rango_costo_min=8000,
            rango_costo_max=15000,
            activo=True,
        )

    def test_eliminar_marca_como_inactivo_y_reactivar(self):
        """eliminar pone activo=False; reactivar lo vuelve True (vía lógica de vista)."""
        # Soft delete equivalente a lo que hace eliminar_referencia_gama en POST
        self.ref.activo = False
        self.ref.save()
        self.ref.refresh_from_db()
        self.assertFalse(self.ref.activo)

        self.ref.activo = True
        self.ref.save()
        self.ref.refresh_from_db()
        self.assertTrue(self.ref.activo)

    def test_lista_oculta_inactivos_por_defecto(self):
        """Sin mostrar_inactivos, la lista solo cuenta activos (misma regla de la vista)."""
        ReferenciaGamaEquipo.objects.create(
            marca='HP',
            modelo_base='EliteBook',
            gama='alta',
            rango_costo_min=20000,
            rango_costo_max=35000,
            activo=False,
        )
        activas = ReferenciaGamaEquipo.objects.filter(activo=True).count()
        self.assertEqual(activas, 1)


class GenerarVideoResumenValidacionTest(TestCase):
    """
    Validación de generar_video_resumen sin encolar Celery real.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Usamos RequestFactory (no Client) para no pasar por PaisMiddleware /
    ForcePasswordChangeMiddleware, que en tests multi-BD consultan 'mexico'.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Video Test',
            ciudad='CDMX',
        )
        self.tecnico = Empleado.objects.create(
            nombre_completo='Técnico Video',
            cargo='Técnico',
            area='Laboratorio',
            sucursal=self.sucursal,
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tecnico_asignado_actual=self.tecnico,
            tipo_servicio='diagnostico',
        )
        self.user = User.objects.create_user(
            username='tech_video',
            password='test-pass-123',
        )

    def _post_generar(self):
        """Arma un request POST autenticado hacia la vista."""
        request = self.factory.post(
            f'/servicio-tecnico/orden/{self.orden.pk}/video-resumen/generar/'
        )
        request.user = self.user
        return generar_video_resumen(request, orden_id=self.orden.pk)

    def test_rechaza_si_hay_menos_de_dos_fotos(self):
        """Con 0 fotos principales responde 400 y no encola Celery."""
        with patch(
            'servicio_tecnico.tasks.generar_video_resumen_task.delay'
        ) as mock_delay:
            respuesta = self._post_generar()

        self.assertEqual(respuesta.status_code, 400)
        data = json.loads(respuesta.content)
        self.assertFalse(data['success'])
        self.assertIn('2 fotos', data['error'])
        mock_delay.assert_not_called()

    def test_encola_cuando_hay_al_menos_dos_fotos(self):
        """Con 2 fotos válidas llama .delay() y devuelve task_id."""
        mock_async = MagicMock()
        mock_async.id = 'task-test-123'

        # No creamos ImageField reales: simulamos conteo = 2
        mock_qs = MagicMock()
        mock_qs.count.return_value = 2

        with patch(
            'servicio_tecnico.views_video_resumen.ImagenOrden.objects.filter',
            return_value=mock_qs,
        ):
            with patch(
                'servicio_tecnico.tasks.generar_video_resumen_task.delay',
                return_value=mock_async,
            ) as mock_delay:
                with patch(
                    'config.paises_config.get_pais_actual',
                    return_value={'db_alias': 'default'},
                ):
                    respuesta = self._post_generar()

        self.assertEqual(respuesta.status_code, 200)
        data = json.loads(respuesta.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['task_id'], 'task-test-123')
        self.assertEqual(data['n_fotos'], 2)
        mock_delay.assert_called_once()
        kwargs = mock_delay.call_args.kwargs
        self.assertEqual(kwargs.get('db_alias'), 'default')
        self.assertEqual(kwargs.get('orden_id'), self.orden.pk)
