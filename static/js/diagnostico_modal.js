"use strict";
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
const ALIAS_COMPONENTES = {
    // ── Componentes principales ──
    'Motherboard': [
        'MOBO', 'MOTHERBOARD', 'TARJETA MADRE', 'BOARD', 'PLACA', 'PLACA MADRE',
        'MAINBOARD', 'MAIN BOARD', 'TARJETA PRINCIPAL', 'LOGIC BOARD',
    ],
    'Pantalla': [
        'PANTALLA', 'LCD', 'DISPLAY', 'SCREEN', 'PANEL', 'PANEL LCD',
        'LED', 'PANEL LED', 'TOUCH SCREEN', 'DIGITALIZADOR',
    ],
    'Disco Duro / SSD': [
        'DISCO', 'DISCO DURO', 'SSD', 'HDD', 'HARD DRIVE',
        'SATA', 'UNIDAD DE ESTADO SOLIDO', 'SOLID STATE',
    ],
    'SSD M.2': [
        'SSD M.2', 'SSD M2', 'M.2 SSD', 'M2 SSD', 'NVME', 'NVME SSD',
        'M.2', 'UNIDAD M.2', 'UNIDAD M2',
    ],
    'Teclado': [
        'TECLADO', 'KEYBOARD',
    ],
    'Teclado USB': [
        'TECLADO USB', 'USB KEYBOARD', 'KEYBOARD USB', 'TECLADO EXTERNO',
    ],
    'Keyboard with Palmrest Assy': [
        'KEYBOARD PALMREST', 'KEYBOARD WITH PALMREST', 'TECLADO CON PALMREST',
        'KEYBOARD PALMREST ASSY', 'TECLADO PALMREST', 'PALMREST ASSY',
    ],
    'Cargador': [
        'CARGADOR', 'ELIMINADOR', 'ADAPTADOR', 'AC ADAPTER', 'POWER ADAPTER',
        'CABLE DE AC', 'ADAPTADOR DE CORRIENTE', 'CHARGER',
    ],
    'Fuente de Poder': [
        'FUENTE DE PODER', 'FUENTE', 'POWER SUPPLY', 'PSU',
        'FUENTE DE ALIMENTACION', 'FUENTE DE ALIMENTACIÓN',
    ],
    'Batería': [
        'BATERIA', 'BATERÍA', 'BATTERY', 'ACUMULADOR', 'CELL',
    ],
    'Pila CMOS': [
        'PILA CMOS', 'CMOS', 'BIOS BATTERY', 'COIN CELL', 'PILA BIOS',
        'PILA', 'CMOS BATTERY',
    ],
    'DC-IN cable': [
        'DC-IN', 'DCIN', 'DC IN', 'DC-IN CABLE', 'JACK DC', 'JACK DE CARGA',
        'POWER JACK', 'CONECTOR DE CARGA', 'PUERTO DE CARGA',
        'CHARGING PORT',
    ],
    'Button Power': [
        'BOTON', 'BOTÓN', 'BUTTON', 'POWER BUTTON', 'BUTTON POWER',
        'BOTON DE ENCENDIDO', 'BOTÓN DE ENCENDIDO', 'SWITCH',
    ],
    'WiFi / Bluetooth': [
        'WIFI', 'WI-FI', 'BLUETOOTH', 'WIRELESS',
        'TARJETA WIFI', 'TARJETA INALAMBRICA', 'TARJETA INALÁMBRICA',
        'WLAN', 'BT', 'MODULO WIFI', 'MÓDULO WIFI', 'WIRELESS CARD',
    ],
    'Wireless Antennas': [
        'ANTENA', 'ANTENAS', 'WIRELESS ANTENNAS', 'ANTENAS WIRELESS',
        'ANTENAS WIFI', 'WIFI ANTENNAS', 'ANTENNA',
    ],
    'Touchpad': [
        'TOUCHPAD', 'TOUCH PAD', 'TRACKPAD', 'TRACK PAD', 'MOUSE PAD',
        'PAD TACTIL', 'PAD TÁCTIL', 'PANEL TACTIL', 'PANEL TÁCTIL',
    ],
    'Mouse': [
        'MOUSE', 'RATON', 'RATÓN', 'RATON USB', 'RATÓN USB', 'USB MOUSE',
    ],
    'Sistema Operativo': [
        'S.O.', 'SISTEMA OPERATIVO', 'WINDOWS', 'INSTALACION DE S.O',
        'INSTALACION S.O', 'INSTALACION SO', 'REINSTALACION', 'REINSTALACIÓN',
        'FORMATEO', 'FORMATO', 'INSTALACION DE SISTEMA', 'INSTALACIÓN DE SISTEMA', 'OS',
    ],
    'Bisagras': [
        'BISAGRA', 'BISAGRAS', 'HINGE', 'HINGES', 'CHARNELA', 'CHARNELAS',
    ],
    'Cubre Bisagras': [
        'CUBRE BISAGRAS', 'COVER HINGE', 'HINGE COVER', 'TAPA BISAGRAS',
        'HINGE CAP', 'HINGE CAPS',
    ],
    'RAM': [
        'RAM', 'MEMORIA', 'MEMORIA RAM', 'DIMM', 'SODIMM', 'SO-DIMM',
        'MODULO DE MEMORIA', 'MÓDULO DE MEMORIA',
    ],
    'Ventilador / Cooling': [
        'VENTILADOR', 'FAN', 'COOLER', 'COOLING', 'SISTEMA DE ENFRIAMIENTO',
    ],
    'Disipador de calor': [
        'DISIPADOR', 'DISIPADOR DE CALOR', 'HEATSINK', 'HEAT SINK',
        'THERMAL', 'THERMAL MODULE', 'PASTA TERMICA', 'PASTA TÉRMICA',
    ],
    'Refrigeración liquida': [
        'REFRIGERACION LIQUIDA', 'REFRIGERACIÓN LIQUIDA', 'LIQUID COOLING',
        'WATER COOLING', 'AIO COOLER', 'ENFRIAMIENTO LIQUIDO',
    ],
    'Carcasa / Chasis': [
        'CARCASA', 'CHASIS', 'PLASTICO', 'PLÁSTICO', 'PLASTICOS', 'PLÁSTICOS',
        'HOUSING', 'CUBIERTA',
    ],
    'Bottom Cover/Case': [
        'BOTTOM', 'BOTTOM COVER', 'BOTTOM CASE', 'BOTTOM BASE',
        'TAPA INFERIOR', 'BASE INFERIOR', 'LOWER CASE',
    ],
    'Top Cover': [
        'TOP COVER', 'LID', 'TAPA SUPERIOR', 'LCD COVER', 'BACK LID',
        'LCD BACK COVER', 'UPPER COVER',
    ],
    'Bisel LCD': [
        'BISEL', 'BISEL LCD', 'LCD BEZEL', 'BEZEL LCD', 'BEZEL',
        'MARCO LCD', 'MARCO', 'FRAME', 'LCD FRAME',
    ],
    'Base de computadora': [
        'BASE', 'BASE DE COMPUTADORA', 'DESKTOP BASE', 'COMPUTER BASE',
        'BASE PC', 'STAND', 'SOPORTE',
    ],
    'Palmrest': [
        'PALMREST', 'PALM REST', 'REPOSA MANOS', 'REPOSAMANOS',
        'REPOSAMANOS ASSY', 'UPPER CASE',
    ],
    // ── Cables ──
    'Cable Flex': [
        'CABLE FLEX', 'FLEX CABLE', 'CABLE FLEXIBLE', 'FLAT CABLE', 'RIBBON',
    ],
    'Cable de video/LVDS': [
        'CABLE DE VIDEO', 'CABLE LVDS', 'LVDS', 'VIDEO CABLE',
        'CABLE DE PANTALLA', 'CABLE LCD', 'EDP CABLE', 'LVDS CABLE',
    ],
    'Cable de Batería': [
        'CABLE DE BATERIA', 'CABLE DE BATERÍA', 'CABLE BATERIA',
        'CABLE BATERÍA', 'BATTERY CABLE',
    ],
    'Cable de I/O Board': [
        'CABLE DE IO', 'CABLE IO BOARD', 'CABLE DE I/O BOARD',
        'CABLE I/O', 'I/O CABLE', 'IO CABLE',
    ],
    'Cable lector de huellas': [
        'CABLE LECTOR DE HUELLAS', 'FINGERPRINT CABLE', 'CABLE FINGERPRINT',
        'CABLE DE HUELLAS',
    ],
    // ── Procesamiento ──
    'Procesador (CPU)': [
        'PROCESADOR', 'CPU', 'PROCESSOR', 'CHIP', 'MICROPROCESADOR',
    ],
    'Tarjeta Gráfica (GPU)': [
        'GPU', 'TARJETA GRAFICA', 'TARJETA GRÁFICA', 'TARJETA DE VIDEO',
        'VIDEO CARD', 'GRAPHICS CARD', 'GRAPHICS',
    ],
    // ── Puertos ──
    'Puerto USB': [
        'PUERTO USB', 'USB PORT', 'CONECTOR USB', 'USB',
    ],
    'Puerto HDMI': [
        'PUERTO HDMI', 'HDMI', 'HDMI PORT', 'CONECTOR HDMI',
    ],
    'Puerto de Red (Ethernet)': [
        'PUERTO DE RED', 'ETHERNET', 'LAN', 'RJ45', 'PUERTO LAN',
        'ETHERNET PORT', 'CONECTOR RJ45', 'NETWORK PORT',
    ],
    // ── Periféricos y multimedia ──
    'Webcam': [
        'CAMARA', 'CÁMARA', 'WEBCAM', 'CAMERA', 'WEB CAM', 'CAM',
        'MODULO DE CAMARA', 'MÓDULO DE CÁMARA',
    ],
    'Micrófono': [
        'MICROFONO', 'MICRÓFONO', 'MIC', 'MICROPHONE', 'MICROFONO INTERNO',
        'MICRÓFONO INTERNO',
    ],
    'Bocinas / Audio': [
        'BOCINA', 'BOCINAS', 'SPEAKER', 'SPEAKERS', 'ALTAVOZ',
        'ALTAVOCES', 'PARLANTE', 'PARLANTES', 'AUDIO',
        'BOCINAS / AUDIO',
    ],
    'Lector de Tarjetas': [
        'LECTOR DE TARJETAS', 'CARD READER', 'LECTOR SD', 'SD READER',
        'LECTOR DE SD', 'MEMORY CARD READER',
    ],
    'Lector de huellas': [
        'LECTOR DE HUELLAS', 'FINGERPRINT', 'HUELLA DIGITAL', 'FINGERPRINT READER',
        'LECTOR HUELLA', 'FINGERPRINT SENSOR',
    ],
    // ── Boards y soportes ──
    'I/O Board': [
        'IO BOARD', 'I/O BOARD', 'TARJETA IO', 'BOARD IO',
        'I/O DAUGHTER BOARD', 'DAUGHTER BOARD', 'TARJETA I/O',
    ],
    'Case HDD': [
        'CASE HDD', 'HDD CASE', 'SOPORTE HDD', 'HDD CADDY', 'CADDY',
    ],
    'HDD/SSD Bracket': [
        'BRACKET HDD', 'HDD BRACKET', 'SSD BRACKET', 'SOPORTE DISCO',
        'HDD/SSD BRACKET', 'BRACKET SSD', 'BRACKET',
    ],
    // ── Accesorios ──
    'Memoria USB': [
        'MEMORIA USB', 'USB DRIVE', 'PENDRIVE', 'FLASH DRIVE', 'USB FLASH',
    ],
    'Tornillos': [
        'TORNILLOS', 'TORNILLO', 'SCREWS', 'SCREW KIT', 'SCREW',
    ],
    // ── Servicios ──
    'Limpieza y mantenimiento': [
        'LIMPIEZA', 'MANTENIMIENTO', 'LIMPIEZA Y MANTENIMIENTO',
        'SERVICIO DE LIMPIEZA', 'CLEANING', 'MAINTENANCE',
    ],
    'Instalación de piezas': [
        'INSTALACION DE PIEZAS', 'INSTALACIÓN DE PIEZAS',
        'INSTALACION', 'INSTALACIÓN', 'LABOR', 'MANO DE OBRA',
    ],
    'Reparación a nivel componente': [
        'REPARACION A NIVEL COMPONENTE', 'REPARACIÓN A NIVEL COMPONENTE',
        'REPARACION COMPONENTE', 'REPARACIÓN COMPONENTE',
        'COMPONENT REPAIR', 'MICRO SOLDADURA', 'MICROSOLDADURA',
    ],
    'Respaldo de información': [
        'RESPALDO', 'RESPALDO DE INFORMACION', 'RESPALDO DE INFORMACIÓN',
        'BACKUP', 'DATA BACKUP', 'RESPALDO DE DATOS',
    ],
    // ── Paquetes ──
    'Paquete Oro': [
        'PAQUETE ORO', 'PAQUETE DE ORO', 'PAQ ORO', 'PAQ. ORO',
    ],
    'Paquete Plata': [
        'PAQUETE PLATA', 'PAQUETE DE PLATA', 'PAQ PLATA', 'PAQ. PLATA',
    ],
    'Paquete Premium': [
        'PAQUETE PREMIUM', 'PAQ PREMIUM', 'PAQ. PREMIUM',
    ],
    'Paquete de mejora': [
        'PAQUETE DE MEJORA', 'PAQUETE MEJORA', 'PAQ MEJORA', 'PAQ. MEJORA',
        'PAQUETE DE MEJORAS',
    ],
};
// ========================================================================
// COMPONENTES SIN NÚMERO DE PARTE (Servicios y Paquetes)
// ========================================================================
/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Algunos componentes son servicios o paquetes que NO tienen número de parte.
 * Por ejemplo, "MANTENIMIENTO" o "PAQUETE PLATA" se mencionan en el diagnóstico
 * como sugerencias pero no llevan un código alfanumérico.
 *
 * Esta lista indica cuáles componentes del mapa de aliases deben buscarse
 * también como "menciones sueltas" en el texto completo del diagnóstico,
 * sin necesidad de que tengan un número de parte asociado.
 */
