"""
Tests del arranque a prueba de olvidos (SECRET_KEY / DEBUG).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
SIGMA no debe arrancar si falta .env: antes usaba una clave de tutorial
que está en git. Estos tests clavan el helper, no vuelven a cargar
todo Django (settings ya se leyó de tu .env real).
"""

from decouple import UndefinedValueError
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.settings import exigir_variable_entorno, validar_secret_key_produccion


class ArranqueSeguroEnvTest(SimpleTestCase):
    """Sin .env no hay default inseguro; en prod tampoco hay clave de tutorial."""

    def test_falta_variable_lanza_improperly_configured(self) -> None:
        def _fuente(_nombre, **_kwargs):
            raise UndefinedValueError('SECRET_KEY')

        with self.assertRaises(ImproperlyConfigured) as ctx:
            exigir_variable_entorno('SECRET_KEY', fuente=_fuente)
        self.assertIn('.env', str(ctx.exception))
        self.assertIn('SECRET_KEY', str(ctx.exception))

    def test_lee_el_valor_cuando_existe(self) -> None:
        def _fuente(nombre, **_kwargs):
            self.assertEqual(nombre, 'DEBUG')
            return True

        self.assertTrue(exigir_variable_entorno('DEBUG', cast=bool, fuente=_fuente))

    def test_clave_insegura_prohibida_si_debug_es_false(self) -> None:
        with self.assertRaises(ImproperlyConfigured):
            validar_secret_key_produccion('django-insecure-abc', debug=False)

    def test_clave_insegura_permitida_en_desarrollo(self) -> None:
        """En DEBUG=True (laptop) una clave local insegura sí puede existir."""
        clave = validar_secret_key_produccion('django-insecure-dev', debug=True)
        self.assertEqual(clave, 'django-insecure-dev')
