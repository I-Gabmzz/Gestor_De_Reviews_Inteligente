import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import React, { act, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'

let dom
let server
let ReviewDetail
let ReviewsPage
let apiClient
let service
let utils
let root
let container
let selectReview
let useSuggestedResponse
let hookState

const review = {
  id: 101, tenant_id: 10, autor: 'Ana', contenido: 'Me cobraron dos veces y nadie responde.',
  fecha: '2026-10-25T12:00:00', fuente: 'manual', puntuacion: 2,
  categoria: 'Queja', estado: 'nueva', prioridad: 'Alta', resumen: 'Resumen previo', tema: 'Precio',
}

before(async () => {
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.navigator = dom.window.navigator
  globalThis.HTMLElement = dom.window.HTMLElement
  globalThis.localStorage = dom.window.localStorage
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  server = await createServer({ server: { middlewareMode: true, hmr: false }, optimizeDeps: { noDiscovery: true, include: [] }, appType: 'custom' })
  ;({ default: ReviewDetail } = await server.ssrLoadModule('/src/components/reviews/ReviewDetail.jsx'))
  ;({ default: ReviewsPage } = await server.ssrLoadModule('/src/pages/ReviewsPage.jsx'))
  ;({ default: apiClient } = await server.ssrLoadModule('/src/services/apiClient.js'))
  service = await server.ssrLoadModule('/src/services/reviewService.js')
  utils = await server.ssrLoadModule('/src/utils/reviewSuggestedResponse.js')
  ;({ default: useSuggestedResponse } = await server.ssrLoadModule('/src/hooks/useSuggestedResponse.js'))
})

after(async () => {
  await server?.close()
  dom?.window.close()
  for (const name of ['window', 'document', 'navigator', 'HTMLElement', 'localStorage', 'IS_REACT_ACT_ENVIRONMENT']) {
    delete globalThis[name]
  }
})

function Harness({ initialReview, canSuggest }) {
  const [current, setCurrent] = useState(initialReview)
  selectReview = setCurrent
  return React.createElement(ReviewDetail, {
    review: current, canPrioritize: true, canClassify: true, onClassified: setCurrent,
    canDetectTopic: true, onTopicDetected: setCurrent, onSummarySaved: setCurrent,
    canSuggest, onSuggested: (result) => setCurrent((previous) => utils.mergeSuggestedResponse(previous, result)),
    onReload: () => setCurrent((previous) => ({ ...previous, respuesta_sugerida: "Vigente tras recargar." })),
    onEdit: () => {}, onStatusConfirm: () => {},
  })
}

async function mount(initialReview = review, canSuggest = true) {
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  await act(async () => { root.render(React.createElement(Harness, { initialReview, canSuggest })) })
  await act(async () => { button('Respuesta sugerida').click() })
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

function panel() {
  return container.querySelector('[aria-label="Respuesta sugerida"]')
}

function deferred() {
  let resolve
  const promise = new Promise((accept) => { resolve = accept })
  return { promise, resolve }
}

async function mountHook(initialReview = review, onSuggested = () => {}) {
  function HookHarness() {
    const [current, setCurrent] = useState(initialReview)
    selectReview = setCurrent
    hookState = useSuggestedResponse(current, onSuggested)
    return null
  }
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  await act(async () => root.render(React.createElement(React.StrictMode, null, React.createElement(HookHarness))))
}

test('A → B → A descarta carga cancelada y permite generar de nuevo', async () => {
  const original = apiClient.post, old = deferred()
  let calls = 0, oldSignal
  apiClient.post = (_url, _body, options) => {
    calls++
    if (calls === 1) { oldSignal = options.signal; return old.promise }
    return Promise.resolve({ data: { ...review, respuesta_sugerida: 'Generación nueva.' } })
  }
  try {
    await mount()
    await act(async () => button('Generar sugerencia').click())
    await act(async () => selectReview({ ...review, id: 202 }))
    await act(async () => selectReview({ ...review }))
    assert.equal(oldSignal.aborted, true)
    assert.equal(panel().getAttribute('aria-busy'), 'false')
    assert.equal(button('Generar sugerencia').disabled, false)
    assert.equal(button('Editar review').disabled, false)
    await act(async () => button('Generar sugerencia').click())
    await act(async () => { old.resolve({ data: { ...review, respuesta_sugerida: 'Obsoleta.' } }); await old.promise })
    assert.equal(calls, 2)
    assert.match(panel().textContent, /Generación nueva/)
    assert.doesNotMatch(panel().textContent, /Obsoleta/)
  } finally { apiClient.post = original; await unmount() }
})

test('rechazo tardío tras A → B → A no altera una nueva petición activa', async () => {
  const original = apiClient.post
  let rejectOld, calls = 0
  const old = new Promise((_resolve, reject) => { rejectOld = reject })
  const fresh = deferred(), results = []
  apiClient.post = () => ++calls === 1 ? old : fresh.promise
  try {
    await mountHook(review, (result) => results.push(result))
    await act(async () => { void hookState.generate() })
    await act(async () => selectReview({ ...review, id: 202 }))
    await act(async () => selectReview({ ...review }))
    assert.equal(hookState.isGenerating, false)
    await act(async () => { void hookState.generate() })
    await act(async () => rejectOld({ response: { status: 503 } }))
    assert.equal(hookState.isGenerating, true)
    assert.equal(hookState.error, '')
    await act(async () => fresh.resolve({ data: { ...review, respuesta_sugerida: 'Resultado nuevo.' } }))
    assert.equal(hookState.isGenerating, false)
    assert.equal(hookState.succeeded, true)
    assert.equal(results.length, 1)
  } finally { apiClient.post = original; await unmount() }
})

for (const status of [409, 503]) {
  test(`A → B → A descarta error anterior ${status} sin borrar el borrador persistido`, async () => {
    const original = apiClient.post
    apiClient.post = async () => { throw { response: { status } } }
    try {
      await mount({ ...review, respuesta_sugerida: 'Borrador persistido.' })
      await act(async () => button('Regenerar sugerencia').click())
      assert.ok(panel().querySelector('[role="alert"]'))
      await act(async () => selectReview({ ...review, id: 202 }))
      await act(async () => selectReview({ ...review, respuesta_sugerida: 'Borrador vigente recuperado.' }))
      assert.equal(panel().querySelector('[role="alert"]'), null)
      assert.equal(button('Recargar información'), undefined)
      assert.equal(button('Regenerar sugerencia').disabled, false)
      assert.match(panel().textContent, /Borrador vigente recuperado/)
      apiClient.post = async () => ({ data: { ...review, respuesta_sugerida: 'Regeneración válida.' } })
      await act(async () => button('Regenerar sugerencia').click())
      assert.match(panel().textContent, /Regeneración válida/)
    } finally { apiClient.post = original; await unmount() }
  })
}

test('éxito de visita anterior no reaparece ni reemplaza el valor persistido al volver', async () => {
  const original = apiClient.post
  apiClient.post = async () => ({ data: { ...review, respuesta_sugerida: 'Éxito anterior.' } })
  try {
    await mount()
    await act(async () => button('Generar sugerencia').click())
    assert.match(panel().textContent, /generada y guardada/)
    await act(async () => selectReview({ ...review, id: 202 }))
    await act(async () => selectReview({ ...review, respuesta_sugerida: 'Persistido más reciente.' }))
    assert.match(panel().textContent, /Persistido más reciente/)
    assert.doesNotMatch(panel().textContent, /Éxito anterior|generada y guardada/)
  } finally { apiClient.post = original; await unmount() }
})

for (const [name, change] of [['contenido', { contenido: 'Contenido distinto.' }], ['tenant', { tenant_id: 20 }]]) {
  test(`ciclo de ${name} cancela la petición y no recupera estados al retornar`, async () => {
    const original = apiClient.post, pending = deferred(), results = []
    let signal
    apiClient.post = (_url, _body, options) => { signal = options.signal; return pending.promise }
    try {
      await mountHook(review, (result) => results.push(result))
      await act(async () => { void hookState.generate() })
      await act(async () => selectReview({ ...review, ...change }))
      assert.equal(signal.aborted, true)
      await act(async () => selectReview({ ...review }))
      await act(async () => pending.resolve({ data: { ...review, respuesta_sugerida: 'Obsoleta.' } }))
      assert.equal(hookState.isGenerating, false)
      assert.equal(hookState.error, '')
      assert.equal(hookState.conflict, false)
      assert.equal(hookState.succeeded, false)
      assert.equal(results.length, 0)
    } finally { apiClient.post = original; await unmount() }
  })
}

test('doble clic al regenerar conserva el borrador y realiza una sola solicitud', async () => {
  const original = apiClient.post, pending = deferred()
  let calls = 0
  apiClient.post = () => { calls++; return pending.promise }
  try {
    await mount({ ...review, respuesta_sugerida: 'Persistido.' })
    await act(async () => { button('Regenerar sugerencia').click(); button('Regenerar sugerencia')?.click() })
    assert.equal(calls, 1)
    assert.match(panel().textContent, /Persistido/)
    await act(async () => pending.resolve({ data: { ...review, respuesta_sugerida: 'Regenerado.' } }))
    assert.match(panel().textContent, /Regenerado/)
  } finally { apiClient.post = original; await unmount() }
})

test('desmontaje cancela y no notifica resultados de una promesa que ignora abort', async () => {
  const original = apiClient.post, pending = deferred(), results = []
  let signal
  apiClient.post = (_url, _body, options) => { signal = options.signal; return pending.promise }
  try {
    await mountHook(review, (result) => results.push(result))
    await act(async () => { void hookState.generate() })
    await unmount()
    assert.equal(signal.aborted, true)
    await act(async () => pending.resolve({ data: { ...review, respuesta_sugerida: 'Tardía.' } }))
    assert.equal(results.length, 0)
  } finally { apiClient.post = original; if (root) await unmount() }
})

test('POST autenticado sin body, tenant ni contenido y con cancelación', async () => {
  const original = apiClient.defaults.adapter
  localStorage.setItem('gestor_reviews_access_token', 'synthetic-token')
  let request
  apiClient.defaults.adapter = async (config) => {
    request = config
    return { data: { ...review, respuesta_sugerida: 'Gracias por tu comentario.' }, status: 200, headers: {}, config }
  }
  try {
    const controller = new AbortController()
    await service.generateSuggestedResponse(101, { signal: controller.signal, tenant_id: 99, contenido: 'No enviar' })
    assert.equal(request.method, 'post')
    assert.equal(request.url, '/reviews/101/respuesta-sugerida')
    assert.equal(request.data, undefined)
    assert.equal(request.params, undefined)
    assert.equal(request.headers.Authorization, 'Bearer synthetic-token')
    assert.equal(request.signal, controller.signal)
  } finally { apiClient.defaults.adapter = original; localStorage.clear() }
})

test('borrador persistido es texto de solo lectura sin acciones de publicación', async () => {
  try {
    await mount({ ...review, respuesta_sugerida: '<script>texto ficticio</script>' })
    assert.match(panel().textContent, /Borrador sugerido por IA — no enviado/)
    assert.match(panel().textContent, /<script>texto ficticio<\/script>/)
    assert.equal(panel().querySelector('script, textarea, input, [contenteditable]'), null)
    assert.equal(button('Publicar'), undefined)
    assert.equal(button('Enviar'), undefined)
    assert.ok(button('Regenerar sugerencia'))
    for (const tab of ['Clasificación', 'Resumen', 'Tema', 'Prioridad']) assert.ok(button(tab))
  } finally { await unmount() }
})

test('genera y regenera sin sobrescribir otras salidas ni estado', async () => {
  const original = apiClient.post
  let calls = 0
  apiClient.post = async () => ({ data: { ...review, estado: 'atendida', categoria: 'Consulta', resumen: 'Antiguo', tema: 'Otro', prioridad: 'Baja', respuesta_sugerida: `Borrador ${++calls}` } })
  try {
    await mount()
    assert.match(panel().textContent, /Todavía no hay/)
    await act(async () => button('Generar sugerencia').click())
    assert.match(panel().textContent, /Borrador 1/)
    await act(async () => button('Regenerar sugerencia').click())
    assert.match(panel().textContent, /Borrador 2/)
    assert.equal(container.querySelector('#review-status').value, 'nueva')
    assert.match(container.textContent, /Resumen previo/)
    assert.match(container.textContent, /Precio/)
    assert.ok(container.querySelector('[aria-label="Prioridad: Alta"]'))
    assert.match(container.textContent, /Queja/)
  } finally { apiClient.post = original; await unmount() }
})

test('loading bloquea duplicados y operaciones concurrentes de la vista', async () => {
  const original = apiClient.post, pending = deferred()
  let calls = 0
  apiClient.post = () => { calls++; return pending.promise }
  try {
    await mount()
    await act(async () => button('Generar sugerencia').click())
    await act(async () => button('Generando sugerencia…').click())
    assert.equal(calls, 1)
    assert.equal(panel().getAttribute('aria-busy'), 'true')
    assert.equal(button('Editar review').disabled, true)
    assert.equal(button('Actualizar prioridad').disabled, true)
    assert.equal(button('Regenerar resumen').disabled, true)
    assert.equal(button('Actualizar tema').disabled, true)
    await act(async () => { pending.resolve({ data: { ...review, respuesta_sugerida: 'Gracias.' } }); await pending.promise })
    assert.equal(panel().getAttribute('aria-busy'), 'false')
  } finally { apiClient.post = original; await unmount() }
})

test('errores preservan borrador y 409 permite recargar antes de regenerar', async () => {
  const original = apiClient.post
  try {
    for (const status of [401, 403, 404, 409, 422, 500, 502, 503, 504]) {
      apiClient.post = async () => { throw { response: { status, data: { detail: 'private-detail' } } } }
      await mount({ ...review, respuesta_sugerida: 'Borrador previo.' })
      await act(async () => button('Regenerar sugerencia').click())
      assert.ok(panel().querySelector('[role="alert"]'))
      assert.match(panel().textContent, /Borrador previo/)
      assert.doesNotMatch(panel().textContent, /private-detail|generada y guardada/)
      if (status === 409) {
        assert.equal(button('Regenerar sugerencia').disabled, true)
        await act(async () => button('Recargar información').click())
        assert.match(panel().textContent, /Vigente tras recargar/)
        assert.equal(button('Regenerar sugerencia').disabled, false)
      }
      await unmount()
    }
  } finally { apiClient.post = original; if (root) await unmount() }
})

test('cambio de selección, tenant o contenido cancela y descarta la respuesta tardía', async () => {
  const original = apiClient.post
  try {
    for (const change of [{ id: 202 }, { tenant_id: 20 }, { contenido: 'Review editada' }]) {
      const pending = deferred()
      let signal
      apiClient.post = (_url, _body, options) => { signal = options.signal; return pending.promise }
      await mount()
      await act(async () => button('Generar sugerencia').click())
      await act(async () => selectReview({ ...review, ...change, respuesta_sugerida: 'Resultado vigente.' }))
      assert.equal(signal.aborted, true)
      await act(async () => { pending.resolve({ data: { ...review, respuesta_sugerida: 'Resultado obsoleto.' } }); await pending.promise })
      assert.match(panel().textContent, /Resultado vigente/)
      assert.doesNotMatch(panel().textContent, /Resultado obsoleto|generada y guardada/)
      await unmount()
    }
  } finally { apiClient.post = original; if (root) await unmount() }
})

test('rechaza respuesta ajena, vacía o inválida sin modificar el resultado', () => {
  for (const changes of [{ id: 202 }, { tenant_id: 20 }, { contenido: 'Otro' }, { respuesta_sugerida: '' }, { respuesta_sugerida: ' ' }, { respuesta_sugerida: null }]) {
    assert.equal(utils.mergeSuggestedResponse(review, { ...review, respuesta_sugerida: 'Sugerencia', ...changes }), review)
  }
})

test('sin permiso solo muestra el borrador sin control de generación', async () => {
  try {
    await mount({ ...review, respuesta_sugerida: 'Persistido.' }, false)
    assert.match(panel().textContent, /Persistido/)
    assert.equal(button('Regenerar sugerencia'), undefined)
  } finally { await unmount() }
})

test('ReviewsPage mantiene selección por URL y actualiza solo el borrador', async () => {
  const original = apiClient.defaults.adapter
  const requests = []
  localStorage.setItem('gestor_reviews_access_token', 'synthetic-token')
  localStorage.setItem('gestor_reviews_user', JSON.stringify({ id: 1, tenant_id: 10, rol: 'usuario_negocio' }))
  apiClient.defaults.adapter = async (config) => {
    requests.push(config)
    const data = config.method === 'post'
      ? { ...review, respuesta_sugerida: 'Borrador desde página.', prioridad: 'Baja', estado: 'atendida' }
      : config.url === '/reviews' ? { items: [review], total: 1 } : review
    return { data, status: 200, headers: {}, config }
  }
  try {
    container = document.createElement('div'); document.body.append(container); root = createRoot(container)
    await act(async () => root.render(React.createElement(MemoryRouter, { initialEntries: ['/reviews?review=101'], future: { v7_startTransition: true, v7_relativeSplatPath: true } }, React.createElement(ReviewsPage))))
    await act(async () => button('Respuesta sugerida').click())
    await act(async () => button('Generar sugerencia').click())
    assert.match(panel().textContent, /Borrador desde página/)
    assert.equal(container.querySelector('#review-status').value, 'nueva')
    assert.ok(container.querySelector('[aria-label="Prioridad: Alta"]'))
    assert.ok(button('Exportar CSV'))
    assert.equal(requests.filter((request) => request.method === 'post').length, 1)
    assert.ok(requests.some((request) => request.url === '/reviews/101'))
    const current = { ...review, respuesta_sugerida: 'Sugerencia vigente del servidor.' }
    apiClient.defaults.adapter = async (config) => {
      if (config.method === 'post') throw { response: { status: 409 } }
      return { data: config.url === '/reviews' ? { items: [current], total: 1 } : current, status: 200, headers: {}, config }
    }
    await act(async () => button('Regenerar sugerencia').click())
    assert.ok(button('Recargar información'))
    await act(async () => button('Recargar información').click())
    assert.match(panel().textContent, /Sugerencia vigente del servidor/)
    assert.equal(button('Regenerar sugerencia').disabled, false)
  } finally { apiClient.defaults.adapter = original; await unmount(); localStorage.clear() }
})
