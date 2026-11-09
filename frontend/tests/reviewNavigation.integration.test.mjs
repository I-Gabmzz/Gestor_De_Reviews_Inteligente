import assert from 'node:assert/strict'
import { after, afterEach, before, test } from 'node:test'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'

let dom
let server
let React
let act
let createRoot
let MemoryRouter
let useLocation
let useNavigate
let ReviewsPage
let apiClient
let root
let container
let originalAdapter
let scrollPosition
let navigateFromRouter
let availableReviews

const reviews = [
  {
    id: 101, tenant_id: 10, autor: 'Ana', contenido: 'Buena atención en sucursal.',
    fecha: '2026-10-24T08:00:00', fuente: 'Google', puntuacion: 5,
    categoria: null, estado: 'nueva', prioridad: null,
  },
  {
    id: 102, tenant_id: 10, autor: 'Luis', contenido: 'La entrega fue rápida.',
    fecha: '2026-10-23T18:30:00', fuente: 'Facebook', puntuacion: 4,
    categoria: 'Servicio', estado: 'en_revision', prioridad: 'Media',
  },
]

function response(config, data) {
  return { data, status: 200, statusText: 'OK', headers: {}, config }
}

function RouterProbe() {
  const location = useLocation()
  navigateFromRouter = useNavigate()
  return React.createElement('output', { 'data-testid': 'current-location' }, `${location.pathname}${location.search}`)
}

before(async () => {
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.navigator = dom.window.navigator
  globalThis.HTMLElement = dom.window.HTMLElement
  globalThis.localStorage = dom.window.localStorage
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  scrollPosition = 0
  Object.defineProperty(dom.window, 'scrollY', { configurable: true, get: () => scrollPosition })
  dom.window.scrollTo = (_x, y) => { scrollPosition = y }
  React = await import('react')
  ;({ act } = React)
  ;({ createRoot } = await import('react-dom/client'))
  ;({ MemoryRouter, useLocation, useNavigate } = await import('react-router-dom'))
  server = await createServer({
    server: { middlewareMode: true, hmr: false },
    optimizeDeps: { noDiscovery: true, include: [] },
    appType: 'custom',
    logLevel: 'error',
  })
  ;({ default: ReviewsPage } = await server.ssrLoadModule('/src/pages/ReviewsPage.jsx'))
  ;({ default: apiClient } = await server.ssrLoadModule('/src/services/apiClient.js'))
  originalAdapter = apiClient.defaults.adapter
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
  container = null
  navigateFromRouter = null
  apiClient.defaults.adapter = originalAdapter
  localStorage.clear()
  availableReviews = [...reviews]
  scrollPosition = 0
})

after(async () => {
  await server?.close()
  dom?.window.close()
  for (const name of ['window', 'document', 'navigator', 'HTMLElement', 'localStorage', 'IS_REACT_ACT_ENVIRONMENT']) {
    delete globalThis[name]
  }
})

async function mount(initialEntry = '/reviews') {
  localStorage.setItem('gestor_reviews_access_token', 'token-de-prueba')
  localStorage.setItem('gestor_reviews_user', JSON.stringify({ id: 1, rol: 'usuario_negocio', tenant_id: 10 }))
  availableReviews = [...reviews]
  apiClient.defaults.adapter = async (config) => {
    if (config.url === '/reviews') {
      const criteria = config.params || {}
      const items = availableReviews.filter((review) => (
        (!criteria.busqueda || review.contenido.toLowerCase().includes(criteria.busqueda.toLowerCase()))
        && (!criteria.estado || review.estado === criteria.estado)
        && (!criteria.fuente || review.fuente.toLowerCase().includes(criteria.fuente.toLowerCase()))
      ))
      return response(config, { items, total: items.length })
    }
    const detailId = /^\/reviews\/(\d+)$/.exec(config.url)?.[1]
    if (detailId) {
      const review = reviews.find((item) => item.id === Number(detailId))
      if (review) return response(config, review)
    }
    throw new Error(`Solicitud inesperada: ${config.url}`)
  }
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  await act(async () => {
    root.render(React.createElement(
      MemoryRouter,
      { initialEntries: [initialEntry] },
      React.createElement(React.Fragment, null,
        React.createElement(RouterProbe),
        React.createElement(ReviewsPage),
      ),
    ))
  })
  await settle()
}

function settle(milliseconds = 20) {
  return act(async () => new Promise((resolve) => setTimeout(resolve, milliseconds)))
}

function locationText() {
  return container.querySelector('[data-testid="current-location"]')?.textContent
}

function reviewCard(id) {
  return container.querySelector(`button.review-card[data-review-id="${id}"]`)
}

function setInputValue(input, value) {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
  setter.call(input, value)
  input.dispatchEvent(new window.Event('input', { bubbles: true }))
}

