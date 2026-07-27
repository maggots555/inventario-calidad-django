"""
Tests del endpoint AJAX guardar_diagnostico_sic_ia.

EXPLICACIÓN PARA PRINCIPIANTES:
Cuando el técnico acepta la mejora de IA, el frontend llama a este endpoint
para persistir SOLO el diagnóstico SIC (sin enviar todo el formulario de
configuración). Aquí comprobamos el caso feliz y validaciones básicas.

Usamos RequestFactory (no Client) para evitar middleware Axes / multi-tenant
y ForcePasswordChange en los tests.
"""

import json

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse

from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import DetalleEquipo, HistorialOrden, OrdenServicio
from servicio_tecnico.views_ia_diagnostico import guardar_diagnostico_sic_ia


User = get_user_model()

TEXTO_ORIGINAL = 'Equipo no enciende, se reviso fuente y placa madre.'
TEXTO_MEJORADO = (
    'El equipo no enciende. Se revisó la fuente de poder y la tarjeta madre '
    'sin detectar daños evidentes en la inspección inicial.'
)


def _request_post(factory: RequestFactory, user, data: dict):
    """
    Arma un POST autenticado con sesión (para messages si hiciera falta).

    Args:
        factory: RequestFactory de Django
        user: Usuario autenticado
        data: Dict con campos POST

    Returns:
        HttpRequest listo para pasar a la vista
    """
    request = factory.post(
        reverse('servicio_tecnico:guardar_diagnostico_sic_ia'),
        data,
    )
    request.user = user
    # Session + messages: algunos middlewares/vistas los asumen presentes
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()
    setattr(request, '_messages', FallbackStorage(request))
    return request


class GuardarDiagnosticoSicIaTest(TestCase):
    """
    Objetivo: al aceptar mejora IA, diagnostico_sic queda en BD.
    """

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Guardar Diag IA',
            ciudad='CDMX',
            direccion='Calle Test 1',
            horario_atencion='Lun-Vie 9-18',
        )
        self.user = User.objects.create_user(
            username='tec_guardar_diag',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico Guardar Diag',
            cargo='Técnico',
            area='Laboratorio',
            email='tec.guardar@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='tecnico',
            contraseña_configurada=True,
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='diagnostico',
            tecnico_asignado_actual=self.empleado,
        )
        self.detalle = DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-GUARDAR-IA-01',
            tipo_equipo='Laptop',
            marca='DELL',
            modelo='Latitude',
            numero_serie='STGUARDIA01',
            diagnostico_sic=TEXTO_ORIGINAL,
        )

    def test_guarda_solo_diagnostico_y_historial(self) -> None:
        """POST válido actualiza diagnostico_sic y crea historial."""
        request = _request_post(
            self.factory,
            self.user,
            {
                'orden_id': str(self.orden.pk),
                'diagnostico_sic': TEXTO_MEJORADO,
            },
        )
        respuesta = guardar_diagnostico_sic_ia(request)

        self.assertEqual(respuesta.status_code, 200)
        # RequestFactory no trae response.json(); parseamos el contenido
        data = json.loads(respuesta.content.decode('utf-8'))
        self.assertTrue(data['success'])
        self.assertEqual(data['diagnostico_sic'], TEXTO_MEJORADO)

        self.detalle.refresh_from_db()
        self.assertEqual(self.detalle.diagnostico_sic, TEXTO_MEJORADO)

        # No debe haber tocado otros campos del detalle
        self.assertEqual(self.detalle.falla_principal, '')

        historial = HistorialOrden.objects.filter(
            orden=self.orden,
            tipo_evento='actualizacion',
        )
        self.assertTrue(historial.exists())
        self.assertIn(
            'mejora de redacción con IA',
            historial.latest('id').comentario,
        )

    def test_rechaza_texto_corto(self) -> None:
        """Menos de 20 caracteres → 400 y no cambia BD."""
        request = _request_post(
            self.factory,
            self.user,
            {
                'orden_id': str(self.orden.pk),
                'diagnostico_sic': 'muy corto',
            },
        )
        respuesta = guardar_diagnostico_sic_ia(request)

        self.assertEqual(respuesta.status_code, 400)
        self.detalle.refresh_from_db()
        self.assertEqual(self.detalle.diagnostico_sic, TEXTO_ORIGINAL)

    def test_rechaza_orden_invalida(self) -> None:
        """orden_id no numérico → 400."""
        request = _request_post(
            self.factory,
            self.user,
            {
                'orden_id': 'abc',
                'diagnostico_sic': TEXTO_MEJORADO,
            },
        )
        respuesta = guardar_diagnostico_sic_ia(request)
        self.assertEqual(respuesta.status_code, 400)
