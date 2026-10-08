"""
Copia (Cc) al empleado de la sesión al enviar un formato digital.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
El PDF va en "Para" a los correos que se capturaron en el formato
(el cliente). Quien pulsó Enviar o Reenviar también debe recibir el
mismo correo, en copia. Si no tiene correo, o ese correo ya está en
la lista del cliente, no se duplica: el cliente igual recibe el PDF.
"""

from __future__ import annotations


def copia_empleado_sesion(
    email_empleado: str,
    destinatarios: list[str],
) -> list[str] | None:
    """
    Arma la lista Cc con el correo del empleado que envió el formato.

    Objetivo de negocio:
        Quien pulsa Enviar o Reenviar (la sesión) recibe una copia del
        PDF, sin repetir el correo si ya está entre los destinatarios.

    Args:
        email_empleado: Correo del empleado de la sesión. Puede venir vacío.
        destinatarios: Correos "Para" del cliente (hasta 3).

    Returns:
        Lista de un correo para pasar como cc=, o None si no hay copia.

    Efectos secundarios:
        Ninguno. No envía correo ni escribe en la base.
    """
    correo = (email_empleado or '').strip()
    if not correo:
        return None

    # EXPLICACIÓN: Ana@x.com y ana@x.com son el mismo buzón.
    # Si el empleado ya está en "Para", no lo repetimos en Cc.
    ya_esta = correo.lower() in {
        (destino or '').strip().lower() for destino in (destinatarios or [])
    }
    if ya_esta:
        return None
    return [correo]
