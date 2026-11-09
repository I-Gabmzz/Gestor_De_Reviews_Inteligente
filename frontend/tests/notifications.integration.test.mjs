import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import React, { act, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'

let dom, server, NotificationBell, ReviewsPage, service, apiClient, root, container, changeUser
const user = { id: 1, tenant_id: 10, rol: 'usuario_negocio' }
const review = { id: 102, tenant_id: 10, autor: 'Caso importante', contenido: 'Me cobraron dos veces.',
  fecha: '2026-11-01T12:00:00', fuente: 'manual', puntuacion: 5, estado: 'nueva', prioridad: 'Alta' }
const notification = { id: 1, review_id: 102, creada_en: '2026-11-01T12:00:00Z', autor: 'Caso importante', extracto: 'Me cobraron dos veces.', prioridad: 'Alta' }

before(async () => {
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
  for (const name of ['window', 'document', 'navigator', 'HTMLElement', 'localStorage']) {
    globalThis[name] = name === 'window' ? dom.window : dom.window[name]
  }
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' })
  ;({ default: NotificationBell } = await server.ssrLoadModule('/src/components/NotificationBell.jsx'))
  ;({ default: ReviewsPage } = await server.ssrLoadModule('/src/pages/ReviewsPage.jsx'))
  ;({ default: apiClient } = await server.ssrLoadModule('/src/services/apiClient.js'))
  service = await server.ssrLoadModule('/src/services/notificationService.js')
})

after(async () => {
  await server?.close()
  dom?.window.close()
  for (const name of ['window', 'document', 'navigator', 'HTMLElement', 'localStorage', 'IS_REACT_ACT_ENVIRONMENT']) delete globalThis[name]
})

function Location() {
  const location = useLocation()
  return React.createElement('output', { 'data-testid': 'location' }, location.pathname + location.search)
}

function Harness({ initialUser }) {
  const [currentUser, setUser] = useState(initialUser)
  changeUser = setUser
  return React.createElement(React.Fragment, null,
    React.createElement(NotificationBell, { user: currentUser }),
    React.createElement(Routes, null,
      React.createElement(Route, { path: '/reviews', element: React.createElement(ReviewsPage) }),
      React.createElement(Route, { path: '*', element: React.createElement('p', null, 'Inicio') }),
    ),
    React.createElement(Location),
  )
}

async function mount({ initialUser = user, path = '/dashboard' } = {}) {
  localStorage.setItem('gestor_reviews_access_token', 'synthetic-token')
  localStorage.setItem('gestor_reviews_user', JSON.stringify(initialUser))
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  await act(async () => {
    root.render(React.createElement(MemoryRouter, { initialEntries: [path], future: { v7_startTransition: true, v7_relativeSplatPath: true } }, React.createElement(Harness, { initialUser })))
  })
}

async function unmount() {
  await act(async () => { root?.unmount() })
  container?.remove()
  root = null
  localStorage.clear()
}

function trigger() { return container.querySelector('button[aria-controls]') }
function panel() { return container.querySelector('section[aria-label="Avisos de prioridad alta"]') }
function button(label) { return [...container.querySelectorAll('button')].find((element) => element.getAttribute('aria-label') === label || element.textContent.trim() === label) }
function deferred() { let resolve; const promise = new Promise((accept) => { resolve = accept }); return { promise, resolve } }

test('consulta autenticada con paginación sin enviar tenant y rechaza estructuras inválidas', async () => {
  const original = apiClient.defaults.adapter
  localStorage.setItem('gestor_reviews_access_token', 'synthetic-token')
  let config
  apiClient.defaults.adapter = async (request) => {
    config = request
    return { data: { items: [notification], total: 1 }, status: 200, statusText: 'OK', headers: {}, config: request }
  }
  try {
    const controller = new AbortController()
    assert.equal((await service.getNotifications({ signal: controller.signal, offset: 5, tenant_id: 20 })).total, 1)
    assert.equal(config.url, '/notificaciones')
    assert.deepEqual(config.params, { limit: 5, offset: 5 })
    assert.equal(config.headers.Authorization, 'Bearer synthetic-token')
    assert.equal(config.signal, controller.signal)
    apiClient.defaults.adapter = async (request) => ({ data: { items: [{ ...notification, review_id: 'https://other.example/' }], total: 1 }, status: 200, headers: {}, config: request })
    await assert.rejects(service.getNotifications(), /no es válida/)
  } finally {
    apiClient.defaults.adapter = original
    localStorage.clear()
  }
})

test('muestra contador, lista el aviso y abre exactamente su review conservando seguimiento', async () => {
  const original = apiClient.get
  const calls = []
  apiClient.get = async (url) => {
    calls.push(url)
    if (url === '/notificaciones') return { data: { items: [notification], total: 1 } }
    if (url === '/reviews') return { data: { items: [{ ...review, id: 101, autor: 'Primera fila' }, review], total: 2 } }
    return { data: { ...review } }
  }
  try {
    await mount()
    assert.equal(trigger().getAttribute('aria-label'), 'Avisos de prioridad alta: 1')
    await act(async () => { trigger().click() })
    const link = panel().querySelector('a')
    assert.equal(link.getAttribute('href'), '/reviews?review=102')
    await act(async () => { link.click() })
    assert.equal(panel(), null)
    assert.equal(container.querySelector('[data-testid="location"]').textContent, '/reviews?review=102')
    const detail = container.querySelector('[aria-label="Detalle de la review"]')
    assert.match(detail.textContent, /Caso importante/)
    assert.match(detail.textContent, /Estado actual: Nueva/)
    assert.equal(document.activeElement, detail.querySelector('h2[tabindex="-1"]'))
    assert.ok(calls.includes('/reviews/102'))
  } finally {
    apiClient.get = original
    if (root) await unmount()
  }
})

test('representa vacío, carga y paginación sin confundir el contador con no leídos', async () => {
  const original = apiClient.get
  let mode = 'empty'
  apiClient.get = async (_url, options) => ({ data: mode === 'empty' ? { items: [], total: 0 } : {
    items: options.params.offset ? [{ ...notification, id: 6, review_id: 106 }] : Array.from({ length: 5 }, (_, index) => ({ ...notification, id: index + 1, review_id: 101 + index })), total: 6,
  } })
  try {
    await mount()
    await act(async () => { trigger().click() })
    assert.match(panel().textContent, /No hay avisos de prioridad alta/)
    mode = 'pages'
    await act(async () => { window.dispatchEvent(new window.Event('review-priority-saved')) })
    assert.equal(panel().querySelectorAll('a').length, 5)
    assert.equal(button('Avisos anteriores').disabled, true)
    await act(async () => { button('Avisos siguientes').click() })
    assert.equal(panel().querySelectorAll('a').length, 1)
    assert.equal(panel().querySelector('a').getAttribute('href'), '/reviews?review=106')
    assert.equal(button('Avisos siguientes').disabled, true)
    assert.equal(button('Avisos anteriores').disabled, false)
    assert.doesNotMatch(panel().textContent, /no leíd/)
  } finally {
    apiClient.get = original
    if (root) await unmount()
  }
})

test('presenta carga, oculta detalles de error y permite reintentar', async () => {
  const original = apiClient.get
  const pending = deferred()
  apiClient.get = () => pending.promise
  try {
    await mount()
    await act(async () => { trigger().click() })
    assert.match(panel().querySelector('[role="status"]').textContent, /Actualizando/)
    await act(async () => { pending.resolve({ data: { items: [], total: 0 } }); await pending.promise })
    apiClient.get = async () => { throw { response: { status: 500, data: { detail: 'private-detail' } } } }
    await act(async () => { window.dispatchEvent(new window.Event('review-priority-saved')) })
    assert.match(panel().querySelector('[role="alert"]').textContent, /No pudimos actualizar/)
    assert.doesNotMatch(panel().textContent, /private-detail/)
    apiClient.get = async () => ({ data: { items: [notification], total: 1 } })
    await act(async () => { button('Reintentar avisos').click() })
    assert.equal(panel().querySelector('[role="alert"]'), null)
    assert.match(panel().textContent, /Caso importante/)
    await act(async () => { document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true })) })
    assert.equal(panel(), null)
    assert.equal(document.activeElement, trigger())
  } finally {
    apiClient.get = original
    if (root) await unmount()
  }
})

