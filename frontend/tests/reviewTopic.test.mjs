import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let ReviewDetail
let service
let apiClient

before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
  ;({ default: ReviewDetail } = await server.ssrLoadModule('/src/components/reviews/ReviewDetail.jsx'))
  service = await server.ssrLoadModule('/src/services/reviewService.js')
  ;({ default: apiClient } = await server.ssrLoadModule('/src/services/apiClient.js'))
})

after(async () => { await server?.close() })

const review = {
  id: 101, tenant_id: 10, autor: 'Ana', fecha: '2026-10-19T12:00:00',
  contenido: 'El personal fue amable.', puntuacion: 5, estado: 'nueva',
  categoria: 'Felicitación', fuente: 'manual', prioridad: 'Alta', tema: 'Atención',
}

test('el detalle presenta tema persistido sin edición manual', () => {
  const html = renderToStaticMarkup(React.createElement(ReviewDetail, { review, canDetectTopic: true }))
  assert.match(html, /Tema principal/)
  assert.match(html, /Atención/)
  assert.match(html, /Generado por IA/)
  assert.match(html, /Detectar tema nuevamente/)
  assert.doesNotMatch(html, /name="tema"/)
  assert.match(html, /Felicitación/)
  assert.match(html, /Editar review/)
})

test('el detalle distingue ausencia de tema y oculta acción sin permiso', () => {
  const html = renderToStaticMarkup(React.createElement(ReviewDetail, { review: { ...review, tema: null } }))
  assert.match(html, /Aún no se ha detectado un tema/)
  assert.doesNotMatch(html, /Detectar tema/)
})

test('el servicio usa el cliente compartido sin enviar tenant ni contenido', async () => {
  const previous = apiClient.post
  const calls = []
  apiClient.post = async (...args) => { calls.push(args); return { data: review } }
  try {
    const controller = new AbortController()
    assert.equal(await service.detectReviewTopic(101, { signal: controller.signal, tenant_id: 20 }), review)
    assert.deepEqual(calls, [['/reviews/101/tema', undefined, { signal: controller.signal, timeout: 150000 }]])
  } finally {
    apiClient.post = previous
  }
})
