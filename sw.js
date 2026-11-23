const CACHE = 'helpertom-v126';
const META = 'helpertom-meta', META_URL = './__news-meta'; // v12.201: 새 기사 배지용 기록(앱이 저장, 활성화 때 지우지 않음)
const FILES = [
  './',
  './index.html',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/badge-96.png',
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
      Promise.all(keys.filter(k => k !== CACHE && k !== META).map(k => caches.delete(k)))
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
  if (/\/data\/((ind|pub|ai)\/[^/]+\.js|fonts\/[^/]+\.woff2|puzzles\/[^/]+\.(json|jpe?g|webp|png))$/.test(new URL(e.request.url).pathname)) {
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

// v12.201: 앱이 닫혀 있는 동안 새 기사 수를 세어 앱 아이콘 배지만 갱신(알림·소리 없음). 안드로이드 설치형 앱의 periodicsync 지원 시에만 동작
self.addEventListener('periodicsync', e => { if (e.tag === 'helpertom-news') e.waitUntil(checkNewsBadge()); });
async function checkNewsBadge() {
  try {
    const mr = await (await caches.open(META)).match(META_URL);
    if (!mr) return;
    const meta = await mr.json(), m = meta.m || {}, seen = new Set(meta.seen || []);
    const [d, x] = await Promise.all(['data/news/latest.json', 'data/news/extra.json'].map(u => fetch(u, { cache: 'no-cache' }).then(r => r.ok ? r.json() : null).catch(() => null)));
    if (!d && !x) return;
    const out = new Set();
    const add = (src, codes) => (codes || []).forEach(c => ((src || {})[c] || []).slice(0, 2).forEach(a => { if (a && a.u) out.add(a.u); }));
    add(d && d.items, m.ind); add(x && x.jobs, m.job); add(x && x.pub, m.pub);
    if (!(m.ind || []).length && !(m.job || []).length && !(m.pub || []).length && m.goal) add(d && d.items, [m.goal]);
    const n = [...out].filter(u => !seen.has(u)).length;
    if (n > 0) { if (self.navigator && navigator.setAppBadge) await navigator.setAppBadge(n); }
    else if (self.navigator && navigator.clearAppBadge) await navigator.clearAppBadge();
  } catch (_) {}
}

// v12.202: 새 기사 푸시 알림(매일 12:30 KST, 하루 최대 1회). 소리·진동 없는 알림 1건 + 아이콘 배지 숫자
self.addEventListener('push', e => {
  let p = {};
  try { p = e.data ? e.data.json() : {}; } catch (_) {}
  const jobs = [self.registration.showNotification(p.title || '헬퍼탐 · 새 기사', {
    body: p.body || '', icon: './icons/icon-192.png', badge: './icons/badge-96.png',
    tag: 'helpertom-news', silent: true, data: { url: p.url || './' }
  })];
  if (p.n > 0 && self.navigator && navigator.setAppBadge) jobs.push(navigator.setAppBadge(p.n).catch(() => {}));
  e.waitUntil(Promise.all(jobs));
});
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || './', self.registration.scope).href;
  e.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
    for (const c of list) { if (c.url.indexOf(self.registration.scope) === 0 && 'focus' in c) return c.focus(); }
    return clients.openWindow(url);
  }));
});
