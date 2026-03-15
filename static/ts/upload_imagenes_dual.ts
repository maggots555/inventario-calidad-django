// ============================================================================
// SISTEMA DUAL DE SUBIDA DE IMÁGENES - GALERÍA Y CÁMARA
// Versión 8.0 - Transacción única + Caché IndexedDB + Auto-recarga
// ============================================================================

/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * 
 * Este módulo maneja la subida de imágenes con dos opciones:
 * 1. Selección desde galería (múltiples archivos a la vez)
 * 2. Captura con cámara (acceso directo en móviles)
 * 
 * Funcionalidades:
 * - Unifica archivos de ambos inputs en un solo array interno (fuente de verdad)
 * - Muestra preview con miniaturas
 * - Permite eliminar imágenes individuales
 * - Valida límites (30 imágenes, 50MB cada una, 95MB total)
 * - Construye FormData y envía via XHR con barra de progreso
 * - Diagnóstico avanzado de errores de red (sin internet, Cloudflare, timeout)
 * - Protección beforeunload durante subida activa
 * - NUEVO v7.0: Caché IndexedDB — las imágenes sobreviven una recarga de página
 * - NUEVO v7.0: Auto-recarga cuando Cloudflare Tunnel corta la conexión
 * 
 * CHANGELOG:
 * 
 * v8.0 (Marzo 2026):
 * - ✅ TRANSACCIÓN ÚNICA: Se eliminó la subida por lotes. Todas las imágenes
 *   se envían al servidor en una sola petición HTTP.
 * - ✅ SIMPLIFICACIÓN: enviarTodo() + enviarXHR() reemplazan
 *   enviarPorLotes() + enviarLote(). Código más limpio y predecible.
 * - ✅ CACHÉ SIGUE ACTIVO: El sistema de caché IndexedDB (v7.0) persiste.
 *   Si Cloudflare corta la conexión, las imágenes se recuperan del caché
 *   tras la recarga automática de la página.
 * - ✅ ELIMINADO: BATCH_SIZE, loteActual, totalLotes, removerImagenesSubidas,
 *   mostrarResumenFinal, BatchResult interface.
 *
 * v7.0 (Marzo 2026):
 * - ✅ CACHÉ INDEXEDDB: Al seleccionar imágenes se guardan automáticamente en
 *   IndexedDB (base de datos del navegador). Si la página se recarga por un
 *   fallo de Cloudflare Tunnel, las imágenes se recuperan automáticamente.
 * - ✅ AUTO-RECARGA EN FALLO: Cuando todos los reintentos de un lote fallan
 *   (Cloudflare cortó el túnel), se guarda el estado en IndexedDB y se recarga
 *   la página automáticamente con un countdown visual de 5 segundos.
 * - ✅ RESTAURACIÓN AUTOMÁTICA: Al cargar la página, se verifica si hay imágenes
 *   pendientes en caché para la misma orden. Si las hay, se restauran y aparece
 *   un banner "X imágenes recuperadas — presiona Subir para completar".
 * - ✅ LIMPIEZA INTELIGENTE: El caché se borra SOLO cuando la subida es 100%
 *   exitosa, o cuando el usuario presiona "Limpiar todo" manualmente.
 *   Los registros con más de 24 horas se eliminan automáticamente al inicio.
 * - ✅ SE ELIMINAN LOS REINTENTOS MANUALES: Ya no se muestra el botón
 *   "Subir" para reintentar después de un fallo de red — se recarga la página.
 * - ✅ MAX_RETRIES reducido a 1: Un solo reintento rápido para detectar glitches
 *   transitorios; si falla, se va directo a auto-recarga.
 *
 * v6.0 (Febrero 2026):
 * - ✅ SUBIDA POR LOTES: Las imágenes se envían en lotes de 5 (configurable)
 *   para evitar que Cloudflare Tunnel corte conexiones grandes.
 * - ✅ REINTENTOS AUTOMÁTICOS: Cada lote fallido se reintenta hasta 2 veces
 *   con backoff exponencial (3s, 6s) — nueva conexión HTTP cada reintento.
 * - ✅ ÉXITO PARCIAL: Si un lote falla, los anteriores ya están guardados.
 *   Las imágenes pendientes quedan seleccionadas para reintento manual.
 * - ✅ PROGRESO DE DOS NIVELES: Barra global + info por lote.
 * - ✅ SIN CAMBIOS EN SERVIDOR: Django procesa lo que recibe, igual que antes.
 *
 * v5.0 (Febrero 2026):
 * - ✅ MIGRACIÓN COMPLETA: Toda la lógica de subida (submit, FormData, XHR,
 *   progreso, errores, beforeunload) movida desde el JS inline del template
 *   a este módulo TypeScript. Un solo punto de control con tipado fuerte.
 * - ✅ ELIMINADO: Input oculto #imagenesUnificadas y transferirArchivosAInputUnificado()
 * - ✅ ELIMINADO: resincronizarInput() (ya no hay input que sincronizar)
 * - ✅ Los IDs de los campos tipo/descripción se leen desde data-* attributes del <form>
 * - ✅ Sin fallback: si el TypeScript no carga, el botón queda disabled
 * 
 * v3.1 (Febrero 2026):
 * - API pública getArchivos(): devuelve archivos desde array interno
 * - API pública resincronizarInput(): restaura input oculto tras error
 * - FIX: Elimina dependencia frágil del input oculto como intermediario
 * 
 * v3.0 (Febrero 2026):
 * - Validación de límite total del request (95MB)
 * - Barra de progreso visual del límite del servidor
 * - Bloqueo automático del botón si excede 95MB
 * - Sistema de colores (verde < 76MB, amarillo 76-95MB, rojo > 95MB)
 * - Panel de resumen con "X MB / 95 MB permitidos"
 * 
 * v2.0 (Enero 2026):
 * - Validación de doble-click unificada con el template
 * - Panel de resumen de tamaño antes de subir
 * - Sistema de toasts Bootstrap para errores descriptivos
 * - Barra de progreso mejorada con conteo individual
 * - API pública para integración con scripts externos
 */

interface ImagenPreview {
    file: File;
    id: string;
    previewUrl: string;
}

// Interface para resumen de subida (API pública)
interface ResumenSubida {
    cantidad: number;
    tamanioTotal: number;
    tamanioMB: string;
    archivosGrandes: string[];
    archivosAdvertencia: string[];
    listoParaSubir: boolean;
    excedeLimiteTotal: boolean;    // Si excede 95MB del request
    cercaDelLimite: boolean;       // Si está cerca del límite (>76MB)
}

// Interface para resultado de la subida
interface UploadResult {
    success: boolean;            // Si la subida fue correcta
    imagenesGuardadas: number;   // Cantidad guardadas en el servidor
    imagenesOmitidas: string[];  // Nombres de imágenes omitidas
    errores: string[];           // Errores de procesamiento individual
    cambioEstado: boolean;       // Si cambió el estado de la orden
    message: string;             // Mensaje del servidor
    archivosEnviados: number;    // Cantidad de archivos enviados
    tipoImagen: string;          // Tipo de imagen subida ('egreso', 'ingreso', etc.)
    egresoCorreoYaEnviado: boolean; // Si ya existe historial de envío de correo de egreso
}

// ============================================================================
// v7.0: CACHÉ IndexedDB — Persistencia de imágenes entre recargas de página
// ============================================================================

/**
 * Estructura de una imagen individual guardada en IndexedDB.
 * Guardamos el ArrayBuffer en lugar del objeto File porque los objetos File
 * no se pueden serializar y no sobreviven una recarga de página.
 * Al restaurar, reconstruimos un File nuevo desde este ArrayBuffer.
 */
interface CachedImage {
    id: string;          // ID único generado al seleccionar (img_timestamp_random)
    name: string;        // Nombre del archivo original
    type: string;        // MIME type (image/jpeg, image/png, etc.)
    lastModified: number;// Timestamp de última modificación del archivo
    size: number;        // Tamaño en bytes (para validaciones)
    buffer: ArrayBuffer; // Contenido binario del archivo (sobrevive recargas)
}

/**
 * Registro completo guardado en IndexedDB por cada sesión de subida.
 * La clave primaria es `ordenUrl` (ruta de la URL actual), así las imágenes
 * quedan vinculadas a una orden específica y no se mezclan entre órdenes.
 */
interface CacheRecord {
    ordenUrl: string;    // window.location.pathname — clave primaria
    tipo: string;        // Tipo de imagen seleccionado (ingreso, diagnostico, etc.)
    descripcion: string; // Descripción opcional escrita por el usuario
    imagenes: CachedImage[];
    savedAt: number;     // Timestamp Unix para poder expirar registros viejos
}

/**
 * CLASE: ImageCache
 * 
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * IndexedDB es una base de datos que el navegador mantiene en el dispositivo.
 * A diferencia de localStorage (que solo guarda texto), IndexedDB puede guardar
 * archivos binarios grandes (imágenes, videos, etc.) — exactamente lo que necesitamos.
 * 
 * Esta clase encapsula todas las operaciones con IndexedDB:
 * - guardar()      → escribe las imágenes pendientes
 * - cargar()       → lee las imágenes de una orden específica
 * - limpiar()      → borra el registro de una orden (tras subida exitosa)
 * - limpiarViejos() → borra registros con más de 24 horas (limpieza automática)
 * 
 * Todas las operaciones son async porque IndexedDB trabaja con callbacks
 * asincrónicos (como las peticiones de red).
 */
class ImageCache {
    private static readonly DB_NAME    = 'sigma-upload-cache';
    private static readonly DB_VERSION = 1;
    private static readonly STORE_NAME = 'pending-uploads';
    private static readonly TTL_MS     = 24 * 60 * 60 * 1000; // 24 horas en ms

    /** Abre (o crea) la base de datos IndexedDB. Retorna una Promise con la conexión. */
    private static abrirDB(): Promise<IDBDatabase> {
        return new Promise((resolve, reject) => {
            const req = indexedDB.open(ImageCache.DB_NAME, ImageCache.DB_VERSION);

            // onupgradeneeded se ejecuta la primera vez que se crea la DB,
            // o cuando incrementamos DB_VERSION. Aquí definimos la estructura.
            req.onupgradeneeded = (event) => {
                const db = (event.target as IDBOpenDBRequest).result;
                if (!db.objectStoreNames.contains(ImageCache.STORE_NAME)) {
                    // Crear el "almacén" (equivalente a una tabla SQL).
                    // keyPath: 'ordenUrl' significa que la clave primaria
                    // es el campo `ordenUrl` de cada objeto guardado.
                    db.createObjectStore(ImageCache.STORE_NAME, { keyPath: 'ordenUrl' });
                }
            };

            req.onsuccess = () => resolve(req.result);
            req.onerror   = () => reject(req.error);
        });
    }

    /**
     * Convierte un objeto File a CachedImage leyendo su contenido binario.
     * Usamos FileReader para leer el archivo como ArrayBuffer.
     * 
     * EXPLICACIÓN: file.arrayBuffer() es la API moderna que retorna una Promise.
     * Está disponible en Chrome 76+, Firefox 69+, Safari 14+, Android 9+.
     */
    private static async fileToCached(file: File, id: string): Promise<CachedImage> {
        const buffer = await file.arrayBuffer();
        return {
            id,
            name:         file.name,
            type:         file.type || 'image/jpeg',
            lastModified: file.lastModified,
            size:         file.size,
            buffer,
        };
    }

