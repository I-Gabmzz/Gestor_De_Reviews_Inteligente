import assert from 'node:assert/strict'
import { after, afterEach, before, test } from 'node:test'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { randomUUID } from 'node:crypto'
import React, { act } from 'react'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'
import react from '@vitejs/plugin-react'

let dom, server, api, App, root, createRoot
const globals = ['window', 'document', 'navigator', 'HTMLElement', 'localStorage']
const tokenKey = 'gestor_reviews_access_token'
const userKey = 'gestor_reviews_user'

before(async () => {
  server = await createServer({
    configFile: false, plugins: [react()], appType: 'custom', envDir: false,
    cacheDir: join(tmpdir(), `access-tests-${randomUUID()}`),
    server: { middlewareMode: true, hmr: false },
    define: { 'import.meta.env.VITE_API_URL': JSON.stringify('/test-only') },
  })
  ;({ default: App } = await server.ssrLoadModule('/src/App.jsx'))
  ;({ default: api } = await server.ssrLoadModule('/src/services/apiClient.js'))
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  dom?.window.close()
  root = null
  for (const name of [...globals, 'IS_REACT_ACT_ENVIRONMENT']) delete globalThis[name]
})

after(async () => server?.close())

function setSession(token, rol = 'admin_general') {
  localStorage.setItem(tokenKey, token)
  localStorage.setItem(userKey, JSON.stringify({ id: 3, rol, correo: 'cuenta@example.com' }))
}

async function mount(path, rol, adapter) {
  dom = new JSDOM('<main id="root"></main>', { url: `http://localhost${path}` })
  for (const name of globals) {
    Object.defineProperty(globalThis, name, { configurable: true, value: dom.window[name] })
  }
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  ;({ createRoot } = await import('react-dom/client'))
  if (rol) setSession('previous-token', rol)
  api.defaults.adapter = adapter
  root = createRoot(document.getElementById('root'))
  await act(async () => root.render(React.createElement(App)))
}

function httpError(config, status, detail) {
  return Object.assign(new Error(detail), { config, response: { status, data: { detail } } })
}

test('una respuesta 401 en una vista protegida vuelve al inicio con aviso', async () => {
  await mount('/admin', 'admin_general', async (config) => {
    throw httpError(config, 401, 'Token inválido o ausente')
  })
  assert.equal(window.location.pathname, '/')
  assert.equal(localStorage.getItem(tokenKey), null)
  assert.equal(localStorage.getItem(userKey), null)
  assert.match(document.querySelector('[role="status"]').textContent, /Tu sesión terminó/)
})

test('un 401 tardío no borra una sesión que acaba de cambiar', async () => {
  let rejectRequest
  await mount('/admin', 'admin_general', (config) => new Promise((_, reject) => {
    rejectRequest = () => reject(httpError(config, 401, 'Token inválido o ausente'))
  }))
  setSession('new-token')
  await act(async () => rejectRequest())
  assert.equal(localStorage.getItem(tokenKey), 'new-token')
  assert.equal(window.location.pathname, '/admin')
})

test('una ruta denegada conserva la sesión y ofrece el inicio autorizado', async () => {
  await mount('/admin', 'usuario_negocio', () => assert.fail('La ruta denegada no debe consultar la API'))
  assert.equal(window.location.pathname, '/sin-acceso')
  assert.equal(localStorage.getItem(tokenKey), 'previous-token')
  const home = [...document.querySelectorAll('a')].find((link) => link.textContent.trim() === 'Ir a mi inicio')
  assert.equal(home?.getAttribute('href'), '/dashboard')
})

test('el acceso indica con quién recuperar la cuenta y muestra credenciales inválidas', async () => {
  await mount('/', 'admin_general', async (config) => {
    assert.equal(config.url, '/auth/login')
    assert.equal(config.headers.get('Authorization'), undefined)
    throw httpError(config, 401, 'Credenciales inválidas')
  })
  const help = document.querySelector('details')
  assert.match(help.textContent, /Contacta a la persona que administra las cuentas de tu negocio/)
  for (const [id, value] of [['correo', 'cuenta@example.com'], ['password', 'incorrecta']]) {
    const input = document.getElementById(id)
    await act(async () => {
      Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(input, value)
      input.dispatchEvent(new window.Event('input', { bubbles: true }))
    })
  }
  await act(async () => document.querySelector('form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true })))
  assert.match(document.querySelector('[role="alert"]').textContent, /El correo o la contraseña son incorrectos/)
  assert.equal(localStorage.getItem(tokenKey), 'previous-token')
})
