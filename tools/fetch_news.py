#!/usr/bin/env python3
"""헬퍼탐 오늘의 산업 기사 수집기 (GitHub Actions 매일 06:00 KST 실행)
- 산업(F01~F60)별로 기사 제목·언론사·시각·링크만 모아 data/news/latest.json 에 저장 (본문은 저장하지 않음)
- 기준 기간: 오늘 06:00(KST) 직전 24시간
- 출처: Google News RSS(키 불필요) + 네이버 뉴스 검색 API(NAVER_CLIENT_ID/SECRET 이 있을 때만)
- 산업당 최대 5건, 같은 언론사 최대 2건, 제목 중복 제거
"""
import json, os, re, sys, time, html, email.utils, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KST = timezone(timedelta(hours=9))
MAX_PER_IND, MAX_PER_PRESS = 5, 2
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

def google_items(terms):
    q = ' OR '.join('"%s"' % t if ' ' in t else t for t in terms) + ' when:2d'
    url = 'https://news.google.com/rss/search?q=%s&hl=ko&gl=KR&ceid=KR:ko' % urllib.parse.quote(q)
    b = http_get(url)
    return parse_google(b) if b else []

def naver_items(terms):
    if not (NID and NSEC):
        return []
    out = []
    for t in terms[:2]:
        url = 'https://openapi.naver.com/v1/search/news.json?query=%s&display=30&sort=date' % urllib.parse.quote(t + ' 산업' if len(t) <= 3 else t)
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

def pick(g, n, start, end):
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
        if len(out) >= MAX_PER_IND:
            break
    return sorted(out, key=lambda x: x['dt'], reverse=True)

def main():
    inds = load_industries()
    start, end = window()
    print('기준 기간: %s ~ %s (KST)' % (start.strftime('%m-%d %H:%M'), end.strftime('%m-%d %H:%M')))
    result, total = {}, 0
    for code, name in inds.items():
        terms = terms_of(name)
        sel = pick(google_items(terms), naver_items(terms), start, end)
        result[code] = [{'t': x['t'], 's': x['s'], 'd': x['dt'].strftime('%Y-%m-%dT%H:%M'), 'u': x['u']} for x in sel]
        total += len(sel)
        print('%s %-24s %d건' % (code, name, len(sel)))
        time.sleep(0.4)
    if total == 0:
        sys.exit('수집된 기사가 0건이라 기존 파일을 유지합니다.')
    doc = {'generated': datetime.now(KST).strftime('%Y-%m-%dT%H:%M'), 'window': {'from': start.strftime('%Y-%m-%dT%H:%M'), 'to': end.strftime('%Y-%m-%dT%H:%M')},
           'sources': ['google'] + (['naver'] if NID and NSEC else []), 'items': result}
    path = os.path.join(ROOT, 'data', 'news', 'latest.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    print('저장: %s (%d건)' % (path, total))

if __name__ == '__main__':
    main()
