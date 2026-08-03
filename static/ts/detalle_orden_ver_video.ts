/**
 * Reproductor in-app #modalVerVideo (Fase C).
 */
(function detalleOrdenVerVideoMain(): void {
    const player = document.getElementById('modalVerVideoPlayer') as HTMLVideoElement | null;
    const tituloEl = document.getElementById('modalVerVideoTitulo');
    const modalEl = document.getElementById('modalVerVideo');
    if (!player || !modalEl) {
        return;
    }

    (window as unknown as { abrirModalVideo: (url: string, titulo: string) => void }).abrirModalVideo =
        function (url: string, titulo: string): void {
            player.src = url;
            if (tituloEl) {
                tituloEl.textContent = titulo;
            }
            const bootstrap = (window as unknown as {
                bootstrap: { Modal: new (el: Element) => { show(): void } };
            }).bootstrap;
            new bootstrap.Modal(modalEl).show();
        };

    modalEl.addEventListener('hidden.bs.modal', function (): void {
        player.pause();
        player.removeAttribute('src');
        player.load();
    });
})();
