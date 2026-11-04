const businessPattern = /^0x[0-9a-fA-F]+:0x[0-9a-fA-F]+$/
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const countFields = ['input_count', 'inserted', 'repeated', 'changed', 'omitted', 'rejected', 'batch_duplicates', 'request_count']
const messages = {
  import_disabled: 'La importación externa está deshabilitada en el servidor.',
  unauthorized_context: 'Tu acceso a la importación ya no está disponible. Revisa tu sesión.',
  connection_unavailable: 'El establecimiento seleccionado ya no está disponible para tu sesión.',
  persistence_disabled: 'La conexión no está habilitada para importar reseñas.',
  import_in_progress: 'El establecimiento tiene una importación pendiente. Solicita su revisión antes de continuar.',
  budget_exhausted: 'Se alcanzó el presupuesto de importación. No se enviará otra solicitud automáticamente.',
  admission_unavailable: 'No pudimos confirmar la admisión. Consulta las reviews y solicita una revisión.',
  admission_schema_invalid: 'La importación necesita una revisión de configuración por el responsable.',
  policy_unavailable: 'La configuración de importación no está disponible.',
  place_unverified: 'No se pudo verificar el establecimiento. No se guardaron reseñas de este lote.',
  incomplete_acquisition: 'La adquisición quedó incompleta. No se guardaron reseñas de este lote.',
  normalization_failed: 'La respuesta recibida no permite importar las reseñas de forma segura.',
  provider_timeout: 'La consulta superó el tiempo de espera. Consulta las reviews antes de solicitar otra importación.',
  provider_unavailable: 'El proveedor no está disponible para esta operación.',
  provider_response: 'El proveedor no devolvió una respuesta válida para importar.',
  persistence_rejected: 'El lote no cumple los requisitos para guardar las reseñas.',
  persistence_conflict: 'No se pudo completar la importación por una operación concurrente.',
  persistence_failed: 'No pudimos confirmar el guardado. Consulta las reviews y solicita una revisión.',
  internal_error: 'No se pudo completar la importación externa.',
}

export function externalImportIdentity(session) {
  const user = session?.user
  if (!session?.access_token || !['usuario_negocio', 'admin_tenant'].includes(user?.rol)
    || !Number.isSafeInteger(user?.id) || user.id < 1
    || !Number.isSafeInteger(user?.tenant_id) || user.tenant_id < 1) return ''
  return JSON.stringify([user.id, user.tenant_id, user.rol])
}

export function externalImportStorageKey(identity, business) {
  return `gestor_reviews_external_import:${identity}:${business}`
}

export function parseExternalConnections(data) {
  if (data?.source !== 'Google' || typeof data.import_enabled !== 'boolean' || !Array.isArray(data.connections)) {
    throw new Error('Respuesta de conexiones no verificable')
  }
  const seen = new Set()
  const connections = data.connections.map((row) => {
    const id = row?.business_data_id
    const name = row?.business_name
    if (typeof id !== 'string' || !id.length || id.length > 128 || seen.has(id)
      || !['available', 'disabled'].includes(row.status)
      || (row.status === 'available' && !businessPattern.test(id))
      || (name != null && (typeof name !== 'string' || !name.trim() || name.length > 255))) throw new Error('Conexión no verificable')
    seen.add(id)
    return { business_data_id: id, business_name: name?.trim() || 'Establecimiento de Google', status: row.status }
  })
  return { source: 'Google', import_enabled: data.import_enabled, connections }
}

export function parseExternalImportResult(data) {
  const complete = data?.stop_reason === 'no_next_token' && data.incomplete === false && data.limited === false
  const bounded = data?.stop_reason === 'max_pages' && data.incomplete === true && data.limited === true
  if (data?.outcome !== 'committed' || data.source !== 'Google' || typeof data.operation_id !== 'string' || !uuidPattern.test(data.operation_id)
    || !['released', 'reconciliation_required'].includes(data.control_status)
    // Sólo el servidor autoriza guardar un lote acotado. Errores de adquisición
    // y combinaciones contradictorias nunca son resultados confirmados.
    || (!complete && !bounded)
    || countFields.some((field) => !Number.isSafeInteger(data[field]) || data[field] < 0)
    || data.request_count < 1 || data.request_count > 5
    || data.batch_duplicates > data.repeated
    || data.input_count !== data.inserted + data.repeated + data.changed + data.omitted + data.rejected) {
    throw new Error('Resultado de importación no verificable')
  }
  return Object.fromEntries([
    ...countFields.map((field) => [field, data[field]]),
    ...['operation_id', 'outcome', 'source', 'control_status', 'incomplete', 'limited', 'stop_reason'].map((field) => [field, data[field]]),
  ])
}

export function externalImportFailure(error) {
  const status = error?.response?.status
  const detail = error?.response?.data?.detail
  const object = detail && typeof detail === 'object' && !Array.isArray(detail) ? detail : null
  const code = object?.code
  const known = typeof code === 'string' && Object.hasOwn(messages, code)
  const definitive = known && ['rejected', 'rolled_back'].includes(object.outcome)
    && object.committed_count === 0 && object.control_status === 'released'
  const authOrValidation = status === 401 || status === 403 || (status === 422 && Array.isArray(detail))
  const requiresReview = !error?.response || status === 504 || code === 'import_in_progress'
    || object?.outcome === 'unknown' || object?.control_status === 'reconciliation_required'
    || (!definitive && !authOrValidation)
  let message = requiresReview
    ? 'No pudimos confirmar el resultado. La operación puede haber guardado reseñas. Consulta las reviews y solicita una revisión antes de continuar.'
    : (known ? messages[code] : 'No se pudo realizar la importación externa.')
  if (code === 'import_in_progress') message = messages.import_in_progress
  if (status === 401) message = 'Tu sesión expiró o no está disponible. Inicia sesión nuevamente.'
  else if (status === 403 && !known) message = 'No tienes permiso para importar reseñas externas. Revisa tu sesión.'
  else if (status === 422 && Array.isArray(detail)) message = 'La solicitud no es válida. Actualiza las conexiones antes de continuar.'
  return {
    message, requiresReview,
    incomplete: object?.incomplete === true, limited: object?.limited === true,
    obtained: Number.isSafeInteger(object?.obtained) && object.obtained >= 0 ? object.obtained : null,
  }
}

export function externalConnectionsError(error) {
  if (error?.response?.status === 401) return 'Tu sesión expiró. Inicia sesión para consultar las conexiones.'
  if (error?.response?.status === 403) return 'No tienes permiso para consultar las conexiones externas.'
  return 'No pudimos consultar las conexiones. Puedes actualizar la lista; esto no inicia una importación.'
}
