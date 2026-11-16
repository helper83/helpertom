// 헬퍼탐 푸시 구독 저장소 (Cloudflare Workers + KV). 구독 정보만 저장하고 알림 발송은 GitHub Actions가 한다.
// 필요한 설정: KV 바인딩 SUBS, 비밀값 ADMIN_TOKEN, (선택) 변수 ALLOWED_ORIGIN
const DEFAULT_ORIGIN = 'https://helper83.github.io';
const TTL = 120 * 24 * 3600; // 120일 동안 앱을 열지 않으면 구독 정보 자동 삭제
const MAX_DEFAULT = 500; // 구독 정원(무료 한도 기준 추정). 변수 MAX_SUBS로 바꿀 수 있음
const COUNT_KEY = '_count';
const CODE = /^[A-Z]{1,2}\d{2,3}$/;

function json(obj, status, cors) { return new Response(JSON.stringify(obj), { status: status || 200, headers: Object.assign({ 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' }, cors) }); }
async function idOf(endpoint) {
  const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(endpoint));
  return Array.from(new Uint8Array(b)).map(x => x.toString(16).padStart(2, '0')).join('');
}
function cleanCodes(a) { return (Array.isArray(a) ? a : []).filter(c => typeof c === 'string' && CODE.test(c)).slice(0, 3); }
function validSub(s) {
  return s && typeof s.endpoint === 'string' && /^https:\/\/[^\s]{10,500}$/.test(s.endpoint) && s.keys && typeof s.keys.p256dh === 'string' && typeof s.keys.auth === 'string' && s.keys.p256dh.length < 200 && s.keys.auth.length < 100;
}
async function getCount(env) { const n = parseInt(await env.SUBS.get(COUNT_KEY), 10); return n > 0 ? n : 0; }
async function setCount(env, n) { await env.SUBS.put(COUNT_KEY, String(Math.max(0, n))); }
function isAdmin(req, env) {
  const h = req.headers.get('Authorization') || '';
  return !!env.ADMIN_TOKEN && h === 'Bearer ' + env.ADMIN_TOKEN;
}

export default {
  async fetch(req, env) {
    const origin = env.ALLOWED_ORIGIN || DEFAULT_ORIGIN;
    const cors = { 'Access-Control-Allow-Origin': origin, 'Access-Control-Allow-Headers': 'Content-Type, Authorization', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Vary': 'Origin' };
    const p = new URL(req.url).pathname.replace(/\/+$/, '') || '/';
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors });
    try {
      if (p === '/' && req.method === 'GET') return json({ ok: true, service: 'helpertom-push' }, 200, cors);

      // 앱(브라우저)에서 오는 요청: 허용된 출처만
      if ((p === '/subscribe' || p === '/unsubscribe') && req.method === 'POST') {
        if (req.headers.get('Origin') !== origin) return json({ ok: false, error: 'origin' }, 403, cors);
        const text = await req.text();
        if (text.length > 4096) return json({ ok: false, error: 'size' }, 413, cors);
        const b = JSON.parse(text);
        if (p === '/unsubscribe') {
          if (!b.endpoint || typeof b.endpoint !== 'string') return json({ ok: false, error: 'bad' }, 400, cors);
          const uid = await idOf(b.endpoint);
          if (await env.SUBS.get(uid)) { await env.SUBS.delete(uid); await setCount(env, (await getCount(env)) - 1); }
          return json({ ok: true }, 200, cors);
        }
        if (!validSub(b.sub)) return json({ ok: false, error: 'bad' }, 400, cors);
        const id = await idOf(b.sub.endpoint);
        const old = await env.SUBS.get(id, 'json');
        const max = parseInt(env.MAX_SUBS, 10) || MAX_DEFAULT;
        if (!old && (await getCount(env)) >= max) return json({ ok: false, error: 'full', max }, 409, cors); // 정원 초과: 신규 구독만 거절
        const m = b.m || {};
        const rec = {
          sub: { endpoint: b.sub.endpoint, keys: { p256dh: b.sub.keys.p256dh, auth: b.sub.keys.auth } },
          m: { ind: cleanCodes(m.ind), job: cleanCodes(m.job), pub: cleanCodes(m.pub), goal: typeof m.goal === 'string' && CODE.test(m.goal) ? m.goal : '' },
          t: Date.now(),
          last: (old && old.last) || { d: '', u: [] } // 마지막 발송 날짜(KST)와 이미 알린 기사 해시
        };
        await env.SUBS.put(id, JSON.stringify(rec), { expirationTtl: TTL });
        if (!old) await setCount(env, (await getCount(env)) + 1);
        return json({ ok: true }, 200, cors);
      }

      // 발송 작업(GitHub Actions)에서 오는 요청: 관리자 토큰 필요
      if (p.indexOf('/admin/') === 0) {
        if (!isAdmin(req, env)) return json({ ok: false, error: 'auth' }, 401, cors);
        if (p === '/admin/list' && req.method === 'GET') {
          const cursor = new URL(req.url).searchParams.get('cursor') || undefined;
          const r = await env.SUBS.list({ limit: 40, cursor });
          const items = [];
          for (const k of r.keys) { if (k.name === COUNT_KEY) continue; const rec = await env.SUBS.get(k.name, 'json'); if (rec) items.push({ id: k.name, rec }); }
          return json({ ok: true, items, cursor: r.list_complete ? '' : r.cursor, done: !!r.list_complete }, 200, cors);
        }
        if (p === '/admin/apply' && req.method === 'POST') {
          const b = await req.json();
          const puts = (b.puts || []).slice(0, 40), dels = (b.dels || []).slice(0, 40);
          for (const x of puts) await env.SUBS.put(x.id, JSON.stringify(x.rec), { expirationTtl: TTL });
          for (const id of dels) await env.SUBS.delete(id);
          if (Number.isInteger(b.count) && b.count >= 0) await setCount(env, b.count); // 발송기가 실제 구독 수로 보정(만료된 구독 반영)
          return json({ ok: true, puts: puts.length, dels: dels.length, count: await getCount(env) }, 200, cors);
        }
      }
      return json({ ok: false, error: 'not found' }, 404, cors);
    } catch (e) {
      return json({ ok: false, error: 'server' }, 500, cors);
    }
  }
};
