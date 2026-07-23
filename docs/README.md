# 📚 Documentación del Sistema

Este directorio contiene toda la documentación técnica, guías de implementación y scripts de utilidades del proyecto.

## 📂 Estructura de Carpetas

### � `/screenshots/`
Capturas de pantalla del sistema para el README principal.
- `README.md` - Guía completa para tomar y preparar screenshots
- 6 imágenes principales del sistema (pendientes de agregar)

### �📖 `/implementaciones/`
Documentación detallada de cada módulo implementado en el sistema.

#### 🔧 `/implementaciones/servicio_tecnico/`
- `README_SERVICIO_TECNICO.md` - Visión general del módulo
- `README_VISTA_DETALLES_ORDEN.md` - Documentación de la vista de detalles
- `GESTION_PIEZAS_COTIZACION_README.md` - Sistema de piezas y cotizaciones
- `CAMBIO_AUTOMATICO_ESTADOS.md` - Flujo automático de estados
- `CAMBIO_FECHAS_RHITSO_MANUAL.md` - Gestión manual de fechas RHITSO

#### 🔄 `/implementaciones/rhitso/`
Sistema de seguimiento de reparaciones especializadas RHITSO.
- `PLAN_IMPLEMENTACION_RHITSO.md` - Plan maestro de implementación
- `RESUMEN_FASE1_RHITSO.md` - Fase 1: Fundamentos
- `RESUMEN_FASE2_RHITSO.md` - Fase 2: Seguimiento
- `RESUMEN_FASE3_RHITSO.md` - Fase 3: Incidencias
- `RESUMEN_FASE5_RHITSO.md` - Fase 5: Vistas AJAX
- `RESUMEN_FASE11_RHITSO.md` - Fase 11: Integración completa
- `FASE_10_2_PDF_RHITSO_COMPLETADO.md` - Generación de PDF
- `PALETA_COLORES_RHITSO.md` - Guía de colores del sistema

#### 📊 `/implementaciones/scorecard/`
Sistema de control de calidad y métricas.
- `SCORECARD_README.md` - Documentación principal
- `SCORECARD_FASE2.md` - Fase 2: Reportes
- `SCORECARD_FASE2_IMPLEMENTADA.md` - Implementación Fase 2
- `SCORECARD_FASE3.md` - Fase 3: Análisis avanzados
- `SCORECARD_FASE3_COMPLETA.md` - Completado Fase 3
- `SCORECARD_FASE4.md` - Fase 4: Dashboard
- `SCORECARD_ATRIBUIBILIDAD.md` - Sistema de atribuibilidad
- `SCORECARD_NOTIFICACIONES_HISTORICO.md` - Notificaciones

#### 🛒 `/implementaciones/venta_mostrador/`
Sistema de ventas mostrador y paquetes.
- `VENTAS_MOSTRADOR_PLAN_IMPLEMENTACION.md` - Plan de implementación
- `CHANGELOG_VENTA_MOSTRADOR.md` - Historial de cambios Fase 1
- `CHANGELOG_VENTA_MOSTRADOR_FASE2.md` - Fase 2
- `CHANGELOG_VENTA_MOSTRADOR_FASE3.md` - Fase 3
- `CHANGELOG_VENTA_MOSTRADOR_FASE4.md` - Fase 4
- `REFACTOR_VENTA_MOSTRADOR_PARTE1_BACKEND.md` - Refactor Backend
- `REFACTOR_VENTA_MOSTRADOR_PARTE2_FRONTEND.md` - Refactor Frontend
- `REFERENCIA_RAPIDA_VENTA_MOSTRADOR.md` - Guía rápida
- `REFERENCIA_RAPIDA_VENTA_MOSTRADOR_FASE3.md` - Fase 3
- `REFERENCIA_RAPIDA_VENTA_MOSTRADOR_FASE4.md` - Fase 4
- `REFERENCIA_RAPIDA_ADMIN_VENTA_MOSTRADOR.md` - Panel Admin

