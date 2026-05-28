"use strict";
// ============================================================================
// LIGHTBOX PERSONALIZADO PARA GALERÍA DE SERVICIO TÉCNICO
// Sin dependencias de Bootstrap Modal - Control total
// ============================================================================
class GaleriaLightbox {
    constructor() {
        // EXPLICACIÓN: Constantes para los límites del zoom
        this.MIN_ZOOM = 0.5;
        this.MAX_ZOOM = 8;
        this.ZOOM_STEP = 0.25;
        this.lightboxContainer = null;
        this.currentImageIndex = 0;
        this.images = [];
        this.isOpen = false;
        // Inicializar estado de zoom
        this.isZoomMode = false;
        this.zoomLevel = 1;
        this.panX = 0;
        this.panY = 0;
        this.isDragging = false;
        this.dragStartX = 0;
        this.dragStartY = 0;
        this.lastPanX = 0;
        this.lastPanY = 0;
        this.pinchStartDistance = 0;
        this.pinchStartZoom = 1;
        // Inicializar rotación
        this.rotationDeg = 0;
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
                    <img src="" alt="" class="lightbox-image" draggable="false">
                    <div class="lightbox-loader">
                        <div class="spinner-border text-light" role="status">
                            <span class="visually-hidden">Cargando...</span>
                        </div>
                    </div>
                </div>
                
                <!-- CONTROLES DE ZOOM (visibles solo en modo inspección) -->
                <div class="lightbox-zoom-controls" style="display: none;">
                    <button type="button" class="btn btn-sm btn-outline-light zoom-out-btn" title="Alejar (-)">
                        <i class="bi bi-dash-lg"></i>
                    </button>
                    <span class="zoom-level-indicator">100%</span>
                    <button type="button" class="btn btn-sm btn-outline-light zoom-in-btn" title="Acercar (+)">
                        <i class="bi bi-plus-lg"></i>
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-light zoom-reset-btn" title="Restablecer zoom">
                        <i class="bi bi-arrows-angle-contract"></i> Reset
                    </button>
                    <button type="button" class="btn btn-sm btn-danger zoom-exit-btn" title="Salir de inspección">
                        <i class="bi bi-x-lg"></i> Cerrar Zoom
                    </button>
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
                        <!-- Grupo izquierdo: acciones principales -->
                        <div class="lightbox-actions-group">
                            <a href="#" class="lightbox-icon-btn lightbox-download" download title="Descargar original">
                                <i class="bi bi-download"></i>
                            </a>
                            <button type="button" class="lightbox-icon-btn lightbox-zoom-toggle" title="Inspeccionar con zoom">
                                <i class="bi bi-search"></i>
                            </button>
                            <button type="button" class="lightbox-icon-btn lightbox-rotate-left" title="Rotar izquierda (90°)">
                                <i class="bi bi-arrow-counterclockwise"></i>
                            </button>
                            <button type="button" class="lightbox-icon-btn lightbox-rotate-right" title="Rotar derecha (90°)">
                                <i class="bi bi-arrow-clockwise"></i>
                            </button>
                        </div>
                        <!-- Centro: contador -->
                        <span class="lightbox-counter">
                            <span class="current-index">1</span> / <span class="total-images">1</span>
                        </span>
                        <!-- Grupo derecho: acción destructiva separada -->
                        <div class="lightbox-actions-group">
                            <button type="button" class="lightbox-icon-btn lightbox-icon-btn--danger lightbox-delete" title="Eliminar imagen">
                                <i class="bi bi-trash-fill"></i>
                            </button>
                        </div>
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
        // ====================================================================
        // EVENT LISTENERS DE ROTACIÓN
        // ====================================================================
        const rotateLeftBtn = this.lightboxContainer.querySelector('.lightbox-rotate-left');
        const rotateRightBtn = this.lightboxContainer.querySelector('.lightbox-rotate-right');
        if (rotateLeftBtn) {
            rotateLeftBtn.addEventListener('click', () => this.rotateLeft());
        }
        if (rotateRightBtn) {
            rotateRightBtn.addEventListener('click', () => this.rotateRight());
        }
        // ====================================================================
        // EVENT LISTENERS DEL MODO ZOOM / INSPECCIÓN
        // ====================================================================
        // Botón "Inspeccionar" en la barra de acciones
        const zoomToggleBtn = this.lightboxContainer.querySelector('.lightbox-zoom-toggle');
        if (zoomToggleBtn) {
            zoomToggleBtn.addEventListener('click', () => this.toggleZoom());
        }
        // Controles de zoom (visibles solo en modo inspección)
        const zoomInBtn = this.lightboxContainer.querySelector('.zoom-in-btn');
        const zoomOutBtn = this.lightboxContainer.querySelector('.zoom-out-btn');
        const zoomResetBtn = this.lightboxContainer.querySelector('.zoom-reset-btn');
        const zoomExitBtn = this.lightboxContainer.querySelector('.zoom-exit-btn');
        if (zoomInBtn) {
            zoomInBtn.addEventListener('click', () => this.zoomIn());
        }
        if (zoomOutBtn) {
            zoomOutBtn.addEventListener('click', () => this.zoomOut());
        }
        if (zoomResetBtn) {
            zoomResetBtn.addEventListener('click', () => this.resetZoom());
        }
        if (zoomExitBtn) {
            zoomExitBtn.addEventListener('click', () => this.toggleZoom());
        }
        // EXPLICACIÓN PARA PRINCIPIANTES:
        // Wheel event para zoom con la rueda del mouse.
        // Se usa { passive: false } para poder llamar preventDefault() y evitar
        // que la página haga scroll mientras el usuario hace zoom en la imagen.
        const imageContainer = this.lightboxContainer.querySelector('.lightbox-image-container');
        if (imageContainer) {
            imageContainer.addEventListener('wheel', (e) => {
                this.handleWheel(e);
            }, { passive: false });
            // Mouse drag para pan
            imageContainer.addEventListener('mousedown', (e) => {
                this.handleMouseDown(e);
            });
            // Touch events para pinch-to-zoom y drag táctil
            imageContainer.addEventListener('touchstart', (e) => {
                this.handleTouchStart(e);
            }, { passive: false });
            imageContainer.addEventListener('touchmove', (e) => {
                this.handleTouchMove(e);
            }, { passive: false });
            imageContainer.addEventListener('touchend', (e) => {
                this.handleTouchEnd(e);
            });
        }
        // Mouse move y mouse up se escuchan en el document
        // para capturar el drag incluso si el cursor sale del contenedor
        document.addEventListener('mousemove', (e) => {
            this.handleMouseMove(e);
        });
        document.addEventListener('mouseup', (e) => {
            this.handleMouseUp(e);
        });
        // Doble click en la imagen para toggle rápido de zoom
        const imgElement = this.lightboxContainer.querySelector('.lightbox-image');
        if (imgElement) {
            imgElement.addEventListener('dblclick', (e) => {
                e.preventDefault();
                if (!this.isZoomMode) {
                    // Si no está en modo zoom, activarlo y hacer zoom 2x
                    this.toggleZoom();
                    this.setZoom(2);
                }
                else if (this.zoomLevel > 1) {
                    // Si ya tiene zoom, resetear
                    this.resetZoom();
                }
                else {
                    // Si está en 1x, hacer zoom 2x
                    this.setZoom(2);
                }
            });
        }
        // Teclado — extendido con controles de zoom
        document.addEventListener('keydown', (e) => {
            if (!this.isOpen)
                return;
            switch (e.key) {
                case 'Escape':
                    // EXPLICACIÓN: Si estamos en modo zoom, Escape sale del zoom.
                    // Si estamos en modo normal, Escape cierra el lightbox.
                    if (this.isZoomMode) {
                        this.toggleZoom();
                    }
                    else {
                        this.close();
                    }
                    break;
                case 'ArrowLeft':
                    if (!this.isZoomMode)
                        this.prev();
                    break;
                case 'ArrowRight':
                    if (!this.isZoomMode)
                        this.next();
                    break;
                case '+':
                case '=':
                    if (this.isZoomMode) {
                        e.preventDefault();
                        this.zoomIn();
                    }
                    break;
                case '-':
                case '_':
                    if (this.isZoomMode) {
                        e.preventDefault();
                        this.zoomOut();
                    }
                    break;
                case '0':
                    if (this.isZoomMode) {
                        e.preventDefault();
                        this.resetZoom();
                    }
                    break;
                // Tecla R: rotar a la derecha. Shift+R: rotar a la izquierda.
                // Disponible tanto en modo normal como en modo inspección.
                case 'r':
                case 'R':
                    e.preventDefault();
                    if (e.shiftKey) {
                        this.rotateLeft();
                    }
                    else {
                        this.rotateRight();
                    }
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
        // Si estamos en modo zoom, salir primero
        if (this.isZoomMode) {
            this.exitZoomMode();
        }
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
        // Resetear rotación y transformación al cargar una imagen nueva
        this.rotationDeg = 0;
        this.panX = 0;
        this.panY = 0;
        imgElement.style.transform = '';
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
    // ========================================================================
    // MÉTODOS DEL MODO ZOOM / INSPECCIÓN
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // El modo zoom permite al usuario ver la imagen en detalle, hacerle zoom
    // con la rueda del mouse (o pellizco en móvil) y arrastrarla para
    // inspeccionar cualquier zona. Esto es útil en control de calidad para
    // revisar defectos, marcas de reparación, etiquetas, etc.
    // ========================================================================
    /**
     * Activa o desactiva el modo inspección (zoom interactivo).
     * Al activarlo: oculta controles de navegación, muestra controles de zoom.
     * Al desactivarlo: restaura todo al estado normal.
     */
    toggleZoom() {
        if (this.isZoomMode) {
            this.exitZoomMode();
        }
        else {
            this.enterZoomMode();
        }
    }
    /**
     * Entra al modo inspección:
     * - Agrega la clase CSS 'zoom-active' al contenedor de imagen
     * - Oculta botones de navegación y barra de info
     * - Muestra los controles de zoom
     * - Carga la imagen original (URL de descarga) para máxima resolución
     */
    enterZoomMode() {
        if (!this.lightboxContainer)
            return;
        this.isZoomMode = true;
        this.zoomLevel = 1;
        this.panX = 0;
        this.panY = 0;
        // Agregar clase CSS al contenedor de imagen
        const imageContainer = this.lightboxContainer.querySelector('.lightbox-image-container');
        if (imageContainer) {
            imageContainer.classList.add('zoom-active');
        }
        // Agregar clase al contenedor principal para el layout de zoom
        this.lightboxContainer.classList.add('zoom-mode');
        // Ocultar navegación prev/next
        const prevBtn = this.lightboxContainer.querySelector('.lightbox-prev');
        const nextBtn = this.lightboxContainer.querySelector('.lightbox-next');
        if (prevBtn)
            prevBtn.style.display = 'none';
        if (nextBtn)
            nextBtn.style.display = 'none';
        // Ocultar barra de info y mostrar controles de zoom
        const infoBar = this.lightboxContainer.querySelector('.lightbox-info');
        const zoomControls = this.lightboxContainer.querySelector('.lightbox-zoom-controls');
        if (infoBar)
            infoBar.style.display = 'none';
        if (zoomControls)
            zoomControls.style.display = 'flex';
        // EXPLICACIÓN: Cargar la imagen original (full resolution) para que el zoom
        // muestre detalles reales, no una imagen escalada de baja resolución.
        const imageData = this.images[this.currentImageIndex];
        const imgElement = this.lightboxContainer.querySelector('.lightbox-image');
        if (imgElement && imageData.urlDescarga) {
            // Guardar la URL actual (thumbnail/media) por si necesitamos restaurar
            imgElement.dataset.originalSrc = imgElement.src;
            // Intentar cargar la imagen original desde la URL de descarga
            const tempImg = new Image();
            tempImg.onload = () => {
                imgElement.src = imageData.urlDescarga;
            };
            tempImg.onerror = () => {
                // Si falla, nos quedamos con la imagen actual
                console.warn('⚠️ No se pudo cargar la imagen original para zoom');
            };
            tempImg.src = imageData.urlDescarga;
        }
        // Actualizar indicador de zoom
        this.updateZoomIndicator();
        this.applyTransform();
        console.log('🔍 Modo inspección activado');
    }
    /**
     * Sale del modo inspección y restaura todo al estado normal.
     */
    exitZoomMode() {
        if (!this.lightboxContainer)
            return;
        this.isZoomMode = false;
        this.zoomLevel = 1;
        this.panX = 0;
        this.panY = 0;
        this.isDragging = false;
        // Remover clase CSS del contenedor de imagen
        const imageContainer = this.lightboxContainer.querySelector('.lightbox-image-container');
        if (imageContainer) {
            imageContainer.classList.remove('zoom-active');
        }
        // Remover clase del contenedor principal
        this.lightboxContainer.classList.remove('zoom-mode');
        // Restaurar imagen a la URL original (media)
        const imgElement = this.lightboxContainer.querySelector('.lightbox-image');
        if (imgElement && imgElement.dataset.originalSrc) {
            imgElement.src = imgElement.dataset.originalSrc;
            delete imgElement.dataset.originalSrc;
        }
        // Resetear transform de la imagen
        if (imgElement) {
            imgElement.style.transform = '';
        }
        // Restaurar navegación prev/next
        const prevBtn = this.lightboxContainer.querySelector('.lightbox-prev');
        const nextBtn = this.lightboxContainer.querySelector('.lightbox-next');
        if (prevBtn)
            prevBtn.style.display = '';
        if (nextBtn)
            nextBtn.style.display = '';
        // Restaurar barra de info y ocultar controles de zoom
        const infoBar = this.lightboxContainer.querySelector('.lightbox-info');
        const zoomControls = this.lightboxContainer.querySelector('.lightbox-zoom-controls');
        if (infoBar)
            infoBar.style.display = '';
        if (zoomControls)
            zoomControls.style.display = 'none';
        // Actualizar navegación (prev/next) para restaurar su opacidad
        this.updateNavigation();
        console.log('🔍 Modo inspección desactivado');
    }
    /**
     * Establece el nivel de zoom a un valor específico.
     * Aplica la transformación CSS y actualiza el indicador.
     */
    setZoom(level) {
        // Limitar el zoom entre MIN_ZOOM y MAX_ZOOM
        this.zoomLevel = Math.max(this.MIN_ZOOM, Math.min(this.MAX_ZOOM, level));
        // EXPLICACIÓN: Si el zoom es menor o igual a 1, centrar la imagen
        // para evitar que quede desplazada sin sentido.
        if (this.zoomLevel <= 1) {
            this.panX = 0;
            this.panY = 0;
        }
        this.applyTransform();
        this.updateZoomIndicator();
    }
    /**
     * Incrementa el zoom un paso.
     */
    zoomIn() {
        this.setZoom(this.zoomLevel + this.ZOOM_STEP);
    }
    /**
     * Decrementa el zoom un paso.
     */
    zoomOut() {
        this.setZoom(this.zoomLevel - this.ZOOM_STEP);
    }
    /**
     * Restablece el zoom a 1x y centra la imagen.
     */
    resetZoom() {
        this.panX = 0;
        this.panY = 0;
        this.setZoom(1);
    }
    /**
     * Aplica la transformación CSS completa a la imagen:
     * rotate (siempre activo) + scale + translate (solo en modo zoom).
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * CSS transform es GPU-acelerado: rotate(), scale() y translate() se
     * ejecutan en la tarjeta gráfica, por eso son tan fluidos.
     *
     * El orden de las funciones importa (se aplican de derecha a izquierda):
     *   1. translate — mueve la imagen (pan en modo zoom)
     *   2. scale     — la escala (zoom)
     *   3. rotate    — la gira alrededor de su centro original
     *
     * Separamos rotate del resto para que la rotación siempre gire alrededor
     * del centro visual de la imagen, independientemente del pan/zoom activo.
     *
     * Si no hay zoom ni pan activos (modo normal), solo aplicamos rotate().
     * Así los botones de rotar funcionan incluso fuera del modo inspección.
     */
    applyTransform() {
        if (!this.lightboxContainer)
            return;
        const imgElement = this.lightboxContainer.querySelector('.lightbox-image');
        if (!imgElement)
            return;
        if (this.isZoomMode) {
            imgElement.style.transform =
                `rotate(${this.rotationDeg}deg) scale(${this.zoomLevel}) translate(${this.panX}px, ${this.panY}px)`;
        }
        else {
            // Fuera del modo zoom solo aplicamos la rotación (sin escala ni pan)
            imgElement.style.transform = this.rotationDeg !== 0
                ? `rotate(${this.rotationDeg}deg)`
                : '';
        }
    }
    /**
     * Actualiza el indicador visual del porcentaje de zoom.
     */
    updateZoomIndicator() {
        if (!this.lightboxContainer)
            return;
        const indicator = this.lightboxContainer.querySelector('.zoom-level-indicator');
        if (indicator) {
            indicator.textContent = `${Math.round(this.zoomLevel * 100)}%`;
        }
    }
    // ========================================================================
    // HANDLERS DE EVENTOS DE MOUSE PARA ZOOM
    // ========================================================================
    /**
     * Maneja el evento wheel (rueda del mouse) para hacer zoom.
     * deltaY negativo = scroll hacia arriba = zoom in
     * deltaY positivo = scroll hacia abajo = zoom out
     */
    handleWheel(e) {
        var _a;
        if (!this.isZoomMode)
            return;
        e.preventDefault();
        e.stopPropagation();
        // EXPLICACIÓN: Calculamos un factor de zoom basado en la velocidad del scroll.
        // Usamos un factor suave para que el zoom sea gradual.
        const delta = e.deltaY > 0 ? -this.ZOOM_STEP : this.ZOOM_STEP;
        const newZoom = this.zoomLevel + delta;
        // EXPLICACIÓN PARA PRINCIPIANTES:
        // Queremos hacer zoom hacia donde está el cursor del mouse,
        // no solo al centro. Para eso calculamos la posición relativa
        // del cursor dentro de la imagen y ajustamos el pan.
        if (newZoom >= this.MIN_ZOOM && newZoom <= this.MAX_ZOOM) {
            const imgElement = (_a = this.lightboxContainer) === null || _a === void 0 ? void 0 : _a.querySelector('.lightbox-image');
            if (imgElement) {
                const rect = imgElement.getBoundingClientRect();
                const centerX = rect.left + rect.width / 2;
                const centerY = rect.top + rect.height / 2;
                // Posición del cursor relativa al centro de la imagen
                const offsetX = (e.clientX - centerX) / this.zoomLevel;
                const offsetY = (e.clientY - centerY) / this.zoomLevel;
                // Ajustar pan para que el zoom se centre en el cursor
                const zoomRatio = newZoom / this.zoomLevel;
                this.panX -= offsetX * (zoomRatio - 1) / newZoom;
                this.panY -= offsetY * (zoomRatio - 1) / newZoom;
            }
        }
        this.setZoom(newZoom);
    }
    /**
     * Inicia el arrastre (drag) de la imagen con el mouse.
     */
    handleMouseDown(e) {
        var _a;
        if (!this.isZoomMode)
            return;
        // Solo responder al botón izquierdo del mouse
        if (e.button !== 0)
            return;
        e.preventDefault();
        this.isDragging = true;
        this.dragStartX = e.clientX;
        this.dragStartY = e.clientY;
        this.lastPanX = this.panX;
        this.lastPanY = this.panY;
        // Cambiar cursor a "grabbing" (mano cerrada)
        const imageContainer = (_a = this.lightboxContainer) === null || _a === void 0 ? void 0 : _a.querySelector('.lightbox-image-container');
        if (imageContainer) {
            imageContainer.style.cursor = 'grabbing';
        }
    }
    /**
     * Mueve la imagen mientras se arrastra con el mouse.
     * EXPLICACIÓN: La traslación se divide entre el zoomLevel para que
     * el movimiento sea proporcional al nivel de zoom (a más zoom,
     * se necesita más arrastre para mover la misma distancia visual).
     */
    handleMouseMove(e) {
        if (!this.isDragging || !this.isZoomMode)
            return;
        e.preventDefault();
        const deltaX = (e.clientX - this.dragStartX) / this.zoomLevel;
        const deltaY = (e.clientY - this.dragStartY) / this.zoomLevel;
        this.panX = this.lastPanX + deltaX;
        this.panY = this.lastPanY + deltaY;
        this.applyTransform();
    }
    /**
     * Finaliza el arrastre con el mouse.
     */
    handleMouseUp(_e) {
        var _a;
        if (!this.isDragging)
            return;
        this.isDragging = false;
        // Restaurar cursor a "grab" (mano abierta)
        const imageContainer = (_a = this.lightboxContainer) === null || _a === void 0 ? void 0 : _a.querySelector('.lightbox-image-container');
        if (imageContainer && this.isZoomMode) {
            imageContainer.style.cursor = '';
        }
    }
    // ========================================================================
    // HANDLERS DE EVENTOS TÁCTILES PARA MÓVIL
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // En móvil no hay mouse. Los usuarios usan:
    // - 1 dedo: arrastrar para mover la imagen (pan)
    // - 2 dedos: pellizcar para zoom (pinch-to-zoom)
    // ========================================================================
    /**
     * Inicia el gesto táctil.
     * Si hay 1 dedo: inicia drag.
     * Si hay 2 dedos: inicia pinch-to-zoom.
     */
    handleTouchStart(e) {
        if (!this.isZoomMode)
            return;
        if (e.touches.length === 1) {
            // Un dedo: drag
            e.preventDefault();
            const touch = e.touches[0];
            this.isDragging = true;
            this.dragStartX = touch.clientX;
            this.dragStartY = touch.clientY;
            this.lastPanX = this.panX;
            this.lastPanY = this.panY;
        }
        else if (e.touches.length === 2) {
            // Dos dedos: pinch-to-zoom
            e.preventDefault();
            this.isDragging = false;
            this.pinchStartDistance = this.getTouchDistance(e.touches[0], e.touches[1]);
            this.pinchStartZoom = this.zoomLevel;
        }
    }
    /**
     * Procesa el movimiento del gesto táctil.
     */
    handleTouchMove(e) {
        if (!this.isZoomMode)
            return;
        if (e.touches.length === 1 && this.isDragging) {
            // Un dedo: mover (pan)
            e.preventDefault();
            const touch = e.touches[0];
            const deltaX = (touch.clientX - this.dragStartX) / this.zoomLevel;
            const deltaY = (touch.clientY - this.dragStartY) / this.zoomLevel;
            this.panX = this.lastPanX + deltaX;
            this.panY = this.lastPanY + deltaY;
            this.applyTransform();
        }
        else if (e.touches.length === 2) {
            // Dos dedos: pinch-to-zoom
            e.preventDefault();
            const currentDistance = this.getTouchDistance(e.touches[0], e.touches[1]);
            if (this.pinchStartDistance > 0) {
                const scale = currentDistance / this.pinchStartDistance;
                this.setZoom(this.pinchStartZoom * scale);
            }
        }
    }
    /**
     * Finaliza el gesto táctil.
     */
    handleTouchEnd(_e) {
        this.isDragging = false;
        this.pinchStartDistance = 0;
    }
    /**
     * Calcula la distancia entre dos puntos de contacto táctil.
     * EXPLICACIÓN: Usamos el teorema de Pitágoras para calcular
     * la distancia entre los dos dedos del usuario.
     */
    getTouchDistance(touch1, touch2) {
        const dx = touch1.clientX - touch2.clientX;
        const dy = touch1.clientY - touch2.clientY;
        return Math.sqrt(dx * dx + dy * dy);
    }
    // ========================================================================
    // MÉTODOS DE ROTACIÓN
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // Rotamos en pasos de 90°. Usamos módulo 360 para que el valor siempre
    // esté entre 0 y 359: (270 + 90) % 360 = 0 (vuelve al inicio).
    // Al rotar, también reseteamos el pan (panX/panY) para que la imagen
    // vuelva al centro — si el usuario la había desplazado con zoom y luego
    // la rota, sería confuso que quedara en una posición inesperada.
    // ========================================================================
    /**
     * Rota la imagen 90° en sentido antihorario.
     * Funciona tanto en modo normal como en modo zoom/inspección.
     */
    rotateLeft() {
        this.rotationDeg = (this.rotationDeg - 90 + 360) % 360;
        // Resetear pan para volver al centro después de rotar
        this.panX = 0;
        this.panY = 0;
        this.applyTransform();
        console.log(`↺ Rotación: ${this.rotationDeg}°`);
    }
    /**
     * Rota la imagen 90° en sentido horario.
     * Funciona tanto en modo normal como en modo zoom/inspección.
     */
    rotateRight() {
        this.rotationDeg = (this.rotationDeg + 90) % 360;
        // Resetear pan para volver al centro después de rotar
        this.panX = 0;
        this.panY = 0;
        this.applyTransform();
        console.log(`↻ Rotación: ${this.rotationDeg}°`);
    }
    // ========================================================================
    // FIN DE MÉTODOS DE ROTACIÓN
    // ========================================================================
    // ========================================================================
    // FIN DE MÉTODOS DE ZOOM
    // ========================================================================
    prev() {
        if (this.currentImageIndex > 0) {
            // Si estamos en modo zoom, salir antes de navegar
            if (this.isZoomMode) {
                this.exitZoomMode();
            }
            this.currentImageIndex--;
            this.loadImage();
            this.updateNavigation();
        }
    }
    next() {
        if (this.currentImageIndex < this.images.length - 1) {
            // Si estamos en modo zoom, salir antes de navegar
            if (this.isZoomMode) {
                this.exitZoomMode();
            }
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