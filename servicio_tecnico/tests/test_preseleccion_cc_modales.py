"""
Tests: preselección de CC en modales (diagnóstico / imágenes / videos).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
En detalle_orden.html los checkboxes de "Con copia a" se marcan según:
- Tú (usuario logueado): siempre
- Área CALIDAD: siempre
- FRONTDESK de la misma sucursal que la orden: sí
- CARRY IN: solo si la orden es MIS (Mail-In Service)

Aquí probamos esa lógica con un template mínimo idéntico a la regla,
y un humo que confirma que los 3 modales del HTML real la incluyen.
"""

from pathlib import Path
from types import SimpleNamespace

from django.template import Context, Template
from django.test import SimpleTestCase


# Misma condición que en detalle_orden.html (diag_emp_ / emp_img_ / ev_emp_).
# EXPLICACIÓN PARA PRINCIPIANTES: usamos un fragmento pequeño para no renderizar
# todo el detalle_orden (es enorme y depende de mucho contexto).
_TEMPLATE_CHECKBOX_CC = Template(
    """
    <input id="{{ prefijo }}_{{ empleado.id }}"
           type="checkbox"
           {% if empleado.id == request.user.empleado.id %}
               checked disabled
           {% elif empleado.area == 'CALIDAD' %}
               checked
           {% elif empleado.area == 'FRONTDESK' and empleado.sucursal == orden.sucursal %}
               checked
           {% elif empleado.area == 'CARRY IN' and orden.detalle_equipo.es_mis %}
               checked
           {% endif %}>
    """
)


def _render_checkbox(*, prefijo, empleado, usuario_empleado_id, es_mis, sucursal_orden):
    """
    Renderiza un checkbox CC con el contexto mínimo.

    Args:
        prefijo: Prefijo del id (diag_emp / emp_img / ev_emp).
        empleado: Objeto con id, area, sucursal.
        usuario_empleado_id: id del empleado logueado.
        es_mis: Si la orden es Mail-In Service.
        sucursal_orden: Sucursal de la orden (para comparar FRONTDESK).

    Returns:
        str: HTML del input renderizado.
    """
    # EXPLICACIÓN PARA PRINCIPIANTES: SimpleNamespace simula modelos sin BD.
    request = SimpleNamespace(
        user=SimpleNamespace(empleado=SimpleNamespace(id=usuario_empleado_id))
    )
    orden = SimpleNamespace(
        sucursal=sucursal_orden,
        detalle_equipo=SimpleNamespace(es_mis=es_mis),
    )
    return _TEMPLATE_CHECKBOX_CC.render(
        Context(
            {
                'prefijo': prefijo,
                'empleado': empleado,
                'request': request,
                'orden': orden,
            }
        )
    )


def _esta_checked(html):
    """True si el input quedó con el atributo checked."""
    return 'checked' in html


class PreseleccionCcLogicaTest(SimpleTestCase):
    """
    Casos felices y de borde de la regla de preselección CC.
    """

    def setUp(self):
        # Dos "sucursales" distintas solo como objetos comparables
        self.sucursal_a = object()
        self.sucursal_b = object()
        self.yo = SimpleNamespace(id=1, area='LAB', sucursal=self.sucursal_a)
        self.calidad = SimpleNamespace(id=2, area='CALIDAD', sucursal=self.sucursal_b)
        self.frontdesk_misma = SimpleNamespace(
            id=3, area='FRONTDESK', sucursal=self.sucursal_a
        )
        self.frontdesk_otra = SimpleNamespace(
            id=4, area='FRONTDESK', sucursal=self.sucursal_b
        )
        self.carry_in = SimpleNamespace(id=5, area='CARRY IN', sucursal=self.sucursal_a)

    def test_usuario_logueado_siempre_checked(self):
        html = _render_checkbox(
            prefijo='diag_emp',
            empleado=self.yo,
            usuario_empleado_id=1,
            es_mis=False,
            sucursal_orden=self.sucursal_a,
        )
        self.assertTrue(_esta_checked(html))
        self.assertIn('disabled', html)

    def test_calidad_siempre_checked(self):
        html = _render_checkbox(
            prefijo='emp_img',
            empleado=self.calidad,
            usuario_empleado_id=99,
            es_mis=False,
            sucursal_orden=self.sucursal_a,
        )
        self.assertTrue(_esta_checked(html))

    def test_frontdesk_misma_sucursal_checked(self):
        html = _render_checkbox(
            prefijo='ev_emp',
            empleado=self.frontdesk_misma,
            usuario_empleado_id=99,
            es_mis=False,
            sucursal_orden=self.sucursal_a,
        )
        self.assertTrue(_esta_checked(html))

    def test_frontdesk_otra_sucursal_no_checked(self):
        html = _render_checkbox(
            prefijo='emp_img',
            empleado=self.frontdesk_otra,
            usuario_empleado_id=99,
            es_mis=False,
            sucursal_orden=self.sucursal_a,
        )
        self.assertFalse(_esta_checked(html))

    def test_carry_in_sin_mis_no_checked(self):
        """Borde: CARRY IN visible en lista pero sin marcar si no es MIS."""
        html = _render_checkbox(
            prefijo='emp_img',
            empleado=self.carry_in,
            usuario_empleado_id=99,
            es_mis=False,
            sucursal_orden=self.sucursal_a,
        )
        self.assertFalse(_esta_checked(html))

    def test_carry_in_con_mis_checked(self):
        """Feliz: orden MIS → CARRY IN preseleccionado."""
        html = _render_checkbox(
            prefijo='diag_emp',
            empleado=self.carry_in,
            usuario_empleado_id=99,
            es_mis=True,
            sucursal_orden=self.sucursal_a,
        )
        self.assertTrue(_esta_checked(html))


class PreseleccionCcTemplateHumoTest(SimpleTestCase):
    """
    Humo: el HTML real de detalle_orden incluye la regla MIS en los 3 modales.
    """

    def test_tres_modales_tienen_regla_carry_in_mis(self):
        # EXPLICACIÓN PARA PRINCIPIANTES: leemos el archivo del template y
        # buscamos que cada modal (diag / img / videos) tenga el elif de MIS.
        ruta = (
            Path(__file__).resolve().parents[1]
            / 'templates'
            / 'servicio_tecnico'
            / 'detalle_orden.html'
        )
        contenido = ruta.read_text(encoding='utf-8')

        # Cada bloque de checkbox debe incluir la condición CARRY IN + es_mis
        self.assertIn("id=\"diag_emp_{{ empleado.id }}\"", contenido)
        self.assertIn("id=\"emp_img_{{ empleado.id }}\"", contenido)
        self.assertIn("id=\"ev_emp_{{ empleado.id }}\"", contenido)

        ocurrencias_mis = contenido.count(
            "empleado.area == 'CARRY IN' and orden.detalle_equipo.es_mis"
        )
        self.assertEqual(
            ocurrencias_mis,
            3,
            'Se esperaban 3 bloques (diagnóstico, imágenes y videos) con regla MIS→CARRY IN',
        )
