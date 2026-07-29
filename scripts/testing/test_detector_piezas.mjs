#!/usr/bin/env node
/**
 * test_detector_piezas.mjs
 * ========================
 * Regresión del detector de piezas (caso real CARGADOR + LCD).
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * El TypeScript del modal no usa módulos (se carga como <script>),
 * así que este script Node replica las reglas NUEVAS del parser
 * (último DPN, wattages excluidos, DPN solo-letras, specs por coma)
 * para validar el texto problemático sin abrir el navegador.
 *
 * Ejecutar:
 *   node scripts/testing/test_detector_piezas.mjs
 *
 * Si cambias la lógica en static/ts/diagnostico_modal.ts, actualiza
 * también este script para mantener la regresión alineada.
 */

'use strict';

// --- Aliases mínimos necesarios para el caso de prueba ---
const ALIAS_COMPONENTES = {
  Motherboard: ['MOBO', 'MOTHERBOARD', 'TARJETA MADRE', 'BOARD', 'PLACA'],
  Pantalla: ['PANTALLA', 'LCD', 'DISPLAY', 'SCREEN', 'PANEL'],
  'Disco Duro / SSD': ['DISCO', 'DISCO DURO', 'SSD', 'HDD'],
  'SSD M.2': ['SSD M.2', 'SSD M2', 'NVME', 'NVME SSD', 'M.2'],
  Cargador: ['CARGADOR', 'ELIMINADOR', 'ADAPTADOR', 'AC ADAPTER', 'CHARGER'],
  Batería: ['BATERIA', 'BATERÍA', 'BATTERY'],
  'Limpieza y mantenimiento': ['LIMPIEZA', 'MANTENIMIENTO', 'LIMPIEZA Y MANTENIMIENTO'],
};

const COMPONENTES_SIN_DPN = ['Limpieza y mantenimiento'];

const FRASES_NECESARIAS = ['COTIZAR PIEZAS PRIORITARIAS', 'PIEZAS NECESARIAS'];
const FRASES_OPCIONALES = [
  'COTIZAR PIEZAS SECUNDARIAS',
  'COTIZAR PIEZAS OPCIONALES',
  'PIEZAS SECUNDARIAS',
  'PIEZAS OPCIONALES',
];
const FRASES_GENERICAS = ['COTIZAR PIEZAS', 'COTIZAR'];

const PALABRAS_NUNCA_DPN = [
  'DELL', 'CHICO', 'GRANDE', 'CABLE', 'PLUG', 'NVME', 'SATA',
  'PANEL', 'COVER', 'TOUCH', 'BOARD', 'DISPLAY', 'ASSEMBLY',
];

function obtenerAliasesOrdenados() {
  const todos = [];
  for (const aliases of Object.values(ALIAS_COMPONENTES)) {
    for (const alias of aliases) todos.push(alias.toUpperCase());
  }
  todos.sort((a, b) => b.length - a.length);
  return todos;
}

function fragmentoEmpiezaConAlias(fragmento) {
  const upper = fragmento.trim().toUpperCase();
  if (!upper) return false;
  for (const alias of obtenerAliasesOrdenados()) {
    if (upper === alias) return true;
    if (
      upper.startsWith(alias + ' ') ||
      upper.startsWith(alias + ':') ||
      upper.startsWith(alias + ',')
    ) {
      return true;
    }
  }
  return false;
}

function esFragmentoSpecSuelta(fragmento) {
  const t = fragmento.trim();
  if (!t) return false;
  if (fragmentoEmpiezaConAlias(t)) return false;
  const upper = t.toUpperCase();
  if (/^\d+(\.\d+)?(HDF?|FHD|UHD|QHD|HD)?$/i.test(upper.replace(/\s+/g, ''))) return true;
  if (/^\d{1,3}W(H)?$/i.test(upper)) return true;
  if (/^\d+(\.\d+)?TB$/i.test(upper)) return true;
  if (/^[A-Z0-9.]{1,6}$/i.test(upper) && upper.length <= 6) return true;
  if (/^[A-Z]{2,4}\s+[A-Z0-9]{4,15}$/i.test(upper)) return true;
  if (t.length <= 20 && /[\d.]/.test(t) && !/\s{2,}/.test(t)) return true;
  return false;
}

