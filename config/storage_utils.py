"""
Utilidades para Gestión de Almacenamiento con Disco Alterno
============================================================

Este módulo proporciona funcionalidades para manejar el almacenamiento de archivos
con soporte para disco alterno cuando el disco principal se queda sin espacio.

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
Este código detecta automáticamente cuándo el disco C: está lleno y cambia
a usar un disco alterno (como D:) para guardar nuevas imágenes.

Características:
- Verifica espacio disponible antes de guardar
- Cambia automáticamente al disco alterno si el principal está lleno
- Mantiene los archivos existentes donde están
- Configurable mediante variables de entorno
"""

import os
import shutil
from pathlib import Path
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from decouple import config


# ============================================================================
# CONFIGURACIÓN DE DISCOS
# ============================================================================

# Función para obtener BASE_DIR de forma segura (compatible con y sin Django inicializado)
def _get_base_dir():
    """
    Obtiene el directorio base del proyecto de forma segura.
    
    EXPLICACIÓN:
    Intenta obtener BASE_DIR de Django settings, pero si Django no está
    inicializado, calcula la ruta manualmente desde este archivo.
    """
    try:
        from django.conf import settings
        return Path(settings.BASE_DIR)
    except:
        # Si Django no está configurado, calcular BASE_DIR manualmente
        # Este archivo está en config/storage_utils.py, así que BASE_DIR es el padre de config/
        return Path(__file__).resolve().parent.parent

# Disco principal (configurable desde .env)
# En Linux: /mnt/django_storage/media (disco de 1TB)
# En Windows: D:/Media_Django/inventario-calidad-django/media
PRIMARY_STORAGE_PATH = config(
    'PRIMARY_MEDIA_ROOT',
    default=str(_get_base_dir() / 'media')
)
PRIMARY_STORAGE_PATH = Path(PRIMARY_STORAGE_PATH)

# Disco alterno (configurable desde .env)
# Fallback cuando el disco principal está lleno
ALTERNATE_STORAGE_PATH = config(
    'ALTERNATE_MEDIA_ROOT',
    default=str(_get_base_dir() / 'media')
)
ALTERNATE_STORAGE_PATH = Path(ALTERNATE_STORAGE_PATH)

# Umbral de espacio libre (en GB) para cambiar al disco alterno
# Si queda menos de este espacio, usa el disco alterno
MIN_FREE_SPACE_GB = config('MIN_FREE_SPACE_GB', default=50, cast=int)


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def get_disk_usage(path: Path) -> dict:
    """
    Obtiene información de uso del disco donde está la ruta especificada.
    
    EXPLICACIÓN:
    Esta función usa la librería shutil para obtener estadísticas del disco:
    - total: Capacidad total del disco
    - used: Espacio usado
    - free: Espacio libre disponible
    
    Args:
        path: Ruta del directorio a verificar
        
    Returns:
        dict con 'total', 'used', 'free' en bytes, y 'free_gb' en gigabytes
    """
    try:
        # Asegurarse de que la ruta existe
        path = Path(path)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        
        # Obtener estadísticas del disco
        usage = shutil.disk_usage(path)
        
        return {
            'total': usage.total,
            'used': usage.used,
            'free': usage.free,
            'free_gb': usage.free / (1024**3),  # Convertir a GB
            'path': str(path)
        }
    except Exception as e:
        print(f"Error al obtener uso del disco para {path}: {e}")
        return {
            'total': 0,
            'used': 0,
            'free': 0,
            'free_gb': 0,
            'path': str(path)
        }


def should_use_alternate_storage() -> bool:
    """
    Determina si se debe usar el disco alterno basándose en el espacio disponible.
    
    EXPLICACIÓN:
    Esta función verifica si el disco principal tiene suficiente espacio libre.
    Si el espacio libre es menor al umbral configurado (MIN_FREE_SPACE_GB),
    retorna True para indicar que se debe usar el disco alterno.
    
    Returns:
        bool: True si se debe usar el disco alterno, False si usar el principal
    """
    primary_usage = get_disk_usage(PRIMARY_STORAGE_PATH)
    free_gb = primary_usage['free_gb']
    
    print(f"[STORAGE CHECK] Espacio libre en disco principal: {free_gb:.2f} GB")
    print(f"[STORAGE CHECK] Umbral mínimo: {MIN_FREE_SPACE_GB} GB")
    
    if free_gb < MIN_FREE_SPACE_GB:
        print(f"[STORAGE CHECK] ⚠️ Espacio insuficiente! Usando disco alterno.")
        return True
    
    print(f"[STORAGE CHECK] ✅ Espacio suficiente. Usando disco principal.")
    return False