const COMPONENTES_SIN_DPN = [
    'Limpieza y mantenimiento',
    'Instalación de piezas',
    'Reparación a nivel componente',
    'Respaldo de información',
    'Paquete Oro',
    'Paquete Plata',
    'Paquete Premium',
    'Paquete de mejora',
];
// ========================================================================
// FRASES INDICADORAS CATEGORIZADAS - Señales de secciones de piezas
// ========================================================================
/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Los técnicos escriben frases que indican el inicio de una sección de piezas.
 * Ahora diferenciamos entre 3 tipos de frases:
 *
 * 1. FRASES_NECESARIAS: Indican piezas necesarias/prioritarias para el funcionamiento.
 *    Ejemplo: "PIEZAS NECESARIAS Y/O PRIORITARIAS.- BATERIA: CP6DF"
 *
 * 2. FRASES_OPCIONALES: Indican piezas opcionales o de mejora.
 *    Ejemplo: "PIEZAS OPCIONALES Y/O SECUNDARIAS.- RAM DDR4: HMA82GS6"
 *
 * 3. FRASES_GENERICAS: Frases sin categoría explícita (default: necesarias).
 *    Ejemplo: "SE ANEXAN NÚMEROS DE PARTE PRIORITARIOS.- ..."
 *
 * Esto permite que el sistema marque automáticamente cada pieza como
 * "Necesaria" u "Opcional" según la sección donde aparece.
 */
/** Frases que indican piezas NECESARIAS / PRIORITARIAS (es_necesaria = true) */
const FRASES_NECESARIAS = [
    'PIEZAS NECESARIAS Y/O PRIORITARIAS',
    'PIEZAS NECESARIAS Y PRIORITARIAS',
    'PIEZAS NECESARIAS',
    'NUMEROS DE PARTE PRIORITARIOS',
    'NÚMEROS DE PARTE PRIORITARIOS',
    'PIEZAS PRIORITARIAS',
    'COTIZAR PIEZAS PRIORITARIAS',
    'PARTES NECESARIAS',
    'PARTES PRIORITARIAS',
    'COMPONENTES NECESARIOS',
    'COMPONENTES PRIORITARIOS',
];
/** Frases que indican piezas OPCIONALES / SECUNDARIAS (es_necesaria = false) */
const FRASES_OPCIONALES = [
    'PIEZAS OPCIONALES Y/O SECUNDARIAS',
    'PIEZAS OPCIONALES Y SECUNDARIAS',
    'PIEZAS OPCIONALES',
    'PIEZAS SECUNDARIAS',
    'PIEZAS RECOMENDADAS',
    'PIEZAS DE MEJORA',
    'MEJORAS OPCIONALES',
    'MEJORAS RECOMENDADAS',
    'PARTES OPCIONALES',
    'PARTES SECUNDARIAS',
    'PARTES RECOMENDADAS',
    'COMPONENTES OPCIONALES',
    'COMPONENTES SECUNDARIOS',
    'COMPONENTES RECOMENDADOS',
];
/** Frases genéricas sin categoría explícita (default: es_necesaria = true) */
const FRASES_GENERICAS = [
    'SE ANEXAN NÚMEROS DE PARTE',
    'SE ANEXAN NUMEROS DE PARTE',
    'SE ANEXA NÚMERO DE PARTE',
    'SE ANEXA NUMERO DE PARTE',
    'NUMERO DE PARTE DE PIEZAS',
    'NÚMERO DE PARTE DE PIEZAS',
    'COTIZAR PIEZAS',
    'PIEZAS A COTIZAR',
    'PARTES A COTIZAR',
    'SE ANEXAN DPN',
    'SE ANEXA DPN',
    'DPN DE PIEZAS',
    'NUMEROS DE PARTE A COTIZAR',
    'NÚMEROS DE PARTE A COTIZAR',
    'ANEXO NUMEROS DE PARTE',
    'ANEXO NÚMEROS DE PARTE',
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // "COTIZAR." suelto (sin "PIEZAS") es muy común al final de los diagnósticos
    // para indicar que lo que sigue son las piezas a cotizar.
    'COTIZAR',
];
// ========================================================================
// FUNCIONES DE DETECCIÓN DE PIEZAS
// ========================================================================
/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Esta función analiza el texto completo del diagnóstico y lo divide en
 * secciones categorizadas. Cada sección contiene las piezas que van después
 * de una frase indicadora, y se clasifica como "necesaria" u "opcional".
 *
 * Ejemplo de diagnóstico con 2 secciones:
 *   "...texto libre del diagnóstico...
 *    PIEZAS NECESARIAS Y/O PRIORITARIAS.- BATERIA: CP6DF, MOBO: 0XPJWG
 *    PIEZAS OPCIONALES Y/O SECUNDARIAS.- RAM: HMA82GS6"
 *
 * Resultado: [
 *   { texto: "BATERIA: CP6DF, MOBO: 0XPJWG", es_necesaria: true },
 *   { texto: "RAM: HMA82GS6", es_necesaria: false }
 * ]
 *
 * Si no encuentra ninguna frase categórica, busca frases genéricas
 * y devuelve todo como "necesaria" (comportamiento backward-compatible).
 * Si no encuentra NADA, devuelve el texto completo como una sola sección.
 */
