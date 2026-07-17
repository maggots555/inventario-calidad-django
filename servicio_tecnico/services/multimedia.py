"""
Compresión y guardado de imágenes/videos de evidencia (Fase 5 modularización).

EXPLICACIÓN PARA PRINCIPIANTES:
Estas funciones NO son vistas HTTP: las llama detalle_orden al subir archivos.
Antes vivían en views.py (~600 líneas). Las sacamos a services/ para:
  1) No mezclar lógica de archivos con el monolito de vistas
  2) Que detalle_orden (y eventualmente Celery) las importen sin ciclo

Efectos secundarios:
  - Escriben archivos en media/ (disco dinámico)
  - Crean ImagenOrden / VideoOrden (el save del modelo registra historial)
"""

import os
import logging

from PIL import Image, ImageOps

from servicio_tecnico.models import ImagenOrden, VideoOrden

logger = logging.getLogger(__name__)


# ============================================================================
# FUNCIÓN AUXILIAR: Comprimir y Guardar Imagen
# ============================================================================

def comprimir_y_guardar_imagen(orden, imagen_file, tipo, descripcion, empleado):
    """
    Comprime y guarda una imagen con la estructura de carpetas solicitada.

    Args:
        orden: OrdenServicio a la que pertenece la imagen
        imagen_file: Archivo de imagen subido
        tipo: Tipo de imagen (ingreso, egreso, etc.)
        descripcion: Descripción opcional
        empleado: Empleado que sube la imagen
    
    Returns:
        ImagenOrden: Registro de imagen creado con ambas versiones
    """
    from django.core.files.base import ContentFile
    from io import BytesIO
    import time
    
    # Obtener número de serie del equipo
    service_tag = orden.detalle_equipo.numero_serie
    
    # Crear timestamp único
    timestamp = int(time.time() * 1000)  # Milisegundos
    
    # Extensión del archivo original
    extension = os.path.splitext(imagen_file.name)[1].lower()
    if not extension:
        extension = '.jpg'
    
    # Nombre del archivo: {tipo}_{timestamp}{extension}
    nombre_archivo = f"{tipo}_{timestamp}{extension}"
    nombre_archivo_original = f"{tipo}_{timestamp}_original{extension}"
    
    # Abrir imagen con Pillow
    img_original = Image.open(imagen_file)
    
    # Corregir rotación EXIF antes de cualquier procesamiento.
    # Las fotos tomadas con celular incluyen un metadato EXIF que indica cómo
    # rotarlas al mostrarlas. Sin esta corrección, Pillow guarda los píxeles
    # en la orientación cruda del sensor (puede salir girada 90°).
    # exif_transpose() aplica esa rotación y elimina el metadato para que
    # cualquier visor (WhatsApp, Windows, etc.) la vea siempre derecha.
    img_original = ImageOps.exif_transpose(img_original)
    
    # Convertir a RGB si es necesario (para JPG)
    if img_original.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img_original.size, (255, 255, 255))
        background.paste(img_original, mask=img_original.split()[-1] if img_original.mode == 'RGBA' else None)
        img_original = background
    
    # ========================================================================
    # GUARDAR IMAGEN ORIGINAL (SIN COMPRIMIR - ALTA RESOLUCIÓN)
    # ========================================================================
    buffer_original = BytesIO()
    img_original.save(buffer_original, format='JPEG', quality=95, optimize=False)
    buffer_original.seek(0)
    
    # ========================================================================
    # CREAR VERSIÓN COMPRIMIDA PARA GALERÍA
    # ========================================================================
    img_comprimida = img_original.copy()
    max_size = (1920, 1920)
    img_comprimida.thumbnail(max_size, Image.Resampling.LANCZOS)
    
    # Guardar versión comprimida en buffer
    buffer_comprimido = BytesIO()
    img_comprimida.save(buffer_comprimido, format='JPEG', quality=85, optimize=True)
    buffer_comprimido.seek(0)
    
    # ========================================================================
    # CREAR REGISTRO DE IMAGENORDEN
    # ========================================================================
    imagen_orden = ImagenOrden(
        orden=orden,
        tipo=tipo,
        descripcion=descripcion,
        subido_por=empleado
    )
    
    # Guardar archivo comprimido (para galería)
    imagen_orden.imagen.save(nombre_archivo, ContentFile(buffer_comprimido.getvalue()), save=False)
    
    # Guardar archivo original (para descargas)
    imagen_orden.imagen_original.save(nombre_archivo_original, ContentFile(buffer_original.getvalue()), save=False)
    
    # Guardar el objeto (esto dispara el save() del modelo que crea el historial)
    imagen_orden.save()
    
    return imagen_orden


