/**
 * diagnostico_modal.ts
 * ====================
 * 
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este archivo TypeScript maneja toda la lógica interactiva del modal
 * "Enviar Diagnóstico al Cliente" en la página detalle_orden.html.
 * 
 * ¿Qué hace?
 * - Actualiza el asunto del correo en tiempo real al escribir el folio
 * - Cuenta componentes seleccionados e imágenes seleccionadas
 * - Permite seleccionar/deseleccionar todos los componentes e imágenes
 * - Genera el JSON de componentes para enviar al servidor
 * - Maneja el envío del formulario via AJAX (fetch)
 * - Actualiza la vista previa del PDF en el iframe
 * - Muestra feedback visual (loading, éxito, error)
 * - Detecta automáticamente números de parte del texto del diagnóstico
 */

// ========================================================================
// INTERFACES (Tipos de datos)
// ========================================================================

/** Datos de un componente para enviar al servidor */
interface ComponenteData {
    componente_db: string;
    dpn: string;
    seleccionado: boolean;
}

/** Respuesta del servidor al enviar diagnóstico */
interface DiagnosticoResponse {
    success: boolean;
    message?: string;
    error?: string;
    data?: {
        destinatario: string;
        folio: string;
        pdf_generado: string;
        piezas_creadas: number;
        imagenes_enviadas: number;
        estado_nuevo: string;
        cotizacion_creada: boolean;
        copia_count: number;
    };
}

/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Esta interfaz representa una pieza detectada automáticamente 
 * del texto del diagnóstico. Contiene el texto original que escribió
 * el técnico, el número de parte extraído y a cuál componente del 
 * sistema corresponde (si se pudo emparejar).
 */
interface PiezaDetectada {
    textoOriginal: string;        // Texto completo como lo escribió el técnico
    descripcionPieza: string;     // Nombre/descripción de la pieza
    numeroParte: string;          // Código/número de parte extraído
    componenteDb: string | null;  // Nombre del componente en la BD (null si no matchea)
    confianza: 'alta' | 'media';  // Qué tan seguro es el emparejamiento
}

// ========================================================================
// MAPA DE ALIASES - Para emparejar texto libre con componentes del sistema
// ========================================================================

/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Los técnicos escriben los nombres de las piezas de muchas maneras diferentes.
 * Por ejemplo, "MOBO", "MOTHERBOARD", "TARJETA MADRE" y "BOARD" se refieren 
 * al mismo componente: "Motherboard". Este mapa permite hacer ese emparejamiento.
 * 
 * La clave (key) es el nombre del componente tal como está en la base de datos
 * (el campo componente_db de la tabla de componentes del modal).
 * Los valores (values) son todas las palabras clave que los técnicos podrían usar.
 */
const ALIAS_COMPONENTES: Record<string, string[]> = {
    'Motherboard': [
        'MOBO', 'MOTHERBOARD', 'TARJETA MADRE', 'BOARD', 'PLACA', 'PLACA MADRE',
        'MAINBOARD', 'MAIN BOARD', 'TARJETA PRINCIPAL', 'LOGIC BOARD'
    ],
    'Pantalla': [
        'PANTALLA', 'LCD', 'DISPLAY', 'SCREEN', 'PANEL', 'PANEL LCD',
        'LED', 'PANEL LED', 'TOUCH SCREEN', 'DIGITALIZADOR'
    ],
    'Disco Duro / SSD': [
        'DISCO', 'DISCO DURO', 'SSD', 'HDD', 'HARD DRIVE', 'NVME',
        'M.2', 'SATA', 'UNIDAD DE ESTADO SOLIDO', 'SOLID STATE'
    ],
    'Teclado': [
        'TECLADO', 'KEYBOARD', 'PALMREST', 'TOP COVER', 'PALM REST',
        'UPPER CASE', 'REPOSAMANOS'
    ],
    'Cargador': [
        'CARGADOR', 'ELIMINADOR', 'ADAPTADOR', 'AC ADAPTER', 'POWER ADAPTER',
        'FUENTE', 'FUENTE DE PODER', 'POWER SUPPLY', 'CABLE DE AC',
        'ADAPTADOR DE CORRIENTE'
    ],
    'Batería': [
        'BATERIA', 'BATTERY', 'PILA', 'ACUMULADOR', 'CELL',
        'PILA CMOS', 'CMOS', 'BIOS BATTERY', 'COIN CELL'
    ],
    'DC-IN': [
        'DC-IN', 'DCIN', 'DC IN', 'JACK DC', 'JACK DE CARGA',
        'POWER JACK', 'CONECTOR DE CARGA', 'PUERTO DE CARGA',
        'CHARGING PORT'
    ],
    'Botón': [
        'BOTON', 'BOTÓN', 'BUTTON', 'POWER BUTTON', 'BOTON DE ENCENDIDO',
        'BOTÓN DE ENCENDIDO', 'SWITCH'
    ],
    'WiFi / Bluetooth': [
        'WIFI', 'WI-FI', 'BLUETOOTH', 'ANTENA', 'ANTENAS', 'WIRELESS',
        'TARJETA WIFI', 'TARJETA INALAMBRICA', 'WLAN', 'BT',
        'MODULO WIFI', 'WIRELESS CARD'
    ],
    'Touchpad': [
        'TOUCHPAD', 'TOUCH PAD', 'TRACKPAD', 'TRACK PAD', 'MOUSE PAD',
        'PAD TACTIL', 'PANEL TACTIL'
    ],
    'Sistema Operativo': [
        'S.O.', 'SO', 'SISTEMA OPERATIVO', 'WINDOWS', 'INSTALACION DE S.O',
        'INSTALACION S.O', 'INSTALACION SO', 'REINSTALACION', 'FORMATEO',
        'FORMATO', 'INSTALACION DE SISTEMA', 'OS'
    ],
    'Bisagras': [
        'BISAGRA', 'BISAGRAS', 'HINGE', 'HINGES', 'CHARNELA', 'CHARNELAS'
    ],
    'RAM': [
        'RAM', 'MEMORIA', 'MEMORIA RAM', 'DIMM', 'SODIMM', 'SO-DIMM',
        'DDR3', 'DDR4', 'DDR5', 'MODULO DE MEMORIA'
    ],
    'Ventilador / Cooling': [
        'VENTILADOR', 'FAN', 'COOLER', 'COOLING', 'DISIPADOR',
        'HEATSINK', 'HEAT SINK', 'THERMAL', 'PASTA TERMICA',
        'SISTEMA DE ENFRIAMIENTO'
    ],
    'Carcasa / Chasis': [
        'CARCASA', 'CHASIS', 'BISEL', 'BEZEL', 'PLASTICO', 'PLASTICOS',
        'BOTTOM', 'BOTTOM COVER', 'BOTTOM BASE', 'TAPA INFERIOR',
        'TAPA TRASERA', 'BACK COVER', 'MARCO', 'FRAME', 'HOUSING',
        'CUBIERTA'
    ],
    'Cable': [
        'CABLE', 'FLEX', 'CABLE FLEX', 'FLAT CABLE', 'RIBBON',
        'CABLE LVDS', 'CABLE DE VIDEO', 'CABLE DE PANTALLA',
        'CONECTOR', 'CABLE DE DATOS'
    ],
    'Webcam': [
        'CAMARA', 'WEBCAM', 'CAMERA', 'WEB CAM', 'CAM',
        'MODULO DE CAMARA'
    ],
    'Limpieza y mantenimiento': [
        'LIMPIEZA', 'MANTENIMIENTO', 'LIMPIEZA Y MANTENIMIENTO',
        'SERVICIO DE LIMPIEZA', 'CLEANING', 'MAINTENANCE'
    ],
    'Bocinas': [
        'BOCINA', 'BOCINAS', 'SPEAKER', 'SPEAKERS', 'ALTAVOZ',
        'ALTAVOCES', 'PARLANTE', 'PARLANTES', 'AUDIO'
    ]
};

// ========================================================================
// FRASES INDICADORAS - Señales de que el texto contiene números de parte
// ========================================================================

/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Los técnicos suelen escribir una frase que indica que a continuación vienen
 * los números de parte. Estas frases nos ayudan a saber dónde empieza 
 * la sección relevante del diagnóstico para extraer piezas.
 */
