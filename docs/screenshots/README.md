# 📸 Screenshots del Sistema

Esta carpeta contiene las capturas de pantalla del sistema para el README principal.

## 📋 Capturas Requeridas

### ✅ Screenshots Principales (6 imágenes)

1. **`dashboard_scorecard.png`**
   - Vista: `/scorecard/` (Dashboard principal)
   - Contenido: KPIs, gráficas de tendencias, métricas en tiempo real
   - Resolución recomendada: 1920x1080
   - **Estado**: ⏳ Pendiente

2. **`lista_ordenes.png`**
   - Vista: `/servicio/` (Lista de órdenes)
   - Contenido: Tabla con órdenes, badges de estados, filtros
   - Resolución recomendada: 1920x1080
   - **Estado**: ⏳ Pendiente

3. **`detalle_orden_rhitso.png`**
   - Vista: `/servicio/<id>/` con seguimiento RHITSO
   - Contenido: Timeline RHITSO, estados, incidencias
   - Resolución recomendada: 1920x1080
   - **Estado**: ⏳ Pendiente

4. **`form_incidencia.png`**
   - Vista: `/scorecard/incidencias/crear/`
   - Contenido: Formulario con secciones, autocompletado, alerta de reincidencias
   - Resolución recomendada: 1920x1080
   - **Estado**: ⏳ Pendiente

5. **`reportes_avanzados.png`**
   - Vista: `/scorecard/reportes/`
   - Contenido: Sistema de tabs, gráfica de Pareto, filtros
   - Resolución recomendada: 1920x1080
   - **Estado**: ⏳ Pendiente

6. **`notificaciones.png`**
   - Vista: `/scorecard/incidencias/<id>/` (sección de notificaciones)
   - Contenido: Historial timeline de notificaciones enviadas
   - Resolución recomendada: 1920x1080
   - **Estado**: ⏳ Pendiente

---

## 🎨 Guía para Tomar Screenshots

### Preparación del Sistema
```bash
# 1. Activar entorno virtual
venv\Scripts\activate

# 2. Poblar datos de ejemplo si es necesario
python scripts/poblado/poblar_sistema.py
python scripts/poblado/poblar_scorecard.py

# 3. Ejecutar el servidor
python manage.py runserver
```

### Configuración del Navegador
- **Navegador**: Chrome o Firefox (preferencia)
- **Resolución de ventana**: 1920x1080 (pantalla completa o F11)
- **Zoom**: 100% (sin zoom)
- **DevTools**: Cerrar (para captura limpia)

### Herramientas Recomendadas
- **Windows**: Win + Shift + S (Snipping Tool)
- **Alternativa**: ShareX (gratuito, con editor integrado)
- **Editor**: Paint, GIMP, Photoshop (para recortar/ajustar)

### Mejores Prácticas
1. **Datos reales pero ficticios**: No incluir información sensible
2. **Interfaz completa**: Mostrar navbar, breadcrumbs, footer
3. **Estado representativo**: Mostrar el sistema en uso activo (no vacío)
4. **Calidad**: Formato PNG para mejor calidad
5. **Peso**: Comprimir imágenes (<500KB por imagen)

### Pasos para Cada Screenshot

#### 1. Dashboard Score Card
```
1. Navegar a: http://127.0.0.1:8000/scorecard/
2. Asegurar que hay datos de ejemplo cargados
3. Esperar a que carguen todas las gráficas (Chart.js)
4. Capturar pantalla completa
5. Guardar como: dashboard_scorecard.png
```

#### 2. Lista de Órdenes
```
1. Navegar a: http://127.0.0.1:8000/servicio/
2. Filtrar por "Activas" para mostrar órdenes en proceso
3. Asegurar que se vean badges de colores de estados
4. Capturar pantalla completa
5. Guardar como: lista_ordenes.png
```

