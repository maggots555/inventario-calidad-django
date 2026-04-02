"use strict";
/**
 * MODAL: ESTADO DE MIS PIEZAS — SEGUIMIENTO PÚBLICO DE ORDEN
 * ===========================================================
 *
 * Controla la apertura/cierre del modal que muestra el estado de los
 * pedidos de piezas al cliente (SeguimientoPieza).
 *
 * Solo se carga en la página cuando existe al menos un SeguimientoPieza
 * vinculado a la orden (el template condiciona el script con {% if seguimientos_piezas %}).
 *
 * Comportamiento:
 *  - Botón #btn-ver-piezas → abre el modal
 *  - Botón #piezas-modal-close / clic en overlay → cierra el modal
 *  - Tecla Escape → cierra el modal
 *  - Bloquea el scroll del body mientras el modal está abierto
 *  - Focus management: al abrir foca el botón cerrar; al cerrar devuelve
 *    el foco al botón que abrió el modal (accesibilidad)
 *
 * COMPILACIÓN:
 *   npm run build
 *   Genera: static/js/piezas_modal.js
 *
 * @version 1.0.0
 * @date Abril 2026
 */
class PiezasModal {
    constructor(overlay, modal, openBtn, closeBtn) {
        this.overlay = overlay;
        this.modal = modal;
        this.openBtn = openBtn;
        this.closeBtn = closeBtn;
        this.bindEvents();
    }
    /** Abre el modal: agrega clase visible, bloquea scroll, foca el botón cerrar */
    open() {
        this.overlay.classList.add('st-modal-overlay--visible');
        document.body.style.overflow = 'hidden';
        // Permitir que la transición CSS termine antes de mover el foco
        setTimeout(() => this.closeBtn.focus(), 50);
    }
    /** Cierra el modal: remueve clase visible, restaura scroll, devuelve foco */
    close() {
        this.overlay.classList.remove('st-modal-overlay--visible');
        document.body.style.overflow = '';
        this.openBtn.focus();
    }
    /** Registra todos los event listeners */
    bindEvents() {
        // Abrir
        this.openBtn.addEventListener('click', () => this.open());
        // Cerrar con botón X
        this.closeBtn.addEventListener('click', () => this.close());
        // Cerrar al clicar el overlay (fuera del modal)
        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay)
                this.close();
        });
        // Cerrar con Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen())
                this.close();
        });
    }
    /** Indica si el modal está abierto actualmente */
    isOpen() {
        return this.overlay.classList.contains('st-modal-overlay--visible');
    }
}
/** Inicialización al cargar el DOM */
document.addEventListener('DOMContentLoaded', () => {
    const overlay = document.getElementById('piezas-modal-overlay');
    const modal = document.getElementById('piezas-modal');
    const openBtn = document.getElementById('btn-ver-piezas');
    const closeBtn = document.getElementById('piezas-modal-close');
    // Si algún elemento no existe en el DOM, no hay nada que inicializar
    if (!overlay || !modal || !openBtn || !closeBtn)
        return;
    new PiezasModal(overlay, modal, openBtn, closeBtn);
});
//# sourceMappingURL=piezas_modal.js.map