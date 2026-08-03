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

        if (btnIrGaleria && seccionGaleria) {
            const btnImg = btnIrGaleria;
            const secImg = seccionGaleria;

            function verificarVisibilidadGaleria(): void {
                const galeriaRect = secImg.getBoundingClientRect();
                const windowHeight = window.innerHeight;
                const galeriaVisible = galeriaRect.top < windowHeight && galeriaRect.bottom > 0;

                if (galeriaVisible) {
                    btnImg.classList.remove('visible');
                } else if (window.scrollY > 300) {
                    btnImg.classList.add('visible');
                } else {
                    btnImg.classList.remove('visible');
                }
            }

            window.addEventListener('scroll', verificarVisibilidadGaleria);
            setTimeout(verificarVisibilidadGaleria, 100);

            btnImg.addEventListener('click', function (): void {
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

        const btnIrGaleriaVideo = document.getElementById('btnIrGaleriaVideo');
        const seccionGaleriaVideo = document.getElementById('galeria-videos');

        if (btnIrGaleriaVideo && seccionGaleriaVideo) {
            const btnVid = btnIrGaleriaVideo;
            const secVid = seccionGaleriaVideo;

            function verificarVisibilidadGaleriaVideo(): void {
                const rect = secVid.getBoundingClientRect();
                const galeriaVisible = rect.top < window.innerHeight && rect.bottom > 0;

                if (galeriaVisible) {
                    btnVid.classList.remove('visible');
                } else if (window.scrollY > 300) {
                    btnVid.classList.add('visible');
                } else {
                    btnVid.classList.remove('visible');
                }
            }

            window.addEventListener('scroll', verificarVisibilidadGaleriaVideo);
            setTimeout(verificarVisibilidadGaleriaVideo, 100);

            btnVid.addEventListener('click', function (): void {
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
