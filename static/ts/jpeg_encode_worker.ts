/**
 * Worker de compresión JPEG (cámara integrada).
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este script NO corre en la página (no tiene acceso a botones ni al video).
 * Corre en un hilo aparte del navegador (Web Worker). Así, cuando comprimimos
 * una foto a JPEG, la interfaz de la cámara no se “congela”.
 *
 * Flujo:
 * 1. El hilo principal captura el frame en un canvas y crea un ImageBitmap.
 * 2. Nos envía ese bitmap + calidad JPEG (0.75 o 0.95) por postMessage.
 * 3. Dibujamos el bitmap en un OffscreenCanvas (canvas sin DOM).
 * 4. convertToBlob() genera el JPEG aquí, fuera del hilo de la UI.
 * 5. Devolvemos el Blob al hilo principal con el mismo id de la petición.
 *
 * IMPORTANTE: este archivo se compila con tsconfig.jpeg_worker.json (lib WebWorker).
 * No uses import/export: es un Worker clásico cargado con new Worker(url).
 */

/** Mensaje que llega desde camara_integrada.ts */
interface JpegEncodeRequest {
    id: number;
    bitmap: ImageBitmap;
    quality: number;
}

/** Respuesta exitosa o de error hacia el hilo principal */
interface JpegEncodeResponseOk {
    id: number;
    ok: true;
    blob: Blob;
}

interface JpegEncodeResponseError {
    id: number;
    ok: false;
    error: string;
}

type JpegEncodeResponse = JpegEncodeResponseOk | JpegEncodeResponseError;

/**
 * Comprime un ImageBitmap a JPEG usando OffscreenCanvas.
 *
 * @param bitmap Imagen ya capturada (transferida desde el hilo principal)
 * @param quality Calidad JPEG 0–1 (ej. 0.95 o 0.75)
 * @returns Blob JPEG listo para subir
 */
async function comprimirBitmapAJpeg(bitmap: ImageBitmap, quality: number): Promise<Blob> {
    // OffscreenCanvas vive solo en memoria: no pinta nada en pantalla.
    const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
    const ctx = canvas.getContext('2d');

    if (!ctx) {
        bitmap.close();
        throw new Error('No se pudo obtener contexto 2D del OffscreenCanvas');
    }

    // Copiar píxeles del bitmap al canvas offscreen
    ctx.drawImage(bitmap, 0, 0);

    // Liberar el bitmap cuanto antes (buena práctica de memoria)
    bitmap.close();

    // Aquí ocurre el trabajo pesado de CPU: codificar JPEG
    return canvas.convertToBlob({
        type: 'image/jpeg',
        quality: quality,
    });
}

/**
 * Maneja cada petición de compresión enviada desde la cámara.
 */
self.onmessage = async (event: MessageEvent<JpegEncodeRequest>): Promise<void> => {
    const data = event.data;
    const id = data?.id;

    // Validación defensiva: si el mensaje no trae lo esperado, avisamos y salimos
    if (typeof id !== 'number' || !data.bitmap) {
        const respuestaError: JpegEncodeResponseError = {
            id: typeof id === 'number' ? id : -1,
            ok: false,
            error: 'Mensaje inválido: se requiere id y bitmap',
        };
        self.postMessage(respuestaError);
        return;
    }

    try {
        const quality = typeof data.quality === 'number' ? data.quality : 0.95;
        const blob = await comprimirBitmapAJpeg(data.bitmap, quality);

        const respuestaOk: JpegEncodeResponseOk = {
            id: id,
            ok: true,
            blob: blob,
        };
        // Blob se clona por structured clone; no hace falta transfer list
        self.postMessage(respuestaOk);
    } catch (err) {
        // Si el bitmap aún no se cerró en un fallo temprano, intentar cerrarlo
        try {
            data.bitmap.close();
        } catch {
            // Ignorar: ya estaba cerrado o no es válido
        }

        const mensaje = err instanceof Error ? err.message : String(err);
        const respuestaError: JpegEncodeResponseError = {
            id: id,
            ok: false,
            error: mensaje,
        };
        self.postMessage(respuestaError);
    }
};
