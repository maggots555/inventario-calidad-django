#!/usr/bin/env python
"""Comprueba que la pantalla de login de SIGMA ya responde.

Lo usa el healthcheck de Docker. No abre la base ni crea datos:
solo pregunta si Gunicorn ya sirve /login/. Si la página contesta
200, el contenedor se considera sano y Nginx puede arrancar.
"""
import sys
import urllib.request


def main() -> int:
    """
    Pregunta a Gunicorn si la pantalla de login ya está viva.

    Returns:
        int: 0 si /login/ responde 200. 1 si no hay respuesta o el código es otro.

    Efectos secundarios:
        Escribe en la salida el motivo cuando falla. No toca la base de datos.
    """
    try:
        respuesta = urllib.request.urlopen(
            "http://127.0.0.1:8000/login/",
            timeout=5,
        )
    except Exception as exc:
        print(f"SIGMA aún no responde: {exc}")
        return 1
    if respuesta.status != 200:
        print(f"Login respondió {respuesta.status}, se esperaba 200.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
