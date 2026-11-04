import assert from 'node:assert/strict'
import { before, after, test } from 'node:test'
import React, { act } from 'react'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'
import react from '@vitejs/plugin-react'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { randomUUID } from 'node:crypto'

let dom, server, Panel, api, root, container, calls, onCreate, onLink, createRoot
const businesses = [{ id: 10, nombre: 'Negocio A', estado: 'activo' }, { id: 20, nombre: 'Negocio B', estado: 'activo' }]
const connection = { business_data_id: '0xabc:0x123', enabled: true, google_maps_url: 'https://www.google.com/maps?ftid=0xabc:0x123' }
const PASSWORD = 'synthetic-form-password'

before(async () => {
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
  for (const name of ['window', 'document', 'navigator', 'HTMLElement', 'localStorage', 'FormData']) Object.defineProperty(globalThis, name, { configurable: true, value: dom.window[name], writable: true })
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  ;({ createRoot } = await import('react-dom/client'))
  server = await createServer({ configFile: false, plugins: [react()], envDir: false,
    cacheDir: join(tmpdir(), `admin-panel-tests-${randomUUID()}`), server: { middlewareMode: true, hmr: false }, appType: 'custom',
    define: { 'import.meta.env.VITE_API_URL': JSON.stringify('/synthetic-only') } })
  ;({ default: Panel } = await server.ssrLoadModule('/src/components/AdminBusinessPanel.jsx'))
  ;({ default: api } = await server.ssrLoadModule('/src/services/apiClient.js'))
  api.defaults.adapter = async (config) => {
    calls.push(config)
    let data
    if (config.method === 'get' && config.url === '/tenants') data = { items: businesses, total: 2 }
    else if (config.method === 'get' && config.url === '/admin/google-connections') data = {
      tenant: businesses.find((row) => row.id === config.params.tenant_id), connections: [connection],
      users: [{ id: 1, nombre: 'Persona del negocio', correo: 'business@example.com', rol: 'admin_tenant', estado: 'activo' }],
    }
    else if (config.method === 'post' && config.url === '/admin/business-accounts') data = await onCreate(JSON.parse(config.data))
    else if (config.method === 'post' && config.url === '/admin/google-connections') data = await onLink(JSON.parse(config.data))
    else if (config.method === 'patch' && config.url === '/admin/google-connections') data = { ...connection, enabled: JSON.parse(config.data).enabled }
    else throw new Error('Unexpected request; real HTTP forbidden')
    return { status: 200, data, headers: {}, config }
  }
})

after(async () => {
  await unmount(); await server.close(); dom.window.close()
  for (const name of ['window', 'document', 'navigator', 'HTMLElement', 'localStorage', 'FormData', 'IS_REACT_ACT_ENVIRONMENT']) delete globalThis[name]
})

async function mount(role = 'admin_general') {
  calls = []; localStorage.clear()
  localStorage.setItem('gestor_reviews_access_token', 'synthetic-token')
  localStorage.setItem('gestor_reviews_user', JSON.stringify({ id: 3, rol: role, tenant_id: role === 'admin_general' ? null : 10 }))
  onCreate = async () => ({ tenant: businesses[0], user: { correo: 'new@example.com' }, connection: null })
  onLink = async () => connection
  container = document.createElement('div'); document.body.append(container); root = createRoot(container)
  await act(async () => root.render(React.createElement(Panel)))
}
async function unmount() { if (root) await act(async () => root.unmount()); root = null; container?.remove(); container = null }
function control(label) { const node = [...container.querySelectorAll('label')].find((row) => row.textContent.trim().startsWith(label)); assert.ok(node, label); return node.querySelector('input,select') }
async function fill(label, value) {
  const input = control(label)
  const prototype = input.tagName === 'SELECT' ? window.HTMLSelectElement.prototype : window.HTMLInputElement.prototype
  await act(async () => { Object.getOwnPropertyDescriptor(prototype, 'value').set.call(input, value); input.dispatchEvent(new window.Event('input', { bubbles: true })); input.dispatchEvent(new window.Event('change', { bubbles: true })) })
}
async function click(label) { const button = [...container.querySelectorAll('button')].find((row) => row.textContent.trim() === label); assert.ok(button, label); await act(async () => button.click()) }
async function submit(label, times = 1) { const form = control(label).closest('form'); await act(async () => { for (let n = 0; n < times; n++) form.dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true })) }) }
function writes(path) { return calls.filter((call) => call.method !== 'get' && call.url === path) }

test('non-general roles never request administrative data', async () => {
  try { await mount('admin_tenant'); assert.equal(calls.length, 0); assert.match(container.textContent, /Inicia sesión como administrador general/) } finally { await unmount() }
})

