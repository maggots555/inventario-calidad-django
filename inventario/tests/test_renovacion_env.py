"""
Tests del candado que exige renovar docker/.env cada 60 días.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No borramos un .env de verdad. Usamos una carpeta temporal.
Comprobamos la regla (sin sello no vence) y la pantalla
(solo el superusuario, clave mala no mueve la fecha, clave buena sí).
"""

import os
import tempfile
from datetime import timedelta, timezone as tz_std
from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from inventario.renovacion_env import (
    DIAS_VIGENCIA,
    dias_restantes,
    esta_vencido,
    guardar_clave_inicial,
    renovar,
)
from inventario.views_renovacion_env import renovar_entorno_docker


def _ajustes_de_prueba(carpeta: str) -> dict:
    """
    Carpeta temporal, caché en memoria y estáticos sin manifest.

    El manifest de collectstatic no hace falta para pintar esta pantalla,
    y la caché local evita depender de Redis al contar intentos fallidos.
    """
    return {
        'RENOVACION_ENV_DIR': carpeta,
        'CACHES': {
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'LOCATION': 'renovacion-env-tests',
            }
        },
        'STORAGES': {
            'default': {
                'BACKEND': 'django.core.files.storage.FileSystemStorage',
            },
            'staticfiles': {
                'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
            },
        },
    }


class RenovacionEnvReglaTests(SimpleTestCase):
    """
    Objetivo: la regla de vencimiento, sin base de datos.

    Efectos secundarios: escribe archivos en una carpeta temporal.
    """

    def setUp(self) -> None:
        """Carpeta vacía y settings apuntando a ella."""
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.override = override_settings(RENOVACION_ENV_DIR=self.tmp.name)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def test_sin_sello_no_esta_vencido(self) -> None:
        """Si nadie armó el candado, el cron no debe borrar nada."""
        self.assertFalse(esta_vencido())
        self.assertIsNone(dias_restantes())

    def test_sello_recien_escrito_sigue_vigente(self) -> None:
        """Armar la clave deja 60 días y no marca vencido."""
        guardar_clave_inicial('clave-segura-1')
        self.assertFalse(esta_vencido())
        self.assertEqual(dias_restantes(), DIAS_VIGENCIA)

    def test_el_cron_puede_leer_el_sello_y_no_el_hash(self) -> None:
        """
        El cron corre como otro usuario. La fecha se puede leer;
        el hash de la clave no.
        """
        guardar_clave_inicial('clave-segura-1')
        carpeta = Path(self.tmp.name)
        modo_carpeta = os.stat(carpeta).st_mode & 0o777
        modo_sello = os.stat(carpeta / 'ultima_ok').st_mode & 0o777
        modo_hash = os.stat(carpeta / 'clave.hash').st_mode & 0o777
        # Otros pueden entrar a la carpeta y leer la fecha.
        self.assertEqual(modo_carpeta, 0o755)
        self.assertEqual(modo_sello, 0o644)
        # Otros no pueden leer el hash (ni el grupo).
        self.assertEqual(modo_hash, 0o600)

    def test_sello_de_hace_61_dias_esta_vencido(self) -> None:
        """Pasados los 60 días, la regla dice que sí venció."""
        guardar_clave_inicial('clave-segura-1')
        # `ahora` no reescribe el archivo: solo simula el reloj del cron.
        dentro_de_61 = timezone.now() + timedelta(days=61)
        self.assertTrue(esta_vencido(ahora=dentro_de_61))
        self.assertLess(dias_restantes(ahora=dentro_de_61), 0)