test('cambiar de negocio cancela la espera y descarta datos anteriores', async () => {
  const original = apiClient.get
  const pending = deferred()
  let oldSignal
  let first = true
  apiClient.get = (_url, options) => {
    if (first) { first = false; oldSignal = options.signal; return pending.promise }
    return Promise.resolve({ data: { items: [{ ...notification, id: 20, review_id: 201, autor: 'Otro negocio' }], total: 1 } })
  }
  try {
    await mount()
    await act(async () => { changeUser({ ...user, id: 20, tenant_id: 20 }) })
    assert.equal(oldSignal.aborted, true)
    await act(async () => { pending.resolve({ data: { items: [notification], total: 1 } }); await pending.promise })
    await act(async () => { trigger().click() })
    assert.match(panel().textContent, /Otro negocio/)
    assert.doesNotMatch(panel().textContent, /Caso importante/)
  } finally {
    apiClient.get = original
    if (root) await unmount()
  }
})

test('una denegación borra los avisos anteriores y un rol general no consulta datos', async () => {
  const original = apiClient.get
  let calls = 0
  apiClient.get = async () => { calls += 1; return { data: { items: [notification], total: 1 } } }
  try {
    await mount()
    await act(async () => { trigger().click() })
    apiClient.get = async () => { throw { response: { status: 403 } } }
    await act(async () => { window.dispatchEvent(new window.Event('review-priority-saved')) })
    assert.doesNotMatch(panel().textContent, /Caso importante/)
    assert.match(panel().querySelector('[role="alert"]').textContent, /ya no tiene acceso/)
    await unmount()
    const previousCalls = calls
    await mount({ initialUser: { id: 3, tenant_id: null, rol: 'admin_general' } })
    assert.equal(trigger(), null)
    assert.equal(calls, previousCalls)
  } finally {
    apiClient.get = original
    if (root) await unmount()
  }
})
