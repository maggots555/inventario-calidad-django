"use strict";
// ============================================================================
// SISTEMA DE SUBIDA DE VIDEO — GALERÍA DE EVIDENCIAS
// Versión 2.0 — UI replicada del sistema de imágenes
// ============================================================================
/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 *
 * Este módulo controla el formulario de subida de un video en detalle_orden.html.
 * La UI replica exactamente el diseño del panel de imágenes:
 *   - Radio cards de colores para elegir el tipo
 *   - Aviso contextual según el tipo seleccionado
 *   - Botón grande "Seleccionar Video"
 *   - Preview con nombre y tamaño del archivo
 *   - Barra de progreso durante la subida
 *   - Spinner "Procesando con FFmpeg…" mientras el servidor comprime
 *   - Mensaje de éxito/error al finalizar
 *
 * Flujo completo:
 * 1. El técnico elige el tipo de video con los radio cards
 * 2. Presiona el botón grande para seleccionar el archivo
 * 3. Se valida tamaño (< 90 MB) y se muestra preview
 * 4. Se habilita el botón "Subir Video"
 * 5. Al enviar: barra de progreso de subida (XHR upload)
 * 6. Al llegar al 100%: spinner FFmpeg (compresión server-side)
 * 7. Respuesta: mensaje de éxito o error → recarga de página
 */
