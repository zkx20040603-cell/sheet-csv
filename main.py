"""구글 시트(웹에 게시한 CSV)의 콘텐츠로 검색·필터가 되는 웹페이지를 만듭니다. 외부 패키지 불필요.

읽는 순서: --csv 인자 → 환경 변수 SHEET_CSV_URL → 같은 폴더의 sample.csv
잘못된 데이터(게시되지 않은 시트, 빠진 열, 공개 행 없음, 잘못된 링크)는 HTML을 만들기 전에 멈춥니다.
"""

import argparse
import csv
from datetime import date, datetime
from html import escape
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


KST = ZoneInfo("Asia/Seoul")
HERE = Path(__file__).parent
SAMPLE_CSV = HERE / "sample.csv"
SITE_FILE = HERE / "site.json"
REQUIRED = ("제목", "내용", "공개")
OPTIONAL = ("분류", "링크")
PUBLIC_VALUES = {"Y", "YES", "예", "O"}


class DataError(ValueError):
    """시트 데이터가 약속한 형식과 다를 때 사용합니다."""


def load_site(filepath=SITE_FILE):
    with Path(filepath).open(encoding="utf-8") as source:
        site = json.load(source)
    for key in ("title", "description"):
        if not isinstance(site.get(key), str) or not site[key].strip():
            raise DataError(f"site.json의 {key}는 비어 있지 않은 문자열이어야 합니다.")
    return site


def read_source(source):
    """URL이면 내려받고, 파일 경로면 읽어서 CSV 문자열을 돌려줍니다."""
    if re.match(r"https?://", source):
        request = Request(source, headers={"User-Agent": "tdrp-sheet-content/1.0"})
        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read()
        except HTTPError as error:
            raise DataError(f"시트 주소에서 {error.code} 응답을 받았습니다. 웹에 게시했는지, 주소가 맞는지 확인하세요.") from error
        except URLError as error:
            raise DataError(f"시트 주소에 연결하지 못했습니다: {error.reason}") from error
    else:
        raw = Path(source).read_bytes()
    text = raw.decode("utf-8-sig")
    head = text.lstrip()[:200].lower()
    if head.startswith("<!doctype html") or head.startswith("<html"):
        raise DataError("CSV 대신 웹페이지가 왔습니다. 파일 → 공유 → 웹에 게시에서 CSV로 게시한 주소인지 확인하세요.")
    return text


def parse_rows(text):
    """열 이름을 확인하고, 공개=Y인 행만 골라 정리합니다. 시트의 행 번호(머리글=1행)를 함께 남깁니다."""
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise DataError("시트가 비어 있습니다. 1행에 열 이름을 적으세요.")
    header = [name.strip() for name in reader.fieldnames]
    missing = [name for name in REQUIRED if name not in header]
    if missing:
        raise DataError(f"필수 열이 없습니다: {', '.join(missing)} / 현재 열: {', '.join(header) or '(없음)'}")
    items, hidden = [], 0
    for number, row in enumerate(reader, start=2):
        row = {(key or "").strip(): (value or "").strip() for key, value in row.items() if key is not None}
        if not any(row.values()):
            continue
        if row.get("공개", "").upper() not in PUBLIC_VALUES:
            hidden += 1
            continue
        for name in ("제목", "내용"):
            if not row.get(name):
                raise DataError(f"{number}행의 {name}이(가) 비어 있습니다.")
        link = row.get("링크", "")
        if link and not re.match(r"https?://", link):
            raise DataError(f"{number}행의 링크는 http:// 또는 https://로 시작해야 합니다: {link}")
        items.append({"row": number, "title": row["제목"], "body": row["내용"],
                      "category": row.get("분류", "") or "기타", "link": link})
    if not items:
        raise DataError("공개 열이 Y인 행이 없습니다. 웹에 보일 행의 공개 열에 Y를 적으세요.")
    return items, hidden


def pick_today(items, target_date):
    """4주차처럼 날짜 순번으로 목록을 순환합니다."""
    return items[(target_date.toordinal() - 1) % len(items)]


