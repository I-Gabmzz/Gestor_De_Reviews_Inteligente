import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let service
let apiClient
let utils
let ReviewDetail
let ReviewClassification

before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
  service = await server.ssrLoadModule('/src/services/reviewService.js')
  ;({ default: apiClient } = await server.ssrLoadModule('/src/services/apiClient.js'))
  utils = await server.ssrLoadModule('/src/utils/reviewClassification.js')
  ;({ default: ReviewDetail } = await server.ssrLoadModule('/src/components/reviews/ReviewDetail.jsx'))
  ;({ default: ReviewClassification } = await server.ssrLoadModule('/src/components/reviews/ReviewClassification.jsx'))
})

after(async () => {
  await server?.close()
  delete globalThis.localStorage
})

const review = {
  id: 101, tenant_id: 10, autor: 'Ana', contenido: 'Mi pedido llegó tarde.',
  fecha: '2026-10-19T12:00:00', fuente: 'manual', puntuacion: 3,
  categoria: 'Consulta', estado: 'nueva', prioridad: 'Alta', resumen: 'Resumen previo', tema: 'Servicio',
}

test('solicita clasificación autenticada sin enviar datos editables ni tenant', async () => {
  const previousAdapter = apiClient.defaults.adapter
  const calls = []
  const result = { ...review, categoria: 'Queja' }
  globalThis.localStorage = { getItem: () => 'synthetic-token' }
  apiClient.defaults.adapter = async (config) => {
    calls.push(config)
    return { data: result, status: 200, statusText: 'OK', headers: {}, config }
  }
  try {
    const controller = new AbortController()
    assert.deepEqual(await service.classifyReview(101, { signal: controller.signal, tenant_id: 20 }), result)
    assert.equal(calls.length, 1)
    assert.equal(calls[0].url, '/reviews/101/clasificacion')
    assert.equal(calls[0].method, 'post')
    assert.equal(calls[0].headers.Authorization, 'Bearer synthetic-token')
    assert.equal(calls[0].data, undefined)
    assert.equal(calls[0].params, undefined)
    assert.equal(calls[0].signal, controller.signal)
    assert.equal(calls[0].timeout, 150000)
  } finally {
    apiClient.defaults.adapter = previousAdapter
  }
})

test('propaga el error sin inventar categoría ni reintentar', async () => {
  const previous = apiClient.post
  const failure = new Error('simulated network error')
  let calls = 0
  apiClient.post = async () => { calls += 1; throw failure }
  try {
    await assert.rejects(service.classifyReview(101), (error) => error === failure)
    assert.equal(calls, 1)
    assert.equal(review.categoria, 'Consulta')
  } finally {
    apiClient.post = previous
  }
})

test('actualiza solo categoría con la respuesta del backend para la misma review', () => {
  for (const categoria of ['Queja', 'Sugerencia', 'Felicitación', 'Consulta']) {
    const result = { ...review, categoria, resumen: 'Respuesta vieja', estado: 'atendida', puntuacion: 1 }
    assert.deepEqual(utils.mergeClassification(review, result), { ...review, categoria })
    assert.equal(review.categoria, 'Consulta')
  }
})

test('no aplica respuestas a otra selección, tenant, contenido o categoría inválida', () => {
  for (const patch of [{ id: 201 }, { tenant_id: 20 }, { contenido: 'Texto editado' }, { categoria: 'Positiva' }, { categoria: null }]) {
    const result = { ...review, categoria: 'Queja', ...patch }
    assert.equal(utils.matchesClassification(review, result), false)
    assert.equal(utils.mergeClassification(review, result), review)
  }
  assert.equal(utils.mergeClassification(null, review), null)
  assert.equal(utils.matchesClassification(review, undefined), false)
})

test('la acción requiere sesión con rol de negocio y tenant', () => {
  for (const rol of ['usuario_negocio', 'admin_tenant']) {
    assert.equal(utils.canClassifyReview({ access_token: 'token', user: { rol, tenant_id: 10 } }), true)
  }
  for (const session of [null, {}, { user: { rol: 'admin_tenant', tenant_id: 10 } },
    { access_token: 'token', user: { rol: 'admin_general', tenant_id: 10 } },
    { access_token: 'token', user: { rol: 'admin_tenant', tenant_id: null } }]) {
    assert.equal(utils.canClassifyReview(session), false)
  }
})

test('el detalle conserva categoría de solo lectura, edición y seguimiento', () => {
  const html = renderToStaticMarkup(React.createElement(ReviewDetail, { review, canClassify: true }))
  assert.match(html, /Consulta/)
  assert.match(html, /Clasificar nuevamente con IA/)
  assert.match(html, /Editar review/)
  assert.match(html, /Estado de seguimiento/)
  assert.doesNotMatch(html, /name="categoria"|name="tenant_id"/)
})

test('sin categoría ofrece clasificación, sin permiso oculta la acción', () => {
  const empty = renderToStaticMarkup(React.createElement(ReviewDetail, { review: { ...review, categoria: null }, canClassify: true }))
  assert.match(empty, /Clasificar con IA/)
  const denied = renderToStaticMarkup(React.createElement(ReviewDetail, { review, canClassify: false }))
  assert.doesNotMatch(denied, /Clasificar.*con IA/)
  assert.match(denied, /Consulta/)
})

test('loading deshabilita clasificación y error permite volver a intentarlo', () => {
  const busy = renderToStaticMarkup(React.createElement(ReviewClassification, {
    canClassify: true, category: review.categoria, isClassifying: true,
  }))
  assert.match(busy, /disabled=""/)
  assert.match(busy, /Clasificando…/)
  assert.match(busy, /role="status"/)
  const failed = renderToStaticMarkup(React.createElement(ReviewClassification, {
    canClassify: true, category: review.categoria, error: 'Inténtalo nuevamente.',
  }))
  assert.doesNotMatch(failed, /disabled=""/)
  assert.match(failed, /role="alert"/)
  assert.match(failed, /Clasificar nuevamente con IA/)
})

test('no muestra el resultado anterior mientras carga otra review', () => {
  const html = renderToStaticMarkup(React.createElement(ReviewDetail, { review, isLoading: true, canClassify: true }))
  assert.doesNotMatch(html, /Consulta|Clasificar con IA|Clasificar nuevamente con IA/)
})

test('traduce errores sin exponer cuerpos técnicos del servidor', () => {
  for (const status of [401, 403, 404, 409, 422, 500, 502, 503, 504]) {
    const message = utils.classificationErrorMessage({ response: { status, data: { detail: 'private-secret' } } })
    assert.equal(typeof message, 'string')
    assert.ok(message.length > 10)
    assert.doesNotMatch(message, /private-secret/)
  }
  assert.match(utils.classificationErrorMessage({ code: 'ECONNABORTED' }), /tardó demasiado/)
  assert.match(utils.classificationErrorMessage({}), /conexión/)
})
