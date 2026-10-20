import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { createServer } from 'vite'

let server
let DashboardPage

before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
  ;({ default: DashboardPage } = await server.ssrLoadModule('/src/pages/DashboardPage.jsx'))
})

after(async () => {
  await server?.close()
  delete globalThis.localStorage
})

function dashboardFor(role) {
  const user = JSON.stringify({ rol: role })
  globalThis.localStorage = {
    getItem: (key) => key === 'gestor_reviews_access_token' ? 'test-token'
      : key === 'gestor_reviews_user' ? user : null,
  }
  return renderToStaticMarkup(
    React.createElement(MemoryRouter, null, React.createElement(DashboardPage)),
  )
}

test('el dashboard presenta gestión de usuarios solo al admin_tenant', () => {
  assert.match(dashboardFor('admin_tenant'), /href="\/users"[^>]*>.*Usuarios/s)
  assert.doesNotMatch(dashboardFor('usuario_negocio'), /href="\/users"/)
})
