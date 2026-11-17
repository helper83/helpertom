import json,sys
from playwright.sync_api import sync_playwright
out={}
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    pg=b.new_page(viewport={'width':390,'height':900})
    errs=[];fails=[];cons=[]
    pg.on('pageerror',lambda e:errs.append(str(e)[:200]))
    pg.on('console',lambda m:cons.append(m.text[:200]) if m.type=='error' else None)
    pg.on('requestfailed',lambda r:fails.append(r.url[-80:]))
    pg.on('response',lambda r:fails.append(str(r.status)+' '+r.url[-80:]) if r.status>=400 else None)
    pg.goto('http://localhost:8846/index.html'); pg.wait_for_timeout(2500)
    pages=pg.evaluate("[...document.querySelectorAll('section.page')].map(s=>s.id)")
    out['pages']=pages
    res={}
    for pid in pages:
        pg.evaluate(f"openPage('{pid}')"); pg.wait_for_timeout(350)
        res[pid]=pg.evaluate("(pid)=>({act:document.getElementById(pid).classList.contains('active')||getComputedStyle(document.getElementById(pid)).display!=='none',sw:document.documentElement.scrollWidth-innerWidth,len:document.getElementById(pid).innerText.length})",pid)
    out['pageState']=res
    # 모든 산업·직무 상세 렌더
    bad=[]
    codes=pg.evaluate("DB.industries.map(i=>i.code)")
    for c in codes:
        pg.evaluate(f"openPage('industryPage')")
        r=pg.evaluate("async(c)=>{try{showIndustry(c);await new Promise(r=>setTimeout(r,250));const t=document.getElementById('industryDetail').innerText;return {l:t.length,warn:/찾지 못|불러오지 못|실패/.test(t)}}catch(e){return {err:String(e)}}}",c)
        if r.get('err') or r.get('warn') or r.get('l',0)<200: bad.append(('ind',c,r))
    jc=pg.evaluate("DB.jobs.map(j=>j.code)")
    for c in jc:
        pg.evaluate("openPage('jobPage')")
        r=pg.evaluate("async(c)=>{try{showJob(c);await new Promise(r=>setTimeout(r,120));const t=document.getElementById('jobDetail').innerText;return {l:t.length,warn:/찾지 못|불러오지 못|실패/.test(t)}}catch(e){return {err:String(e)}}}",c)
        if r.get('err') or r.get('warn') or r.get('l',0)<200: bad.append(('job',c,r))
    out['bad']=bad
    out['errs']=errs[:10];out['cons']=cons[:10];out['fails']=fails[:15]
    print(json.dumps(out,ensure_ascii=False,indent=1))
    b.close()
