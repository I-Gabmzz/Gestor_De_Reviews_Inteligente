import assert from 'node:assert/strict'
import test from 'node:test'

import { canAccessRoute, homeForRole } from '../src/utils/roleAccess.js'

const businessRoutes = ['/dashboard', '/imports', '/reviews', '/reviews/new']

test('usuario_negocio puede abrir las rutas operativas y no las administrativas', () => {
  for (const path of businessRoutes) assert.equal(canAccessRoute('usuario_negocio', path), true, path)
  assert.equal(canAccessRoute('usuario_negocio', '/users'), false)
  assert.equal(canAccessRoute('usuario_negocio', '/admin'), false)
  assert.equal(homeForRole('usuario_negocio'), '/dashboard')
})

test('admin_tenant puede abrir las rutas operativas y gestionar usuarios', () => {
  for (const path of [...businessRoutes, '/users']) assert.equal(canAccessRoute('admin_tenant', path), true, path)
  assert.equal(canAccessRoute('admin_tenant', '/admin'), false)
  assert.equal(homeForRole('admin_tenant'), '/dashboard')
})

test('admin_general solo puede abrir su inicio administrativo', () => {
  for (const path of [...businessRoutes, '/users']) assert.equal(canAccessRoute('admin_general', path), false, path)
  assert.equal(canAccessRoute('admin_general', '/admin'), true)
  assert.equal(homeForRole('admin_general'), '/admin')
})

test('un rol desconocido no recibe acceso a rutas protegidas', () => {
  for (const path of [...businessRoutes, '/users', '/admin']) {
    assert.equal(canAccessRoute('otro_rol', path), false, path)
  }
  assert.equal(homeForRole('otro_rol'), '/')
})
