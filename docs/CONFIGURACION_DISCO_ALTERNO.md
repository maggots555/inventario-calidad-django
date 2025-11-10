# 💾 Guía de Configuración de Disco Alterno para Almacenamiento de Imágenes

## 📋 Índice
1. [¿Qué es el Disco Alterno?](#qué-es-el-disco-alterno)
2. [¿Cómo Funciona?](#cómo-funciona)
3. [Configuración Paso a Paso](#configuración-paso-a-paso)
4. [Ejemplo de Uso en Modelos](#ejemplo-de-uso-en-modelos)
5. [Monitoreo del Almacenamiento](#monitoreo-del-almacenamiento)
6. [Preguntas Frecuentes](#preguntas-frecuentes)

---

## 🎯 ¿Qué es el Disco Alterno?

El **disco alterno** es una solución automática para evitar que tu aplicación Django deje de funcionar cuando el disco principal (C:) se queda sin espacio.

### Problema que Resuelve:
- ❌ Disco C: lleno = aplicación deja de guardar imágenes
- ❌ Errores al subir evidencias, fotos de perfil, etc.
- ❌ Sistema inaccesible por falta de espacio

### Solución:
- ✅ Detecta automáticamente cuando hay poco espacio
- ✅ Cambia al disco alterno (D:, E:, etc.) sin intervención manual
- ✅ Continúa funcionando sin interrupciones

---

## ⚙️ ¿Cómo Funciona?

### Flujo Automático:

```
1. Usuario sube una imagen
   ↓
2. Sistema verifica espacio en disco principal
   ↓
3. ¿Hay más de 5 GB libres?
   ├── SÍ → Guarda en disco principal (C:/media/)
   └── NO → Guarda en disco alterno (D:/Media_Django/)
```

### Ubicaciones Actuales de Archivos:

```
📁 Disco Principal (C:)
└── c:\Users\DELL\Proyecto_Django\inventario-calidad-django\media\
    ├── empleados/fotos/              # Fotos de perfil
    ├── scorecard/evidencias/YYYY/MM/ # Evidencias de calidad
    └── servicio_tecnico/
        ├── imagenes/YYYY/MM/          # Imágenes comprimidas
        └── imagenes_originales/YYYY/MM/ # Imágenes originales

📁 Disco Alterno (D:) - SE ACTIVA CUANDO C: ESTÁ LLENO
└── D:\Media_Django\inventario-calidad-django\media\
    ├── empleados/fotos/
    ├── scorecard/evidencias/YYYY/MM/
    └── servicio_tecnico/
        ├── imagenes/YYYY/MM/
        └── imagenes_originales/YYYY/MM/
```

---

## 🛠️ Configuración Paso a Paso

### **Paso 1: Configurar Variables de Entorno**

Edita tu archivo `.env` (o crea uno desde `.env.example`):

```bash
# ============================================================================
# CONFIGURACIÓN DE ALMACENAMIENTO CON DISCO ALTERNO
# ============================================================================

# Ruta del disco alterno (puedes usar cualquier disco con espacio)
# Ejemplos:
#   D:/Media_Django/inventario-calidad-django/media
#   E:/Django_Media/
#   \\servidor\compartido\media\
ALTERNATE_STORAGE_PATH=D:/Media_Django/inventario-calidad-django/media

# Espacio mínimo (en GB) antes de cambiar al disco alterno
# Si el disco principal tiene menos de esto, usa el alterno
MIN_FREE_SPACE_GB=5
```

**IMPORTANTE**: Usa barras diagonales (`/`) o doble barra invertida (`\\`), no una sola `\`.

### **Paso 2: Crear el Directorio del Disco Alterno**

El sistema crea automáticamente las carpetas, pero puedes crearlas manualmente:

**Opción A - Manual (Windows):**
```powershell
# Crear carpeta en disco D:
New-Item -Path "D:\Media_Django\inventario-calidad-django\media" -ItemType Directory -Force
```

**Opción B - Automático:**
El sistema crea las carpetas automáticamente cuando se sube la primera imagen.

### **Paso 3: Verificar Permisos**

Asegúrate de que la aplicación tiene permisos de escritura en el disco alterno:

```powershell
# Verificar permisos (debe mostrar la carpeta)
Get-Acl "D:\Media_Django"
```

### **Paso 4: Probar la Configuración**

1. **Accede al Monitor de Almacenamiento:**
   ```
   http://localhost:8000/admin/storage-monitor/
   ```

2. **Verifica que ambos discos aparezcan:**
   - Disco Principal: debe mostrar espacio actual
   - Disco Alterno: debe mostrar ruta configurada

3. **Sube una imagen de prueba:**
   - Ve a cualquier módulo (Score Card, Servicio Técnico, Empleados)
   - Sube una imagen
   - Verifica que se guardó correctamente

---

## 💻 Ejemplo de Uso en Modelos

Si quieres usar el almacenamiento dinámico en tus propios modelos:

### **Opción 1: Usando DynamicFileSystemStorage (Recomendado)**

```python
# En tu models.py
from django.db import models
from config.storage_utils import DynamicFileSystemStorage

class MiModelo(models.Model):
    nombre = models.CharField(max_length=100)
    
    # Campo de imagen con almacenamiento dinámico
    imagen = models.ImageField(
        upload_to='mi_app/imagenes/%Y/%m/',
        storage=DynamicFileSystemStorage(),  # ← Esto activa el disco alterno
        help_text="Imagen que se guarda automáticamente en el disco con espacio"
    )
```

### **Opción 2: Usando upload_to dinámico**

```python
# En tu models.py
from django.db import models
from config.storage_utils import dynamic_upload_to

class MiModelo(models.Model):
    nombre = models.CharField(max_length=100)
    
    # Campo de imagen con upload_to dinámico
    imagen = models.ImageField(
        upload_to=dynamic_upload_to('mi_app/imagenes/%Y/%m/'),  # ← Genera ruta dinámica
        help_text="Imagen con ruta calculada dinámicamente"
    )
```

### **¿Cuál Usar?**

| Método | Ventajas | Cuándo Usarlo |
|--------|----------|--------------|
| `DynamicFileSystemStorage` | ✅ Más control<br>✅ Verifica espacio al guardar | Para modelos críticos |
| `dynamic_upload_to` | ✅ Más simple<br>✅ Compatible con storage por defecto | Para la mayoría de casos |

---

## 📊 Monitoreo del Almacenamiento

### **Vista de Administración**

Accede al monitor en:
```
http://localhost:8000/admin/storage-monitor/
```

**Funcionalidades:**
- 📈 Gráficas de espacio usado/libre
- 🔄 Auto-refresh cada 30 segundos
- ⚠️ Alertas cuando el espacio es bajo
- 📍 Indica qué disco está activo

### **Vista Programática**

Si necesitas obtener información de almacenamiento en tu código:

```python
from config.storage_utils import get_storage_info

# Obtener información de ambos discos
storage_info = get_storage_info()

print(f"Disco principal: {storage_info['primary']['free_gb']:.2f} GB libres")
print(f"Disco alterno: {storage_info['alternate']['free_gb']:.2f} GB libres")
print(f"Disco activo: {'Principal' if storage_info['primary']['is_active'] else 'Alterno'}")
```

---

## 🌐 Sistema de Múltiples Ubicaciones (Archivos Existentes + Nuevos)

### **El Problema**

Cuando implementas el disco alterno, surge un desafío:
- ✅ **Archivos NUEVOS**: Se guardan correctamente en disco D:
- ❌ **Archivos EXISTENTES**: Permanecen en disco C: y Django no los encuentra

### **La Solución Implementada**

El sistema ahora busca archivos en **AMBAS ubicaciones** automáticamente:

```
Usuario solicita: /media/scorecard/evidencias/2025/11/imagen.jpg
                           ↓
        ┌──────────────────────────────────────────┐
        │  Vista: serve_media_from_multiple_locations  │
        └──────────────────────────────────────────┘
                           ↓
        ┌─────────────────────────────────────────┐
        │  1. Buscar en Disco Alterno (D:)        │
        │     D:\Media_Django\...\imagen.jpg      │
        └─────────────────────────────────────────┘
                           ↓
                    ¿Encontrado?
                    ↙         ↘
                  SÍ          NO
                   ↓           ↓
            Devolver     ┌──────────────────────┐
            archivo      │ 2. Buscar en Disco   │
                         │    Principal (C:)    │
                         └──────────────────────┘
                                  ↓
                            ¿Encontrado?
                            ↙         ↘
                          SÍ          NO
                           ↓           ↓
                    Devolver      Error 404
                    archivo
```

### **Archivos Modificados**

**1. `config/media_views.py`** (NUEVO)
- Vista personalizada `serve_media_from_multiple_locations()`
- Busca archivos en orden: Disco D: → Disco C:
- Implementa caché HTTP para mejor rendimiento

**2. `config/urls.py`** (MODIFICADO)
- Configurado para usar la vista personalizada
- Solo en desarrollo (DEBUG=True)
- Patrón: `^media/(?P<path>.*)$`

**3. `config/settings.py`** (MODIFICADO)
- Configuración `STORAGES` para Django 5.x
- Storage por defecto: `DynamicFileSystemStorage`

### **Cómo Funciona**

**Para Nuevos Archivos:**
```python
# Al subir una imagen, DynamicFileSystemStorage decide dónde guardar
usuario.foto_perfil = imagen_subida  # Se guarda en disco con más espacio
```

**Para Servir Archivos:**
```python
# Django busca el archivo automáticamente
GET /media/empleados/fotos/juan.jpg
  → Busca en D:\Media_Django\...\empleados\fotos\juan.jpg (PRIMERO)
  → Si no existe, busca en C:\...\media\empleados\fotos\juan.jpg
  → Retorna el primero que encuentre
```

### **Logs de Debugging**

En la consola del servidor verás mensajes informativos:

```
[MEDIA SERVE] ✅ Archivo encontrado: D:\Media_Django\...\imagen_nueva.jpg
[MEDIA SERVE] ✅ Archivo encontrado: C:\...\media\imagen_antigua.jpg
[MEDIA SERVE] ❌ Archivo no encontrado: imagen_inexistente.jpg
```

### **Ventajas de Esta Solución**

✅ **Transparente**: Los usuarios no notan ninguna diferencia  
✅ **Automática**: No requiere intervención manual  
✅ **Compatible**: Funciona con todos los archivos existentes  
✅ **Eficiente**: Usa caché HTTP para mejor rendimiento  
✅ **Escalable**: Fácil agregar más ubicaciones si es necesario  

---

## ❓ Preguntas Frecuentes

### **1. ¿Qué pasa con las imágenes que ya están guardadas?**
✅ Se quedan donde están. Solo las **nuevas** imágenes se guardan en el disco alterno.

### **2. ¿Puedo mover manualmente las imágenes al disco alterno?**
✅ Sí, puedes copiar la carpeta `media/` completa al disco alterno:

```powershell
# Copiar todo al disco D:
Copy-Item -Path "C:\Users\DELL\Proyecto_Django\inventario-calidad-django\media\*" `
          -Destination "D:\Media_Django\inventario-calidad-django\media\" `
          -Recurse -Force
```

Luego actualiza `MEDIA_ROOT` en `settings.py` para que apunte al disco D:.

### **3. ¿Qué pasa si el disco alterno también se llena?**
⚠️ El sistema intentará guardar en el disco activo y mostrará un error si no hay espacio.

**Solución:** Aumenta el espacio del disco o configura un tercer disco (requiere modificar `storage_utils.py`).

### **4. ¿Funciona con rutas de red (NAS, servidores)?**
✅ Sí, puedes usar rutas UNC:

```bash
ALTERNATE_STORAGE_PATH=\\\\servidor\\compartido\\media
```

**IMPORTANTE:** Asegúrate de tener permisos de escritura en la ruta de red.

### **5. ¿Puedo cambiar el umbral de 5 GB?**
✅ Sí, edita `.env`:

```bash
# Cambiar a 10 GB
MIN_FREE_SPACE_GB=10

# O 1 GB para pruebas
MIN_FREE_SPACE_GB=1
```

### **6. ¿Cómo verifico qué disco se está usando actualmente?**
Accede al monitor: http://localhost:8000/admin/storage-monitor/

O revisa los logs del servidor (terminal) cuando subes una imagen:
```
[STORAGE CHECK] Espacio libre en disco principal: 3.45 GB
[STORAGE CHECK] Umbral mínimo: 5 GB
[STORAGE CHECK] ⚠️ Espacio insuficiente! Usando disco alterno.
```

### **7. ¿Afecta el rendimiento?**
✅ **No significativamente.** La verificación de espacio es muy rápida (~1ms).

El impacto es mínimo comparado con el beneficio de evitar errores por falta de espacio.

### **8. ¿Puedo desactivar el disco alterno?**
✅ Sí, simplemente no configures `ALTERNATE_STORAGE_PATH` o déjalo vacío:

```bash
ALTERNATE_STORAGE_PATH=
```

El sistema solo usará el disco principal.

---

## � Configuración para Producción

⚠️ **IMPORTANTE**: La vista `serve_media_from_multiple_locations` solo funciona en desarrollo (DEBUG=True).

En producción, debes configurar tu servidor web (nginx/apache) para servir ambas ubicaciones:

### **Nginx (Recomendado)**

```nginx
server {
    listen 80;
    server_name tudominio.com;
    
    # Servir archivos media desde múltiples ubicaciones
    location /media/ {
        # Intentar primero en disco alterno, luego disco principal
        alias /media/disk_d/;
        try_files $uri @fallback_media;
    }
    
    location @fallback_media {
        alias /media/disk_c/;
    }
    
    # Proxy para Django
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### **Apache**

```apache
<VirtualHost *:80>
    ServerName tudominio.com
    
    # Intentar servir desde disco D:, si no existe, buscar en C:
    Alias /media/ "/media/disk_d/"
    <Directory "/media/disk_d/">
        Require all granted
        Options -Indexes +FollowSymLinks
    </Directory>
    
    # Fallback a disco C:
    AliasMatch /media/(.*)$ "/media/disk_c/$1"
    <Directory "/media/disk_c/">
        Require all granted
        Options -Indexes +FollowSymLinks
    </Directory>
    
    # Proxy para Django
    ProxyPass /media/ !
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/
</VirtualHost>
```

---

## �🔧 Solución de Problemas

### **Problema: Error "No module named 'config.storage_utils'"**

**Causa:** El archivo `storage_utils.py` no está en la carpeta `config/`.

**Solución:**
```powershell
# Verificar que existe
Test-Path "config\storage_utils.py"  # Debe retornar True
```

### **Problema: "Permission denied" al guardar en disco alterno**

**Causa:** Falta de permisos de escritura.

**Solución (Windows):**
```powershell
# Dar permisos completos a la carpeta
icacls "D:\Media_Django" /grant Users:F /T
```

### **Problema: Las imágenes se guardan en el principal aunque esté lleno**

**Causa:** Las variables de entorno no se cargaron.

**Solución:**
1. Verifica que `.env` existe en la raíz del proyecto
2. Reinicia el servidor Django
3. Verifica la configuración en el monitor de almacenamiento

---

## 📚 Recursos Adicionales

- **Archivo de utilidades:** `config/storage_utils.py`
- **Template del monitor:** `templates/admin_storage_monitor.html`
- **Vista del monitor:** `inventario/views.py` → `admin_storage_monitor()`
- **Configuración:** `.env.example` → Sección de almacenamiento

---

## 🎓 Resumen para Principiantes

### ¿Qué hace este sistema?

1. **Vigila** el espacio en tu disco C: cada vez que subes una imagen
2. **Decide** automáticamente si hay suficiente espacio (más de 5 GB)
3. **Cambia** al disco alterno (D:) si C: está lleno
4. **Continúa** funcionando sin errores

### Beneficios:

- ✅ **Evita errores** por disco lleno
- ✅ **Automático** - no requiere intervención manual
- ✅ **Transparente** - el usuario no nota la diferencia
- ✅ **Monitoreable** - puedes ver el estado en tiempo real
- ✅ **Configurable** - ajusta el umbral según tus necesidades

### Configuración Mínima:

Solo necesitas 2 líneas en `.env`:

```bash
ALTERNATE_STORAGE_PATH=D:/Media_Django/inventario-calidad-django/media
MIN_FREE_SPACE_GB=5
```

¡Y listo! El sistema maneja todo automáticamente. 🎉

---

**Documentación creada:** Noviembre 2025  
**Versión:** 1.0  
**Proyecto:** Inventario Calidad Django
