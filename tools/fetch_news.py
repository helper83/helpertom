#!/usr/bin/env python3
"""헬퍼탐 오늘의 기사 수집기 (GitHub Actions 매일 06:00 KST 실행)
- 산업(F01~F60)별로 기사 제목·언론사·시각·링크만 모아 data/news/latest.json 에 저장 (본문은 저장하지 않음)
- 직무(J01~)와 중앙 공공기관(C001~)은 data/news/extra.json 에 따로 저장 (기사가 있는 항목만, 항목당 최대 3건)
- 기준 기간: 오늘 06:00(KST) 직전 24시간
- 출처: Google News RSS(키 불필요) + 네이버 뉴스 검색 API(NAVER_CLIENT_ID/SECRET 이 있을 때만)
- 산업당 최대 5건, 같은 언론사 최대 2건, 제목 중복 제거
- 24시간 기준 2건 이하인 산업은 48시간으로 넓혀 다시 선정(결과의 ext 목록)
- 산업별 검색어(q)·제목 매칭어(m)·제외어(x)는 tools/news_keywords.json 에서 관리
"""
import json, os, re, sys, time, html, email.utils, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KST = timezone(timedelta(hours=9))
MAX_PER_IND, MAX_PER_PRESS, MIN_OK = 5, 2, 3
UA = 'Mozilla/5.0 (compatible; HelperTomNewsBot/1.0; +https://helper83.github.io/helpertom/)'
NID, NSEC = os.environ.get('NAVER_CLIENT_ID', ''), os.environ.get('NAVER_CLIENT_SECRET', '')

def load_industries():
    src = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    out = {}
    for code, name in re.findall(r'"code":"(F\d\d)","name":"([^"]+)"', src):
        out.setdefault(code, name)
    if len(out) < 50:
        sys.exit('산업 목록을 읽지 못했습니다: %d건' % len(out))
    return out

def load_jobs():
    src = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    out = {}
    for code, name in re.findall(r'"code":"(J\d{2,3})","name":"([^"]+)"', src):
        out.setdefault(code, name)
    return out

def load_public():
    src = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    out = {}
    for code, name in re.findall(r'"pCode":"(C\d{3})","name":"([^"]+)"', src):
        out.setdefault(code, name)
    return out

JOB_STOP = {'관리', '운영', '개발', '기획', '영업', '구매', '지원', '서비스', '연구', '분석', '설계', '제작', '교육', '사무', '행정'}
JOB_CTX = '직무 OR 직업 OR 채용 OR 인력 OR 전문가'
JOB_BAD = ['인사발령', '정기인사', '임원인사', '승진인사', '인사이동', '인사 발령', '부고', '결혼']

def job_terms(name):
    base = re.sub(r'\([^)]*\)', '', name)
    ts = [t.strip() for t in re.split(r'[·,/]', base) if len(t.strip()) >= 2]
    good = [t for t in ts if t not in JOB_STOP]
    return (good or ts or [name])[:3]

def pub_terms(name):
    n = re.sub(r'^\s*[\(（㈜][^)）]*[\)）]\s*|㈜', '', name).strip()
    alts = [n]
    if n.startswith('한국') and len(n) - 2 >= 3:
        alts.append(n[2:])
    return n, alts

def load_keywords():
    try:
        d = json.load(open(os.path.join(ROOT, 'tools', 'news_keywords.json'), encoding='utf-8'))
        return d.get('_global_exclude', []), d.get('industries', {})
    except Exception as e:
        print('! 키워드 파일을 읽지 못해 산업명 기반으로 진행: %s' % e, file=sys.stderr)
        return [], {}

def relevant(title, kw, gx):
    t = title.lower()
    if any(x.lower() in t for x in gx + kw.get('x', [])):
        return False
    keys = kw.get('q', []) + kw.get('m', [])
    return True if not keys else any(k.lower() in t for k in keys)

def terms_of(name):
    ts = []
    for t in re.split(r'[·,/]', re.sub(r'\([^)]*\)', '', name)):
        t = t.strip()
        if len(t) >= 2 and t not in ts:
            ts.append(t)
    return ts[:3]