    /**
     * Reconstruye un objeto File desde un CachedImage almacenado.
     * new File([buffer], name, { type, lastModified }) es la API estándar
     * disponible en todos los navegadores modernos (Android 7+).
     */
    static cachedToFile(cached: CachedImage): File {
        return new File([cached.buffer], cached.name, {
            type:         cached.type,
            lastModified: cached.lastModified,
        });
    }

    /**
     * Guarda las imágenes pendientes en IndexedDB.
     * Se llama cada vez que se agrega, elimina o modifica la selección.
     * 
     * @param ordenUrl   - Ruta de la orden actual (window.location.pathname)
     * @param tipo       - Tipo de imagen seleccionado (radio button)
     * @param descripcion - Texto del campo descripción
     * @param imagenes   - Pares { file, id } del array imagenesSeleccionadas
     */
    static async guardar(
        ordenUrl: string,
        tipo: string,
        descripcion: string,
        imagenes: Array<{ file: File; id: string }>
    ): Promise<void> {
        if (imagenes.length === 0) {
            // Si no hay imágenes, borramos el registro para no dejar caché vacío
            await ImageCache.limpiar(ordenUrl);
            return;
        }

        try {
            const cachedImagenes = await Promise.all(
                imagenes.map(img => ImageCache.fileToCached(img.file, img.id))
            );

            const record: CacheRecord = {
                ordenUrl,
                tipo,
                descripcion,
                imagenes: cachedImagenes,
                savedAt: Date.now(),
            };

            const db    = await ImageCache.abrirDB();
            const tx    = db.transaction(ImageCache.STORE_NAME, 'readwrite');
            const store = tx.objectStore(ImageCache.STORE_NAME);
            store.put(record); // put = insert or update (upsert)
            db.close();

            console.log(`💾 Caché: ${imagenes.length} imagen(es) guardada(s) para ${ordenUrl}`);
        } catch (e) {
            // El caché es best-effort: si falla, no interrumpimos el flujo principal
            console.warn('⚠️ No se pudo guardar en caché IndexedDB:', e);
        }
    }

    /**
     * Carga el registro de imágenes pendientes para una orden específica.
     * Retorna null si no hay caché o si el registro expiró (+24h).
     */
    static async cargar(ordenUrl: string): Promise<CacheRecord | null> {
        try {
            const db    = await ImageCache.abrirDB();
            const tx    = db.transaction(ImageCache.STORE_NAME, 'readonly');
            const store = tx.objectStore(ImageCache.STORE_NAME);

            const record: CacheRecord | undefined = await new Promise((resolve, reject) => {
                const req = store.get(ordenUrl);
                req.onsuccess = () => resolve(req.result as CacheRecord | undefined);
                req.onerror   = () => reject(req.error);
            });
            db.close();

            if (!record) return null;

            // Verificar expiración: si tiene más de 24h, ignorar y borrar
            if (Date.now() - record.savedAt > ImageCache.TTL_MS) {
                console.log('🗑️ Caché expirado (> 24h) — descartando');
                await ImageCache.limpiar(ordenUrl);
                return null;
            }

            return record;
        } catch (e) {
            console.warn('⚠️ No se pudo leer el caché IndexedDB:', e);
            return null;
        }
    }

    /**
     * Elimina el registro de caché de una orden específica.
     * Se llama tras subida exitosa o al limpiar la selección manualmente.
     */
    static async limpiar(ordenUrl: string): Promise<void> {
        try {
            const db    = await ImageCache.abrirDB();
            const tx    = db.transaction(ImageCache.STORE_NAME, 'readwrite');
            const store = tx.objectStore(ImageCache.STORE_NAME);
            store.delete(ordenUrl);
            db.close();
            console.log(`🗑️ Caché limpiado para ${ordenUrl}`);
        } catch (e) {
            console.warn('⚠️ No se pudo limpiar el caché IndexedDB:', e);
        }
    }

    /**
     * Elimina todos los registros con más de 24 horas.
     * Se llama al inicializar la página para no acumular datos viejos.
     */
    static async limpiarViejos(): Promise<void> {
        try {
            const db    = await ImageCache.abrirDB();
            const tx    = db.transaction(ImageCache.STORE_NAME, 'readwrite');
            const store = tx.objectStore(ImageCache.STORE_NAME);

            // getAll() retorna todos los registros del store
            const todos: CacheRecord[] = await new Promise((resolve, reject) => {
                const req = store.getAll();
                req.onsuccess = () => resolve(req.result as CacheRecord[]);
                req.onerror   = () => reject(req.error);
            });

            const ahora = Date.now();
            let eliminados = 0;
            for (const record of todos) {
                if (ahora - record.savedAt > ImageCache.TTL_MS) {
                    store.delete(record.ordenUrl);
                    eliminados++;
                }
            }

            db.close();
            if (eliminados > 0) {
                console.log(`🗑️ Caché: ${eliminados} registro(s) expirado(s) eliminado(s)`);
            }
        } catch (e) {
            console.warn('⚠️ No se pudo limpiar registros viejos de IndexedDB:', e);
        }
    }
}

// ============================================================================

class UploadImagenesDual {
    // Elementos del DOM - Selección de archivos
    private inputGaleria: HTMLInputElement | null;
    private inputCamara: HTMLInputElement | null;
    private previewContainer: HTMLElement | null;
    private contenedorMiniaturas: HTMLElement | null;
    private btnSubir: HTMLButtonElement | null;
    private btnLimpiarTodo: HTMLButtonElement | null;
    private cantidadSpan: HTMLElement | null;
    
    // NUEVO v5.0: Elementos del DOM - Formulario y subida
    private formElement: HTMLFormElement | null;
    private progresoDiv: HTMLElement | null;
    private barraProgreso: HTMLElement | null;
    private textoProgreso: HTMLElement | null;
    private porcentajeProgreso: HTMLElement | null;
    private infoArchivos: HTMLElement | null;
    
    // NUEVO v5.0: IDs de campos Django (leídos desde data-* attributes del form)
    // NOTA: tipoSelectId ya no se usa — el tipo ahora se lee desde input[name="tipo"]:checked
    private descripcionInputId: string = '';
    
    // Panel de resumen
    private panelResumen: HTMLElement | null = null;
    
    // Contenedor de toasts
    private toastContainer: HTMLElement | null = null;
    
    // Array de imágenes seleccionadas (FUENTE DE VERDAD)
    private imagenesSeleccionadas: ImagenPreview[] = [];
    
    // Límites de validación
    private readonly MAX_IMAGENES = 30;
    private readonly MAX_SIZE_MB = 50;
    private readonly MAX_SIZE_BYTES = this.MAX_SIZE_MB * 1024 * 1024;
    private readonly ADVERTENCIA_SIZE_MB = 40; // Advertir si > 40MB
    
    // Límite total del request (alineado con Cloudflare Free: 100MB max)
    private readonly MAX_REQUEST_SIZE_MB = 95;  // DATA_UPLOAD_MAX_MEMORY_SIZE
    private readonly MAX_REQUEST_SIZE_BYTES = this.MAX_REQUEST_SIZE_MB * 1024 * 1024;
    private readonly ADVERTENCIA_REQUEST_MB = 76; // Advertir al 80% del límite
    
    // NUEVO v5.0: Timeout de XHR (10 minutos, alineado con Gunicorn y Nginx)
    private readonly XHR_TIMEOUT_MS = 600000;
    
    // Control de estado de procesamiento
    private estaProcesando: boolean = false;
    private archivosListos: boolean = false;
    
    // Control de envío (para evitar doble-click)
    private enviando: boolean = false;
    private ultimoClickSubir: number = 0;
    private readonly DEBOUNCE_MS = 1500; // 1.5 segundos entre clicks
    
    // NUEVO v5.0: Flag para protección beforeunload
    private subiendoImagenes: boolean = false;

    // v7.0: Clave de caché — ruta de la URL actual (identifica la orden)
    // Ejemplo: '/servicio_tecnico/detalle/123/' — única por orden
    private readonly cacheOrdenUrl: string;
    
    constructor() {
        // Elementos de selección de archivos
        this.inputGaleria = document.getElementById('inputGaleria') as HTMLInputElement;
        this.inputCamara = document.getElementById('inputCamara') as HTMLInputElement;
        this.previewContainer = document.getElementById('previewImagenes');
        this.contenedorMiniaturas = document.getElementById('contenedorMiniaturas');
        this.btnSubir = document.getElementById('btnSubirImagenes') as HTMLButtonElement;
        this.btnLimpiarTodo = document.getElementById('btnLimpiarTodo') as HTMLButtonElement;
        this.cantidadSpan = document.getElementById('cantidadImagenes');
        
        // NUEVO v5.0: Elementos del formulario y progreso
        this.formElement = document.getElementById('formSubirImagenes') as HTMLFormElement;
        this.progresoDiv = document.getElementById('progresoUpload');
        this.barraProgreso = document.getElementById('barraProgreso');
        this.textoProgreso = document.getElementById('textoProgreso');
        this.porcentajeProgreso = document.getElementById('porcentajeProgreso');
        this.infoArchivos = document.getElementById('infoArchivos');
        
        // NUEVO v5.0: Leer IDs de campos Django desde data-* attributes
        if (this.formElement) {
            this.descripcionInputId = this.formElement.dataset.descripcionId || '';
        }

        // v7.0: Inicializar clave de caché con la ruta actual
        this.cacheOrdenUrl = window.location.pathname;
        
        this.init();
    }
    
    private init(): void {
        // Crear contenedor de toasts si no existe
        this.crearContenedorToasts();
        
        // Crear panel de resumen
        this.crearPanelResumen();
        
        // Event listeners para los inputs de archivo
        if (this.inputGaleria) {
            this.inputGaleria.addEventListener('change', (e) => this.handleFileSelect(e));
        }
        
        // IMPORTANTE: El botón de cámara ahora abre el modal de cámara integrada
        // en lugar de usar el input file con capture
        const labelCamara = document.querySelector('label[for="inputCamara"]');
        if (labelCamara) {
            labelCamara.addEventListener('click', (e) => {
                e.preventDefault();
                this.abrirCamaraIntegrada();
            });
        }
        
        // Event listener para limpiar todo
        if (this.btnLimpiarTodo) {
            this.btnLimpiarTodo.addEventListener('click', () => this.limpiarTodo());
        }
        
        // ── NUEVO: Listeners en los radio buttons de tipo de imagen ──────────
        // Al cambiar el tipo seleccionado:
        //   1. Actualizamos el estado del botón "Subir" (requiere tipo elegido)
        //   2. Mostramos un aviso contextual debajo del selector
        this.inicializarRadioTipo();
        
        // Configurar callback de la cámara integrada
        this.configurarCamaraIntegrada();
        
        // NUEVO v5.0: Inicializar formulario de subida (submit handler + beforeunload)
        this.inicializarFormularioSubida();

        // v7.0: Limpiar registros de caché expirados (> 24h) — fire-and-forget
        ImageCache.limpiarViejos();

        // v7.0: Restaurar imágenes pendientes desde caché (si las hay)
        this.restaurarDesdeCache();

        // Botón manual de envío de imágenes de egreso (mostrado si no se envió vía modal)
        const btnEgreso = document.getElementById('btnEnviarImagenesEgreso');
        if (btnEgreso) {
            btnEgreso.addEventListener('click', () => this.mostrarModalEgresoEmail());
        }
        
        console.log('✅ Sistema dual de subida de imágenes v8.0 inicializado');
    }
    
