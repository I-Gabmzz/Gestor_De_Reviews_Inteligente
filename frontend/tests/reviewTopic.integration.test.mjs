import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import React, { useState } from 'react'
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'

let dom
let server
let ReviewDetail
let apiClient
let detectReviewTopic
let root
let container
let chooseReview

const baseReview = {
  id: 101, tenant_id: 10, autor: 'Ana', fecha: '2026-10-19T12:00:00',
  contenido: 'El personal fue amable.', puntuacion: 5, estado: 'nueva',
  categoria: 'Felicitación', fuente: 'manual', prioridad: 'Alta', tema: null,
}

before(async () => {
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.navigator = dom.window.navigator
  globalThis.HTMLElement = dom.window.HTMLElement
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  globalThis.localStorage = dom.window.localStorage
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
  ;({ default: ReviewDetail } = await server.ssrLoadModule('/src/components/reviews/ReviewDetail.jsx'))
  ;({ default: apiClient } = await server.ssrLoadModule('/src/services/apiClient.js'))
  ;({ detectReviewTopic } = await server.ssrLoadModule('/src/services/reviewService.js'))
})

after(async () => {
  await server?.close()
  dom?.window.close()
  for (const name of ['window', 'document', 'navigator', 'HTMLElement', 'IS_REACT_ACT_ENVIRONMENT', 'localStorage']) {
    delete globalThis[name]
  }
})

function Harness({ initialReview }) {
  const [review, setReview] = useState(initialReview)
  chooseReview = setReview
  return React.createElement(ReviewDetail, {
    review, canDetectTopic: true, onTopicDetected: setReview,
    onEdit: () => {}, onStatusConfirm: () => {},
  })
}

async function mount(review = baseReview) {
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  await act(async () => { root.render(React.createElement(Harness, { initialReview: review })) })
}

async function unmount() {
  await act(async () => { root?.unmount() })
  container?.remove()
  root = null
  container = null
}

function button(label) {
  return [...container.querySelectorAll('button')].find((item) => item.textContent.trim() === label)
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((accept, fail) => { resolve = accept; reject = fail })
  return { promise, resolve, reject }
}

test('el cliente envía POST autenticado sin datos del tenant y recibe ReviewRead.tema', async () => {
  localStorage.setItem('gestor_reviews_access_token', 'token-de-prueba')
  const adapter = apiClient.defaults.adapter
  let request
  apiClient.defaults.adapter = async (config) => {
    request = config
    return { data: { ...baseReview, tema: 'Servicio' }, status: 200, statusText: 'OK', headers: {}, config }
  }
  try {
    const response = await detectReviewTopic(baseReview.id)
    assert.equal(request.method, 'post')
    assert.equal(request.url, '/reviews/101/tema')
    assert.equal(request.data, undefined)
    assert.equal(request.headers.Authorization, 'Bearer token-de-prueba')
    assert.equal(response.tema, 'Servicio')
  } finally {
    apiClient.defaults.adapter = adapter
    localStorage.clear()
  }
})

test('muestra tema persistido tras cargar datos, detecta, espera y regenera', async () => {
  const previous = apiClient.post
  const first = deferred()
  const second = deferred()
  const calls = []
  apiClient.post = (...args) => { calls.push(args); return calls.length === 1 ? first.promise : second.promise }
  try {
    await mount()
    assert.match(container.textContent, /Aún no se ha detectado un tema/)
    await act(async () => { button('Detectar tema').click() })
    assert.equal(button('Detectando tema…').disabled, true)
    assert.match(container.querySelector('[role="status"]').textContent, /Analizando/)
    assert.equal(calls[0][0], '/reviews/101/tema')
    assert.equal(calls[0][1], undefined)
    await act(async () => { first.resolve({ data: { ...baseReview, tema: 'Atención' } }); await first.promise })
    assert.match(container.textContent, /Atención/)
    assert.match(container.textContent, /Generado por IA/)
    await act(async () => { button('Detectar tema nuevamente').click() })
    await act(async () => { second.resolve({ data: { ...baseReview, tema: 'Servicio' } }); await second.promise })
    assert.match(container.textContent, /Servicio/)
    await unmount()
    await mount({ ...baseReview, tema: 'Servicio' })
    assert.match(container.textContent, /Servicio/)
    assert.ok(button('Detectar tema nuevamente'))
  } finally {
    apiClient.post = previous
    if (root) await unmount()
  }
})

test('presenta errores HTTP y conserva el tema anterior', async () => {
  const previous = apiClient.post
  const cases = [
    [401, /sesión expiró/], [403, /No tienes permiso/], [404, /ya no está disponible/],
    [409, /cambió durante el análisis/], [422, /único tema/], [502, /tema válido/],
    [503, /no está disponible/], [504, /tardó demasiado/],
  ]
  try {
    for (const [status, message] of cases) {
      apiClient.post = async () => { throw { response: { status } } }
      await mount({ ...baseReview, tema: 'Precio' })
      await act(async () => { button('Detectar tema nuevamente').click() })
      assert.match(container.querySelector('[role="alert"]').textContent, message)
      assert.match(container.querySelector('[aria-label="Tema principal"]').textContent, /Precio/)
      await unmount()
    }
  } finally {
    apiClient.post = previous
    if (root) await unmount()
  }
})

test('descarta la respuesta pendiente al cambiar de review y no mezcla resultados', async () => {
  const previous = apiClient.post
  const pending = deferred()
  let signal
  apiClient.post = (_url, _body, options) => { signal = options.signal; return pending.promise }
  const other = { ...baseReview, id: 202, tenant_id: 20, contenido: 'Otro comentario', tema: 'Producto' }
  try {
    await mount()
    await act(async () => { button('Detectar tema').click() })
    await act(async () => { chooseReview(other) })
    assert.equal(signal.aborted, true)
    await act(async () => { pending.resolve({ data: { ...baseReview, tema: 'Atención' } }); await pending.promise })
    assert.match(container.textContent, /Producto/)
    assert.doesNotMatch(container.querySelector('[aria-label="Tema principal"]').textContent, /Atención/)
  } finally {
    apiClient.post = previous
    if (root) await unmount()
  }
})
