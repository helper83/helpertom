const CACHE = 'helpertom-v72';
const FILES = [
  './',
  './index.html',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-maskable-512.png'
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => Promise.all(FILES.map(u => fetch(new Request(u, { cache: 'reload' })).then(r => r.ok ? c.put(u, r) : null).catch(() => null)))));
  self.skipWaiting();
});

// v12.124: DB를 나눈 data/ 조각은 설치 직후 백그라운드로 미리 받아 두어 오프라인에서도 쓸 수 있게 한다(실패해도 설치에는 영향 없음)
async function precacheShards() {
  try {
    const meta = await (await fetch('data/shards.json', { cache: 'no-cache' })).json();
    const c = await caches.open(CACHE);
    const urls = meta.files.map(f => f + '?v=' + meta.ver);
    for (let i = 0; i < urls.length; i += 6) {
      await Promise.all(urls.slice(i, i + 6).map(async u => {
        if (await c.match(u)) return;
        try { const r = await fetch(u); if (r.ok) await c.put(u, r); } catch (_) {}
      }));
    }
  } catch (_) {}
}
self.addEventListener('message', e => { if (e.data === 'precache-shards') e.waitUntil(precacheShards()); });

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  // POST 등 비-GET 요청(구글시트 전송 등)은 캐시하지 않고 그대로 네트워크로
  if (e.request.method !== 'GET') return;
  // 페이지(HTML)는 네트워크 우선 → 새 버전이 바로 보이고, 오프라인이면 캐시 사용. 나머지는 캐시 우선
  const isPage = e.request.mode === 'navigate' || /\/(index\.html)?$/.test(new URL(e.request.url).pathname);
  if (isPage) {
    e.respondWith(
      fetch(e.request, { cache: 'no-cache' }).then(r => {
        const copy = r.clone();
        caches.open(CACHE).then(c => c.put(e.request, copy)).catch(() => {});
        return r;
      }).catch(() => caches.match(e.request).then(r => r || caches.match('./index.html')))
    );
    return;
  }
  // v12.137: 사진 퍼즐 목록(manifest.json)은 네트워크 우선 → 사진을 추가·교체해도 바로 반영, 오프라인이면 캐시 사용
  if (/\/data\/(puzzles\/manifest|news\/(latest|extra))\.json$/.test(new URL(e.request.url).pathname)) {
    e.respondWith(fetch(e.request, { cache: 'no-cache' }).then(n => {
      if (n.ok) { const copy = n.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)).catch(() => {}); }
      return n;
    }).catch(() => caches.match(e.request)));
    return;
  }
  // data/ 조각: 캐시 우선, 없으면 받아서 저장
  if (/\/data\/((ind|pub)\/[^/]+\.js|fonts\/[^/]+\.woff2|puzzles\/[^/]+\.(json|jpe?g|webp|png))$/.test(new URL(e.request.url).pathname)) {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request).then(n => {
      if (n.ok) { const copy = n.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)).catch(() => {}); }
      return n;
    })));
    return;
  }
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});
