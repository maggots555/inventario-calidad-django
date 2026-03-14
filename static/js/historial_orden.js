"use strict";
/**
 * HISTORIAL DE ORDEN - MEJORAS VISUALES
 * =====================================
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este archivo mejora la experiencia del usuario al visualizar el historial:
 * - Resalta eventos recientes (últimas 24 horas)
 * - Animación suave al cargar la página
 * - Scroll automático al evento más reciente
 * - Mejoras de accesibilidad
 *
 * COMPILACIÓN:
 * Este archivo TypeScript se compila a JavaScript con:
 * npm run build
 *
 * El archivo generado será: static/js/historial_orden.js
 *
 * @version 1.0.0
 * @date Marzo 2026
 */
/**
 * Inicializa las mejoras visuales del historial
 */
function inicializarHistorial() {
    const timeline = document.querySelector('.timeline');
    if (!timeline) {
        return; // No hay historial en esta página
    }
    // Obtener todos los items del timeline
    const items = timeline.querySelectorAll('.timeline-item');
    if (items.length === 0) {
        return;
    }
    // Resaltar eventos recientes (últimas 24 horas)
    resaltarEventosRecientes(items);
    // Animación suave de aparición
    animarEntradaItems(items);
    // Agregar efectos hover mejorados
    agregarEfectosHover(items);
}
/**
 * Resalta eventos que ocurrieron en las últimas 24 horas
 *
 * EXPLICACIÓN:
 * Añade clases CSS y estilos inline a eventos recientes para resaltarlos:
 * - Clase 'evento-reciente' para la animación de palpitación
 * - Borde izquierdo azul y fondo suave
 * - Badge "Reciente"
 */
function resaltarEventosRecientes(items) {
    const ahora = new Date();
    const hace24Horas = new Date(ahora.getTime() - (24 * 60 * 60 * 1000));
    items.forEach(item => {
        var _a, _b;
        // Buscar la fecha en el elemento
        const fechaTexto = (_a = item.querySelector('small.text-muted')) === null || _a === void 0 ? void 0 : _a.textContent;
        if (!fechaTexto)
            return;
        // Parsear fecha (formato: "14/03/2026 15:30")
        const fechaMatch = fechaTexto.match(/(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2})/);
        if (fechaMatch) {
            const [, dia, mes, anio, hora, minuto] = fechaMatch;
            const fechaEvento = new Date(parseInt(anio), parseInt(mes) - 1, // Meses en JavaScript son 0-indexed
            parseInt(dia), parseInt(hora), parseInt(minuto));
            // Si el evento es reciente (últimas 24 horas)
            if (fechaEvento > hace24Horas) {
                // Agregar clase para activar animación de palpitación
                item.classList.add('evento-reciente');
                // Estilos visuales
                item.style.borderLeft = '3px solid #0d6efd';
                item.style.paddingLeft = '12px';
                item.style.backgroundColor = 'rgba(13, 110, 253, 0.05)';
                item.style.borderRadius = '4px';
                // Agregar badge "Reciente"
                const badge = item.querySelector('.badge');
                if (badge && !item.querySelector('.badge-reciente')) {
                    const badgeReciente = document.createElement('span');
                    badgeReciente.className = 'badge bg-primary bg-opacity-25 text-primary ms-1 badge-reciente';
                    badgeReciente.style.fontSize = '0.65rem';
                    badgeReciente.innerHTML = '<i class="bi bi-clock-fill"></i> Reciente';
                    (_b = badge.parentElement) === null || _b === void 0 ? void 0 : _b.appendChild(badgeReciente);
                }
            }
        }
    });
}
/**
 * Anima la entrada de los items del historial
 *
 * EXPLICACIÓN:
 * Usa animación CSS para que los eventos aparezcan suavemente
 * en lugar de mostrarse todos de golpe.
 */
