/**
 * Sistema de Plantillas Automáticas para Comentarios de Rechazo
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Cuando eliges un motivo de rechazo (select), se precarga una plantilla
 * estructurada en el textarea de detalle. Sirve en:
 * - ST (detalle_orden): #id_motivo_rechazo / #id_detalle_rechazo
 * - Almacén con orden ST: mismos IDs en #registrarMotivoRechazoStModal
 * - Almacén sin orden: #id_motivo_rechazo_solicitud / #id_detalle_rechazo_solicitud
 *
 * También habilita/deshabilita el checkbox de correo de feedback (solo modal ST).
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

    'no_especifica_motivo': `[RAZÓN PRINCIPAL]: Cliente no especifica motivo, únicamente rechaza la cotización
[DETALLE]: No proporciona detalles adicionales sobre su decisión
[CONTEXTO]: Comunicación limitada o nula después de la cotización
[ALTERNATIVA]: Se registra rechazo sin motivo específico`,

    'rechazo_sin_decision': `[RAZÓN PRINCIPAL]: Cliente retira equipo sin tomar decisión
[DETALLE]: Se presenta al centro de servicio y retira sin [aceptar / rechazar] formalmente
[CONTEXTO]: Menciona que [evaluará opciones / consultará / esperará mejor momento]
[ALTERNATIVA]: [Buscará segunda opinión / Evaluará presupuesto / Comparará alternativas]`,

    'no_autorizado_por_empresa': `[RAZÓN PRINCIPAL]: Empresa no autoriza la reparación
[DETALLE]: El cliente informa que [su empresa / el área de compras] no aprueba el gasto
[CONTEXTO]: [Política interna / Presupuesto cerrado / Requiere otra cotización]
[ALTERNATIVA]: [Esperará autorización / Evaluará compra de equipo / Cancelará servicio]`,

    'otro': `[RAZÓN PRINCIPAL]: Otro motivo
[DETALLE]: [DESCRIBE_EL_MOTIVO]
[CONTEXTO]: [CONTEXTO_ADICIONAL]
[ALTERNATIVA]: [ALTERNATIVA_DEL_CLIENTE]`,
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
    'no_especifica_motivo': 'No especifica motivo',
    'rechazo_sin_decision': 'Rechazo sin decisión clara',
    'no_autorizado_por_empresa': 'No autorizado por empresa',
    'otro': 'Otro motivo',
};

/**
 * Lee del modal de Almacén la lista JSON de motivos que permiten correo.
 * Si no existe el atributo, usa el set por defecto (paridad con constants.py).
 */
function obtenerMotivosConCorreo(): Set<string> {
    const modal = document.getElementById('registrarMotivoRechazoStModal');
    const raw = modal?.getAttribute('data-motivos-feedback');
    if (raw) {
        try {
            const parsed: unknown = JSON.parse(raw);
            if (Array.isArray(parsed)) {
                return new Set(parsed.filter((x): x is string => typeof x === 'string'));
            }
        } catch {
            console.warn('⚠️ No se pudo parsear data-motivos-feedback');
        }
    }
    return new Set([
        'costo_alto',
        'muchas_piezas',
        'tiempo_largo',
        'falta_justificacion',
        'no_vale_pena',
        'rechazo_sin_decision',
        'no_especifica_motivo',
        'no_autorizado_por_empresa',
        'otro',
        'falta_de_respuesta',
    ]);
}

/**
 * Habilita o deshabilita el checkbox de feedback según el motivo.
 */
