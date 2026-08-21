// Declaraciones globales compartidas entre múltiples archivos TypeScript
declare const Chart: any;

// DashboardLoader se define en static/ts/dashboard_loader.ts y se compila
// junto con el resto del proyecto — no se re-declara aquí para evitar TS2300.
// globals.d.ts solo declara las extensiones de Window.

/** Opciones del scanner QR/barras (static/ts/scanner_codigo.ts). */
interface AbrirScannerCodigoOpciones {
    targetInput: HTMLInputElement;
    onDetect?: (codigo: string) => void;
    tituloModal?: string;
}

interface Window {
    sigmaLoader: InstanceType<typeof DashboardLoader> | null;
    /** Abre modal de cámara y escribe el código detectado en un input */
    abrirScannerCodigo?: (opciones: AbrirScannerCodigoOpciones) => void;
    /**
     * Token CSRF (cookie sigma_csrftoken / csrftoken o input del form).
     * Definido en static/ts/csrf.ts y cargado desde base.html.
     */
    getCsrfToken?: () => string;
    /** Venta mostrador (static/ts/venta_mostrador.ts) — onclick del detalle de orden */
    abrirModalVentaMostrador?: () => void;
    abrirModalPiezaVentaMostrador?: (esEdicion?: boolean, piezaId?: number | null) => void;
    editarPiezaVentaMostrador?: (piezaId: number) => void;
    eliminarPiezaVentaMostrador?: (piezaId: number) => void;
    toggleCambioPiezaCosto?: () => void;
    toggleLimpiezaCosto?: () => void;
    toggleKitCosto?: () => void;
    toggleReinstalacionCosto?: () => void;
    toggleRespaldoCosto?: () => void;
    /**
     * Easter egg del ganso (static/ts/easter_egg_ganso.ts).
     * Solo existe en el dashboard de inicio. ejecutar() ignora el azar diario.
     */
    SigmaGansoEasterEgg?: {
        ejecutar: () => void;
        puedeCorrer: () => boolean;
    };
}

