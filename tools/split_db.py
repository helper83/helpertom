#!/usr/bin/env python3
"""헬퍼탐 DB 분리 도구 (v12.124)

index.html 안의 EMBEDDED_DB(한 줄 JSON)를 '가벼운 인라인 DB + 지연 로딩 shard'로 나눈다.

  python3 tools/split_db.py split --db full_db.json --html index.html --out . --ver v12.124
  python3 tools/split_db.py merge --html index.html --out full_db.json   # 인라인 + shard → 원본 DB 복원

분리 규칙
  - 산업 패키지: 기업(companies) 안의 무거운 필드(HEAVY_COMPANY)만 data/ind/<산업코드>.js 로 이동
  - 공공기관 패키지: 전체를 64개씩 묶어 data/pub/<번호>.js 로 이동
  - 인라인에는 화면 첫 로딩에 필요한 색인만 남긴다
      DB.lazy.publicChunk   기관코드 → shard 번호
      DB.lazy.publicJobIndex 직무코드 → JOB-ALIO 공고 기관(역방향 색인)
      DB.lazy.discPub       오늘의 발견 카드에 쓰는 중앙기관 요약(검증 통과 기관만)
shard 파일 형식(JSONP 방식, file:// 에서도 동작)
  window.__HT_SHARD('ind','F01',{...});  window.__HT_SHARD('pub','07',{...});
"""
import argparse, hashlib, json, os, re, sys

HEAVY_COMPANY = [
    'actualRecruitRoles', 'collegePriorityRoles', 'profile', 'recruitEvidence',
    'recruitRoleMappings', 'talentProfile', 'candidateJobs', 'reverify',
    'collegeRolePolicy', 'claimVerification', 'detailAudit', 'roleResearch',
    'roleReverification',
]
PUB_CHUNK = 64
PREFIX = 'const EMBEDDED_DB ='


def dumps(o):
    return json.dumps(o, ensure_ascii=False, separators=(',', ':'))


def read_html_db(path):
    s = open(path, encoding='utf-8').read()
    i = s.index(PREFIX)
    e = s.index('\n', i)
    body = s[i + len(PREFIX):e].strip()
    if body.endswith(';'):
        body = body[:-1]
    return s, i, e, json.loads(body)


def write_shard(path, kind, key, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write("window.__HT_SHARD('%s','%s',%s);\n" % (kind, key, dumps(data)))


def read_shard(path):
    t = open(path, encoding='utf-8').read().strip()
    m = re.match(r"window\.__HT_SHARD\('([^']*)','([^']*)',(.*)\);$", t, re.S)
    return m.group(1), m.group(2), json.loads(m.group(3))


def do_split(db, html_path, out, ver):
    s, i, e, _ = read_html_db(html_path) if os.path.exists(html_path) else (None,) * 4
    # --- 산업 ---
    ind_files = []
    for code, pkg in db['industryPackages'].items():
        heavy = {}
        for co in pkg.get('companies', []):
            h = {k: co.pop(k) for k in HEAVY_COMPANY if k in co}
            if h:
                heavy[co['id']] = h
        write_shard(os.path.join(out, 'data', 'ind', code + '.js'), 'ind', code, heavy)
        ind_files.append('data/ind/%s.js' % code)
    # --- 공공 ---
    pubs = db['publicPackages']
    codes = sorted(pubs.keys())
    chunk_of, pub_files = {}, []
    for n in range(0, len(codes), PUB_CHUNK):
        key = '%02d' % (n // PUB_CHUNK)
        part = {c: pubs[c] for c in codes[n:n + PUB_CHUNK]}
        for c in part:
            chunk_of[c] = key
        write_shard(os.path.join(out, 'data', 'pub', key + '.js'), 'pub', key, part)
        pub_files.append('data/pub/%s.js' % key)
    # 색인: 직무 → JOB-ALIO 공고 기관 (publicOrgsForJob 과 같은 결과)
    in_idx = {o['pCode'] for t in ('CENTRAL', 'LOCAL') for o in db['public'].get(t, [])}
    jidx = {}
    for pc, raw in pubs.items():
        if raw.get('jobsSource') != 'JOB-ALIO' or pc not in in_idx:
            continue
        for j in raw.get('jobs') or []:
            if not isinstance(j, dict) or not j.get('c'):
                continue
            jidx.setdefault(j['c'], []).append({'pCode': pc, 'title': j.get('t') or '', 'url': j.get('u') or ''})
    # 색인: 오늘의 발견 중앙기관 카드(검증 통과 기관만, 원래 선정 규칙과 동일)
    job_codes = {j['code'] for j in db['jobs']}
    disc = {}
    for o in db['public'].get('CENTRAL', []):
        pk = pubs.get(o['pCode'])
        if not pk:
            continue
        st = str(pk.get('jobAuditStatus') or '')
        if not st or re.match(r'^부분 검증|^NCS 표준 패턴', st):
            continue
        if not ((pk.get('purpose') or pk.get('studentIntro')) and pk.get('officialUrl')):
            continue
        jl = [(x if isinstance(x, str) else x.get('c')) for x in (pk.get('jobs') or [])]
        jl = [c for c in jl if c]
        if not jl or not all(c in job_codes for c in jl):
            continue
        disc[o['pCode']] = {
            'purpose': pk.get('purpose') or '', 'studentIntro': pk.get('studentIntro') or '',
            'business': pk.get('business') or '', 'officialUrl': pk.get('officialUrl') or '',
            'jobAuditStatus': st,
            'jobs': [x if isinstance(x, str) else {'c': x.get('c'), 't': x.get('t') or ''} for x in (pk.get('jobs') or [])],
        }
    db['publicPackages'] = {}
    db['lazy'] = {'ver': ver, 'publicChunk': chunk_of, 'publicJobIndex': jidx, 'discPub': disc}
    # sw.js 가 읽는 shard 목록
    with open(os.path.join(out, 'data', 'shards.json'), 'w', encoding='utf-8') as f:
        json.dump({'ver': ver, 'files': ind_files + pub_files}, f, ensure_ascii=False)
    # index.html 갱신
    if s is not None:
        line = PREFIX + dumps(db) + ';'
        open(html_path, 'w', encoding='utf-8').write(s[:i] + line + s[e:])
    return db


def do_merge(html_path, out_json, base='.'):
    _, _, _, db = read_html_db(html_path)
    for code, pkg in db['industryPackages'].items():
        kind, key, heavy = read_shard(os.path.join(base, 'data', 'ind', code + '.js'))
        for co in pkg.get('companies', []):
            co.update(heavy.get(co['id'], {}))
    pubs = {}
    for fn in sorted(os.listdir(os.path.join(base, 'data', 'pub'))):
        _, _, part = read_shard(os.path.join(base, 'data', 'pub', fn))
        pubs.update(part)
    db['publicPackages'] = pubs
    db.pop('lazy', None)
    json.dump(db, open(out_json, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    return db


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['split', 'merge'])
    ap.add_argument('--db')
    ap.add_argument('--html', default='index.html')
    ap.add_argument('--out', default='.')
    ap.add_argument('--ver', default='v12.124')
    a = ap.parse_args()
    if a.cmd == 'split':
        db = json.load(open(a.db, encoding='utf-8'))
        do_split(db, a.html, a.out, a.ver)
        print('split ok')
    else:
        do_merge(a.html, a.out, os.path.dirname(os.path.abspath(a.html)))
        print('merge ok')
