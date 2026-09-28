"""
Lista de copia del modal «Enviar Cotización al Cliente».

EXPLICACIÓN PARA PRINCIPIANTES:
La lista pasó de renglones de texto a tarjetas con foto, como Recepción
y el aviso PNC. Quien envía («TÚ») queda marcado y bloqueado por id de
empleado, no comparando el correo del login.

El script arma el POST a mano y solo debe leer las casillas de este
modal: en la misma página hay otros name="copia_empleados".
"""

from pathlib import Path

from django.test import SimpleTestCase


_RAIZ = Path(__file__).resolve().parents[2]
_TEMPLATE = (
    _RAIZ
    / 'almacen'
    / 'templates'
    / 'almacen'
    / 'cotizaciones'
    / 'detalle_solicitud.html'
)
_CSS = _RAIZ / 'static' / 'css' / 'cotizacion_cliente.css'
_TS = _RAIZ / 'static' / 'ts' / 'cotizacion_cliente_modal.ts'


class ModalEnviarCotizacionCcDisenoTest(SimpleTestCase):
    """
    Sin BD: el markup y el script conservan el contrato de la copia.
    """

    def test_lista_cc_tiene_fotos_y_tu_bloqueado(self):
        """
        Objetivo: la copia usa tarjetas y «TÚ» no se puede desmarcar.

        Efectos: ninguno.
        """
        texto = _TEMPLATE.read_text(encoding='utf-8')
        inicio = texto.find('id="modalEnviarCotizacionCliente"')
        fin = texto.find('window.COTIZACION_CLIENTE_CONFIG')
        modal = texto[inicio:fin]

        for gancho in (
            'id="ccEmp{{ emp.pk }}"',
            'name="copia_empleados"',
            'id="ccEmpCurrentUser"',
            'checked disabled',
            'not usuario_en_lista_cc',
            'cot-cc-scroll',
            'cot-cc-item-tu',
            'cot-cc-avatar-tu',
            'emp.foto_perfil',
        ):
            self.assertIn(gancho, modal, f'Falta en la copia de cotización: {gancho}')

        # Antes se comparaba el correo del login; eso fallaba si no coincidía.
        self.assertNotIn('emp.email == request.user.email', modal)
        self.assertNotIn(' order-1', modal)
        self.assertNotIn(' order-2', modal)

    def test_css_y_script_solo_leen_este_modal(self):
        """
        Objetivo: el estilo vive en la hoja del modal y el POST no
        mezcla las copias de Recepción o del aviso PNC.

        Efectos: ninguno.
        """
        css = _CSS.read_text(encoding='utf-8')
        self.assertIn('#modalEnviarCotizacionCliente .cot-cc-scroll', css)
        self.assertIn('#modalEnviarCotizacionCliente .cot-cc-avatar-tu', css)
        self.assertIn('[data-bs-theme="dark"]', css)

        ts = _TS.read_text(encoding='utf-8')
        self.assertIn("getElementById('modalEnviarCotizacionCliente')", ts)
        self.assertIn(
            'input[name="copia_empleados"]:checked',
            ts,
        )
        self.assertNotIn(
            "document.querySelectorAll<HTMLInputElement>('input[name=\"copia_empleados\"]:checked')",
            ts,
        )
