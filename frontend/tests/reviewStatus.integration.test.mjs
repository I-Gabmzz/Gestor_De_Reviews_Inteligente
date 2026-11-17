import assert from 'node:assert/strict'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'
import React, { act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { createServer } from 'vite'

test('mantiene el estado confirmado al fallar y conserva el detalle al guardar fuera del filtro', async () => {
  const dom = new JSDOM('<!doctype html><div id="root"></div>', { url: 'http://localhost/reviews' })
  const { window } = dom
  Object.assign(globalThis, {
    window,
    document: window.document,
    localStorage: window.localStorage,
    IS_REACT_ACT_ENVIRONMENT: true,
  })
  localStorage.setItem('gestor_reviews_access_token', 'test-token')
  localStorage.setItem('gestor_reviews_user', JSON.stringify({ id: 1, tenant_id: 10, rol: 'usuario_negocio' }))

  let server
  let root
  try {
    server = await createServer({ server: { middlewareMode: true, ws: false }, appType: 'custom', logLevel: 'error' })
    const { default: ReviewsPage } = await server.ssrLoadModule('/src/pages/ReviewsPage.jsx')
    const { default: apiClient } = await server.ssrLoadModule('/src/services/apiClient.js')
    let review = {
      id: 101, tenant_id: 10, autor: 'Ana Luna', contenido: 'Comentario original del cliente.',
      fecha: '2026-11-09T10:00:00', fuente: 'Google', puntuacion: 4, estado: 'nueva',
    }
    const attempts = []
    apiClient.defaults.adapter = async (config) => {
      const reply = (data) => ({ data, config, status: 200, headers: {} })
      if (config.url === '/dashboard') return reply({ nombre_negocio: 'Negocio de prueba' })
      if (config.url === '/reviews') {
        const items = !config.params.estado || config.params.estado === review.estado ? [review] : []
        return reply({ items, total: items.length })
      }
      if (config.url === '/reviews/101') return reply(review)
      if (config.method === 'patch' && config.url === '/reviews/101/status') {
        attempts.push(JSON.parse(config.data))
        if (attempts.length === 1) throw Object.assign(new Error('Fallo de prueba'), { response: { status: 503 } })
        review = { ...review, ...attempts.at(-1) }
        return reply(review)
      }
      throw new Error(`Solicitud inesperada: ${config.url}`)
    }

    const container = document.getElementById('root')
    root = createRoot(container)
    await act(async () => {
      root.render(React.createElement(MemoryRouter, null, React.createElement(ReviewsPage)))
    })

    const select = (selector, value) => act(async () => {
      const field = container.querySelector(selector)
      field.value = value
      field.dispatchEvent(new window.Event('change', { bubbles: true }))
    })
    const submit = () => act(async () => {
      container.querySelector('#review-status').form.requestSubmit()
    })
    const detail = () => container.querySelector('[aria-label="Detalle de la review"]')
    await select('#review-estado', 'nueva')
    await select('#review-status', 'atendida')
    await submit()

    assert.match(detail().textContent, /Estado actual: Nueva/)
    assert.match(detail().querySelector('[role="alert"]').textContent, /No fue posible guardar/)
    assert.equal(container.querySelector('#review-status').value, 'atendida')

    await submit()

    assert.deepEqual(attempts, [{ estado: 'atendida' }, { estado: 'atendida' }])
    assert.match(detail().textContent, /Estado actual: Atendida/)
    assert.match(detail().querySelector('[role="status"]').textContent, /Estado guardado/)
    assert.equal(container.querySelector('#review-estado').value, 'nueva')
    assert.equal(container.querySelector('table'), null)
    assert.match(container.textContent, /No hay reviews que coincidan/)
  } finally {
    if (root) await act(async () => root.unmount())
    await server?.close()
    window.close()
    for (const name of ['window', 'document', 'localStorage', 'IS_REACT_ACT_ENVIRONMENT']) delete globalThis[name]
  }
})
