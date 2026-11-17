import json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for w in (390,768,1280):
        pg=b.new_page(viewport={'width':w,'height':900}); errs=[]
        pg.on('pageerror',lambda e:errs.append(str(e)[:150]))
        pg.on('dialog',lambda d:d.dismiss())
        pg.goto('http://localhost:8846/index.html'); pg.wait_for_timeout(2500); pg.add_style_tag(content='#discModal,.modal-back,.overlay,.guide-pop{display:none!important}')
        hs=[]; n=0
        for pid in pg.evaluate("[...document.querySelectorAll('section.page')].map(s=>s.id)"):
            pg.evaluate(f"openPage('{pid}')"); pg.wait_for_timeout(250)
            hs.append((pid,pg.evaluate("document.documentElement.scrollWidth-innerWidth")))
            # 해당 페이지 안의 종류 선택 버튼(kt-*) 모두 클릭
            btns=pg.locator(f"#kt-{pid} button")
            for i in range(btns.count()):
                try: btns.nth(i).click(timeout=1500); pg.wait_for_timeout(200); n+=1
                except Exception as e: errs.append(f'click {pid}#{i} {str(e)[:60]}')
                hs.append((pid+'/'+str(i),pg.evaluate("document.documentElement.scrollWidth-innerWidth")))
        # 홈 리스트 항목 클릭
        pg.evaluate("openPage('homePage')"); pg.wait_for_timeout(300)
        rows=pg.locator('#discList [data-disc]'); 
        for i in range(rows.count()):
            try: rows.nth(i).click(timeout=1500); pg.wait_for_timeout(300); pg.keyboard.press('Escape'); n+=1
            except Exception as e: errs.append(f'row{i} {str(e)[:60]}')
        print(w,'클릭',n,'가로넘침',[x for x in hs if x[1]>0],'오류',errs[:6])
        pg.close()
    b.close()
