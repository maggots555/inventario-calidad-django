"""
Regresión visual del modal «Notificar al cliente: sin piezas (PNC)».

EXPLICACIÓN PARA PRINCIPIANTES:
El modal pasó a dos columnas y la lista de copias se ve como la de
«Notificar a Recepción». Quien envía («TÚ») queda marcado y bloqueado,
con un input hidden porque un checkbox disabled no viaja en el POST.
notificar_cliente_pnc.ts sigue buscando los mismos id.
Este test lee el HTML (sin base de datos) y lo confirma.
"""

from pathlib import Path

from django.test import SimpleTestCase


_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / 'templates'
    / 'almacen'
    / 'cotizaciones'
    / 'detalle_solicitud.html'
)
_CSS = (
    Path(__file__).resolve().parents[2]
    / 'static'
    / 'css'
    / 'notificar_cliente_pnc_modal.css'
)


class ModalNotificarClientePncDisenoTest(SimpleTestCase):
    """
    Sin BD: el markup fuente conserva el contrato del formulario.
    """

    def test_modal_conserva_ganchos_y_el_orden_de_columnas(self):
        """
        Objetivo: el rediseño no borra el correo, la nota ni las copias.

        Efectos: ninguno.
        """
        texto = _TEMPLATE.read_text(encoding='utf-8')
        inicio = texto.find('id="modalNotificarClientePnc"')
        fin = texto.find('id="notificarClientePncConfig"')
        modal = texto[inicio:fin]

        for gancho in (
            'id="formNotificarClientePnc"',
            'id="btnNotificarClientePnc"',
            'id="email_cliente_pnc"',
            'name="email_cliente"',
            'id="mensaje_personalizado_pnc_cliente"',
            'name="mensaje_personalizado"',
            'name="copia_empleados"',
            'id="pnc_cli_emp_{{ empleado.id }}"',
            'checked disabled',
            'id="pnc_cli_emp_current_user"',
            'not usuario_en_lista_cc',
            'pnc-cli-split',
            'pnc-cli-col-izq',
            'pnc-cli-col-der',
            'pnc-cli-item-tu',
        ):
            self.assertIn(gancho, modal, f'Falta en el modal PNC: {gancho}')

        # Contactos escritos antes que la nota, sin cruzar columnas.
        self.assertLess(
            modal.find('id="email_cliente_pnc"'),
            modal.find('id="mensaje_personalizado_pnc_cliente"'),
        )
        self.assertNotIn(' order-1', modal)
        self.assertNotIn(' order-2', modal)

    def test_css_ambar_esta_enlazado(self):
        """
        Objetivo: la hoja del modal se carga en el detalle de la solicitud.

        Efectos: ninguno.
        """
        texto = _TEMPLATE.read_text(encoding='utf-8')
        self.assertIn('css/notificar_cliente_pnc_modal.css', texto)
        self.assertTrue(_CSS.is_file())
        css = _CSS.read_text(encoding='utf-8')
        self.assertIn('#modalNotificarClientePnc', css)
        self.assertIn('[data-bs-theme="dark"]', css)
        self.assertIn('#f59e0b', css)
        self.assertIn('.pnc-cli-avatar-tu', css)
