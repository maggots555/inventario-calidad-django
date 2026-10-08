"""
Tests de la frase del clima en el saludo del inicio.

EXPLICACIÓN PARA PRINCIPIANTES:
No salimos a Internet. Open-Meteo se simula con un doble (mock):
le decimos qué JSON "respondió" y comprobamos la frase en español.

Casos:
1) Código de lluvia → "lluvioso". Día despejado y caliente → "caluroso".
2) Sucursal sin ciudad, o ciudad que el buscador no conoce → capital del país.
3) El servicio no contesta → la frase queda vacía. No se cambia a la capital.
4) La segunda lectura sale del caché: ya no hay otra llamada HTTP.
"""

import json
import urllib.error
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.core.cache import cache
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from inventario.clima_saludo import (
    _CAPITALES,
    frase_clima_para_usuario,
    frase_desde_codigo,
)
from inventario.models import Empleado, Sucursal


# Caché en memoria, aislado de Redis, para que un test no deje frases al siguiente.
_CACHE_DE_PRUEBA = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'clima-saludo-tests',
    },
}

# País fijo: estos tests no pasan por el middleware que elige México/Argentina/etc.
_PAIS_MEXICO = {
    'codigo': 'MX',
    'timezone': 'America/Mexico_City',
}


def _respuesta_json(payload: dict):
    """
    Imita el objeto que devuelve urllib al abrir una URL (un context manager).

    Args:
        payload: dict que la función bajo prueba va a leer como JSON.

    Returns:
        MagicMock usable con `with urlopen(...) as respuesta`.
    """
    cuerpo = json.dumps(payload).encode('utf-8')
    respuesta = mock.MagicMock()
    respuesta.read.return_value = cuerpo
    respuesta.__enter__.return_value = respuesta
    respuesta.__exit__.return_value = False
    return respuesta


class FraseDesdeCodigoTest(SimpleTestCase):
    """
    Objetivo: el mapa código de clima → frase, sin base de datos ni red.

    Efectos secundarios: ninguno.
    """

    def test_lluvia_dice_lluvioso(self):
        """Código 61 es lluvia. Aunque haga calor, la frase dice lluvioso."""
        frase = frase_desde_codigo(61, 34.0)
        self.assertIn('lluvioso', frase)
        self.assertNotIn('caluroso', frase)

    def test_despejado_y_caliente_dice_caluroso(self):
        """Código 0 es cielo despejado. Con máxima de 33° se dice caluroso."""
        frase = frase_desde_codigo(0, 33.0)
        self.assertEqual(frase, 'hoy nos espera un día caluroso')

    def test_despejado_y_templado_dice_soleado(self):
        """Sin calor ni frío extremos, un día despejado se dice soleado."""
        frase = frase_desde_codigo(1, 24.0)
        self.assertEqual(frase, 'hoy nos espera un día soleado')

    def test_tormenta_y_frio(self):
        """La tormenta gana al resto. Un día despejado y helado se dice frío."""
        self.assertEqual(frase_desde_codigo(95, 28.0), 'hoy nos espera un día con tormentas')
        self.assertEqual(frase_desde_codigo(0, 8.0), 'hoy nos espera un día frío')