function actualizarCheckboxFeedback(motivoSeleccionado: string): void {
    const checkbox = document.getElementById('enviar_feedback_rechazo') as HTMLInputElement | null;
    const ayuda = document.getElementById('ayudaFeedbackRechazo');
    if (!checkbox) {
        return;
    }

    const modal = document.getElementById('registrarMotivoRechazoStModal');
    const yaRegistrado = modal?.getAttribute('data-motivo-ya-registrado') === '1';
    const motivosConCorreo = obtenerMotivosConCorreo();
    const permiteCorreo =
        motivoSeleccionado !== '' && motivosConCorreo.has(motivoSeleccionado);

    if (permiteCorreo) {
        checkbox.disabled = false;
        // Solo marcar por defecto en el primer registro (no al ver/editar)
        if (!yaRegistrado) {
            checkbox.checked = true;
        }
        if (ayuda && !yaRegistrado) {
            ayuda.textContent =
                'Si está marcado y el motivo lo permite, se encola el correo al cliente (mismo flujo que en ST).';
        }
    } else {
        checkbox.disabled = true;
        checkbox.checked = false;
        if (ayuda) {
            ayuda.textContent =
                motivoSeleccionado === ''
                    ? 'Selecciona un motivo para habilitar el envío de correo.'
                    : 'Este motivo no envía correo de feedback al cliente.';
        }
    }
}

/**
 * True si el texto de detalle aún parece plantilla cruda (con placeholders [CAMPO]).
 */
function detalleParecePlantillaSinEditar(valor: string): boolean {
    const trim = valor.trim();
    if (!trim.startsWith('[RAZÓN PRINCIPAL]:')) {
        return false;
    }
    return /\[[A-ZÁÉÍÓÚÑ_]+\]/.test(trim);
}

interface OpcionesPlantillasRechazo {
    /** ID del select de motivo */
    selectId: string;
    /** ID del textarea de detalle */
    textareaId: string;
    /** Si true, actualiza el checkbox de feedback (solo modal ST) */
    conFeedback: boolean;
}

/**
 * Engancha plantillas a un par select/textarea concretos.
 *
 * EXPLICACIÓN: en Almacén pueden coexistir el modal ST y el de solicitud
 * (IDs distintos). Cada par se inicializa por separado.
 */
function inicializarPlantillasParaCampos(opciones: OpcionesPlantillasRechazo): void {
    const selectMotivo = document.getElementById(
        opciones.selectId,
    ) as HTMLSelectElement | null;
    const textareaDetalle = document.getElementById(
        opciones.textareaId,
    ) as HTMLTextAreaElement | null;

    if (!selectMotivo || !textareaDetalle) {
        return;
    }

    const formContenedor = selectMotivo.closest('form');

    selectMotivo.addEventListener('change', (event: Event) => {
        const target = event.target as HTMLSelectElement;
        const motivoSeleccionado = target.value;

        if (opciones.conFeedback) {
            actualizarCheckboxFeedback(motivoSeleccionado);
        }

        if (!motivoSeleccionado || motivoSeleccionado === '') {
            // EXPLICACIÓN: no borramos prefill de piezas/servicios al limpiar el select
            textareaDetalle.placeholder =
                'Selecciona un motivo de rechazo y se cargará automáticamente una plantilla.';
            return;
        }

        const plantilla = PLANTILLAS_RECHAZO[motivoSeleccionado];

        if (plantilla) {
            const valorActual = textareaDetalle.value.trim();
            // EXPLICACIÓN: no pisamos detalle guardado, prefill de ítems ni texto editado.
            // Solo reemplazamos vacío o plantilla cruda sin editar.
            const puedeReemplazar =
                valorActual === '' || detalleParecePlantillaSinEditar(valorActual);

            if (puedeReemplazar) {
                textareaDetalle.value = plantilla;
                mostrarNotificacionPlantilla(motivoSeleccionado, textareaDetalle);
                textareaDetalle.focus();

                const primerCampo = plantilla.match(/\[([A-ZÁÉÍÓÚÑ_]+)\]/);
                if (primerCampo) {
                    const inicio = plantilla.indexOf(primerCampo[0]);
                    textareaDetalle.setSelectionRange(
                        inicio,
                        inicio + primerCampo[0].length,
                    );
                }
            }
        } else {
            console.warn(`⚠️ No hay plantilla definida para el motivo: ${motivoSeleccionado}`);
        }
    });

    agregarAyudaContextual(textareaDetalle);
    if (opciones.conFeedback) {
        actualizarCheckboxFeedback(selectMotivo.value);
    }

    if (formContenedor) {
        formContenedor.addEventListener('submit', (event: Event) => {
            if (!debeValidarPlantillaEnSubmit(formContenedor)) {
                return;
            }
            if (!validarPlantillaEditada(textareaDetalle)) {
                event.preventDefault();
            }
        });
    }
}

