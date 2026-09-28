"""
Regresión del rediseño visual del modal de imágenes de ingreso.

EXPLICACIÓN PARA PRINCIPIANTES:
El modal se ve como el de diagnóstico (dos columnas), pero el JavaScript
sigue buscando los mismos id y name. Este test lee el archivo HTML
(sin base de datos) y confirma que esos ganchos siguen escritos, incluso
los que solo aparecen cuando el email del cliente es inválido.
"""

from pathlib import Path

from django.test import SimpleTestCase


_TEMPLATES_ST = (
    Path(__file__).resolve().parents[1] / 'templates' / 'servicio_tecnico'
)
_PARTIAL = _TEMPLATES_ST / 'partials' / 'detalle_orden' / '_modal_enviar_imagenes.html'
_ORQUESTADOR = _TEMPLATES_ST / 'detalle_orden.html'
_CSS = Path(__file__).resolve().parents[2] / 'static' / 'css' / 'enviar_imagenes_modal.css'


class ModalEnviarImagenesDisenoTest(SimpleTestCase):
    """
    Sin BD: el markup fuente conserva el contrato del formulario.
    """

    def test_partial_conserva_ganchos_y_ambas_ramas_de_email(self):
        """
        Objetivo: ni el envío ni el aviso de email inválido perdieron sus anclas.

        Args: ninguno (lee el filesystem).
        Efectos: ninguno.
        """
        texto = _PARTIAL.read_text(encoding='utf-8')

        # Ganchos que el TS y el POST necesitan, en cualquier rama.
        for gancho in (
            'id="modalEnviarImagenesCliente"',
            'id="formEnviarImagenesCliente"',
            'id="btnEnviarImagenes"',
            'form="formEnviarImagenesCliente"',
            'name="enviar_a_cliente"',
            'name="copia_tecnico"',
            'name="copia_empleados"',
            'name="imagenes_seleccionadas"',
            'name="mensaje_personalizado"',
            'name="modelo_ia_inspeccion"',
            'checkbox-imagen',
            'id="seleccionarTodasImagenes"',
            'id="contadorImagenesSeleccionadas"',
            'id="galeriaImagenesModal"',
            'id="previsualizacionArchivos"',
            'id="previsualizacionMensajePersonalizado"',
            'id="textoMensajePersonalizado"',
            'id="tecnico_asignado"',
            'id="emp_img_{{ empleado.id }}"',
            'id="img_emp_current_user"',
            'data-email-invalido="true"',
            "#modalEditarInfoEquipo",
            'ing-modal-split',
        ):
            self.assertIn(gancho, texto, f'Falta en el partial: {gancho}')

    def test_css_azul_esta_enlazado_en_detalle_orden(self):
        """
        Objetivo: la hoja nueva se carga en la página de la orden.

        Efectos: ninguno.
        """
        orquestador = _ORQUESTADOR.read_text(encoding='utf-8')
        self.assertIn("css/enviar_imagenes_modal.css", orquestador)
        self.assertTrue(_CSS.is_file(), 'Falta static/css/enviar_imagenes_modal.css')
        css = _CSS.read_text(encoding='utf-8')
        # El acento del ingreso es azul SIC, no el verde del diagnóstico.
        self.assertIn('#1f6391', css)
        self.assertIn('[data-bs-theme="dark"]', css)
        self.assertNotIn('.diag-', css)
