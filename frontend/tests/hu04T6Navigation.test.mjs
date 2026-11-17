import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { createServer } from 'vite'

let server
let ProtectedRoute

before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
  ;({ ProtectedRoute } = await server.ssrLoadModule('/src/App.jsx'))
})

after(async () => {
  await server?.close()
  delete globalThis.localStorage
})

function navigationFor(role, path = '/dashboard') {
  const user = JSON.stringify({ rol: role })
  globalThis.localStorage = {
    getItem: (key) => key === 'gestor_reviews_access_token' ? 'test-token'
      : key === 'gestor_reviews_user' ? user : null,
  }
  return renderToStaticMarkup(
    React.createElement(MemoryRouter, { initialEntries: [path] },
      React.createElement(ProtectedRoute, { path }, React.createElement('main')),
    ),
  )
}

test('la navegación del negocio presenta gestión de usuarios solo al admin_tenant', () => {
  assert.match(navigationFor('admin_tenant'), /href="\/users"[^>]*>Usuarios<\/a>/)
  assert.doesNotMatch(navigationFor('usuario_negocio'), /href="\/users"/)
})

test('ambos roles de negocio tienen un enlace directo a la bandeja y se indica la sección activa', () => {
  for (const role of ['admin_tenant', 'usuario_negocio']) {
    assert.match(navigationFor(role), /href="\/reviews"[^>]*>Reseñas<\/a>/)
    assert.match(navigationFor(role, '/reviews'), /aria-current="location"[^>]*href="\/reviews"[^>]*>Reseñas<\/a>/)
  }
  assert.doesNotMatch(navigationFor('admin_general', '/admin'), /href="\/reviews"/)
})
