"use strict";
/**
 * Reproductor in-app #modalVerVideo (Fase C).
 */
(function detalleOrdenVerVideoMain() {
    const player = document.getElementById('modalVerVideoPlayer');
    const tituloEl = document.getElementById('modalVerVideoTitulo');
    const modalEl = document.getElementById('modalVerVideo');
    if (!player || !modalEl) {
        return;
    }
    window.abrirModalVideo =
        function (url, titulo) {
            player.src = url;
            if (tituloEl) {
                tituloEl.textContent = titulo;
            }
            const bootstrap = window.bootstrap;
            new bootstrap.Modal(modalEl).show();
        };
    modalEl.addEventListener('hidden.bs.modal', function () {
        player.pause();
        player.removeAttribute('src');
        player.load();
    });
})();
//# sourceMappingURL=detalle_orden_ver_video.js.map