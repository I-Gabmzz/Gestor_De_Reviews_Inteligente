import assert from 'node:assert/strict'
import { after, afterEach, before, test } from 'node:test'

import { JSDOM } from 'jsdom'
import { createServer } from 'vite'

let dom
let server
let React
let act
let createRoot
let ReviewSummary
let apiClient
let getReviewById
let root
let container

before(async () => {
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.navigator = dom.window.navigator
  globalThis.localStorage = dom.window.localStorage
  globalThis.IS_REACT_ACT_ENVIRONMENT = true

  React = await import('react')
  ;({ act } = React)
  ;({ createRoot } = await import('react-dom/client'))
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  ;({ default: ReviewSummary } = await server.ssrLoadModule('/src/components/reviews/ReviewSummary.jsx'))
  ;({ default: apiClient } = await server.ssrLoadModule('/src/services/apiClient.js'))
  ;({ getReviewById } = await server.ssrLoadModule('/src/services/reviewService.js'))
  localStorage.setItem('gestor_reviews_access_token', 'test-token')
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
  container = null
})

after(async () => {
  await server?.close()
  dom?.window.close()
  for (const name of ['window', 'document', 'navigator', 'localStorage', 'IS_REACT_ACT_ENVIRONMENT']) {
    delete globalThis[name]
  }
})

const original = { id: 101, contenido: 'La entrega tardó.', resumen: null }

function response(config, data) {
  return { data, status: 200, statusText: 'OK', headers: {}, config }
}

async function render(review, onSaved = () => {}) {
  if (!root) {
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
  }
  await act(async () => {
    root.render(React.createElement(ReviewSummary, { key: review.id, review, onSaved }))
  })
}

function button() {
  return container.querySelector('button')
}

function click() {
  act(() => button().dispatchEvent(new window.MouseEvent('click', { bubbles: true })))
}

test('genera, muestra, recupera y regenera usando el componente y servicio reales', async () => {
  const requests = []
  const stored = { ...original }
  const summaries = ['La entrega tardó.', 'Hubo demora en la entrega.']
  apiClient.defaults.adapter = async (config) => {
    requests.push(config)
    if (config.method === 'post' && config.url === '/reviews/101/resumen') {
      stored.resumen = summaries.shift()
      return response(config, { ...stored })
    }
    if (config.method === 'get' && config.url === '/reviews/101') {
      return response(config, { ...stored })
    }
    throw new Error(`Solicitud inesperada: ${config.method} ${config.url}`)
  }

  let latest
  const save = (updated) => { latest = updated }
  await render(original, save)
  assert.match(container.textContent, /todavía no tiene un resumen/)
  assert.match(button().textContent, /Generar resumen/)

  click()
  await act(async () => {})
  assert.equal(latest.resumen, 'La entrega tardó.')
  await render(latest, save)
  assert.match(container.textContent, /La entrega tardó/)
  assert.match(container.textContent, /Generado por IA/)
  assert.match(container.textContent, /Resumen generado y guardado/)
  assert.equal(requests[0].method, 'post')
  assert.equal(requests[0].url, '/reviews/101/resumen')
  assert.equal(requests[0].data, '{}')
  assert.equal(requests[0].headers.Authorization, 'Bearer test-token')

  const reloaded = await getReviewById(101)
  await render(reloaded, save)
  assert.match(container.textContent, /La entrega tardó/)
  assert.match(button().textContent, /Regenerar resumen/)

  click()
  await act(async () => {})
  await render(latest, save)
  assert.match(container.textContent, /Hubo demora en la entrega/)
  assert.equal(requests.filter((request) => request.method === 'post').length, 2)
})

test('muestra carga y bloquea solicitudes duplicadas', async () => {
  let resolveRequest
  let calls = 0
  apiClient.defaults.adapter = (config) => {
    calls += 1
    return new Promise((resolve) => { resolveRequest = () => resolve(response(config, { ...original, resumen: 'Resumen listo.' })) })
  }
  await render(original)
  click()
  await act(async () => {})
  assert.match(container.textContent, /Generando resumen/)
  assert.equal(button().disabled, true)
  click()
  assert.equal(calls, 1)
  await act(async () => resolveRequest())
  assert.equal(button().disabled, false)
})

for (const [status, message] of [
  [401, 'sesión expiró'], [403, 'No tienes permiso'], [404, 'ya no está disponible'],
  [422, 'no permite generar'], [503, 'no está disponible'], [504, 'tardó demasiado'],
]) {
  test(`muestra un error recuperable para HTTP ${status}`, async () => {
    apiClient.defaults.adapter = async (config) => {
      throw { response: { status, data: { detail: 'detalle privado' }, config } }
    }
    await render(original)
    click()
    await act(async () => {})
    assert.match(container.querySelector('[role="alert"]').textContent, new RegExp(message))
    assert.doesNotMatch(container.textContent, /detalle privado/)
    assert.equal(button().disabled, false)
    assert.doesNotMatch(container.textContent, /Resumen generado y guardado/)
  })
}

test('cambiar de review cancela la espera y no muestra el resumen anterior', async () => {
  let finishOldRequest
  let oldSignal
  apiClient.defaults.adapter = (config) => {
    oldSignal = config.signal
    return new Promise((resolve) => {
      finishOldRequest = () => resolve(response(config, { ...original, resumen: 'Resumen de la primera.' }))
    })
  }
  let saved = 0
  await render(original, () => { saved += 1 })
  click()
  const second = { id: 202, contenido: 'Otra review.', resumen: null }
  await render(second, () => { saved += 1 })
  assert.equal(oldSignal.aborted, true)
  await act(async () => finishOldRequest())
  assert.equal(saved, 0)
  assert.doesNotMatch(container.textContent, /Resumen de la primera/)
  assert.match(container.textContent, /todavía no tiene un resumen/)
})