/**
 * Inicializa el sistema de plantillas automáticas (ST + Almacén sin orden).
 */
function inicializarPlantillasRechazo(): void {
    // Modal / form ST (detalle_orden o Almacén con orden)
    inicializarPlantillasParaCampos({
        selectId: 'id_motivo_rechazo',
        textareaId: 'id_detalle_rechazo',
        conFeedback: true,
    });

    // Modal Almacén sin orden / FL- (IDs propios para no chocar)
    inicializarPlantillasParaCampos({
        selectId: 'id_motivo_rechazo_solicitud',
        textareaId: 'id_detalle_rechazo_solicitud',
        conFeedback: false,
    });
}

/**
 * True si el submit actual es un rechazo (ST con radio, o forms de Almacén).
 */
function debeValidarPlantillaEnSubmit(form: HTMLFormElement): boolean {
    if (
        form.id === 'formRegistrarMotivoRechazoSt' ||
        form.id === 'formRegistrarMotivoRechazoSolicitud'
    ) {
        return true;
    }
    // ST: solo si eligió la acción rechazar
    const accionRadio = form.querySelector(
        'input[name="accion"]:checked'
    ) as HTMLInputElement | null;
    return Boolean(accionRadio && accionRadio.value === 'rechazar');
}

/**
 * Muestra notificación temporal indicando que se cargó la plantilla
 */
function mostrarNotificacionPlantilla(
    motivo: string,
    textareaDetalle: HTMLTextAreaElement,
): void {
    const nombreMotivo = NOMBRES_MOTIVOS[motivo] || motivo;

    const notificacion = document.createElement('div');
    notificacion.className = 'alert alert-info alert-dismissible fade show mt-2';
    notificacion.style.fontSize = '0.9rem';
    notificacion.innerHTML = `
        <i class="bi bi-info-circle"></i>
        <strong>Plantilla cargada:</strong> ${nombreMotivo}<br>
        <small>Edita los campos entre <code>[ ]</code> con los datos específicos del caso.</small>
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    if (textareaDetalle.parentElement) {
        textareaDetalle.parentElement.insertBefore(
            notificacion,
            textareaDetalle.nextSibling,
        );

        setTimeout(() => {
            notificacion.classList.remove('show');
            setTimeout(() => notificacion.remove(), 300);
        }, 5000);
    }
}

/**
 * Agrega ayuda contextual al textarea (solo una vez)
 */
function agregarAyudaContextual(textarea: HTMLTextAreaElement): void {
    if (textarea.parentElement?.querySelector('.ayuda-plantilla-rechazo')) {
        return;
    }
    const helpText = document.createElement('div');
    helpText.className = 'form-text mt-2 ayuda-plantilla-rechazo';
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
    const camposNoEditados = valor.match(/\[[A-ZÁÉÍÓÚÑ_]+\]/g);

    if (camposNoEditados && camposNoEditados.length > 0) {
        const confirmacion = confirm(
            `⚠️ Aún hay ${camposNoEditados.length} campo(s) sin completar:\n\n` +
                camposNoEditados.join(', ') +
                '\n\n' +
                '¿Deseas continuar de todos modos?'
        );
        return confirmacion;
    }

    return true;
}

/**
 * Inicializar cuando el DOM esté listo.
 * La auto-apertura del modal de Almacén vive en un script inline del template
 * (más fiable que el JS cacheado); aquí solo inicializamos plantillas.
 */
document.addEventListener('DOMContentLoaded', () => {
    inicializarPlantillasRechazo();
});
