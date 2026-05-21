"""
Validadores reutilizables compartidos entre todas las apps del proyecto.
"""
from django.core.exceptions import ValidationError


class FileSizeValidator:
    """
    Validador de tamaño máximo para archivos subidos.

    Uso en un campo:
        validators=[FileSizeValidator(10)]   # rechaza archivos > 10 MB

    Implementa deconstruct() para ser serializable en migraciones de Django.
    """

    def __init__(self, max_mb=10):
        self.max_mb = max_mb

    def __call__(self, value):
        if hasattr(value, 'size') and value.size > self.max_mb * 1024 * 1024:
            raise ValidationError(
                f'El archivo es demasiado grande. El tamaño máximo permitido es {self.max_mb} MB.'
            )

    def __eq__(self, other):
        return isinstance(other, FileSizeValidator) and self.max_mb == other.max_mb

    def deconstruct(self):
        return (
            'config.validators.FileSizeValidator',
            [self.max_mb],
            {},
        )
