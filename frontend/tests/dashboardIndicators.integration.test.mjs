import assert from 'node:assert/strict'
import { test } from 'node:test'
import React, { act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'

test('muestra indicadores enlazados y reseñas recientes con datos opcionales', async () => {
  const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost/dashboard' })
  for (const name of ['window', 'document', 'navigator', 'localStorage']) {
    globalThis[name] = name === 'window' ? dom.window : dom.window[name]
  }
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  const server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' })
  const container = document.querySelector('#root')
  const root = createRoot(container)
  try {
    const { default: DashboardPage } = await server.ssrLoadModule('/src/pages/DashboardPage.jsx')
    const { default: apiClient } = await server.ssrLoadModule('/src/services/apiClient.js')
    apiClient.defaults.adapter = async (config) => {
      assert.equal(config.url, '/dashboard')
      return {
        status: 200,
        headers: {},
        config,
        data: {
          total_reviews: 12, reviews_nuevas: 4, reviews_en_revision: 3,
          reviews_atendidas: 5, reviews_urgentes: 2, promedio_puntuacion: 3.75,
          reviews_recientes: [
            { id: 1, contenido: 'Reseña con datos ausentes', estado: 'nueva', fecha: null, puntuacion: null },
            { id: 2, contenido: 'Reseña con datos presentes', estado: 'nueva', fecha: '2026-01-02T12:00:00', puntuacion: 4 },
          ],
        },
      }
    }
    await act(async () => {
      root.render(React.createElement(MemoryRouter, {
        future: { v7_startTransition: true, v7_relativeSplatPath: true },
      }, React.createElement(DashboardPage)))
    })
    const cards = [...container.querySelectorAll('article')]
    assert.deepEqual(cards.flatMap((card) => {
      const link = card.querySelector('a')
      return link ? [[link.textContent.trim(), link.getAttribute('href'), card.querySelector('.text-3xl').textContent]] : []
    }), [
      ['Total de reviews', '/reviews', '12'],
      ['Reviews nuevas', '/reviews?estado=nueva', '4'],
      ['Reviews en revisión', '/reviews?estado=en_revision', '3'],
      ['Reviews atendidas', '/reviews?estado=atendida', '5'],
      ['Reviews urgentes', '/reviews?urgente=true', '2'],
    ])
    const average = cards.find((card) => card.textContent.includes('Promedio de puntuación'))
    assert.equal(average.querySelector('a'), null)
    assert.equal(average.querySelector('.text-3xl').textContent, '3.8')

    const [missing, present] = container.querySelectorAll('tbody tr')
    assert.equal(missing.cells[1].textContent.trim(), 'Sin puntuación')
    assert.equal(missing.cells[1].querySelector('svg'), null)
    assert.equal(missing.cells[3].textContent.trim(), 'Sin fecha')
    assert.equal(present.cells[1].textContent.trim(), '4/5')
    assert.ok(present.cells[1].querySelector('svg'))
    assert.ok(present.cells[3].textContent.includes('02/01/2026'))
    assert.ok(!container.querySelector('tbody').textContent.includes('0/5'))
    assert.ok(!container.querySelector('tbody').textContent.includes('Invalid Date'))
  } finally {
    await act(async () => root.unmount())
    await server.close()
    dom.window.close()
    for (const name of ['window', 'document', 'navigator', 'localStorage', 'IS_REACT_ACT_ENVIRONMENT']) {
      delete globalThis[name]
    }
  }
})