### 📘 `/guias/`
Guías de referencia y manuales de usuario.

#### ⚙️ `/guias/setup/`
Configuración inicial y comandos esenciales.
- `SETUP_NUEVA_MAQUINA.md` - Configuración de entorno
- `GIT_COMANDOS_ESENCIALES.md` - Comandos Git

#### 📑 `/guias/referencias/`
Referencias técnicas y guías de estilo.
- `GUIA_COLORES_BADGES.md` - Sistema de colores
- `README_REFERENCIAS_GAMA.md` - Referencias de gamas
- `NOTIFICACIONES_GUIA_RAPIDA.md` - Sistema de notificaciones
- `REFACTOR_FRONTEND_COMPLETADO.md` - Refactorización frontend
- `RESUMEN_CAMPO_NUMERO_ORDEN.md` - Campo número de orden
- `RESUMEN_FASE3.md` - Resumen general Fase 3
- `MEJORAS_CARGA_IMAGENES.md` - Optimización de imágenes
- `PLAN_REPORTES_FASE2_FASE3.md` - Sistema de reportes

## 🔧 Scripts de Utilidades

### `/scripts/poblado/`
Scripts para poblar datos iniciales en el sistema.
- `poblar_estados_rhitso.py` - Estados del proceso RHITSO
- `poblar_productos.py` - Catálogo de productos
- `poblar_scorecard.py` - Datos de Scorecard
- `poblar_servicios.py` - Catálogo de servicios
- `poblar_sistema.py` - Configuración general

### `/scripts/verificacion/`
Scripts de validación y actualización.
- `actualizar_seguimientos_existentes.py` - Actualizar seguimientos
- `verificar_datos.py` - Validación de datos
- `verificar_fase1.py` - Validar Fase 1
- `verificar_fase2.py` - Validar Fase 2
- `verificar_fase2_signals.py` - Validar signals Fase 2
- `verificar_fase3_formularios.py` - Validar formularios Fase 3
- `verificar_fase4_vista_principal.py` - Validar vista Fase 4
- `verificar_fase5_vistas_ajax.py` - Validar AJAX Fase 5
- `verificar_fase11_integracion.py` - Validar integración Fase 11
- `verificar_usuario_empleado.py` - Validar usuarios

### `/scripts/testing/`
Scripts de prueba y testing.
- `test_apis_fase3.py` - Pruebas API Fase 3
- `test_colores_rhitso.py` - Pruebas sistema de colores
- `test_compresion_imagenes.py` - Pruebas compresión
- `test_dias_habiles.py` - Pruebas cálculo días hábiles
- `test_email_config.py` - Pruebas configuración email
- `test_pdf_rhitso.py` - Pruebas generación PDF
- `test_rhitso_config.py` - Pruebas configuración RHITSO
- `test_scanner_fixes.py` - Pruebas scanner

---

## 🚀 Cómo Usar Esta Documentación

### Para Desarrolladores Nuevos
1. Empieza con `/guias/setup/SETUP_NUEVA_MAQUINA.md`
2. Revisa las implementaciones de cada módulo en `/implementaciones/`
3. Consulta las guías de referencia según necesites

### Para Desarrollo
1. Antes de modificar un módulo, lee su documentación en `/implementaciones/`
2. Usa los scripts de `/scripts/verificacion/` para validar cambios
3. Ejecuta los tests en `/scripts/testing/` antes de commit

### Para Mantenimiento
1. Los scripts de `/scripts/poblado/` ayudan a resetear datos de prueba
2. Usa `/scripts/verificacion/` para diagnóstico de problemas
3. Consulta `/guias/referencias/` para convenciones del sistema

---

**Fecha de Última Actualización:** Octubre 2025  
**Versión del producto (SIGMA):** v1.0.0  
**Framework:** Django 5.2.14 | Python 3.12+  
**Proyecto:** Sistema Integrado de Servicio Técnico y Control de Calidad