@override_settings(
    CACHES=_CACHE_DE_PRUEBA,
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            # El dashboard extiende base.html, que pide CSS con {% static %}.
            # Sin esto, el test exige el manifiesto de collectstatic.
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class ClimaSaludoTest(TestCase):
    """
    Objetivo: ciudad de la sucursal, respaldo a la capital, fallo de red y caché.

    Efectos secundarios: crea sucursal, usuario y empleado en la BD de pruebas.
    El HTTP real está parcheado.
    """

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        """Limpia el caché y arma un empleado en una sucursal sin ciudad."""
        cache.clear()
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            codigo='SUC-CLIMA',
            nombre='Satélite',
            ciudad='',
            activa=True,
        )
        self.usuario = User.objects.create_user(
            username='jorge_clima',
            first_name='Jorge',
            password='testpass123',
        )
        Empleado.objects.create(
            nombre_completo='Jorge Prueba',
            cargo='Técnico',
            area='Laboratorio',
            sucursal=self.sucursal,
            user=self.usuario,
        )

    def _parche_pais(self):
        """Fija el país en México para no depender del hilo del middleware."""
        return mock.patch(
            'config.paises_config.get_pais_actual',
            return_value=_PAIS_MEXICO,
        )

    def test_sin_ciudad_consulta_la_capital(self):
        """
        Sucursal sin ciudad: no se busca el nombre, se pide el clima
        de Ciudad de México (latitud fija del módulo).
        """
        urls = []

        def falso_urlopen(peticion, timeout=2.5):
            urls.append(peticion.full_url)
            return _respuesta_json({
                'daily': {
                    'weather_code': [61],
                    'temperature_2m_max': [22.0],
                },
            })

        with self._parche_pais(), mock.patch(
            'inventario.clima_saludo.urllib.request.urlopen',
            side_effect=falso_urlopen,
        ):
            frase = frase_clima_para_usuario(self.usuario)

        self.assertEqual(frase, 'hoy nos espera un día lluvioso')
        self.assertEqual(len(urls), 1)
        # Sin ciudad no hay geocodificación: una sola llamada, la del pronóstico.
        self.assertNotIn('geocoding-api', urls[0])
        latitud = _CAPITALES['MX']['latitud']
        self.assertIn(f'latitude={latitud:.4f}', urls[0])

    def test_servicio_no_responde_frase_vacia(self):
        """Si Open-Meteo falla, el saludo no recibe frase y no hay excepción."""
        with self._parche_pais(), mock.patch(
            'inventario.clima_saludo.urllib.request.urlopen',
            side_effect=urllib.error.URLError('sin red'),
        ):
            frase = frase_clima_para_usuario(self.usuario)

        self.assertEqual(frase, '')

    def test_ciudad_desconocida_usa_la_capital(self):
        """
        Si el buscador contesta y no conoce el nombre, sí usamos la capital.
        Eso es distinto de un corte de red.
        """
        self.sucursal.ciudad = 'CiudadQueNoExisteXYZ'
        self.sucursal.save(update_fields=['ciudad'])
        urls = []

        def falso_urlopen(peticion, timeout=2.5):
            urls.append(peticion.full_url)
            if 'geocoding-api' in peticion.full_url:
                return _respuesta_json({'results': []})
            return _respuesta_json({
                'daily': {
                    'weather_code': [3],
                    'temperature_2m_max': [18.0],
                },
            })

        with self._parche_pais(), mock.patch(
            'inventario.clima_saludo.urllib.request.urlopen',
            side_effect=falso_urlopen,
        ):
            frase = frase_clima_para_usuario(self.usuario)

        self.assertEqual(frase, 'hoy nos espera un día nublado')
        self.assertEqual(len(urls), 2)
        self.assertIn('geocoding-api', urls[0])
        latitud = _CAPITALES['MX']['latitud']
        self.assertIn(f'latitude={latitud:.4f}', urls[1])

    def test_falla_de_red_no_cambia_a_la_capital(self):
        """
        Un timeout al buscar Guadalajara no debe pedir el clima de la capital.
        La segunda visita relee el fallo guardado y no vuelve a salir a Internet.
        """
        self.sucursal.ciudad = 'Guadalajara'
        self.sucursal.save(update_fields=['ciudad'])
        llamadas = []

        def falso_urlopen(peticion, timeout=2.5):
            llamadas.append(peticion.full_url)
            raise urllib.error.URLError('timeout')

        with self._parche_pais(), mock.patch(
            'inventario.clima_saludo.urllib.request.urlopen',
            side_effect=falso_urlopen,
        ):
            primera = frase_clima_para_usuario(self.usuario)
            cuantas = len(llamadas)
            segunda = frase_clima_para_usuario(self.usuario)

        self.assertEqual(primera, '')
        self.assertEqual(segunda, '')
        # Solo el intento de ubicar la ciudad. No hay segunda llamada al pronóstico.
        self.assertEqual(cuantas, 1)
        self.assertIn('geocoding-api', llamadas[0])
        self.assertEqual(len(llamadas), 1)

    def test_respuesta_enorme_no_se_usa(self):
        """Un cuerpo más grande que el tope se descarta y el saludo queda vacío."""
        self.sucursal.ciudad = 'Guadalajara'
        self.sucursal.save(update_fields=['ciudad'])

        def falso_urlopen(peticion, timeout=2.5):
            respuesta = mock.MagicMock()
            respuesta.read.return_value = b'{' + (b'x' * 70_000)
            respuesta.__enter__.return_value = respuesta
            respuesta.__exit__.return_value = False
            return respuesta

        with self._parche_pais(), mock.patch(
            'inventario.clima_saludo.urllib.request.urlopen',
            side_effect=falso_urlopen,
        ):
            frase = frase_clima_para_usuario(self.usuario)

        self.assertEqual(frase, '')

    def test_segunda_lectura_sale_del_cache(self):
        """
        La primera visita geocodifica y pide el pronóstico.
        La segunda relee la frase guardada y no vuelve a llamar.
        """
        self.sucursal.ciudad = 'Guadalajara'
        self.sucursal.save(update_fields=['ciudad'])
        llamadas = []

        def falso_urlopen(peticion, timeout=2.5):
            url = peticion.full_url
            llamadas.append(url)
            if 'geocoding-api' in url:
                return _respuesta_json({
                    'results': [{
                        'latitude': 20.6597,
                        'longitude': -103.3496,
                        'name': 'Guadalajara',
                    }],
                })
            return _respuesta_json({
                'daily': {
                    'weather_code': [0],
                    'temperature_2m_max': [33.2],
                },
            })

        with self._parche_pais(), mock.patch(
            'inventario.clima_saludo.urllib.request.urlopen',
            side_effect=falso_urlopen,
        ):
            primera = frase_clima_para_usuario(self.usuario)
            cuantas_la_primera_vez = len(llamadas)
            segunda = frase_clima_para_usuario(self.usuario)

        self.assertEqual(primera, 'hoy nos espera un día caluroso')
        self.assertEqual(segunda, primera)
        # Geocodificar + pronóstico. La segunda lectura no suma llamadas.
        self.assertEqual(cuantas_la_primera_vez, 2)
        self.assertEqual(len(llamadas), 2)

    def test_template_muestra_la_frase(self):
        """El hero pinta la frase cuando el servidor la mandó."""
        html = self._render_home('hoy nos espera un día lluvioso')
        self.assertIn('greeting-clima', html)
        self.assertIn('hoy nos espera un día lluvioso', html)
        # Coma solo antes del nombre. Después de Jorge va un espacio, no otra coma.
        # Y los spans van pegados: si hay un salto de línea, aparece "días , Jorge".
        self.assertIn(
            '<span class="greeting-name">, Jorge</span>'
            '<span class="greeting-clima"> hoy nos espera un día lluvioso</span>',
            html,
        )
        self.assertNotIn(', hoy nos espera', html)
        # El gancho de la hora sigue ahí: el JavaScript cambia "Bienvenido".
        self.assertIn('id="greeting-time"', html)

    def test_template_sin_clima_no_agrega_la_frase(self):
        """Sin dato de clima el saludo no inventa una cola."""
        html = self._render_home('')
        self.assertNotIn('greeting-clima', html)
        self.assertIn('id="greeting-time"', html)

    def _render_home(self, frase_clima: str) -> str:
        """
        Renderiza el dashboard con un contexto mínimo, sin ejecutar la vista.

        La vista real armaría la cita con IA y el clima por HTTP.
        Aquí solo queremos ver el HTML del saludo.

        Args:
            frase_clima: texto que habría producido frase_clima_para_usuario.

        Returns:
            str: HTML del dashboard.
        """
        request = self.factory.get('/')
        request.user = self.usuario
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return render_to_string(
            'dashboard_principal.html',
            {'frase_clima': frase_clima, 'cita_diaria': ''},
            request=request,
        )
