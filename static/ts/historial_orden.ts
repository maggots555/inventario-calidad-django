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
 * Interfaz para elementos del historial
 */
interface EventoHistorial {
    elemento: HTMLElement;
    fecha: Date;
    tipo: string;
}

/**
 * Inicializa las mejoras visuales del historial
 */
function inicializarHistorial(): void {
    const timeline = document.querySelector('.timeline');
    
    if (!timeline) {
        return; // No hay historial en esta página
    }
    
    // Obtener todos los items del timeline
    const items = timeline.querySelectorAll<HTMLElement>('.timeline-item');
    
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
function resaltarEventosRecientes(items: NodeListOf<HTMLElement>): void {
    const ahora = new Date();
    const hace24Horas = new Date(ahora.getTime() - (24 * 60 * 60 * 1000));
    
    items.forEach(item => {
        // Buscar la fecha en el elemento
        const fechaTexto = item.querySelector<HTMLElement>('small.text-muted')?.textContent;
        
        if (!fechaTexto) return;
        
        // Parsear fecha (formato: "14/03/2026 15:30")
        const fechaMatch = fechaTexto.match(/(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2})/);
        
        if (fechaMatch) {
            const [, dia, mes, anio, hora, minuto] = fechaMatch;
            const fechaEvento = new Date(
                parseInt(anio),
                parseInt(mes) - 1, // Meses en JavaScript son 0-indexed
                parseInt(dia),
                parseInt(hora),
                parseInt(minuto)
            );
            
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
                    badge.parentElement?.appendChild(badgeReciente);
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
function animarEntradaItems(items: NodeListOf<HTMLElement>): void {
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
function agregarEfectosHover(items: NodeListOf<HTMLElement>): void {
    items.forEach(item => {
        item.addEventListener('mouseenter', function() {
            this.style.backgroundColor = 'rgba(0, 0, 0, 0.02)';
            this.style.transition = 'background-color 0.2s ease';
        });
        
        item.addEventListener('mouseleave', function() {
            // Mantener el fondo azul si es evento reciente
            if (this.style.borderLeft === '3px solid rgb(13, 110, 253)') {
                this.style.backgroundColor = 'rgba(13, 110, 253, 0.05)';
            } else {
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
function filtrarPorTipo(tipo: string): void {
    const items = document.querySelectorAll<HTMLElement>('.timeline-item');
    
    items.forEach(item => {
        const badge = item.querySelector('.badge');
        
        if (!badge) return;
        
        // Mostrar todos si tipo === 'todos'
        if (tipo === 'todos') {
            item.style.display = 'block';
            return;
        }
        
        // Ocultar items que no coinciden con el tipo
        const tipoEvento = badge.textContent?.toLowerCase() || '';
        if (tipoEvento.includes(tipo.toLowerCase())) {
            item.style.display = 'block';
        } else {
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
function exportarHistorial(): string {
    const items = document.querySelectorAll<HTMLElement>('.timeline-item');
    let textoExportado = '═══════════════════════════════════════\n';
    textoExportado += '   HISTORIAL DE ORDEN DE SERVICIO\n';
    textoExportado += '═══════════════════════════════════════\n\n';
    
    items.forEach((item, index) => {
        const badge = item.querySelector('.badge')?.textContent?.trim() || '';
        const fecha = item.querySelector('small.text-muted')?.textContent?.trim() || '';
        const comentario = item.querySelector('p')?.textContent?.trim() || '';
        const usuario = item.querySelectorAll('small.text-muted')[1]?.textContent?.trim() || '';
        
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
    (window as any).historialOrden = {
        filtrarPorTipo,
        exportarHistorial
    };
});