def get_active_storage_path() -> Path:
    """
    Retorna la ruta de almacenamiento activa (principal o alterno).
    
    EXPLICACIÓN:
    Esta función decide qué disco usar basándose en el espacio disponible.
    Es el punto central para determinar dónde se guardarán los nuevos archivos.
    
    Returns:
        Path: Ruta del directorio de almacenamiento activo
    """
    if should_use_alternate_storage():
        # Asegurar que el disco alterno existe
        ALTERNATE_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
        return ALTERNATE_STORAGE_PATH
    return PRIMARY_STORAGE_PATH


def get_storage_info() -> dict:
    """
    Obtiene información completa de ambos discos.
    
    EXPLICACIÓN:
    Esta función recopila estadísticas de ambos discos (principal y alterno)
    para que puedas monitorear el espacio disponible en cada uno.
    Útil para dashboards o reportes administrativos.
    
    Returns:
        dict con información de disco principal, alterno, y cuál está activo
    """
    primary = get_disk_usage(PRIMARY_STORAGE_PATH)
    alternate = get_disk_usage(ALTERNATE_STORAGE_PATH)
    active_path = get_active_storage_path()
    
    return {
        'primary': {
            'path': str(PRIMARY_STORAGE_PATH),
            'free_gb': primary['free_gb'],
            'total_gb': primary['total'] / (1024**3),
            'used_gb': primary['used'] / (1024**3),
            'is_active': active_path == PRIMARY_STORAGE_PATH
        },
        'alternate': {
            'path': str(ALTERNATE_STORAGE_PATH),
            'free_gb': alternate['free_gb'],
            'total_gb': alternate['total'] / (1024**3),
            'used_gb': alternate['used'] / (1024**3),
            'is_active': active_path == ALTERNATE_STORAGE_PATH
        },
        'min_free_space_gb': MIN_FREE_SPACE_GB
    }


# ============================================================================
# STORAGE PERSONALIZADO PARA DJANGO
# ============================================================================

