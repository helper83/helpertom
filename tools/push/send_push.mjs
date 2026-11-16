// 매일 12:30(KST) GitHub Actions에서 실행: 구독자별로 '아직 알리지 않은 새 기사'가 있으면 하루 1회, 무음 알림 1건을 보낸다.
// 환경변수: VAPID_PRIVATE_KEY, ADMIN_TOKEN (GitHub Secrets) / FORCE=1(같은 날 재발송 허용) / DRY_RUN=1(전송 없이 확인) / PUSH_API(테스트용 주소 덮어쓰기)
import fs from 'node:fs';
import crypto from 'node:crypto';
import webpush from 'web-push';

const root = new URL('../../', import.meta.url).pathname;
const html = fs.readFileSync(root + 'index.html', 'utf8');
const PUSH_API = (process.env.PUSH_API || (html.match(/PUSH_API = '([^']*)'/) || [])[1] || '').replace(/\/+$/, '');
const VAPID_PUBLIC = (html.match(/PUSH_VAPID = '([^']*)'/) || [])[1] || '';
const APP_URL = 'https://helper83.github.io/helpertom/';
const DRY = process.env.DRY_RUN === '1', FORCE = process.env.FORCE === '1';
if (!PUSH_API || !VAPID_PUBLIC) { console.log('푸시 주소/공개키가 앱에 설정되지 않아 건너뜁니다.'); process.exit(0); }
if (!process.env.ADMIN_TOKEN || (!DRY && !process.env.VAPID_PRIVATE_KEY)) { console.error('ADMIN_TOKEN / VAPID_PRIVATE_KEY 비밀값이 없습니다.'); process.exit(1); }
if (!DRY) webpush.setVapidDetails('mailto:hp83@naver.com', VAPID_PUBLIC, process.env.VAPID_PRIVATE_KEY);

const kstToday = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
const read = f => { try { return JSON.parse(fs.readFileSync(root + f, 'utf8')); } catch (e) { return null; } };
const d = read('data/news/latest.json'), x = read('data/news/extra.json');
if (!d || !d.generated) { console.log('기사 파일이 없어 건너뜁니다.'); process.exit(0); }
const kstYesterday = new Date(Date.now() + 9 * 3600e3 - 86400e3).toISOString().slice(0, 10);
/* 수집이 늦어 어제 저녁에야 끝난 기사도 다음 날 12:30에 합쳐서 보낸다(이미 알린 기사는 아래에서 걸러짐). 이틀 이상 묵은 기사는 보내지 않는다. */
if (!FORCE && String(d.generated).slice(0, 10) < kstYesterday) { console.log('최근 이틀 안에 갱신된 기사가 없어 건너뜁니다. (생성: ' + d.generated + ')'); process.exit(0); }

const h8 = u => crypto.createHash('sha1').update(u).digest('hex').slice(0, 8);
// 앱의 새 기사 배지와 같은 규칙: 찜한 산업·직무·기관별 기사 2건(최대 3개씩), 찜이 없으면 목표 산업
function articlesFor(m) {
  const out = [], seen = new Set();
  const add = (src, codes) => (codes || []).forEach(c => ((src || {})[c] || []).slice(0, 2).forEach(a => { if (a && a.u && !seen.has(a.u)) { seen.add(a.u); out.push(a); } }));
  add(d.items, m.ind); add(x && x.jobs, m.job); add(x && x.pub, m.pub);
  if (!out.length && !(m.ind || []).length && !(m.job || []).length && !(m.pub || []).length && m.goal) add(d.items, [m.goal]);
  return out;
}
const api = (path, opt) => fetch(PUSH_API + path, Object.assign({ headers: { Authorization: 'Bearer ' + process.env.ADMIN_TOKEN, 'Content-Type': 'application/json' } }, opt)).then(r => { if (!r.ok) throw new Error(path + ' ' + r.status); return r.json(); });

let cursor = '', total = 0, sent = 0, skipped = 0, removed = 0, failed = 0;
do {
  const page = await api('/admin/list' + (cursor ? '?cursor=' + encodeURIComponent(cursor) : ''));
  const puts = [], dels = [];
  for (const it of page.items) {
    total++;
    const rec = it.rec, last = rec.last || { d: '', u: [] };
    if (!FORCE && last.d === kstToday) { skipped++; continue; }              // 하루 최대 1회
    const arts = articlesFor(rec.m || {});
    const fresh = arts.filter(a => !(last.u || []).includes(h8(a.u)));        // 아직 알리지 않은 기사
    if (!fresh.length) { skipped++; continue; }
    const n = fresh.length;
    const payload = JSON.stringify({ title: '헬퍼탐 · 새 기사 ' + n + '건', body: fresh[0].t + (n > 1 ? ' 외 ' + (n - 1) + '건' : ''), n, url: APP_URL });
    if (DRY) { console.log('[DRY] ' + it.id.slice(0, 6) + ' → ' + payload); sent++; continue; }
    try {
      await webpush.sendNotification(rec.sub, payload, { TTL: 4 * 3600, urgency: 'normal' });
      rec.last = { d: kstToday, u: arts.map(a => h8(a.u)).slice(0, 12) };
      puts.push({ id: it.id, rec }); sent++;
    } catch (e) {
      if (e.statusCode === 404 || e.statusCode === 410) { dels.push(it.id); removed++; } else { failed++; console.log('전송 실패 ' + it.id.slice(0, 6) + ' ' + (e.statusCode || e.message)); }
    }
  }
  if (!DRY && (puts.length || dels.length)) await api('/admin/apply', { method: 'POST', body: JSON.stringify({ puts, dels }) });
  cursor = page.done ? '' : page.cursor;
} while (cursor);
if (!DRY) await api('/admin/apply', { method: 'POST', body: JSON.stringify({ puts: [], dels: [], count: total - removed }) }); // 구독 수 카운터를 실제 값으로 보정
console.log('구독 ' + total + '건 · 발송 ' + sent + ' · 건너뜀 ' + skipped + ' · 만료 삭제 ' + removed + ' · 실패 ' + failed + (DRY ? ' (DRY_RUN)' : ''));
