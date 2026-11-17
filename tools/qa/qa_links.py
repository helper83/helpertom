import json,re
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    pg=b.new_page(viewport={'width':390,'height':900}); errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e)[:200]))
    pg.goto('http://localhost:8846/index.html'); pg.wait_for_timeout(2500)
    for c in ('J45','J49'):
        pg.evaluate("openPage('jobPage')"); pg.evaluate(f"showJob('{c}')"); pg.wait_for_timeout(300)
        t=pg.evaluate("document.getElementById('jobDetail').innerText")
        print(c,[t[max(0,m.start()-25):m.end()+15].replace('\n',' ') for m in re.finditer('찾지 못|불러오지 못|실패',t)])
    ind=set(pg.evaluate("DB.industries.map(i=>i.code)")); job=set(pg.evaluate("DB.jobs.map(j=>j.code)"))
    # 상세 화면 안의 모든 onclick 대상 코드 확인 + 실제 클릭 실행
    broken=[];tested=0
    def scan(page,fn,codes,kind):
        global tested
        for c in codes:
            pg.evaluate(f"openPage('{page}')"); pg.evaluate(f"{fn}('{c}')"); pg.wait_for_timeout(280)
            box={'industryPage':'industryDetail','jobPage':'jobDetail'}[page]
            hs=pg.evaluate("(b)=>[...document.getElementById(b).querySelectorAll('[onclick]')].map(e=>e.getAttribute('onclick'))",box)
            for h in set(hs):
                for m in re.finditer(r"'([FJ]\d{2,3})'",h):
                    t=m.group(1); ok=(t in ind) if t[0]=='F' else (t in job)
                    if not ok: broken.append((kind,c,h[:90]))
    scan('industryPage','showIndustry',sorted(ind),'ind')
    scan('jobPage','showJob',sorted(job),'job')
    print('깨진 코드 링크:',broken[:20],len(broken))
    print('errs',errs[:5])
    b.close()
