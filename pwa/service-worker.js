const CACHE_NAME = 'auditoria-pwa-v1';
const OFFLINE_URL = '/pwa/offline.html';

const ASSETS_TO_CACHE = [
  '/',
  '/pwa/manifest.json',
  '/pwa/icon-192.png',
  '/pwa/icon-512.png',
  '/pwa/icon-maskable-192.png',
  '/pwa/icon-maskable-512.png',
  '/pwa/offline.html'
];

// Instalação - Cache dos assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[PWA] Cache aberto');
        return cache.addAll(ASSETS_TO_CACHE);
      })
      .then(() => self.skipWaiting())
  );
});

// Ativação - Limpar caches antigos
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((cacheName) => cacheName !== CACHE_NAME)
            .map((cacheName) => caches.delete(cacheName))
        );
      })
      .then(() => self.clients.claim())
  );
});

// Fetch - Estratégia de cache com fallback para offline
self.addEventListener('fetch', (event) => {
  // Ignorar requisições não-GET
  if (event.request.method !== 'GET') return;

  // Ignorar requisições de API e WebSocket
  if (event.request.url.includes('/_stcore/') || 
      event.request.url.includes('/_stcore/conn') ||
      event.request.url.includes('ws://') ||
      event.request.url.includes('wss://')) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Cache da resposta se for válida
        if (response && response.status === 200) {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return response;
      })
      .catch(() => {
        // Fallback para cache ou página offline
        return caches.match(event.request)
          .then((cachedResponse) => {
            if (cachedResponse) {
              return cachedResponse;
            }
            // Se não estiver em cache, mostrar página offline
            return caches.match(OFFLINE_URL);
          });
      })
  );
});

// Push notifications (preparação para futuro)
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'Auditoria Inteligente';
  const options = {
    body: data.body || 'Nova atualização disponível',
    icon: '/pwa/icon-192.png',
    badge: '/pwa/icon-192.png',
    vibrate: [100, 50, 100],
    data: {
      url: data.url || '/'
    }
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// Click na notificação
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow(event.notification.data.url)
  );
});
