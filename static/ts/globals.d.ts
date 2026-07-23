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
}