const FRASES_INDICADORAS: string[] = [
    'SE ANEXAN NÚMEROS DE PARTE',
    'SE ANEXAN NUMEROS DE PARTE',
    'SE ANEXA NÚMERO DE PARTE',
    'SE ANEXA NUMERO DE PARTE',
    'NUMEROS DE PARTE PRIORITARIOS',
    'NÚMEROS DE PARTE PRIORITARIOS',
    'NUMERO DE PARTE DE PIEZAS',
    'NÚMERO DE PARTE DE PIEZAS',
    'COTIZAR PIEZAS PRIORITARIAS',
    'COTIZAR PIEZAS',
    'PIEZAS A COTIZAR',
    'PIEZAS PRIORITARIAS',
    'PARTES A COTIZAR',
    'SE ANEXAN DPN',
    'SE ANEXA DPN',
    'DPN DE PIEZAS',
    'NUMEROS DE PARTE A COTIZAR',
    'NÚMEROS DE PARTE A COTIZAR',
    'ANEXO NUMEROS DE PARTE',
    'ANEXO NÚMEROS DE PARTE',
];

// ========================================================================
// FUNCIONES DE DETECCIÓN DE PIEZAS
// ========================================================================

/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Esta función busca en el texto del diagnóstico la frase que indica
 * dónde empiezan los números de parte (por ejemplo "SE ANEXAN NÚMEROS 
 * DE PARTE PRIORITARIOS.-"). Devuelve solo el texto después de esa frase,
 * que es donde están las piezas reales.
 * 
 * Si no encuentra ninguna frase indicadora, devuelve el texto completo
 * para intentar buscar piezas en todo el diagnóstico.
 */
function extraerSeccionPiezas(texto: string): string {
    const textoUpper = texto.toUpperCase();
    
    let mejorPosicion = -1;
    let mejorLongitud = 0;
    
    for (const frase of FRASES_INDICADORAS) {
        const pos = textoUpper.indexOf(frase);
        if (pos !== -1) {
            // Preferir la frase más larga encontrada (más específica)
            if (frase.length > mejorLongitud) {
                mejorPosicion = pos;
                mejorLongitud = frase.length;
            }
        }
    }
    
    if (mejorPosicion !== -1) {
        // Extraer todo después de la frase indicadora
        let inicio = mejorPosicion + mejorLongitud;
        const resto = texto.substring(inicio);
        
        // Saltar separadores iniciales como ".-", ":", "-", "."
        const limpio = resto.replace(/^[\s.\-:]+/, '');
        return limpio;
    }
    
    // Si no hay frase indicadora, devolver todo el texto
    return texto;
}

/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Esta función toma el texto de la sección de piezas y lo divide en
 * fragmentos individuales. Los técnicos separan las piezas con comas,
 * puntos, punto y coma, o la conjunción "Y".
 * 
 * Ejemplo: "BATERIA 56W: CP6DF, PILA CMOS: W6NPD" 
 * Se divide en: ["BATERIA 56W: CP6DF", "PILA CMOS: W6NPD"]
 */
function dividirEnFragmentos(texto: string): string[] {
    // Dividir por comas, puntos y coma, o punto seguido de espacio
    // También dividir por " Y " cuando es conjunción entre piezas
    // pero NO cuando forma parte del nombre (ej: "LIMPIEZA Y MANTENIMIENTO")
    const fragmentos: string[] = texto
        .split(/[,;]|\.\s|\.-/)
        .flatMap((frag: string): string[] => {
            // Sub-dividir por " Y " solo si ambos lados parecen tener un código
            // Es decir, si " Y " separa dos piezas independientes
            const partes: string[] = frag.split(/\s+Y\s+/i);
            if (partes.length > 1) {
                // Verificar si al menos 2 partes tienen algo que parece un código
                const partesConCodigo = partes.filter((p: string) => 
                    /[A-Z0-9]{3,}/.test(p.trim().toUpperCase())
                );
                if (partesConCodigo.length >= 2) {
                    return partes;
                }
            }
            return [frag];
        })
        .map((f: string) => f.trim())
        .filter((f: string) => f.length > 0);
    
    return fragmentos;
}

/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Esta función toma un fragmento individual (ej: "BATERIA 56W: CP6DF")
 * y extrae la descripción de la pieza y el número de parte.
 * 
 * Maneja dos formatos:
 * 1. Con dos puntos: "BATERIA 56W: CP6DF" → pieza: "BATERIA 56W", parte: "CP6DF"
 * 2. Sin dos puntos: "TOP COVER 4Y37V" → pieza: "TOP COVER", parte: "4Y37V"
 * 
 * Para el formato sin dos puntos, busca al final del texto un patrón
 * que parezca un código alfanumérico (como 4Y37V, X5CF4, 1M3M4).
 */
function extraerParteDeFragmento(fragmento: string): PiezaDetectada | null {
    const textoLimpio = fragmento.trim();
    
    // Ignorar fragmentos muy cortos o que no tienen sentido
    if (textoLimpio.length < 3) return null;
    
    // Ignorar fragmentos que son solo texto genérico sin códigos
    // (ej: "INSTALACION DE S.O. SUGERIDO" sin número de parte)
    
    let descripcion = '';
    let numeroParte = '';
    
    // FORMATO 1: Con dos puntos → "COMPONENTE: CÓDIGO"
    if (textoLimpio.includes(':')) {
        const partes = textoLimpio.split(':');
        // Tomar la última parte como código (puede haber ":" en la descripción)
        const posibleCodigo = partes[partes.length - 1].trim();
        
        // Verificar que el código parece un número de parte válido
        // (alfanumérico, generalmente 3-10 caracteres, sin espacios largos)
        const codigoLimpio = posibleCodigo.split(/\s+/)[0].trim();
        
        if (/^[A-Za-z0-9]{3,15}$/.test(codigoLimpio)) {
            descripcion = partes.slice(0, -1).join(':').trim();
            numeroParte = codigoLimpio.toUpperCase();
        }
    }
    
    // FORMATO 2: Sin dos puntos → "COMPONENTE CÓDIGO" (código al final)
    if (!numeroParte) {
        // Buscar un código alfanumérico al final del texto
        // Los códigos suelen ser 4-7 caracteres alfanuméricos con al menos un dígito y una letra
        const match = textoLimpio.match(/\s+([A-Za-z0-9]{4,10})\.?\s*$/);
        
        if (match) {
            const posibleCodigo = match[1];
            // Verificar que tiene mezcla de letras y números (no es una palabra normal)
            const tieneDigitos = /\d/.test(posibleCodigo);
            const tieneLetras = /[A-Za-z]/.test(posibleCodigo);
            
            // Un código de parte típicamente tiene letras Y números mezclados
            // Excluir palabras comunes que podrían confundirse
            const palabrasExcluidas = [
                'DELL', 'CORE', 'INTEL', 'NVIDIA', 'QUADRO',
                'CHICO', 'GRANDE', 'CABLE', 'PILA', 'PLUG',
                'PARA', 'ESTA', 'ESTE', 'COMO', 'TIENE',
                'NUEVO', 'NUEVA', 'ROTO', 'ROTA', 'DAÑADO',
                'SUGERIDO', 'SUGERIDA', 'PRIORITARIO', 'NECESARIO',
                'REEMPLAZO', 'SUSTITUIR', 'COTIZAR'
            ];
            
            if (tieneDigitos && tieneLetras && 
                !palabrasExcluidas.includes(posibleCodigo.toUpperCase())) {
                descripcion = textoLimpio.substring(0, match.index || 0).trim();
                numeroParte = posibleCodigo.toUpperCase();
            }
        }
    }
    
    // Si no se encontró un número de parte válido, saltar este fragmento
    if (!numeroParte || !descripcion) return null;
    
    // Limpiar descripción de caracteres sobrantes
    descripcion = descripcion.replace(/[\-\.]+$/, '').trim();
    
    // Intentar emparejar con un componente de la base de datos
    const matchComponente = buscarComponenteDb(descripcion);
    
    return {
        textoOriginal: textoLimpio,
        descripcionPieza: descripcion,
        numeroParte: numeroParte,
        componenteDb: matchComponente.nombre,
        confianza: matchComponente.confianza
    };
}

/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Esta función busca en el mapa de aliases cuál componente de la base de datos
 * corresponde a la descripción que escribió el técnico.
 * 
 * Por ejemplo, si el técnico escribió "MOBO CORE i7 6820HQ", esta función
 * busca la palabra "MOBO" en todos los aliases y encuentra que corresponde
 * al componente "Motherboard".
 */
function buscarComponenteDb(descripcion: string): { nombre: string | null; confianza: 'alta' | 'media' } {
    const descUpper = descripcion.toUpperCase();
    
    // Primero buscar coincidencia directa/exacta con el nombre del componente
    for (const [componenteDb, aliases] of Object.entries(ALIAS_COMPONENTES)) {
        // Coincidencia directa con el nombre en la BD
        if (descUpper === componenteDb.toUpperCase()) {
            return { nombre: componenteDb, confianza: 'alta' };
        }
    }
    
    // Buscar por aliases — priorizar los aliases más largos (más específicos)
    let mejorMatch: { nombre: string; confianza: 'alta' | 'media'; longitud: number } | null = null;
    
    for (const [componenteDb, aliases] of Object.entries(ALIAS_COMPONENTES)) {
        for (const alias of aliases) {
            // Verificar si el alias aparece en la descripción
            if (descUpper.includes(alias)) {
                const confianza: 'alta' | 'media' = alias.length >= 4 ? 'alta' : 'media';
                
                if (!mejorMatch || alias.length > mejorMatch.longitud) {
                    mejorMatch = { nombre: componenteDb, confianza, longitud: alias.length };
                }
            }
        }
    }
    
    if (mejorMatch) {
        return { nombre: mejorMatch.nombre, confianza: mejorMatch.confianza };
    }
    
    return { nombre: null, confianza: 'media' };
}

/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Esta es la función principal que coordina todo el proceso de detección.
 * Recibe el texto completo del diagnóstico y devuelve una lista de piezas
 * detectadas con sus números de parte.
 * 
 * Proceso:
 * 1. Busca la sección del texto donde están los números de parte
 * 2. Divide esa sección en fragmentos individuales (uno por pieza)
 * 3. De cada fragmento extrae la descripción y el número de parte
 * 4. Empareja cada pieza con un componente del sistema
 */
function extraerPiezasDiagnostico(textoDiagnostico: string): PiezaDetectada[] {
    if (!textoDiagnostico || textoDiagnostico.trim().length === 0) {
        return [];
    }
    
    // Paso 1: Encontrar la sección relevante del diagnóstico
    const seccionPiezas = extraerSeccionPiezas(textoDiagnostico);
    
    // Paso 2: Dividir en fragmentos individuales
    const fragmentos = dividirEnFragmentos(seccionPiezas);
    
    // Paso 3: Extraer pieza y número de parte de cada fragmento
    const piezas: PiezaDetectada[] = [];
    
    for (const fragmento of fragmentos) {
        const pieza = extraerParteDeFragmento(fragmento);
        if (pieza) {
            // Evitar duplicados (mismo número de parte)
            const yaExiste = piezas.some(p => p.numeroParte === pieza.numeroParte);
            if (!yaExiste) {
                piezas.push(pieza);
            }
        }
    }
    
    return piezas;
}

// ========================================================================
// FUNCIONES PRINCIPALES
// ========================================================================

/**
 * Inicializa toda la lógica del modal de diagnóstico.
 * Se ejecuta cuando el DOM está completamente cargado.
 */
function initDiagnosticoModal(): void {
    // Elementos del DOM
    const inputFolio = document.getElementById('inputFolioDiagnostico') as HTMLInputElement | null;
    const spanFolioPreview = document.getElementById('spanFolioPreview') as HTMLElement | null;
    const btnEnviar = document.getElementById('btnEnviarDiagnostico') as HTMLButtonElement | null;
    const form = document.getElementById('formEnviarDiagnostico') as HTMLFormElement | null;
    const inputComponentesJSON = document.getElementById('inputComponentesJSON') as HTMLInputElement | null;
    const btnRefrescarPreview = document.getElementById('btnRefrescarPreviewDiag') as HTMLButtonElement | null;
    const iframePreview = document.getElementById('iframePreviewDiagnostico') as HTMLIFrameElement | null;
    
    // Checkboxes
    const checkboxSelectAllImgs = document.getElementById('seleccionarTodasImagenesDiag') as HTMLInputElement | null;
    
    // Botón y dropdown para agregar componentes adicionales
    const btnAgregarComponente = document.getElementById('btnAgregarComponente') as HTMLButtonElement | null;
    const dropdownComponentesAdicionales = document.getElementById('dropdownComponentesAdicionales') as HTMLElement | null;
    const componentesAdicionalesTbody = document.getElementById('componentesAdicionales') as HTMLTableSectionElement | null;
    
    // Contadores
    const contadorComponentes = document.getElementById('contadorComponentesSeleccionados') as HTMLElement | null;
    const contadorImagenes = document.getElementById('contadorImagenesDiagSeleccionadas') as HTMLElement | null;
    
    // Contador para IDs únicos de componentes dinámicos
    let contadorComponentesDinamicos = 0;
    const componentesAgregados = new Set<string>(); // Para evitar duplicados

    // Si no hay modal en la página, no ejecutar nada
    if (!form) return;

    // ====================================================================
    // 1. Actualización en tiempo real del asunto
    // ====================================================================
    if (inputFolio && spanFolioPreview) {
        inputFolio.addEventListener('input', () => {
            const folioValue = inputFolio.value.trim();
            spanFolioPreview.textContent = folioValue || '___';
        });
    }

    // ====================================================================
    // 2. Contador de componentes seleccionados
    // ====================================================================
    function actualizarContadorComponentes(): void {
        // Contar componentes predefinidos
        const checkboxesPredefinidos = document.querySelectorAll<HTMLInputElement>('.checkbox-componente');
        let seleccionados = 0;
        checkboxesPredefinidos.forEach(cb => {
            if (cb.checked) seleccionados++;
        });
        
        // Contar componentes adicionales dinámicos
        const checkboxesDinamicos = document.querySelectorAll<HTMLInputElement>('.checkbox-componente-dinamico');
        checkboxesDinamicos.forEach(cb => {
            if (cb.checked) seleccionados++;
        });
        
        if (contadorComponentes) {
            contadorComponentes.textContent = `${seleccionados} seleccionado${seleccionados !== 1 ? 's' : ''}`;
        }
    }

    // Event listeners para checkboxes de componentes predefinidos
    document.querySelectorAll<HTMLInputElement>('.checkbox-componente').forEach(cb => {
        cb.addEventListener('change', actualizarContadorComponentes);
    });

    // ====================================================================
    // 3. Contador de imágenes seleccionadas
    // ====================================================================
    function actualizarContadorImagenes(): void {
        const checkboxes = document.querySelectorAll<HTMLInputElement>('.checkbox-imagen-diag');
        let seleccionadas = 0;
        checkboxes.forEach(cb => {
            if (cb.checked) seleccionadas++;
        });
        if (contadorImagenes) {
            contadorImagenes.textContent = `${seleccionadas} seleccionada${seleccionadas !== 1 ? 's' : ''}`;
        }
    }

    // Event listeners para checkboxes de imágenes
    document.querySelectorAll<HTMLInputElement>('.checkbox-imagen-diag').forEach(cb => {
        cb.addEventListener('change', actualizarContadorImagenes);
    });

    // Seleccionar/deseleccionar todas las imágenes
    if (checkboxSelectAllImgs) {
        checkboxSelectAllImgs.addEventListener('change', () => {
            const checked = checkboxSelectAllImgs.checked;
            document.querySelectorAll<HTMLInputElement>('.checkbox-imagen-diag').forEach(cb => {
                cb.checked = checked;
            });
            actualizarContadorImagenes();
        });
    }

    // ====================================================================
    // 4. Componentes adicionales dinámicos
    // ====================================================================
    
    /**
     * Carga el dropdown con componentes adicionales disponibles.
     * Lee la lista de componentes del data-attribute y los inserta en el dropdown.
     */
    function cargarDropdownComponentes(): void {
        if (!btnAgregarComponente || !dropdownComponentesAdicionales) return;
        
        try {
            const componentesJSON = btnAgregarComponente.getAttribute('data-componentes');
            if (!componentesJSON) {
                dropdownComponentesAdicionales.innerHTML = '<li><span class="dropdown-item text-muted small">No hay componentes adicionales disponibles</span></li>';
                return;
            }
            
            const componentes: string[] = JSON.parse(componentesJSON);
            
            if (componentes.length === 0) {
                dropdownComponentesAdicionales.innerHTML = '<li><span class="dropdown-item text-muted small">No hay componentes adicionales disponibles</span></li>';
                return;
            }
            
            // Limpiar dropdown
            dropdownComponentesAdicionales.innerHTML = '';
            
            // Agregar cada componente como opción
            componentes.forEach(nombreComponente => {
                const li = document.createElement('li');
                const a = document.createElement('a');
                a.className = 'dropdown-item cursor-pointer';
                a.style.color = '#000'; // Forzar color negro para visibilidad
                a.textContent = nombreComponente;
                a.addEventListener('click', () => agregarComponenteDinamico(nombreComponente));
                li.appendChild(a);
                dropdownComponentesAdicionales.appendChild(li);
            });
        } catch (error) {
            console.error('Error al cargar componentes disponibles:', error);
            dropdownComponentesAdicionales.innerHTML = '<li><span class="dropdown-item text-danger small">Error cargando componentes</span></li>';
        }
    }
    
    /**
     * Agrega una fila dinámica para un componente adicional.
     */
    function agregarComponenteDinamico(nombreComponente: string): void {
        if (!componentesAdicionalesTbody) return;
        
        // Evitar duplicados
        if (componentesAgregados.has(nombreComponente)) {
            alert(`⚠️ El componente "${nombreComponente}" ya ha sido agregado.`);
            return;
        }
        
        contadorComponentesDinamicos++;
        const idUnico = `comp_dinamico_${contadorComponentesDinamicos}`;
        
        // Crear fila
        const tr = document.createElement('tr');
        tr.className = 'table-success'; // Destacar que es dinámico
        tr.setAttribute('data-componente-nombre', nombreComponente);
        
        // Celda checkbox
        const tdCheck = document.createElement('td');
        tdCheck.className = 'text-center align-middle';
        const checkbox = document.createElement('input');
        checkbox.className = 'form-check-input checkbox-componente-dinamico';
        checkbox.type = 'checkbox';
        checkbox.checked = true; // Pre-seleccionado
        checkbox.id = idUnico;
        checkbox.setAttribute('data-componente-db', nombreComponente);
        checkbox.addEventListener('change', actualizarContadorComponentes);
        tdCheck.appendChild(checkbox);
        
        // Celda nombre
        const tdNombre = document.createElement('td');
        tdNombre.className = 'align-middle fw-semibold';
        const label = document.createElement('label');
        label.htmlFor = idUnico;
        label.className = 'mb-0 cursor-pointer d-block';
        label.innerHTML = `${nombreComponente} <span class="badge bg-success ms-2">ADICIONAL</span>`;
        tdNombre.appendChild(label);
        
        // Celda DPN
        const tdDpn = document.createElement('td');
        tdDpn.className = 'align-middle';
        const inputDpn = document.createElement('input');
        inputDpn.type = 'text';
        inputDpn.className = 'form-control form-control-sm input-dpn-dinamico';
        inputDpn.setAttribute('data-componente-db', nombreComponente);
        inputDpn.placeholder = 'Ej: DPN: 0XPJWG';
        tdDpn.appendChild(inputDpn);
        
        // Botón eliminar
        const btnEliminar = document.createElement('button');
        btnEliminar.type = 'button';
        btnEliminar.className = 'btn btn-danger btn-sm ms-2';
        btnEliminar.innerHTML = '<i class="bi bi-x-circle"></i>';
        btnEliminar.title = 'Eliminar componente';
        btnEliminar.addEventListener('click', () => eliminarComponenteDinamico(tr, nombreComponente));
        tdDpn.appendChild(btnEliminar);
        
        // Ensamblar fila
        tr.appendChild(tdCheck);
        tr.appendChild(tdNombre);
        tr.appendChild(tdDpn);
        
        // Insertar en tabla
        componentesAdicionalesTbody.appendChild(tr);
        
        // Registrar como agregado
        componentesAgregados.add(nombreComponente);
        
        // Actualizar contador
        actualizarContadorComponentes();
    }
    
    /**
     * Elimina una fila de componente dinámico.
     */
    function eliminarComponenteDinamico(fila: HTMLTableRowElement, nombreComponente: string): void {
        if (confirm(`¿Eliminar el componente "${nombreComponente}"?`)) {
            fila.remove();
            componentesAgregados.delete(nombreComponente);
            actualizarContadorComponentes();
        }
    }
    
    // Cargar dropdown al inicializar
    cargarDropdownComponentes();

    // ====================================================================
    // 4.4. Edición inline del email del cliente
    // ====================================================================
    
    /**
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Esta sección maneja la edición inline del email del destinatario.
     * El patrón "inline edit" permite editar un valor directamente en la 
     * interfaz sin abrir otra página o modal:
     * 1. El email se muestra como texto normal con un botón "Editar"
     * 2. Al hacer clic en Editar, el texto se convierte en un input editable
     * 3. El usuario modifica el email y hace clic en Guardar (o Cancelar)
     * 4. Al guardar, se envía un AJAX POST al servidor para persistir el cambio
     * 5. Si todo sale bien, el texto se actualiza con el nuevo email
     */
    
    const btnEditarEmail = document.getElementById('btnEditarEmailCliente') as HTMLButtonElement | null;
    const vistaLectura = document.getElementById('emailClienteVistaLectura') as HTMLElement | null;
    const vistaEdicion = document.getElementById('emailClienteVistaEdicion') as HTMLElement | null;
    const inputEditarEmail = document.getElementById('inputEditarEmailCliente') as HTMLInputElement | null;
    const btnGuardarEmail = document.getElementById('btnGuardarEmailCliente') as HTMLButtonElement | null;
    const btnCancelarEmail = document.getElementById('btnCancelarEmailCliente') as HTMLButtonElement | null;
    const spanEmailCliente = document.getElementById('spanEmailCliente') as HTMLElement | null;
    const feedbackEmail = document.getElementById('feedbackEmailCliente') as HTMLElement | null;
    const cardDestinatario = document.getElementById('cardDestinatarioEmail') as HTMLElement | null;
    const badgeEmailValido = document.getElementById('badgeEmailValido') as HTMLElement | null;
    
    // Obtener el ID del detalle_equipo del data attribute del formulario
    const detalleEquipoId = form ? form.getAttribute('data-detalle-equipo-id') : null;
    
    // Log de diagnóstico para verificar que los elementos se encontraron
    console.log('[Diagnostico Modal] Edición email - Elementos encontrados:', {
        btnEditarEmail: !!btnEditarEmail,
        vistaLectura: !!vistaLectura,
        vistaEdicion: !!vistaEdicion,
        inputEditarEmail: !!inputEditarEmail,
        btnGuardarEmail: !!btnGuardarEmail,
        btnCancelarEmail: !!btnCancelarEmail,
        spanEmailCliente: !!spanEmailCliente,
        detalleEquipoId: detalleEquipoId,
    });
    
    /**
     * Cambia entre modo lectura y modo edición.
     */
    function toggleModoEdicion(mostrarEdicion: boolean): void {
        if (vistaLectura) vistaLectura.style.display = mostrarEdicion ? 'none' : 'flex';
        if (vistaEdicion) vistaEdicion.style.display = mostrarEdicion ? 'block' : 'none';
        
        if (mostrarEdicion && inputEditarEmail) {
            // Enfocar el input y seleccionar el texto
            setTimeout(() => {
                inputEditarEmail.focus();
                inputEditarEmail.select();
            }, 100);
        }
        
        // Limpiar feedback
        if (feedbackEmail) {
            feedbackEmail.textContent = '';
            feedbackEmail.className = 'text-muted mt-1 d-block';
        }
    }
    
    /**
     * Actualiza la UI después de un cambio exitoso de email.
     * Cambia los estilos visuales del card para reflejar el estado válido.
     */
    function actualizarUIEmailExitoso(nuevoEmail: string): void {
        // Actualizar el texto del email
        if (spanEmailCliente) {
            spanEmailCliente.textContent = nuevoEmail;
            spanEmailCliente.className = ''; // Quitar clase text-danger si existía
        }
        
        // Actualizar el card a estilo "válido" (verde)
        if (cardDestinatario) {
            cardDestinatario.style.background = 'linear-gradient(135deg, #e8f5e9 0%, #f1f8e9 100%)';
            cardDestinatario.style.border = '2px solid #4caf50';
            
            // Cambiar ícono del card a check
            const iconoCard = cardDestinatario.querySelector('.bi-exclamation-triangle-fill');
            if (iconoCard) {
                iconoCard.className = 'bi bi-person-check-fill text-success fs-2 me-3 flex-shrink-0';
            }
        }
        
        // Actualizar badge a "VÁLIDO"
        if (badgeEmailValido) {
            badgeEmailValido.className = 'badge bg-success ms-2';
            badgeEmailValido.innerHTML = '<i class="bi bi-check-circle-fill"></i> VÁLIDO';
        }
        
        // Actualizar el botón a "Editar" (ya no "Agregar")
        if (btnEditarEmail) {
            btnEditarEmail.className = 'btn btn-sm btn-outline-primary ms-2 py-0 px-2';
            btnEditarEmail.innerHTML = '<i class="bi bi-pencil-fill"></i> Editar';
            btnEditarEmail.title = 'Editar email del cliente';
        }
        
        // Actualizar el título del card
        const tituloCard = cardDestinatario?.querySelector('.fw-bold');
        if (tituloCard) {
            const textoClase = tituloCard.className;
            if (textoClase.includes('text-warning')) {
                tituloCard.className = textoClase.replace('text-warning', 'text-success');
            }
        }
        
        // Actualizar el valor del input para futuras ediciones
        if (inputEditarEmail) {
            inputEditarEmail.value = nuevoEmail;
        }
    }
    
    /**
     * Envía el nuevo email al servidor vía AJAX.
     */
    async function guardarEmailCliente(): Promise<void> {
        console.log('[Diagnostico Modal] guardarEmailCliente() llamada');
        console.log('[Diagnostico Modal] detalleEquipoId:', detalleEquipoId);
        console.log('[Diagnostico Modal] inputEditarEmail:', inputEditarEmail?.value);
        
        if (!inputEditarEmail) {
            console.error('[Diagnostico Modal] inputEditarEmail no encontrado en el DOM');
            return;
        }
        
        if (!detalleEquipoId) {
            console.error('[Diagnostico Modal] detalleEquipoId es null/vacío. Verifica data-detalle-equipo-id en el form.');
            if (feedbackEmail) {
                feedbackEmail.textContent = 'Error interno: No se pudo identificar el equipo. Recarga la página.';
                feedbackEmail.className = 'text-danger mt-1 d-block small';
            }
            return;
        }
        
        const nuevoEmail = inputEditarEmail.value.trim();
        
        // Validación básica en el cliente
        if (!nuevoEmail) {
            if (feedbackEmail) {
                feedbackEmail.textContent = 'El email no puede estar vacío.';
                feedbackEmail.className = 'text-danger mt-1 d-block small';
            }
            inputEditarEmail.classList.add('is-invalid');
            return;
        }
        
        // Validar formato con regex básico
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(nuevoEmail)) {
            if (feedbackEmail) {
                feedbackEmail.textContent = 'Formato de email inválido. Ejemplo: usuario@dominio.com';
                feedbackEmail.className = 'text-danger mt-1 d-block small';
            }
            inputEditarEmail.classList.add('is-invalid');
            return;
        }
        
        // Deshabilitar botones durante el envío
        if (btnGuardarEmail) {
            btnGuardarEmail.disabled = true;
            btnGuardarEmail.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
        }
        if (btnCancelarEmail) btnCancelarEmail.disabled = true;
        inputEditarEmail.readOnly = true;
        
        try {
            // Obtener token CSRF
            const csrfToken = (document.querySelector('[name=csrfmiddlewaretoken]') as HTMLInputElement)?.value || '';
            
            const response = await fetch(
                `/servicio-tecnico/api/detalle-equipo/${detalleEquipoId}/actualizar-email/`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    body: JSON.stringify({ email: nuevoEmail }),
                }
            );
            
            const data = await response.json();
            
            if (data.success) {
                console.log('[Diagnostico Modal] Email actualizado exitosamente:', nuevoEmail);
                
                // Éxito: actualizar la UI
                actualizarUIEmailExitoso(nuevoEmail);
                toggleModoEdicion(false);
                
                // Efecto visual de confirmación en el span del email
                if (spanEmailCliente) {
                    spanEmailCliente.style.transition = 'background-color 0.3s ease';
                    spanEmailCliente.style.backgroundColor = '#c8e6c9';
                    spanEmailCliente.style.padding = '2px 6px';
                    spanEmailCliente.style.borderRadius = '4px';
                    setTimeout(() => {
                        spanEmailCliente.style.backgroundColor = 'transparent';
                    }, 2500);
                }
            } else {
                // Error del servidor
                console.error('[Diagnostico Modal] Error del servidor:', data.error);
                if (feedbackEmail) {
                    feedbackEmail.textContent = data.error || 'Error al guardar el email.';
                    feedbackEmail.className = 'text-danger mt-1 d-block small';
                }
                inputEditarEmail.classList.add('is-invalid');
            }
        } catch (error) {
            console.error('Error al actualizar email del cliente:', error);
            if (feedbackEmail) {
                feedbackEmail.textContent = 'Error de conexión. Inténtalo de nuevo.';
                feedbackEmail.className = 'text-danger mt-1 d-block small';
            }
        } finally {
            // Restaurar botones
            if (btnGuardarEmail) {
                btnGuardarEmail.disabled = false;
                btnGuardarEmail.innerHTML = '<i class="bi bi-check-lg"></i>';
            }
            if (btnCancelarEmail) btnCancelarEmail.disabled = false;
            inputEditarEmail.readOnly = false;
        }
    }
    
    // Event listeners para la edición inline
    if (btnEditarEmail) {
        btnEditarEmail.addEventListener('click', () => {
            toggleModoEdicion(true);
        });
    }
    
    if (btnGuardarEmail) {
        btnGuardarEmail.addEventListener('click', (e: Event) => {
            e.preventDefault(); // Evitar que el form padre haga submit
            e.stopPropagation();
            console.log('[Diagnostico Modal] Botón guardar email clickeado');
            guardarEmailCliente();
        });
    }
    
    if (btnCancelarEmail) {
        btnCancelarEmail.addEventListener('click', () => {
            // Restaurar valor original
            if (inputEditarEmail && spanEmailCliente) {
                const emailActual = spanEmailCliente.textContent?.trim() || '';
                // Solo restaurar si es un email válido (no "No configurado")
                if (emailActual && emailActual !== 'No configurado') {
                    inputEditarEmail.value = emailActual;
                } else {
                    inputEditarEmail.value = '';
                }
            }
            if (inputEditarEmail) inputEditarEmail.classList.remove('is-invalid');
            toggleModoEdicion(false);
        });
    }
    
    // Permitir guardar con Enter y cancelar con Escape
    if (inputEditarEmail) {
        inputEditarEmail.addEventListener('keydown', (event: KeyboardEvent) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                event.stopPropagation(); // Evitar que el form padre haga submit
                console.log('[Diagnostico Modal] Enter presionado en input email');
                guardarEmailCliente();
            } else if (event.key === 'Escape') {
                event.preventDefault();
                btnCancelarEmail?.click();
            }
        });
        
        // Quitar estado de error cuando el usuario empiece a escribir
        inputEditarEmail.addEventListener('input', () => {
            inputEditarEmail.classList.remove('is-invalid');
            if (feedbackEmail) {
                feedbackEmail.textContent = '';
                feedbackEmail.className = 'text-muted mt-1 d-block';
            }
        });
    }

    // ====================================================================
    // 4.5. Detección automática de piezas del diagnóstico
    // ====================================================================
    
    /**
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Esta sección maneja el botón "Detectar Piezas" que analiza el texto
     * del diagnóstico y muestra las piezas encontradas como sugerencias
     * interactivas. El agente puede aceptar cada sugerencia para que
     * los campos DPN se llenen automáticamente.
     */
    
    const btnDetectarPiezas = document.getElementById('btnDetectarPiezas') as HTMLButtonElement | null;
    const panelPiezasDetectadas = document.getElementById('panelPiezasDetectadas') as HTMLElement | null;
    const contenedorPiezas = document.getElementById('contenedorPiezasDetectadas') as HTMLElement | null;
    const btnCerrarPanel = document.getElementById('btnCerrarPanelPiezas') as HTMLButtonElement | null;
    const btnAplicarTodas = document.getElementById('btnAplicarTodasPiezas') as HTMLButtonElement | null;
    
    // Almacenar las piezas detectadas para referencia
    let piezasDetectadasActuales: PiezaDetectada[] = [];
    
    /**
     * Aplica una pieza detectada: marca el checkbox del componente
     * correspondiente y llena su campo DPN con el número de parte.
     * Si el componente no existe en los 18 predefinidos, lo agrega
     * como componente dinámico.
     */
    function aplicarPieza(pieza: PiezaDetectada, filaUI: HTMLElement): void {
        if (!pieza.componenteDb) return;
        
        const componenteDb = pieza.componenteDb;
        
        // Buscar si existe como componente predefinido
        const checkboxPredefinido = document.querySelector<HTMLInputElement>(
            `.checkbox-componente[data-componente-db="${componenteDb}"]`
        );
        
        if (checkboxPredefinido) {
            // Es un componente predefinido — marcar checkbox y llenar DPN
            const inputDpn = document.querySelector<HTMLInputElement>(
                `.input-dpn[data-componente-db="${componenteDb}"]`
            );
            
            // Verificar si ya tiene un DPN diferente escrito
            if (inputDpn && inputDpn.value.trim() && inputDpn.value.trim() !== pieza.numeroParte) {
                const sobreescribir = confirm(
                    `El componente "${componenteDb}" ya tiene el DPN "${inputDpn.value.trim()}".\n\n` +
                    `¿Deseas reemplazarlo con "${pieza.numeroParte}"?`
                );
                if (!sobreescribir) return;
            }
            
            checkboxPredefinido.checked = true;
            if (inputDpn) {
                inputDpn.value = pieza.numeroParte;
                // Efecto visual de "llenado automático"
                inputDpn.style.transition = 'background-color 0.5s ease';
                inputDpn.style.backgroundColor = '#d4edda';
                setTimeout(() => {
                    inputDpn.style.backgroundColor = '';
                }, 2000);
            }
        } else {
            // No es predefinido — buscar si ya existe como dinámico
            const checkboxDinamico = document.querySelector<HTMLInputElement>(
                `.checkbox-componente-dinamico[data-componente-db="${componenteDb}"]`
            );
            
            if (checkboxDinamico) {
                // Ya existe como dinámico — solo llenar DPN
                checkboxDinamico.checked = true;
                const inputDpnDinamico = document.querySelector<HTMLInputElement>(
                    `.input-dpn-dinamico[data-componente-db="${componenteDb}"]`
                );
                if (inputDpnDinamico) {
                    inputDpnDinamico.value = pieza.numeroParte;
                    inputDpnDinamico.style.transition = 'background-color 0.5s ease';
                    inputDpnDinamico.style.backgroundColor = '#d4edda';
                    setTimeout(() => {
                        inputDpnDinamico.style.backgroundColor = '';
                    }, 2000);
                }
            } else {
                // No existe — agregarlo como componente dinámico
                agregarComponenteDinamico(componenteDb);
                
                // Esperar un tick para que el DOM se actualice y luego llenar DPN
                setTimeout(() => {
                    const nuevoInputDpn = document.querySelector<HTMLInputElement>(
                        `.input-dpn-dinamico[data-componente-db="${componenteDb}"]`
                    );
                    if (nuevoInputDpn) {
                        nuevoInputDpn.value = pieza.numeroParte;
                        nuevoInputDpn.style.transition = 'background-color 0.5s ease';
                        nuevoInputDpn.style.backgroundColor = '#d4edda';
                        setTimeout(() => {
                            nuevoInputDpn.style.backgroundColor = '';
                        }, 2000);
                    }
                }, 50);
            }
        }
        
        // Actualizar contador
        actualizarContadorComponentes();
        
        // Marcar la fila de la UI como aplicada
        filaUI.classList.remove('list-group-item-light', 'list-group-item-warning');
        filaUI.classList.add('list-group-item-success');
        
        const btnAplicar = filaUI.querySelector('.btn-aplicar-pieza') as HTMLButtonElement | null;
        if (btnAplicar) {
            btnAplicar.disabled = true;
            btnAplicar.innerHTML = '<i class="bi bi-check-lg"></i> Aplicado';
            btnAplicar.classList.remove('btn-outline-success', 'btn-outline-primary');
            btnAplicar.classList.add('btn-success');
        }
        
        // Deshabilitar el dropdown de asignación manual si existe
        const selectManual = filaUI.querySelector('.select-asignar-componente') as HTMLSelectElement | null;
        if (selectManual) {
            selectManual.disabled = true;
        }
    }
    
    /**
     * Construye la UI del panel de piezas detectadas.
     * Cada pieza se muestra como una fila con:
     * - Badge de confianza (verde = alta, amarillo = sin match)
     * - Descripción de la pieza y número de parte
     * - Botón "Aplicar" o dropdown para asignación manual
     * 
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Cuando dos o más piezas apuntan al mismo componente (por ejemplo,
     * "PALMREST CON TECLADO" y "TOUCHPAD" ambas matchean a "Teclado"),
     * solo la primera obtiene el botón "Aplicar" directo. Las demás
     * muestran un dropdown con la sugerencia preseleccionada para que
     * el agente pueda reasignarlas a otro componente manualmente.
     */
    function renderizarPiezasDetectadas(piezas: PiezaDetectada[]): void {
        if (!contenedorPiezas || !panelPiezasDetectadas) return;
        
        // Limpiar contenido anterior
        contenedorPiezas.innerHTML = '';
        
        if (piezas.length === 0) {
            contenedorPiezas.innerHTML = `
                <div class="alert alert-info mb-0">
                    <i class="bi bi-info-circle"></i>
                    <strong>No se detectaron números de parte</strong> en el texto del diagnóstico.
                    <br><small class="text-muted">Asegúrate de que el diagnóstico contenga frases como 
                    "SE ANEXAN NÚMEROS DE PARTE" seguidas de las piezas con sus códigos.</small>
                </div>
            `;
            panelPiezasDetectadas.style.display = 'block';
            if (btnAplicarTodas) btnAplicarTodas.style.display = 'none';
            return;
        }
        
        // Detectar componentes duplicados:
        // Contar cuántas piezas apuntan al mismo componenteDb
        // La primera de cada componente obtiene "Aplicar" directo,
        // las siguientes obtienen dropdown con sugerencia.
        const componenteUsado = new Set<string>();
        
        // Construir lista de piezas
        const lista = document.createElement('div');
        lista.className = 'list-group list-group-flush';
        
        let piezasConMatchUnico = 0;
        
        piezas.forEach((pieza, index) => {
            // Determinar si este componente ya fue "reclamado" por otra pieza
            const esComponenteDuplicado = pieza.componenteDb !== null && componenteUsado.has(pieza.componenteDb);
            
            // Registrar el componente como usado (solo si tiene match)
            if (pieza.componenteDb) {
                componenteUsado.add(pieza.componenteDb);
            }
            
            // Determinar si esta pieza debe tener aplicación directa o dropdown
            const necesitaDropdown = !pieza.componenteDb || esComponenteDuplicado;
            
            const fila = document.createElement('div');
            fila.className = necesitaDropdown
                ? 'list-group-item list-group-item-warning d-flex align-items-center justify-content-between py-2'
                : 'list-group-item list-group-item-light d-flex align-items-center justify-content-between py-2';
            fila.id = `pieza-detectada-${index}`;
            
            // Marcar filas duplicadas con data-attribute para que "Aplicar todas" las salte
            if (esComponenteDuplicado) {
                fila.setAttribute('data-duplicado', 'true');
            }
            
            // Lado izquierdo: badge + info de la pieza
            const infoDiv = document.createElement('div');
            infoDiv.className = 'd-flex align-items-center flex-wrap gap-2';
            
            // Badge de confianza
            const badge = document.createElement('span');
            if (esComponenteDuplicado) {
                // Componente duplicado — badge naranja con icono de conflicto
                badge.className = 'badge bg-warning text-dark';
                badge.innerHTML = '<i class="bi bi-diagram-2-fill"></i>';
                badge.title = `Conflicto: otra pieza ya usa "${pieza.componenteDb}" — asigna manualmente`;
            } else if (pieza.componenteDb && pieza.confianza === 'alta') {
                badge.className = 'badge bg-success';
                badge.innerHTML = '<i class="bi bi-check-circle-fill"></i>';
                badge.title = 'Coincidencia alta';
            } else if (pieza.componenteDb && pieza.confianza === 'media') {
                badge.className = 'badge bg-info';
                badge.innerHTML = '<i class="bi bi-question-circle-fill"></i>';
                badge.title = 'Coincidencia media';
            } else {
                badge.className = 'badge bg-warning text-dark';
                badge.innerHTML = '<i class="bi bi-exclamation-triangle-fill"></i>';
                badge.title = 'Sin coincidencia automática';
            }
            infoDiv.appendChild(badge);
            
            // Descripción de la pieza
            const descSpan = document.createElement('span');
            descSpan.className = 'fw-semibold';
            descSpan.textContent = pieza.descripcionPieza;
            infoDiv.appendChild(descSpan);
            
            // Flecha separadora
            const arrow = document.createElement('i');
            arrow.className = 'bi bi-arrow-right text-muted';
            infoDiv.appendChild(arrow);
            
            // Número de parte (destacado)
            const codeSpan = document.createElement('code');
            codeSpan.className = 'fs-6 fw-bold text-primary';
            codeSpan.textContent = pieza.numeroParte;
            infoDiv.appendChild(codeSpan);
            
            // Si hay match, mostrar a cuál componente apunta
            if (pieza.componenteDb) {
                const matchSpan = document.createElement('span');
                if (esComponenteDuplicado) {
                    matchSpan.className = 'badge bg-warning bg-opacity-25 text-dark border border-warning';
                    matchSpan.innerHTML = `<i class="bi bi-diagram-2"></i> ${pieza.componenteDb} <small>(duplicado)</small>`;
                } else {
                    matchSpan.className = 'badge bg-light text-dark border';
                    matchSpan.innerHTML = `<i class="bi bi-link-45deg"></i> ${pieza.componenteDb}`;
                }
                infoDiv.appendChild(matchSpan);
                
                // Solo contar como match único (para "Aplicar todas") si no es duplicado
                if (!esComponenteDuplicado) {
                    piezasConMatchUnico++;
                }
            }
            
            fila.appendChild(infoDiv);
            
            // Lado derecho: acciones
            const accionesDiv = document.createElement('div');
            accionesDiv.className = 'd-flex align-items-center gap-2';
            
            if (!necesitaDropdown) {
                // Tiene match único — botón "Aplicar" directo
                const btnAplicar = document.createElement('button');
                btnAplicar.type = 'button';
                btnAplicar.className = 'btn btn-sm btn-outline-success btn-aplicar-pieza';
                btnAplicar.innerHTML = '<i class="bi bi-check2-square"></i> Aplicar';
                btnAplicar.title = `Aplicar ${pieza.numeroParte} a ${pieza.componenteDb}`;
                btnAplicar.addEventListener('click', () => aplicarPieza(pieza, fila));
                accionesDiv.appendChild(btnAplicar);
            } else {
                // Sin match O componente duplicado — dropdown para asignar manualmente
                const selectComponente = crearDropdownComponentes(pieza.componenteDb);
                accionesDiv.appendChild(selectComponente);
                
                // Botón aplicar (se habilita al seleccionar componente)
                const btnAplicarManual = document.createElement('button');
                btnAplicarManual.type = 'button';
                btnAplicarManual.className = 'btn btn-sm btn-outline-primary btn-aplicar-pieza';
                btnAplicarManual.innerHTML = '<i class="bi bi-check2-square"></i>';
                btnAplicarManual.title = 'Aplicar a componente seleccionado';
                btnAplicarManual.disabled = !selectComponente.value;
                
                selectComponente.addEventListener('change', () => {
                    btnAplicarManual.disabled = !selectComponente.value;
                });
                
                btnAplicarManual.addEventListener('click', () => {
                    if (selectComponente.value) {
                        // Crear una copia de la pieza con el componente asignado manualmente
                        const piezaAsignada: PiezaDetectada = {
                            ...pieza,
                            componenteDb: selectComponente.value,
                            confianza: 'alta'
                        };
                        aplicarPieza(piezaAsignada, fila);
                    }
                });
                
                accionesDiv.appendChild(btnAplicarManual);
            }
            
            fila.appendChild(accionesDiv);
            lista.appendChild(fila);
        });
        
        contenedorPiezas.appendChild(lista);
        
        // Mostrar/ocultar botón "Aplicar todas" (solo para matches únicos)
        if (btnAplicarTodas) {
            btnAplicarTodas.style.display = piezasConMatchUnico > 0 ? 'inline-flex' : 'none';
            btnAplicarTodas.innerHTML = `<i class="bi bi-check-all"></i> Aplicar todas las coincidencias (${piezasConMatchUnico})`;
        }
        
        // Mostrar el panel
        panelPiezasDetectadas.style.display = 'block';
    }
    
    /**
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Crea un <select> (dropdown) con todos los componentes disponibles
     * para asignación manual. Si se proporciona una sugerencia (componenteSugerido),
     * esa opción aparece preseleccionada para que el agente solo tenga que
     * confirmar o cambiar.
     * 
     * @param componenteSugerido - Nombre del componente que el parser sugiere (puede ser null)
     */
    function crearDropdownComponentes(componenteSugerido: string | null): HTMLSelectElement {
        const selectComponente = document.createElement('select');
        selectComponente.className = 'form-select form-select-sm select-asignar-componente';
        selectComponente.style.maxWidth = '180px';
        selectComponente.innerHTML = '<option value="">Asignar a...</option>';
        
        // Agregar los 18 componentes predefinidos como opciones
        const checkboxesExistentes = document.querySelectorAll<HTMLInputElement>('.checkbox-componente');
        checkboxesExistentes.forEach(cb => {
            const nombre = cb.getAttribute('data-componente-db') || '';
            const option = document.createElement('option');
            option.value = nombre;
            option.textContent = nombre;
            selectComponente.appendChild(option);
        });
        
        // Separador y opción de componentes adicionales (del dropdown)
        if (btnAgregarComponente) {
            try {
                const componentesJSON = btnAgregarComponente.getAttribute('data-componentes');
                if (componentesJSON) {
                    const componentesAdicionales: string[] = JSON.parse(componentesJSON);
                    if (componentesAdicionales.length > 0) {
                        const optSeparador = document.createElement('option');
                        optSeparador.disabled = true;
                        optSeparador.textContent = '── Adicionales ──';
                        selectComponente.appendChild(optSeparador);
                        
                        componentesAdicionales.forEach(nombre => {
                            const option = document.createElement('option');
                            option.value = nombre;
                            option.textContent = nombre;
                            selectComponente.appendChild(option);
                        });
                    }
                }
            } catch (_e) { /* Ignorar errores de JSON */ }
        }
        
        // Si hay sugerencia, preseleccionarla
        if (componenteSugerido) {
            selectComponente.value = componenteSugerido;
        }
        
        return selectComponente;
    }
    
    // Event listener para el botón "Detectar Piezas"
    if (btnDetectarPiezas) {
        btnDetectarPiezas.addEventListener('click', () => {
            // Obtener el texto del diagnóstico desde el data-attribute
            const textoDiagnostico = btnDetectarPiezas.getAttribute('data-diagnostico') || '';
            
            if (!textoDiagnostico.trim()) {
                if (panelPiezasDetectadas && contenedorPiezas) {
                    contenedorPiezas.innerHTML = `
                        <div class="alert alert-warning mb-0">
                            <i class="bi bi-exclamation-triangle"></i>
                            <strong>Sin diagnóstico.</strong> No hay texto de diagnóstico disponible para analizar.
                        </div>
                    `;
                    panelPiezasDetectadas.style.display = 'block';
                }
                return;
            }
            
            // Efecto visual de "analizando"
            btnDetectarPiezas.disabled = true;
            const textoOriginalBtn = btnDetectarPiezas.innerHTML;
            btnDetectarPiezas.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Analizando...';
            
            // Pequeño delay para dar feedback visual
            setTimeout(() => {
                // Ejecutar detección
                piezasDetectadasActuales = extraerPiezasDiagnostico(textoDiagnostico);
                
                // Renderizar resultados
                renderizarPiezasDetectadas(piezasDetectadasActuales);
                
                // Restaurar botón
                btnDetectarPiezas.disabled = false;
                btnDetectarPiezas.innerHTML = textoOriginalBtn;
            }, 300);
        });
    }
    
    // Botón "Cerrar panel"
    if (btnCerrarPanel && panelPiezasDetectadas) {
        btnCerrarPanel.addEventListener('click', () => {
            panelPiezasDetectadas.style.display = 'none';
        });
    }
    
    // Botón "Aplicar todas las coincidencias"
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // "Aplicar todas" solo aplica las piezas con match único (no duplicadas).
    // Las piezas duplicadas requieren intervención manual del agente.
    if (btnAplicarTodas) {
        btnAplicarTodas.addEventListener('click', () => {
            let aplicadas = 0;
            
            piezasDetectadasActuales.forEach((pieza, index) => {
                if (pieza.componenteDb) {
                    const filaUI = document.getElementById(`pieza-detectada-${index}`);
                    if (filaUI) {
                        // Saltar piezas que son duplicadas (requieren asignación manual)
                        if (filaUI.getAttribute('data-duplicado') === 'true') return;
                        
                        // Verificar que no fue ya aplicada
                        const btnAplicar = filaUI.querySelector('.btn-aplicar-pieza') as HTMLButtonElement | null;
                        if (btnAplicar && !btnAplicar.disabled) {
                            aplicarPieza(pieza, filaUI);
                            aplicadas++;
                        }
                    }
                }
            });
            
            if (aplicadas > 0) {
                btnAplicarTodas.disabled = true;
                btnAplicarTodas.innerHTML = `<i class="bi bi-check-all"></i> ${aplicadas} pieza${aplicadas !== 1 ? 's' : ''} aplicada${aplicadas !== 1 ? 's' : ''}`;
                btnAplicarTodas.classList.remove('btn-outline-primary');
                btnAplicarTodas.classList.add('btn-success');
            }
        });
    }

    // ====================================================================
    // 5. Construir JSON de componentes
    // ====================================================================
    function construirComponentesJSON(): ComponenteData[] {
        const componentes: ComponenteData[] = [];
        
        // 1. Componentes predefinidos (de la tabla estática)
        const checkboxesPredefinidos = document.querySelectorAll<HTMLInputElement>('.checkbox-componente');
        
        checkboxesPredefinidos.forEach(cb => {
            const componenteDb = cb.getAttribute('data-componente-db') || '';
            const inputDpn = document.querySelector<HTMLInputElement>(
                `.input-dpn[data-componente-db="${componenteDb}"]`
            );
            
            componentes.push({
                componente_db: componenteDb,
                dpn: inputDpn ? inputDpn.value.trim() : '',
                seleccionado: cb.checked
            });
        });
        
        // 2. Componentes adicionales dinámicos (agregados por el usuario)
        const checkboxesDinamicos = document.querySelectorAll<HTMLInputElement>('.checkbox-componente-dinamico');
        
        checkboxesDinamicos.forEach(cb => {
            const componenteDb = cb.getAttribute('data-componente-db') || '';
            const inputDpn = document.querySelector<HTMLInputElement>(
                `.input-dpn-dinamico[data-componente-db="${componenteDb}"]`
            );
            
            componentes.push({
                componente_db: componenteDb,
                dpn: inputDpn ? inputDpn.value.trim() : '',
                seleccionado: cb.checked
            });
        });
        
        return componentes;
    }

    // ====================================================================
    // 6. Actualizar vista previa del PDF
    // ====================================================================
    if (btnRefrescarPreview && iframePreview) {
        btnRefrescarPreview.addEventListener('click', () => {
            const folio = inputFolio ? inputFolio.value.trim() : 'PREVIEW';
            const componentes = construirComponentesJSON();
            
            // Construir URL con parámetros
            const previewUrl = form.getAttribute('action') || '';
            // La URL de preview es diferente a la de envío
            // Extraer la base (orden/<id>/) y agregar preview-pdf-diagnostico/
            const baseUrl = previewUrl.replace('enviar-diagnostico-cliente/', 'preview-pdf-diagnostico/');
            
            const params = new URLSearchParams();
            params.set('folio', folio || 'PREVIEW');
            params.set('componentes', JSON.stringify(componentes));
            
            const fullUrl = `${baseUrl}?${params.toString()}`;
            
            // Mostrar loading
            btnRefrescarPreview.disabled = true;
            btnRefrescarPreview.innerHTML = '<i class="bi bi-hourglass-split"></i> Generando...';
            
            iframePreview.src = fullUrl;
            
            // Restaurar botón cuando carga
            iframePreview.onload = () => {
                btnRefrescarPreview.disabled = false;
                btnRefrescarPreview.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Actualizar Vista Previa';
            };
            
            // Timeout de seguridad
            setTimeout(() => {
                if (btnRefrescarPreview.disabled) {
                    btnRefrescarPreview.disabled = false;
                    btnRefrescarPreview.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Actualizar Vista Previa';
                }
            }, 15000);
        });
    }

    // ====================================================================
    // 7. Envío del formulario via AJAX
    // ====================================================================
    if (btnEnviar && form) {
        btnEnviar.addEventListener('click', async () => {
            // Validaciones client-side
            const folio = inputFolio ? inputFolio.value.trim() : '';
            if (!folio) {
                alert('⚠️ El folio es obligatorio. Por favor, ingresa un folio para el diagnóstico.');
                if (inputFolio) inputFolio.focus();
                return;
            }
            
            // Verificar que al menos un componente está seleccionado
            const componentesSeleccionados = document.querySelectorAll<HTMLInputElement>(
                '.checkbox-componente:checked'
            );
            if (componentesSeleccionados.length === 0) {
                const continuar = confirm(
                    '⚠️ No has seleccionado ningún componente.\n\n' +
                    '¿Deseas continuar sin marcar componentes?\n' +
                    '(El PDF se generará sin observaciones de componentes)'
                );
                if (!continuar) return;
            }
            
            // Confirmación final
            const confirmMsg = `¿Enviar diagnóstico al cliente?\n\n` +
                `📋 Folio: ${folio}\n` +
                `🔧 Componentes: ${componentesSeleccionados.length} seleccionados\n` +
                `📸 Imágenes: ${document.querySelectorAll('.checkbox-imagen-diag:checked').length} seleccionadas\n\n` +
                `El estado de la orden cambiará a "Diagnóstico enviado al cliente".`;
            
            if (!confirm(confirmMsg)) return;
            
            // Preparar datos del formulario
            const formData = new FormData(form);
            
            // Agregar JSON de componentes
            const componentesJSON = JSON.stringify(construirComponentesJSON());
            formData.set('componentes', componentesJSON);
            
            // Mostrar estado de loading
            btnEnviar.disabled = true;
            const textoOriginal = btnEnviar.innerHTML;
            btnEnviar.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Enviando diagnóstico...';
            
            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                
                const data: DiagnosticoResponse = await response.json();
                
                if (data.success) {
                    // Éxito - mostrar mensaje y cerrar modal
                    alert(data.message || '✅ Diagnóstico enviado exitosamente.');
                    
                    // Cerrar modal
                    const modalElement = document.getElementById('modalEnviarDiagnostico');
                    if (modalElement) {
                        // eslint-disable-next-line @typescript-eslint/no-explicit-any
                        const bsLib = (window as unknown as Record<string, unknown>)['bootstrap'] as {
                            Modal: { getInstance(el: HTMLElement): { hide(): void } | null };
                        } | undefined;
                        if (bsLib) {
                            const modal = bsLib.Modal.getInstance(modalElement);
                            if (modal) modal.hide();
                        }
                    }
                    
                    // Recargar página para ver estado actualizado
                    window.location.reload();
                } else {
                    // Error del servidor
                    alert(data.error || '❌ Error al enviar el diagnóstico.');
                }
            } catch (error) {
                console.error('Error en envío de diagnóstico:', error);
                alert('❌ Error de conexión. Verifica tu conexión a internet e intenta nuevamente.');
            } finally {
                // Restaurar botón
                btnEnviar.disabled = false;
                btnEnviar.innerHTML = textoOriginal;
            }
        });
    }
}

// ========================================================================
// INICIALIZACIÓN
// ========================================================================
document.addEventListener('DOMContentLoaded', initDiagnosticoModal);
