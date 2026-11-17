import assert from 'node:assert/strict'
import { after, afterEach, before, test } from 'node:test'
import React, { act } from 'react'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'
import react from '@vitejs/plugin-react'

let dom, server, App, api, createRoot, root, container, requests, respond
const browserGlobals = ['window', 'document', 'navigator', 'HTMLElement', 'localStorage', 'sessionStorage', 'FormData']
const business = { id: 10, nombre: 'Negocio de prueba', estado: 'activo' }

before(async () => {
  dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost/' })
  for (const name of browserGlobals) {
    Object.defineProperty(globalThis, name, { configurable: true, value: dom.window[name], writable: true })
  }
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  ;({ createRoot } = await import('react-dom/client'))
  server = await createServer({
    configFile: false,
    plugins: [react()],
    server: { middlewareMode: true, hmr: false, ws: false },
    optimizeDeps: { noDiscovery: true },
    appType: 'custom',
  })
  ;({ default: App } = await server.ssrLoadModule('/src/App.jsx'))
  ;({ default: api } = await server.ssrLoadModule('/src/services/apiClient.js'))
  api.defaults.adapter = async (config) => {
    requests.push(config)
    const data = await respond(config)
    return { status: 200, data, headers: {}, config }
  }
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  root = null
})

after(async () => {
  await server?.close()
  dom?.window.close()
  for (const name of [...browserGlobals, 'IS_REACT_ACT_ENVIRONMENT']) delete globalThis[name]
})

function readFixture({ method, url }) {
  if (method === 'get' && url === '/tenants') return { items: [business], total: 1 }
  if (method === 'get' && url === '/admin/google-connections') return { tenant: business, connections: [], users: [] }
  if (method === 'get' && url === '/integrations/google/reviews/connections') {
    return { source: 'Google', import_enabled: false, connections: [] }
  }
  if (method === 'get' && url.includes('/notifications')) return { items: [], total: 0 }
  assert.fail('Solicitud inesperada: ' + method + ' ' + url)
}

async function mount(path, role, handle = readFixture) {
  respond = handle
  requests = []
  localStorage.clear()
  localStorage.setItem('gestor_reviews_access_token', 'fixture-token')
  localStorage.setItem('gestor_reviews_user', JSON.stringify({
    id: 1, nombre: 'Persona de prueba', rol: role, tenant_id: role === 'admin_general' ? null : business.id,
  }))
  window.history.replaceState(null, '', path)
  container = document.querySelector('#root')
  root = createRoot(container)
  await act(async () => root.render(React.createElement(App)))
}

function field(id) {
  const control = document.getElementById(id)
  assert.ok(control, id)
  return control
}

async function fill(id, value) {
  const control = field(id)
  const prototype = control.tagName === 'SELECT' ? window.HTMLSelectElement.prototype : window.HTMLInputElement.prototype
  await act(async () => {
    Object.getOwnPropertyDescriptor(prototype, 'value').set.call(control, value)
    control.dispatchEvent(new window.Event(control.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }))
  })
}

async function chooseFile(name) {
  const control = field('reviews-file')
  const file = new window.File(['contenido,fecha,puntuacion'], name, { type: 'text/plain' })
  await act(async () => {
    Object.defineProperty(control, 'files', { configurable: true, value: [file] })
    control.dispatchEvent(new window.Event('change', { bubbles: true }))
  })
}

async function submit(id, count = 1) {
  const form = field(id).closest('form')
  await act(async () => {
    for (let i = 0; i < count; i++) {
      form.dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }))
    }
  })
}

function assertFieldError(id, pattern) {
  const control = field(id)
  assert.equal(control.getAttribute('aria-invalid'), 'true')
  assert.ok(control.getAttribute('aria-describedby').split(' ').includes(id + '-error'))
  assert.match(field(id + '-error').textContent, pattern)
}

test('CSV identifica una extensión inválida junto al selector y no envía el archivo', async () => {
  await mount('/imports', 'usuario_negocio')
  await chooseFile('reviews.txt')
  assertFieldError('reviews-file', /\.csv o \.xlsx/)
  assert.ok(field('reviews-file').form.querySelector('button').disabled)
  await submit('reviews-file')
  assert.equal(requests.filter(({ method }) => method === 'post').length, 0)
  await chooseFile('reviews.CSV')
  assert.equal(field('reviews-file').getAttribute('aria-invalid'), null)
})