function reconstruirFragmentosConSpecs(fragmentos) {
  const resultado = [];
  for (const frag of fragmentos) {
    const limpio = frag.trim();
    if (!limpio) continue;
    if (resultado.length > 0 && esFragmentoSpecSuelta(limpio)) {
      resultado[resultado.length - 1] = `${resultado[resultado.length - 1]} ${limpio}`;
    } else {
      resultado.push(limpio);
    }
  }
  return resultado;
}

function dividirEnFragmentos(texto) {
  const fragmentosCrudos = texto
    .split(/[,;]|\.\s|\.-/)
    .flatMap((frag) => {
      const partes = frag.split(/\s+Y\s+/i);
      if (partes.length > 1) {
        const partesPieza = partes.filter((p) => {
          const t = p.trim();
          if (!t) return false;
          if (fragmentoEmpiezaConAlias(t)) return true;
          return (
            /[A-Za-z]+\d+[A-Za-z0-9]*|\d+[A-Za-z]+[A-Za-z0-9]*/.test(t) ||
            /\b[A-Za-z]{5,7}\b/.test(t)
          );
        });
        if (partesPieza.length >= 2) return partes;
      }
      return [frag];
    })
    .map((f) => f.trim())
    .filter((f) => f.length > 0);
  return reconstruirFragmentosConSpecs(fragmentosCrudos);
}

function esCapacidadOTamaño(token) {
  const t = token.toUpperCase().replace(/^\.+|\.+$/g, '');
  if (/^\d{1,3}W$/.test(t)) return true;
  if (/^\d{1,3}WH$/.test(t)) return true;
  if (/^\d+(\.\d+)?TB$/.test(t)) return true;
  if (/^\d+(\.\d+)?(GB|MB)$/.test(t)) return true;
  if (/^\d+(\.\d+)?(HDF?|FHD|UHD|QHD|HD)$/.test(t)) return true;
  if (/^\d+\.\d+$/.test(t)) return true;
  return false;
}

function esCandidatoDpnMixto(token) {
  if (!/^[A-Za-z0-9]{4,15}$/.test(token)) return false;
  if (!/\d/.test(token) || !/[A-Za-z]/.test(token)) return false;
  if (esCapacidadOTamaño(token)) return false;
  if (PALABRAS_NUNCA_DPN.includes(token.toUpperCase())) return false;
  return true;
}

function esCandidatoDpnSoloLetras(token) {
  if (!/^[A-Za-z]{5,7}$/.test(token)) return false;
  if (PALABRAS_NUNCA_DPN.includes(token.toUpperCase())) return false;
  return true;
}

function elegirMejorDpnEnFragmento(texto, permiteSoloLetras) {
  if (texto.includes(':')) {
    const partes = texto.split(':');
    const posibleCodigo = partes[partes.length - 1].trim().split(/\s+/)[0].trim();
    if (
      esCandidatoDpnMixto(posibleCodigo) ||
      (permiteSoloLetras && esCandidatoDpnSoloLetras(posibleCodigo))
    ) {
      return {
        descripcion: partes.slice(0, -1).join(':').trim(),
        numeroParte: posibleCodigo.toUpperCase(),
      };
    }
  }

  const tokenRegex = /\b([A-Za-z0-9]+(?:\.[A-Za-z0-9]+)?)\b/g;
  const candidatos = [];
  let m;
  while ((m = tokenRegex.exec(texto)) !== null) {
    const tokenSinPuntoFinal = m[1].replace(/\.$/, '');
    if (esCapacidadOTamaño(tokenSinPuntoFinal)) continue;
    if (esCandidatoDpnMixto(tokenSinPuntoFinal)) {
      candidatos.push({ token: tokenSinPuntoFinal, index: m.index });
      continue;
    }
    if (permiteSoloLetras && esCandidatoDpnSoloLetras(tokenSinPuntoFinal)) {
      candidatos.push({ token: tokenSinPuntoFinal, index: m.index });
    }
  }
  if (candidatos.length === 0) return null;
  const elegido = candidatos[candidatos.length - 1];
  const descripcion = texto.substring(0, elegido.index).trim();
  if (!descripcion) return null;
  return { descripcion, numeroParte: elegido.token.toUpperCase() };
}