function animarEntradaItems(items) {
    items.forEach((item, index) => {
        // Ocultar inicialmente
        item.style.opacity = '0';
        item.style.transform = 'translateX(-20px)';
        item.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        // Animar con delay escalonado
        setTimeout(() => {
            item.style.opacity = '1';
            item.style.transform = 'translateX(0)';
        }, index * 50); // 50ms de delay entre cada item
    });
}
/**
 * Agrega efectos hover mejorados a los items del historial
 *
 * EXPLICACIÓN:
 * Sutil resaltado al pasar el mouse para mejorar la interactividad
 */
function agregarEfectosHover(items) {
    items.forEach(item => {
        item.addEventListener('mouseenter', function () {
            this.style.backgroundColor = 'rgba(0, 0, 0, 0.02)';
            this.style.transition = 'background-color 0.2s ease';
        });
        item.addEventListener('mouseleave', function () {
            // Mantener el fondo azul si es evento reciente
            if (this.style.borderLeft === '3px solid rgb(13, 110, 253)') {
                this.style.backgroundColor = 'rgba(13, 110, 253, 0.05)';
            }
            else {
                this.style.backgroundColor = 'transparent';
            }
        });
    });
}
/**
 * Función para filtrar eventos por tipo (uso futuro)
 *
 * EXPLICACIÓN:
 * Esta función permite filtrar el historial por tipo de evento.
 * Por ahora no está en uso, pero está lista para implementación futura
 * si se desea agregar botones de filtro.
 */
function filtrarPorTipo(tipo) {
    const items = document.querySelectorAll('.timeline-item');
    items.forEach(item => {
        var _a;
        const badge = item.querySelector('.badge');
        if (!badge)
            return;
        // Mostrar todos si tipo === 'todos'
        if (tipo === 'todos') {
            item.style.display = 'block';
            return;
        }
        // Ocultar items que no coinciden con el tipo
        const tipoEvento = ((_a = badge.textContent) === null || _a === void 0 ? void 0 : _a.toLowerCase()) || '';
        if (tipoEvento.includes(tipo.toLowerCase())) {
            item.style.display = 'block';
        }
        else {
            item.style.display = 'none';
        }
    });
}
/**
 * Función para exportar el historial a texto plano (uso futuro)
 *
 * EXPLICACIÓN:
 * Permite copiar todo el historial al portapapeles para documentación.
 */
function exportarHistorial() {
    const items = document.querySelectorAll('.timeline-item');
    let textoExportado = '═══════════════════════════════════════\n';
    textoExportado += '   HISTORIAL DE ORDEN DE SERVICIO\n';
    textoExportado += '═══════════════════════════════════════\n\n';
    items.forEach((item, index) => {
        var _a, _b, _c, _d, _e, _f, _g, _h;
        const badge = ((_b = (_a = item.querySelector('.badge')) === null || _a === void 0 ? void 0 : _a.textContent) === null || _b === void 0 ? void 0 : _b.trim()) || '';
        const fecha = ((_d = (_c = item.querySelector('small.text-muted')) === null || _c === void 0 ? void 0 : _c.textContent) === null || _d === void 0 ? void 0 : _d.trim()) || '';
        const comentario = ((_f = (_e = item.querySelector('p')) === null || _e === void 0 ? void 0 : _e.textContent) === null || _f === void 0 ? void 0 : _f.trim()) || '';
        const usuario = ((_h = (_g = item.querySelectorAll('small.text-muted')[1]) === null || _g === void 0 ? void 0 : _g.textContent) === null || _h === void 0 ? void 0 : _h.trim()) || '';
        textoExportado += `[${index + 1}] ${badge}\n`;
        textoExportado += `Fecha: ${fecha}\n`;
        textoExportado += `Detalle: ${comentario}\n`;
        if (usuario) {
            textoExportado += `Usuario: ${usuario}\n`;
        }
        textoExportado += '\n';
    });
    return textoExportado;
}
// ============================================================================
// INICIALIZACIÓN AUTOMÁTICA AL CARGAR LA PÁGINA
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
    inicializarHistorial();
    // Exponer funciones globalmente para uso desde la consola o futuras features
    window.historialOrden = {
        filtrarPorTipo,
        exportarHistorial
    };
});
//# sourceMappingURL=historial_orden.js.map