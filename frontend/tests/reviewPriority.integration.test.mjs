import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import React, { act, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { renderToStaticMarkup } from 'react-dom/server'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'

let dom
let server
let ReviewDetail
let ReviewTable
let apiClient
let service
let utils
let root
let container
let selectReview

const review = {
  id: 101, tenant_id: 10, autor: 'Ana', contenido: 'Me cobraron dos veces y nadie responde.',
  fecha: '2026-10-25T12:00:00', fuente: 'manual', puntuacion: 2,
  categoria: 'Queja', estado: 'nueva', prioridad: null, resumen: 'Resumen previo', tema: 'Precio',
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
  ;({ default: ReviewTable } = await server.ssrLoadModule('/src/components/reviews/ReviewTable.jsx'))
  ;({ default: apiClient } = await server.ssrLoadModule('/src/services/apiClient.js'))
  service = await server.ssrLoadModule('/src/services/reviewService.js')
  utils = await server.ssrLoadModule('/src/utils/reviewPriority.js')
})

after(async () => {
  await server?.close()
  dom?.window.close()
  for (const name of ['window', 'document', 'navigator', 'HTMLElement', 'localStorage', 'IS_REACT_ACT_ENVIRONMENT']) {
    delete globalThis[name]
  }
})

function Harness({ initialReview, canPrioritize }) {
  const [current, setCurrent] = useState(initialReview)
  selectReview = setCurrent
  return React.createElement(ReviewDetail, {
    review: current, canClassify: true, onClassified: setCurrent,
    canDetectTopic: true, onTopicDetected: setCurrent, onSummarySaved: setCurrent,
    canPrioritize, onPrioritized: (result) => setCurrent((previous) => utils.mergePriority(previous, result)),
    onEdit: () => {}, onStatusConfirm: () => {},
  })
}

async function mount(initialReview = review, canPrioritize = true) {
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  await act(async () => { root.render(React.createElement(Harness, { initialReview, canPrioritize })) })
  await act(async () => { button('Prioridad').click() })
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
  return container.querySelector('[aria-label="Prioridad de atención"]')
}

function deferred() {
  let resolve
  const promise = new Promise((accept) => { resolve = accept })
  return { promise, resolve }
}

test('envía POST autenticado sin prioridad manual, contenido ni tenant', async () => {
  const previous = apiClient.defaults.adapter
  localStorage.setItem('gestor_reviews_access_token', 'synthetic-token')
  let request
  apiClient.defaults.adapter = async (config) => {
    request = config
    return { data: { ...review, prioridad: 'Alta' }, status: 200, statusText: 'OK', headers: {}, config }
  }
  try {
    const controller = new AbortController()
    const result = await service.prioritizeReview(101, { signal: controller.signal, tenant_id: 20, prioridad: 'Baja' })
    assert.equal(result.prioridad, 'Alta')
    assert.equal(request.url, '/reviews/101/prioridad')
    assert.equal(request.method, 'post')
    assert.equal(request.headers.Authorization, 'Bearer synthetic-token')
    assert.equal(request.data, undefined)
    assert.equal(request.params, undefined)
    assert.equal(request.signal, controller.signal)
    assert.equal(request.timeout, 150000)
  } finally {
    apiClient.defaults.adapter = previous
    localStorage.clear()
  }
})

test('genera, muestra carga, evita doble envío y conserva la operación al cambiar pestañas', async () => {
  const previous = apiClient.post
  const pending = deferred()
  const calls = []
  apiClient.post = (...args) => { calls.push(args); return pending.promise }
  try {
    await mount()
    assert.match(panel().textContent, /Sin determinar/)
    await act(async () => { button('Determinar prioridad').click() })
    await act(async () => { button('Determinando prioridad…').click() })
    assert.equal(calls.length, 1)
    assert.equal(panel().getAttribute('aria-busy'), 'true')
    assert.equal(button('Determinando prioridad…').disabled, true)
    assert.equal(button('Clasificar con IA'), undefined)
    assert.equal(button('Reclasificar con IA').disabled, true)
    assert.equal(button('Actualizar tema').disabled, true)
    assert.equal(button('Regenerar resumen').disabled, true)
    assert.equal(button('Editar review').disabled, true)
    assert.equal(container.querySelector('#review-status').disabled, true)
    await act(async () => { button('Tema').click() })
    assert.equal(calls[0][2].signal.aborted, false)
    assert.ok(button('Prioridad').querySelector('[aria-label="En proceso"]'))
    await act(async () => {
      pending.resolve({ data: { ...review, prioridad: 'Alta', estado: 'atendida', resumen: 'Respuesta vieja' } })
      await pending.promise
    })
    await act(async () => { button('Prioridad').click() })
    assert.match(panel().textContent, /Prioridad actualizada y guardada/)
    assert.match(panel().textContent, /Solo lectura/)
    assert.equal(panel().getAttribute('aria-busy'), 'false')
    assert.equal(container.querySelector('#review-status').value, 'nueva')
    assert.match(container.textContent, /Resumen previo/)
    assert.equal(button('Editar review').disabled, false)
    assert.equal(button('Prioridad').querySelector('[aria-label="En proceso"]'), null)
    assert.ok(panel().querySelector('[aria-label="Prioridad: Alta"] svg'))
  } finally {
    apiClient.post = previous
    if (root) await unmount()
  }
})