def generate_html(site, items, hidden, target_date, generated_at, source_label, environment=None):
    environment = os.environ if environment is None else environment
    today = pick_today(items, target_date)
    categories = sorted({item["category"] for item in items})
    generated_kst = generated_at.astimezone(KST)
    run_number = environment.get("GITHUB_RUN_NUMBER", "")
    commit = environment.get("GITHUB_SHA", "")
    provenance = f"Actions 실행 #{escape(run_number)}" if run_number else "로컬 생성본"
    if commit:
        provenance += f" · 커밋 {escape(commit[:7])}"

    def card(item):
        link = (f'<a class="more" href="{escape(item["link"])}" rel="noopener">자세히 보기</a>'
                if item["link"] else "")
        search_text = " ".join([item["title"], item["body"], item["category"]]).lower()
        return (f'<li class="card" data-category="{escape(item["category"])}" data-search="{escape(search_text)}">'
                f'<span class="tag">{escape(item["category"])}</span><h3>{escape(item["title"])}</h3>'
                f'<p>{escape(item["body"])}</p>{link}</li>')

    options = "".join(f'<option value="{escape(c)}">{escape(c)}</option>' for c in categories)
    cards = "\n".join(card(item) for item in items)
    today_link = (f'<a class="more" href="{escape(today["link"])}" rel="noopener">자세히 보기</a>'
                  if today["link"] else "")
    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{escape(site["description"])}">
  <title>{escape(site["title"])}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
      background: #f4f7fa; color: #182433; line-height: 1.6; }}
    header {{ background: #0f3552; color: #fff; padding: 36px 20px 30px; }}
    header .wrap, main {{ max-width: 920px; margin: 0 auto; }}
    header h1 {{ margin: 0 0 8px; font-size: 30px; letter-spacing: -0.5px; }}
    header p {{ margin: 0; color: #d4e3ef; }}
    main {{ padding: 26px 20px 40px; }}
    .today {{ background: #fff; border: 2px solid #f59e0b; border-radius: 16px; padding: 22px 24px; margin-bottom: 26px; }}
    .today .label {{ color: #b45309; font-size: 14px; font-weight: 700; margin: 0 0 6px; }}
    .today h2 {{ margin: 0 0 8px; font-size: 22px; }}
    .tools {{ display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-start; margin-bottom: 10px; }}
    .tools label {{ display: block; font-size: 14px; font-weight: 700; margin-bottom: 4px; }}
    .tools .field {{ flex: 1 1 220px; }}
    input, select {{ width: 100%; height: 46px; font: inherit; padding: 8px 12px; border: 1px solid #9fb3c4; border-radius: 8px; background: #fff; }}
    input:focus-visible, select:focus-visible, a:focus-visible {{ outline: 3px solid #f59e0b; outline-offset: 2px; }}
    #count {{ color: #45596b; font-size: 15px; margin: 6px 0 16px; }}
    #empty {{ background: #fff7ed; border: 1px solid #fed7aa; border-radius: 12px; padding: 16px 18px; }}
    ul.cards {{ list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }}
    .card {{ background: #fff; border: 1px solid #d5e0ea; border-radius: 14px; padding: 18px 18px 16px; }}
    .card h3 {{ margin: 8px 0 6px; font-size: 18px; overflow-wrap: anywhere; }}
    .card p {{ margin: 0 0 8px; color: #33475b; overflow-wrap: anywhere; }}
    .tag {{ display: inline-block; font-size: 12px; font-weight: 700; color: #0f3552; background: #e3eef7; border-radius: 999px; padding: 2px 10px; }}
    .more {{ color: #0b6a8a; font-size: 14px; }}
    footer {{ color: #5b6f80; font-size: 13px; border-top: 1px solid #d5e0ea; margin-top: 30px; padding-top: 14px; }}
    footer p {{ margin: 2px 0; }}
    @media (max-width: 600px) {{ header h1 {{ font-size: 25px; }} .today {{ padding: 18px; }} }}
  </style>
</head>
<body>
  <header><div class="wrap"><h1>{escape(site["title"])}</h1><p>{escape(site["description"])}</p></div></header>
  <main>
    <section class="today" aria-labelledby="today-title">
      <p class="label">오늘의 추천 · <time datetime="{target_date.isoformat()}">{target_date.isoformat()}</time></p>
      <h2 id="today-title">{escape(today["title"])}</h2>
      <p>{escape(today["body"])}</p>{today_link}
    </section>
    <section aria-labelledby="list-title">
      <h2 id="list-title">전체 목록</h2>
      <div class="tools">
        <div class="field"><label for="q">검색</label><input id="q" type="search" placeholder="제목·내용·분류에서 찾기"></div>
        <div class="field"><label for="category">분류</label><select id="category"><option value="">전체</option>{options}</select></div>
      </div>
      <p id="count" role="status" aria-live="polite">전체 {len(items)}개</p>
      <p id="empty" hidden>조건에 맞는 항목이 없습니다. 검색어를 줄이거나 분류를 ‘전체’로 바꿔 보세요.</p>
      <ul class="cards" id="cards">
{cards}
      </ul>
    </section>
    <footer>
      <p>데이터: {escape(source_label)} · 공개 {len(items)}개{f" · 비공개 {hidden}개 제외" if hidden else ""}</p>
      <p>마지막 생성 <time datetime="{generated_kst.isoformat(timespec="seconds")}">{generated_kst.strftime("%Y.%m.%d %H:%M:%S")} KST</time> · {provenance}</p>
      <p>{escape(site.get("source_note", ""))}</p>
    </footer>
  </main>
  <script>
    const q = document.getElementById('q');
    const category = document.getElementById('category');
    const cards = [...document.querySelectorAll('#cards .card')];
    const count = document.getElementById('count');
    const empty = document.getElementById('empty');
    function apply() {{
      const word = q.value.trim().toLowerCase();
      const cat = category.value;
      let shown = 0;
      for (const card of cards) {{
        const ok = (!word || card.dataset.search.includes(word)) && (!cat || card.dataset.category === cat);
        card.hidden = !ok;
        if (ok) shown++;
      }}
      count.textContent = (word || cat) ? `전체 ${{cards.length}}개 중 ${{shown}}개` : `전체 ${{cards.length}}개`;
      empty.hidden = shown !== 0;
    }}
    q.addEventListener('input', apply);
    category.addEventListener('change', apply);
  </script>
</body>
</html>
'''


def atomic_write(output, content):
    """같은 폴더에 임시 파일을 완성한 뒤 교체하여 기존 HTML의 손상을 막습니다."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                         prefix=f".{output.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def parse_date(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise argparse.ArgumentTypeError("날짜는 YYYY-MM-DD 형식으로 입력하세요.")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"사용할 수 없는 날짜입니다: {value}") from error


def main(argv=None):
    parser = argparse.ArgumentParser(description="구글 시트 콘텐츠로 검색·필터 웹페이지를 만듭니다.")
    parser.add_argument("--csv", help="CSV 파일 경로 또는 웹에 게시한 CSV 주소")
    parser.add_argument("--output", default="index.html", type=Path, help="출력 HTML 경로")
    parser.add_argument("--date", type=parse_date, help="오늘의 추천 날짜 미리보기: YYYY-MM-DD")
    args = parser.parse_args(argv)
    source = args.csv or os.environ.get("SHEET_CSV_URL", "").strip() or str(SAMPLE_CSV)
    source_label = "구글 시트(웹에 게시한 CSV)" if re.match(r"https?://", source) else f"로컬 파일 {Path(source).name}"
    try:
        generated_at = datetime.now(KST)
        target_date = args.date or generated_at.date()
        site = load_site()
        items, hidden = parse_rows(read_source(source))
        html = generate_html(site, items, hidden, target_date, generated_at, source_label)
        atomic_write(args.output, html)
    except (OSError, ValueError) as error:
        print(f"생성 실패: {error}", file=sys.stderr)
        return 1
    print(f"데이터: {source_label}")
    print(f"공개 {len(items)}개 · 비공개 {hidden}개 · 오늘의 추천 날짜 {target_date}")
    print(f"HTML 생성 완료: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