test('catalog shows business name and assigned accounts without requesting SerpApi', async () => {
  try {
    await mount()
    assert.match(container.textContent, /Negocio A|Persona del negocio|business@example.com/)
    assert.ok(calls.every((call) => call.method === 'get'))
    assert.equal(calls[0].headers.Authorization, 'Bearer synthetic-token')
    assert.equal(container.querySelector('input[type="password"]').type, 'password')
    assert.ok([...control('Permisos de la cuenta').options].every((option) => option.value !== 'admin_general'))
    await fill('Nombre de la persona', 'Nombre conservado')
    await act(async () => window.dispatchEvent(new window.Event('focus')))
    assert.equal(control('Nombre de la persona').value, 'Nombre conservado')
  } finally { await unmount() }
})

test('creating account assigns selected business and clears private password', async () => {
  try {
    await mount(); await fill('Negocio de la cuenta', '20'); await fill('Nombre de la persona', 'Nueva persona')
    await fill('Correo de acceso', 'new@example.com'); await fill('Contraseña inicial', PASSWORD)
    await fill('Permisos de la cuenta', 'usuario_negocio')
    await submit('Correo de acceso')
    assert.equal(writes('/admin/business-accounts').length, 1)
    assert.deepEqual(JSON.parse(writes('/admin/business-accounts')[0].data), {
      tenant_id: 20, nombre: 'Nueva persona', correo: 'new@example.com', password: PASSWORD, rol: 'usuario_negocio',
    })
    assert.equal(control('Contraseña inicial').value, '')
    assert.match(container.textContent, /Cuenta creada/)
  } finally { await unmount() }
})

test('new business can be created with account and confirmed Maps link in one request', async () => {
  try {
    await mount(); await act(async () => control('Nuevo negocio').click())
    await fill('Nombre del nuevo negocio', 'Negocio nuevo'); await fill('Nombre de la persona', 'Nueva persona')
    await fill('Correo de acceso', 'new@example.com'); await fill('Contraseña inicial', PASSWORD)
    await act(async () => control('Vincular Google Maps al crear la cuenta').click())
    await fill('Enlace de Google Maps para la nueva cuenta', 'https://maps.app.goo.gl/Synthetic')
    await act(async () => control('Confirmo que esta ficha corresponde al negocio de la cuenta.').click())
    await submit('Correo de acceso')
    const payload = JSON.parse(writes('/admin/business-accounts')[0].data)
    assert.equal(payload.business_name, 'Negocio nuevo'); assert.equal(payload.confirmed, true)
    assert.equal(payload.google_maps_url, 'https://maps.app.goo.gl/Synthetic')
    assert.equal('tenant_id' in payload, false)
  } finally { await unmount() }
})

test('link existing business sends the selected ID and explicit confirmation', async () => {
  try {
    await mount(); await fill('Negocio a vincular', '20')
    await fill('Enlace de Google Maps', 'https://maps.app.goo.gl/Synthetic')
    await act(async () => control('Confirmo que la ficha corresponde a Negocio B.').click())
    await submit('Enlace de Google Maps')
    assert.deepEqual(JSON.parse(writes('/admin/google-connections')[0].data), {
      tenant_id: 20, google_maps_url: 'https://maps.app.goo.gl/Synthetic', confirmed: true,
    })
    assert.match(container.textContent, /Ficha de Google Maps vinculada/)
  } finally { await unmount() }
})

test('pause uses an explicit state change and never sends review import', async () => {
  try {
    await mount(); await click('Pausar conexión')
    assert.deepEqual(JSON.parse(writes('/admin/google-connections')[0].data), { tenant_id: 10, business_data_id: connection.business_data_id, enabled: false })
    assert.equal(calls.filter((call) => call.url.includes('/reviews/import')).length, 0)
  } finally { await unmount() }
})

test('double submit produces only one mutation', async () => {
  let resolve
  try {
    await mount(); await fill('Negocio de la cuenta', '10')
    onCreate = () => new Promise((done) => { resolve = done })
    await submit('Correo de acceso', 2)
    assert.equal(writes('/admin/business-accounts').length, 1)
    await act(async () => resolve({ tenant: businesses[0], user: { correo: 'new@example.com' }, connection: null }))
  } finally { resolve?.({ tenant: businesses[0], user: { correo: 'new@example.com' }, connection: null }); await unmount() }
})

test('session changes hide accounts and discard a late create response', async () => {
  let resolve
  try {
    await mount(); onCreate = () => new Promise((done) => { resolve = done })
    await submit('Correo de acceso')
    await act(async () => { localStorage.clear(); window.dispatchEvent(new window.StorageEvent('storage', { key: null })) })
    await act(async () => resolve({ tenant: businesses[0], user: { correo: 'private-new@example.com' }, connection: null }))
    assert.doesNotMatch(container.textContent, /private-new@example.com|business@example.com|Cuenta creada/)
    assert.match(container.textContent, /Inicia sesión como administrador general/)
  } finally { resolve?.({ tenant: businesses[0], user: { correo: 'new@example.com' }, connection: null }); await unmount() }
})