#### 3. Detalle Orden RHITSO
```
1. Navegar a una orden que tenga seguimiento RHITSO activo
2. Scroll para mostrar el timeline RHITSO completo
3. Asegurar que se vean las incidencias si existen
4. Capturar desde el título hasta el final del timeline
5. Guardar como: detalle_orden_rhitso.png
```

#### 4. Formulario Incidencia
```
1. Navegar a: http://127.0.0.1:8000/scorecard/incidencias/crear/
2. Llenar algunos campos para mostrar el formulario activo
3. Scroll para mostrar las secciones principales
4. Si es posible, provocar la alerta de reincidencias
5. Capturar pantalla completa
6. Guardar como: form_incidencia.png
```

#### 5. Reportes Avanzados
```
1. Navegar a: http://127.0.0.1:8000/scorecard/reportes/
2. Dejar el tab "Resumen Ejecutivo" activo
3. Esperar a que carguen todas las gráficas
4. Asegurar que el gráfico de Pareto sea visible
5. Capturar pantalla completa
6. Guardar como: reportes_avanzados.png
```

#### 6. Notificaciones
```
1. Navegar al detalle de una incidencia con notificaciones enviadas
2. Scroll hasta la sección "Historial de Notificaciones"
3. Asegurar que se vean al menos 2-3 notificaciones en el timeline
4. Capturar desde el título de la sección hasta el final
5. Guardar como: notificaciones.png
```

---

## 🖼️ Formato de Imágenes

### Especificaciones Técnicas
- **Formato**: PNG (preferido) o JPG
- **Resolución**: 1920x1080 o 1600x900 mínimo
- **Peso máximo**: 500KB por imagen (comprimir si es necesario)
- **Nombrado**: Usar snake_case (ej: `dashboard_scorecard.png`)

### Compresión de Imágenes
Si las imágenes son muy pesadas (>500KB):

**Opción 1 - Online:**
- [TinyPNG](https://tinypng.com/) - Compresión inteligente
- [Compressor.io](https://compressor.io/) - Alternativa

**Opción 2 - Python:**
```python
# Usar el script de compresión del proyecto
python scripts/testing/test_compresion_imagenes.py
```

---

## 📤 Subir Screenshots al Repositorio

Una vez que tengas las 6 imágenes:

```bash
# 1. Copiar imágenes a esta carpeta
# docs/screenshots/

# 2. Agregar al repositorio
git add docs/screenshots/

# 3. Commit
git commit -m "docs: Agregar screenshots del sistema para README

- Agregar dashboard_scorecard.png (Dashboard principal con KPIs)
- Agregar lista_ordenes.png (Gestión de órdenes)
- Agregar detalle_orden_rhitso.png (Seguimiento RHITSO)
- Agregar form_incidencia.png (Formulario de incidencias)
- Agregar reportes_avanzados.png (Reportes con 7 tabs)
- Agregar notificaciones.png (Historial de notificaciones)

Las imágenes mejoran la presentación del README y facilitan
la comprensión del sistema para nuevos usuarios/desarrolladores."

# 4. Push a GitHub
git push
```

---

## ✅ Checklist de Verificación

Antes de subir las imágenes, verificar:

- [ ] Las 6 imágenes están en formato PNG
- [ ] Cada imagen pesa menos de 500KB
- [ ] Los nombres de archivo coinciden con los del README.md
- [ ] No hay información sensible visible (emails reales, datos de clientes)
- [ ] Las imágenes se ven nítidas y profesionales
- [ ] La interfaz está en español (consistente con el sistema)
- [ ] Se muestran datos de ejemplo suficientes (no pantallas vacías)

---

## 🎯 Resultado Esperado

Al completar este proceso, el README.md del repositorio mostrará:
- ✅ 6 screenshots profesionales del sistema
- ✅ Mejor presentación visual en GitHub
- ✅ Facilita onboarding de nuevos desarrolladores
- ✅ Demuestra la complejidad y calidad del sistema
- ✅ Ayuda en presentaciones a stakeholders

---

**Última actualización**: Octubre 14, 2025
