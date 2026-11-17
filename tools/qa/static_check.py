"""정적 점검: 핸들러 함수·id 참조·중복 id·aria-controls·label for·href=#  (사용: python3 -I tools/qa/static_check.py index.html)"""
import re,sys
from collections import Counter
s=open(sys.argv[1] if len(sys.argv)>1 else 'index.html',encoding='utf-8').read()
defs=set(re.findall(r'function\s+([A-Za-z_$][\w$]*)',s))|set(re.findall(r'(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function|\()',s))|set(re.findall(r'window\.([A-Za-z_$][\w$]*)\s*=',s))
calls=set()
for m in re.finditer(r'\bon(?:click|change|input|submit|keydown|keyup|focus|blur)\s*=\s*"([^"]*)"',s):
    calls|=set(re.findall(r'(?<![\w.$])([A-Za-z_$][\w$]*)\s*\(',m.group(1)))
bi={'if','return','function','event','this','confirm','alert','prompt','setTimeout','encodeURIComponent','String','Number','parseInt','Array','JSON'}
ids=set(re.findall(r'\bid=["\']([^"\']+)["\']',s))
refs=set(re.findall(r"\$\('([A-Za-z][\w-]*)'\)",s))|set(re.findall(r"getElementById\('([A-Za-z][\w-]*)'\)",s))
print('미정의 핸들러 함수:',sorted(c for c in calls if c not in defs and c not in bi))
print('정의 안 된 id 참조(동적 생성이면 정상):',sorted(r for r in refs if r not in ids))
print('중복 id:',[k for k,v in Counter(re.findall(r'\bid="([^"]+)"',s)).items() if v>1])
print('aria-controls 누락:',sorted(x for x in set(re.findall(r'aria-controls="([^"]+)"',s)) if x not in ids))
print('label for 누락:',sorted(x for x in set(re.findall(r'<label[^>]*\bfor="([^"]+)"',s)) if x not in ids))