// ============================================================================
// MENSAJES CONTEXTUALES POR TIPO — Mismo patrón que imágenes
// ============================================================================
const AVISOS_VIDEO = {
    ingreso: {
        clase: 'aviso-ingreso',
        texto: '📥 Video de ingreso: documenta el estado inicial del equipo al recibirlo.',
    },
    diagnostico: {
        clase: 'aviso-diagnostico',
        texto: '🔍 Video de diagnóstico: muestra el proceso de identificación del problema.',
    },
    reparacion: {
        clase: 'aviso-reparacion',
        texto: '🔧 Video de reparación: evidencia del trabajo realizado en el equipo.',
    },
    egreso: {
        clase: 'aviso-egreso',
        texto: '📤 Video de egreso: documenta el estado final del equipo antes de entregarlo.',
    },
    packing: {
        clase: 'aviso-packing',
        texto: '📦 Video de packing: evidencia del empaque y protección para envío.',
    },
};
// ============================================================================
// CLASE PRINCIPAL
// ============================================================================
class UploadVideo {
    constructor() {
        this.archivoSeleccionado = null;
        // Buscar todos los elementos por ID
        this.form = document.getElementById('form-subir-video');
        this.inputVideo = document.getElementById('inputVideo');
        this.btnSubir = document.getElementById('btnSubirVideo');
        this.avisoCont = document.getElementById('tipoVideoAviso');
        this.previewCont = document.getElementById('previewVideo');
        this.nombreSpan = document.getElementById('nombreArchivoVideo');
        this.tamanoSpan = document.getElementById('tamanoArchivoVideo');
        this.btnQuitar = document.getElementById('btnQuitarVideo');
        this.progresoCont = document.getElementById('progresoVideoUpload');
        this.barra = document.getElementById('barraProgresoVideo');
        this.textoProgreso = document.getElementById('textoProgresoVideo');
        this.porcentajeBadge = document.getElementById('porcentajeProgresoVideo');
        this.infoUpload = document.getElementById('infoVideoUpload');
        this.ffmpegCont = document.getElementById('estadoFFmpeg');
        this.resultadoCont = document.getElementById('resultadoVideo');
        this.mensajeResult = document.getElementById('mensajeResultadoVideo');
        // Si algún elemento crítico no existe, no inicializar
        if (!this.form || !this.inputVideo || !this.btnSubir) {
            return;
        }
        this.inicializar();
    }
    // -------------------------------------------------------------------------
    // Registro de eventos
    // -------------------------------------------------------------------------
    inicializar() {
        // Radio cards de tipo
        const radios = this.form.querySelectorAll('.tipo-imagen-radio');
        radios.forEach(radio => {
            radio.addEventListener('change', () => this.onTipoChanged(radio.value));
        });
        // Selección de archivo
        this.inputVideo.addEventListener('change', () => this.onArchivoSeleccionado());
        // Botón quitar
        this.btnQuitar.addEventListener('click', () => this.quitarArchivo());
        // Envío del formulario
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.enviar();
        });
    }
    // -------------------------------------------------------------------------
    // Cambio de tipo (radio cards)
    // -------------------------------------------------------------------------
    onTipoChanged(tipo) {
        const aviso = AVISOS_VIDEO[tipo];
        if (aviso && this.avisoCont) {
            this.avisoCont.className = `tipo-imagen-aviso mt-2 ${aviso.clase}`;
            this.avisoCont.textContent = aviso.texto;
        }
        // Refrescar estado del botón (necesita tipo + archivo)
        this.actualizarEstadoBoton();
    }
    // -------------------------------------------------------------------------
    // Selección de archivo
    // -------------------------------------------------------------------------
    onArchivoSeleccionado() {
        const archivos = this.inputVideo.files;
        if (!archivos || archivos.length === 0) {
            this.quitarArchivo();
            return;
        }
        const archivo = archivos[0];
        // Validar tamaño
        if (archivo.size > UploadVideo.MAX_BYTES) {
            const mb = (archivo.size / (1024 * 1024)).toFixed(1);
            this.mostrarResultado(false, `❌ El video pesa ${mb} MB y supera el límite de 90 MB. Recórtalo antes de subirlo.`);
            this.inputVideo.value = '';
            return;
        }
        this.archivoSeleccionado = archivo;
        this.mostrarPreview(archivo);
        this.ocultarResultado();
        this.actualizarEstadoBoton();
    }
    // -------------------------------------------------------------------------
    // Preview del archivo
    // -------------------------------------------------------------------------
    mostrarPreview(archivo) {
        const mb = (archivo.size / (1024 * 1024)).toFixed(2);
        this.nombreSpan.textContent = archivo.name;
        this.tamanoSpan.textContent = `${mb} MB`;
        this.previewCont.style.display = 'block';
    }
    quitarArchivo() {
        this.archivoSeleccionado = null;
        this.inputVideo.value = '';
        this.previewCont.style.display = 'none';
        this.nombreSpan.textContent = '—';
        this.tamanoSpan.textContent = '';
        this.actualizarEstadoBoton();
        this.ocultarResultado();
    }
    // -------------------------------------------------------------------------
    // Habilitar / deshabilitar botón Subir
    // El botón solo se habilita cuando hay tipo Y archivo seleccionado
    // -------------------------------------------------------------------------
    actualizarEstadoBoton() {
        const tieneTipo = !!this.form.querySelector('.tipo-imagen-radio:checked');
        const tieneArchivo = !!(this.archivoSeleccionado && this.archivoSeleccionado.size > 0 && this.archivoSeleccionado.size <= UploadVideo.MAX_BYTES);
        this.btnSubir.disabled = !(tieneArchivo && tieneTipo);
    }
    // -------------------------------------------------------------------------
    // Envío vía XHR
    // -------------------------------------------------------------------------
    enviar() {
        if (!this.archivoSeleccionado) {
            this.mostrarResultado(false, '⚠️ Selecciona un archivo de video primero.');
            return;
        }
        const tipoRadio = this.form.querySelector('.tipo-imagen-radio:checked');
        if (!tipoRadio) {
            this.mostrarResultado(false, '⚠️ Elige el tipo de video antes de subir.');
            return;
        }
        const formData = new FormData(this.form);
        // UI: bloquear mientras se envía
        this.bloquearUI(true);
        this.mostrarProgreso(0, 'Subiendo…');
        this.ocultarResultado();
        this.ffmpegCont.style.display = 'none';
        const xhr = new XMLHttpRequest();
        const url = this.form.action || window.location.href;
        // ── Progreso de upload ──
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const pct = Math.round((e.loaded / e.total) * 100);
                if (pct < 100) {
                    this.mostrarProgreso(pct, `Subiendo… ${pct}%`);
                }
                else {
                    // Upload completo → FFmpeg procesando
                    this.progresoCont.style.display = 'none';
                    this.ffmpegCont.style.display = 'block';
                    if (this.infoUpload) {
                        this.infoUpload.innerHTML = '<i class="bi bi-cpu"></i> FFmpeg comprimiendo el video…';
                    }
                }
            }
        });
        // ── Respuesta del servidor ──
        xhr.addEventListener('load', () => {
            this.bloquearUI(false);
            this.progresoCont.style.display = 'none';
            this.ffmpegCont.style.display = 'none';
            try {
                const data = JSON.parse(xhr.responseText);
                if (data.success) {
                    const ahorro = data.porcentaje_compresion != null
                        ? ` · Compresión: −${data.porcentaje_compresion}%`
                        : '';
                    this.mostrarResultado(true, `✅ ${data.message || 'Video guardado.'}${ahorro}`);
                    // Recargar para mostrar el video en la galería
                    setTimeout(() => window.location.reload(), 1800);
                }
                else {
                    this.mostrarResultado(false, `❌ ${data.error || 'Error desconocido al guardar el video.'}`);
                    console.error('[UploadVideo] Error:', data);
                }
            }
            catch {
                this.mostrarResultado(false, `❌ Error inesperado del servidor (código ${xhr.status}). Intenta de nuevo.`);
            }
        });
        // ── Error de red ──
        xhr.addEventListener('error', () => {
            this.bloquearUI(false);
            this.progresoCont.style.display = 'none';
            this.ffmpegCont.style.display = 'none';
            this.mostrarResultado(false, '❌ Error de conexión. Verifica tu internet e intenta de nuevo.');
        });
        // ── Timeout ──
        xhr.addEventListener('timeout', () => {
            this.bloquearUI(false);
            this.progresoCont.style.display = 'none';
            this.ffmpegCont.style.display = 'none';
            this.mostrarResultado(false, '❌ La solicitud tardó demasiado. El video puede ser muy grande o la conexión es lenta.');
        });
        xhr.open('POST', url);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.timeout = 360000; // 6 minutos
        xhr.send(formData);
    }
    // -------------------------------------------------------------------------
    // UI helpers
    // -------------------------------------------------------------------------
    bloquearUI(bloqueado) {
        // Botón subir
        this.btnSubir.disabled = bloqueado;
        if (bloqueado) {
            this.btnSubir.dataset.originalHtml = this.btnSubir.innerHTML;
            this.btnSubir.innerHTML = `
                <span class="spinner-border spinner-border-sm d-block mb-1" role="status" aria-hidden="true"></span>
                Procesando…
            `;
        }
        else if (this.btnSubir.dataset.originalHtml) {
            this.btnSubir.innerHTML = this.btnSubir.dataset.originalHtml;
            // Re-evaluar si debe quedar habilitado
            this.actualizarEstadoBoton();
        }
        // Deshabilitar radio cards durante el proceso
        const radios = this.form.querySelectorAll('.tipo-imagen-radio');
        radios.forEach(r => { r.disabled = bloqueado; });
        // Deshabilitar input de archivo
        this.inputVideo.disabled = bloqueado;
    }
    mostrarProgreso(pct, texto) {
        this.progresoCont.style.display = 'block';
        this.barra.style.width = `${pct}%`;
        this.textoProgreso.textContent = texto;
        this.porcentajeBadge.textContent = `${pct}%`;
        this.barra.setAttribute('aria-valuenow', String(pct));
    }
    mostrarResultado(exito, mensaje) {
        this.resultadoCont.style.display = 'block';
        this.mensajeResult.className = `alert py-2 mb-0 ${exito ? 'alert-success' : 'alert-danger'}`;
        this.mensajeResult.textContent = mensaje;
    }
    ocultarResultado() {
        this.resultadoCont.style.display = 'none';
        this.mensajeResult.textContent = '';
    }
}
// Límite acordado: 90 MB (bajo el tope de 100 MB de Cloudflare Free)
UploadVideo.MAX_BYTES = 90 * 1024 * 1024;
// ============================================================================
// INICIALIZACIÓN
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
    new UploadVideo();
});
// ============================================================================
// FUNCIÓN GLOBAL: Eliminar video desde botón en la galería
// ============================================================================
/**
 * Elimina un video vía AJAX y remueve su tarjeta del DOM con animación.
 *
 * @param videoId   ID del VideoOrden en la base de datos
 * @param url       URL de la vista eliminar_video (generada con {% url %})
 * @param csrfToken Token CSRF del formulario
 */
function eliminarVideo(videoId, url, csrfToken) {
    if (!confirm('¿Estás seguro de que deseas eliminar este video? Esta acción no se puede deshacer.')) {
        return;
    }
    const body = new FormData();
    body.append('csrfmiddlewaretoken', csrfToken);
    fetch(url, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        body,
    })
        .then(r => r.json())
        .then((data) => {
        if (data.success) {
            const tarjeta = document.querySelector(`[data-video-id="${videoId}"]`);
            if (tarjeta) {
                tarjeta.style.transition = 'opacity 0.3s ease';
                tarjeta.style.opacity = '0';
                setTimeout(() => tarjeta.remove(), 320);
            }
        }
        else {
            alert(`Error al eliminar el video: ${data.error || 'Error desconocido'}`);
        }
    })
        .catch(() => {
        alert('Error de conexión al intentar eliminar el video. Intenta de nuevo.');
    });
}
//# sourceMappingURL=upload_video.js.map