    // =========================================================================
    // NUEVO: Selector de tipo de imagen (radio cards)
    // =========================================================================

    /**
     * Inicializa los listeners de los radio buttons de tipo de imagen.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Los radio buttons con name="tipo" controlan qué categoría de imagen se sube
     * (ingreso, diagnóstico, reparación, egreso, autorización).
     * Este método:
     *   1. Escucha cada cambio en los radio buttons
     *   2. Actualiza el botón "Subir" (solo se habilita si hay tipo + archivos)
     *   3. Muestra un aviso contextual informativo debajo del selector
     */
    private inicializarRadioTipo(): void {
        const radios = document.querySelectorAll<HTMLInputElement>('input[name="tipo"].tipo-imagen-radio');
        
        radios.forEach(radio => {
            radio.addEventListener('change', () => {
                // 1. Actualizar estado del botón subir
                this.actualizarEstadoBotonSubir();
                // 2. Mostrar aviso contextual del tipo elegido
                this.mostrarAvisoTipo(radio.value);
            });
        });
    }

    /**
     * Devuelve el valor del radio button de tipo actualmente seleccionado.
     * Retorna cadena vacía si ninguno está seleccionado.
     */
    private getTipoSeleccionado(): string {
        const checked = this.formElement
            ? this.formElement.querySelector<HTMLInputElement>('input[name="tipo"]:checked')
            : document.querySelector<HTMLInputElement>('input[name="tipo"]:checked');
        return checked ? checked.value : '';
    }

    /**
     * Muestra un aviso contextual debajo del selector de tipo.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Cada tipo de imagen tiene una implicación diferente en el flujo de trabajo:
     * - ingreso    → cambia la orden a "En Diagnóstico" automáticamente
     * - egreso     → cambia la orden a "Finalizado" automáticamente (¡irreversible!)
     * - los demás  → solo agregan fotos, sin cambio de estado
     * Informamos al usuario antes de que suba para que tome la decisión consciente.
     */
    private mostrarAvisoTipo(tipo: string): void {
        const avisoEl = document.getElementById('tipoImagenAviso');
        if (!avisoEl) return;

        type AvisoConfig = { clase: string; icono: string; texto: string };

        const avisos: Record<string, AvisoConfig> = {
            ingreso:      { clase: 'aviso-ingreso',      icono: 'bi-info-circle-fill',      texto: 'Subir como <strong>Ingreso</strong> cambiará el estado de la orden a <strong>En Diagnóstico</strong>.' },
            diagnostico:  { clase: 'aviso-diagnostico',  icono: 'bi-search',                texto: 'Fotos tomadas durante el <strong>diagnóstico</strong> del equipo. No cambia el estado de la orden.' },
            reparacion:   { clase: 'aviso-reparacion',   icono: 'bi-wrench-adjustable',     texto: 'Fotos del proceso de <strong>reparación</strong>. No cambia el estado de la orden.' },
            egreso:       { clase: 'aviso-egreso',       icono: 'bi-exclamation-triangle-fill', texto: '<strong>¡Atención!</strong> Subir como <strong>Egreso</strong> marcará la orden como <strong>Finalizada - Lista para Entrega</strong>.' },
            autorizacion: { clase: 'aviso-autorizacion', icono: 'bi-patch-check',           texto: 'Evidencia de <strong>autorización RHITSO</strong>. No cambia el estado de la orden.' },
            packing:      { clase: 'aviso-packing',      icono: 'bi-box-seam',               texto: 'Fotos del proceso de <strong>packing</strong> del equipo. No cambia el estado de la orden.' },
        };

        const config = avisos[tipo];
        if (!config) {
            avisoEl.className = 'tipo-imagen-aviso d-none mt-2';
            return;
        }

        avisoEl.className = `tipo-imagen-aviso ${config.clase} mt-2`;
        avisoEl.innerHTML = `<i class="bi ${config.icono}"></i><span>${config.texto}</span>`;
    }

    // =========================================================================
    // NUEVO v5.0: Formulario de subida (migrado desde JS inline del template)
    // =========================================================================
    
    /**
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Configura el formulario de subida de imágenes:
     * 1. Intercepta el submit del formulario HTML
     * 2. Construye un FormData con los archivos del array interno
     * 3. Envía via XHR con monitoreo de progreso
     * 4. Registra protección beforeunload para evitar cierre accidental
     */
    private inicializarFormularioSubida(): void {
        if (!this.formElement) {
            console.warn('⚠️ Formulario #formSubirImagenes no encontrado');
            return;
        }
        
        // Interceptar el submit del formulario
        this.formElement.addEventListener('submit', (e) => this.handleSubmit(e));
        
        // Registrar protección beforeunload
        window.addEventListener('beforeunload', (e) => this.advertenciaBeforeUnload(e));
        
        console.log('✅ Formulario de subida inicializado (submit handler + beforeunload)');
    }

    // =========================================================================
    // v7.0: RESTAURACIÓN DESDE CACHÉ IndexedDB
    // =========================================================================

    /**
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Esta función se ejecuta al cargar la página. Verifica si el navegador
     * tiene imágenes guardadas en IndexedDB para esta orden específica.
     * 
     * Esto ocurre cuando:
     * 1. La subida anterior falló por un corte de Cloudflare Tunnel
     * 2. El sistema guardó las imágenes pendientes en IndexedDB
     * 3. Recargó la página automáticamente
     * 
     * Si encuentra imágenes en caché, las reconstruye y las muestra listas
     * para que el usuario solo tenga que presionar "Subir" de nuevo.
     */
    private async restaurarDesdeCache(): Promise<void> {
        const record = await ImageCache.cargar(this.cacheOrdenUrl);
        if (!record || record.imagenes.length === 0) return;

        console.log(`🔄 [Caché] Restaurando ${record.imagenes.length} imagen(es) para ${this.cacheOrdenUrl}`);

        // Reconstruir objetos File desde los ArrayBuffers almacenados.
        // NOTA: Estos archivos ya fueron validados cuando se seleccionaron.
        // No repetimos la validación para no mostrar errores/advertencias falsos.
        for (const cached of record.imagenes) {
            try {
                const file = ImageCache.cachedToFile(cached);
                const previewUrl = URL.createObjectURL(file);
                this.imagenesSeleccionadas.push({ file, id: cached.id, previewUrl });
            } catch (e) {
                console.warn(`⚠️ No se pudo restaurar imagen '${cached.name}':`, e);
            }
        }

        if (this.imagenesSeleccionadas.length === 0) return;

        // Restaurar el tipo de imagen seleccionado (radio button)
        if (record.tipo) {
            const radio = this.formElement?.querySelector<HTMLInputElement>(
                `input[name="tipo"][value="${record.tipo}"]`
            );
            if (radio) {
                radio.checked = true;
                this.mostrarAvisoTipo(record.tipo);
            }
        }

        // Restaurar la descripción escrita por el usuario
        if (record.descripcion && this.descripcionInputId) {
            const descEl = document.getElementById(this.descripcionInputId) as HTMLInputElement | null;
            if (descEl) descEl.value = record.descripcion;
        }

        // Actualizar estado y UI
        this.archivosListos = true;
        this.actualizarPreview();
        this.actualizarEstadoBotonSubir();
        this.actualizarPanelResumen();

        // Mostrar banner de recuperación encima del formulario
        this.mostrarBannerRestauracion(this.imagenesSeleccionadas.length);

        console.log(`✅ [Caché] ${this.imagenesSeleccionadas.length} imagen(es) restaurada(s) correctamente`);
    }

    /**
     * Muestra un banner informativo cuando se restauraron imágenes desde caché.
     * Se inyecta dinámicamente ANTES del formulario de subida.
     */
    private mostrarBannerRestauracion(cantidad: number): void {
        if (!this.formElement) return;

        // Evitar duplicados
        const existente = document.getElementById('cacheBannerRestauracion');
        if (existente) existente.remove();

        const banner = document.createElement('div');
        banner.id = 'cacheBannerRestauracion';
        banner.className = 'alert alert-info alert-dismissible d-flex align-items-start gap-2 mb-3';
        banner.setAttribute('role', 'alert');
        banner.innerHTML = `
            <i class="bi bi-arrow-repeat fs-5 flex-shrink-0"></i>
            <div>
                <strong>${cantidad} imagen${cantidad !== 1 ? 'es' : ''} recuperada${cantidad !== 1 ? 's' : ''} automáticamente.</strong>
                La página se recargó porque la conexión se cortó durante la subida anterior.
                Tus imágenes siguen seleccionadas — presiona <strong>Subir</strong> para completar la carga.
            </div>
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Cerrar"></button>
        `;

        // Insertar antes del formulario
        this.formElement.parentNode?.insertBefore(banner, this.formElement);
    }

    /**
     * Sincroniza el estado actual de las imágenes seleccionadas con IndexedDB.
     * Se llama después de cualquier cambio en la selección (agregar, eliminar).
     * 
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Esta función es "fire-and-forget" — la llamamos sin await porque:
     * 1. No necesitamos esperar a que termine para continuar con la UI
     * 2. Si falla, es un error menor que no debe interrumpir la experiencia
     * 3. Guardamos también el tipo y descripción actuales para poder restaurarlos
     */
    private sincronizarCache(): void {
        const tipo = this.getTipoSeleccionado();
        const descEl = this.descripcionInputId
            ? document.getElementById(this.descripcionInputId) as HTMLInputElement | null
            : null;
        const descripcion = descEl?.value ?? '';

        // fire-and-forget: no await, la UI no debe esperar
        ImageCache.guardar(
            this.cacheOrdenUrl,
            tipo,
            descripcion,
            this.imagenesSeleccionadas.map(img => ({ file: img.file, id: img.id }))
        );
    }
    
