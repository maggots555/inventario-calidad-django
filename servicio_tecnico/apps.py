from django.apps import AppConfig


class ServicioTecnicoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'servicio_tecnico'
    
    def ready(self):
        """
        Método que se ejecuta cuando Django inicia la aplicación.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        ================================
        El método ready() se ejecuta UNA SOLA VEZ cuando Django inicia.
        Es el lugar perfecto para registrar signals (señales/detectores).
        
        ¿Qué son los signals?
            Son detectores automáticos que observan cuando algo cambia en
            la base de datos y ejecutan código automáticamente.
        
        ¿Por qué importarlos aquí?
            Django necesita saber que existen los signals para que funcionen.
            Si no los importamos, Django no los ejecutará aunque estén definidos.
        
        El import dentro de ready():
            Importamos aquí (no al inicio del archivo) para evitar problemas
            de "importación circular" (cuando dos archivos se importan mutuamente
            y Django se confunde sobre cuál cargar primero).
        """
        # Importar signals para que Django los registre
        # El simple hecho de importar el módulo signals.py hace que los
        # decoradores @receiver registren las funciones
        import servicio_tecnico.signals