function activateNativeButtonByKeyboard(button, key) {
  const keydown = new window.KeyboardEvent('keydown', { key, bubbles: true, cancelable: true })
  const keyup = new window.KeyboardEvent('keyup', { key, bubbles: true, cancelable: true })
  button.dispatchEvent(keydown)
  button.dispatchEvent(keyup)

  // JSDOM dispatches keyboard events but does not synthesize a browser's native button click.
  if (!keydown.defaultPrevented && !keyup.defaultPrevented) button.click()
  return { keydown, keyup }
}

test('seleccionar una tarjeta móvil abre el detalle y enfoca su encabezado', async () => {
  await mount()
  await act(async () => reviewCard(101).click())

  assert.equal(locationText(), '/reviews?review=101')
  assert.equal(container.querySelector('h2[tabindex="-1"]')?.textContent.trim(), 'Ana')
  assert.equal(document.activeElement, container.querySelector('h2[tabindex="-1"]'))
})

test('seleccionar una fila de escritorio enfoca el detalle correspondiente', async () => {
  await mount()
  await act(async () => container.querySelector('tr[data-review-id="102"]').click())
  await settle()

  assert.equal(locationText(), '/reviews?review=102')
  assert.equal(container.querySelector('h2[tabindex="-1"]')?.textContent.trim(), 'Luis')
  assert.equal(document.activeElement, container.querySelector('h2[tabindex="-1"]'))
})

for (const { key, name } of [{ key: 'Enter', name: 'Enter' }, { key: ' ', name: 'Espacio' }]) {
  test(`la tarjeta móvil conserva activación nativa única con ${name} y restaura el foco`, async () => {
    await mount()
    const card = reviewCard(101)
    let events
    await act(async () => { events = activateNativeButtonByKeyboard(card, key) })

    assert.equal(events.keydown.defaultPrevented, false)
    assert.equal(events.keyup.defaultPrevented, false)
    assert.equal(locationText(), '/reviews?review=101')
    assert.equal(document.activeElement?.textContent.includes('Ana'), true)

    await act(async () => navigateFromRouter(-1))
    assert.equal(locationText(), '/reviews')
    assert.equal(document.activeElement?.getAttribute('data-review-id'), '101')
  })

  test(`la fila de escritorio se activa una vez con ${name} y restaura el foco`, async () => {
    await mount()
    const row = container.querySelector('tr[data-review-id="102"]')
    const event = new window.KeyboardEvent('keydown', { key, bubbles: true, cancelable: true })
    await act(async () => { row.dispatchEvent(event) })

    assert.equal(event.defaultPrevented, true)
    assert.equal(locationText(), '/reviews?review=102')
    assert.equal(document.activeElement?.textContent.trim(), 'Luis')

    await act(async () => navigateFromRouter(-1))
    assert.equal(locationText(), '/reviews')
    assert.equal(document.activeElement?.getAttribute('data-review-id'), '102')
  })
}

test('al cambiar de escritorio a móvil, el retorno enfoca la tarjeta visible y no la fila oculta', async () => {
  await mount()
  const mobileCard = reviewCard(102)
  const desktopRow = container.querySelector('tr[data-review-id="102"]')
  mobileCard.hidden = true

  await act(async () => desktopRow.click())
  desktopRow.hidden = true
  mobileCard.hidden = false
  await act(async () => navigateFromRouter(-1))

  assert.equal(locationText(), '/reviews')
  assert.equal(document.activeElement?.tagName, 'BUTTON')
  assert.equal(document.activeElement?.getAttribute('data-review-id'), '102')
})

test('regresar conserva búsqueda y filtros, restaura scroll y enfoca la tarjeta que abrió el detalle', async () => {
  await mount()
  const search = container.querySelector('#review-search')
  await act(async () => {
    setInputValue(search, 'Buena atención')
    const status = container.querySelector('#review-estado')
    status.value = 'nueva'
    status.dispatchEvent(new window.Event('change', { bubbles: true }))
  })
  await settle(450)

  const trigger = reviewCard(101)
  assert.ok(trigger)
  scrollPosition = 512
  await act(async () => trigger.click())
  assert.equal(document.activeElement, container.querySelector('h2[tabindex="-1"]'))

  await act(async () => [...container.querySelectorAll('button')].find((item) => item.textContent.includes('Volver a resultados')).click())

  assert.equal(locationText(), '/reviews')
  assert.equal(container.querySelector('#review-search').value, 'Buena atención')
  assert.equal(container.querySelector('#review-estado').value, 'nueva')
  assert.equal(scrollPosition, 512)
  assert.equal(document.activeElement?.tagName, 'BUTTON')
  assert.equal(document.activeElement?.getAttribute('data-review-id'), '101')
})