    /**
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Este es el handler principal del submit. Cuando el usuario hace clic en
     * "Subir Imágenes", esta función:
     * 1. Previene el envío normal del formulario (lo haremos nosotros con XHR)
     * 2. Valida que haya archivos y que el sistema esté listo
     * 3. Construye un FormData con los archivos del array interno
     * 4. Envía con XHR para poder mostrar barra de progreso
     */
    private handleSubmit(e: Event): void {
        e.preventDefault(); // Prevenir envío normal del formulario
        
        // Verificar si puede enviar (no procesando, no enviando, hay archivos)
        if (!this.puedeEnviar()) {
            console.warn('⚠️ El sistema está procesando o no está listo. Ignorando submit.');
            
            if (this.getEstaEnviando()) {
                this.mostrarToast('Ya hay una subida en progreso. Por favor espera.', 'warning');
            } else if (this.getEstaProcesando()) {
                this.mostrarToast('Los archivos aún se están procesando. Espera un momento.', 'info');
            } else {
                this.mostrarToast('Selecciona al menos una imagen antes de subir.', 'warning');
            }
            return;
        }
        
        // Marcar como enviando para bloquear el botón
        this.marcarEnviando();
        
        // Obtener archivos desde el array interno (fuente de verdad)
        const archivosParaSubir = this.getArchivos();
        
        // Validar que haya archivos
        if (archivosParaSubir.length === 0) {
            this.mostrarToast('Por favor selecciona al menos una imagen para subir.', 'warning');
            this.marcarFinEnvio();
            return;
        }
        
        // ── Confirmación extra para tipo EGRESO ──────────────────────────────
        // EXPLICACIÓN: Subir como "egreso" cambia el estado de la orden a
        // "Finalizado - Listo para Entrega" de forma automática en el servidor.
        // Al ser una acción de alto impacto y con difícil reversión, pedimos
        // confirmación explícita al usuario antes de continuar.
        const tipoActual = this.getTipoSeleccionado();
        if (tipoActual === 'egreso') {
            const confirmar = confirm(
                '⚠️ Estás a punto de subir imágenes de EGRESO.\n\n' +
                'Esto marcará la orden como "Finalizada - Lista para Entrega" automáticamente.\n\n' +
                '¿Deseas continuar?'
            );
            if (!confirmar) {
                // Usuario canceló — devolver el botón a su estado normal
                this.marcarFinEnvio();
                return;
            }
        }
        
        console.log(`📤 Enviando ${archivosParaSubir.length} imagen(es) en una sola transacción`);
        
        // Deshabilitar formulario durante la subida
        this.deshabilitarFormulario();
        
        // Mostrar barra de progreso
        if (this.progresoDiv) this.progresoDiv.style.display = 'block';
        if (this.barraProgreso) this.barraProgreso.style.width = '0%';
        if (this.textoProgreso) this.textoProgreso.textContent = 'Iniciando subida...';
        if (this.porcentajeProgreso) this.porcentajeProgreso.textContent = '0%';
        
        // Activar protección beforeunload
        this.subiendoImagenes = true;
        
        // Iniciar subida (transacción única)
        this.enviarTodo(archivosParaSubir);
    }
    
    /**
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Construye el FormData con todos los datos necesarios para el servidor:
     * - Token CSRF (seguridad de Django)
     * - Tipo de formulario ('subir_imagenes')
     * - Tipo de imagen seleccionado (ingreso, proceso, etc.)
     * - Descripción opcional
     * - Los archivos de imagen (con nombre 'imagenes' que espera Django)
     */
    private construirFormData(archivos: File[]): FormData {
        const formData = new FormData();
        
        // Agregar token CSRF
        if (this.formElement) {
            const csrfInput = this.formElement.querySelector('input[name="csrfmiddlewaretoken"]') as HTMLInputElement;
            if (csrfInput) {
                formData.append('csrfmiddlewaretoken', csrfInput.value);
            }
        }
        
        // Agregar tipo de formulario
        formData.append('form_type', 'subir_imagenes');
        
        // Agregar tipo de imagen desde los radio buttons (input[name="tipo"]:checked)
        // EXPLICACIÓN: Ya no usamos un <select> sino radio buttons con name="tipo".
        // Buscamos dentro del formulario el radio que esté marcado.
        const tipoChecked = this.formElement
            ? this.formElement.querySelector<HTMLInputElement>('input[name="tipo"]:checked')
            : document.querySelector<HTMLInputElement>('input[name="tipo"]:checked');
        if (tipoChecked) {
            formData.append('tipo', tipoChecked.value);
        }
        
        // Agregar descripción desde el input de Django
        if (this.descripcionInputId) {
            const descripcionInput = document.getElementById(this.descripcionInputId) as HTMLInputElement;
            if (descripcionInput) {
                formData.append('descripcion', descripcionInput.value || '');
            }
        }
        
        // Agregar cada archivo con el nombre 'imagenes'
        // (Django los recibe con request.FILES.getlist('imagenes'))
        archivos.forEach(archivo => {
            formData.append('imagenes', archivo, archivo.name);
        });
        
        return formData;
    }
    
    // =========================================================================
    // v8.0: SUBIDA EN TRANSACCIÓN ÚNICA (con caché IndexedDB para fallos)
    // =========================================================================
    
    /**
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Envía TODAS las imágenes al servidor en una sola petición HTTP.
     * 
     * v8.0: Se eliminó la subida por lotes. El sistema de caché IndexedDB (v7.0)
     * ya resuelve el problema de desconexiones de Cloudflare: si se corta la
     * conexión, la página se recarga automáticamente y las imágenes se recuperan
     * del caché, listas para reintentar la subida completa.
     * 
     * Escenarios posibles:
     * 1. Éxito → limpiar caché, mostrar mensaje verde, recargar página
     * 2. Error del servidor → mostrar mensaje, rehabilitar formulario
     * 3. Error de red (Cloudflare) → guardar en caché, auto-recargar
     */
    private async enviarTodo(archivos: File[]): Promise<void> {
        const totalBytes = archivos.reduce((sum, f) => sum + f.size, 0);
        const totalMB = (totalBytes / (1024 * 1024)).toFixed(2);
        
        // Mostrar info inicial
        if (this.infoArchivos) {
            this.infoArchivos.innerHTML = `
                <div class="d-flex align-items-center justify-content-between flex-wrap">
                    <span><i class="bi bi-collection"></i> <strong>${archivos.length}</strong> imagen${archivos.length !== 1 ? 'es' : ''}</span>
                    <span class="badge bg-secondary">${totalMB} MB total</span>
                </div>
            `;
        }
        
        try {
            const resultado = await this.enviarXHR(archivos);
            
            // Desactivar protección beforeunload
            this.subiendoImagenes = false;
            this.marcarFinEnvio();
            
            if (resultado.success) {
                // ═══ ÉXITO: Todas las imágenes se subieron correctamente ═══
                if (this.barraProgreso) {
                    this.barraProgreso.classList.remove('progress-bar-animated', 'progress-bar-striped', 'bg-warning');
                    this.barraProgreso.classList.add('bg-success');
                    this.barraProgreso.style.width = '100%';
                }
                if (this.textoProgreso) this.textoProgreso.textContent = '¡Completado!';
                if (this.porcentajeProgreso) this.porcentajeProgreso.textContent = '✓';
                
                let html = `
                    <div class="d-flex align-items-center text-success">
                        <i class="bi bi-check-circle-fill me-2"></i>
                        <span>✅ ${resultado.imagenesGuardadas} imagen(es) subida(s) correctamente.</span>
                    </div>
                `;
                
                if (resultado.errores.length > 0) {
                    html += `
                        <div class="mt-1">
                            <small class="text-danger">
                                <i class="bi bi-x-circle"></i> ${resultado.errores.length} error(es) menores al procesar
                            </small>
                        </div>
                    `;
                }
                
                if (this.infoArchivos) this.infoArchivos.innerHTML = html;
                
                // Limpiar selección y caché
                this.limpiarDespuesDeExito();
                
                // Detectar si fue egreso para mostrar modal de correo
                const esEgreso = resultado.tipoImagen === 'egreso';
                if (esEgreso && !resultado.egresoCorreoYaEnviado) {
                    this.mostrarModalEgresoEmail();
                } else {
                    setTimeout(() => { window.location.reload(); }, 1500);
                }
            } else {
                // ═══ ERROR DEL SERVIDOR (respondió pero con error) ═══
                if (this.barraProgreso) {
                    this.barraProgreso.classList.remove('bg-success', 'progress-bar-animated', 'progress-bar-striped');
                    this.barraProgreso.classList.add('bg-danger');
                    this.barraProgreso.style.width = '100%';
                }
                if (this.textoProgreso) this.textoProgreso.textContent = 'Error del servidor';
                if (this.porcentajeProgreso) this.porcentajeProgreso.textContent = '✗';
                
                if (this.infoArchivos) {
                    this.infoArchivos.innerHTML = `
                        <div class="text-danger">
                            <i class="bi bi-x-circle-fill me-1"></i>
                            ${resultado.message || 'Error al procesar las imágenes en el servidor.'}
                        </div>
                    `;
                }
                
                // Rehabilitar formulario para reintentar
                this.rehabilitarFormulario();
            }
        } catch (errorInfo: unknown) {
            // ═══ ERROR DE RED — Cloudflare cortó el túnel ═══
            const info = errorInfo as { tipo: string; diagnostico: string };
            console.error(`❌ Error de red: ${info.tipo}: ${info.diagnostico}`);
            
            // Desactivar protección beforeunload
            this.subiendoImagenes = false;
            this.marcarFinEnvio();
            
            if (this.barraProgreso) {
                this.barraProgreso.classList.remove('bg-success', 'progress-bar-animated', 'progress-bar-striped', 'bg-warning');
                this.barraProgreso.classList.add('bg-danger');
                this.barraProgreso.style.width = '100%';
            }
            if (this.textoProgreso) this.textoProgreso.textContent = 'Conexión cortada';
            if (this.porcentajeProgreso) this.porcentajeProgreso.textContent = '✗';
            
            // Guardar TODAS las imágenes en caché antes de recargar
            this.sincronizarCache();
            
            let html = `
                <div class="text-danger">
                    <i class="bi bi-x-circle-fill me-1"></i>
                    No se pudo completar la subida. La conexión fue cortada (Cloudflare Tunnel).
                </div>
                <div class="mt-1">
                    <small class="text-muted">
                        <i class="bi bi-shield-check"></i> Tus imágenes se guardaron localmente.
                        Recargando la página para restablecer la conexión...
                    </small>
                </div>
                <div class="mt-2 d-flex align-items-center gap-2">
                    <div class="spinner-border spinner-border-sm text-danger"></div>
                    <span id="cacheCountdown" class="text-danger fw-bold">Recargando en 5s...</span>
                </div>
            `;
            
            html += `
                <details class="mt-2">
                    <summary class="text-muted" style="cursor: pointer; font-size: 0.8rem;">
                        <i class="bi bi-bug"></i> Info técnica para soporte
                    </summary>
                    <div class="mt-1 p-2 bg-light rounded" style="font-size: 0.75rem; font-family: monospace;">
                        <div>• ${info.diagnostico}</div>
                        <div><strong>Hora:</strong> ${new Date().toLocaleString('es-MX')}</div>
                        <div><strong>Navegador:</strong> ${navigator.userAgent.substring(0, 80)}...</div>
                        <div><strong>Online:</strong> ${navigator.onLine ? 'Sí' : 'No'}</div>
                    </div>
                </details>
            `;
            
            if (this.infoArchivos) this.infoArchivos.innerHTML = html;
            
            // Countdown visual + recarga
            this.iniciarCountdownRecarga(5);
        }
    }
    