function extraerSeccionesCategoricas(texto) {
    const textoUpper = texto.toUpperCase();
    const frasesEncontradas = [];
    // Buscar TODAS las frases de las 3 categorías en el texto
    // Priorizar las más largas cuando hay solapamiento en la misma posición
    // Helper: buscar frases de un array y agregarlas con su categoría
    function buscarFrases(frases, esNecesaria) {
        for (const frase of frases) {
            let posicion = 0;
            // Buscar todas las ocurrencias de la frase en el texto
            while (posicion < textoUpper.length) {
                const pos = textoUpper.indexOf(frase, posicion);
                if (pos === -1)
                    break;
                // Verificar si ya existe una frase que cubre esta posición
                // y es más larga (más específica)
                const existeMasEspecifica = frasesEncontradas.some(f => f.posicion <= pos &&
                    (f.posicion + f.longitud) >= (pos + frase.length));
                if (!existeMasEspecifica) {
                    // Remover frases menos específicas que esta nueva cubre
                    const indicesARemover = [];
                    frasesEncontradas.forEach((f, idx) => {
                        if (pos <= f.posicion &&
                            (pos + frase.length) >= (f.posicion + f.longitud)) {
                            indicesARemover.push(idx);
                        }
                    });
                    // Remover de atrás hacia adelante para no afectar índices
                    for (let i = indicesARemover.length - 1; i >= 0; i--) {
                        frasesEncontradas.splice(indicesARemover[i], 1);
                    }
                    frasesEncontradas.push({
                        posicion: pos,
                        longitud: frase.length,
                        es_necesaria: esNecesaria,
                        frase: frase
                    });
                }
                posicion = pos + 1; // Avanzar para buscar más ocurrencias
            }
        }
    }
    // Buscar en orden de prioridad: necesarias, opcionales, genéricas
    buscarFrases(FRASES_NECESARIAS, true);
    buscarFrases(FRASES_OPCIONALES, false);
    buscarFrases(FRASES_GENERICAS, true); // Genéricas = necesarias por default
    // Si no se encontró ninguna frase, devolver todo el texto como una sección necesaria
    if (frasesEncontradas.length === 0) {
        return [{ texto: texto, es_necesaria: true }];
    }
    // Ordenar por posición en el texto (de izquierda a derecha)
    frasesEncontradas.sort((a, b) => a.posicion - b.posicion);
    // Construir secciones: cada sección va desde el fin de una frase
    // hasta el inicio de la siguiente frase (o el final del texto)
    const secciones = [];
    for (let i = 0; i < frasesEncontradas.length; i++) {
        const fraseActual = frasesEncontradas[i];
        const inicioTexto = fraseActual.posicion + fraseActual.longitud;
        // El fin de la sección es el inicio de la siguiente frase, o el final del texto
        const finTexto = (i + 1 < frasesEncontradas.length)
            ? frasesEncontradas[i + 1].posicion
            : texto.length;
        // Extraer el texto de la sección
        let textoSeccion = texto.substring(inicioTexto, finTexto);
        // Limpiar separadores iniciales como ".-", ":", "-", "."
        textoSeccion = textoSeccion.replace(/^[\s.\-:]+/, '').trim();
        // Solo agregar secciones con contenido
        if (textoSeccion.length > 0) {
            secciones.push({
                texto: textoSeccion,
                es_necesaria: fraseActual.es_necesaria
            });
        }
    }
    // Si después de procesar no quedó ninguna sección con contenido,
    // devolver todo el texto como fallback
    if (secciones.length === 0) {
        return [{ texto: texto, es_necesaria: true }];
    }
    return secciones;
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
function dividirEnFragmentos(texto) {
    // Dividir por comas, puntos y coma, o punto seguido de espacio
    // También dividir por " Y " cuando es conjunción entre piezas
    // pero NO cuando forma parte del nombre (ej: "LIMPIEZA Y MANTENIMIENTO")
    const fragmentos = texto
        .split(/[,;]|\.\s|\.-/)
        .flatMap((frag) => {
        // Sub-dividir por " Y " solo si ambos lados parecen tener un código
        // Es decir, si " Y " separa dos piezas independientes
        const partes = frag.split(/\s+Y\s+/i);
        if (partes.length > 1) {
            // Verificar si al menos 2 partes tienen algo que parece un código
            const partesConCodigo = partes.filter((p) => /[A-Z0-9]{3,}/.test(p.trim().toUpperCase()));
            if (partesConCodigo.length >= 2) {
                return partes;
            }
        }
        return [frag];
    })
        .map((f) => f.trim())
        .filter((f) => f.length > 0);
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
function extraerParteDeFragmento(fragmento, es_necesaria = true) {
    const textoLimpio = fragmento.trim();
    // Ignorar fragmentos muy cortos o que no tienen sentido
    if (textoLimpio.length < 3)
        return null;
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
    // FORMATO 3: Código en cualquier posición del fragmento
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // A veces los técnicos escriben texto DESPUÉS del número de parte, como:
    //   "PALMREST ASSEMBLY 2DPKM EN ESPAÑOL CON LUZ"
    // donde "2DPKM" está en medio, no al final. Este formato busca cualquier
    // token alfanumérico (4-15 chars con letras Y números mezclados) en cualquier
    // posición del fragmento. Usa la misma lista de exclusiones para evitar
    // falsos positivos como "DDR4", "i7", etc.
    if (!numeroParte) {
        // Buscar TODOS los tokens alfanuméricos en el texto
        const tokenRegex = /\b([A-Za-z0-9]{4,15})\b/g;
        let tokenMatch;
        // Lista extendida de exclusiones para el formato 3 (más agresivo)
        // ya que busca en cualquier posición, necesitamos ser más estrictos
        const palabrasExcluidasF3 = [
            'DELL', 'CORE', 'INTEL', 'NVIDIA', 'QUADRO', 'LENOVO',
            'ASUS', 'ACER', 'EPSA', 'BIOS', 'HDMI', 'USB3', 'USB2',
            'CHICO', 'GRANDE', 'CABLE', 'PILA', 'PLUG', 'WIFI',
            'PARA', 'ESTA', 'ESTE', 'COMO', 'TIENE', 'TIPO', 'SOLO',
            'NUEVO', 'NUEVA', 'ROTO', 'ROTA', 'TODO', 'TODA', 'AREA',
            'PART', 'WITH', 'FROM', 'THAT', 'THIS', 'EACH', 'WILL',
            'DISPLAY', 'ASSEMBLY', 'COVER', 'TOUCH', 'PANEL',
            'EQUIPO', 'FALLA', 'VIDEO', 'DAÑO', 'REEMPLAZO',
            'SUGERIDO', 'SUGERIDA', 'PRIORITARIO', 'NECESARIO',
            'SUSTITUIR', 'COTIZAR', 'VERIFICA', 'PRESENTA',
            'ARRIBA', 'ABAJO', 'AFECTA', 'REQUIERE', 'INGRESA',
            'ENCIENDE', 'FUNCIONA', 'EJECUTAN', 'ARROJANDO',
            'PRUEBAS', 'VALIDAR', 'DEBIDO', 'ENCUENTRA', 'DENTRO',
            'SISTEMA', 'MARCA', 'TEST', 'REVISION', 'CORRE',
            'ESPAÑOL', 'ADICIONAL', 'GARANTIA',
        ];
        while ((tokenMatch = tokenRegex.exec(textoLimpio)) !== null) {
            const posibleCodigo = tokenMatch[1];
            const tieneDigitos = /\d/.test(posibleCodigo);
            const tieneLetras = /[A-Za-z]/.test(posibleCodigo);
            if (tieneDigitos && tieneLetras &&
                !palabrasExcluidasF3.includes(posibleCodigo.toUpperCase())) {
                // Encontramos un código válido — la descripción es todo lo que
                // está ANTES de este token en el fragmento
                const posInicio = tokenMatch.index;
                descripcion = textoLimpio.substring(0, posInicio).trim();
                numeroParte = posibleCodigo.toUpperCase();
                break; // Tomar el primero válido
            }
        }
    }
    // Si no se encontró un número de parte válido, saltar este fragmento
    if (!numeroParte || !descripcion)
        return null;
    // Limpiar descripción de caracteres sobrantes
    descripcion = descripcion.replace(/[\-\.]+$/, '').trim();
    // Intentar emparejar con un componente de la base de datos
    const matchComponente = buscarComponenteDb(descripcion);
    return {
        textoOriginal: textoLimpio,
        descripcionPieza: descripcion,
        numeroParte: numeroParte,
        componenteDb: matchComponente.nombre,
        confianza: matchComponente.confianza,
        es_necesaria: es_necesaria
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
function buscarComponenteDb(descripcion) {
    const descUpper = descripcion.toUpperCase();
    // Primero buscar coincidencia directa/exacta con el nombre del componente
    for (const [componenteDb, aliases] of Object.entries(ALIAS_COMPONENTES)) {
        // Coincidencia directa con el nombre en la BD
        if (descUpper === componenteDb.toUpperCase()) {
            return { nombre: componenteDb, confianza: 'alta' };
        }
    }
    // Buscar por aliases — priorizar los aliases más largos (más específicos)
    let mejorMatch = null;
    for (const [componenteDb, aliases] of Object.entries(ALIAS_COMPONENTES)) {
        for (const alias of aliases) {
            // Verificar si el alias aparece en la descripción
            if (descUpper.includes(alias)) {
                const confianza = alias.length >= 4 ? 'alta' : 'media';
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
 * detectadas con sus números de parte y su categoría (necesaria/opcional).
 *
 * Proceso:
 * 1. Divide el texto en secciones categorizadas (necesarias vs opcionales)
 * 2. Para cada sección, divide en fragmentos individuales (uno por pieza)
 * 3. De cada fragmento extrae la descripción y el número de parte
 * 4. Empareja cada pieza con un componente del sistema
 * 5. Propaga la categoría (es_necesaria) de la sección a cada pieza
 * 6. Busca menciones de servicios/paquetes sin número de parte
 */
function extraerPiezasDiagnostico(textoDiagnostico) {
    if (!textoDiagnostico || textoDiagnostico.trim().length === 0) {
        return [];
    }
    // Paso 1: Dividir en secciones categorizadas (necesarias, opcionales, genéricas)
    const secciones = extraerSeccionesCategoricas(textoDiagnostico);
    // Paso 2: Procesar cada sección por separado, propagando es_necesaria
    const piezas = [];
    for (const seccion of secciones) {
        // Dividir la sección en fragmentos individuales
        const fragmentos = dividirEnFragmentos(seccion.texto);
        for (const fragmento of fragmentos) {
            // Extraer pieza pasando la categoría de la sección
            const pieza = extraerParteDeFragmento(fragmento, seccion.es_necesaria);
            if (pieza) {
                // EXPLICACIÓN PARA PRINCIPIANTES:
                // Evitar duplicados: si ya tenemos una pieza con el mismo número de parte,
                // no la agregamos otra vez. Pero solo comparamos si el DPN no está vacío,
                // porque las piezas sin DPN (servicios) se manejan aparte en el Paso 3.
                const yaExiste = pieza.numeroParte
                    ? piezas.some(p => p.numeroParte === pieza.numeroParte)
                    : false;
                if (!yaExiste) {
                    piezas.push(pieza);
                }
            }
        }
    }
    // Paso 3: Buscar servicios/paquetes mencionados sin número de parte
    const serviciosSinDPN = detectarServiciosSinDPN(textoDiagnostico, piezas);
    piezas.push(...serviciosSinDPN);
    return piezas;
}
/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Esta función busca en el texto completo del diagnóstico menciones de
 * servicios o paquetes que NO requieren número de parte.
 *
 * Por ejemplo, si el técnico escribió "SE RECOMIENDA REALIZAR MANTENIMIENTO"
 * o "COTIZAR PAQUETE PLATA", esta función detecta esas menciones y las
 * agrega como piezas detectadas con numeroParte vacío.
 *
 * Solo busca componentes listados en COMPONENTES_SIN_DPN (servicios y paquetes).
 * Evita duplicados si el componente ya fue detectado por la lógica de piezas
 * con número de parte.
 */
function detectarServiciosSinDPN(textoDiagnostico, piezasYaDetectadas) {
    const textoUpper = textoDiagnostico.toUpperCase();
    const serviciosDetectados = [];
    // Set de componentes ya detectados para evitar duplicados
    const componentesYaDetectados = new Set(piezasYaDetectadas
        .filter(p => p.componenteDb !== null)
        .map(p => p.componenteDb));
    for (const componenteDb of COMPONENTES_SIN_DPN) {
        // Si ya fue detectado con número de parte, no duplicar
        if (componentesYaDetectados.has(componenteDb))
            continue;
        // Obtener aliases de este componente
        const aliases = ALIAS_COMPONENTES[componenteDb];
        if (!aliases)
            continue;
        // Buscar si algún alias aparece en el texto completo
        // Priorizar el alias más largo (más específico)
        let mejorAlias = null;
        let mejorPosicion = -1;
        for (const alias of aliases) {
            const pos = textoUpper.indexOf(alias);
            if (pos !== -1) {
                if (!mejorAlias || alias.length > mejorAlias.length) {
                    mejorAlias = alias;
                    mejorPosicion = pos;
                }
            }
        }
        if (mejorAlias && mejorPosicion !== -1) {
            // Extraer un fragmento de contexto alrededor de la mención
            // para mostrarlo al usuario en la UI
            const inicioContexto = Math.max(0, mejorPosicion - 30);
            const finContexto = Math.min(textoDiagnostico.length, mejorPosicion + mejorAlias.length + 30);
            let contexto = textoDiagnostico.substring(inicioContexto, finContexto).trim();
            if (inicioContexto > 0)
                contexto = '...' + contexto;
            if (finContexto < textoDiagnostico.length)
                contexto = contexto + '...';
            serviciosDetectados.push({
                textoOriginal: contexto,
                descripcionPieza: componenteDb,
                numeroParte: '', // Sin número de parte
                componenteDb: componenteDb,
                confianza: 'alta',
                es_necesaria: true, // Servicios/paquetes siempre como necesarios
            });
        }
    }
    return serviciosDetectados;
}
// ========================================================================
// FUNCIONES PRINCIPALES
// ========================================================================
/**
 * Inicializa toda la lógica del modal de diagnóstico.
 * Se ejecuta cuando el DOM está completamente cargado.
 */
function initDiagnosticoModal() {
    // Elementos del DOM
    const inputFolio = document.getElementById('inputFolioDiagnostico');
    const spanFolioPreview = document.getElementById('spanFolioPreview');
    const btnEnviar = document.getElementById('btnEnviarDiagnostico');
    const form = document.getElementById('formEnviarDiagnostico');
    const inputComponentesJSON = document.getElementById('inputComponentesJSON');
    const btnRefrescarPreview = document.getElementById('btnRefrescarPreviewDiag');
    const iframePreview = document.getElementById('iframePreviewDiagnostico');
    // Checkboxes
    const checkboxSelectAllImgs = document.getElementById('seleccionarTodasImagenesDiag');
    // Botón y dropdown para agregar componentes adicionales
    const btnAgregarComponente = document.getElementById('btnAgregarComponente');
    const dropdownComponentesAdicionales = document.getElementById('dropdownComponentesAdicionales');
    const componentesAdicionalesTbody = document.getElementById('componentesAdicionales');
    // Contadores
    const contadorComponentes = document.getElementById('contadorComponentesSeleccionados');
    const contadorImagenes = document.getElementById('contadorImagenesDiagSeleccionadas');
    // Contador para IDs únicos de componentes dinámicos
    let contadorComponentesDinamicos = 0;
    const componentesAgregados = new Set(); // Para evitar duplicados
    // Si no hay modal en la página, no ejecutar nada
    if (!form)
        return;
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
    // 2. Toggle DPN: habilitar/deshabilitar campo al marcar checkbox
    // ====================================================================
    /**
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Crea un badge (etiqueta) clickeable que permite al usuario indicar
     * si una pieza es "Necesaria" (verde) o "Opcional" (amarillo).
     * Al hacer clic, el badge alterna entre ambos estados.
     *
     * @param componenteDb - Nombre del componente en la BD
     * @param esDinamico - Si es un componente dinámico (agregado manualmente)
     * @param esNecesariaInicial - Estado inicial (true = necesaria, false = opcional)
     */
    function crearBadgeTipo(componenteDb, esDinamico, esNecesariaInicial = true) {
        const badge = document.createElement('span');
        const claseDpn = esDinamico ? 'badge-tipo-dinamico' : 'badge-tipo-pieza';
        badge.className = `badge ${claseDpn} cursor-pointer`;
        badge.setAttribute('data-componente-db', componenteDb);
        badge.setAttribute('data-es-necesaria', esNecesariaInicial ? 'true' : 'false');
        badge.title = 'Clic para alternar entre Necesaria y Opcional';
        // Aplicar estado visual inicial
        actualizarBadgeTipo(badge, esNecesariaInicial);
        // Event listener: click para alternar
        badge.addEventListener('click', () => {
            const esNecesariaActual = badge.getAttribute('data-es-necesaria') === 'true';
            const nuevoEstado = !esNecesariaActual;
            badge.setAttribute('data-es-necesaria', nuevoEstado ? 'true' : 'false');
            actualizarBadgeTipo(badge, nuevoEstado);
        });
        return badge;
    }
    /**
     * Actualiza el aspecto visual de un badge de tipo según su estado.
     */
    function actualizarBadgeTipo(badge, esNecesaria) {
        if (esNecesaria) {
            badge.className = badge.className
                .replace(/bg-warning/g, '')
                .replace(/text-dark/g, '')
                .replace(/bg-success/g, '');
            badge.classList.add('bg-success');
            badge.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i>Necesaria';
        }
        else {
            badge.className = badge.className
                .replace(/bg-success/g, '')
                .replace(/bg-warning/g, '')
                .replace(/text-dark/g, '');
            badge.classList.add('bg-warning', 'text-dark');
            badge.innerHTML = '<i class="bi bi-dash-circle me-1"></i>Opcional';
        }
    }
    /**
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Esta función controla que el campo de texto DPN (número de parte)
     * solo se pueda llenar cuando el checkbox del componente está marcado.
     * Si desmarcas el componente, el campo se deshabilita y se limpia.
     * También controla la visibilidad del badge de tipo (Necesaria/Opcional):
     * - Al marcar: muestra el badge en la celda "Tipo"
     * - Al desmarcar: oculta el badge y resetea a "Necesaria" por default
     */
    function toggleDpnInput(checkbox, esDinamico = false) {
        var _a;
        const componenteDb = checkbox.getAttribute('data-componente-db') || '';
        const selectorDpn = esDinamico
            ? `.input-dpn-dinamico[data-componente-db="${componenteDb}"]`
            : `.input-dpn[data-componente-db="${componenteDb}"]`;
        const inputDpn = document.querySelector(selectorDpn);
        if (!inputDpn)
            return;
        // Buscar la celda de tipo para este componente
        const selectorBadge = esDinamico ? 'badge-tipo-dinamico' : 'badge-tipo-pieza';
        const celdaTipo = esDinamico
            ? (_a = checkbox.closest('tr')) === null || _a === void 0 ? void 0 : _a.querySelector('.celda-tipo-dinamico')
            : document.querySelector(`.celda-tipo-pieza[data-componente-db="${componenteDb}"]`);
        if (checkbox.checked) {
            inputDpn.disabled = false;
            inputDpn.placeholder = 'Ej: DPN: 0XPJWG';
            // Estilo visual: fila activa
            const fila = checkbox.closest('tr');
            if (fila) {
                fila.classList.remove('diagnostico-row-disabled');
                fila.classList.add('diagnostico-row-active');
            }
            // Mostrar badge de tipo si no existe aún en la celda
            if (celdaTipo) {
                const badgeExistente = celdaTipo.querySelector(`.${selectorBadge}`);
                if (!badgeExistente) {
                    const badge = crearBadgeTipo(componenteDb, esDinamico);
                    celdaTipo.appendChild(badge);
                }
                else {
                    // Si ya existe, hacerlo visible
                    badgeExistente.style.display = '';
                }
            }
        }
        else {
            inputDpn.disabled = true;
            inputDpn.value = '';
            inputDpn.placeholder = 'Selecciona el componente primero';
            // Estilo visual: fila inactiva
            const fila = checkbox.closest('tr');
            if (fila) {
                fila.classList.remove('diagnostico-row-active');
                fila.classList.add('diagnostico-row-disabled');
            }
            // Ocultar y resetear el badge de tipo
            if (celdaTipo) {
                const badgeExistente = celdaTipo.querySelector(`.${selectorBadge}`);
                if (badgeExistente) {
                    badgeExistente.style.display = 'none';
                    // Resetear a "necesaria" por default
                    badgeExistente.setAttribute('data-es-necesaria', 'true');
                    actualizarBadgeTipo(badgeExistente, true);
                }
            }
        }
    }
    /**
     * Aplica el estado inicial de todos los DPN (deshabilitados porque
     * ningún checkbox está marcado al abrir el modal).
     */
    function inicializarEstadoDpn() {
        document.querySelectorAll('.checkbox-componente').forEach(cb => {
            toggleDpnInput(cb, false);
        });
    }
    // ====================================================================
    // 2b. Contador de componentes seleccionados
    // ====================================================================
    function actualizarContadorComponentes() {
        // Contar componentes predefinidos
        const checkboxesPredefinidos = document.querySelectorAll('.checkbox-componente');
        let seleccionados = 0;
        checkboxesPredefinidos.forEach(cb => {
            if (cb.checked)
                seleccionados++;
        });
        // Contar componentes adicionales dinámicos
        const checkboxesDinamicos = document.querySelectorAll('.checkbox-componente-dinamico');
        checkboxesDinamicos.forEach(cb => {
            if (cb.checked)
                seleccionados++;
        });
        if (contadorComponentes) {
            contadorComponentes.textContent = `${seleccionados} seleccionado${seleccionados !== 1 ? 's' : ''}`;
        }
    }
    // Event listeners para checkboxes de componentes predefinidos
    document.querySelectorAll('.checkbox-componente').forEach(cb => {
        cb.addEventListener('change', () => {
            toggleDpnInput(cb, false);
            actualizarContadorComponentes();
        });
    });
    // Aplicar estado inicial de los DPN (deshabilitados)
    inicializarEstadoDpn();
    // ====================================================================
    // 3. Contador de imágenes seleccionadas
    // ====================================================================
    function actualizarContadorImagenes() {
        const checkboxes = document.querySelectorAll('.checkbox-imagen-diag');
        let seleccionadas = 0;
        checkboxes.forEach(cb => {
            if (cb.checked)
                seleccionadas++;
        });
        if (contadorImagenes) {
            contadorImagenes.textContent = `${seleccionadas} seleccionada${seleccionadas !== 1 ? 's' : ''}`;
        }
    }
    // Event listeners para checkboxes de imágenes
    document.querySelectorAll('.checkbox-imagen-diag').forEach(cb => {
        cb.addEventListener('change', actualizarContadorImagenes);
    });
    // Seleccionar/deseleccionar todas las imágenes
    if (checkboxSelectAllImgs) {
        checkboxSelectAllImgs.addEventListener('change', () => {
            const checked = checkboxSelectAllImgs.checked;
            document.querySelectorAll('.checkbox-imagen-diag').forEach(cb => {
                cb.checked = checked;
            });
            actualizarContadorImagenes();
        });
    }
    // ====================================================================
    // 4. Componentes adicionales dinámicos
    // ====================================================================
    /**
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Carga el dropdown con componentes adicionales disponibles.
     * Incluye un campo de búsqueda en la parte superior para filtrar
     * la lista en tiempo real mientras el técnico escribe.
     *
     * Estructura resultante del dropdown:
     * ┌──────────────────────────────────────┐
     * │  [Buscar componente...              ] │  ← input de búsqueda
     * ├──────────────────────────────────────┤
     * │  Batería                             │
     * │  Bisagras                            │  ← se filtran en vivo
     * │  ...                                 │
     * │  (Sin resultados)                    │  ← si nada coincide
     * └──────────────────────────────────────┘
     */
    function cargarDropdownComponentes() {
        if (!btnAgregarComponente || !dropdownComponentesAdicionales)
            return;
        try {
            const componentesJSON = btnAgregarComponente.getAttribute('data-componentes');
            if (!componentesJSON) {
                dropdownComponentesAdicionales.innerHTML = '<li><span class="dropdown-item text-muted small">No hay componentes adicionales disponibles</span></li>';
                return;
            }
            const componentes = JSON.parse(componentesJSON);
            if (componentes.length === 0) {
                dropdownComponentesAdicionales.innerHTML = '<li><span class="dropdown-item text-muted small">No hay componentes adicionales disponibles</span></li>';
                return;
            }
            // Limpiar dropdown
            dropdownComponentesAdicionales.innerHTML = '';
            // ── Campo de búsqueda al inicio del dropdown ──
            const liBuscador = document.createElement('li');
            liBuscador.className = 'px-2 py-1';
            // Evitar que Bootstrap cierre el dropdown al interactuar con el input
            liBuscador.addEventListener('click', (e) => e.stopPropagation());
            const inputBuscar = document.createElement('input');
            inputBuscar.type = 'text';
            inputBuscar.className = 'form-control form-control-sm';
            inputBuscar.placeholder = 'Buscar componente...';
            inputBuscar.setAttribute('autocomplete', 'off');
            // Evitar que teclas cierren el dropdown
            inputBuscar.addEventListener('keydown', (e) => {
                e.stopPropagation();
            });
            liBuscador.appendChild(inputBuscar);
            dropdownComponentesAdicionales.appendChild(liBuscador);
            // Separador visual entre buscador y lista
            const liDivider = document.createElement('li');
            liDivider.innerHTML = '<hr class="dropdown-divider my-1">';
            dropdownComponentesAdicionales.appendChild(liDivider);
            // ── Elemento "Sin resultados" (oculto por defecto) ──
            const liSinResultados = document.createElement('li');
            liSinResultados.style.display = 'none';
            liSinResultados.innerHTML = '<span class="dropdown-item text-muted small fst-italic">Sin resultados</span>';
            dropdownComponentesAdicionales.appendChild(liSinResultados);
            // ── Agregar cada componente como opción filtrable ──
            const itemsComponentes = [];
            componentes.forEach(nombreComponente => {
                const li = document.createElement('li');
                li.setAttribute('data-nombre-normalizado', normalizarTexto(nombreComponente));
                const a = document.createElement('a');
                a.className = 'dropdown-item cursor-pointer';
                a.style.color = '#000'; // Forzar color negro para visibilidad
                a.textContent = nombreComponente;
                a.addEventListener('click', () => agregarComponenteDinamico(nombreComponente));
                li.appendChild(a);
                dropdownComponentesAdicionales.appendChild(li);
                itemsComponentes.push(li);
            });
            // ── Lógica de filtrado en tiempo real ──
            inputBuscar.addEventListener('input', () => {
                const filtro = normalizarTexto(inputBuscar.value);
                let hayResultados = false;
                itemsComponentes.forEach(li => {
                    const nombreNorm = li.getAttribute('data-nombre-normalizado') || '';
                    const coincide = filtro === '' || nombreNorm.includes(filtro);
                    li.style.display = coincide ? '' : 'none';
                    if (coincide)
                        hayResultados = true;
                });
                // Mostrar/ocultar "Sin resultados"
                liSinResultados.style.display = hayResultados ? 'none' : '';
            });
            // ── Auto-focus y limpiar filtro al abrir el dropdown ──
            // EXPLICACIÓN PARA PRINCIPIANTES:
            // Bootstrap emite el evento "shown.bs.dropdown" cuando el menú
            // se termina de mostrar. Aprovechamos para enfocar el input
            // y limpiar cualquier filtro anterior.
            const dropdownParent = btnAgregarComponente.closest('.dropdown') || btnAgregarComponente.parentElement;
            if (dropdownParent) {
                dropdownParent.addEventListener('shown.bs.dropdown', () => {
                    inputBuscar.value = '';
                    inputBuscar.dispatchEvent(new Event('input')); // Limpiar filtro
                    inputBuscar.focus();
                });
            }
        }
        catch (error) {
            console.error('Error al cargar componentes disponibles:', error);
            dropdownComponentesAdicionales.innerHTML = '<li><span class="dropdown-item text-danger small">Error cargando componentes</span></li>';
        }
    }
    /**
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Normaliza un texto para búsquedas: lo convierte a minúsculas y quita
     * acentos/tildes para que "Batería" coincida con "bateria".
     * Ejemplo: "Café" → "cafe", "Pantalla" → "pantalla"
     */
    function normalizarTexto(texto) {
        return texto.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    }
    /**
     * Agrega una fila dinámica para un componente adicional.
     * Incluye la celda "Tipo" con badge Necesaria/Opcional.
     */
    function agregarComponenteDinamico(nombreComponente) {
        if (!componentesAdicionalesTbody)
            return;
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
        checkbox.addEventListener('change', () => {
            toggleDpnInput(checkbox, true);
            actualizarContadorComponentes();
        });
        tdCheck.appendChild(checkbox);
        // Celda nombre
        const tdNombre = document.createElement('td');
        tdNombre.className = 'align-middle fw-semibold';
        const label = document.createElement('label');
        label.htmlFor = idUnico;
        label.className = 'mb-0 cursor-pointer d-block';
        label.innerHTML = `${nombreComponente} <span class="badge bg-success ms-2">ADICIONAL</span>`;
        tdNombre.appendChild(label);
        // Celda Tipo (badge Necesaria/Opcional) — visible porque viene pre-seleccionado
        const tdTipo = document.createElement('td');
        tdTipo.className = 'text-center align-middle celda-tipo-dinamico';
        const badgeTipo = crearBadgeTipo(nombreComponente, true);
        tdTipo.appendChild(badgeTipo);
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
        // Ensamblar fila (4 celdas: check, nombre, tipo, dpn)
        tr.appendChild(tdCheck);
        tr.appendChild(tdNombre);
        tr.appendChild(tdTipo);
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
    function eliminarComponenteDinamico(fila, nombreComponente) {
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
    const btnEditarEmail = document.getElementById('btnEditarEmailCliente');
    const vistaLectura = document.getElementById('emailClienteVistaLectura');
    const vistaEdicion = document.getElementById('emailClienteVistaEdicion');
    const inputEditarEmail = document.getElementById('inputEditarEmailCliente');
    const btnGuardarEmail = document.getElementById('btnGuardarEmailCliente');
    const btnCancelarEmail = document.getElementById('btnCancelarEmailCliente');
    const spanEmailCliente = document.getElementById('spanEmailCliente');
    const feedbackEmail = document.getElementById('feedbackEmailCliente');
    const cardDestinatario = document.getElementById('cardDestinatarioEmail');
    const badgeEmailValido = document.getElementById('badgeEmailValido');
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
    function toggleModoEdicion(mostrarEdicion) {
        if (vistaLectura)
            vistaLectura.style.display = mostrarEdicion ? 'none' : 'flex';
        if (vistaEdicion)
            vistaEdicion.style.display = mostrarEdicion ? 'block' : 'none';
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
    function actualizarUIEmailExitoso(nuevoEmail) {
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
        const tituloCard = cardDestinatario === null || cardDestinatario === void 0 ? void 0 : cardDestinatario.querySelector('.fw-bold');
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
    async function guardarEmailCliente() {
        var _a;
        console.log('[Diagnostico Modal] guardarEmailCliente() llamada');
        console.log('[Diagnostico Modal] detalleEquipoId:', detalleEquipoId);
        console.log('[Diagnostico Modal] inputEditarEmail:', inputEditarEmail === null || inputEditarEmail === void 0 ? void 0 : inputEditarEmail.value);
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
        if (btnCancelarEmail)
            btnCancelarEmail.disabled = true;
        inputEditarEmail.readOnly = true;
        try {
            // Obtener token CSRF
            const csrfToken = ((_a = document.querySelector('[name=csrfmiddlewaretoken]')) === null || _a === void 0 ? void 0 : _a.value) || '';
            const response = await fetch(`/servicio-tecnico/api/detalle-equipo/${detalleEquipoId}/actualizar-email/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({ email: nuevoEmail }),
            });
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
            }
            else {
                // Error del servidor
                console.error('[Diagnostico Modal] Error del servidor:', data.error);
                if (feedbackEmail) {
                    feedbackEmail.textContent = data.error || 'Error al guardar el email.';
                    feedbackEmail.className = 'text-danger mt-1 d-block small';
                }
                inputEditarEmail.classList.add('is-invalid');
            }
        }
        catch (error) {
            console.error('Error al actualizar email del cliente:', error);
            if (feedbackEmail) {
                feedbackEmail.textContent = 'Error de conexión. Inténtalo de nuevo.';
                feedbackEmail.className = 'text-danger mt-1 d-block small';
            }
        }
        finally {
            // Restaurar botones
            if (btnGuardarEmail) {
                btnGuardarEmail.disabled = false;
                btnGuardarEmail.innerHTML = '<i class="bi bi-check-lg"></i>';
            }
            if (btnCancelarEmail)
                btnCancelarEmail.disabled = false;
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
        btnGuardarEmail.addEventListener('click', (e) => {
            e.preventDefault(); // Evitar que el form padre haga submit
            e.stopPropagation();
            console.log('[Diagnostico Modal] Botón guardar email clickeado');
            guardarEmailCliente();
        });
    }
    if (btnCancelarEmail) {
        btnCancelarEmail.addEventListener('click', () => {
            var _a;
            // Restaurar valor original
            if (inputEditarEmail && spanEmailCliente) {
                const emailActual = ((_a = spanEmailCliente.textContent) === null || _a === void 0 ? void 0 : _a.trim()) || '';
                // Solo restaurar si es un email válido (no "No configurado")
                if (emailActual && emailActual !== 'No configurado') {
                    inputEditarEmail.value = emailActual;
                }
                else {
                    inputEditarEmail.value = '';
                }
            }
            if (inputEditarEmail)
                inputEditarEmail.classList.remove('is-invalid');
            toggleModoEdicion(false);
        });
    }
    // Permitir guardar con Enter y cancelar con Escape
    if (inputEditarEmail) {
        inputEditarEmail.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                event.stopPropagation(); // Evitar que el form padre haga submit
                console.log('[Diagnostico Modal] Enter presionado en input email');
                guardarEmailCliente();
            }
            else if (event.key === 'Escape') {
                event.preventDefault();
                btnCancelarEmail === null || btnCancelarEmail === void 0 ? void 0 : btnCancelarEmail.click();
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
    const btnDetectarPiezas = document.getElementById('btnDetectarPiezas');
    const panelPiezasDetectadas = document.getElementById('panelPiezasDetectadas');
    const contenedorPiezas = document.getElementById('contenedorPiezasDetectadas');
    const btnCerrarPanel = document.getElementById('btnCerrarPanelPiezas');
    const btnAplicarTodas = document.getElementById('btnAplicarTodasPiezas');
    // Almacenar las piezas detectadas para referencia
    let piezasDetectadasActuales = [];
    /**
     * Aplica una pieza detectada: marca el checkbox del componente
     * correspondiente y llena su campo DPN con el número de parte.
     * Si el componente no existe en los 18 predefinidos, lo agrega
     * como componente dinámico.
     */
    function aplicarPieza(pieza, filaUI) {
        if (!pieza.componenteDb)
            return;
        const componenteDb = pieza.componenteDb;
        // Buscar si existe como componente predefinido
        const checkboxPredefinido = document.querySelector(`.checkbox-componente[data-componente-db="${componenteDb}"]`);
        if (checkboxPredefinido) {
            // Es un componente predefinido — marcar checkbox y llenar DPN
            const inputDpn = document.querySelector(`.input-dpn[data-componente-db="${componenteDb}"]`);
            // EXPLICACIÓN PARA PRINCIPIANTES:
            // Si la pieza tiene numeroParte vacío (ej: servicios como "Mantenimiento"),
            // NO preguntamos si quiere sobreescribir — solo marcamos el checkbox.
            // Solo mostramos el diálogo de confirmación si la pieza trae un DPN real
            // y el input ya tiene un DPN diferente.
            if (pieza.numeroParte && inputDpn && inputDpn.value.trim() && inputDpn.value.trim() !== pieza.numeroParte) {
                const sobreescribir = confirm(`El componente "${componenteDb}" ya tiene el DPN "${inputDpn.value.trim()}".\n\n` +
                    `¿Deseas reemplazarlo con "${pieza.numeroParte}"?`);
                if (!sobreescribir)
                    return;
            }
            checkboxPredefinido.checked = true;
            if (inputDpn) {
                inputDpn.disabled = false;
                // Solo llenar el input DPN si la pieza trae un número de parte real
                if (pieza.numeroParte) {
                    inputDpn.value = pieza.numeroParte;
                    // Efecto visual de "llenado automático"
                    inputDpn.style.transition = 'background-color 0.5s ease';
                    inputDpn.style.backgroundColor = '#d4edda';
                    setTimeout(() => {
                        inputDpn.style.backgroundColor = '';
                    }, 2000);
                }
            }
            // Actualizar estilo de fila activa y mostrar badge
            toggleDpnInput(checkboxPredefinido, false);
            // Setear es_necesaria en el badge según la pieza detectada
            const celdaTipoPre = document.querySelector(`.celda-tipo-pieza[data-componente-db="${componenteDb}"]`);
            if (celdaTipoPre) {
                const badgePre = celdaTipoPre.querySelector('.badge-tipo-pieza');
                if (badgePre) {
                    badgePre.setAttribute('data-es-necesaria', pieza.es_necesaria ? 'true' : 'false');
                    actualizarBadgeTipo(badgePre, pieza.es_necesaria);
                }
            }
        }
        else {
            // No es predefinido — buscar si ya existe como dinámico
            const checkboxDinamico = document.querySelector(`.checkbox-componente-dinamico[data-componente-db="${componenteDb}"]`);
            if (checkboxDinamico) {
                // Ya existe como dinámico — marcar checkbox y llenar DPN si tiene
                checkboxDinamico.checked = true;
                const inputDpnDinamico = document.querySelector(`.input-dpn-dinamico[data-componente-db="${componenteDb}"]`);
                if (inputDpnDinamico) {
                    inputDpnDinamico.disabled = false;
                    // Solo llenar el input DPN si la pieza trae un número de parte real
                    if (pieza.numeroParte) {
                        inputDpnDinamico.value = pieza.numeroParte;
                        inputDpnDinamico.style.transition = 'background-color 0.5s ease';
                        inputDpnDinamico.style.backgroundColor = '#d4edda';
                        setTimeout(() => {
                            inputDpnDinamico.style.backgroundColor = '';
                        }, 2000);
                    }
                }
                toggleDpnInput(checkboxDinamico, true);
                // Setear es_necesaria en el badge del componente dinámico
                const filaDin = checkboxDinamico.closest('tr');
                if (filaDin) {
                    const celdaTipoDin = filaDin.querySelector('.celda-tipo-dinamico');
                    if (celdaTipoDin) {
                        const badgeDin = celdaTipoDin.querySelector('.badge-tipo-dinamico');
                        if (badgeDin) {
                            badgeDin.setAttribute('data-es-necesaria', pieza.es_necesaria ? 'true' : 'false');
                            actualizarBadgeTipo(badgeDin, pieza.es_necesaria);
                        }
                    }
                }
            }
            else {
                // No existe — agregarlo como componente dinámico
                agregarComponenteDinamico(componenteDb);
                // Esperar un tick para que el DOM se actualice y luego llenar DPN
                setTimeout(() => {
                    const nuevoInputDpn = document.querySelector(`.input-dpn-dinamico[data-componente-db="${componenteDb}"]`);
                    if (nuevoInputDpn) {
                        // Solo llenar el input DPN si la pieza trae un número de parte real
                        if (pieza.numeroParte) {
                            nuevoInputDpn.value = pieza.numeroParte;
                            nuevoInputDpn.style.transition = 'background-color 0.5s ease';
                            nuevoInputDpn.style.backgroundColor = '#d4edda';
                            setTimeout(() => {
                                nuevoInputDpn.style.backgroundColor = '';
                            }, 2000);
                        }
                    }
                    // Setear es_necesaria en el badge del nuevo componente dinámico
                    const nuevoCheckbox = document.querySelector(`.checkbox-componente-dinamico[data-componente-db="${componenteDb}"]`);
                    if (nuevoCheckbox) {
                        const filaNueva = nuevoCheckbox.closest('tr');
                        if (filaNueva) {
                            const celdaTipoNueva = filaNueva.querySelector('.celda-tipo-dinamico');
                            if (celdaTipoNueva) {
                                const badgeNuevo = celdaTipoNueva.querySelector('.badge-tipo-dinamico');
                                if (badgeNuevo) {
                                    badgeNuevo.setAttribute('data-es-necesaria', pieza.es_necesaria ? 'true' : 'false');
                                    actualizarBadgeTipo(badgeNuevo, pieza.es_necesaria);
                                }
                            }
                        }
                    }
                }, 50);
            }
        }
        // Actualizar contador
        actualizarContadorComponentes();
        // Marcar la fila de la UI como aplicada
        filaUI.classList.remove('list-group-item-light', 'list-group-item-warning');
        filaUI.classList.add('list-group-item-success');
        const btnAplicar = filaUI.querySelector('.btn-aplicar-pieza');
        if (btnAplicar) {
            btnAplicar.disabled = true;
            btnAplicar.innerHTML = '<i class="bi bi-check-lg"></i> Aplicado';
            btnAplicar.classList.remove('btn-outline-success', 'btn-outline-primary');
            btnAplicar.classList.add('btn-success');
        }
        // Deshabilitar el dropdown de asignación manual si existe
        const selectManual = filaUI.querySelector('.select-asignar-componente');
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
    function renderizarPiezasDetectadas(piezas) {
        if (!contenedorPiezas || !panelPiezasDetectadas)
            return;
        // Limpiar contenido anterior
        contenedorPiezas.innerHTML = '';
        if (piezas.length === 0) {
            contenedorPiezas.innerHTML = `
                <div class="alert alert-info mb-0">
                    <i class="bi bi-info-circle"></i>
                    <strong>No se detectaron piezas ni servicios</strong> en el texto del diagnóstico.
                    <br><small class="text-muted">Asegúrate de que el diagnóstico contenga frases como 
                    "SE ANEXAN NÚMEROS DE PARTE" seguidas de las piezas con sus códigos, 
                    o menciones de servicios como "MANTENIMIENTO" o "PAQUETE PLATA".</small>
                </div>
            `;
            panelPiezasDetectadas.style.display = 'block';
            if (btnAplicarTodas)
                btnAplicarTodas.style.display = 'none';
            return;
        }
        // Detectar componentes duplicados:
        // Contar cuántas piezas apuntan al mismo componenteDb
        // La primera de cada componente obtiene "Aplicar" directo,
        // las siguientes obtienen dropdown con sugerencia.
        const componenteUsado = new Set();
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
            }
            else if (pieza.componenteDb && pieza.confianza === 'alta') {
                badge.className = 'badge bg-success';
                badge.innerHTML = '<i class="bi bi-check-circle-fill"></i>';
                badge.title = 'Coincidencia alta';
            }
            else if (pieza.componenteDb && pieza.confianza === 'media') {
                badge.className = 'badge bg-info';
                badge.innerHTML = '<i class="bi bi-question-circle-fill"></i>';
                badge.title = 'Coincidencia media';
            }
            else {
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
            // EXPLICACIÓN PARA PRINCIPIANTES:
            // Si la pieza tiene número de parte, lo mostramos en un <code> destacado.
            // Si NO tiene (servicios como "Mantenimiento" o paquetes como "Paquete Plata"),
            // mostramos un badge de "Servicio" en lugar del número de parte.
            if (pieza.numeroParte) {
                // Número de parte (destacado)
                const codeSpan = document.createElement('code');
                codeSpan.className = 'fs-6 fw-bold text-primary';
                codeSpan.textContent = pieza.numeroParte;
                infoDiv.appendChild(codeSpan);
            }
            else {
                // Sin DPN — mostrar badge de servicio/paquete
                const servicioBadge = document.createElement('span');
                servicioBadge.className = 'badge bg-info bg-opacity-75 text-dark';
                servicioBadge.innerHTML = '<i class="bi bi-wrench me-1"></i>Servicio';
                servicioBadge.title = 'Este componente no requiere número de parte';
                infoDiv.appendChild(servicioBadge);
            }
            // Badge de tipo: Necesaria (verde) u Opcional (amarillo)
            const badgeTipoDetectada = document.createElement('span');
            if (pieza.es_necesaria) {
                badgeTipoDetectada.className = 'badge bg-success bg-opacity-75';
                badgeTipoDetectada.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i>Necesaria';
                badgeTipoDetectada.title = 'Pieza necesaria / prioritaria';
            }
            else {
                badgeTipoDetectada.className = 'badge bg-warning text-dark';
                badgeTipoDetectada.innerHTML = '<i class="bi bi-dash-circle me-1"></i>Opcional';
                badgeTipoDetectada.title = 'Pieza opcional / secundaria';
            }
            infoDiv.appendChild(badgeTipoDetectada);
            // Si hay match, mostrar a cuál componente apunta
            if (pieza.componenteDb) {
                const matchSpan = document.createElement('span');
                if (esComponenteDuplicado) {
                    matchSpan.className = 'badge bg-warning bg-opacity-25 text-dark border border-warning';
                    matchSpan.innerHTML = `<i class="bi bi-diagram-2"></i> ${pieza.componenteDb} <small>(duplicado)</small>`;
                }
                else {
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
                btnAplicar.title = pieza.numeroParte
                    ? `Aplicar ${pieza.numeroParte} a ${pieza.componenteDb}`
                    : `Aplicar ${pieza.componenteDb}`;
                btnAplicar.addEventListener('click', () => aplicarPieza(pieza, fila));
                accionesDiv.appendChild(btnAplicar);
            }
            else {
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
                        const piezaAsignada = {
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
    function crearDropdownComponentes(componenteSugerido) {
        const selectComponente = document.createElement('select');
        selectComponente.className = 'form-select form-select-sm select-asignar-componente';
        selectComponente.style.maxWidth = '180px';
        selectComponente.innerHTML = '<option value="">Asignar a...</option>';
        // Agregar los 18 componentes predefinidos como opciones
        const checkboxesExistentes = document.querySelectorAll('.checkbox-componente');
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
                    const componentesAdicionales = JSON.parse(componentesJSON);
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
            }
            catch (_e) { /* Ignorar errores de JSON */ }
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
                        if (filaUI.getAttribute('data-duplicado') === 'true')
                            return;
                        // Verificar que no fue ya aplicada
                        const btnAplicar = filaUI.querySelector('.btn-aplicar-pieza');
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
    function construirComponentesJSON() {
        const componentes = [];
        // 1. Componentes predefinidos (de la tabla estática)
        const checkboxesPredefinidos = document.querySelectorAll('.checkbox-componente');
        checkboxesPredefinidos.forEach(cb => {
            const componenteDb = cb.getAttribute('data-componente-db') || '';
            const inputDpn = document.querySelector(`.input-dpn[data-componente-db="${componenteDb}"]`);
            // Leer es_necesaria desde el badge de tipo (default: true)
            const celdaTipo = document.querySelector(`.celda-tipo-pieza[data-componente-db="${componenteDb}"]`);
            const badgeTipo = celdaTipo === null || celdaTipo === void 0 ? void 0 : celdaTipo.querySelector('.badge-tipo-pieza');
            const esNecesaria = badgeTipo
                ? badgeTipo.getAttribute('data-es-necesaria') !== 'false'
                : true;
            componentes.push({
                componente_db: componenteDb,
                dpn: inputDpn ? inputDpn.value.trim() : '',
                seleccionado: cb.checked,
                es_necesaria: esNecesaria
            });
        });
        // 2. Componentes adicionales dinámicos (agregados por el usuario)
        const checkboxesDinamicos = document.querySelectorAll('.checkbox-componente-dinamico');
        checkboxesDinamicos.forEach(cb => {
            const componenteDb = cb.getAttribute('data-componente-db') || '';
            const inputDpn = document.querySelector(`.input-dpn-dinamico[data-componente-db="${componenteDb}"]`);
            // Leer es_necesaria desde el badge de tipo dinámico (default: true)
            const filaDin = cb.closest('tr');
            const celdaTipoDin = filaDin === null || filaDin === void 0 ? void 0 : filaDin.querySelector('.celda-tipo-dinamico');
            const badgeTipoDin = celdaTipoDin === null || celdaTipoDin === void 0 ? void 0 : celdaTipoDin.querySelector('.badge-tipo-dinamico');
            const esNecesariaDin = badgeTipoDin
                ? badgeTipoDin.getAttribute('data-es-necesaria') !== 'false'
                : true;
            componentes.push({
                componente_db: componenteDb,
                dpn: inputDpn ? inputDpn.value.trim() : '',
                seleccionado: cb.checked,
                es_necesaria: esNecesariaDin
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
            var _a, _b;
            // Validaciones client-side
            const folio = inputFolio ? inputFolio.value.trim() : '';
            if (!folio) {
                alert('⚠️ El folio es obligatorio. Por favor, ingresa un folio para el diagnóstico.');
                if (inputFolio)
                    inputFolio.focus();
                return;
            }
            // Verificar que al menos un componente está seleccionado
            // IMPORTANTE: incluir AMBOS selectores — predefinidos Y dinámicos (piezas adicionales)
            const componentesSeleccionados = document.querySelectorAll('.checkbox-componente:checked, .checkbox-componente-dinamico:checked');
            if (componentesSeleccionados.length === 0) {
                const continuar = confirm('⚠️ No has seleccionado ningún componente.\n\n' +
                    '¿Deseas continuar sin marcar componentes?\n' +
                    '(El PDF se generará sin observaciones de componentes)');
                if (!continuar)
                    return;
            }
            // Confirmación final
            const confirmMsg = `¿Enviar diagnóstico al cliente?\n\n` +
                `📋 Folio: ${folio}\n` +
                `🔧 Componentes: ${componentesSeleccionados.length} seleccionados\n` +
                `📸 Imágenes: ${document.querySelectorAll('.checkbox-imagen-diag:checked').length} seleccionadas\n\n` +
                `El estado de la orden cambiará a "Diagnóstico enviado al cliente".`;
            if (!confirm(confirmMsg))
                return;
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
                const data = await response.json();
                if (data.success) {
                    // Cerrar modal de envío
                    const modalElement = document.getElementById('modalEnviarDiagnostico');
                    if (modalElement) {
                        const bsLib = window['bootstrap'];
                        if (bsLib) {
                            const modal = bsLib.Modal.getInstance(modalElement);
                            if (modal)
                                modal.hide();
                        }
                    }
                    // Construir modal de confirmación estilizado
                    const destinatario = ((_a = data.data) === null || _a === void 0 ? void 0 : _a.destinatario) || '';
                    const folio = ((_b = data.data) === null || _b === void 0 ? void 0 : _b.folio) || '';
                    const modalHTML = `
                        <div class="modal fade" id="modalConfirmacionDiagnostico" tabindex="-1" aria-hidden="true">
                            <div class="modal-dialog modal-dialog-centered">
                                <div class="modal-content">
                                    <div class="modal-header bg-success text-white">
                                        <h5 class="modal-title">
                                            <i class="bi bi-send-check"></i> Diagnóstico en Proceso
                                        </h5>
                                    </div>
                                    <div class="modal-body">
                                        <div class="text-center mb-3">
                                            <i class="bi bi-gear" style="font-size: 3rem; color: #198754;"></i>
                                        </div>
                                        <p class="text-center fs-5 mb-2">
                                            El diagnóstico se está enviando <strong>en segundo plano</strong>.
                                        </p>
                                        <div class="alert alert-info mb-0">
                                            <i class="bi bi-info-circle me-1"></i>
                                            <strong>Folio:</strong> ${folio}<br>
                                            <strong>Destinatario:</strong> ${destinatario}<br><br>
                                            El PDF, imágenes y correo se están procesando.
                                            Puedes continuar trabajando normalmente.
                                        </div>
                                    </div>
                                    <div class="modal-footer">
                                        <button type="button" class="btn btn-primary" onclick="location.reload()">
                                            <i class="bi bi-check-lg"></i> Aceptar
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                    // Eliminar modal previo si existe y agregar el nuevo
                    const prevModal = document.getElementById('modalConfirmacionDiagnostico');
                    if (prevModal)
                        prevModal.remove();
                    document.body.insertAdjacentHTML('beforeend', modalHTML);
                    // Mostrar modal de confirmación
                    const bsConfirm = window['bootstrap'];
                    if (bsConfirm) {
                        const confirmModal = new bsConfirm.Modal(document.getElementById('modalConfirmacionDiagnostico'));
                        confirmModal.show();
                    }
                }
                else {
                    // Error del servidor
                    alert(data.error || '❌ Error al enviar el diagnóstico.');
                }
            }
            catch (error) {
                console.error('Error en envío de diagnóstico:', error);
                alert('❌ Error de conexión. Verifica tu conexión a internet e intenta nuevamente.');
            }
            finally {
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
//# sourceMappingURL=diagnostico_modal.js.map