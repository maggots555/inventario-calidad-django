# 📁 Imágenes para PDF RHITSO

## 🎯 Propósito
Esta carpeta contiene las imágenes necesarias para generar el PDF del formato RHITSO.

## 📂 Estructura de Carpetas

```
static/images/
├── logos/
│   ├── logo_sic.png       (Logo de SIC - izquierda del PDF)
│   └── logo_rhitso.png    (Logo de RHITSO - derecha del PDF)
└── rhitso/
    └── diagrama.png       (Diagrama de laptop para revisión de daños)
```

## 📋 Especificaciones de las Imágenes

### **Logo SIC** (`logos/logo_sic.png`)
- **Ubicación en PDF**: Esquina superior izquierda
- **Tamaño recomendado**: 200x100 px (se escalará automáticamente)
- **Formato**: PNG con transparencia (se convertirá automáticamente)
- **Uso**: Identificación de la empresa

### **Logo RHITSO** (`logos/logo_rhitso.png`)
- **Ubicación en PDF**: Esquina superior derecha
- **Tamaño recomendado**: 200x100 px (se escalará automáticamente)
- **Formato**: PNG con transparencia (se convertirá automáticamente)
- **Uso**: Identificación del servicio especializado

### **Diagrama de Laptop** (`rhitso/diagrama.png`)
- **Ubicación en PDF**: Sección "Revisión de Daños Externos"
- **Tamaño recomendado**: 800x400 px (se escalará proporcionalmente)
- **Formato**: PNG o JPG
- **Contenido**: Diagrama de una laptop vista desde arriba para marcar daños
- **Uso**: Documentar daños físicos del equipo

## 🔧 Conversión Automática
El sistema convierte automáticamente imágenes PNG con transparencia a JPG con fondo blanco para compatibilidad con ReportLab.

## ⚠️ IMPORTANTE
- **NO uses** espacios en los nombres de archivo
- **Mantén** los nombres exactos especificados arriba
- **Asegúrate** de que las imágenes existan antes de generar PDFs
- Si falta una imagen, el PDF mostrará un espacio en blanco con mensaje

## 📐 Dimensiones en el PDF
Las imágenes se escalan automáticamente manteniendo proporciones:
- **Logos**: 35x18 puntos en el PDF
- **Diagrama**: Hasta 180 puntos de ancho, altura proporcional

## 🎨 Sugerencias de Diseño
- Usa imágenes de buena calidad (300 DPI para impresión)
- Los logos deben tener fondo transparente
- El diagrama debe ser claro y legible
- Colores: Preferiblemente RGB (se convierten automáticamente a CMYK si es necesario)

## 📝 Notas para el Desarrollador
- Las rutas se construyen usando `settings.STATIC_ROOT` o `settings.STATICFILES_DIRS`
- La conversión de PNG a JPG se realiza con Pillow (PIL)
- Las imágenes se cargan con `ImageReader` de ReportLab
- Se maneja automáticamente el caso de imágenes faltantes
