# 진로 결정 → 수업 나눔 (구글 슬라이드로 보내기) 설정 · v1.21

학습자가 **진로 결정 > 최종 목표 고르기**에서 닉네임·목표 산업·목표 직무·목표 공공기관(선택)과 각 선택 이유를 쓰고
`전송 전 미리보기 → 이 내용으로 제출`을 누르면, 강사 구글 드라이브의 슬라이드에 **닉네임별 슬라이드 1장**이 생깁니다.
같은 닉네임으로 다시 제출하면 그 슬라이드가 새 내용으로 바뀝니다.

## 1회 설정 (helper83@gmail.com)
1. script.google.com → 새 프로젝트 → 아래 코드 붙여넣기
2. 배포 → 새 배포 → 웹 앱 / 실행: 나 / 액세스: 모든 사용자 → URL(…/exec) 복사 (첫 배포 때 권한 승인)
3. index.html의 `var CFG={url:''}`(진로 결정 수업 나눔 스크립트)에 URL 입력 후 배포
4. 첫 제출 때 드라이브에 `헬퍼손 진로 결정 수업 나눔` 슬라이드가 자동 생성됩니다. 공유(링크 보기)해서 수업 화면에 띄우세요.

```js
function doPost(e) {
  var p = e.parameter || {};
  if (p.kind !== 'goal') return ContentService.createTextOutput('bad');
  var c = function (k, n) { return String(p[k] || '').replace(/[\r\n]+/g, ' ').slice(0, n); };
  var nick = c('nick', 12); if (!nick || !c('ind', 80) || !c('job', 80)) return ContentService.createTextOutput('bad');
  var lock = LockService.getScriptLock(); lock.waitLock(20000);
  try {
    var props = PropertiesService.getScriptProperties(), id = props.getProperty('DECK'), deck;
    if (id) { try { deck = SlidesApp.openById(id); } catch (x) { deck = null; } }
    if (!deck) { deck = SlidesApp.create('헬퍼손 진로 결정 수업 나눔'); props.setProperty('DECK', deck.getId());
      deck.getSlides().forEach(function (s) { s.remove(); }); }
    deck.getSlides().forEach(function (s) { if (s.getNotesPage().getSpeakerNotesShape().getText().asString().trim() === 'GOAL:' + nick) s.remove(); });
    var s = deck.appendSlide(SlidesApp.PredefinedLayout.BLANK);
    s.getNotesPage().getSpeakerNotesShape().getText().setText('GOAL:' + nick);
    var W = deck.getPageWidth(), t = s.insertTextBox('🎯 ' + nick, 40, 24, W - 80, 56);
    t.getText().getTextStyle().setFontSize(30).setBold(true).setForegroundColor('#1E5FA8');
    var rows = [['목표 산업', c('ind', 80), c('whyInd', 80)], ['목표 직무', c('job', 80), c('whyJob', 80)]];
    if (c('pub', 80)) rows.push(['목표 공공기관', c('pub', 80), c('whyPub', 80)]);
    var tb = s.insertTable(rows.length + 1, 3, 40, 100, W - 80, 40 * (rows.length + 1));
    ['구분', '선택', '고른 이유'].forEach(function (h, i) { tb.getCell(0, i).getText().setText(h).getTextStyle().setBold(true).setFontSize(16); });
    rows.forEach(function (r, ri) { r.forEach(function (v, ci) { tb.getCell(ri + 1, ci).getText().setText(v || '-').getTextStyle().setFontSize(18); }); });
    var l = s.insertTextBox('산업-직무 연결: ' + (c('link', 20) || '-'), 40, 100 + 52 * (rows.length + 1) + 20, W - 80, 36);
    l.getText().getTextStyle().setFontSize(16).setForegroundColor('#555555');
  } finally { lock.releaseLock(); }
  return ContentService.createTextOutput('ok');
}
```

## 유의
- 브라우저는 no-cors로 보내 성공 여부를 알 수 없습니다. 슬라이드에서 직접 확인하세요.
- 웹앱 URL을 아는 사람은 누구나 제출할 수 있습니다(길이·형식만 제한). 앱 화면에서 이메일·전화번호·주민번호 형태는 차단합니다.
- 슬라이드는 닉네임 기준으로 갱신되므로 같은 닉네임을 두 사람이 쓰면 덮어씁니다.
