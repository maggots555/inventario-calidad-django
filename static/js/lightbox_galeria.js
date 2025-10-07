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
        
        console.log('✅ Lightbox inicializado con', this.images.length, 'imágenes');
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
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(lightbox);
        this.lightboxContainer = lightbox;
    }
    
    collectImages() {
        // Buscar todas las imágenes de la galería
        const galleryImages = document.querySelectorAll('.gallery-image');
        
        galleryImages.forEach((item, index) => {
            const img = item.querySelector('img');
            const container = item.closest('.gallery-image-container');
            
            if (img && container) {
                // Obtener metadata
                const descripcion = container.dataset.descripcion || '';
                const usuario = container.dataset.usuario || 'Usuario';
                const fecha = container.dataset.fecha || '';
                const urlDescarga = container.dataset.urlDescarga || img.src;
                
                this.images.push({
                    index: index,
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
    }
    
    attachEventListeners() {
        // Botón cerrar
        const closeBtn = this.lightboxContainer.querySelector('.lightbox-close');
        closeBtn.addEventListener('click', () => this.close());
        
        // Click en overlay para cerrar
        const overlay = this.lightboxContainer.querySelector('.lightbox-overlay');
        overlay.addEventListener('click', () => this.close());
        
        // Navegación
        const prevBtn = this.lightboxContainer.querySelector('.lightbox-prev');
        const nextBtn = this.lightboxContainer.querySelector('.lightbox-next');
        
        prevBtn.addEventListener('click', () => this.prev());
        nextBtn.addEventListener('click', () => this.next());
        
        // Teclado
        document.addEventListener('keydown', (e) => {
            if (!this.isOpen) return;
            
            switch(e.key) {
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
        
        // Ocultar lightbox
        this.lightboxContainer.classList.remove('active');
        document.body.style.overflow = '';
        
        console.log('❌ Lightbox cerrado');
    }
    
    loadImage() {
        const imageData = this.images[this.currentImageIndex];
        const imgElement = this.lightboxContainer.querySelector('.lightbox-image');
        const loader = this.lightboxContainer.querySelector('.lightbox-loader');
        
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
        const imageData = this.images[this.currentImageIndex];
        
        // Descripción
        const descEl = this.lightboxContainer.querySelector('.lightbox-description');
        descEl.textContent = imageData.descripcion || 'Sin descripción';
        
        // Usuario
        const userEl = this.lightboxContainer.querySelector('.user-name');
        userEl.textContent = imageData.usuario;
        
        // Fecha
        const dateEl = this.lightboxContainer.querySelector('.date-text');
        dateEl.textContent = imageData.fecha;
        
        // Botón descarga
        const downloadBtn = this.lightboxContainer.querySelector('.lightbox-download');
        downloadBtn.href = imageData.urlDescarga;
        
        // Contador
        const currentEl = this.lightboxContainer.querySelector('.current-index');
        const totalEl = this.lightboxContainer.querySelector('.total-images');
        currentEl.textContent = this.currentImageIndex + 1;
        totalEl.textContent = this.images.length;
    }
    
    updateNavigation() {
        const prevBtn = this.lightboxContainer.querySelector('.lightbox-prev');
        const nextBtn = this.lightboxContainer.querySelector('.lightbox-next');
        
        // Mostrar/ocultar botones según posición
        if (this.currentImageIndex === 0) {
            prevBtn.style.opacity = '0.3';
            prevBtn.style.pointerEvents = 'none';
        } else {
            prevBtn.style.opacity = '1';
            prevBtn.style.pointerEvents = 'auto';
        }
        
        if (this.currentImageIndex === this.images.length - 1) {
            nextBtn.style.opacity = '0.3';
            nextBtn.style.pointerEvents = 'none';
        } else {
            nextBtn.style.opacity = '1';
            nextBtn.style.pointerEvents = 'auto';
        }
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