test('CSV anuncia el procesamiento, evita envíos simultáneos y muestra el resultado', async () => {
  let resolveUpload
  await mount('/imports', 'usuario_negocio', (config) => {
    if (config.url === '/reviews/import') return new Promise((resolve) => { resolveUpload = resolve })
    return readFixture(config)
  })
  await chooseFile('reviews.xlsx')
  await submit('reviews-file', 2)
  assert.equal(requests.filter(({ url }) => url === '/reviews/import').length, 1)
  assert.equal(field('reviews-file').form.getAttribute('aria-busy'), 'true')
  assert.ok(field('reviews-file').disabled)
  assert.match(container.textContent, /Procesando el archivo/)
  await act(async () => resolveUpload({ es_valido: true, total_filas: 1, filas_guardadas: 1 }))
  assert.equal(field('reviews-file').form.getAttribute('aria-busy'), 'false')
  assert.match(container.textContent, /Importación completada/)
  await chooseFile('otro.csv')
  assert.doesNotMatch(container.textContent, /Importación completada|Las métricas se recalcularán/)
})

test('CSV muestra errores de filas y devuelve al selector la indicación de corregir el archivo', async () => {
  await mount('/imports', 'usuario_negocio', (config) => config.url === '/reviews/import' ? {
    es_valido: false, total_errores: 1, errores_por_fila: [{ fila: 2, campo: 'puntuacion', mensaje: 'Valor inválido' }],
  } : readFixture(config))
  await chooseFile('reviews.csv')
  await submit('reviews-file')
  assertFieldError('reviews-file', /Corrige los errores/)
  const errors = container.querySelector('ul[aria-label="Errores por fila"]')
  assert.match(errors.textContent, /Fila 2 · puntuacion/)
  assert.match(errors.textContent, /Valor inválido/)
})

test('alta administrativa asocia la validación nativa y el error estructurado de la API al correo', async () => {
  await mount('/admin', 'admin_general', (config) => {
    if (config.url === '/admin/business-accounts') {
      throw { response: { status: 422, data: { detail: [{ loc: ['body', 'correo'], msg: 'diagnóstico interno de prueba' }] } } }
    }
    return readFixture(config)
  })
  await fill('admin-account-email', 'incorrecto')
  await act(async () => assert.equal(field('admin-account-email').checkValidity(), false))
  assertFieldError('admin-account-email', /.+/)
  await fill('admin-account-email', 'persona@example.test')
  assert.equal(field('admin-account-email').getAttribute('aria-invalid'), null)
  await submit('admin-account-email')
  assertFieldError('admin-account-email', /Revisa el valor/)
  assert.match(field('admin-account').parentElement.textContent, /Revisa los datos del formulario/)
  assert.doesNotMatch(container.textContent, /diagnóstico interno de prueba/)
})

test('vincular Google Maps muestra procesamiento y error operativo junto al formulario', async () => {
  let rejectLink
  await mount('/admin', 'admin_general', (config) => {
    if (config.url === '/admin/google-connections' && config.method === 'post') {
      return new Promise((resolve, reject) => { rejectLink = reject })
    }
    return readFixture(config)
  })
  await fill('admin-link-maps', 'https://maps.app.goo.gl/FichaDePrueba')
  await act(async () => field('admin-link-confirm').click())
  await submit('admin-link-maps', 2)
  assert.equal(requests.filter(({ url, method }) => url === '/admin/google-connections' && method === 'post').length, 1)
  assert.equal(field('admin-link').getAttribute('aria-busy'), 'true')
  assert.equal(field('admin-account').getAttribute('aria-busy'), 'false')
  assert.match(field('admin-link').parentElement.textContent, /Guardando la conexión/)
  await act(async () => rejectLink(new Error('Fallo de transporte simulado')))
  assert.equal(field('admin-link').getAttribute('aria-busy'), 'false')
  assert.match(field('admin-link').parentElement.textContent, /No pudimos confirmar el resultado/)
})

test('cambio de rol señala el ID inválido y muestra el resultado de un ID válido', async () => {
  await mount('/admin', 'admin_general', (config) => config.url === '/users/23/role'
    ? { id: 23, nombre: 'Persona de prueba', rol: 'admin_tenant' }
    : readFixture(config))
  await act(async () => assert.equal(field('role-user-id').checkValidity(), false))
  assertFieldError('role-user-id', /Ingresa un ID de usuario válido/)
  assert.equal(requests.filter(({ method }) => method === 'patch').length, 0)
  await fill('role-user-id', '23')
  assert.equal(field('role-user-id').getAttribute('aria-invalid'), null)
  await submit('role-user-id')
  assert.equal(requests.filter(({ url }) => url === '/users/23/role').length, 1)
  assert.match(field('role-user-id').form.textContent, /Rol guardado/)
})
