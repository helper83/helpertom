import re,json
from playwright.sync_api import sync_playwright
src=open('index.html',encoding='utf-8').read()
sels=set(re.findall(r"\['(#[A-Za-z][\w-]*(?: [^',]*)?)',",src))
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    pg=b.new_page(viewport={'width':1280,'height':900}); errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e)[:160]))
    pg.goto('http://localhost:8846/index.html'); pg.wait_for_timeout(2500)
    miss=[]
    for s in sorted(sels):
        if s.startswith('#kt-'): continue
        try:
            if pg.evaluate("s=>!document.querySelector(s)",s): miss.append(s)
        except Exception as e: miss.append('ERR '+s)
    print('TIPS/TOUR/TAB 선택자 중 DOM에 없는 것:',miss)
    # 모든 data-page 버튼 → 해당 페이지 열림
    r=pg.evaluate("""()=>{const o=[];document.querySelectorAll('.stop[data-page]').forEach(b=>{const id=b.dataset.page;if(!document.getElementById(id))o.push(id)});return o}""")
    print('없는 페이지 탭:',r,errs)
    b.close()
