"""
Formateadores personalizados para el sistema de logging.

EXPLICACIÓN: Este módulo soluciona el problema de emojis en logs de Windows.
Windows usa codificación cp1252 que no soporta emojis, causando errores.

SOLUCIÓN: Filtrar automáticamente emojis antes de escribir en consola/archivos.
"""

import logging
import re


class SafeFormatter(logging.Formatter):
    """
    Formateador que elimina emojis y caracteres Unicode problemáticos.
    
    ¿QUÉ HACE?
    - Detecta emojis y caracteres especiales en los mensajes de log
    - Los reemplaza por texto ASCII seguro (ejemplo: ✅ → [OK])
    - Permite que Windows muestre los logs sin errores
    
    ¿POR QUÉ ES NECESARIO?
    - Windows consola usa cp1252 (solo caracteres básicos)
    - Emojis como ✅, 🎁, ⚠️ causan UnicodeEncodeError
    - Archivos de log con UTF-8 pueden guardar emojis correctamente
    """
    
    # Patrones de emojis comunes y sus reemplazos
    EMOJI_REPLACEMENTS = {
        '✅': '[OK]',
        '✓': '[OK]',
        '❌': '[ERROR]',
        '⚠️': '[ALERTA]',
        '⚠': '[ALERTA]',
        '🎁': '[BENEFICIO]',
        '🔍': '[INFO]',
        '📊': '[ESTADISTICA]',
        '💾': '[GUARDADO]',
        '📧': '[EMAIL]',
        '🔔': '[NOTIFICACION]',
        '⏰': '[TIEMPO]',
        '📱': '[DISPOSITIVO]',
        '🔧': '[REPARACION]',
        '💰': '[DINERO]',
    }
    
    # Regex para detectar CUALQUIER emoji (rango Unicode)
    # Emojis están en rangos específicos de Unicode
    EMOJI_PATTERN = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # Emoticones
        "\U0001F300-\U0001F5FF"  # Símbolos y pictogramas
        "\U0001F680-\U0001F6FF"  # Transporte y símbolos de mapa
        "\U0001F1E0-\U0001F1FF"  # Banderas (iOS)
        "\U00002702-\U000027B0"  # Dingbats
        "\U000024C2-\U0001F251"  # Caracteres encerrados
        "\u2705"  # ✅ checkmark específico
        "\u274C"  # ❌ cruz específica
        "\u2713"  # ✓ check simple
        "\u26A0"  # ⚠ símbolo de advertencia
        "]+",
        flags=re.UNICODE
    )
    
    def format(self, record):
        """
        Formatea el registro de log eliminando emojis problemáticos.
        
        FLUJO:
        1. Formatea el mensaje original (fecha, nivel, mensaje)
        2. Reemplaza emojis conocidos por texto ASCII
        3. Elimina emojis desconocidos con regex
        4. Retorna mensaje seguro para Windows
        """
        # Formatear mensaje original
        formatted_message = super().format(record)
        
        # Reemplazar emojis conocidos por texto ASCII
        for emoji, replacement in self.EMOJI_REPLACEMENTS.items():
            formatted_message = formatted_message.replace(emoji, replacement)
        
        # Eliminar cualquier emoji restante
        formatted_message = self.EMOJI_PATTERN.sub('[EMOJI]', formatted_message)
        
        return formatted_message


class UTF8FileFormatter(logging.Formatter):
    """
    Formateador para archivos UTF-8 que PRESERVA emojis.
    
    ¿CUÁNDO USAR?
    - En archivos de log que usan encoding='utf-8'
    - Los emojis se guardan correctamente en el archivo
    - Puedes leer el archivo con un editor que soporte UTF-8
    
    VENTAJA:
    - Información completa y legible en archivos
    - Los emojis son útiles para escanear logs visualmente
    """
    pass  # No necesita modificaciones, solo identifica el propósito


class ConsoleFormatter(SafeFormatter):
    """
    Formateador específico para consola de Windows.
    
    Hereda de SafeFormatter para eliminar emojis automáticamente.
    Evita el error UnicodeEncodeError en cmd.exe y PowerShell.
    """
    pass