def window(now=None):
    now = now or datetime.now(KST)
    end = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if end > now:
        end -= timedelta(days=1)
    return end - timedelta(days=1), end

def http_get(url, headers=None, tries=3):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=dict({'User-Agent': UA}, **(headers or {})))
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read()
        except Exception as e:
            if k == tries - 1:
                print('  ! 실패 %s (%s)' % (url[:90], e), file=sys.stderr)
                return None
            time.sleep(1.5 * (k + 1))

def clean(t):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', t or ''))).strip()

def parse_google(xml_bytes):
    items = []
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return items
    for it in root.iter('item'):
        title, link, pub = clean(it.findtext('title')), (it.findtext('link') or '').strip(), it.findtext('pubDate')
        src = clean(it.findtext('source'))
        if src and title.endswith(' - ' + src):
            title = title[:-len(src) - 3].strip()
        try:
            dt = email.utils.parsedate_to_datetime(pub).astimezone(KST)
        except Exception:
            continue
        if title and link:
            items.append({'t': title, 's': src or '구글뉴스', 'dt': dt, 'u': link, 'k': 'g'})
    return items

def parse_naver(js):
    items = []
    for it in (js or {}).get('items', []):
        try:
            dt = email.utils.parsedate_to_datetime(it.get('pubDate', '')).astimezone(KST)
        except Exception:
            continue
        u = it.get('originallink') or it.get('link') or ''
        host = urllib.parse.urlparse(u).netloc.lower().replace('www.', '')
        t = clean(it.get('title'))
        if t and u:
            items.append({'t': t, 's': host or '네이버뉴스', 'dt': dt, 'u': u, 'k': 'n'})
    return items

def google_items(terms, excl=(), ctx=''):
    q = '(' + ' OR '.join('"%s"' % t if ' ' in t else t for t in terms[:4]) + ')' + (' (%s)' % ctx if ctx else '') + ''.join(' -"%s"' % x if ' ' in x else ' -%s' % x for x in list(excl)[:4]) + ' when:2d'
    url = 'https://news.google.com/rss/search?q=%s&hl=ko&gl=KR&ceid=KR:ko' % urllib.parse.quote(q)
    b = http_get(url)
    return parse_google(b) if b else []

def naver_items(terms):
    if not (NID and NSEC):
        return []
    out = []
    for t in terms[:2]:
        url = 'https://openapi.naver.com/v1/search/news.json?query=%s&display=40&sort=date' % urllib.parse.quote(t + ' 산업' if len(t) <= 3 else t)
        b = http_get(url, {'X-Naver-Client-Id': NID, 'X-Naver-Client-Secret': NSEC})
        if b:
            try:
                out += parse_naver(json.loads(b.decode('utf-8')))
            except Exception:
                pass
        time.sleep(0.2)
    return out

def norm(t):
    return re.sub(r'[^0-9A-Za-z가-힣]', '', t)[:24]

def pick(g, n, start, end, limit=None):
    cand = [x for x in (n + g) if start <= x['dt'] < end]
    n_l = sorted([x for x in cand if x['k'] == 'n'], key=lambda x: x['dt'], reverse=True)
    g_l = [x for x in cand if x['k'] == 'g']          # 구글은 관련도 순서 유지
    order, i = [], 0
    while i < max(len(n_l), len(g_l)):
        if i < len(n_l): order.append(n_l[i])
        if i < len(g_l): order.append(g_l[i])
        i += 1
    seen, press, out = set(), {}, []
    for x in order:
        key = norm(x['t'])
        if key in seen or press.get(x['s'], 0) >= MAX_PER_PRESS:
            continue
        seen.add(key); press[x['s']] = press.get(x['s'], 0) + 1; out.append(x)
        if len(out) >= (limit or MAX_PER_IND):
            break
    return sorted(out, key=lambda x: x['dt'], reverse=True)

