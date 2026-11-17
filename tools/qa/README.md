# 배포 전 QA 도구 (tools/qa)

한 줄 요약: 저장소 루트에서 서버를 켜고 아래 스크립트를 순서대로 돌리면, 전 탭·전 산업·전 직무의 오류와 깨진 링크를 한 번에 점검합니다.

```bash
python3 -m http.server 8846 &            # 루트에서 실행
python3 -I tools/qa/static_check.py index.html   # 핸들러·id·aria 정적 점검
python3 -I tools/qa/run_all.py            # 위 5개를 한 번에 실행하고 실패 시 종료 코드 1 (GitHub Actions: .github/workflows/qa.yml)
python3 -I tools/qa/qa_links.py          # 상세 화면 안 산업·직무 코드 링크 유효성
python3 -I tools/qa/qa_selectors.py      # 도움말(TIPS/TOUR)·탭 선택자가 DOM에 있는지
python3 -I tools/qa/qa_click.py          # 390/768/1280px 구분 버튼 클릭·가로 넘침
pkill -f "http.server 8846"
```

- 필요: `pip install playwright` + Chrome (스크립트 안 `executable_path`를 환경에 맞게 수정)
- 해석 주의: qa_all의 `bad`에 "실패 로그" 같은 정상 문구가 걸릴 수 있음, qa_selectors의 `#dff6ff` 등 색상 코드는 오탐
- 점검 중 환영 팝업이 클릭을 가리면 qa_click처럼 `#discModal`을 숨겨서 실행

## 자동 실행
- `.github/workflows/qa.yml`: `index.html`·`sw.js`·`data/`·`tools/qa/`를 올리면 GitHub Actions가 `run_all.py`를 돌립니다. 실패하면 커밋에 ✗ 표시와 메일 알림이 옵니다.
- 주의: GitHub Pages 배포는 별도로 진행되어 QA 실패가 배포를 막지는 않습니다(실패 알림을 받고 수정 후 다시 올리는 방식).