test('un deep link abre detalle sin limpiar criterios locales y su acción vuelve a resultados', async () => {
  await mount()
  await act(async () => {
    setInputValue(container.querySelector('#review-search'), 'Buena atención')
    const status = container.querySelector('#review-estado')
    status.value = 'nueva'
    status.dispatchEvent(new window.Event('change', { bubbles: true }))
  })
  await settle(450)
  await act(async () => navigateFromRouter('/reviews?review=102'))

  assert.equal(locationText(), '/reviews?review=102')
  assert.equal(document.activeElement, container.querySelector('h2[tabindex="-1"]'))
  assert.equal(container.querySelector('#review-search').value, 'Buena atención')
  assert.equal(container.querySelector('#review-estado').value, 'nueva')
  await act(async () => [...container.querySelectorAll('button')].find((item) => item.textContent.includes('Volver a resultados')).click())

  assert.equal(locationText(), '/reviews')
  assert.equal(container.querySelector('#review-search').value, 'Buena atención')
  assert.equal(container.querySelector('#review-estado').value, 'nueva')
  assert.equal(document.activeElement, container.querySelector('[aria-label="Listado de reviews"]'))
})

test('un deep link de error enfoca el mensaje general y no el error de exportación', async () => {
  await mount()
  await act(async () => navigateFromRouter('/reviews?review=999999'))
  await settle()

  const alert = [...container.querySelectorAll('[role="alert"][tabindex="-1"]')]
    .find((element) => element.textContent.includes('No fue posible cargar las reviews'))
  assert.ok(alert)
  assert.equal(document.activeElement?.textContent, alert.textContent)
})

test('el error de exportación enfoca su propio mensaje', async () => {
  await mount()
  const exportButton = [...container.querySelectorAll('button')]
    .find((button) => button.textContent.includes('Exportar CSV'))
  assert.ok(exportButton)
  await act(async () => exportButton.click())
  await settle()

  const alert = [...container.querySelectorAll('[role="alert"][tabindex="-1"]')]
    .find((element) => element.textContent.includes('No pudimos conectar con el servidor para exportar'))
  assert.ok(alert)
  assert.equal(document.activeElement?.textContent, alert.textContent)

  const search = container.querySelector('#review-search')
  await act(async () => {
    search.focus()
    setInputValue(search, 'Buena')
  })
  await settle(450)
  assert.equal(document.activeElement?.id, 'review-search')
})

test('atrás y adelante del navegador alternan bandeja y detalle con foco coherente', async () => {
  await mount()
  await act(async () => reviewCard(102).click())
  await settle()
  await act(async () => navigateFromRouter(-1))

  assert.equal(locationText(), '/reviews')
  assert.equal(document.activeElement, reviewCard(102))

  await act(async () => navigateFromRouter(1))
  assert.equal(locationText(), '/reviews?review=102')
  assert.equal(document.activeElement, container.querySelector('h2[tabindex="-1"]'))
})

test('abrir la misma reseña dos veces y luego otra no deja historial ni foco residuales', async () => {
  await mount()

  for (let attempt = 0; attempt < 2; attempt += 1) {
    await act(async () => reviewCard(101).click())
    assert.equal(locationText(), '/reviews?review=101')
    await act(async () => [...container.querySelectorAll('button')].find((item) => item.textContent.includes('Volver a resultados')).click())
    assert.equal(locationText(), '/reviews')
    assert.equal(document.activeElement?.getAttribute('data-review-id'), '101')
  }

  await act(async () => reviewCard(102).click())
  assert.equal(locationText(), '/reviews?review=102')
  await act(async () => navigateFromRouter(-1))
  assert.equal(locationText(), '/reviews')
  assert.equal(document.activeElement?.getAttribute('data-review-id'), '102')

  await act(async () => navigateFromRouter(1))
  assert.equal(locationText(), '/reviews?review=102')
  assert.equal(document.activeElement?.textContent.trim(), 'Luis')
  await act(async () => navigateFromRouter(-1))
  assert.equal(locationText(), '/reviews')
  assert.equal(document.activeElement?.getAttribute('data-review-id'), '102')
})

test('un contexto anterior no restaura scroll ni foco al volver de un deep link directo a la misma review', async () => {
  await mount()
  scrollPosition = 512
  await act(async () => reviewCard(101).click())
  await act(async () => [...container.querySelectorAll('button')].find((item) => item.textContent.includes('Volver a resultados')).click())
  assert.equal(locationText(), '/reviews')

  scrollPosition = 128
  await act(async () => navigateFromRouter('/reviews?review=101'))
  await settle()
  await act(async () => [...container.querySelectorAll('button')].find((item) => item.textContent.includes('Volver a resultados')).click())

  assert.equal(locationText(), '/reviews')
  assert.equal(scrollPosition, 0)
  assert.equal(document.activeElement, container.querySelector('[aria-label="Listado de reviews"]'))
})

test('si la reseña deja de aparecer, el retorno enfoca el estado vacío en vez de un disparador retirado', async () => {
  await mount()
  const trigger = reviewCard(101)
  await act(async () => trigger.click())
  availableReviews = []
  await act(async () => [...container.querySelectorAll('button')].find((item) => item.textContent.includes('Actualizar')).click())
  await settle()
  await act(async () => [...container.querySelectorAll('button')].find((item) => item.textContent.includes('Volver a resultados')).click())

  assert.equal(locationText(), '/reviews')
  assert.equal(reviewCard(101), null)
  assert.match(document.activeElement.textContent, /Todavía no hay reviews/)
})