function buscarComponenteDb(descripcion) {
  const descUpper = descripcion.toUpperCase();
  let mejorMatch = null;
  for (const [componenteDb, aliases] of Object.entries(ALIAS_COMPONENTES)) {
    for (const alias of aliases) {
      if (descUpper.includes(alias)) {
        if (!mejorMatch || alias.length > mejorMatch.longitud) {
          mejorMatch = { nombre: componenteDb, longitud: alias.length };
        }
      }
    }
  }
  return mejorMatch ? { nombre: mejorMatch.nombre } : { nombre: null };
}

function extraerSeccionesCategoricas(texto) {
  const textoUpper = texto.toUpperCase();
  const frasesEncontradas = [];

  function buscarFrases(frases, esNecesaria) {
    for (const frase of frases) {
      let posicion = 0;
      while (posicion < textoUpper.length) {
        const pos = textoUpper.indexOf(frase, posicion);
        if (pos === -1) break;
        const existeMasEspecifica = frasesEncontradas.some(
          (f) => f.posicion <= pos && f.posicion + f.longitud >= pos + frase.length
        );
        if (!existeMasEspecifica) {
          const indicesARemover = [];
          frasesEncontradas.forEach((f, idx) => {
            if (pos <= f.posicion && pos + frase.length >= f.posicion + f.longitud) {
              indicesARemover.push(idx);
            }
          });
          for (let i = indicesARemover.length - 1; i >= 0; i--) {
            frasesEncontradas.splice(indicesARemover[i], 1);
          }
          frasesEncontradas.push({
            posicion: pos,
            longitud: frase.length,
            es_necesaria: esNecesaria,
          });
        }
        posicion = pos + 1;
      }
    }
  }

  buscarFrases(FRASES_NECESARIAS, true);
  buscarFrases(FRASES_OPCIONALES, false);
  buscarFrases(FRASES_GENERICAS, true);
  if (frasesEncontradas.length === 0) {
    return [{ texto, es_necesaria: true }];
  }
  frasesEncontradas.sort((a, b) => a.posicion - b.posicion);
  const secciones = [];
  for (let i = 0; i < frasesEncontradas.length; i++) {
    const fraseActual = frasesEncontradas[i];
    const inicioTexto = fraseActual.posicion + fraseActual.longitud;
    const finTexto =
      i + 1 < frasesEncontradas.length
        ? frasesEncontradas[i + 1].posicion
        : texto.length;
    let textoSeccion = texto.substring(inicioTexto, finTexto);
    textoSeccion = textoSeccion.replace(/^[\s.\-:]+/, '').trim();
    if (textoSeccion.length > 0) {
      secciones.push({ texto: textoSeccion, es_necesaria: fraseActual.es_necesaria });
    }
  }
  return secciones.length ? secciones : [{ texto, es_necesaria: true }];
}

function extraerParteDeFragmento(fragmento, es_necesaria) {
  const textoLimpio = fragmento.trim();
  if (textoLimpio.length < 3) return null;
  const tieneAlias = fragmentoEmpiezaConAlias(textoLimpio);
  const dpnElegido = elegirMejorDpnEnFragmento(textoLimpio, tieneAlias);
  if (dpnElegido) {
    const descripcion = dpnElegido.descripcion.replace(/[\-\.]+$/, '').trim();
    if (!descripcion) return null;
    return {
      descripcionPieza: descripcion,
      numeroParte: dpnElegido.numeroParte,
      componenteDb: buscarComponenteDb(descripcion).nombre,
      es_necesaria,
    };
  }
  if (tieneAlias) {
    const palabras = textoLimpio.split(/\s+/).filter(Boolean);
    if (palabras.length <= 8) {
      const nombre = buscarComponenteDb(textoLimpio).nombre;
      if (nombre) {
        return {
          descripcionPieza: textoLimpio,
          numeroParte: '',
          componenteDb: nombre,
          es_necesaria,
        };
      }
    }
  }
  return null;
}

