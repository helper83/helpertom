# 새 기사 푸시 알림 설정 (한 번만 하면 됨)

매일 12:30(KST) 하루 최대 1회, 무음 알림. 서버는 Cloudflare 무료 플랜을 쓴다.
※ 화면 메뉴 이름은 Cloudflare·GitHub 개편에 따라 조금 다를 수 있음(확인 필요).

## 1. Cloudflare 워커 만들기
1. https://dash.cloudflare.com/sign-up 에서 무료 계정 가입
2. **Workers & Pages → Create → Worker** → 이름 `helpertom-push` → Deploy
3. **Edit code** → 기존 내용을 모두 지우고 `tools/push/worker.js` 전체를 붙여넣기 → Deploy
4. **Storage & Databases → KV → Create** → 이름 `helpertom-subs`
5. 워커 → **Settings → Bindings → Add → KV namespace** → 변수 이름 `SUBS`, 방금 만든 KV 선택
6. 워커 → **Settings → Variables and Secrets**
   - Secret `ADMIN_TOKEN` = (전달받은 관리자 토큰)
   - Text `ALLOWED_ORIGIN` = `https://helper83.github.io`
7. 워커 주소(`https://helpertom-push.○○○.workers.dev`)를 복사해 개발 담당(Claude)에게 전달 → 앱의 `PUSH_API`에 입력

## 2. GitHub 비밀값 등록
저장소 helper83/helpertom → **Settings → Secrets and variables → Actions → New repository secret**
- `VAPID_PRIVATE_KEY` = (전달받은 비공개 키)
- `PUSH_ADMIN_TOKEN` = (1-6의 ADMIN_TOKEN과 같은 값)

## 3. 시험
1. 폰에서 앱 홈의 **새 기사 알림 받기** → 허용
2. GitHub → Actions → **새 기사 푸시 알림** → Run workflow (force 체크) → 알림 도착 확인
3. 알림이 소리 나면: 폰 설정 → 앱 알림(헬퍼탐/크롬) → 해당 알림 채널을 ‘무음’으로

## 운영 메모
- 무료 한도(Cloudflare KV 쓰기 하루 1,000건): 구독자 1명당 하루 최대 2건 쓰기 → 약 500명까지(추정)
- 구독 정보는 120일간 앱을 열지 않으면 자동 삭제
- 비밀값(VAPID 비공개 키·관리자 토큰)은 저장소 파일·채팅에 남기지 말 것
