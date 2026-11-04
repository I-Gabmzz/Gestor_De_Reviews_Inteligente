import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { randomUUID } from 'node:crypto'
import React, { act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'
import react from '@vitejs/plugin-react'

let dom, server, Page, api, root, container, utils
let calls, discovery, onPost, onGet
const BUSINESS = '0xabc:0x123'
const OTHER = '0xabc:0x456'
const baseList = { source: 'Google', import_enabled: true, connections: [{ business_data_id: BUSINESS, business_name: 'Negocio de demostración', status: 'available' }] }
const confirmed = {
  operation_id: '11111111-1111-4111-8111-111111111111', source: 'Google', outcome: 'committed', control_status: 'released',
  input_count: 10, inserted: 4, repeated: 2, changed: 1, omitted: 2, rejected: 1, batch_duplicates: 1,
  request_count: 2, incomplete: false, limited: false, stop_reason: 'no_next_token',
}

before(async () => {
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
  for (const name of ['window', 'document', 'navigator', 'HTMLElement', 'localStorage', 'sessionStorage', 'FormData', 'File']) {
    Object.defineProperty(globalThis, name, { configurable: true, value: dom.window[name], writable: true })
  }
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  server = await createServer({ configFile: false, plugins: [react()], envDir: false,
    cacheDir: join(tmpdir(), `a21f-vite-tests-${randomUUID()}`),
    server: { middlewareMode: true, hmr: false }, appType: 'custom',
    define: { 'import.meta.env.VITE_API_URL': JSON.stringify('/synthetic-only') },
  })
  ;({ default: Page } = await server.ssrLoadModule('/src/pages/ImportReviewsPage.jsx'))
  ;({ default: api } = await server.ssrLoadModule('/src/services/apiClient.js'))
  utils = await server.ssrLoadModule('/src/utils/externalReviewImport.js')
  api.defaults.adapter = async (config) => {
    calls.push(config)
    if (config.method === 'get' && config.url === '/integrations/google/reviews/connections') {
      return { status: 200, data: onGet ? await onGet(config) : discovery, headers: {}, config }
    }
    if (config.method === 'post' && ['/integrations/google/reviews/import', '/reviews/import'].includes(config.url)) {
      return { status: 200, data: await onPost(config), headers: {}, config }
    }
    throw new Error('Unexpected request: real HTTP is forbidden')
  }
})

after(async () => {
  if (root) await unmount()
  await server?.close()
  dom?.window.close()
  for (const name of ['window', 'document', 'navigator', 'HTMLElement', 'localStorage', 'sessionStorage', 'FormData', 'File', 'IS_REACT_ACT_ENVIRONMENT']) delete globalThis[name]
})

function session(id = 1, tenant = 10, role = 'usuario_negocio') {
  localStorage.setItem('gestor_reviews_access_token', `synthetic-token-${id}`)
  localStorage.setItem('gestor_reviews_user', JSON.stringify({ id, tenant_id: tenant, rol: role }))
}

async function mount({ clear = true, list = baseList, role = 'usuario_negocio' } = {}) {
  if (clear) {
    calls = []; onGet = null; onPost = async () => ({ ...confirmed }); discovery = list
    sessionStorage.clear(); localStorage.clear(); session(1, 10, role)
  }
  container = document.createElement('div'); document.body.append(container)
  root = createRoot(container)
  await act(async () => root.render(React.createElement(MemoryRouter, { initialEntries: ['/imports'], future: { v7_startTransition: true, v7_relativeSplatPath: true } },
    React.createElement(Routes, null,
      React.createElement(Route, { path: '/imports', element: React.createElement(Page) }),
      React.createElement(Route, { path: '/reviews', element: React.createElement('h1', null, 'Listado sintético de reviews') }),
    ),
  )))
}

async function unmount() {
  await act(async () => root?.unmount()); container?.remove(); root = null; container = null
}
function button(label) { return [...container.querySelectorAll('button')].find((node) => node.textContent.trim() === label) }
function imports() { return calls.filter((call) => call.url === '/integrations/google/reviews/import') }
async function choose(id = BUSINESS) {
  await act(async () => { const select = container.querySelector('#external-establishment'); select.value = id; select.dispatchEvent(new window.Event('change', { bubbles: true })) })
}
async function submit(times = 1) {
  await act(async () => { for (let n = 0; n < times; n += 1) container.querySelector('#external-establishment').closest('form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true })) })
}
function deferred() { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
function failure(status, code, changes = {}) { return { response: { status, data: { detail: { code, message: 'synthetic-private-internal', outcome: 'rejected', committed_count: 0, control_status: 'released', ...changes } } } } }

test('carga conexiones, envía solo el ID, bloquea doble envío y presenta seis contadores y navegación', async () => {
  try {
    await mount()
    assert.equal(container.querySelector(`option[value="${BUSINESS}"]`).textContent, 'Negocio de demostración')
    assert.doesNotMatch(container.textContent, new RegExp(BUSINESS))
    assert.equal(calls[0].headers.Authorization, 'Bearer synthetic-token-1')
    assert.equal(button('Importar desde Google').disabled, true)
    await choose()
    const pending = deferred(); onPost = () => pending.promise
    await submit(2)
    assert.equal(imports().length, 1)
    assert.deepEqual(JSON.parse(imports()[0].data), { business_data_id: BUSINESS })
    assert.equal(imports()[0].timeout, 720000)
    assert.equal(api.defaults.timeout, 10000)
    assert.equal(button('Importando desde Google…').disabled, true)
    assert.equal(container.querySelector('#external-establishment').disabled, true)
    assert.match(container.textContent, /No envíes otra importación/)
    await act(async () => { pending.resolve(confirmed); await pending.promise })
    assert.match(container.textContent, /Importación confirmada/)
    assert.deepEqual([...container.querySelectorAll('dl dt')].map((item) => item.textContent), ['Obtenidas', 'Insertadas', 'Repetidas', 'Cambiadas', 'Omitidas', 'Rechazadas'])
    assert.deepEqual([...container.querySelectorAll('dl dd')].map((item) => item.textContent), ['10', '4', '2', '1', '2', '1'])
    assert.equal(sessionStorage.length, 0)
    const link = [...container.querySelectorAll('a')].find((node) => node.textContent.includes('Consultar reviews'))
    await act(async () => link.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true, button: 0 })))
    assert.match(container.textContent, /Listado sintético/)
  } finally { await unmount() }
})

for (const [name, list, copy] of [
  ['vacío', { ...baseList, connections: [] }, /no tiene conexiones externas/],
  ['deshabilitado global', { ...baseList, import_enabled: false }, /deshabilitada en el servidor/],
  ['conexión deshabilitada', { ...baseList, connections: [{ business_data_id: BUSINESS, status: 'disabled' }] }, /No hay conexiones habilitadas/],
]) test(`estado ${name} no permite importar`, async () => {
  try {
    await mount({ list })
    assert.match(container.textContent, copy)
    assert.equal(imports().length, 0)
    if (container.querySelector('#external-establishment')) {
      await choose(); await submit()
      assert.equal(button('Importar desde Google').disabled, true)
    }
    assert.equal(imports().length, 0)
  } finally { await unmount() }
})

test('sin rol autorizado no consulta conexiones ni envía aunque se monte la página directamente', async () => {
  try { await mount({ role: 'admin_general' }); assert.equal(calls.length, 0); assert.match(container.textContent, /Tu sesión no permite/)
  } finally { await unmount() }
})

for (const [status, code, changes, blocked] of [
  [404, 'connection_unavailable', {}, false], [409, 'import_in_progress', {}, true],
  [409, 'incomplete_acquisition', { incomplete: true, limited: true, obtained: 3 }, false],
  [429, 'budget_exhausted', {}, false], [500, 'internal_error', { outcome: 'unknown', committed_count: null }, true],
  [502, 'place_unverified', {}, false], [503, 'persistence_failed', { outcome: 'unknown', committed_count: null }, true],
  [504, 'provider_timeout', {}, true],
]) test(`HTTP ${status}/${code} se interpreta sin publicar mensajes internos`, async () => {
  try {
    await mount(); await choose()
    onPost = async () => { throw failure(status, code, changes) }
    await submit()
    assert.equal(imports().length, 1)
    assert.equal(button('Importar desde Google').disabled, blocked)
    assert.doesNotMatch(container.textContent, /synthetic-private-internal|Importación confirmada/)
    if (blocked) assert.match(container.textContent, /protegida en esta pestaña/)
    if (changes.incomplete) assert.match(container.textContent, /adquisición está incompleta/)
    if (changes.limited) assert.match(container.textContent, /límite configurado/)
  } finally { await unmount() }
})

for (const [status, detail, copy] of [
  [401, 'synthetic-private-internal', /sesión expiró/],
  [403, 'synthetic-private-internal', /No tienes permiso/],
  [422, [{ loc: ['body'], msg: 'synthetic-private-internal', input: 'synthetic-private-internal' }], /solicitud no es válida/],
  [422, { code: 'persistence_rejected', outcome: 'rejected', committed_count: 0, control_status: 'released' }, /requisitos para guardar/],
]) test(`detail ${typeof detail}/${status} es seguro y compatible`, async () => {
  try {
    await mount(); await choose()
    onPost = async () => { throw { response: { status, data: { detail } } } }
    await submit()
    assert.match(container.textContent, copy)
    assert.doesNotMatch(container.textContent, /synthetic-private-internal/)
    assert.equal(button('Importar desde Google').disabled, false)
  } finally { await unmount() }
})

for (const code of ['ECONNABORTED', 'ERR_NETWORK']) test(`${code} conserva protección tras recarga de componente y actualizar lista`, async () => {
  try {
    await mount(); await choose()
    onPost = async () => { throw { code, message: 'synthetic-private-internal' } }
    await submit()
    assert.match(container.textContent, /puede haber guardado reseñas/)
    assert.equal(button('Importar desde Google').disabled, true)
    assert.equal(sessionStorage.length, 1)
    await unmount(); await mount({ clear: false }); await choose()
    await act(async () => button('Actualizar conexiones').click())
    await submit()
    assert.equal(imports().length, 1)
    assert.equal(button('Importar desde Google').disabled, true)
    assert.ok([...container.querySelectorAll('a')].some((node) => node.textContent === 'Consultar reviews'))
  } finally { await unmount() }
})

test('navegar durante POST no borra la protección y descarta la respuesta tardía', async () => {
  const pending = deferred()
  try {
    await mount(); await choose(); onPost = () => pending.promise; await submit()
    const signal = imports()[0].signal
    await unmount()
    assert.equal(signal.aborted, true)
    await mount({ clear: false }); await choose()
    await act(async () => { pending.resolve(confirmed); await pending.promise })
    assert.equal(button('Importar desde Google').disabled, true)
    assert.doesNotMatch(container.textContent, /Importación confirmada/)
    assert.equal(imports().length, 1)
  } finally { pending.resolve(confirmed); await unmount() }
})

test('cambio de cuenta descarta resultados y no comparte bloqueos entre tenants', async () => {
  const pending = deferred()
  try {
    await mount(); await choose(); onPost = () => pending.promise; await submit()
    discovery = { ...baseList, connections: [{ business_data_id: OTHER, status: 'available' }] }
    await act(async () => { session(2, 20); window.dispatchEvent(new window.StorageEvent('storage', { key: 'gestor_reviews_user' })) })
    await act(async () => { pending.resolve(confirmed); await pending.promise })
    assert.doesNotMatch(container.textContent, /Importación confirmada/)
    assert.equal(container.querySelector(`option[value="${BUSINESS}"]`), null)
    await choose(OTHER)
    assert.equal(button('Importar desde Google').disabled, false)
    assert.equal(imports().length, 1)
  } finally { pending.resolve(confirmed); await unmount() }
})

for (const result of [{ ...confirmed, control_status: 'reconciliation_required' }, { ...confirmed, inserted: 999 }]) {
  test(`resultado ${result.inserted === 999 ? 'inválido' : 'confirmado con reconciliación'} no habilita repetir`, async () => {
    try {
      await mount(); await choose(); onPost = async () => result; await submit()
      assert.equal(button('Importar desde Google').disabled, true)
      assert.match(container.textContent, /reconciliación/)
      assert.equal(container.textContent.includes('Importación confirmada'), result.inserted !== 999)
    } finally { await unmount() }
  })
}

test('sin almacenamiento de protección no se envía POST', async () => {
  let original
  try {
    await mount()
    original = Object.getOwnPropertyDescriptor(window, 'sessionStorage')
    Object.defineProperty(window, 'sessionStorage', { configurable: true, get() { throw new Error('synthetic storage denied') } })
    await choose(); await submit()
    assert.equal(imports().length, 0)
    assert.equal(button('Importar desde Google').disabled, true)
    assert.match(container.textContent, /no permite conservar/)
  } finally { if (original) Object.defineProperty(window, 'sessionStorage', original); await unmount() }
})

test('CSV y Excel conservan multipart, ruta, validación y timeout general', async () => {
  try {
    for (const extension of ['csv', 'xlsx']) {
      await mount()
      onPost = async (config) => {
        assert.equal(config.url, '/reviews/import')
        assert.equal(config.timeout, 10000)
        assert.equal(config.data.get('file').name, `synthetic.${extension}`)
        return { es_valido: true, filas_guardadas: 1, total_filas: 1 }
      }
      const input = container.querySelector('#reviews-file')
      Object.defineProperty(input, 'files', { configurable: true, value: [new File(['synthetic-only'], `synthetic.${extension}`)] })
      await act(async () => input.dispatchEvent(new window.Event('change', { bubbles: true })))
      await act(async () => input.closest('form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true })))
      assert.match(container.textContent, /Importación completada/)
      assert.equal(imports().length, 0)
      await unmount()
    }
  } finally { await unmount() }
})

test('contratos inválidos de descubrimiento no se muestran ni permiten importar', async () => {
  for (const data of [{ ...baseList, source: 'Other' }, { ...baseList, connections: [...baseList.connections, ...baseList.connections] }, { ...baseList, connections: [{ business_data_id: 'synthetic-private-internal', status: 'available' }] }]) {
    try {
      await mount({ list: data })
      assert.match(container.textContent, /No pudimos consultar/)
      assert.equal(container.querySelector('#external-establishment'), null)
      assert.doesNotMatch(container.textContent, /synthetic-private-internal/)
    } finally { await unmount() }
  }
})

test('el error de listado permite actualizar solo GET y protege estados tardíos', async () => {
  const pending = deferred()
  try {
    await mount(); onGet = () => pending.promise
    await act(async () => button('Actualizar conexiones').click())
    assert.match(container.textContent, /Consultando conexiones/)
    assert.equal(button('Actualizar conexiones').disabled, true)
    await act(async () => { pending.reject({ response: { status: 503, data: { detail: 'synthetic-private-internal' } } }); await pending.promise.catch(() => {}) })
    assert.match(container.textContent, /No pudimos consultar/)
    onGet = null
    await act(async () => button('Actualizar conexiones').click())
    assert.ok(container.querySelector('#external-establishment'))
    assert.equal(imports().length, 0)
  } finally { await unmount() }
})

test('códigos u objetos inesperados no se confunden con rechazo confirmado', () => {
  assert.equal(utils.externalImportFailure({ response: { status: 503, data: { detail: 'unknown' } } }).requiresReview, true)
  assert.equal(utils.externalImportFailure(failure(503, ['provider_unavailable'])).requiresReview, true)
  assert.throws(() => utils.parseExternalImportResult({ ...confirmed, operation_id: [confirmed.operation_id] }))
})

for (const mode of ['logout', 'admin_general']) test(`F1: ${mode} descarta el catálogo y conserva la protección incierta`, async () => {
  try {
    await mount(); await choose()
    onPost = async () => { throw { code: 'ERR_NETWORK' } }
    await submit()
    const marker = sessionStorage.key(0)
    await act(async () => {
      if (mode === 'logout') localStorage.clear()
      else session(3, 20, 'admin_general')
      window.dispatchEvent(new window.StorageEvent('storage', { key: null }))
    })
    assert.equal(Boolean(container.querySelector('#external-establishment')), false)
    assert.doesNotMatch(container.textContent, new RegExp(BUSINESS))
    assert.match(container.textContent, /Tu sesión no permite/)
    assert.equal(calls.filter((call) => call.method === 'get').length, 1)
    assert.equal(sessionStorage.getItem(marker), 'pending')

    discovery = { ...baseList, connections: [{ business_data_id: OTHER, status: 'available' }] }
    await act(async () => { session(2, 20); window.dispatchEvent(new window.StorageEvent('storage', { key: 'gestor_reviews_user' })) })
    assert.equal(Boolean(container.querySelector(`option[value="${BUSINESS}"]`)), false)
    assert.ok(container.querySelector(`option[value="${OTHER}"]`))
    discovery = baseList
    await act(async () => { session(); window.dispatchEvent(new window.StorageEvent('storage', { key: 'gestor_reviews_user' })) })
    await choose(); await submit(2)
    assert.equal(button('Importar desde Google').disabled, true)
    assert.equal(sessionStorage.getItem(marker), 'pending')
    assert.equal(imports().length, 1)
  } finally { await unmount() }
})

for (const [name, change] of [
  ['usuario', () => session(2, 10)],
  ['tenant', () => session(1, 20)],
  ['token de la misma cuenta', () => localStorage.setItem('gestor_reviews_access_token', 'synthetic-rotated-token')],
]) test(`F1: cambio de ${name} oculta catálogo y resultado antes del nuevo GET`, async () => {
  const pending = deferred()
  try {
    await mount(); await choose(); await submit()
    onGet = () => pending.promise
    await act(async () => { change(); window.dispatchEvent(new window.StorageEvent('storage', { key: 'gestor_reviews_user' })) })
    assert.equal(Boolean(container.querySelector('#external-establishment')), false)
    assert.equal(Boolean(container.querySelector('dl')), false)
    assert.doesNotMatch(container.textContent, /Importación confirmada/)
    await act(async () => {
      pending.resolve({ ...baseList, connections: [{ business_data_id: OTHER, status: 'available' }] })
      await pending.promise
    })
    assert.equal(Boolean(container.querySelector(`option[value="${BUSINESS}"]`)), false)
    assert.ok(container.querySelector(`option[value="${OTHER}"]`))
    assert.equal(imports().length, 1)
  } finally { pending.resolve(baseList); await unmount() }
})

test('F1: GET tardío de una sesión invalidada no restaura su catálogo', async () => {
  const oldGet = deferred()
  try {
    await mount(); onGet = () => oldGet.promise
    await act(async () => button('Actualizar conexiones').click())
    const oldSignal = calls.at(-1).signal
    await act(async () => { localStorage.clear(); window.dispatchEvent(new window.StorageEvent('storage', { key: null })) })
    assert.equal(oldSignal.aborted, true)
    assert.equal(Boolean(container.querySelector('#external-establishment')), false)
    assert.doesNotMatch(container.textContent, /Consultando conexiones/)
    onGet = null
    discovery = { ...baseList, connections: [{ business_data_id: OTHER, status: 'available' }] }
    await act(async () => { session(2, 20); window.dispatchEvent(new window.StorageEvent('storage', { key: 'gestor_reviews_user' })) })
    await act(async () => { oldGet.resolve(baseList); await oldGet.promise })
    assert.equal(Boolean(container.querySelector(`option[value="${BUSINESS}"]`)), false)
    assert.ok(container.querySelector(`option[value="${OTHER}"]`))
    assert.equal(imports().length, 0)
  } finally { oldGet.resolve(baseList); await unmount() }
})

test('F1: POST tardío tras logout no restaura resultados ni libera la marca pendiente', async () => {
  const pending = deferred()
  try {
    await mount(); await choose(); onPost = () => pending.promise; await submit()
    const marker = sessionStorage.key(0)
    await act(async () => { localStorage.clear(); window.dispatchEvent(new window.StorageEvent('storage', { key: null })) })
    await act(async () => { pending.resolve(confirmed); await pending.promise })
    assert.equal(Boolean(container.querySelector('#external-establishment')), false)
    assert.equal(Boolean(container.querySelector('dl')), false)
    assert.doesNotMatch(container.textContent, /Importación confirmada/)
    assert.equal(sessionStorage.getItem(marker), 'pending')
    assert.equal(imports().length, 1)
  } finally { pending.resolve(confirmed); await unmount() }
})

for (const [reason, code, status] of [
  ['max_pages', 'incomplete_acquisition', 409],
  ['empty_with_token', 'incomplete_acquisition', 409],
  ['repeated_token', 'incomplete_acquisition', 409],
  ['error', 'provider_unavailable', 503],
]) test(`F2: adquisición ${reason} coherente se presenta como error A-21B, sin éxito ni contadores verificados`, async () => {
  try {
    await mount(); await choose()
    onPost = async () => { throw failure(status, code, {
      operation_id: confirmed.operation_id, request_count: 2, obtained: 3,
      incomplete: true, limited: reason === 'max_pages', stop_reason: reason,
    }) }
    await submit()
    assert.doesNotMatch(container.textContent, /Importación confirmada|synthetic-private-internal/)
    assert.equal(Boolean(container.querySelector('dl')), false)
    assert.match(container.textContent, /adquisición está incompleta/)
    assert.equal(container.textContent.includes('límite configurado'), reason === 'max_pages')
    assert.equal(imports().length, 1)
  } finally { await unmount() }
})

for (const [name, changes] of [
  ['contraejemplo original', { stop_reason: 'max_pages', incomplete: false, limited: false }],
  ['max_pages sin incomplete', { stop_reason: 'max_pages', incomplete: false, limited: true }],
  ['max_pages sin limited', { stop_reason: 'max_pages', incomplete: true, limited: false }],
  ['no_next_token con incomplete', { incomplete: true }],
  ['no_next_token con limited', { limited: true }],
  ['error sin incomplete', { stop_reason: 'error' }],
  ['unknown por HTTP 200', { outcome: 'unknown' }],
  ['rolled_back por HTTP 200', { outcome: 'rolled_back' }],
  ['control_status inválido', { control_status: 'running' }],
  ...['empty_with_token', 'repeated_token', 'error'].map((reason) => [
    `committed incompleto ${reason} no permitido por A-21B`, { stop_reason: reason, incomplete: true, limited: reason === 'max_pages' },
  ]),
]) test(`F2: ${name} conserva incertidumbre y no permite un segundo POST`, async () => {
  try {
    await mount(); await choose()
    onPost = async () => ({ ...confirmed, ...changes, internal_message: 'synthetic-private-internal' })
    await submit(2)
    assert.equal(imports().length, 1)
    assert.doesNotMatch(container.textContent, /Importación confirmada|synthetic-private-internal/)
    assert.equal(Boolean(container.querySelector('dl')), false)
    assert.match(container.textContent, /puede haber guardado reseñas/)
    assert.equal(button('Importar desde Google').disabled, true)
    assert.equal(sessionStorage.length, 1)
    await act(async () => button('Actualizar conexiones').click())
    await submit(2)
    await unmount(); await mount({ clear: false }); await choose(); await submit(2)
    assert.equal(imports().length, 1)
    assert.equal(button('Importar desde Google').disabled, true)
    assert.equal(sessionStorage.length, 1)
  } finally { await unmount() }
})

test('lote limitado confirmado muestra contadores, alcance y permite repetir sin bloqueo', async () => {
  try {
    await mount(); await choose()
    onPost = async () => ({ ...confirmed, stop_reason: 'max_pages', incomplete: true, limited: true })
    await submit()
    assert.match(container.textContent, /Importación confirmada/)
    assert.match(container.textContent, /Se guardó un lote limitado/)
    assert.match(container.textContent, /No representa todas las reseñas/)
    assert.ok(container.querySelector('dl'))
    assert.equal(sessionStorage.length, 0)
    assert.equal(button('Importar desde Google').disabled, false)
    await submit()
    assert.equal(imports().length, 2)
  } finally { await unmount() }
})