function detectarServiciosSinDPN(textoDiagnostico, piezasYaDetectadas) {
  const textoUpper = textoDiagnostico.toUpperCase();
  const ya = new Set(piezasYaDetectadas.filter((p) => p.componenteDb).map((p) => p.componenteDb));
  const out = [];
  for (const componenteDb of COMPONENTES_SIN_DPN) {
    if (ya.has(componenteDb)) continue;
    const aliases = ALIAS_COMPONENTES[componenteDb] || [];
    for (const alias of aliases) {
      if (textoUpper.includes(alias)) {
        out.push({
          descripcionPieza: componenteDb,
          numeroParte: '',
          componenteDb,
          es_necesaria: true,
        });
        break;
      }
    }
  }
  return out;
}

function extraerPiezasDiagnostico(textoDiagnostico) {
  const secciones = extraerSeccionesCategoricas(textoDiagnostico);
  const piezas = [];
  for (const seccion of secciones) {
    for (const fragmento of dividirEnFragmentos(seccion.texto)) {
      const pieza = extraerParteDeFragmento(fragmento, seccion.es_necesaria);
      if (!pieza) continue;
      const yaExiste = pieza.numeroParte
        ? piezas.some((p) => p.numeroParte === pieza.numeroParte)
        : piezas.some(
            (p) =>
              p.componenteDb &&
              p.componenteDb === pieza.componenteDb &&
              !p.numeroParte
          );
      if (!yaExiste) piezas.push(pieza);
    }
  }
  piezas.push(...detectarServiciosSinDPN(textoDiagnostico, piezas));
  return piezas;
}

// --- Caso real del usuario ---
const TEXTO = (
  'COTIZAR PIEZAS PRIORITARIAS: BATERIA 42WH FDRHM, CARGADOR 45W PLUG CHICO KXTTW Y MANTENIMIENTO. ' +
  'COTIZAR PIEZAS SECUNDARIAS: LCD,15.6HDF,TN,AG,BOE 96M67 Y SSD 1TB NVME.'
);

const piezas = extraerPiezasDiagnostico(TEXTO);

function assert(cond, msg) {
  if (!cond) {
    console.error('FAIL:', msg);
    console.error('Piezas detectadas:', JSON.stringify(piezas, null, 2));
    process.exit(1);
  }
}

const bat = piezas.find((p) => p.componenteDb === 'Batería');
assert(bat, 'Debe detectar Batería');
assert(bat.numeroParte === 'FDRHM', `Batería DPN debe ser FDRHM, fue ${bat.numeroParte}`);
assert(bat.es_necesaria === true, 'Batería debe ser necesaria');

const carg = piezas.find((p) => p.componenteDb === 'Cargador');
assert(carg, 'Debe detectar Cargador');
assert(carg.numeroParte === 'KXTTW', `Cargador DPN debe ser KXTTW, fue ${carg.numeroParte}`);

const pant = piezas.find((p) => p.componenteDb === 'Pantalla');
assert(pant, 'Debe detectar Pantalla (LCD)');
assert(pant.numeroParte === '96M67', `Pantalla DPN debe ser 96M67, fue ${pant.numeroParte}`);
assert(pant.es_necesaria === false, 'Pantalla debe ser secundaria/opcional');

const ssd = piezas.find(
  (p) => p.componenteDb === 'SSD M.2' || p.componenteDb === 'Disco Duro / SSD'
);
assert(ssd, 'Debe detectar SSD (sin inventar DPN falso)');
assert(!ssd.numeroParte || !['1TB', 'NVME'].includes(ssd.numeroParte), 'SSD no debe usar 1TB/NVME como DPN');

const mant = piezas.find((p) => p.componenteDb === 'Limpieza y mantenimiento');
assert(mant, 'Debe detectar Mantenimiento');

console.log('OK — detector piezas (caso CARGADOR + LCD)');
console.log(
  piezas
    .map(
      (p) =>
        `  - ${p.componenteDb || '?'} | DPN=${p.numeroParte || '(vacío)'} | ${p.es_necesaria ? 'necesaria' : 'opcional'}`
    )
    .join('\n')
);
