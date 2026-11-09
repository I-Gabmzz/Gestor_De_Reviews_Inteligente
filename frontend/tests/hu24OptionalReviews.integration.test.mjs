import assert from 'node:assert/strict'
import { after, afterEach, before, test } from 'node:test'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'

let dom, server, React, act, createRoot, MemoryRouter, ManualReviewPage, ReviewEditForm, ReviewTable, ReviewDetail, apiClient
let container, root, originalPost, originalPatch

before(async () => {
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.navigator = dom.window.navigator
  globalThis.HTMLElement = dom.window.HTMLElement
  globalThis.localStorage = dom.window.localStorage
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  dom.window.HTMLDialogElement.prototype.showModal = function () { this.open = true }
  dom.window.HTMLDialogElement.prototype.close = function () { this.open = false }
  React = await import('react')
  ;({ act } = React)
  ;({ createRoot } = await import('react-dom/client'))
  ;({ MemoryRouter } = await import('react-router-dom'))
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  ;({ default: ManualReviewPage } = await server.ssrLoadModule('/src/pages/ManualReviewPage.jsx'))
  ;({ default: ReviewEditForm } = await server.ssrLoadModule('/src/components/reviews/ReviewEditForm.jsx'))
  ;({ default: ReviewTable } = await server.ssrLoadModule('/src/components/reviews/ReviewTable.jsx'))
  ;({ default: ReviewDetail } = await server.ssrLoadModule('/src/components/reviews/ReviewDetail.jsx'))
  ;({ default: apiClient } = await server.ssrLoadModule('/src/services/apiClient.js'))
  originalPost = apiClient.post
  originalPatch = apiClient.patch
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
  apiClient.post = originalPost
  apiClient.patch = originalPatch
})

after(async () => {
  await server?.close()
  dom?.window.close()
  for (const name of ['window', 'document', 'navigator', 'HTMLElement', 'localStorage', 'IS_REACT_ACT_ENVIRONMENT']) delete globalThis[name]
})

async function mount(element) {
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  await act(async () => root.render(React.createElement(MemoryRouter, null, element)))
}

async function setValue(selector, value) {
  const element = container.querySelector(selector)
  assert.ok(element, selector)
  const prototype = element.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : element.tagName === 'SELECT' ? window.HTMLSelectElement.prototype : window.HTMLInputElement.prototype
  await act(async () => {
    Object.getOwnPropertyDescriptor(prototype, 'value').set.call(element, value)
    element.dispatchEvent(new window.Event('input', { bubbles: true }))
    element.dispatchEvent(new window.Event('change', { bubbles: true }))
  })
}

async function submit() {
  await act(async () => container.querySelector('form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true })))
}

test('registro sin fecha ni puntuación envía null y rechaza contenido en blanco', async () => {
  const calls = []
  apiClient.post = async (url, payload) => { calls.push({ url, payload }); return { status: 201, data: { id: 1 } } }
  await mount(React.createElement(ManualReviewPage))
  await setValue('#contenido', '   ')
  await submit()
  assert.equal(calls.length, 0)
  assert.match(container.textContent, /Escribe el contenido/)
  await setValue('#contenido', 'Buena atención')
  await submit()
  assert.deepEqual(calls, [{ url: '/reviews', payload: { autor: null, contenido: 'Buena atención', fecha: null, puntuacion: null } }])
})

test('edición envía solo cambios y permite limpiar valores sin alterar fuente ni contenido', async () => {
  const calls = []
  const review = { id: 7, tenant_id: 10, autor: 'Ana', contenido: '  Histórico  ', fecha: '2026-01-01T12:00:00', puntuacion: 4, fuente: 'Google', estado: 'atendida' }
  apiClient.patch = async (url, payload) => { calls.push({ url, payload }); return { data: { ...review, ...payload } } }
  await mount(React.createElement(ReviewEditForm, { review, onCancel() {}, onSaved() {} }))
  await setValue('#review-edit-fecha', '')
  await setValue('#review-edit-puntuacion', '')
  await submit()
  assert.deepEqual(calls, [{ url: '/reviews/7', payload: { fecha: null, puntuacion: null } }])
})

test('edición rechaza puntuaciones fuera del rango', async () => {
  const calls = []
  const review = { id: 8, tenant_id: 10, autor: null, contenido: 'Bien', fecha: null, puntuacion: null, fuente: 'manual', estado: 'nueva' }
  apiClient.patch = async (...args) => { calls.push(args); return { data: review } }
  await mount(React.createElement(ReviewEditForm, { review, onCancel() {}, onSaved() {} }))
  for (const score of ['0', '6']) {
    await setValue('#review-edit-puntuacion', score)
    await submit()
    assert.match(container.textContent, /entero entre 1 y 5/)
  }
  assert.equal(calls.length, 0)
})

test('tabla, detalle y edición abren una reseña sin datos opcionales', async () => {
  const review = { id: 1, tenant_id: 10, autor: null, contenido: 'Bien', fecha: null, puntuacion: null, fuente: 'manual', estado: 'nueva' }
  await mount(React.createElement(React.Fragment, null,
    React.createElement(ReviewTable, { reviews: [review], onSelect() {} }),
    React.createElement(ReviewDetail, { review, onEdit() {}, onStatusConfirm() {} }),
    React.createElement(ReviewEditForm, { review, onCancel() {}, onSaved() {} }),
  ))
  assert.match(container.textContent, /Sin fecha/)
  assert.match(container.textContent, /Sin puntuación/)
  assert.equal(container.querySelector('#review-edit-fecha').value, '')
  assert.equal(container.querySelector('#review-edit-puntuacion').value, '')
})
