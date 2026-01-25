# 📋 INSTRUCCIONES PARA PROBAR EL DASHBOARD DE DISTRIBUCIÓN MULTI-SUCURSAL

## ✅ Estado Actual

**TODO EL CÓDIGO ESTÁ IMPLEMENTADO Y LISTO**. Solo falta probarlo en el navegador.

### Archivos Creados/Modificados:
1. ✅ `almacen/views.py` - 2 funciones nuevas agregadas
2. ✅ `almacen/urls.py` - Ruta configurada
3. ✅ `almacen/templates/almacen/dashboard_distribucion_sucursales.html` - Template completo
4. ✅ `static/ts/dashboard-distribucion-sucursales.ts` - TypeScript compilado
5. ✅ `static/js/dashboard-distribucion-sucursales.js` - JavaScript generado
6. ✅ `templates/base.html` - Enlace en menú agregado

---

## 🚀 PASOS PARA PROBAR

### 1. Iniciar el Servidor de Desarrollo

Abre una terminal y ejecuta:

```bash
cd /home/maggots/Django_proyect/inventario-calidad-django
source venv/bin/activate
python manage.py runserver
```

Deberías ver algo como:
```
System check identified no issues (0 silenced).
January 24, 2026 - 20:00:00
Django version 5.2.5, using settings 'config.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

### 2. Acceder al Dashboard

Abre tu navegador y ve a:

```
http://127.0.0.1:8000/almacen/dashboard/distribucion-sucursales/
```

**O** navega desde el menú:
1. Inicia sesión con tu usuario
2. Ve al menú "Almacén"
3. Haz clic en "Distribución Multi-Sucursal"

---

## ✅ CHECKLIST DE PRUEBAS

### Funcionalidades Básicas
- [ ] **Página carga sin errores**: Verifica que no haya errores 404 o 500
- [ ] **KPIs se muestran**: 4 tarjetas en la parte superior con estadísticas
- [ ] **Tabla principal visible**: Con columnas de Central + 4 sucursales
- [ ] **Productos listados**: Deberías ver 2 productos (P0021 y P0044)
- [ ] **Colores aplicados**: Celdas en rojo (0), amarillo (1-10) o verde (10+)

### Tarjetas Resumen (debajo de KPIs)
- [ ] **5 tarjetas de ubicación**: Central + 4 sucursales
- [ ] **Totales correctos**:
  - Central: 6 unidades
  - SUCDROF19: 2 unidades
  - SUCGUAD20: 12 unidades
  - SUCMONT74: 5 unidades
  - SUCSATE20: 1 unidad

### Filtros
- [ ] **Búsqueda por texto**: Escribe "RAM" y presiona Enter
  - Debería mostrar solo el producto "RAM 4 GB"
- [ ] **Filtro por categoría**: Selecciona una categoría del dropdown
- [ ] **Filtro por sucursal**: Selecciona una sucursal
- [ ] **Limpiar filtros**: Botón "Limpiar Filtros" funciona

### Paginación
- [ ] **Controles visibles**: Si hay más de 50 productos (actualmente solo 2)
- [ ] **Navegación funciona**: Páginas siguientes/anteriores

### Exportar Excel
- [ ] **Botón "Exportar Excel"**: Visible en la parte superior
- [ ] **Descarga funciona**: Al hacer clic se descarga un archivo `.xlsx`
- [ ] **Archivo válido**: Se puede abrir en Excel/LibreOffice

### Verificar Contenido del Excel (si descarga funciona):
1. **Hoja 1 - Distribución General**: Tabla completa con colores
2. **Hoja 2 - Resumen por Sucursal**: Totales y porcentajes
3. **Hoja 3 - Productos Sin Stock**: Lista de productos con 0 unidades
4. **Hoja 4 - Movimientos Recientes**: Últimos 30 días (puede estar vacía)
5. **Hoja 5 - Alertas de Reposición**: Productos con ≤10 unidades

### Interactividad (TypeScript)
- [ ] **Búsqueda en tiempo real**: Escribe en el campo de búsqueda (espera 300ms)
- [ ] **Tooltips**: Pasa el mouse sobre las celdas "días sin movimiento"
- [ ] **Sin errores en consola**: Presiona F12, ve a "Console", verifica que no haya errores rojos

---

## 📊 DATOS ESPERADOS

Basado en las pruebas automatizadas, deberías ver:

### Producto 1: P0021 - RAM 4 GB
| Ubicación | Unidades | Color |
|-----------|----------|-------|
| Central | 6 | 🟡 Amarillo |
| SUCDROF19 | 0 | 🔴 Rojo |
| SUCGUAD20 | 4 | 🟡 Amarillo |
| SUCMONT74 | 0 | 🔴 Rojo |
| SUCSATE20 | 0 | 🔴 Rojo |
| **TOTAL** | **10** | - |

### Producto 2: P0044 - SSD 1 TB
| Ubicación | Unidades | Color |
|-----------|----------|-------|
| Central | 0 | 🔴 Rojo |
| SUCDROF19 | 2 | 🟡 Amarillo |
| SUCGUAD20 | 8 | 🟡 Amarillo |
| SUCMONT74 | 5 | 🟡 Amarillo |
| SUCSATE20 | 1 | 🟡 Amarillo |
| **TOTAL** | **16** | - |

---

## 🐛 RESOLUCIÓN DE PROBLEMAS

### Si la página no carga (Error 404)
1. Verifica que el servidor esté corriendo
2. Revisa la URL: debe ser `/almacen/dashboard/distribucion-sucursales/`
3. Mira los logs del servidor en la terminal

### Si te redirige al login
- Inicia sesión con un usuario que tenga permisos de `almacen.view_productoalmacen`
- Si eres superusuario, deberías tener acceso automáticamente

### Si la tabla está vacía
- Los 2 productos tienen unidades disponibles, deberían mostrarse
- Revisa si hay filtros activos (búsqueda o categoría seleccionada)
- Mira los logs del servidor para errores

### Si los colores no se muestran
1. Presiona F12 → Pestaña "Network"
2. Busca `dashboard-distribucion-sucursales.css`
3. Si aparece error 404, el archivo CSS no existe (no debería pasar, está en el template)

### Si el botón Excel no funciona
1. Presiona F12 → Pestaña "Console"
2. Busca errores de JavaScript
3. Verifica que el archivo JS se cargó: `dashboard-distribucion-sucursales.js`

### Si hay errores en la consola del navegador
1. Copia el error exacto
2. Verifica que TypeScript se compiló correctamente:
   ```bash
   npm run build
   ```
3. Refresca la página (Ctrl+F5 para forzar recarga)

---

## 📝 REPORTAR RESULTADOS

Por favor, reporta:

### ✅ Si TODO funciona:
"Todo funciona perfectamente. Los filtros, exportación y visualización están operativos."

### ⚠️ Si HAY problemas:
1. **Qué paso falló** (usa el checklist de arriba)
2. **Mensaje de error** (si hay alguno)
3. **Captura de pantalla** (si es posible)
4. **Logs del servidor** (copia las líneas relevantes de la terminal)

---

## 🎯 RESULTADO ESPERADO

Si todo funciona correctamente, verás:

1. **Dashboard profesional** con diseño Bootstrap
2. **Tabla colorida** que muestra claramente qué productos necesitan reposición
3. **Filtros funcionales** para encontrar productos rápidamente
4. **Exportación Excel** con 5 hojas de análisis detallado
5. **Navegación fluida** sin errores de JavaScript

---

## 📞 SIGUIENTES PASOS

Una vez que confirmes que todo funciona:

1. **Agregar más datos de prueba** (opcional):
   ```bash
   # Si quieres más productos con unidades
   python scripts/poblado/poblar_almacen.py  # (si existe este script)
   ```

2. **Personalizar** (opcional):
   - Ajustar colores en el template
   - Cambiar umbral de "stock bajo" (actualmente 10)
   - Agregar más columnas personalizadas

3. **Documentar para tu equipo**:
   - Crear manual de usuario
   - Capacitar usuarios sobre filtros y exportación

---

**NOTA IMPORTANTE**: Todos los scripts de prueba automatizados pasaron correctamente:
- ✅ Lógica de distribución verificada
- ✅ Integridad de datos confirmada
- ✅ Totales cuadran perfectamente (26 unidades)

**Solo falta la prueba visual en el navegador.**

---

Creado: 24 de enero de 2026
Proyecto: Sistema Integrado de Gestión Técnica y Control de Calidad (SIGMA)
