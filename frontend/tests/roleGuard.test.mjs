import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { createServer } from 'vite'

let server
let ProtectedRoute
let logout
let getStoredSession

before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
  ;({ ProtectedRoute } = await server.ssrLoadModule('/src/App.jsx'))
  ;({ logout, getStoredSession } = await server.ssrLoadModule('/src/services/authService.js'))
})

after(async () => {
  await server?.close()
  delete globalThis.localStorage
})

function openAs(role, path) {
  const values = new Map()
  if (role) {
    values.set('gestor_reviews_access_token', 'test-token')
    values.set('gestor_reviews_user', JSON.stringify({ rol: role }))
  }
  globalThis.localStorage = { getItem: (key) => values.get(key) ?? null }

  return renderToStaticMarkup(
    React.createElement(MemoryRouter, { initialEntries: [path] },
      React.createElement(Routes, null,
        React.createElement(Route, {
          path,
          element: React.createElement(ProtectedRoute, { path }, React.createElement('span', null, 'contenido autorizado')),
        }),
      ),
    ),
  )
}

test('la guarda permite acceso directo solo al rol autorizado', () => {
  assert.match(openAs('usuario_negocio', '/reviews/new'), /contenido autorizado/)
  assert.doesNotMatch(openAs('usuario_negocio', '/users'), /contenido autorizado/)
  assert.match(openAs('admin_tenant', '/users'), /contenido autorizado/)
  assert.doesNotMatch(openAs('admin_tenant', '/admin'), /contenido autorizado/)
  assert.match(openAs('admin_general', '/admin'), /contenido autorizado/)
  assert.doesNotMatch(openAs('admin_general', '/dashboard'), /contenido autorizado/)
  assert.doesNotMatch(openAs(null, '/dashboard'), /contenido autorizado/)
})

test('cerrar sesión elimina la identidad y el token sin borrar otras preferencias', () => {
  const values = new Map([
    ['gestor_reviews_access_token', 'test-token'],
    ['gestor_reviews_user', JSON.stringify({ rol: 'admin_tenant' })],
    ['preferencia', 'conservar'],
  ])
  globalThis.localStorage = {
    getItem: (key) => values.get(key) ?? null,
    removeItem: (key) => values.delete(key),
  }
  assert.equal(getStoredSession().user.rol, 'admin_tenant')
  logout()
  assert.equal(getStoredSession(), null)
  assert.equal(values.has('gestor_reviews_access_token'), false)
  assert.equal(values.has('gestor_reviews_user'), false)
  assert.equal(values.get('preferencia'), 'conservar')
})
