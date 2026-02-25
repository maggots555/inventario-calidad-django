"use strict";
// ============================================================================
// LIGHTBOX PERSONALIZADO PARA GALERÍA DE SERVICIO TÉCNICO
// Sin dependencias de Bootstrap Modal - Control total
// ============================================================================
class GaleriaLightbox {
    constructor() {
        this.lightboxContainer = null;
        this.currentImageIndex = 0;
        this.images = [];
        this.isOpen = false;
        this.init();
    }
    init() {
        // Crear el lightbox en el DOM
        this.createLightbox();
        // Buscar todas las imágenes de la galería
        this.collectImages();
        // Agregar event listeners
        this.attachEventListeners();
        // NUEVO: Escuchar cambios de pestaña para recargar imágenes
        this.attachTabListeners();
        console.log('✅ Lightbox inicializado con', this.images.length, 'imágenes');
    }
    // NUEVO: Método para escuchar cambios de pestaña
    attachTabListeners() {
        // Buscar todos los botones de pestañas de Bootstrap
        const tabButtons = document.querySelectorAll('[data-bs-toggle="pill"]');
        tabButtons.forEach((button) => {
            button.addEventListener('shown.bs.tab', () => {
                // EXPLICACIÓN: Cuando se muestra una nueva pestaña, recargamos las imágenes
                console.log('📑 Pestaña cambiada, recargando galería...');
                this.reloadGallery();
            });
        });
    }
    // NUEVO: Método público para recargar la galería
    reloadGallery() {
        // Cerrar el lightbox si está abierto
        if (this.isOpen) {
            this.close();
        }
        // Recolectar las imágenes de la nueva pestaña activa
        this.collectImages();
    }
    createLightbox() {
        // Crear el contenedor del lightbox
        const lightbox = document.createElement('div');
        lightbox.id = 'custom-lightbox';
        lightbox.className = 'custom-lightbox';
        lightbox.innerHTML = `
            <div class="lightbox-overlay"></div>
            <div class="lightbox-content">
                <button class="lightbox-close" aria-label="Cerrar">
                    <i class="bi bi-x-lg"></i>
                </button>
                
                <button class="lightbox-nav lightbox-prev" aria-label="Anterior">
                    <i class="bi bi-chevron-left"></i>
                </button>
                
                <button class="lightbox-nav lightbox-next" aria-label="Siguiente">
                    <i class="bi bi-chevron-right"></i>
                </button>
                
                <div class="lightbox-image-container">
                    <img src="" alt="" class="lightbox-image">
                    <div class="lightbox-loader">
                        <div class="spinner-border text-light" role="status">
                            <span class="visually-hidden">Cargando...</span>
                        </div>
                    </div>
                </div>
                
                <div class="lightbox-info">
                    <div class="lightbox-caption">
                        <p class="lightbox-description"></p>
                        <div class="lightbox-meta">
                            <span class="lightbox-user">
                                <i class="bi bi-person-circle"></i> 
                                <span class="user-name"></span>
                            </span>
                            <span class="lightbox-date">
                                <i class="bi bi-calendar"></i> 
                                <span class="date-text"></span>
                            </span>
                        </div>
                    </div>
                    <div class="lightbox-actions">
                        <a href="#" class="btn btn-primary btn-sm lightbox-download" download>
                            <i class="bi bi-download"></i> Descargar Original
                        </a>
                        <span class="lightbox-counter">
                            <span class="current-index">1</span> / <span class="total-images">1</span>
                        </span>
                        <button type="button" class="btn btn-danger btn-sm lightbox-delete">
                            <i class="bi bi-trash-fill"></i> Eliminar
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(lightbox);
        this.lightboxContainer = lightbox;
    }
    collectImages() {
        // EXPLICACIÓN: Ahora solo recolectamos imágenes de la pestaña activa
        // Buscar el contenedor de pestañas activo
        const activeTabPane = document.querySelector('.tab-pane.active');
        if (!activeTabPane) {
            // Si no hay pestañas, buscar todas las imágenes (compatibilidad con páginas sin pestañas)
            this.collectAllImages();
            return;
        }
        // Limpiar el array de imágenes antes de recolectar
        this.images = [];
        // Buscar solo las imágenes dentro de la pestaña activa
        const galleryImages = activeTabPane.querySelectorAll('.gallery-image');
        galleryImages.forEach((item, index) => {
            const img = item.querySelector('img');
            const container = item.closest('.gallery-image-container');
            if (img && container) {
                // Obtener metadata
                const imagenId = parseInt(container.dataset.imagenId || '0', 10);
                const descripcion = container.dataset.descripcion || '';
                const usuario = container.dataset.usuario || 'Usuario';
                const fecha = container.dataset.fecha || '';
                const urlDescarga = container.dataset.urlDescarga || img.src;
                this.images.push({
                    index: index,
                    imagenId: imagenId,
                    src: img.src,
                    descripcion: descripcion,
                    usuario: usuario,
                    fecha: fecha,
                    urlDescarga: urlDescarga
                });
                // Agregar click listener a la imagen
                item.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    this.open(index);
                });
                // Cambiar cursor a pointer
                item.style.cursor = 'pointer';
            }
        });
        console.log(`🖼️ Galería: ${this.images.length} imágenes cargadas desde la pestaña activa`);
    }
    // EXPLICACIÓN: Método auxiliar para cargar todas las imágenes (cuando no hay pestañas)
    collectAllImages() {
        this.images = [];
        const galleryImages = document.querySelectorAll('.gallery-image');
        galleryImages.forEach((item, index) => {
            const img = item.querySelector('img');
            const container = item.closest('.gallery-image-container');
            if (img && container) {
                const imagenId = parseInt(container.dataset.imagenId || '0', 10);
                const descripcion = container.dataset.descripcion || '';
                const usuario = container.dataset.usuario || 'Usuario';
                const fecha = container.dataset.fecha || '';
                const urlDescarga = container.dataset.urlDescarga || img.src;
                this.images.push({
                    index: index,
                    imagenId: imagenId,
                    src: img.src,
                    descripcion: descripcion,
                    usuario: usuario,
                    fecha: fecha,
                    urlDescarga: urlDescarga
                });
                item.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    this.open(index);
                });
                item.style.cursor = 'pointer';
            }
        });
        console.log(`🖼️ Galería: ${this.images.length} imágenes cargadas (sin pestañas)`);
    }
    attachEventListeners() {
        if (!this.lightboxContainer)
            return;
        // Botón cerrar
        const closeBtn = this.lightboxContainer.querySelector('.lightbox-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.close());
        }
        // Click en overlay para cerrar
        const overlay = this.lightboxContainer.querySelector('.lightbox-overlay');
        if (overlay) {
            overlay.addEventListener('click', () => this.close());
        }
        // Navegación
        const prevBtn = this.lightboxContainer.querySelector('.lightbox-prev');
        const nextBtn = this.lightboxContainer.querySelector('.lightbox-next');
        if (prevBtn) {
            prevBtn.addEventListener('click', () => this.prev());
        }
        if (nextBtn) {
            nextBtn.addEventListener('click', () => this.next());
        }
        // Botón eliminar del lightbox
        const deleteBtn = this.lightboxContainer.querySelector('.lightbox-delete');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', () => this.eliminarImagenActual());
        }
        // Teclado
        document.addEventListener('keydown', (e) => {
            if (!this.isOpen)
                return;
            switch (e.key) {
                case 'Escape':
                    this.close();
                    break;
                case 'ArrowLeft':
                    this.prev();
                    break;
                case 'ArrowRight':
                    this.next();
                    break;
            }
        });
    }
    open(index) {
        this.currentImageIndex = index;
        this.isOpen = true;
        if (!this.lightboxContainer)
            return;
        // Mostrar lightbox
        this.lightboxContainer.classList.add('active');
        document.body.style.overflow = 'hidden';
        // Cargar imagen
        this.loadImage();
        // Actualizar navegación
        this.updateNavigation();
        console.log('🖼️ Lightbox abierto - Imagen', index + 1);
    }
    close() {
        this.isOpen = false;
        if (!this.lightboxContainer)
            return;
        // Ocultar lightbox
        this.lightboxContainer.classList.remove('active');
        document.body.style.overflow = '';
        console.log('❌ Lightbox cerrado');
    }
    loadImage() {
        if (!this.lightboxContainer)
            return;
        const imageData = this.images[this.currentImageIndex];
        const imgElement = this.lightboxContainer.querySelector('.lightbox-image');
        const loader = this.lightboxContainer.querySelector('.lightbox-loader');
        if (!imgElement || !loader)
            return;
        // Mostrar loader
        loader.style.display = 'flex';
        imgElement.style.opacity = '0';
        // Cargar nueva imagen
        const tempImg = new Image();
        tempImg.onload = () => {
            imgElement.src = imageData.src;
            imgElement.alt = imageData.descripcion;
            // Ocultar loader, mostrar imagen
            setTimeout(() => {
                loader.style.display = 'none';
                imgElement.style.opacity = '1';
            }, 100);
        };
        tempImg.onerror = () => {
            console.error('Error cargando imagen:', imageData.src);
            loader.style.display = 'none';
            imgElement.style.opacity = '1';
        };
        tempImg.src = imageData.src;
        // Actualizar info
        this.updateInfo();
    }
    updateInfo() {
        if (!this.lightboxContainer)
            return;
        const imageData = this.images[this.currentImageIndex];
        // Descripción
        const descEl = this.lightboxContainer.querySelector('.lightbox-description');
        if (descEl) {
            descEl.textContent = imageData.descripcion || 'Sin descripción';
        }
        // Usuario
        const userEl = this.lightboxContainer.querySelector('.user-name');
        if (userEl) {
            userEl.textContent = imageData.usuario;
        }
        // Fecha
        const dateEl = this.lightboxContainer.querySelector('.date-text');
        if (dateEl) {
            dateEl.textContent = imageData.fecha;
        }
        // Botón descarga
        const downloadBtn = this.lightboxContainer.querySelector('.lightbox-download');
        if (downloadBtn) {
            downloadBtn.href = imageData.urlDescarga;
        }
        // Contador
        const currentEl = this.lightboxContainer.querySelector('.current-index');
        const totalEl = this.lightboxContainer.querySelector('.total-images');
        if (currentEl) {
            currentEl.textContent = String(this.currentImageIndex + 1);
        }
        if (totalEl) {
            totalEl.textContent = String(this.images.length);
        }
        // Botón eliminar: guardar el ID de la imagen actual en un data attribute
        // para que eliminarImagenActual() sepa qué imagen borrar
        const deleteBtn = this.lightboxContainer.querySelector('.lightbox-delete');
        if (deleteBtn) {
            deleteBtn.dataset.imagenId = String(imageData.imagenId);
            // Ocultar el botón si la imagen no tiene ID válido (sin permisos / sin datos)
            deleteBtn.style.display = imageData.imagenId > 0 ? '' : 'none';
        }
    }
    updateNavigation() {
        if (!this.lightboxContainer)
            return;
        const prevBtn = this.lightboxContainer.querySelector('.lightbox-prev');
        const nextBtn = this.lightboxContainer.querySelector('.lightbox-next');
        if (!prevBtn || !nextBtn)
            return;
        // Mostrar/ocultar botones según posición
        if (this.currentImageIndex === 0) {
            prevBtn.style.opacity = '0.3';
            prevBtn.style.pointerEvents = 'none';
        }
        else {
            prevBtn.style.opacity = '1';
            prevBtn.style.pointerEvents = 'auto';
        }
        if (this.currentImageIndex === this.images.length - 1) {
            nextBtn.style.opacity = '0.3';
            nextBtn.style.pointerEvents = 'none';
        }
        else {
            nextBtn.style.opacity = '1';
            nextBtn.style.pointerEvents = 'auto';
        }
    }
    /**
     * Elimina la imagen actualmente visible en el lightbox.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Reutilizamos la misma función confirmarEliminarImagen() que ya existe en la
     * página (detalle_orden.html) para no duplicar la lógica de confirmación y AJAX.
     *
     * BUG CORREGIDO: Antes pasábamos el botón del lightbox (.lightbox-delete) como
     * event.currentTarget. confirmarEliminarImagen() lo pone en estado "spinner" y
     * solo lo restaura si hay ERROR — en éxito asume que el botón desaparecerá con
     * su contenedor. Como el lightbox NO desaparece del DOM, el botón quedaba
     * permanentemente deshabilitado con spinner.
     *
     * SOLUCIÓN: Pasamos el botón de la MINIATURA en la galería como currentTarget.
     * Ese botón sí desaparece del DOM cuando la eliminación es exitosa (junto con
     * .col-md-3). Si no se encuentra la miniatura, usamos un elemento temporal
     * desechable que no afecta al lightbox.
     */
    eliminarImagenActual() {
        if (!this.lightboxContainer)
            return;
        const imageData = this.images[this.currentImageIndex];
        if (!imageData || imageData.imagenId <= 0) {
            console.warn('⚠️ No se puede eliminar: imagenId no válido');
            return;
        }
        const imagenId = imageData.imagenId;
        // EXPLICACIÓN: Buscar el botón de eliminar de la MINIATURA en la galería,
        // no el del lightbox. Ese botón sí desaparece del DOM al eliminar con éxito,
        // por lo que confirmarEliminarImagen() puede ponerle el spinner sin problema.
        const contenedorMiniatura = document.querySelector(`.gallery-image-container[data-imagen-id="${imagenId}"]`);
        const btnMiniatura = contenedorMiniatura
            ? contenedorMiniatura.querySelector('.btn-eliminar-miniatura')
            : null;
        // Si no hay miniatura en el DOM (ej: se eliminó antes), creamos un elemento
        // temporal desechable para que confirmarEliminarImagen() pueda operar sin
        // afectar al botón del lightbox.
        const targetBtn = btnMiniatura !== null && btnMiniatura !== void 0 ? btnMiniatura : document.createElement('button');
        const eventoSintetico = {
            stopPropagation: () => { },
            currentTarget: targetBtn
        };
        // OPCIÓN A: Usar la función global confirmarEliminarImagen() si existe en la página
        // Esta función ya tiene la confirmación, el AJAX, el spinner y la eliminación del DOM
        if (typeof window.confirmarEliminarImagen === 'function') {
            // Cerrar lightbox primero para que el usuario vea el efecto en la galería
            this.close();
            window.confirmarEliminarImagen(imagenId, imageData.descripcion || 'imagen', eventoSintetico);
            return;
        }
        // OPCIÓN B: Fallback si la función global no está disponible
        const confirmacion = confirm(`⚠️ ¿Estás seguro de eliminar esta imagen?\n\nEsta acción NO se puede deshacer.`);
        if (!confirmacion)
            return;
        console.log(`🗑️ Eliminando imagen ID: ${imagenId} desde lightbox`);
        this.close();
    }
    prev() {
        if (this.currentImageIndex > 0) {
            this.currentImageIndex--;
            this.loadImage();
            this.updateNavigation();
        }
    }
    next() {
        if (this.currentImageIndex < this.images.length - 1) {
            this.currentImageIndex++;
            this.loadImage();
            this.updateNavigation();
        }
    }
}
// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    // Solo inicializar si hay imágenes de galería
    if (document.querySelector('.gallery-image')) {
        window.galeriaLightbox = new GaleriaLightbox();
    }
});
//# sourceMappingURL=lightbox_galeria.js.map