class DynamicFileSystemStorage(FileSystemStorage):
    """
    Sistema de almacenamiento con soporte para disco alterno Y multi-país.
    
    EXPLICACIÓN:
    v1.0: Solo manejaba failover entre disco principal y alterno.
    v2.0: También organiza archivos por país usando subcarpetas.
    
    Ejemplo de rutas generadas:
    - México:    /mnt/django_storage/media/mexico/servicio_tecnico/imagenes/123/foto.jpg
    - Argentina: /mnt/django_storage/media/argentina/servicio_tecnico/imagenes/123/foto.jpg
    """
    
    def __init__(self, **kwargs):
        """
        Inicializa el storage con la ruta activa.
        
        NOTA IMPORTANTE (BUG CORREGIDO v2.0):
        Este __init__ se ejecuta UNA SOLA VEZ cuando Django arranca.
        NO ponemos lógica de país aquí porque el país cambia con cada request.
        La detección de país se hace en _save(), url() y path().
        """
        # Obtener la ruta activa basada en espacio disponible
        active_path = get_active_storage_path()
        
        # Configurar el storage con la ruta activa
        kwargs['location'] = active_path
        
        # Llamar al constructor de la clase padre (FileSystemStorage)
        super().__init__(**kwargs)
        
        print(f"[DYNAMIC STORAGE] Inicializado con ruta base: {active_path}")
    
    def _get_country_prefix(self) -> str:
        """
        Obtiene el prefijo de carpeta del país activo.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Esta función consulta el middleware (thread-locals) para saber
        qué país está activo y retorna su subcarpeta de media.
        
        Si no hay país activo (ej: manage.py, migrations), retorna
        el país por defecto para no romper nada.
        
        Returns:
            str: Subcarpeta del país (ej: 'mexico', 'argentina')
        """
        from config.middleware_pais import get_current_pais_config
        from config.paises_config import PAIS_DEFAULT, PAISES_CONFIG
        
        pais_config = get_current_pais_config()
        if pais_config:
            return pais_config.get('media_subdir', PAIS_DEFAULT)
        
        # Fallback: país por defecto
        return PAISES_CONFIG.get(PAIS_DEFAULT, {}).get('media_subdir', PAIS_DEFAULT)
    
    def _save(self, name, content):
        """
        Guarda un archivo con prefijo de país.
        
        CAMBIO v2.0:
        Antes: guardaba en /media/servicio_tecnico/imagenes/123/foto.jpg
        Ahora: guarda en /media/mexico/servicio_tecnico/imagenes/123/foto.jpg
        
        Args:
            name: Nombre del archivo a guardar
            content: Contenido del archivo
            
        Returns:
            str: Nombre del archivo guardado
        """
        # Verificar espacio y actualizar ruta si es necesario
        active_path = get_active_storage_path()
        
        # Si la ruta activa cambió, actualizar location
        if Path(self.location) != active_path:
            print(f"[DYNAMIC STORAGE] Cambiando ubicación de {self.location} a {active_path}")
            self.location = active_path
        
        # Agregar prefijo de país al nombre del archivo
        country_prefix = self._get_country_prefix()
        if not name.startswith(country_prefix + '/'):
            name = os.path.join(country_prefix, name)
        
        # Guardar el archivo usando el método del padre
        return super()._save(name, content)
    
    def url(self, name):
        """
        Genera la URL del archivo con prefijo de país.
        
        CAMBIO v2.0:
        Antes: /media/servicio_tecnico/imagenes/123/foto.jpg
        Ahora: /media/mexico/servicio_tecnico/imagenes/123/foto.jpg
        """
        country_prefix = self._get_country_prefix()
        if not name.startswith(country_prefix + '/'):
            name = os.path.join(country_prefix, name)
        return super().url(name)
    
    def path(self, name):
        """
        Genera la ruta absoluta del archivo con prefijo de país.
        
        CAMBIO v2.0:
        Antes: /mnt/django_storage/media/servicio_tecnico/imagenes/123/foto.jpg
        Ahora: /mnt/django_storage/media/mexico/servicio_tecnico/imagenes/123/foto.jpg
        """
        country_prefix = self._get_country_prefix()
        if not name.startswith(country_prefix + '/'):
            name = os.path.join(country_prefix, name)
        return super().path(name)


# ============================================================================
# FUNCIÓN AUXILIAR PARA UPLOAD_TO DINÁMICO
# ============================================================================

def dynamic_upload_to(base_path: str):
    """
    Genera una función upload_to que usa el disco activo dinámicamente.
    
    EXPLICACIÓN:
    Esta función crea otra función que Django usa en los campos ImageField/FileField.
    El campo 'upload_to' determina en qué subcarpeta se guarda el archivo.
    
    Esta función hace que la ruta se determine dinámicamente basándose en el espacio.
    
    Args:
        base_path: Ruta base relativa (ej: 'empleados/fotos/')
        
    Returns:
        function: Función que Django usará para determinar la ruta de guardado
        
    Ejemplo de uso en models.py:
        from config.storage_utils import dynamic_upload_to
        
        foto_perfil = models.ImageField(
            upload_to=dynamic_upload_to('empleados/fotos/%Y/%m/')
        )
    """
    def upload_to_func(instance, filename):
        """
        Función interna que determina la ruta completa del archivo.
        
        Args:
            instance: Instancia del modelo que está guardando el archivo
            filename: Nombre del archivo original
            
        Returns:
            str: Ruta completa donde se guardará el archivo
        """
        from datetime import datetime
        
        # Reemplazar patrones de fecha en la ruta
        now = datetime.now()
        path = base_path.replace('%Y', str(now.year))
        path = path.replace('%m', str(now.month).zfill(2))
        path = path.replace('%d', str(now.day).zfill(2))
        
        # Retornar la ruta con el nombre del archivo
        return os.path.join(path, filename)
    
    return upload_to_func
