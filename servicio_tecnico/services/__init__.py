"""
Servicios de dominio de Servicio Técnico (lógica fuera de las vistas HTTP).

EXPLICACIÓN PARA PRINCIPIANTES:
Aquí van helpers que crean registros o coordinan reglas de negocio y que
pueden usarse desde views, tasks Celery u otras apps (p. ej. Almacén),
sin depender del monolito views.py.
"""

from .historial import registrar_historial

__all__ = ['registrar_historial']
