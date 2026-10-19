const businessRoles = ['usuario_negocio', 'admin_tenant']

const routeRoles = {
  '/dashboard': businessRoles,
  '/imports': businessRoles,
  '/reviews': businessRoles,
  '/reviews/new': businessRoles,
  '/users': ['admin_tenant'],
  '/admin': ['admin_general'],
}

export function homeForRole(role) {
  if (role === 'admin_general') return '/admin'
  if (businessRoles.includes(role)) return '/dashboard'
  return '/'
}

export function canAccessRoute(role, path) {
  return routeRoles[path]?.includes(role) ?? false
}
