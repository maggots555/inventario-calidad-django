"""
Humo del easter egg del ganso (dashboard de inicio).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El easter egg es una broma visual: un ganso camina por la barra superior,
"se roba" la foto del avatar y la devuelve. Vive en archivos estáticos
(static/ts/easter_egg_ganso.ts + static/css/easter_egg_ganso.css).

Como es JavaScript, aquí NO podemos ver la animación. Lo que sí protegemos
con estos tests es lo que se rompe en silencio:

1) Que el home siga cargando el CSS y el JS del ganso (si alguien limpia
   el template, el easter egg desaparece y nadie se entera).
2) Que el gancho del truco manual (.cita-diaria) siga existiendo.
3) Que el easter egg NO hable con el servidor: debe ser 100% visual, sin
   fetch ni formularios. Así garantizamos que la foto de perfil guardada
   (Empleado.foto_perfil) nunca se borra ni se modifica.

Usamos render_to_string con RequestFactory (no el Client HTTP) para evitar
el middleware multi-país y, sobre todo, para NO ejecutar la vista real:
dashboard_principal genera la cita del día llamando a la IA (Gemini/Ollama),
y un test nunca debe salir a Internet.
"""

from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings


@override_settings(
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            # Evita exigir manifest de collectstatic para CSS/JS nuevos
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class EasterEggGansoTest(TestCase):
    """
    Objetivo: que el ganso siga enchufado al home y siga siendo inofensivo.

    Efectos secundarios: crea un User mínimo en la BD de pruebas.
    """

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        """Crea factory y usuario autenticado para renderizar el dashboard."""
        self.factory = RequestFactory()
        self.usuario = User.objects.create_user(
            username='ganso_easter_egg_test',
            password='testpass123',
        )

    def _render_home(self) -> str:
        """
        Renderiza dashboard_principal.html con un contexto mínimo.

        Pasamos 'cita_diaria' a mano porque el gancho del truco manual
        (5 clics) vive dentro de ese bloque del template.

        Returns:
            str: HTML renderizado del dashboard de inicio.
        """
        request = self.factory.get('/')
        request.user = self.usuario
        request.session = SessionStore()
        request._messages = FallbackStorage(request)

        return render_to_string(
            'dashboard_principal.html',
            {'cita_diaria': 'El universo no trae manual; tú escribes el tuyo.'},
            request=request,
        )

    def test_home_carga_estaticos_del_ganso(self):
        """El dashboard de inicio debe enlazar el CSS y el JS del easter egg."""
        html = self._render_home()

        # Paso 1: la hoja de estilos con el waddle, el HONK y el hueco del avatar
        self.assertIn('easter_egg_ganso.css', html)

        # Paso 2: el script compilado (nunca se edita a mano: sale de tsc)
        self.assertIn('js/easter_egg_ganso.js', html)

    def test_home_conserva_gancho_de_la_cita(self):
        """
        El truco manual son 5 clics en .cita-diaria; si esa clase cambia,
        el easter egg deja de poder invocarse a voluntad.
        """
        html = self._render_home()
        self.assertIn('class="cita-diaria"', html)

    def test_easter_egg_es_solo_visual(self):
        """
        El módulo del ganso no debe comunicarse con el servidor.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Leemos el archivo fuente como texto y comprobamos que no aparezcan
        formas de mandar datos (fetch, XMLHttpRequest, .submit()). Si alguien
        en el futuro intentara "robar" la foto de verdad (borrarla en la BD),
        este test falla y lo frena.
        """
        ruta_ts = Path(settings.BASE_DIR) / 'static' / 'ts' / 'easter_egg_ganso.ts'
        self.assertTrue(ruta_ts.exists(), 'Falta static/ts/easter_egg_ganso.ts')

        codigo = ruta_ts.read_text(encoding='utf-8')

        # Paso 1: nada de llamadas al backend
        self.assertNotIn('fetch(', codigo)
        self.assertNotIn('XMLHttpRequest', codigo)
        self.assertNotIn('.submit(', codigo)

        # Paso 2: el robo es un clon del DOM, no una eliminación
        self.assertIn('cloneNode(true)', codigo)

        # Paso 3: la escena se apaga con prefers-reduced-motion
        self.assertIn('prefers-reduced-motion', codigo)

    def test_easter_egg_funciona_con_dedo(self):
        """
        El easter egg debe seguir disponible en celular, tablet y la PWA.

        EXPLICACIÓN PARA PRINCIPIANTES:
        La primera versión solo corría con mouse: pedía un puntero "fino"
        (any-pointer: fine) y una ventana de 992px o más. Eso dejaba fuera
        a los técnicos que usan SIGMA instalado en el teléfono.

        Estas comprobaciones son un candado: si alguien vuelve a meter esos
        filtros, el test falla y avisa que la PWA se quedó sin ganso.
        """
        base = Path(settings.BASE_DIR) / 'static'
        codigo = (base / 'ts' / 'easter_egg_ganso.ts').read_text(encoding='utf-8')
        estilos = (base / 'css' / 'easter_egg_ganso.css').read_text(encoding='utf-8')

        # Paso 1: sin filtros de mouse (esos apagaban el easter egg en táctil)
        self.assertNotIn('any-pointer: fine', codigo)
        self.assertNotIn('any-hover: hover', codigo)

        # Paso 2: el CSS ya no esconde el ganso en pantallas de móvil
        self.assertNotIn('991.98px', estilos)

        # Paso 3: en móvil el ganso se encoge en lugar de desaparecer
        self.assertIn('max-width: 576px', estilos)

        # Paso 4: 5 toques rápidos no deben disparar el zoom por doble toque
        self.assertIn('touch-action: manipulation', estilos)