test('regenera y muestra la prioridad persistida al volver a cargar datos', async () => {
  const previous = apiClient.post
  apiClient.post = async () => ({ data: { ...review, prioridad: 'Media' } })
  try {
    await mount({ ...review, prioridad: 'Alta' })
    await act(async () => { button('Actualizar prioridad').click() })
    assert.ok(panel().querySelector('[aria-label="Prioridad: Media"]'))
    await unmount()
    await mount({ ...review, prioridad: 'Media' })
    assert.ok(panel().querySelector('[aria-label="Prioridad: Media"]'))
    assert.ok(button('Actualizar prioridad'))
    assert.equal(container.querySelector('[name="prioridad"]'), null)
  } finally {
    apiClient.post = previous
    if (root) await unmount()
  }
})

test('traduce errores, conserva el valor anterior y permite reintentar sin revelar detalles', async () => {
  const previous = apiClient.post
  const cases = [
    [401, /sesión expiró/], [403, /No tienes permiso/], [404, /ya no está disponible/],
    [409, /contenido cambió/], [422, /no permite determinar/], [500, /No fue posible guardar/],
    [502, /prioridad válida/], [503, /no está disponible/], [504, /tardó demasiado/],
  ]
  try {
    for (const [status, message] of cases) {
      let calls = 0
      apiClient.post = async () => { calls += 1; throw { response: { status, data: { detail: 'private-detail' } } } }
      await mount({ ...review, prioridad: 'Media' })
      await act(async () => { button('Actualizar prioridad').click() })
      assert.equal(calls, 1)
      assert.match(panel().querySelector('[role="alert"]').textContent, message)
      assert.ok(panel().querySelector('[aria-label="Prioridad: Media"]'))
      assert.doesNotMatch(panel().textContent, /private-detail|actualizada y guardada/)
      assert.equal(button('Actualizar prioridad').disabled, false)
      await unmount()
    }
  } finally {
    apiClient.post = previous
    if (root) await unmount()
  }
})

test('cancela y descarta respuestas tardías al cambiar de review, negocio o contenido', async () => {
  const previous = apiClient.post
  try {
    for (const change of [{ id: 202 }, { tenant_id: 20 }, { contenido: 'Texto corregido' }]) {
      const pending = deferred()
      let signal
      apiClient.post = (_url, _body, options) => { signal = options.signal; return pending.promise }
      await mount()
      await act(async () => { button('Determinar prioridad').click() })
      await act(async () => { selectReview({ ...review, ...change, prioridad: 'Baja' }) })
      assert.equal(signal.aborted, true)
      await act(async () => { pending.resolve({ data: { ...review, prioridad: 'Alta' } }); await pending.promise })
      assert.ok(panel().querySelector('[aria-label="Prioridad: Baja"]'))
      assert.doesNotMatch(panel().textContent, /actualizada y guardada/)
      await unmount()
    }
  } finally {
    apiClient.post = previous
    if (root) await unmount()
  }
})

test('rechaza respuestas de otra review o con una prioridad fuera del contrato', async () => {
  const previous = apiClient.post
  try {
    for (const change of [{ id: 202 }, { tenant_id: 20 }, { contenido: 'Texto editado' }, { prioridad: 'alta' }, { prioridad: null }]) {
      apiClient.post = async () => ({ data: { ...review, prioridad: 'Alta', ...change } })
      await mount({ ...review, prioridad: 'Media' })
      await act(async () => { button('Actualizar prioridad').click() })
      assert.ok(panel().querySelector('[aria-label="Prioridad: Media"]'))
      assert.match(panel().querySelector('[role="alert"]').textContent, /No pudimos confirmar/)
      await unmount()
    }
  } finally {
    apiClient.post = previous
    if (root) await unmount()
  }
})

test('solo cambia prioridad en respuestas coincidentes y exige una sesión de negocio', () => {
  for (const prioridad of ['Baja', 'Media', 'Alta']) {
    assert.deepEqual(utils.mergePriority(review, { ...review, prioridad, estado: 'atendida', categoria: 'Consulta' }), { ...review, prioridad })
  }
  for (const change of [{ id: 202 }, { tenant_id: 20 }, { contenido: 'Otro' }, { prioridad: 'Urgente' }]) {
    assert.equal(utils.mergePriority(review, { ...review, prioridad: 'Alta', ...change }), review)
  }
  assert.equal(utils.mergePriority(null, review), null)
  for (const rol of ['usuario_negocio', 'admin_tenant']) {
    assert.equal(utils.canPrioritizeReview({ access_token: 'token', user: { rol, tenant_id: 10 } }), true)
  }
  for (const session of [null, {}, { user: { rol: 'admin_tenant', tenant_id: 10 } },
    { access_token: 'token', user: { rol: 'admin_general', tenant_id: 10 } },
    { access_token: 'token', user: { rol: 'admin_tenant', tenant_id: null } }]) {
    assert.equal(utils.canPrioritizeReview(session), false)
  }
})

test('sin permiso muestra el valor de solo lectura y oculta la acción', async () => {
  try {
    await mount({ ...review, prioridad: 'Alta' }, false)
    assert.ok(panel().querySelector('[aria-label="Prioridad: Alta"]'))
    assert.equal(button('Actualizar prioridad'), undefined)
    assert.equal(button('Determinar prioridad'), undefined)
    assert.equal(container.querySelector('[name="prioridad"]'), null)
  } finally {
    if (root) await unmount()
  }
})

test('la tabla identifica Alta mediante texto e icono sin agregar otra columna', () => {
  const html = renderToStaticMarkup(React.createElement(ReviewTable, {
    reviews: [{ ...review, prioridad: 'Alta' }], selectedReviewId: review.id, onSelect: () => {},
  }))
  const parsed = new JSDOM(html).window.document
  const badge = parsed.querySelector('[aria-label="Prioridad: Alta"]')
  assert.match(badge.textContent, /Alta/)
  assert.ok(badge.querySelector('svg[aria-hidden="true"]'))
  assert.equal(parsed.querySelectorAll('th').length, 6)
})