def collect_extra(entities, terms_fn, match_fn, ctx, start, end, limit=3, bad=()):
    out, total = {}, 0
    for code, name in entities.items():
        terms, keys = terms_fn(name)
        g = [x for x in google_items(terms, (), ctx) if match_fn(x['t'], keys) and not any(b in x['t'] for b in bad)]
        sel = pick(g, [], start, end, limit)
        if len(sel) < 2:
            wide = pick(g, [], start - timedelta(days=1), end, limit)
            if len(wide) > len(sel):
                sel = wide
        if sel:
            out[code] = [{'t': x['t'], 's': x['s'], 'd': x['dt'].strftime('%Y-%m-%dT%H:%M'), 'u': x['u']} for x in sel]
            total += len(sel)
        time.sleep(0.4)
    return out, total

def main():
    inds = load_industries()
    gx, KW = load_keywords()
    start, end = window()
    print('기준 기간: %s ~ %s (KST)' % (start.strftime('%m-%d %H:%M'), end.strftime('%m-%d %H:%M')))
    result, total, ext = {}, 0, []
    for code, name in inds.items():
        kw = KW.get(code, {})
        terms = kw.get('q') or terms_of(name)
        g = [x for x in google_items(terms, kw.get('x', [])) if relevant(x['t'], kw, gx)]
        n = [x for x in naver_items(terms) if relevant(x['t'], kw, gx)]
        sel = pick(g, n, start, end)
        if len(sel) < MIN_OK:   # 24시간 안에 2건 이하 → 48시간으로 확장
            wide = pick(g, n, start - timedelta(days=1), end)
            if len(wide) > len(sel):
                sel = wide; ext.append(code)
        result[code] = [{'t': x['t'], 's': x['s'], 'd': x['dt'].strftime('%Y-%m-%dT%H:%M'), 'u': x['u']} for x in sel]
        total += len(sel)
        print('%s %-24s %d건' % (code, name, len(sel)))
        time.sleep(0.4)
    if total == 0:
        sys.exit('수집된 기사가 0건이라 기존 파일을 유지합니다.')
    doc = {'generated': datetime.now(KST).strftime('%Y-%m-%dT%H:%M'), 'window': {'from': start.strftime('%Y-%m-%dT%H:%M'), 'to': end.strftime('%Y-%m-%dT%H:%M')},
           'sources': ['google'] + (['naver'] if NID and NSEC else []), 'ext': ext, 'items': result}
    path = os.path.join(ROOT, 'data', 'news', 'latest.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    print('저장: %s (%d건, 48시간 확장 %d개 산업, 0건 %d개)' % (path, total, len(ext), sum(1 for v in result.values() if not v)))
    # 직무·중앙 공공기관 기사 (실패해도 산업 기사는 이미 저장됨)
    try:
        jobs = load_jobs(); pubs = load_public()
        print('직무 %d개 · 중앙 공공기관 %d곳 수집 시작' % (len(jobs), len(pubs)))
        jr, jt = collect_extra(jobs, lambda nm: (job_terms(nm), job_terms(nm)), lambda t, ks: any(k.lower() in t.lower() for k in ks), JOB_CTX, start, end, 3, JOB_BAD)
        pr, pt = collect_extra(pubs, lambda nm: ([pub_terms(nm)[0]], pub_terms(nm)[1]), lambda t, ks: any(k.lower() in t.lower() for k in ks), '', start, end, 3)
        ex = {'generated': doc['generated'], 'window': doc['window'], 'jobs': jr, 'pub': pr}
        with open(os.path.join(ROOT, 'data', 'news', 'extra.json'), 'w', encoding='utf-8') as f:
            json.dump(ex, f, ensure_ascii=False, separators=(',', ':'))
        print('저장: extra.json (직무 %d개 %d건 · 공공기관 %d곳 %d건)' % (len(jr), jt, len(pr), pt))
    except Exception as e:
        print('! 직무·공공기관 기사 수집 실패: %s' % e, file=sys.stderr)

# ---------- 구글뉴스 중계 링크 → 언론사 원문 링크 변환 ----------
# 구글뉴스 링크(news.google.com/rss/articles/...)는 일부 폰·통신망에서 "비정상 트래픽(We're sorry...)" 안내 페이지로 막힌다.
# 선정된 기사만 원문 주소로 바꿔 저장하고(실패하면 기존 구글 링크 그대로 둠), 원래 구글 링크는 g 에 남겨 알림·배지의 '이미 본 기사' 판정이 유지되게 한다.
import base64
RES_PATH = os.path.join(ROOT, 'data', 'news', 'resolved.json')
GN = re.compile(r'^https://news\.google\.com/(?:rss/)?(?:read|articles)/([A-Za-z0-9_-]+)')

def gn_id(u):
    m = GN.match(u or '')
    return m.group(1) if m else ''

def gn_direct(gid):
    """예전 형식 ID는 base64 안에 원문 주소가 그대로 들어 있다(네트워크 불필요). 새 형식(AU_yqL...)은 ''."""
    try:
        raw = base64.urlsafe_b64decode(gid + '=' * (-len(gid) % 4))
    except Exception:
        return ''
    if b'AU_yqL' in raw[:12]:
        return ''
    m = re.search(rb'https?://[\x21-\x7e]+', raw)
    if not m:
        return ''
    u = m.group(0).decode('ascii', 'ignore')
    return '' if 'google.' in urllib.parse.urlparse(u).netloc else u

def gn_fetch(gid):
    """구글뉴스 기사 ID → 원문 주소 (페이지의 서명·시간값을 받아 batchexecute 로 조회). 실패하면 ''."""
    page = http_get('https://news.google.com/rss/articles/%s?hl=ko&gl=KR&ceid=KR:ko' % gid)
    if not page:
        return ''
    txt = page.decode('utf-8', 'ignore')
    sg, ts = re.search(r'data-n-a-sg="([^"]+)"', txt), re.search(r'data-n-a-ts="([^"]+)"', txt)
    if not (sg and ts):
        return ''
    inner = '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"%s",%s,"%s"]' % (gid, ts.group(1), sg.group(1))
    body = 'f.req=' + urllib.parse.quote(json.dumps([[['Fbv4je', inner, None, 'generic']]]))
    try:
        req = urllib.request.Request('https://news.google.com/_/DotsSplashUi/data/batchexecute', data=body.encode('utf-8'),
                                     headers={'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8', 'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode('utf-8', 'ignore')
        part = json.loads(raw.split('\n\n')[1])
        u = json.loads(part[0][2])[1]
        return u if isinstance(u, str) and u.startswith('http') and 'news.google.' not in urllib.parse.urlparse(u).netloc else ''
    except Exception:
        return ''

def resolve_links(fetch=gn_fetch, budget_sec=900, pause=0.5, root=None):
    base = root or ROOT
    paths = [os.path.join(base, 'data', 'news', f) for f in ('latest.json', 'extra.json')]
    res_path = os.path.join(base, 'data', 'news', 'resolved.json')
    docs = {}
    for pth in paths:
        try:
            docs[pth] = json.load(open(pth, encoding='utf-8'))
        except Exception:
            pass
    def arts(doc):
        groups = [doc.get('items') or {}] + [doc.get(k) or {} for k in ('jobs', 'pub')]
        return [a for g in groups for lst in g.values() for a in lst]
    try:
        cache = json.load(open(res_path, encoding='utf-8'))
    except Exception:
        cache = {}
    t0, fails, done, hit, new = time.time(), 0, 0, 0, {}
    for doc in docs.values():
        for a in arts(doc):
            gid = gn_id(a.get('u', ''))
            if not gid:
                continue
            u = cache.get(gid) or gn_direct(gid)
            if not u and fails < 8 and time.time() - t0 < budget_sec:
                u = fetch(gid); time.sleep(pause); done += 1
                fails = 0 if u else fails + 1
            if u:
                new[gid] = u; hit += 1
                a['g'] = a['u']; a['u'] = u
    for pth, doc in docs.items():
        with open(pth, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    with open(res_path, 'w', encoding='utf-8') as f:   # 오늘 쓰인 ID만 남겨 파일이 커지지 않게 함
        json.dump(new, f, ensure_ascii=False, separators=(',', ':'))
    print('원문 링크 변환: %d건 성공 (새로 조회 %d건)%s' % (hit, done, ' · 연속 실패로 조회 중단(구글 링크 유지)' if fails >= 8 else ''))

if __name__ == '__main__':
    main()
    try:
        resolve_links()
    except Exception as e:
        print('! 원문 링크 변환 실패(구글 링크 유지): %s' % e, file=sys.stderr)
