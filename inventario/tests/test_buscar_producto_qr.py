"""
La búsqueda por QR del inventario exige sesión y no filtra pistas.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
RequestFactory llama la vista directo, sin el middleware de países.
Así el producto de prueba se lee de la misma base donde se creó.
AnonymousUser simula a alguien que no ha entrado al sistema.
"""

import json

from django.contrib.auth.models import AnonymousUser, Permission, User
from django.test import RequestFactory, TestCase

from inventario.models import Producto
from inventario.views import buscar_producto_fraccionable_qr, buscar_producto_qr


class BuscarProductoQrSeguroTests(TestCase):
    """Sin login no hay datos. Con login, hace falta el permiso del escáner."""

    def setUp(self):
        self.factory = RequestFactory()
        self.producto = Producto.objects.create(
            nombre='Alcohol isopropilico',
            codigo_qr='INV-QR-SEGURO-01',
            cantidad=4,
            ubicacion='Anaquel B',
            es_objeto_unico=True,
            stock_minimo=0,
        )
        self.usuario = User.objects.create_user(
            username='almacen_qr',
            password='testpass123',
        )
        permiso = Permission.objects.get(codename='add_movimiento')
        self.usuario.user_permissions.add(permiso)
        # has_perm guarda el resultado. Recargamos después de dar el permiso.
        self.usuario = User.objects.get(pk=self.usuario.pk)
        self.sin_permiso = User.objects.create_user(
            username='sin_escaner',
            password='testpass123',
        )

    def _get(self, usuario, codigo):
        """Arma el GET que haría el escáner y llama la vista."""
        request = self.factory.get(
            '/inventario/api/buscar-producto-qr/',
            {'codigo_qr': codigo},
        )
        request.user = usuario
        return buscar_producto_qr(request)

    def test_anonimo_no_recibe_el_producto(self):
        """Quien no inició sesión va al login, no al JSON del stock."""
        response = self._get(AnonymousUser(), self.producto.codigo_qr)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_sesion_sin_permiso_no_recibe_el_producto(self):
        """Haber entrado no alcanza: hace falta el permiso del movimiento rápido."""
        response = self._get(self.sin_permiso, self.producto.codigo_qr)
        self.assertEqual(response.status_code, 302)
        self.assertIn('acceso', response.url)
        self.assertNotIn(self.producto.nombre, response.url)

    def test_con_permiso_encuentra_el_producto(self):
        """Quien registra movimientos sí ve nombre y cantidad."""
        response = self._get(self.usuario, self.producto.codigo_qr)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['nombre'], 'Alcohol isopropilico')
        self.assertEqual(data['cantidad_actual'], 4)
        self.assertNotIn('debug', data)

    def test_no_encontrado_no_incluye_depuracion(self):
        """Un código inexistente no devuelve debug ni el texto buscado."""
        response = self._get(self.usuario, 'NO-EXISTE-999')
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertEqual(data, {'error': 'Producto no encontrado'})
        self.assertNotIn('debug', data)
        self.assertNotIn('codigo_buscado', data)
        self.assertNotIn('codigo_original', data)


class BuscarProductoFraccionableQrSeguroTests(TestCase):
    """La búsqueda fraccionaria pide el mismo permiso y no devuelve pistas."""

    def setUp(self):
        self.factory = RequestFactory()
        self.producto = Producto.objects.create(
            nombre='Alcohol litro',
            codigo_qr='INV-QR-FRAC-01',
            cantidad=2,
            ubicacion='Anaquel C',
            es_fraccionable=True,
            unidad_base='ml',
            cantidad_unitaria=1000,
            cantidad_actual=400,
            stock_minimo=0,
        )
        self.usuario = User.objects.create_user(
            username='almacen_frac',
            password='testpass123',
        )
        permiso = Permission.objects.get(codename='add_movimiento')
        self.usuario.user_permissions.add(permiso)
        self.usuario = User.objects.get(pk=self.usuario.pk)
        self.sin_permiso = User.objects.create_user(
            username='sin_frac',
            password='testpass123',
        )

    def _get(self, usuario, codigo):
        """Arma el GET de la pantalla fraccionaria y llama la vista."""
        request = self.factory.get(
            '/inventario/api/buscar-producto-fraccionable-qr/',
            {'codigo_qr': codigo},
        )
        request.user = usuario
        return buscar_producto_fraccionable_qr(request)

    def test_anonimo_va_al_login(self):
        """Sin sesión no hay stock fraccionario."""
        response = self._get(AnonymousUser(), self.producto.codigo_qr)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_sesion_sin_permiso_no_ve_el_producto(self):
        """Una cuenta sin el permiso del escáner no consulta esta API."""
        response = self._get(self.sin_permiso, self.producto.codigo_qr)
        self.assertEqual(response.status_code, 302)
        self.assertIn('acceso', response.url)

    def test_con_permiso_encuentra_el_fraccionable(self):
        """Quien registra movimientos sí ve el nombre y la unidad."""
        response = self._get(self.usuario, self.producto.codigo_qr)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['nombre'], 'Alcohol litro')
        self.assertEqual(data['unidad_base'], 'ml')
        self.assertNotIn('costo_unitario', data)

    def test_no_encontrado_no_repite_el_codigo(self):
        """Un fallo no devuelve el texto buscado ni un repr del escáner."""
        response = self._get(self.usuario, 'NO-EXISTE-FRAC')
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertEqual(data, {'error': 'Producto no encontrado'})
        self.assertNotIn('codigo_buscado', data)
        self.assertNotIn('codigo_recibido', data)