    /**
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Envía todas las imágenes al servidor usando XMLHttpRequest (XHR).
     * Retorna una Promise que se resuelve cuando el servidor responde,
     * o se rechaza si hay un error de red (Cloudflare cortó la conexión, etc.)
     */
    private enviarXHR(archivos: File[]): Promise<UploadResult> {
        return new Promise((resolve, reject) => {
            const formData = this.construirFormData(archivos);
            
            const tamanioTotal = archivos.reduce((sum, f) => sum + f.size, 0);
            const tamanioMB = (tamanioTotal / (1024 * 1024)).toFixed(2);
            
            console.log(`📤 Enviando ${archivos.length} archivo(s), ${tamanioMB} MB`);
            
            const xhr = new XMLHttpRequest();
            
            // Progreso de subida
            xhr.upload.addEventListener('progress', (e) => {
                if (!e.lengthComputable) return;
                
                const porcentaje = Math.round((e.loaded / e.total) * 100);
                
                if (this.barraProgreso) this.barraProgreso.style.width = porcentaje + '%';
                if (this.porcentajeProgreso) this.porcentajeProgreso.textContent = porcentaje + '%';
                
                if (porcentaje < 100) {
                    // Subiendo datos al servidor
                    if (this.textoProgreso) {
                        this.textoProgreso.textContent = `Subiendo... ${porcentaje}%`;
                    }
                    if (this.infoArchivos) {
                        const mbSubidos = (e.loaded / (1024 * 1024)).toFixed(2);
                        this.infoArchivos.innerHTML = `
                            <div class="d-flex align-items-center justify-content-between flex-wrap">
                                <span><i class="bi bi-cloud-arrow-up text-primary"></i> Subiendo <strong>${archivos.length}</strong> imagen${archivos.length !== 1 ? 'es' : ''}...</span>
                                <span class="badge bg-primary">${mbSubidos} / ${tamanioMB} MB</span>
                            </div>
                        `;
                    }
                } else {
                    // Datos enviados, servidor procesando
                    if (this.textoProgreso) {
                        this.textoProgreso.textContent = 'Procesando en servidor...';
                    }
                    if (this.barraProgreso) this.barraProgreso.classList.add('progress-bar-striped');
                    if (this.infoArchivos) {
                        this.infoArchivos.innerHTML = `
                            <div class="d-flex align-items-center">
                                <span class="spinner-border spinner-border-sm text-info me-2"></span>
                                <span>Comprimiendo y guardando ${archivos.length} imagen${archivos.length !== 1 ? 'es' : ''}...</span>
                            </div>
                        `;
                    }
                }
            });
            
            // Respuesta del servidor
            xhr.addEventListener('load', () => {
                if (this.barraProgreso) this.barraProgreso.classList.remove('progress-bar-striped');
                
                if (xhr.status === 200 || xhr.status === 500) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        resolve({
                            success: data.success,
                            imagenesGuardadas: data.imagenes_guardadas || 0,
                            imagenesOmitidas: data.imagenes_omitidas || [],
                            errores: data.errores || [],
                            cambioEstado: data.cambio_estado || false,
                            message: data.message || data.error || '',
                            archivosEnviados: archivos.length,
                            tipoImagen: data.tipo_imagen || '',
                            egresoCorreoYaEnviado: data.egreso_correo_ya_enviado || false,
                        });
                    } catch (e) {
                        console.error('Error al parsear respuesta:', e);
                        reject({ tipo: 'parse_error', diagnostico: 'Respuesta del servidor no válida' });
                    }
                } else {
                    reject({ tipo: `http_${xhr.status}`, diagnostico: `Error HTTP ${xhr.status}` });
                }
            });
            
            // Error de red — esto es lo que dispara Cloudflare al cortar
            xhr.addEventListener('error', () => {
                let tipo = 'desconocido';
                let diagnostico = '';
                
                if (!navigator.onLine) {
                    tipo = 'sin_internet';
                    diagnostico = 'Sin conexión a internet';
                } else if (tamanioTotal > 100 * 1024 * 1024) {
                    tipo = 'cloudflare_limite';
                    diagnostico = `Archivo(s) de ${tamanioMB}MB excede límite Cloudflare`;
                } else {
                    tipo = 'conexion_cortada';
                    diagnostico = 'Conexión cortada (Cloudflare Tunnel, red inestable)';
                }
                
                console.error(`[ERROR RED] Tipo: ${tipo} | ${diagnostico}`);
                reject({ tipo, diagnostico });
            });
            
            // Timeout
            xhr.addEventListener('timeout', () => {
                console.error(`[TIMEOUT] ${tamanioMB}MB, timeout=${this.XHR_TIMEOUT_MS / 1000}s`);
                reject({ tipo: 'timeout', diagnostico: `Timeout después de ${this.XHR_TIMEOUT_MS / 60000} minutos` });
            });
            
            // Abrir y enviar
            const url = this.formElement?.action || window.location.href;
            xhr.open('POST', url);
            xhr.timeout = this.XHR_TIMEOUT_MS;
            xhr.send(formData);
        });
    }
    
    /**
     * Obtiene los destinatarios de egreso y muestra un modal Bootstrap preguntando
     * si el usuario quiere enviar las imágenes de egreso al cliente por correo.
     * 
     * FLUJO:
     * 1. Obtiene URL de destinatarios desde data-url-destinatarios-egreso del form
     * 2. Hace GET al endpoint para obtener email, CC y conteo de imágenes
     * 3. Construye e inyecta un modal Bootstrap dinámicamente
     * 4. Cancel → recarga normal; Accept → POST al endpoint de envío + recarga
     */
    private async mostrarModalEgresoEmail(): Promise<void> {
        const form = this.formElement;
        if (!form) {
            window.location.reload();
            return;
        }

        const urlDestinatarios = form.dataset.urlDestinatariosEgreso;
        const urlEnviar = form.dataset.urlEnviarEgreso;

        if (!urlDestinatarios || !urlEnviar) {
            // No están configuradas las URLs — recargar normalmente
            window.location.reload();
            return;
        }

        // ── 1. Obtener destinatarios ─────────────────────────────────────────
        let emailPrincipal = '';
        let destinatariosCopia: string[] = [];
        let imagenesCount = 0;
        let desdeHistorial = false;

        try {
            const resp = await fetch(urlDestinatarios, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (resp.ok) {
                const data = await resp.json();
                emailPrincipal = data.email || '';
                destinatariosCopia = data.destinatarios_copia || [];
                imagenesCount = data.imagenes_egreso_count || 0;
                desdeHistorial = data.desde_historial || false;
            }
        } catch (_) {
            // Si falla el fetch, recargar normalmente
            window.location.reload();
            return;
        }

        // ── 2. Construir HTML del modal ──────────────────────────────────────
        const modalId = 'modalEgresoEmailDinamico';

        // Limpiar modal anterior si existiera
        document.getElementById(modalId)?.remove();

        const ccHtml = destinatariosCopia.length > 0
            ? destinatariosCopia.map(cc => `<li class="list-group-item py-1 px-2 small text-muted">${cc}</li>`).join('')
            : '<li class="list-group-item py-1 px-2 small text-muted fst-italic">Sin copias</li>';

        const origenBadge = desdeHistorial
            ? `<span class="badge bg-success-subtle text-success border border-success-subtle ms-1" title="Obtenido del historial de ingreso">
                    <i class="bi bi-clock-history"></i> Desde historial
               </span>`
            : `<span class="badge bg-warning-subtle text-warning border border-warning-subtle ms-1" title="No se encontró historial de ingreso — usando email de la orden">
                    <i class="bi bi-exclamation-triangle"></i> Sin historial
               </span>`;

        const modalHtml = `
        <div class="modal fade" id="${modalId}" tabindex="-1" aria-labelledby="${modalId}Label" aria-modal="true" role="dialog">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header" style="background: linear-gradient(135deg, #e67e22 0%, #d35400 100%); color: white;">
                        <h5 class="modal-title" id="${modalId}Label">
                            <i class="bi bi-envelope-paper-fill me-2"></i> ¿Enviar imágenes de egreso?
                        </h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Cerrar"></button>
                    </div>
                    <div class="modal-body">
                        <p class="mb-3">
                            Se subieron <strong>${imagenesCount}</strong> imagen(es) de egreso.
                            ¿Deseas enviarlas al cliente por correo electrónico?
                        </p>

                        <!-- Destinatarios colapsables -->
                        <div class="mb-3">
                            <button class="btn btn-sm btn-outline-secondary w-100 d-flex justify-content-between align-items-center"
                                    type="button"
                                    data-bs-toggle="collapse"
                                    data-bs-target="#egresoDestinatariosCollapse"
                                    aria-expanded="false"
                                    aria-controls="egresoDestinatariosCollapse">
                                <span>
                                    <i class="bi bi-people me-1"></i>
                                    Destinatarios ${origenBadge}
                                </span>
                                <i class="bi bi-chevron-down"></i>
                            </button>
                            <div class="collapse mt-2" id="egresoDestinatariosCollapse">
                                <ul class="list-group list-group-flush border rounded">
                                    <li class="list-group-item py-1 px-2">
                                        <i class="bi bi-envelope me-1 text-primary"></i>
                                        <strong class="small">Para:</strong>
                                        <span class="small ms-1">${emailPrincipal || '(sin correo)'}</span>
                                    </li>
                                    ${destinatariosCopia.length > 0 ? `
                                    <li class="list-group-item py-1 px-2">
                                        <i class="bi bi-people me-1 text-secondary"></i>
                                        <strong class="small">CC:</strong>
                                    </li>
                                    ${ccHtml}
                                    ` : ''}
                                </ul>
                            </div>
                        </div>

                        <!-- Aviso importante -->
                        <div class="alert alert-warning py-2 mb-0 small">
                            <i class="bi bi-exclamation-triangle-fill me-1"></i>
                            <strong>Nota:</strong> El correo indicará al cliente que su equipo
                            <strong>aún NO está listo</strong> para recoger. Solo se le notifica
                            que el proceso de egreso ha comenzado.
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal" id="btnEgresoModalCancelar">
                            <i class="bi bi-x-lg me-1"></i> No enviar
                        </button>
                        <button type="button" class="btn btn-warning text-white" id="btnEgresoModalAceptar" ${!emailPrincipal ? 'disabled' : ''}>
                            <i class="bi bi-send-fill me-1"></i> Sí, enviar
                        </button>
                    </div>
                </div>
            </div>
        </div>`;

        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // ── 3. Mostrar modal con Bootstrap ───────────────────────────────────
        const modalEl = document.getElementById(modalId)!;
        const modal = new (window as unknown as { bootstrap: { Modal: new (el: Element) => { show(): void; hide(): void } } }).bootstrap.Modal(modalEl);
        modal.show();

        // ── 4. Manejadores de botones ────────────────────────────────────────

        // Cancelar → recargar normalmente
        modalEl.addEventListener('hidden.bs.modal', () => {
            modalEl.remove();
            window.location.reload();
        });

        // Aceptar → POST al endpoint de envío
        document.getElementById('btnEgresoModalAceptar')?.addEventListener('click', async () => {
            const btnAceptar = document.getElementById('btnEgresoModalAceptar') as HTMLButtonElement | null;
            const btnCancelar = document.getElementById('btnEgresoModalCancelar') as HTMLButtonElement | null;

            if (btnAceptar) {
                btnAceptar.disabled = true;
                btnAceptar.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Enviando...';
            }
            if (btnCancelar) btnCancelar.disabled = true;

            try {
                // Obtener CSRF token del DOM
                const csrfInput = document.querySelector<HTMLInputElement>('[name=csrfmiddlewaretoken]');
                const csrfToken = csrfInput?.value || '';

                const resp = await fetch(urlEnviar, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest',
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({}),
                });

                if (resp.ok) {
                    if (btnAceptar) {
                        btnAceptar.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i> ¡Enviado!';
                        btnAceptar.classList.replace('btn-warning', 'btn-success');
                    }
                    // Esperar un momento para que el usuario vea el feedback
                    setTimeout(() => {
                        modal.hide();
                    }, 1200);
                } else {
                    // Error del servidor
                    if (btnAceptar) {
                        btnAceptar.disabled = false;
                        btnAceptar.innerHTML = '<i class="bi bi-exclamation-circle me-1"></i> Error — reintentar';
                        btnAceptar.classList.replace('btn-warning', 'btn-danger');
                    }
                    if (btnCancelar) btnCancelar.disabled = false;
                }
            } catch (_) {
                if (btnAceptar) {
                    btnAceptar.disabled = false;
                    btnAceptar.innerHTML = '<i class="bi bi-exclamation-circle me-1"></i> Error de red — reintentar';
                    btnAceptar.classList.replace('btn-warning', 'btn-danger');
                }
                if (btnCancelar) btnCancelar.disabled = false;
            }
        });
    }

    /**
     * Muestra un countdown visual y recarga la página cuando llega a 0.
     * 
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * setInterval() ejecuta una función cada N milisegundos. Aquí la usamos
     * para actualizar el contador visible (5, 4, 3, 2, 1...) y al llegar a 0
     * lo cancelamos y llamamos window.location.reload().
     * 
     * El usuario ve el contador y sabe que el sistema está funcionando,
     * no se queda con la sensación de que "algo se rompió".
     * 
     * @param segundos - Segundos antes de recargar (por defecto 5)
     */
    private iniciarCountdownRecarga(segundos: number = 5): void {
        let restantes = segundos;

        const intervalo = setInterval(() => {
            restantes--;
            const el = document.getElementById('cacheCountdown');
            if (el) {
                el.textContent = restantes > 0
                    ? `Recargando en ${restantes}s...`
                    : 'Recargando ahora...';
            }

            if (restantes <= 0) {
                clearInterval(intervalo);
                window.location.reload();
            }
        }, 1000);
    }
    
    /**
     * Deshabilita el formulario durante la subida.
     * Previene interacción con los controles mientras se sube.
     */
    private deshabilitarFormulario(): void {
        if (this.btnSubir) {
            this.btnSubir.disabled = true;
            this.btnSubir.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Subiendo...';
        }
        
        // Deshabilitar los radio buttons de tipo y el input de descripción
        // EXPLICACIÓN: Al deshabilitar los radio buttons, el CSS :disabled aplica
        // opacity: 0.5 a los cards y bloquea el puntero (pointer-events: none).
        if (this.formElement) {
            this.formElement.querySelectorAll<HTMLInputElement>('input[name="tipo"]')
                .forEach(radio => { radio.disabled = true; });
        }
        if (this.descripcionInputId) {
            const descripcionInput = document.getElementById(this.descripcionInputId) as HTMLInputElement;
            if (descripcionInput) descripcionInput.disabled = true;
        }
    }
    
    /**
     * Rehabilita el formulario después de un error.
     * Permite al usuario reintentar la subida.
     */
    private rehabilitarFormulario(): void {
        if (this.btnSubir) this.btnSubir.disabled = false;
        
        // Rehabilitar radio buttons de tipo y el input de descripción
        if (this.formElement) {
            this.formElement.querySelectorAll<HTMLInputElement>('input[name="tipo"]')
                .forEach(radio => { radio.disabled = false; });
        }
        if (this.descripcionInputId) {
            const descripcionInput = document.getElementById(this.descripcionInputId) as HTMLInputElement;
            if (descripcionInput) descripcionInput.disabled = false;
        }
    }
    
    /**
     * Protección beforeunload: advierte al usuario si intenta cerrar/navegar
     * durante una subida activa. Se activa al iniciar el XHR y se desactiva
     * al completar (éxito o error).
     */
    private advertenciaBeforeUnload(e: BeforeUnloadEvent): void {
        if (this.subiendoImagenes) {
            e.preventDefault();
            // Chrome ignora mensajes personalizados, pero otros navegadores lo muestran
            e.returnValue = 'Hay una subida de imágenes en progreso. Si sales, se perderán.';
        }
    }
    
    // =========================================================================
    // Sistema de Toasts Bootstrap
    // =========================================================================
    
    /**
     * Crea el contenedor de toasts si no existe
     */
    private crearContenedorToasts(): void {
        if (document.getElementById('toastContainerImagenes')) {
            this.toastContainer = document.getElementById('toastContainerImagenes');
            return;
        }
        
        const container = document.createElement('div');
        container.id = 'toastContainerImagenes';
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '1100';
        document.body.appendChild(container);
        this.toastContainer = container;
    }
    
    /**
     * Muestra un toast con el mensaje especificado
     */
    public mostrarToast(
        mensaje: string, 
        tipo: 'success' | 'warning' | 'error' | 'info' = 'info',
        detalles?: string[],
        duracion: number = 6000
    ): void {
        if (!this.toastContainer) return;
        
        const iconos = {
            success: 'bi-check-circle-fill',
            warning: 'bi-exclamation-triangle-fill',
            error: 'bi-x-circle-fill',
            info: 'bi-info-circle-fill'
        };
        
        const colores = {
            success: 'text-success',
            warning: 'text-warning',
            error: 'text-danger',
            info: 'text-primary'
        };
        
        const bgClasses = {
            success: 'border-success',
            warning: 'border-warning',
            error: 'border-danger',
            info: 'border-primary'
        };
        
        const toastId = `toast_${Date.now()}`;
        
        // Construir HTML de detalles si existen
        let detallesHtml = '';
        if (detalles && detalles.length > 0) {
            const detallesLimitados = detalles.slice(0, 5); // Máximo 5 detalles
            const hayMas = detalles.length > 5;
            
            detallesHtml = `
                <div class="toast-body pt-0">
                    <small class="text-muted">
                        <ul class="mb-0 ps-3" style="font-size: 0.85em;">
                            ${detallesLimitados.map(d => `<li>${d}</li>`).join('')}
                            ${hayMas ? `<li class="text-muted">... y ${detalles.length - 5} más</li>` : ''}
                        </ul>
                    </small>
                </div>
            `;
        }
        
        const toastHtml = `
            <div id="${toastId}" class="toast border-start border-4 ${bgClasses[tipo]}" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header">
                    <i class="bi ${iconos[tipo]} ${colores[tipo]} me-2"></i>
                    <strong class="me-auto">${tipo === 'error' ? 'Error' : tipo === 'warning' ? 'Advertencia' : tipo === 'success' ? 'Éxito' : 'Información'}</strong>
                    <small class="text-muted">ahora</small>
                    <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Cerrar"></button>
                </div>
                <div class="toast-body">
                    ${mensaje}
                </div>
                ${detallesHtml}
            </div>
        `;
        
        this.toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        
        const toastElement = document.getElementById(toastId);
        if (toastElement) {
            // Usar Bootstrap Toast si está disponible
            if (typeof (window as any).bootstrap !== 'undefined') {
                const bsToast = new (window as any).bootstrap.Toast(toastElement, {
                    autohide: true,
                    delay: duracion
                });
                bsToast.show();
                
                // Eliminar del DOM después de ocultarse
                toastElement.addEventListener('hidden.bs.toast', () => {
                    toastElement.remove();
                });
            } else {
                // Fallback sin Bootstrap
                toastElement.classList.add('show');
                setTimeout(() => {
                    toastElement.remove();
                }, duracion);
            }
        }
    }
    
    // =========================================================================
    // Panel de Resumen Pre-Subida
    // =========================================================================
    
    /**
     * Crea el panel de resumen de subida
     */
    private crearPanelResumen(): void {
        const previewContainer = document.getElementById('previewImagenes');
        if (!previewContainer || document.getElementById('panelResumenSubida')) {
            this.panelResumen = document.getElementById('panelResumenSubida');
            return;
        }
        
        const panel = document.createElement('div');
        panel.id = 'panelResumenSubida';
        panel.className = 'alert alert-info d-none mb-3';
        panel.innerHTML = `
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
                <div>
                    <i class="bi bi-info-circle me-1"></i>
                    <span id="resumenCantidad">0 imágenes</span>
                    <span class="text-muted mx-2">|</span>
                    <strong id="resumenTamanio">0 MB</strong>
                </div>
                <div id="resumenEstado" class="badge bg-secondary">
                    Selecciona imágenes
                </div>
            </div>
            
            <!-- Barra de progreso del límite total del servidor -->
            <div class="mb-2">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small class="text-muted">
                        <i class="bi bi-server"></i> Límite del servidor:
                    </small>
                    <small id="textoLimiteServidor" class="fw-bold">0 / ${this.MAX_REQUEST_SIZE_MB} MB</small>
                </div>
                <div class="progress" style="height: 8px;">
                    <div id="barraLimiteServidor" 
                         class="progress-bar bg-success" 
                         role="progressbar" 
                         style="width: 0%"
                         aria-valuenow="0" 
                         aria-valuemin="0" 
                         aria-valuemax="100">
                    </div>
                </div>
            </div>
            
            <div id="resumenAdvertencias" class="d-none">
                <small class="text-warning">
                    <i class="bi bi-exclamation-triangle"></i>
                    <span id="textoAdvertencias"></span>
                </small>
            </div>
        `;
        
        // Insertar antes del contenedor de preview
        previewContainer.parentElement?.insertBefore(panel, previewContainer);
        this.panelResumen = panel;
    }
    
    /**
     * Actualiza el panel de resumen con la información actual
     */
    private actualizarPanelResumen(): void {
        if (!this.panelResumen) return;
        
        const resumen = this.obtenerResumen();
        
        // Mostrar/ocultar panel
        if (resumen.cantidad > 0) {
            this.panelResumen.classList.remove('d-none');
        } else {
            this.panelResumen.classList.add('d-none');
            return;
        }
        
        // Actualizar cantidad
        const cantidadSpan = this.panelResumen.querySelector('#resumenCantidad');
        if (cantidadSpan) {
            cantidadSpan.textContent = `${resumen.cantidad} imagen${resumen.cantidad !== 1 ? 'es' : ''}`;
        }
        
        // Actualizar tamaño
        const tamanioSpan = this.panelResumen.querySelector('#resumenTamanio');
        if (tamanioSpan) {
            tamanioSpan.textContent = resumen.tamanioMB;
        }
        
        // Actualizar barra de progreso del límite del servidor
        const barraLimite = this.panelResumen.querySelector('#barraLimiteServidor') as HTMLElement;
        const textoLimite = this.panelResumen.querySelector('#textoLimiteServidor');
        
        if (barraLimite && textoLimite) {
            const tamanioTotalMB = resumen.tamanioTotal / (1024 * 1024);
            const porcentajeUso = (tamanioTotalMB / this.MAX_REQUEST_SIZE_MB) * 100;
            
            // Actualizar texto
            textoLimite.textContent = `${tamanioTotalMB.toFixed(1)} / ${this.MAX_REQUEST_SIZE_MB} MB`;
            
            // Actualizar barra
            barraLimite.style.width = `${Math.min(porcentajeUso, 100)}%`;
            barraLimite.setAttribute('aria-valuenow', porcentajeUso.toFixed(0));
            
            // Cambiar color según porcentaje
            barraLimite.className = 'progress-bar';
            if (porcentajeUso >= 100) {
                barraLimite.classList.add('bg-danger');
                textoLimite.classList.add('text-danger');
            } else if (porcentajeUso >= 80) {
                barraLimite.classList.add('bg-warning');
                textoLimite.classList.add('text-warning');
            } else if (porcentajeUso >= 60) {
                barraLimite.classList.add('bg-info');
                textoLimite.classList.remove('text-danger', 'text-warning');
            } else {
                barraLimite.classList.add('bg-success');
                textoLimite.classList.remove('text-danger', 'text-warning');
            }
        }
        
        // Actualizar estado
        const estadoBadge = this.panelResumen.querySelector('#resumenEstado') as HTMLElement;
        if (estadoBadge) {
            if (this.estaProcesando) {
                estadoBadge.className = 'badge bg-warning';
                estadoBadge.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Procesando...';
            } else if (resumen.excedeLimiteTotal) {
                estadoBadge.className = 'badge bg-danger';
                estadoBadge.innerHTML = '<i class="bi bi-x-circle me-1"></i>Excede límite del servidor';
            } else if (resumen.listoParaSubir) {
                estadoBadge.className = 'badge bg-success';
                estadoBadge.innerHTML = '<i class="bi bi-check-circle me-1"></i>Listo para subir';
            } else {
                estadoBadge.className = 'badge bg-secondary';
                estadoBadge.textContent = 'Selecciona imágenes';
            }
        }
        
        // Actualizar advertencias
        const advertenciasDiv = this.panelResumen.querySelector('#resumenAdvertencias') as HTMLElement;
        const textoAdvertencias = this.panelResumen.querySelector('#textoAdvertencias');
        
        if (advertenciasDiv && textoAdvertencias) {
            const mensajes: string[] = [];
            
            if (resumen.excedeLimiteTotal) {
                const exceso = ((resumen.tamanioTotal / (1024 * 1024)) - this.MAX_REQUEST_SIZE_MB).toFixed(1);
                mensajes.push(`⚠️ El tamaño total excede el límite del servidor en ${exceso}MB. Elimina algunas imágenes.`);
            } else if (resumen.cercaDelLimite) {
                const restante = (this.MAX_REQUEST_SIZE_MB - (resumen.tamanioTotal / (1024 * 1024))).toFixed(1);
                mensajes.push(`⚠️ Te quedan ${restante}MB disponibles del límite del servidor.`);
            }
            
            if (resumen.archivosGrandes.length > 0) {
                mensajes.push(`${resumen.archivosGrandes.length} archivo(s) exceden el límite de ${this.MAX_SIZE_MB}MB`);
            }
            if (resumen.archivosAdvertencia.length > 0) {
                mensajes.push(`${resumen.archivosAdvertencia.length} archivo(s) son muy grandes (>40MB)`);
            }
            
            if (mensajes.length > 0) {
                advertenciasDiv.classList.remove('d-none');
                textoAdvertencias.textContent = mensajes.join(' | ');
                
                // Cambiar color del panel según severidad
                if (resumen.excedeLimiteTotal || resumen.archivosGrandes.length > 0) {
                    this.panelResumen.className = 'alert alert-danger mb-3';
                } else if (resumen.cercaDelLimite || resumen.archivosAdvertencia.length > 0) {
                    this.panelResumen.className = 'alert alert-warning mb-3';
                } else {
                    this.panelResumen.className = 'alert alert-info mb-3';
                }
            } else {
                advertenciasDiv.classList.add('d-none');
                this.panelResumen.className = 'alert alert-info mb-3';
            }
        }
    }
    
    // =========================================================================
    // API PÚBLICA: Para integración con scripts externos
    // =========================================================================
    
    /**
     * API PÚBLICA: Consultar si el sistema está listo para subir
     */
    public puedeEnviar(): boolean {
        const ahora = Date.now();
        const tiempoDesdeUltimoClick = ahora - this.ultimoClickSubir;
        
        return this.archivosListos && 
               !this.estaProcesando && 
               !this.enviando && 
               this.imagenesSeleccionadas.length > 0 &&
               tiempoDesdeUltimoClick >= this.DEBOUNCE_MS;
    }
    
    /**
     * API PÚBLICA: Marcar que se inició el envío
     */
    public marcarEnviando(): void {
        this.enviando = true;
        this.ultimoClickSubir = Date.now();
        this.actualizarEstadoBotonSubir();
        console.log('📤 Envío iniciado - botón bloqueado');
    }
    
    /**
     * API PÚBLICA: Marcar que terminó el envío (éxito o error)
     */
    public marcarFinEnvio(): void {
        this.enviando = false;
        this.actualizarEstadoBotonSubir();
        console.log('✅ Envío finalizado - botón desbloqueado');
    }
    
    /**
     * API PÚBLICA: Limpiar después de subida exitosa
     */
    public limpiarDespuesDeExito(): void {
        this.limpiarTodo();
        this.marcarFinEnvio();
    }
    
    /**
     * API PÚBLICA: Obtener resumen de la subida para mostrar
     */
    public obtenerResumen(): ResumenSubida {
        const archivosGrandes: string[] = [];
        const archivosAdvertencia: string[] = [];
        let tamanioTotal = 0;
        
        this.imagenesSeleccionadas.forEach(img => {
            tamanioTotal += img.file.size;
            const sizeMB = img.file.size / (1024 * 1024);
            
            if (sizeMB > this.MAX_SIZE_MB) {
                archivosGrandes.push(`${img.file.name} (${sizeMB.toFixed(1)}MB - excede límite)`);
            } else if (sizeMB > this.ADVERTENCIA_SIZE_MB) {
                archivosAdvertencia.push(`${img.file.name} (${sizeMB.toFixed(1)}MB)`);
            }
        });
        
        const excedeLimiteTotal = tamanioTotal > this.MAX_REQUEST_SIZE_BYTES;
        const cercaDelLimite = tamanioTotal > (this.ADVERTENCIA_REQUEST_MB * 1024 * 1024);
        
        return {
            cantidad: this.imagenesSeleccionadas.length,
            tamanioTotal: tamanioTotal,
            tamanioMB: (tamanioTotal / (1024 * 1024)).toFixed(2) + ' MB',
            archivosGrandes: archivosGrandes,
            archivosAdvertencia: archivosAdvertencia,
            listoParaSubir: this.archivosListos && !this.estaProcesando && archivosGrandes.length === 0 && !excedeLimiteTotal,
            excedeLimiteTotal: excedeLimiteTotal,
            cercaDelLimite: cercaDelLimite
        };
    }
    
    /**
     * API PÚBLICA: Obtener cantidad de imágenes
     */
    public getCantidadImagenes(): number {
        return this.imagenesSeleccionadas.length;
    }
    
    /**
     * API PÚBLICA: Verificar si está procesando
     */
    public getEstaProcesando(): boolean {
        return this.estaProcesando;
    }
    
    /**
     * API PÚBLICA: Verificar si está enviando
     */
    public getEstaEnviando(): boolean {
        return this.enviando;
    }
    
    /**
     * API PÚBLICA: Obtener los archivos seleccionados como array de File.
     * 
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Este método devuelve los archivos directamente desde el array interno.
     * Es la fuente de verdad del sistema, inmune a modificaciones del DOM.
     */
    public getArchivos(): File[] {
        return this.imagenesSeleccionadas.map(img => img.file);
    }
    
    // =========================================================================
    // Métodos de cámara integrada
    // =========================================================================
    
    /**
     * Abre el modal de cámara integrada
     */
    private abrirCamaraIntegrada(): void {
        const camaraIntegrada = (window as any).camaraIntegrada;
        if (camaraIntegrada) {
            camaraIntegrada.abrir();
        } else {
            console.error('❌ Cámara integrada no disponible');
            this.mostrarToast(
                'La cámara integrada no está disponible. Verifica que estés usando HTTPS o localhost.',
                'error'
            );
        }
    }
    
    /**
     * Configura el callback para recibir fotos de la cámara integrada
     */
    private configurarCamaraIntegrada(): void {
        // Esperar a que la cámara integrada esté disponible
        const intervalo = setInterval(() => {
            const camaraIntegrada = (window as any).camaraIntegrada;
            if (camaraIntegrada) {
                clearInterval(intervalo);
                
                // Configurar callback para recibir fotos capturadas
                camaraIntegrada.setOnFotosCapturadas((fotos: Blob[]) => {
                    this.agregarFotosDeCamara(fotos);
                });
                
                console.log('✅ Cámara integrada conectada al sistema de upload');
            }
        }, 100);
        
        // Timeout de 5 segundos
        setTimeout(() => clearInterval(intervalo), 5000);
    }
    
    /**
     * Agrega fotos capturadas desde la cámara integrada
     */
    private agregarFotosDeCamara(fotos: Blob[]): void {
        console.log(`📸 Recibidas ${fotos.length} foto(s) desde cámara integrada`);
        
        // Convertir Blobs a Files
        const archivos: File[] = fotos.map((blob, index) => {
            const timestamp = Date.now() + index;
            return new File([blob], `captura_${timestamp}.jpg`, { type: 'image/jpeg' });
        });
        
        // Agregar usando el método existente
        this.agregarArchivos(archivos);
        
        // Mostrar toast de confirmación
        this.mostrarToast(
            `${fotos.length} foto(s) capturada(s) desde la cámara`,
            'success'
        );
    }
    
    // =========================================================================
    // Manejo de archivos
    // =========================================================================
    
    /**
     * Maneja la selección de archivos desde cualquier input
     */
    private handleFileSelect(event: Event): void {
        const input = event.target as HTMLInputElement;
        
        if (!input.files || input.files.length === 0) {
            return;
        }
        
        const nuevosArchivos = Array.from(input.files);
        const origen = input.id === 'inputGaleria' ? 'galería' : 'cámara';
        
        console.log(`📸 ${nuevosArchivos.length} archivo(s) seleccionado(s) desde ${origen}`);
        
        // Validar y agregar archivos
        this.agregarArchivos(nuevosArchivos);
        
        // Limpiar el input para permitir seleccionar los mismos archivos de nuevo
        input.value = '';
    }
    
    /**
     * Agrega archivos al array de imágenes seleccionadas.
     * v5.0: Ya no transfiere a input oculto, el array es la fuente de verdad.
     */
    private async agregarArchivos(archivos: File[]): Promise<void> {
        // CRÍTICO: Marcar como procesando y deshabilitar botón de subir
        this.estaProcesando = true;
        this.archivosListos = false;
        this.actualizarEstadoBotonSubir();
        this.actualizarPanelResumen();
        
        let agregados = 0;
        let omitidos = 0;
        const errores: string[] = [];
        const advertencias: string[] = [];
        
        console.log(`🔄 Iniciando procesamiento de ${archivos.length} archivo(s)...`);
        
        for (const archivo of archivos) {
            // Validar que sea una imagen
            if (!archivo.type.startsWith('image/')) {
                errores.push(`${archivo.name}: No es una imagen válida`);
                omitidos++;
                continue;
            }
            
            // Validar tamaño
            if (archivo.size > this.MAX_SIZE_BYTES) {
                const sizeMB = (archivo.size / (1024 * 1024)).toFixed(2);
                errores.push(`${archivo.name}: ${sizeMB}MB excede el límite de ${this.MAX_SIZE_MB}MB`);
                omitidos++;
                continue;
            }
            
            // Advertir si está cerca del límite
            const sizeMB = archivo.size / (1024 * 1024);
            if (sizeMB > this.ADVERTENCIA_SIZE_MB) {
                advertencias.push(`${archivo.name}: ${sizeMB.toFixed(1)}MB (archivo grande, puede tardar)`);
            }
            
            // Validar límite total de imágenes
            if (this.imagenesSeleccionadas.length >= this.MAX_IMAGENES) {
                errores.push(`Límite alcanzado: máximo ${this.MAX_IMAGENES} imágenes por carga`);
                omitidos++;
                break;
            }
            
            // Generar ID único
            const id = `img_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            
            // Crear URL de preview
            const previewUrl = URL.createObjectURL(archivo);
            
            // Agregar a la lista
            this.imagenesSeleccionadas.push({
                file: archivo,
                id: id,
                previewUrl: previewUrl
            });
            
            agregados++;
            
            // Yield al event loop cada 3 archivos para mantener UI responsive
            if (agregados % 3 === 0) {
                await this.delay(10);
            }
        }
        
        // Mostrar errores con toast descriptivo
        if (errores.length > 0) {
            console.warn('⚠️ Archivos omitidos:', errores);
            this.mostrarToast(
                `${errores.length} archivo(s) no se pudieron agregar`,
                'error',
                errores,
                8000
            );
        }
        
        // Mostrar advertencias si hay archivos grandes
        if (advertencias.length > 0 && errores.length === 0) {
            this.mostrarToast(
                `${advertencias.length} archivo(s) son muy grandes y pueden tardar en subir`,
                'warning',
                advertencias,
                5000
            );
        }
        
        if (agregados > 0) {
            console.log(`✅ ${agregados} imagen(es) agregada(s). Total: ${this.imagenesSeleccionadas.length}`);
        }
        
        // Actualizar UI
        this.actualizarPreview();
        
        // v5.0: Ya no se llama a transferirArchivosAInputUnificado()
        // El array interno es la fuente de verdad, FormData se construye desde él
        
        // Marcar como listo
        this.estaProcesando = false;
        this.archivosListos = this.imagenesSeleccionadas.length > 0;
        this.actualizarEstadoBotonSubir();
        this.actualizarPanelResumen();

        // v7.0: Guardar selección actual en caché IndexedDB (fire-and-forget)
        // Así si la conexión se corta durante la subida, las imágenes se pueden recuperar
        if (this.imagenesSeleccionadas.length > 0) {
            this.sincronizarCache();
        }
        
        console.log(`✅ Procesamiento completado. Archivos listos: ${this.archivosListos}`);
    }
    
    /**
     * Utilidad: Delay para yield al event loop
     */
    private delay(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    /**
     * Actualiza el estado del botón de subir según el contexto.
     */
    public actualizarEstadoBotonSubir(): void {
        if (!this.btnSubir) {
            return;
        }
        
        // Obtener resumen para validar límite total
        const resumen = this.obtenerResumen();
        
        // EXPLICACIÓN PARA PRINCIPIANTES:
        // El botón de subir solo se habilita cuando se cumplen TODAS estas condiciones:
        // 1. No está procesando archivos en este momento
        // 2. No está enviando al servidor en este momento
        // 3. Hay archivos listos para subir
        // 4. El usuario seleccionó al menos un archivo
        // 5. El tamaño total no excede el límite del servidor
        // 6. El usuario seleccionó un tipo de imagen (NUEVO: obligatorio)
        const tipoSeleccionado = this.getTipoSeleccionado();
        const debeEstarDeshabilitado = this.estaProcesando || 
                                        this.enviando || 
                                        !this.archivosListos || 
                                        this.imagenesSeleccionadas.length === 0 ||
                                        resumen.excedeLimiteTotal ||
                                        tipoSeleccionado === '';   // ← Tipo obligatorio
        
        this.btnSubir.disabled = debeEstarDeshabilitado;
        
        // Cambiar texto del botón según estado (orden de prioridad: errores primero)
        if (resumen.excedeLimiteTotal) {
            this.btnSubir.innerHTML = '<i class="bi bi-exclamation-triangle"></i> Excede límite del servidor';
        } else if (this.enviando) {
            this.btnSubir.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Subiendo...';
        } else if (this.estaProcesando) {
            this.btnSubir.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Procesando...';
        } else if (tipoSeleccionado === '') {
            // Guiar al usuario a seleccionar un tipo antes de subir
            this.btnSubir.innerHTML = '<i class="bi bi-tag"></i> Selecciona un tipo';
        } else if (this.imagenesSeleccionadas.length > 0) {
            this.btnSubir.innerHTML = `<i class="bi bi-cloud-upload"></i> Subir ${this.imagenesSeleccionadas.length} Imagen${this.imagenesSeleccionadas.length !== 1 ? 'es' : ''}`;
        } else {
            this.btnSubir.innerHTML = '<i class="bi bi-cloud-upload"></i> Subir Imágenes';
        }
        
        console.log(`🔘 Botón: ${debeEstarDeshabilitado ? 'DESHABILITADO' : 'HABILITADO'} | Procesando: ${this.estaProcesando} | Enviando: ${this.enviando} | Listos: ${this.archivosListos} | Excede límite: ${resumen.excedeLimiteTotal} | Tipo: "${tipoSeleccionado}"`);
    }
    
    /**
     * Actualiza la visualización del preview de imágenes
     */
    private actualizarPreview(): void {
        if (!this.previewContainer || !this.contenedorMiniaturas || !this.cantidadSpan) {
            return;
        }
        
        // Mostrar u ocultar el contenedor de preview
        if (this.imagenesSeleccionadas.length > 0) {
            this.previewContainer.style.display = 'block';
            
            // Actualizar contador
            this.cantidadSpan.textContent = String(this.imagenesSeleccionadas.length);
            
            // Limpiar miniaturas existentes
            this.contenedorMiniaturas.innerHTML = '';
            
            // Crear miniaturas
            this.imagenesSeleccionadas.forEach((imagen, index) => {
                const miniatura = this.crearMiniatura(imagen, index);
                if (this.contenedorMiniaturas) {
                    this.contenedorMiniaturas.appendChild(miniatura);
                }
            });
        } else {
            this.previewContainer.style.display = 'none';
        }
    }
    
    /**
     * Crea un elemento de miniatura para una imagen
     */
    private crearMiniatura(imagen: ImagenPreview, index: number): HTMLElement {
        const col = document.createElement('div');
        col.className = 'col-4 col-sm-3 col-md-2';
        
        // Calcular tamaño del archivo
        const sizeMB = imagen.file.size / (1024 * 1024);
        const sizeText = sizeMB.toFixed(2);
        
        // Color del indicador según tamaño
        let sizeClass = 'text-success'; // < 10MB
        if (sizeMB > this.ADVERTENCIA_SIZE_MB) {
            sizeClass = 'text-warning fw-bold';
        } else if (sizeMB > 20) {
            sizeClass = 'text-info';
        }
        
        col.innerHTML = `
            <div class="preview-thumbnail" data-id="${imagen.id}">
                <img src="${imagen.previewUrl}" alt="Preview ${index + 1}">
                <button type="button" class="btn-eliminar-preview" data-id="${imagen.id}" title="Eliminar imagen">
                    <i class="bi bi-x-circle-fill"></i>
                </button>
                <div class="preview-info">
                    <small class="${sizeClass}">${sizeText} MB</small>
                </div>
            </div>
        `;
        
        // Event listener para eliminar
        const btnEliminar = col.querySelector('.btn-eliminar-preview') as HTMLButtonElement;
        if (btnEliminar) {
            btnEliminar.addEventListener('click', () => this.eliminarImagen(imagen.id));
        }
        
        return col;
    }
    
    /**
     * Elimina una imagen del array de seleccionadas.
     * v5.0: Simplificado, ya no transfiere a input oculto.
     */
    private eliminarImagen(id: string): void {
        const index = this.imagenesSeleccionadas.findIndex(img => img.id === id);
        
        if (index !== -1) {
            const nombreArchivo = this.imagenesSeleccionadas[index].file.name;
            
            // Liberar memoria del ObjectURL
            URL.revokeObjectURL(this.imagenesSeleccionadas[index].previewUrl);
            
            // Eliminar del array
            this.imagenesSeleccionadas.splice(index, 1);
            
            console.log(`🗑️ Imagen eliminada: ${nombreArchivo}. Total: ${this.imagenesSeleccionadas.length}`);
            
            // Actualizar UI
            this.actualizarPreview();
            this.archivosListos = this.imagenesSeleccionadas.length > 0;
            this.actualizarEstadoBotonSubir();
            this.actualizarPanelResumen();

            // v7.0: Sincronizar caché (reflejar la eliminación)
            this.sincronizarCache();
        }
    }
    
    /**
     * Limpia todas las imágenes seleccionadas.
     * v7.0: También limpia el caché IndexedDB de esta orden.
     */
    private limpiarTodo(): void {
        // Liberar memoria de todos los ObjectURLs
        this.imagenesSeleccionadas.forEach(img => {
            URL.revokeObjectURL(img.previewUrl);
        });
        
        // Limpiar array
        this.imagenesSeleccionadas = [];
        
        // Limpiar inputs de selección
        if (this.inputGaleria) this.inputGaleria.value = '';
        if (this.inputCamara) this.inputCamara.value = '';
        
        // Resetear estados
        this.estaProcesando = false;
        this.archivosListos = false;
        this.enviando = false;
        
        console.log('🧹 Todas las imágenes eliminadas');

        // v7.0: Limpiar caché IndexedDB — el usuario borró la selección voluntariamente
        ImageCache.limpiar(this.cacheOrdenUrl);

        // Quitar banner de restauración si existe
        document.getElementById('cacheBannerRestauracion')?.remove();
        
        // Actualizar UI
        this.actualizarPreview();
        this.actualizarEstadoBotonSubir();
        this.actualizarPanelResumen();
    }
    
    /**
     * Limpia memoria al destruir el objeto
     */
    public destroy(): void {
        this.imagenesSeleccionadas.forEach(img => {
            URL.revokeObjectURL(img.previewUrl);
        });
        this.imagenesSeleccionadas = [];
    }
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    // Verificar que estamos en la página correcta
    if (document.getElementById('formSubirImagenes')) {
        (window as any).uploadImagenesDual = new UploadImagenesDual();
        console.log('✅ Sistema de subida dual v8.0 inicializado (caché IndexedDB activo)');
    }
});
