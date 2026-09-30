/**
 * detalle_orden_fabs.ts — botones flotantes ir a galería (Fase C).
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Dos FAB: ir a galería de imágenes y a galería de videos.
 * Aparecen tras scrollear 300px y se ocultan si la sección ya es visible.
 */

(function detalleOrdenFabsMain(): void {
    document.addEventListener('DOMContentLoaded', function (): void {
        const btnIrGaleria = document.getElementById('btnIrGaleria');
        const seccionGaleria = document.getElementById('galeria-imagenes');
        const btnIrGaleriaVideo = document.getElementById('btnIrGaleriaVideo');
        const seccionGaleriaVideo = document.getElementById('galeria-videos');

        /**
         * Pone o quita .visible solo si el estado cambió.
         * Quitar y volver a poner la clase reinicia el glow y provoca el flash.
         */
        function fijarVisible(boton: HTMLElement, visible: boolean): void {
            const yaVisible = boton.classList.contains('visible');
            if (visible === yaVisible) {
                return;
            }
            boton.classList.toggle('visible', visible);
        }

        /**
         * El botón se muestra si ya bajamos 300px y la sección no está en pantalla.
         * El margen evita que un borde del viewport encienda y apague el botón en cada frame.
         */
        function debeMostrar(boton: HTMLElement, seccion: HTMLElement): boolean {
            const rect = seccion.getBoundingClientRect();
            const yaVisible = boton.classList.contains('visible');
            const margen = yaVisible ? 24 : 0;
            const umbralScroll = yaVisible ? 260 : 300;
            const enPantalla = rect.top < window.innerHeight - margen && rect.bottom > margen;
            return !enPantalla && window.scrollY > umbralScroll;
        }

        let framePendiente = 0;

        function sincronizarFabs(): void {
            framePendiente = 0;
            if (btnIrGaleria && seccionGaleria) {
                fijarVisible(btnIrGaleria, debeMostrar(btnIrGaleria, seccionGaleria));
            }
            if (btnIrGaleriaVideo && seccionGaleriaVideo) {
                fijarVisible(btnIrGaleriaVideo, debeMostrar(btnIrGaleriaVideo, seccionGaleriaVideo));
            }
        }

        function pedirSincronizacion(): void {
            if (framePendiente !== 0) {
                return;
            }
            framePendiente = window.requestAnimationFrame(sincronizarFabs);
        }

        const hayGaleria = Boolean(
            (btnIrGaleria && seccionGaleria) || (btnIrGaleriaVideo && seccionGaleriaVideo),
        );
        if (hayGaleria) {
            window.addEventListener('scroll', pedirSincronizacion, { passive: true });
            window.setTimeout(sincronizarFabs, 100);
        }

        if (btnIrGaleria && seccionGaleria) {
            const secImg = seccionGaleria;
            btnIrGaleria.addEventListener('click', function (): void {
                secImg.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start',
                    inline: 'nearest',
                });
                setTimeout(function (): void {
                    secImg.classList.add('highlight-section');
                    setTimeout(() => {
                        secImg.classList.remove('highlight-section');
                    }, 2000);
                }, 500);
            });
        }

        if (btnIrGaleriaVideo && seccionGaleriaVideo) {
            const secVid = seccionGaleriaVideo;
            btnIrGaleriaVideo.addEventListener('click', function (): void {
                secVid.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start',
                    inline: 'nearest',
                });
                setTimeout(function (): void {
                    secVid.classList.add('highlight-section');
                    setTimeout(() => {
                        secVid.classList.remove('highlight-section');
                    }, 2000);
                }, 500);
            });
        }
    });
})();
