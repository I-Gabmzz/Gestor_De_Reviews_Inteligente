import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import React, { act, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'

let dom
let server
let ReviewDetail
let apiClient
let root
let container
let selectReview

const review = {
  id: 101, tenant_id: 10, autor: 'Ana', contenido: 'Mi pedido llegó tarde.',
  fecha: '2026-10-19T12:00:00', fuente: 'manual', puntuacion: 3,
  categoria: null, estado: 'nueva', prioridad: 'Alta', resumen: 'Resumen previo', tema: 'Servicio',
}

before(async () => {
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.navigator = dom.window.navigator
  globalThis.HTMLElement = dom.window.HTMLElement
  globalThis.localStorage = dom.window.localStorage
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
  ;({ default: ReviewDetail } = await server.ssrLoadModule('/src/components/reviews/ReviewDetail.jsx'))
  ;({ default: apiClient } = await server.ssrLoadModule('/src/services/apiClient.js'))
})

after(async () => {
  await server?.close()
  dom?.window.close()
  for (const name of ['window', 'document', 'navigator', 'HTMLElement', 'localStorage', 'IS_REACT_ACT_ENVIRONMENT']) {
    delete globalThis[name]
  }
})

function Harness({ initialReview }) {
  const [current, setCurrent] = useState(initialReview)
  selectReview = setCurrent
  return React.createElement(ReviewDetail, {
    review: current, canClassify: true, onClassified: setCurrent,
    canDetectTopic: true, onTopicDetected: setCurrent, onSummarySaved: setCurrent,
    onEdit: () => {}, onStatusConfirm: () => {},
  })
}

async function mount(initialReview = review) {
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  await act(async () => { root.render(React.createElement(Harness, { initialReview })) })
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
  const promise = new Promise((accept) => { resolve = accept })
  return { promise, resolve }
}

test('clasifica desde el detalle, muestra carga, conserva otros datos y regenera', async () => {
  const previous = apiClient.post
  const first = deferred()
  const second = deferred()
  const calls = []
  apiClient.post = (...args) => { calls.push(args); return calls.length === 1 ? first.promise : second.promise }
  try {
    await mount()
    assert.match(container.textContent, /Sin información/)
    await act(async () => { button('Clasificar con IA').click() })
    assert.equal(button('Clasificando…').disabled, true)
    assert.match(container.querySelector('[role="status"]').textContent, /Analizando/)
    assert.equal(calls.length, 1)
    assert.equal(calls[0][0], '/reviews/101/clasificacion')
    assert.equal(calls[0][1], undefined)
    await act(async () => { first.resolve({ data: { ...review, categoria: 'Queja' } }); await first.promise })
    assert.match(container.textContent, /Queja/)
    assert.match(container.textContent, /Categoría actualizada/)
    assert.match(container.textContent, /Categoría actualizada y guardada/)
    assert.match(container.textContent, /Mi pedido llegó tarde/)
    assert.match(container.textContent, /manual/)
    await act(async () => { button('Reclasificar con IA').click() })
    await act(async () => { second.resolve({ data: { ...review, categoria: 'Sugerencia' } }); await second.promise })
    assert.match(container.textContent, /Sugerencia/)
    await unmount()
    await mount({ ...review, categoria: 'Sugerencia' })
    assert.match(container.textContent, /Sugerencia/)
    assert.ok(button('Reclasificar con IA'))
  } finally {
    apiClient.post = previous
    if (root) await unmount()
  }
})

test('muestra errores HTTP y permite reintentar sin borrar la categoría previa', async () => {
  const previous = apiClient.post
  const cases = [
    [401, /sesión expiró/], [403, /No tienes permiso/], [404, /ya no está disponible/],
    [409, /contenido cambió/], [422, /no permite determinar/], [500, /No fue posible guardar/],
    [502, /respuesta no válida/], [503, /no está disponible/], [504, /tardó demasiado/],
  ]
  try {
    for (const [status, message] of cases) {
      let calls = 0
      apiClient.post = async () => { calls += 1; throw { response: { status, data: { detail: 'secreto-interno' } } } }
      await mount({ ...review, categoria: 'Consulta' })
      await act(async () => { button('Reclasificar con IA').click() })
      assert.equal(calls, 1)
      assert.match(container.querySelector('[role="alert"]').textContent, message)
      assert.doesNotMatch(container.textContent, /Categoría actualizada y guardada/)
      assert.doesNotMatch(container.textContent, /secreto-interno/)
      assert.match(container.textContent, /Consulta/)
      assert.equal(button('Reclasificar con IA').disabled, false)
      await unmount()
    }
    apiClient.post = async () => ({ data: { ...review, categoria: 'Felicitación' } })
    await mount({ ...review, categoria: 'Consulta' })
    await act(async () => { button('Reclasificar con IA').click() })
    assert.match(container.textContent, /Felicitación/)
    assert.equal(container.querySelector('[role="alert"]'), null)
  } finally {
    apiClient.post = previous
    if (root) await unmount()
  }
})

test('cambiar de review cancela la espera y descarta la respuesta tardía', async () => {
  const previous = apiClient.post
  const pending = deferred()
  let signal
  apiClient.post = (_url, _body, options) => { signal = options.signal; return pending.promise }
  const other = { ...review, id: 202, tenant_id: 20, contenido: 'Comentario distinto.', categoria: 'Consulta' }
  try {
    await mount()
    await act(async () => { button('Clasificar con IA').click() })
    await act(async () => { selectReview(other) })
    assert.equal(signal.aborted, true)
    await act(async () => { pending.resolve({ data: { ...review, categoria: 'Queja' } }); await pending.promise })
    assert.match(container.textContent, /Consulta/)
    assert.doesNotMatch(container.textContent, /Queja|Categoría actualizada/)
  } finally {
    apiClient.post = previous
    if (root) await unmount()
  }
})

test('rechaza respuestas de otra identidad, tenant, contenido o categoría', async () => {
  const previous = apiClient.post
  const variants = [
    { id: 202 }, { tenant_id: 20 }, { contenido: 'Texto cambiado' }, { categoria: 'Positiva' },
  ]
  try {
    for (const variant of variants) {
      apiClient.post = async () => ({ data: { ...review, categoria: 'Queja', ...variant } })
      await mount({ ...review, categoria: 'Consulta' })
      await act(async () => { button('Reclasificar con IA').click() })
      assert.match(container.textContent, /Consulta/)
      assert.match(container.querySelector('[role="alert"]').textContent, /No pudimos confirmar/)
      assert.doesNotMatch(container.textContent, /Categoría actualizada/)
      await unmount()
    }
  } finally {
    apiClient.post = previous
    if (root) await unmount()
  }
})

test('las pestañas muestran un solo panel y permiten navegar con teclado', async () => {
  try {
    await mount()
    const tabs = [...container.querySelectorAll('[role="tab"]')]
    assert.deepEqual(tabs.map((tab) => tab.textContent), ['Clasificación', 'Resumen', 'Tema'])
    for (const tab of tabs) {
      const panel = document.getElementById(tab.getAttribute('aria-controls'))
      assert.equal(panel.getAttribute('aria-labelledby'), tab.id)
    }
    assert.equal(container.querySelectorAll('[role="tabpanel"]:not([hidden])').length, 1)
    await act(async () => { tabs[0].dispatchEvent(new window.KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true })) })
    assert.equal(tabs[1].getAttribute('aria-selected'), 'true')
    assert.equal(document.activeElement, tabs[1])
    assert.equal(document.getElementById(tabs[1].getAttribute('aria-controls')).hidden, false)
    await act(async () => { tabs[1].dispatchEvent(new window.KeyboardEvent('keydown', { key: 'End', bubbles: true })) })
    assert.equal(tabs[2].getAttribute('aria-selected'), 'true')
    await act(async () => { tabs[2].dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Home', bubbles: true })) })
    assert.equal(tabs[0].getAttribute('aria-selected'), 'true')
    assert.equal(container.querySelectorAll('[role="tabpanel"]:not([hidden])').length, 1)
  } finally {
    if (root) await unmount()
  }
})

test('cambiar de pestaña conserva el resumen pendiente y bloquea otros análisis hasta guardar', async () => {
  const previous = apiClient.post
  const pending = deferred()
  let signal
  apiClient.post = (_url, _body, options) => { signal = options.signal; return pending.promise }
  try {
    await mount({ ...review, resumen: null })
    await act(async () => { button('Resumen').click() })
    await act(async () => { button('Generar resumen').click() })
    await act(async () => { button('Tema').click() })
    assert.equal(signal.aborted, false)
    assert.ok(button('Resumen').querySelector('[aria-label="En proceso"]'))
    assert.equal(button('Actualizar tema').disabled, true)
    assert.equal(button('Clasificar con IA').disabled, true)
    assert.equal(button('Editar review').disabled, true)
    await act(async () => { pending.resolve({ data: { ...review, resumen: 'El pedido llegó tarde.' } }); await pending.promise })
    assert.equal(button('Actualizar tema').disabled, false)
    await act(async () => { button('Resumen').click() })
    const selectedPanel = container.querySelector('[role="tabpanel"]:not([hidden])')
    assert.match(selectedPanel.textContent, /El pedido llegó tarde/)
    assert.match(selectedPanel.textContent, /Resumen generado y guardado/)
    assert.equal(button('Resumen').querySelector('[aria-label="En proceso"]'), null)
  } finally {
    apiClient.post = previous
    if (root) await unmount()
  }
})