class RenovacionEnvPantallaTests(TestCase):
    """
    Objetivo: permisos y efecto de la clave sobre el sello.

    Efectos secundarios: usuarios de prueba y archivos en carpeta temporal.
    """

    databases = {'default'}

    def setUp(self) -> None:
        """Superusuario, usuario normal, carpeta temporal y caché local."""
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.override = override_settings(**_ajustes_de_prueba(self.tmp.name))
        self.override.enable()
        self.addCleanup(self.override.disable)
        cache.clear()

        self.factory = RequestFactory()
        self.superuser = User.objects.create_superuser(
            username='renovador',
            email='renovador@example.com',
            password='clave-de-login',
        )
        self.normal = User.objects.create_user(
            username='empleado_normal',
            password='clave-de-login',
        )

    def _peticion(self, usuario, metodo: str, datos: dict | None = None):
        """
        Request de prueba con sesión y mensajes, sin pasar por middleware.

        Args:
            usuario: User ya guardado.
            metodo: 'get' o 'post'.
            datos: Campos del formulario, solo en POST.
        """
        ruta = reverse('renovar_entorno_docker')
        if metodo == 'post':
            request = self.factory.post(ruta, datos or {})
        else:
            request = self.factory.get(ruta)
        request.user = usuario
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return request

    def _texto_sello(self) -> str:
        """Lee ultima_ok de la carpeta temporal."""
        from pathlib import Path

        return (Path(self.tmp.name) / 'ultima_ok').read_text(encoding='utf-8')

    def test_la_ruta_existe(self) -> None:
        """La pantalla cuelga de inventario, junto a las otras de admin."""
        self.assertEqual(
            reverse('renovar_entorno_docker'),
            '/inventario/admin/renovar-entorno/',
        )

    def test_superusuario_ve_el_aviso_antes_de_armar(self) -> None:
        """La primera visita explica que todavía no se borra nada."""
        response = renovar_entorno_docker(self._peticion(self.superuser, 'get'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('docker/.env', html)
        self.assertIn('no está armado', html)

    def test_quien_no_es_superusuario_no_entra(self) -> None:
        """Un usuario normal es redirigido a acceso denegado."""
        response = renovar_entorno_docker(self._peticion(self.normal, 'get'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('acceso-denegado', response.url)

    def test_primera_clave_crea_hash_y_sello(self) -> None:
        """Armar el candado deja los dos archivos y responde con redirección."""
        from pathlib import Path

        response = renovar_entorno_docker(self._peticion(self.superuser, 'post', {
            'accion': 'armar',
            'clave': 'clave-segura-1',
            'clave2': 'clave-segura-1',
        }))
        self.assertEqual(response.status_code, 302)
        carpeta = Path(self.tmp.name)
        self.assertTrue((carpeta / 'clave.hash').is_file())
        self.assertTrue((carpeta / 'ultima_ok').is_file())
        self.assertFalse(esta_vencido())

    def test_clave_incorrecta_no_mueve_la_fecha(self) -> None:
        """Un error de tecleo no renueva el plazo."""
        guardar_clave_inicial('clave-segura-1')
        antes = self._texto_sello()
        response = renovar_entorno_docker(self._peticion(self.superuser, 'post', {
            'accion': 'renovar',
            'clave': 'esto-no-es',
        }))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._texto_sello(), antes)
        self.assertFalse(renovar('esto-no-es'))

    def test_clave_correcta_actualiza_el_sello(self) -> None:
        """La clave buena sustituye la fecha vieja por una de hoy."""
        from pathlib import Path

        guardar_clave_inicial('clave-segura-1')
        # Fecha vieja a propósito: si la vista no escribe, el test lo nota.
        viejo = (
            (timezone.now() - timedelta(days=10))
            .astimezone(tz_std.utc)
            .strftime('%Y-%m-%dT%H:%M:%SZ')
        )
        (Path(self.tmp.name) / 'ultima_ok').write_text(viejo, encoding='utf-8')

        response = renovar_entorno_docker(self._peticion(self.superuser, 'post', {
            'accion': 'renovar',
            'clave': 'clave-segura-1',
        }))
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(self._texto_sello(), viejo)
        self.assertFalse(esta_vencido())
        self.assertEqual(dias_restantes(), DIAS_VIGENCIA)
