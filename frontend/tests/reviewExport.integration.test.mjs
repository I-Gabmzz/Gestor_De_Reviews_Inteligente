import assert from 'node:assert/strict'
import { after, afterEach, before, test } from 'node:test'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'

let dom
let server
let React
let act
let createRoot
let MemoryRouter
let ReviewsPage
let apiClient
let root
let container
let originalAdapter
let originalCreateObjectURL
let originalRevokeObjectURL
let originalAnchorClick
let exportReply
let requests = []
let downloads = []
let revoked = []

const review = {
  id: 101, tenant_id: 10, autor: 'Ana', contenido: 'Excelente atención',
  fecha: '2026-10-24T08:00:00', fuente: 'Google', puntuacion: 5,
  categoria: null, estado: 'nueva', prioridad: 'Alta', resumen: null, tema: null,
}
const csvBytes = new TextEncoder().encode(
  '\uFEFFid,contenido,autor,fecha,fuente,puntuacion,categoria,estado\r\n101,Excelente atención,Ana,2026-10-24T08:00:00,Google,5,,nueva\r\n',
)
const csvBlob = new Blob([csvBytes], { type: 'text/csv' })

function response(config, data, headers = {}) {
  return { data, status: 200, statusText: 'OK', headers, config }
}

function csvResponse(config, disposition = 'attachment; filename="reviews_20261024.csv"') {
  return response(config, csvBlob, {
    'content-type': 'text/csv; charset=utf-8',
    'content-disposition': disposition,
  })
}

before(async () => {
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.navigator = dom.window.navigator
  globalThis.HTMLElement = dom.window.HTMLElement
  globalThis.localStorage = dom.window.localStorage
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  React = await import('react')
  ;({ act } = React)
  ;({ createRoot } = await import('react-dom/client'))
  ;({ MemoryRouter } = await import('react-router-dom'))
  originalCreateObjectURL = URL.createObjectURL
  originalRevokeObjectURL = URL.revokeObjectURL
  originalAnchorClick = dom.window.HTMLAnchorElement.prototype.click
  URL.createObjectURL = (blob) => {
    downloads.push({ blob, url: 'blob:test-export' })
    return 'blob:test-export'
  }
  URL.revokeObjectURL = (url) => { revoked.push(url) }
  dom.window.HTMLAnchorElement.prototype.click = function () {
    downloads.at(-1).filename = this.download
    downloads.at(-1).href = this.href
  }
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  ;({ default: ReviewsPage } = await server.ssrLoadModule('/src/pages/ReviewsPage.jsx'))
  ;({ default: apiClient } = await server.ssrLoadModule('/src/services/apiClient.js'))
  originalAdapter = apiClient.defaults.adapter
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
  container = null
  apiClient.defaults.adapter = originalAdapter
  localStorage.clear()
  requests = []
  downloads = []
  revoked = []
  exportReply = null
})

after(async () => {
  await server?.close()
  URL.createObjectURL = originalCreateObjectURL
  URL.revokeObjectURL = originalRevokeObjectURL
  dom?.window.HTMLAnchorElement && (dom.window.HTMLAnchorElement.prototype.click = originalAnchorClick)
  dom?.window.close()
  for (const name of ['window', 'document', 'navigator', 'HTMLElement', 'localStorage', 'IS_REACT_ACT_ENVIRONMENT']) {
    delete globalThis[name]
  }
})

async function mount(role = 'usuario_negocio') {
  localStorage.setItem('gestor_reviews_access_token', 'token-de-prueba')
  localStorage.setItem('gestor_reviews_user', JSON.stringify({ id: 1, rol: role, tenant_id: 10 }))
  apiClient.defaults.adapter = async (config) => {
    requests.push(config)
    if (config.url === '/reviews') return response(config, { items: [review], total: 1 })
    if (config.url === '/reviews/101') return response(config, review)
    if (config.url === '/reviews/export') return exportReply ? exportReply(config) : csvResponse(config)
    throw new Error(`Solicitud inesperada: ${config.url}`)
  }
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  await act(async () => {
    root.render(React.createElement(MemoryRouter, null, React.createElement(ReviewsPage)))
  })
}

async function unmount() {
  await act(async () => root.unmount())
  container.remove()
  root = null
  container = null
}

function button(label) {
  return [...container.querySelectorAll('button')].find((element) => element.textContent.trim() === label)
}

async function clickExport() {
  await act(async () => { button('Exportar CSV').click() })
}

function inputValue(input, value) {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
  setter.call(input, value)
  input.dispatchEvent(new window.Event('input', { bubbles: true }))
}

function deferred() {
  let resolve
  const promise = new Promise((accept) => { resolve = accept })
  return { promise, resolve }
}

test('el botón aparece solo para los dos roles autorizados', async () => {
  for (const role of ['usuario_negocio', 'admin_tenant', 'admin_general']) {
    await mount(role)
    assert.equal(Boolean(button('Exportar CSV')), role !== 'admin_general')
    await unmount()
  }
})

