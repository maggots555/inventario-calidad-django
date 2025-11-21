/**
 * Sistema de Plantillas Automáticas para Comentarios de Rechazo
 * 
 * Este módulo carga automáticamente plantillas estructuradas cuando
 * el usuario selecciona un motivo de rechazo en el formulario de cotización.
 * 
 * Beneficios:
 * - Estandarización de comentarios para mejor análisis de text mining
 * - Facilita el registro para técnicos (solo editan campos específicos)
 * - Mejora precisión del modelo ML de predicción de rechazos
 */

// Plantillas estructuradas por motivo de rechazo
const PLANTILLAS_RECHAZO: Record<string, string> = {
    'costo_alto': `[RAZÓN PRINCIPAL]: Presupuesto excedido
[DETALLE]: Costo de $[MONTO] supera el máximo de $[MONTO_MAXIMO] que puede invertir
[CONTEXTO]: Equipo tiene [AÑOS] años de uso, [CONDICIÓN]
[ALTERNATIVA]: [Evaluando comprar equipo nuevo / Buscando opciones más económicas / Esperando mejor momento financiero]`,

    'no_vale_pena': `[RAZÓN PRINCIPAL]: Equipo muy antiguo o depreció su valor
[DETALLE]: [AÑOS] años de uso, ya depreció su valor comercial
[CONTEXTO]: [Mantenimientos previos frecuentes / Equipo obsoleto / Bajo rendimiento actual]
[ALTERNATIVA]: Comprará equipo [nuevo / reciente / de gama superior]`,

    'muchas_piezas': `[RAZÓN PRINCIPAL]: Reparación muy extensa
[DETALLE]: Requiere [CANTIDAD] piezas diferentes: [LISTA_PIEZAS]
[CONTEXTO]: Duda sobre [efectividad post-reparación / garantía / tiempo de reparación]
[ALTERNATIVA]: Prefiere [garantía de equipo nuevo / reparación parcial / segunda opinión]`,

    'tiempo_largo': `[RAZÓN PRINCIPAL]: Tiempo de espera inaceptable
[DETALLE]: [DÍAS] días hábiles para [obtener piezas / completar reparación]
[CONTEXTO]: Necesita equipo operativo [urgentemente / para trabajo / para estudios]
[ALTERNATIVA]: [Rentará equipo temporal / Comprará usado disponible / Esperará disponibilidad]`,

    'falta_justificacion': `[RAZÓN PRINCIPAL]: Diagnóstico poco claro o falta evidencia
[DETALLE]: No comprende [por qué falló / necesidad de tantas piezas / diagnóstico técnico]
[CONTEXTO]: [Desconfianza en diagnóstico / Solicita evidencia fotográfica / Quiere segunda opinión]
[ALTERNATIVA]: [Buscará segunda opinión / Solicitará más detalles / Evaluará con técnico de confianza]`,

    'sin_presupuesto': `[RAZÓN PRINCIPAL]: Sin liquidez actual
[DETALLE]: No dispone de $[MONTO] en este momento
[CONTEXTO]: [Posible financiamiento en X meses / Esperando ingreso / Prioridades financieras]
[ALTERNATIVA]: [Solicitará reparación parcial / Esperará / Buscará financiamiento / Venderá equipo]`,

    'reparo_otro_lugar': `[RAZÓN PRINCIPAL]: Encontró opción más económica
[DETALLE]: Encontró proveedor con precio de $[MONTO] ($[DIFERENCIA] más barato)
[CONTEXTO]: Cotizó en [CANTIDAD] lugares diferentes, comparó [precio / tiempo / garantía]
[ALTERNATIVA]: Acepta [riesgo por ahorro / menor garantía / proveedor no certificado]`,

    'no_hay_partes': `[RAZÓN PRINCIPAL]: Pieza descontinuada o sin stock
[DETALLE]: [Fabricante suspendió producción / No disponible en mercado / Importación muy larga]
[CONTEXTO]: Modelo [legacy sin soporte / antiguo / fuera de catálogo]
[ALTERNATIVA]: [Comprará equipo compatible actual / Esperará disponibilidad / Buscará usado]`,

    'no_apto': `[RAZÓN PRINCIPAL]: Equipo no es apto para reparación
[DETALLE]: [Daño irreparable / Costo supera valor del equipo / Obsolescencia técnica]
[CONTEXTO]: [Equipo muy antiguo / Daño estructural / Sin repuestos disponibles]
[ALTERNATIVA]: [Reciclará equipo / Donará / Comprará nuevo]`,

    'solo_venta_mostrador': `[RAZÓN PRINCIPAL]: Solo desea servicio de venta mostrador
[DETALLE]: No acepta [cambio de piezas / reparación completa], solo [limpieza / mantenimiento básico]
[CONTEXTO]: [Presupuesto limitado / Equipo temporal / Solo necesita funcionalidad básica]
[ALTERNATIVA]: Solicitará [solo limpieza / servicio express / mantenimiento preventivo]`,

    'falta_de_respuesta': `[RAZÓN PRINCIPAL]: Cliente no responde después de múltiples intentos
[DETALLE]: [CANTIDAD] intentos de contacto vía [correo / teléfono / WhatsApp] sin respuesta
[CONTEXTO]: Última comunicación: [FECHA], equipo disponible para recolección
[ALTERNATIVA]: Se asume no acepta, equipo se pone disponible para retiro`,

    'rechazo_sin_decision': `[RAZÓN PRINCIPAL]: Cliente retira equipo sin tomar decisión
[DETALLE]: Se presenta al centro de servicio y retira sin [aceptar / rechazar] formalmente
[CONTEXTO]: Menciona que [evaluará opciones / consultará / esperará mejor momento]
[ALTERNATIVA]: [Buscará segunda opinión / Evaluará presupuesto / Comparará alternativas]`
};

