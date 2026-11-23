"""배포 전 QA 한 번에 실행 — 실패 항목이 있으면 종료 코드 1.
사용: 저장소 루트에서  python3 -I tools/qa/run_all.py   (환경변수 CHROME_PATH 로 Chrome 경로 지정, 기본 /usr/bin/google-chrome)
점검: ① 정적(핸들러·aria·label) ② 8개 탭·산업·직무 전체 렌더의 JS·콘솔·네트워크 오류 ③ 상세 화면 안 산업·직무 코드 링크 ④ 도움말 선택자 ⑤ 390/768/1280px 가로 넘침·구분 버튼 클릭
"""
import os,re,subprocess,sys,time
from collections import Counter
from playwright.sync_api import sync_playwright
ROOT=os.getcwd(); PORT=8861; CH=os.environ.get('CHROME_PATH','/usr/bin/google-chrome'); fails=[]
def fail(m):
    fails.append(m)
    if len(fails)<=40: print('FAIL',m)
src=open('index.html',encoding='utf-8').read()
# ① 정적
defs=set(re.findall(r'function\s+([A-Za-z_$][\w$]*)',src))|set(re.findall(r'(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function|\()',src))|set(re.findall(r'window\.([A-Za-z_$][\w$]*)\s*=',src))
calls=set()
for m in re.finditer(r'\bon(?:click|change|input|submit|keydown|keyup|focus|blur)\s*=\s*"([^"]*)"',src): calls|=set(re.findall(r'(?<![\w.$])([A-Za-z_$][\w$]*)\s*\(',m.group(1)))
bi={'if','return','function','event','this','confirm','alert','prompt','setTimeout','encodeURIComponent','String','Number','parseInt','Array','JSON'}
ids=set(re.findall(r'\bid=["\']([^"\']+)["\']',src))
x=sorted(c for c in calls if c not in defs and c not in bi)
if x: fail('미정의 핸들러 함수 %s'%x)
x=sorted(a for a in set(re.findall(r'aria-controls="([^"]+)"',src)) if a not in ids)
if x: fail('aria-controls 대상 없음 %s'%x)
x=sorted(a for a in set(re.findall(r'<label[^>]*\bfor="([^"]+)"',src)) if a not in ids)
if x: fail('label for 대상 없음 %s'%x)
srv=subprocess.Popen([sys.executable,'-m','http.server',str(PORT)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
URL='http://localhost:%d/index.html'%PORT
try:
  with sync_playwright() as p:
    b=p.chromium.launch(executable_path=CH,args=['--no-sandbox'])
    pg=b.new_page(viewport={'width':390,'height':900}); errs=[]
    pg.on('pageerror',lambda e:errs.append('JS '+str(e)[:150]))
    pg.on('console',lambda m:errs.append('콘솔 '+m.text[:150]) if m.type=='error' else None)
    pg.on('response',lambda r:errs.append('HTTP %d %s'%(r.status,r.url[-60:])) if r.status>=400 else None)
    pg.goto(URL); pg.wait_for_timeout(2500)
    pages=pg.evaluate("[...document.querySelectorAll('section.page')].map(s=>s.id)")
    for pid in pages: pg.evaluate("openPage('%s')"%pid); pg.wait_for_timeout(200)
    ind=pg.evaluate("DB.industries.map(i=>i.code)")
    if not ind: fail('산업 목록을 읽지 못함')
    job=pg.evaluate("DB.jobs.map(j=>j.code)"); pg.evaluate("openPage('industryPage')")
    for c in ind:
        r=pg.evaluate("async(c)=>{try{showIndustry(c);const el=document.getElementById('industryDetail');for(let i=0;i<30;i++){await new Promise(r=>setTimeout(r,100));if(el.innerText.length>=200)break}return el.innerText.length}catch(e){return -1}}",c)
        if r<200: fail('산업 %s 상세 렌더 이상(%s)'%(c,r))
    pg.evaluate("openPage('jobPage')")
    for c in job:
        r=pg.evaluate("async(c)=>{try{showJob(c);const el=document.getElementById('jobDetail');for(let i=0;i<30;i++){await new Promise(r=>setTimeout(r,60));if(el.innerText.length>=200)break}return el.innerText.length}catch(e){return -1}}",c)
        if r<200: fail('직무 %s 상세 렌더 이상(%s)'%(c,r))
        # ③ 코드 링크
        for h in set(pg.evaluate("[...document.getElementById('jobDetail').querySelectorAll('[onclick]')].map(e=>e.getAttribute('onclick'))")):
            for m in re.finditer(r"'([FJ]\d{2,3})'",h):
                t=m.group(1)
                if (t[0]=='F' and t not in ind) or (t[0]=='J' and t not in job): fail('깨진 코드 링크 %s → %s'%(c,t))
    for e in errs[:10]: fail(e)
    # ④ 도움말 선택자
    sels=set(re.findall(r"\['(#[A-Za-z][\w-]*(?: [^',]*)?)',",src))
    for s in sorted(sels):
        if s.startswith('#kt-') or re.fullmatch(r'#[0-9a-fA-F]{3,6}',s): continue
        try:
            if pg.evaluate("s=>!document.querySelector(s)",s): fail('도움말 선택자가 화면에 없음 %s'%s)
        except Exception: fail('잘못된 선택자 %s'%s)
    pg.close()
    # ⑤ 3개 폭 클릭·넘침
    for w in (390,768,1280):
        pg=b.new_page(viewport={'width':w,'height':900}); e2=[]
        pg.on('pageerror',lambda e:e2.append(str(e)[:120])); pg.goto(URL); pg.wait_for_timeout(2500)
        pg.add_style_tag(content='#discModal,.modal-back,.overlay,.guide-pop{display:none!important}')
        for pid in pages:
            pg.evaluate("openPage('%s')"%pid); pg.wait_for_timeout(200)
            if pg.evaluate("document.documentElement.scrollWidth-innerWidth")>0: fail('가로 넘침 %dpx %s'%(w,pid))
            btns=pg.locator('#kt-%s button'%pid)
            for i in range(btns.count()):
                try: btns.nth(i).click(timeout=2000); pg.wait_for_timeout(150)
                except Exception: fail('버튼 클릭 불가 %dpx %s#%d'%(w,pid,i))
                if pg.evaluate("document.documentElement.scrollWidth-innerWidth")>0: fail('가로 넘침 %dpx %s/%d'%(w,pid,i))
        for e in e2[:5]: fail('JS %dpx %s'%(w,e))
        pg.close()
    b.close()
finally: srv.terminate()
print('\n결과:', 'FAIL %d건'%len(fails) if fails else 'PASS (이상 없음)'); sys.exit(1 if fails else 0)
