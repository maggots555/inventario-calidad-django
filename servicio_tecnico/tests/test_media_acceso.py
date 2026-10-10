"""
/media/ no se entrega a cualquiera. Banners sí. El resto pide sesión o token.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from config.media_acceso import (
    anexar_token_seguimiento,
    clasificar_acceso_media,
    ruta_relativa_segura,
)
from config.media_views import serve_media_from_multiple_locations
from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import DetalleEquipo, EnlaceSeguimientoCliente, OrdenServicio
from servicio_tecnico.services.nombre_archivo_privado import nombre_archivo_privado


class _UsuarioLogueado:
    """Sustituto mínimo: la vista solo pregunta is_authenticated."""

    is_authenticated = True


class RutaYAccesoMediaTests(TestCase):
    """Reglas de la URL, sin leer el disco."""

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(nombre='Sucursal Media', ciudad='CDMX')
        self.user = User.objects.create_user(username='tec_media', password='testpass123')
        self.tecnico = Empleado.objects.create(
            nombre_completo='Técnico Media',
            cargo='Técnico',
            area='Laboratorio',
            email='tec.media@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='tecnico',
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='diagnostico',
            tecnico_asignado_actual=self.tecnico,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-MEDIA-01',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
            numero_serie='SN-MEDIA-01',
            email_cliente='cliente.media@test.local',
            nombre_cliente='Cliente Media',
            falla_principal='No enciende',
        )
        self.enlace = EnlaceSeguimientoCliente.objects.create(
            orden=self.orden,
            token='token-media-vigente',
            activo=True,
        )

    def _get(self, path, usuario, token=''):
        """GET /media/... con el usuario y el ?t= que indique la prueba."""
        query = {'t': token} if token else None
        request = self.factory.get(f'/media/{path}', data=query or {})
        request.user = usuario
        return request

    def test_puntos_puntos_no_es_ruta_segura(self):
        """../../etc/passwd no se limpia: se rechaza. Un slash inicial se queda dentro de media."""
        self.assertIsNone(ruta_relativa_segura('../../etc/passwd'))
        # /etc/passwd sin los puntos se vuelve media/etc/passwd, no el /etc del sistema.
        self.assertEqual(ruta_relativa_segura('/etc/passwd'), 'etc/passwd')

    def test_anonimo_no_ve_evidencia_y_si_ve_banner(self):
        """Sin sesión, la foto de la orden se niega. El banner de publicidad no."""
        evidencia = 'mexico/servicio_tecnico/imagenes/OOW-MEDIA-01/ingreso_1.jpg'
        banner = 'mexico/banners/2026/10/promo.jpg'
        anon = AnonymousUser()
        self.assertEqual(
            clasificar_acceso_media(self._get(evidencia, anon), evidencia),
            'denegado',
        )
        self.assertEqual(
            clasificar_acceso_media(self._get(banner, anon), banner),
            'publico',
        )

    def test_sesion_de_staff_ve_la_evidencia(self):
        """El personal logueado abre la foto sin token."""
        evidencia = 'mexico/servicio_tecnico/imagenes/OOW-MEDIA-01/ingreso_1.jpg'
        request = self._get(evidencia, _UsuarioLogueado())
        self.assertEqual(clasificar_acceso_media(request, evidencia), 'privado')

    def test_token_solo_abre_la_carpeta_de_su_orden(self):
        """El ?t= del cliente sirve para su folio, no para el de otra orden."""
        propia = 'mexico/servicio_tecnico/imagenes/OOW-MEDIA-01/ingreso_1.jpg'
        ajena = 'mexico/servicio_tecnico/imagenes/OTRA-ORDEN/ingreso_1.jpg'
        request = self._get(propia, AnonymousUser(), token='token-media-vigente')
        self.assertEqual(clasificar_acceso_media(request, propia), 'privado')
        self.assertEqual(clasificar_acceso_media(request, ajena), 'denegado')

    def test_token_no_abre_otro_pais_ni_un_folio_suelto_en_el_nombre(self):
        """ORD-2026-0001 existe en cada país. El token no cruza la carpeta."""
        otra_pais = 'argentina/servicio_tecnico/imagenes/OOW-MEDIA-01/ingreso_1.jpg'
        folio_en_el_archivo = (
            'mexico/servicio_tecnico/imagenes/OTRA/OOW-MEDIA-01.jpg'
        )
        request = self._get(otra_pais, AnonymousUser(), token='token-media-vigente')
        self.assertEqual(clasificar_acceso_media(request, otra_pais), 'denegado')
        self.assertEqual(
            clasificar_acceso_media(request, folio_en_el_archivo),
            'denegado',
        )

    def test_sesion_de_mexico_no_abre_argentina(self):
        """El personal logueado ve su país. La carpeta del otro país sigue cerrada."""
        ajena = 'argentina/servicio_tecnico/imagenes/OOW-MEDIA-01/ingreso_1.jpg'
        request = self._get(ajena, _UsuarioLogueado())
        self.assertEqual(clasificar_acceso_media(request, ajena), 'denegado')

    def test_token_abre_el_cfdi_de_su_orden_y_no_el_de_otra(self):
        """facturacion/<id>/ sí. El id de otra orden, no."""
        propia = f'mexico/facturacion/{self.orden.pk}/pdf/uuid.pdf'
        ajena = 'mexico/facturacion/999999/pdf/uuid.pdf'
        request = self._get(propia, AnonymousUser(), token='token-media-vigente')
        self.assertEqual(clasificar_acceso_media(request, propia), 'privado')
        self.assertEqual(clasificar_acceso_media(request, ajena), 'denegado')

    def test_token_se_anexa_a_la_url_de_la_galeria(self):
        """La página de seguimiento tiene que mandar el permiso en la foto."""
        url = anexar_token_seguimiento('/media/mexico/a.jpg', 'token con espacio')
        self.assertEqual(url, '/media/mexico/a.jpg?t=token%20con%20espacio')


@override_settings(MEDIA_ACCEL_REDIRECT=True)
class VistaMediaAccelTests(TestCase):
    """Con el ajuste de Docker, Django no lee el disco: le pide a Nginx."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_anonimo_recibe_404_sin_abrir_el_archivo(self):
        """Sin sesión ni token, ni siquiera llega el redirect interno."""
        request = self.factory.get('/media/mexico/servicio_tecnico/imagenes/X/a.jpg')
        request.user = AnonymousUser()
        with self.assertRaises(Http404):
            serve_media_from_multiple_locations(
                request,
                'mexico/servicio_tecnico/imagenes/X/a.jpg',
            )

    def test_con_sesion_responde_x_accel_redirect(self):
        """El personal logueado obtiene la ruta interna del archivo real."""
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            destino = raiz / 'mexico' / 'servicio_tecnico' / 'imagenes' / 'X'
            destino.mkdir(parents=True)
            archivo = destino / 'ingreso_1.jpg'
            archivo.write_bytes(b'\xff\xd8\xff')
            path = 'mexico/servicio_tecnico/imagenes/X/ingreso_1.jpg'
            request = self.factory.get(f'/media/{path}')
            request.user = _UsuarioLogueado()
            with patch('config.storage_utils.PRIMARY_STORAGE_PATH', raiz), patch(
                'config.storage_utils.ALTERNATE_STORAGE_PATH', raiz
            ):
                response = serve_media_from_multiple_locations(request, path)
            self.assertEqual(
                response['X-Accel-Redirect'],
                '/media-interno/mexico/servicio_tecnico/imagenes/X/ingreso_1.jpg',
            )
            self.assertEqual(response['Cache-Control'], 'private, no-store')
            self.assertEqual(response['Content-Type'], 'image/jpeg')

    def test_un_enlace_fuera_de_media_no_se_entrega(self):
        """Un symlink dentro de media que apunta afuera no se manda a Nginx."""
        with tempfile.TemporaryDirectory() as media, tempfile.TemporaryDirectory() as fuera_dir:
            raiz = Path(media)
            carpeta = raiz / 'mexico'
            carpeta.mkdir()
            secreto = Path(fuera_dir) / 'secreto.txt'
            secreto.write_text('no', encoding='utf-8')
            enlace = carpeta / 'foto.jpg'
            enlace.symlink_to(secreto)
            request = self.factory.get('/media/mexico/foto.jpg')
            request.user = _UsuarioLogueado()
            with patch('config.storage_utils.PRIMARY_STORAGE_PATH', raiz), patch(
                'config.storage_utils.ALTERNATE_STORAGE_PATH', raiz
            ):
                with self.assertRaises(Http404):
                    serve_media_from_multiple_locations(request, 'mexico/foto.jpg')

    def test_un_banner_que_apunta_a_una_firma_no_se_entrega(self):
        """
        banners/ es público. Si ese nombre es un enlace a una firma,
        no se sigue: si no, cualquiera vería el archivo privado.
        """
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            firma_dir = raiz / 'mexico' / 'servicio_tecnico' / 'formato_garantia' / 'OOW-1'
            firma_dir.mkdir(parents=True)
            firma = firma_dir / 'firma.png'
            firma.write_bytes(b'\x89PNG')
            banners = raiz / 'mexico' / 'banners'
            banners.mkdir(parents=True)
            trampa = banners / 'promo.jpg'
            trampa.symlink_to(firma)
            request = self.factory.get('/media/mexico/banners/promo.jpg')
            request.user = AnonymousUser()
            with patch('config.storage_utils.PRIMARY_STORAGE_PATH', raiz), patch(
                'config.storage_utils.ALTERNATE_STORAGE_PATH', raiz
            ):
                with self.assertRaises(Http404):
                    serve_media_from_multiple_locations(
                        request,
                        'mexico/banners/promo.jpg',
                    )


class NombreArchivoPrivadoTests(SimpleTestCase):
    """Las firmas nuevas no se llaman firma_cliente.png."""

    def test_el_nombre_cambia_y_no_es_el_fijo(self):
        """Dos llamadas no repiten el nombre. Ninguna es el viejo nombre fijo."""
        uno = nombre_archivo_privado('firma_cliente')
        otro = nombre_archivo_privado('firma_cliente')
        self.assertNotEqual(uno, otro)
        self.assertNotEqual(uno, 'firma_cliente.png')
        self.assertTrue(uno.startswith('firma_cliente_'))
        self.assertTrue(uno.endswith('.png'))