// Diccionario de nombres legibles de motivos
const NOMBRES_MOTIVOS: Record<string, string> = {
    'costo_alto': 'Costo muy elevado',
    'no_vale_pena': 'No vale la pena reparar',
    'muchas_piezas': 'Demasiadas piezas a cambiar',
    'tiempo_largo': 'Tiempo de espera muy largo',
    'falta_justificacion': 'Falta de justificación técnica',
    'sin_presupuesto': 'No tiene presupuesto disponible',
    'reparo_otro_lugar': 'Reparó en otro lugar',
    'no_hay_partes': 'No hay partes disponibles',
    'no_apto': 'Equipo no apto para reparación',
    'solo_venta_mostrador': 'Solo venta mostrador',
    'falta_de_respuesta': 'Falta de respuesta del cliente',
    'rechazo_sin_decision': 'Rechazo sin decisión clara'
};

/**
 * Inicializa el sistema de plantillas automáticas
 */
function inicializarPlantillasRechazo(): void {
    const selectMotivo = document.getElementById('id_motivo_rechazo') as HTMLSelectElement | null;
    const textareaDetalle = document.getElementById('id_detalle_rechazo') as HTMLTextAreaElement | null;
    
    if (!selectMotivo || !textareaDetalle) {
        console.warn('⚠️ Elementos de formulario de rechazo no encontrados');
        return;
    }
    
    // Evento: cuando cambia el motivo de rechazo
    selectMotivo.addEventListener('change', (event: Event) => {
        const target = event.target as HTMLSelectElement;
        const motivoSeleccionado = target.value;
        
        if (!motivoSeleccionado || motivoSeleccionado === '') {
            // Si no hay motivo seleccionado, limpiar textarea
            textareaDetalle.value = '';
            textareaDetalle.placeholder = 'Selecciona un motivo de rechazo y se cargará automáticamente una plantilla.';
            return;
        }
        
        // Obtener plantilla correspondiente
        const plantilla = PLANTILLAS_RECHAZO[motivoSeleccionado];
        
        if (plantilla) {
            // Solo cargar plantilla si el campo está vacío o tiene la plantilla anterior
            const valorActual = textareaDetalle.value.trim();
            const esPlantillaAnterior = valorActual.startsWith('[RAZÓN PRINCIPAL]:');
            
            if (valorActual === '' || esPlantillaAnterior) {
                textareaDetalle.value = plantilla;
                
                // Mostrar notificación visual
                mostrarNotificacionPlantilla(motivoSeleccionado);
                
                // Auto-focus en el textarea para empezar a editar
                textareaDetalle.focus();
                
                // Seleccionar el primer campo editable [MONTO], [AÑOS], etc.
                const primerCampo = plantilla.match(/\[([A-Z_]+)\]/);
                if (primerCampo) {
                    const inicio = plantilla.indexOf(primerCampo[0]);
                    textareaDetalle.setSelectionRange(inicio, inicio + primerCampo[0].length);
                }
            }
        } else {
            console.warn(`⚠️ No hay plantilla definida para el motivo: ${motivoSeleccionado}`);
        }
    });
    
    // Agregar ayuda contextual
    agregarAyudaContextual(textareaDetalle);
}

