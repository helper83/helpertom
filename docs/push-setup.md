# 새 기사 푸시 알림 설정 (한 번만 하면 됨)

매일 12:30(KST) 하루 최대 1회, 무음 알림. 서버는 Cloudflare 무료 플랜을 쓴다.
※ 화면 메뉴 이름은 2026-11 실제 화면 기준(개편되면 달라질 수 있음 → 확인 필요).

## 1. Cloudflare 워커 만들기
1. https://dash.cloudflare.com/sign-up 에서 무료 계정 가입
2. **Workers & Pages → Create application → Hello World 템플릿**으로 워커 생성 → 이름 `helpertom-push` → Deploy
   - ⚠ **Git 저장소 연결형(Connect to Git)으로 만들지 말 것.** 연결형은 코드 붙여넣기 방식과 맞지 않는다.
3. **Edit code** → 기존 내용을 모두 지우고 `tools/push/worker.js` 전체를 붙여넣기 → Deploy
4. 왼쪽 메뉴 **Storage & databases → Workers KV → Create instance** → 이름 `helpertom-subs`
5. 워커 → **Settings → Bindings → Add → KV namespace** → 변수 이름 **`SUBS`**(코드가 쓰는 이름과 정확히 같아야 함), 방금 만든 KV 선택 → Deploy
6. 워커 → **Settings → Variables and Secrets → Add**
   | 이름 | 종류 | 값 |
   |---|---|---|
   | `ADMIN_TOKEN` | **Secret** | (전달받은 관리자 토큰) |
   | `ALLOWED_ORIGIN` | Text | `https://helper83.github.io` |
   | `MAX_SUBS` (선택) | Text | `500` (생략하면 500) |
7. 워커 주소(`https://helpertom-push.○○○.workers.dev`)를 앱의 `PUSH_API`에 입력(개발 담당에게 전달). 주소를 브라우저로 열어 `{"ok":true,"service":"helpertom-push"}`가 보이면 정상.

## 2. GitHub 비밀값 등록
저장소 helper83/helpertom → **Settings → Secrets and variables → Actions → New repository secret**
- `VAPID_PRIVATE_KEY` = (전달받은 비공개 키)
- `PUSH_ADMIN_TOKEN` = (1-6의 ADMIN_TOKEN과 같은 값)

## 3. 시험
1. 폰에서 앱을 `?push=1` 주소로 한 번 열기(시험판 버튼 표시) → 홈의 **새 기사 알림 받기** → 허용
2. GitHub → Actions → **새 기사 푸시 알림** → Run workflow (force 체크) → 알림 도착 확인
3. 알림이 소리 나면: 폰 설정 → 앱 알림(헬퍼탐/크롬) → 해당 알림 채널을 ‘무음’으로
4. 정식 공개 때는 앱의 `PUSH_BETA`를 `false`로 바꿔 모든 기기에 버튼을 보이게 한다.

## 운영 규칙
- **구독 정원 500명**: 무료 한도(KV 쓰기 하루 1,000건, 구독자당 하루 최대 2건 → 약 500명, 추정) 기준. 정원이 차면 새 구독만 거절하고(기존 구독자는 계속 유지), 앱에는 "구독하지 않아도 앱을 열면 매일 오늘의 기사를 볼 수 있어요" 안내가 뜬다. 한도를 바꾸려면 워커 변수 `MAX_SUBS`만 고친다.
- 구독 수 카운터(`_count`)는 매일 발송 작업이 실제 구독 수로 보정한다(120일 미접속 자동 삭제 반영).
- **수집이 늦은 날**: 12:30에 오늘 기사가 아직 없으면 어제 기사 중 아직 안 알린 것만 보내고, 이미 알린 기사는 다시 보내지 않는다. 그날 늦게 수집된 기사는 **다음 날 12:30에 합쳐서** 발송한다(최근 이틀 안 기사만 대상, 이틀 넘게 묵으면 발송 안 함).
- 구독 정보는 120일간 앱을 열지 않으면 자동 삭제
- 비밀값(VAPID 비공개 키·관리자 토큰)은 저장소 파일·채팅에 남기지 말 것

## 워커 코드를 바꾼 뒤(이번 v12.205 등)
Cloudflare 워커는 GitHub와 자동 연결되지 않는다. `tools/push/worker.js`가 바뀌면 **Edit code에 전체를 다시 붙여넣고 Deploy**해야 새 규칙(정원 500명)이 적용된다.
