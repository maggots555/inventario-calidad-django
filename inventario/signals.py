from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Empleado
from .utils import sincronizar_grupo_empleado


@receiver(post_save, sender=Empleado)
def actualizar_grupo_al_cambiar_rol(sender, instance, created, **kwargs):
    """
    Signal que sincroniza el grupo del usuario cuando cambia el rol del empleado
    
    Se ejecuta automáticamente DESPUÉS de guardar un Empleado.
    Solo procesa empleados que YA tienen usuario asignado.
    """
    if instance.user:
        sincronizar_grupo_empleado(instance)