test('exporta el Blob recibido con autenticación, filtros y nombre del servidor sin alterar la pantalla', async () => {
  await mount()
  exportReply = (config) => csvResponse(config, 'attachment; filename="reporte_reviews.csv"')
  await clickExport()
  const request = requests.find((item) => item.url === '/reviews/export')
  assert.equal(request.method, 'get')
  assert.equal(request.responseType, 'blob')
  assert.equal(request.headers.Authorization, 'Bearer token-de-prueba')
  assert.deepEqual(request.params, {})
  assert.equal(downloads.length, 1)
  assert.strictEqual(downloads[0].blob, csvBlob)
  assert.deepEqual(new Uint8Array(await downloads[0].blob.arrayBuffer()), csvBytes)
  assert.equal(downloads[0].filename, 'reporte_reviews.csv')
  assert.deepEqual(revoked, ['blob:test-export'])
  assert.equal(document.querySelector('a[download]'), null)
  assert.equal(container.querySelector('#review-search').value, '')
  assert.match(container.textContent, /Excelente atención/)
})

test('usa los filtros de la última lista cargada, también durante el debounce', async () => {
  await mount()
  await act(async () => {
    inputValue(container.querySelector('#review-search'), '  excelente  ')
    inputValue(container.querySelector('#review-fuente'), '  Google  ')
  })
  await clickExport()
  assert.deepEqual(requests.filter((item) => item.url === '/reviews/export')[0].params, {})

  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 450)) })
  await act(async () => {
    for (const [id, value] of [
      ['review-fecha-desde', '2026-10-01'], ['review-fecha-hasta', '2026-10-24'],
      ['review-puntuacion', '5'], ['review-estado', 'nueva'],
    ]) {
      const element = container.querySelector(`#${id}`)
      if (element.tagName === 'SELECT') element.value = value
      else inputValue(element, value)
      element.dispatchEvent(new window.Event('change', { bubbles: true }))
    }
  })
  await clickExport()
  const expected = {
    busqueda: 'excelente', fecha_desde: '2026-10-01', fecha_hasta: '2026-10-24',
    puntuacion: '5', estado: 'nueva', fuente: 'Google',
  }
  assert.deepEqual(requests.filter((item) => item.url === '/reviews').at(-1).params, expected)
  assert.deepEqual(requests.filter((item) => item.url === '/reviews/export').at(-1).params, expected)
  assert.equal(container.querySelector('#review-search').value, '  excelente  ')
  assert.equal(container.querySelector('#review-fuente').value, '  Google  ')
  assert.match(container.textContent, /Excelente atención/)
})

test('muestra carga, bloquea clics repetidos y libera recursos al terminar', async () => {
  await mount()
  const pending = deferred()
  exportReply = () => pending.promise
  await clickExport()
  assert.equal(button('Exportando CSV…').disabled, true)
  button('Exportando CSV…').click()
  assert.equal(requests.filter((item) => item.url === '/reviews/export').length, 1)
  await act(async () => { pending.resolve(csvResponse(requests.at(-1))); await pending.promise })
  assert.equal(button('Exportar CSV').disabled, false)
  assert.deepEqual(revoked, ['blob:test-export'])
})

test('usa respaldo ante nombre ausente o inseguro', async () => {
  await mount()
  for (const disposition of [undefined, 'attachment; filename="../privado.csv"']) {
    exportReply = (config) => disposition === undefined
      ? response(config, csvBlob, { 'content-type': 'text/csv; charset=utf-8' })
      : csvResponse(config, disposition)
    await clickExport()
    assert.match(downloads.at(-1).filename, /^reviews_\d{8}\.csv$/)
  }
})

test('muestra errores HTTP, de red y CSV inválido sin descargar ni perder filtros', async () => {
  await mount()
  const cases = [
    [() => { throw { response: { status: 401 } } }, /sesión expiró/],
    [() => { throw { response: { status: 403 } } }, /No tienes permiso/],
    [() => { throw { response: { status: 500 } } }, /No fue posible exportar/],
    [() => { throw new Error('sin conexión') }, /No pudimos conectar/],
    [(config) => response(config, new Blob([]), { 'content-type': 'text/csv' }), /CSV válido/],
    [(config) => response(config, csvBlob, { 'content-type': 'text/html' }), /CSV válido/],
    [(config) => response(config, new Blob(['error']), { 'content-type': 'text/csv' }), /CSV válido/],
  ]
  for (const [reply, message] of cases) {
    exportReply = reply
    await clickExport()
    assert.match(container.querySelector('[role="alert"]').textContent, message)
    assert.equal(button('Exportar CSV').disabled, false)
    assert.equal(downloads.length, 0)
    assert.match(container.textContent, /Excelente atención/)
  }
})