# ============================================================================
# FUNCIÓN AUXILIAR: Comprimir y Guardar Video con FFmpeg
# ============================================================================

def comprimir_y_guardar_video(orden, video_file, tipo, descripcion, empleado):
    """
    Comprime un video usando FFmpeg y guarda el resultado junto a un thumbnail.

    EXPLICACIÓN PARA PRINCIPIANTES:
    - Recibe el video crudo del formulario (puede ser .mp4, .mov, .avi, etc.)
    - Lo comprime a H.264/AAC con FFmpeg al estándar acordado (máx 60 s, CRF 28)
    - Extrae un thumbnail del segundo 1 del video comprimido
    - Guarda el VideoOrden en la base de datos (el save() del modelo crea historial)

    Args:
        orden: OrdenServicio a la que pertenece el video
        video_file: Archivo de video subido (InMemoryUploadedFile o TemporaryUploadedFile)
        tipo: Tipo de video (ingreso, diagnostico, reparacion, egreso, autorizacion, packing)
        descripcion: Descripción opcional del video
        empleado: Empleado que sube el video

    Returns:
        VideoOrden: Registro creado con video comprimido y thumbnail
    
    Raises:
        RuntimeError: Si FFmpeg no está disponible o falla la compresión
    """
    import subprocess
    import tempfile
    import time
    from django.core.files.base import ContentFile
    from pathlib import Path as PPath

    # Número de serie del equipo para logging
    service_tag = orden.detalle_equipo.numero_serie

    # Timestamp único para nombres de archivo
    timestamp = int(time.time() * 1000)

    # Extensión de entrada (preservar para que FFmpeg detecte el codec de entrada)
    extension_entrada = os.path.splitext(video_file.name)[1].lower()
    if not extension_entrada:
        extension_entrada = '.mp4'

    # Nombre base del archivo de salida (siempre .mp4)
    nombre_video = f"{tipo}_{timestamp}.mp4"
    nombre_thumb = f"{tipo}_{timestamp}_thumb.jpg"

    # =========================================================================
    # ESCRIBIR ARCHIVO TEMPORAL DE ENTRADA
    # =========================================================================
    with tempfile.NamedTemporaryFile(suffix=extension_entrada, delete=False) as tmp_in:
        for chunk in video_file.chunks():
            tmp_in.write(chunk)
        tmp_in_path = tmp_in.name

    tmp_out_path = tmp_in_path + '_out.mp4'
    tmp_thumb_path = tmp_in_path + '_thumb.jpg'

    # Resolver ruta absoluta de ffmpeg igual que en ollama_client.py:
    # Gunicorn corre con un PATH reducido que puede no incluir el directorio
    # de ffmpeg. shutil.which() busca en el PATH del proceso; si no lo encuentra,
    # cae al fallback de ruta absoluta conocida en producción.
    import shutil
    ffmpeg_bin = shutil.which('ffmpeg') or '/usr/bin/ffmpeg'

    try:
        # =====================================================================
        # COMPRIMIR CON FFMPEG
        # Comando acordado: H.264 + AAC, máx 1080p, CRF 23, fast
        # El límite de duración es 600 s (10 min) como red de seguridad contra
        # inputs maliciosos. El límite real de UX es 90 MB de tamaño de archivo,
        # controlado en el frontend (auto-stop de MediaRecorder) y en el form
        # de validación Django (forms.py).
        # =====================================================================
        cmd_compress = [
            ffmpeg_bin,
            '-protocol_whitelist', 'file,pipe,fd',
            '-i', tmp_in_path,
            '-vf', (
                "scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease,"
                "scale=trunc(iw/2)*2:trunc(ih/2)*2,"
                "unsharp=5:5:1.0:5:5:0.0"
            ),
            '-c:v', 'libx264',
            '-crf', '23',
            '-preset', 'fast',
            '-pix_fmt', 'yuv420p',
            '-profile:v', 'main',
            '-level', '4.0',
            '-c:a', 'aac',
            '-b:a', '128k',    # Subido de 96k: evita distorsión al recodificar Opus→AAC
            '-ar', '48000',    # Sample rate explícito — previene variación entre dispositivos
            '-map', '0:v:0',
            '-map', '0:a:0?',
            '-movflags', '+faststart',
            '-t', '600',  # Safety-limit: 10 min máx (el límite real de UX es 90 MB en el cliente)
            '-map_metadata', '-1',
            '-y',
            tmp_out_path,
        ]
        resultado = subprocess.run(
            cmd_compress,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutos máximo
        )
        if resultado.returncode != 0:
            raise RuntimeError(
                f'FFmpeg falló (código {resultado.returncode}): {resultado.stderr[-500:]}'
            )

        # =====================================================================
        # EXTRAER THUMBNAIL DEL SEGUNDO 1
        # =====================================================================
        cmd_thumb = [
            ffmpeg_bin,
            '-protocol_whitelist', 'file,pipe,fd',
            '-i', tmp_out_path,
            '-ss', '00:00:01',
            '-vframes', '1',
            '-q:v', '3',
            '-y',
            tmp_thumb_path,
        ]
        subprocess.run(cmd_thumb, capture_output=True, timeout=30)
        # Si el thumbnail falla no es crítico; VideoOrden.thumbnail puede quedar vacío

        # =====================================================================
        # MEDIR DURACIÓN CON FFPROBE (antes de crear el registro)
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # ffprobe lee los metadatos del video comprimido para obtener su duración
        # exacta en segundos. Si falla por cualquier motivo, simplemente guarda
        # None — no es un error crítico.
        # =====================================================================
        duracion_segundos = None
        try:
            cmd_probe = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                tmp_out_path,
            ]
            resultado_probe = subprocess.run(
                cmd_probe, capture_output=True, text=True, timeout=10
            )
            if resultado_probe.returncode == 0:
                duracion_segundos = int(float(resultado_probe.stdout.strip()))
        except Exception:
            pass  # No crítico — el video se guarda igualmente sin duración

        # =====================================================================
        # CREAR REGISTRO VideoOrden
        # =====================================================================
        tamano_original_mb = round(video_file.size / (1024 * 1024), 2)
        tamano_final_mb    = round(os.path.getsize(tmp_out_path) / (1024 * 1024), 2)

        video_orden = VideoOrden(
            orden=orden,
            tipo=tipo,
            descripcion=descripcion,
            subido_por=empleado,
            tamano_original_mb=tamano_original_mb,
            tamano_final_mb=tamano_final_mb,
            duracion_segundos=duracion_segundos,
        )

        # Guardar video comprimido usando File() para no cargar todo en RAM
        from django.core.files import File
        with open(tmp_out_path, 'rb') as f_video:
            video_orden.video.save(nombre_video, File(f_video), save=False)

        # Guardar thumbnail (si se generó) — es pequeño, ContentFile está bien
        if PPath(tmp_thumb_path).exists():
            with open(tmp_thumb_path, 'rb') as f_thumb:
                video_orden.thumbnail.save(nombre_thumb, ContentFile(f_thumb.read()), save=False)

        # save() del modelo registra el historial automáticamente
        video_orden.save()

        return video_orden

    finally:
        # Limpiar archivos temporales siempre, aunque haya error
        for tmp_path in [tmp_in_path, tmp_out_path, tmp_thumb_path]:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
