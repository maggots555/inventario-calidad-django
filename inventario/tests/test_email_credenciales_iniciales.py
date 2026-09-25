"""
Tests del correo de credenciales iniciales.

EXPLICACIÓN PARA PRINCIPIANTES:
No se manda un correo de verdad. Primero se rellena la plantilla HTML
para comprobar que ya es un aviso de tablas (y que el alta y el reenvío
no se mezclan). Después se simula el envío para ver que el texto plano,
el botón y el logo siguen pegados al mismo mensaje.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from inventario.utils import (
    construir_texto_plano_credenciales,
    enviar_credenciales_empleado,
)


PLANTILLA = 'emails/credenciales_iniciales.html'
URL_LOGIN = 'https://mexico.sigmasystem.work/login/'
URL_SISTEMA = 'https://mexico.sigmasystem.work'


def _empleado(**overrides) -> SimpleNamespace:
    """
    Empleado falso con los campos que el HTML y el texto plano leen.

    Args:
        **overrides: Campos a cambiar (sucursal, nombre, correo).

    Returns:
        SimpleNamespace: Empleado listo para la plantilla.

    Efectos secundarios:
        Ninguno.
    """
    empleado = SimpleNamespace(
        nombre_completo='Ana López',
        email='ana@sic.mx',
        cargo='Técnico',
        area='Taller',
        sucursal=None,
        fecha_envio_credenciales=None,
        save=lambda: None,
    )
    for clave, valor in overrides.items():
        setattr(empleado, clave, valor)
    return empleado


def _contexto(**overrides) -> dict:
    """
    Contexto mínimo igual al de enviar_credenciales_empleado.

    Args:
        **overrides: Claves a cambiar (es_reenvio, sucursal).

    Returns:
        dict: Contexto para render_to_string.

    Efectos secundarios:
        Ninguno.
    """
    contexto = {
        'empleado': _empleado(),
        'contraseña_temporal': 'AbC123XyZ',
        'usuario': 'ana@sic.mx',
        'es_reenvio': False,
        'nombre_sistema': 'Sistema Integral de Gestión SIGMA',
        'url_login': URL_LOGIN,
        'url_sistema': URL_SISTEMA,
    }
    contexto.update(overrides)
    return contexto


class CredencialesInicialesEmailTemplateTests(SimpleTestCase):
    """El HTML debe ser correo de tablas y conservar las frases del alta."""

    def test_bienvenida_es_correo_de_tablas(self):
        """Alta: saludo, contraseña, botón y pie, sin CSS de página web."""
        from django.template.loader import render_to_string

        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('role="presentation"', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('#1f6391', html)
        self.assertIn('Sistema Integral de Gestión SIGMA', html)
        self.assertIn('¡Bienvenido al Sistema!', html)
        self.assertIn('Hola <strong>Ana López</strong>', html)
        self.assertIn('se te ha otorgado acceso', html)
        self.assertIn('credenciales personales', html)
        self.assertIn('TUS CREDENCIALES DE ACCESO', html)
        self.assertIn('Usuario:', html)
        self.assertIn('ana@sic.mx', html)
        self.assertIn('Contraseña Temporal:', html)
        self.assertIn('AbC123XyZ', html)
        self.assertIn('CAMBIO DE CONTRASEÑA OBLIGATORIO', html)
        self.assertIn('TEMPORAL y de un solo uso', html)
        self.assertIn('¿Qué pasará en tu primer inicio de sesión?', html)
        self.assertIn('Acceder al Sistema Ahora', html)
        self.assertIn(URL_LOGIN, html)
        self.assertIn('Dirección del sistema:', html)
        self.assertIn(URL_SISTEMA, html)
        self.assertIn('Información de tu cuenta:', html)
        self.assertIn('Técnico', html)
        self.assertIn('Taller', html)
        self.assertIn('¿Problemas para acceder?', html)
        self.assertIn('Recomendaciones de seguridad:', html)
        self.assertIn('Este es un email automático, por favor no responder.', html)
        self.assertIn('Todos los derechos reservados', html)
        self.assertNotIn('Como solicitaste', html)
        self.assertNotIn('Reenvío de Credenciales de Acceso', html)
        self.assertNotIn('Sucursal:', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('display:grid', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('box-shadow', html)
        self.assertNotIn(':hover', html)
        self.assertNotIn('instagram.com', html)
        self.assertNotIn('cid:icon_', html)

    def test_reenvio_cambia_el_saludo(self):
        """Reenvío: otro título y no repite el párrafo de bienvenida."""
        from django.template.loader import render_to_string

        html = render_to_string(PLANTILLA, _contexto(es_reenvio=True))

        self.assertIn('Reenvío de Credenciales de Acceso', html)
        self.assertIn('Como solicitaste, te reenviamos tus credenciales', html)
        self.assertIn('AbC123XyZ', html)
        self.assertIn(URL_LOGIN, html)
        self.assertNotIn('¡Bienvenido al Sistema!', html)
        self.assertNotIn('se te ha otorgado acceso', html)
        self.assertNotIn('credenciales personales', html)

    def test_con_sucursal_muestra_el_nombre(self):
        """Si el empleado tiene sucursal, la fila sale; si no, el otro test ya lo cubre."""
        from django.template.loader import render_to_string

        html = render_to_string(
            PLANTILLA,
            _contexto(empleado=_empleado(sucursal=SimpleNamespace(nombre='Centro'))),
        )

        self.assertIn('Sucursal:', html)
        self.assertIn('Centro', html)


class CredencialesInicialesTextoPlanoTests(SimpleTestCase):
    """El text/plain lleva las mismas frases y la misma URL que el HTML."""

    def test_bienvenida_incluye_clave_y_enlace(self):
        """Alta: contraseña, login y sin la frase de reenvío."""
        texto = construir_texto_plano_credenciales(_contexto())

        self.assertIn('¡Bienvenido al Sistema!', texto)
        self.assertIn('Hola Ana López,', texto)
        self.assertIn('Usuario: ana@sic.mx', texto)
        self.assertIn('Contraseña Temporal: AbC123XyZ', texto)
        self.assertIn(URL_LOGIN, texto)
        self.assertIn(URL_SISTEMA, texto)
        self.assertIn('Acceder al Sistema Ahora:', texto)
        self.assertIn('Este es un email automático, por favor no responder.', texto)
        self.assertNotIn('Como solicitaste', texto)
        self.assertNotIn('Sucursal:', texto)

    def test_reenvio_y_sucursal(self):
        """Reenvío con sucursal: cambia el saludo y agrega la sucursal."""
        texto = construir_texto_plano_credenciales(
            _contexto(
                es_reenvio=True,
                empleado=_empleado(sucursal=SimpleNamespace(nombre='Centro')),
            )
        )

        self.assertIn('Reenvío de Credenciales de Acceso', texto)
        self.assertIn('Como solicitaste', texto)
        self.assertIn('Sucursal: Centro', texto)
        self.assertIn(URL_LOGIN, texto)
        self.assertNotIn('¡Bienvenido al Sistema!', texto)


class EnviarCredencialesEmpleadoTests(SimpleTestCase):
    """El envío sigue al mismo destinatario y ahora pega logo + HTML."""

    @override_settings(
        EMAIL_HOST_USER='sigma@test.local',
        EMAIL_HOST_PASSWORD='secreto',
        EMAIL_HOST='smtp.test',
        EMAIL_PORT=587,
        DEFAULT_FROM_EMAIL='sigma@test.local',
    )
    @patch('inventario.utils.EmailMultiAlternatives')
    @patch('config.paises_config.get_pais_actual')
    def test_arma_html_texto_plano_y_logo(self, mock_pais, mock_mail):
        """No abre SMTP: revisa asunto, cuerpo, HTML y que se intente el logo."""
        mock_pais.return_value = {
            'url_base': URL_SISTEMA,
            'db_alias': 'default',
        }
        mensaje = MagicMock()
        mock_mail.return_value = mensaje
        empleado = _empleado()
        guardados = []
        empleado.save = lambda: guardados.append(True)

        exito, error = enviar_credenciales_empleado(
            empleado,
            'AbC123XyZ',
            es_reenvio=False,
        )

        self.assertTrue(exito)
        self.assertIsNone(error)
        self.assertEqual(guardados, [True])
        mock_mail.assert_called_once()
        kwargs = mock_mail.call_args.kwargs
        self.assertEqual(kwargs['subject'], '¡Bienvenido al Sistema Integral de Gestión!')
        self.assertEqual(kwargs['to'], ['ana@sic.mx'])
        self.assertIn('AbC123XyZ', kwargs['body'])
        self.assertIn(URL_LOGIN, kwargs['body'])
        mensaje.attach_alternative.assert_called_once()
        html, mime = mensaje.attach_alternative.call_args.args
        self.assertEqual(mime, 'text/html')
        self.assertIn('role="presentation"', html)
        self.assertIn('AbC123XyZ', html)
        self.assertIn(URL_LOGIN, html)
        # El helper real pega el PNG si está en static/.
        mensaje.attach.assert_called()
        mensaje.send.assert_called_once_with(fail_silently=False)
