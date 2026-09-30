# 구글 시트 콘텐츠 예제

**구글 시트에 적은 목록을 GitHub Actions가 읽어 검색·필터가 되는 웹페이지로 만들고, GitHub Pages에 배포하는 예제**입니다. 4주차 ‘오늘의 한 문장’의 `데이터 → Actions → Pages` 흐름에서 데이터 자리를 `quotes.json` 대신 구글 시트로 바꿨습니다. Python 표준 라이브러리만 사용합니다.

```text
구글 시트 편집 → 웹에 게시(CSV 주소)
  → main에 저장 / 버튼으로 실행 / 예약 시각 도달
  → Actions가 main.py 실행: CSV 읽기 → 열 확인 → 공개 행 고르기 → HTML 생성
  → GitHub Pages에 배포
```

## 파일 역할

| 파일 | 역할 |
|---|---|
| `sample.csv` | 시트와 같은 열 구조의 샘플. 시트를 연결하기 전 로컬 실행에 씁니다 |
| `site.json` | 서비스 제목·설명·출처 문구 |
| `main.py` | CSV 읽기, 열 확인, 공개 행 선택, 오늘의 추천, 검색·필터 화면 생성 |
| `.github/workflows/sheet_site.yml` | 실행 조건, 저장소 변수 `SHEET_CSV_URL` 전달, Pages 배포 |
| `extras/sheet-live.html` | 선택 실습: 방문할 때마다 브라우저가 시트를 읽는 방식 |

## 시트의 열 약속

1행에는 아래 열 이름을 그대로 적습니다. 순서는 바뀌어도 됩니다.

| 열 | 필수 | 내용 |
|---|---|---|
| 제목 | 필수 | 카드 제목 |
| 내용 | 필수 | 한두 문장 설명 |
| 분류 | 선택 | 필터에 쓰는 분류. 비우면 ‘기타’ |
| 링크 | 선택 | 자세히 보기 주소. `http://` 또는 `https://`로 시작 |
| 공개 | 필수 | `Y`인 행만 웹에 표시. 쓰는 중인 행은 `N` |

## 1. 로컬에서 먼저 실행

```bash
python3 main.py --output _site/index.html
```

`_site/index.html`을 브라우저로 열어 검색·분류 필터를 확인합니다. 아직 시트를 연결하지 않았으므로 `sample.csv`를 읽습니다.

## 2. 구글 시트 만들고 게시하기

1. 구글 시트를 새로 만들고 `sample.csv`를 가져오거나(파일 → 가져오기) 1행에 열 이름을 적습니다.
2. 함께 고칠 사람이 있으면 편집 권한을 줍니다(공유 → 이메일 → 편집자).
3. 파일 → 공유 → **웹에 게시** → 게시할 시트 선택 → 형식 **쉼표로 구분된 값(.csv)** → 게시.
4. 나타난 주소를 복사합니다. `.../pub?...output=csv`로 끝나는 주소입니다.

## 3. 저장소에 연결하기

1. 저장소 Settings → Secrets and variables → Actions → **Variables** 탭 → New repository variable
2. Name: `SHEET_CSV_URL`, Value: 2-4에서 복사한 주소 → Add variable
3. Settings → Pages → Source가 **GitHub Actions**인지 확인합니다.
4. Actions → Sheet Content Site → Run workflow로 실행합니다.
5. build·deploy 성공 뒤 공개 주소에서 바닥글의 ‘데이터: 구글 시트(웹에 게시한 CSV)’와 생성 시각을 확인합니다.

시트를 고친 뒤에는 워크플로를 다시 실행해야 웹에 반영됩니다. 매일 자동으로 다시 읽으려면 워크플로의 `schedule` 두 줄 앞 `#`을 지웁니다.

## 4. 검증할 것

| 상황 | 기대 결과 |
|---|---|
| 정상 | 공개 행 수만큼 카드가 보이고 바닥글에 시트 출처가 표시됨 |
| 공개 N 행 | 웹에 나오지 않고 바닥글에 ‘비공개 n개 제외’ |
| 검색 결과 없음 | ‘조건에 맞는 항목이 없습니다’ 안내 |
| 열 이름을 바꿈 | build 실패, 로그에 ‘필수 열이 없습니다’와 현재 열 목록 |
| 링크에 `https://` 없음 | build 실패, 로그에 행 번호와 이유 |
| 휴대전화 폭 | 가로 넘침 없이 카드가 한 줄로 쌓임 |

실패 검증은 복사한 시트나 로컬 CSV로 하고, 끝나면 정상 데이터로 되돌려 다시 실행합니다.

## 공개 범위

웹에 게시한 CSV는 주소를 아는 누구나 읽을 수 있습니다. 연락처·학번·개인 메모처럼 공개하면 안 되는 내용은 시트에 적지 않습니다. README에는 **웹에 게시한 CSV 주소만** 적고, 편집 주소는 적지 않습니다.

## 볼 때 읽기(선택)

`extras/sheet-live.html`은 방문자가 페이지를 열 때마다 브라우저가 시트를 읽습니다. 시트를 고치면 새로고침만으로 반영되지만, 읽는 동안 빈 화면이 잠깐 보이고 시트 주소에 문제가 있으면 방문자 화면에서 오류가 납니다. 파일 안의 `CSV_URL`을 바꾸고 로컬 서버나 GitHub Pages에서 엽니다.

## 공식 문서

- 구글 문서도구 파일 게시: https://support.google.com/docs/answer/183965?hl=ko
- GitHub Actions 변수: https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-variables
- Pages 사용자 지정 워크플로: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