/**
 * Muestra notificación temporal indicando que se cargó la plantilla
 */
function mostrarNotificacionPlantilla(motivo: string): void {
    const nombreMotivo = NOMBRES_MOTIVOS[motivo] || motivo;
    
    // Crear elemento de notificación
    const notificacion = document.createElement('div');
    notificacion.className = 'alert alert-info alert-dismissible fade show mt-2';
    notificacion.style.fontSize = '0.9rem';
    notificacion.innerHTML = `
        <i class="bi bi-info-circle"></i>
        <strong>Plantilla cargada:</strong> ${nombreMotivo}<br>
        <small>Edita los campos entre <code>[ ]</code> con los datos específicos del caso.</small>
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Insertar después del textarea
    const textareaDetalle = document.getElementById('id_detalle_rechazo');
    if (textareaDetalle && textareaDetalle.parentElement) {
        textareaDetalle.parentElement.insertBefore(notificacion, textareaDetalle.nextSibling);
        
        // Auto-cerrar después de 5 segundos
        setTimeout(() => {
            notificacion.classList.remove('show');
            setTimeout(() => notificacion.remove(), 300);
        }, 5000);
    }
}

/**
 * Agrega ayuda contextual al textarea
 */
function agregarAyudaContextual(textarea: HTMLTextAreaElement): void {
    const helpText = document.createElement('div');
    helpText.className = 'form-text mt-2';
    helpText.innerHTML = `
        <i class="bi bi-lightbulb"></i> <strong>Cómo usar las plantillas:</strong><br>
        1️⃣ Selecciona el motivo de rechazo arriba<br>
        2️⃣ Se cargará automáticamente una plantilla estructurada<br>
        3️⃣ Edita los campos entre <code>[ ]</code> con información específica<br>
        4️⃣ Mantén la estructura para mejor análisis de datos
    `;
    
    if (textarea.parentElement) {
        textarea.parentElement.appendChild(helpText);
    }
}

/**
 * Validar que se editaron los campos de la plantilla antes de enviar
 */
function validarPlantillaEditada(textarea: HTMLTextAreaElement): boolean {
    const valor = textarea.value;
    
    // Buscar campos sin editar (aún con [ ])
    const camposNoEditados = valor.match(/\[([A-Z_]+)\]/g);
    
    if (camposNoEditados && camposNoEditados.length > 0) {
        const confirmacion = confirm(
            `⚠️ Aún hay ${camposNoEditados.length} campo(s) sin completar:\n\n` +
            camposNoEditados.join(', ') + '\n\n' +
            '¿Deseas continuar de todos modos?'
        );
        return confirmacion;
    }
    
    return true;
}

/**
 * Inicializar cuando el DOM esté listo
 */
document.addEventListener('DOMContentLoaded', () => {
    inicializarPlantillasRechazo();
    
    // Agregar validación al formulario antes de enviar
    const form = document.querySelector('form') as HTMLFormElement | null;
    const textareaDetalle = document.getElementById('id_detalle_rechazo') as HTMLTextAreaElement | null;
    
    if (form && textareaDetalle) {
        form.addEventListener('submit', (event: Event) => {
            const accionRadio = document.querySelector('input[name="accion"]:checked') as HTMLInputElement | null;
            
            // Solo validar si se está rechazando
            if (accionRadio && accionRadio.value === 'rechazar') {
                if (!validarPlantillaEditada(textareaDetalle)) {
                    event.preventDefault();
                }
            }
        });
    }
});
