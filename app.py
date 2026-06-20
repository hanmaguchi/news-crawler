import html
import re
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from crawler.dedup import dedup
from crawler.export import to_csv, to_excel, to_json
from crawler.sentiment import classify
from crawler.sources import GoogleNewsSource, NaverNewsSource, RssSource

load_dotenv()

st.set_page_config(page_title="뉴스 크롤러", page_icon="📰", layout="wide")
st.title("📰 뉴스기사 크롤러")

# ── 세션 초기화 ────────────────────────────────────────────────────────────────
for _key, _default in [
    ("custom_sources", []),
    ("search_history", []),
    ("keyword_input", ""),
    ("press_blacklist", set()),
]:
    if _key not in st.session_state:
        st.session_state[_key] = _default

naver = NaverNewsSource()


# ── 헬퍼 ───────────────────────────────────────────────────────────────────────
def _highlight(text: str, keywords: list[str]) -> str:
    escaped = html.escape(text)
    for kw in keywords:
        if kw:
            pattern = re.compile(re.escape(html.escape(kw)), re.IGNORECASE)
            escaped = pattern.sub(lambda m: f"<mark>{m.group()}</mark>", escaped)
    return escaped


_SENTIMENT_STYLE = {
    "긍정": "background:#c6efce;border-radius:4px;padding:1px 6px",
    "부정": "background:#ffc7ce;border-radius:4px;padding:1px 6px",
    "중립": "color:#888",
}


def _render_table(articles, keywords: list[str], sent_map: dict[str, str]) -> str:
    rows = []
    for idx, a in enumerate(articles, start=1):
        date_str = a.pub_date.strftime("%Y-%m-%d %H:%M") if a.pub_date else ""
        link = (
            f'<a href="{html.escape(a.url)}" target="_blank">기사보기</a>'
            if a.url else ""
        )
        sentiment = sent_map.get(a.url, "중립")
        style = _SENTIMENT_STYLE.get(sentiment, "")
        rows.append(
            f"<tr>"
            f"<td style='text-align:center;color:#888'>{idx}</td>"
            f"<td style='white-space:nowrap'>{date_str}</td>"
            f"<td>{html.escape(a.press)}</td>"
            f"<td style='word-break:keep-all'>{_highlight(a.title, keywords)}</td>"
            f"<td style='white-space:nowrap'>{link}</td>"
            f"<td style='white-space:nowrap'><span style='{style}'>{sentiment}</span></td>"
            f"<td>{html.escape(a.source)}</td>"
            f"</tr>"
        )

    return f"""
<style>
.news-table {{width:100%;border-collapse:collapse;font-size:0.9em;margin-top:8px}}
.news-table th {{background:#f0f2f6;padding:8px 12px;text-align:left;
                 border-bottom:2px solid #ddd;white-space:nowrap}}
.news-table td {{padding:7px 12px;border-bottom:1px solid #eee;vertical-align:top}}
.news-table tr:hover td {{background:#f8f9fa}}
.news-table a {{color:#0563c1;text-decoration:none}}
.news-table a:hover {{text-decoration:underline}}
.news-table mark {{background:#fff176;padding:0 2px;border-radius:2px}}
</style>
<table class="news-table">
<thead><tr>
  <th>#</th><th>배포일자</th><th>언론사</th><th>제목</th><th>링크</th><th>감성</th><th>출처</th>
</tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>"""


# ── 검색어 + 히스토리 ──────────────────────────────────────────────────────────
history = st.session_state.search_history
if history:
    def _on_history_select():
        sel = st.session_state.get("history_sel", "")
        if sel:
            st.session_state.keyword_input = sel

    st.selectbox(
        "최근 검색어",
        [""] + history,
        key="history_sel",
        on_change=_on_history_select,
        format_func=lambda x: "— 선택하면 검색어에 자동 입력 —" if x == "" else x,
    )

keyword_raw = st.text_input(
    "검색어 (쉼표로 여러 키워드 동시 수집 가능)",
    key="keyword_input",
    placeholder="예: 인공지능   또는   삼성전자, 이재용, 갤럭시",
)
keywords = [k.strip() for k in keyword_raw.split(",") if k.strip()]

# ── 기간 ───────────────────────────────────────────────────────────────────────
c1, c2 = st.columns(2)
start_d = c1.date_input("시작일", value=date.today() - timedelta(days=7))
end_d = c2.date_input("종료일", value=date.today())

# ── 출처 선택 ──────────────────────────────────────────────────────────────────
st.subheader("수집 출처")
use_naver = st.checkbox(
    "네이버",
    value=naver.configured,
    disabled=not naver.configured,
    help=None if naver.configured else "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 미설정",
)
if not naver.configured:
    st.caption("⚠️ 네이버 API 키가 없어 비활성화됨. .env에 키를 설정하면 활성화됩니다.")
use_google = st.checkbox("구글", value=True)

with st.expander("➕ 커스텀 RSS 소스 추가"):
    rc1, rc2 = st.columns(2)
    new_name = rc1.text_input("소스 이름", key="rss_name")
    new_url = rc2.text_input("RSS 피드 URL", key="rss_url")
    if st.button("추가") and new_name and new_url:
        st.session_state.custom_sources.append((new_name, new_url))
    for i, (n, u) in enumerate(st.session_state.custom_sources):
        cols = st.columns([4, 1])
        cols[0].write(f"**{n}** — {u}")
        if cols[1].button("삭제", key=f"del_{i}"):
            st.session_state.custom_sources.pop(i)
            st.rerun()

# ── 언론사 블랙리스트 ──────────────────────────────────────────────────────────
with st.expander("🚫 언론사 블랙리스트"):
    bl = st.session_state.press_blacklist
    bl_input = st.text_input("언론사명 직접 입력 후 Enter", key="bl_manual")
    if bl_input:
        bl.add(bl_input.strip())
        st.session_state.bl_manual = ""
        st.rerun()
    if bl:
        st.caption(f"블랙리스트 {len(bl)}개 — 검색 결과에서 자동 제외됩니다.")
        for press in sorted(bl):
            bc1, bc2 = st.columns([5, 1])
            bc1.write(press)
            if bc2.button("해제", key=f"bl_rm_{press}"):
                bl.discard(press)
                st.rerun()
    else:
        st.caption("블랙리스트가 비어 있습니다.")

# ── 검색 실행 ──────────────────────────────────────────────────────────────────
if st.button("🔍 검색", type="primary"):
    if not keywords:
        st.warning("검색어를 입력하세요.")
        st.stop()
    if start_d > end_d:
        st.warning("시작일이 종료일보다 늦습니다.")
        st.stop()

    sources = []
    if use_naver:
        sources.append(naver)
    if use_google:
        sources.append(GoogleNewsSource())
    sources += [RssSource(n, u) for n, u in st.session_state.custom_sources]
    if not sources:
        st.warning("최소 하나의 출처를 선택하세요.")
        st.stop()

    for kw in reversed(keywords):
        if kw in st.session_state.search_history:
            st.session_state.search_history.remove(kw)
        st.session_state.search_history.insert(0, kw)
    st.session_state.search_history = st.session_state.search_history[:10]

    collected = []
    for kw in keywords:
        for src in sources:
            try:
                with st.spinner(f"[{kw}] {src.name} 수집 중…"):
                    collected += src.search(kw, start_d, end_d)
            except Exception as e:  # noqa: BLE001
                st.warning(f"[{kw}] {src.name} 수집 실패: {e}")

    articles_all = sorted(dedup(collected), key=lambda a: a.pub_date, reverse=True)
    st.session_state.articles = articles_all
    st.session_state.keywords_used = keywords

# ── 결과 표시 ──────────────────────────────────────────────────────────────────
articles_all = st.session_state.get("articles", [])
keywords_used = st.session_state.get("keywords_used", [])

if articles_all:
    bl = st.session_state.press_blacklist
    articles = [a for a in articles_all if a.press not in bl]
    hidden = len(articles_all) - len(articles)

    msg = f"총 {len(articles_all)}건 (중복 제거 후)"
    if hidden:
        msg += f" — 블랙리스트 {hidden}건 제외"
    st.success(msg)

    # 감성 1회 계산 (테이블·요약 공유)
    with st.spinner("감성 분석 중…"):
        sent_map = {a.url: classify(a.title) for a in articles}

    # ── 감성 요약 ──────────────────────────────────────────────
    vals = list(sent_map.values())
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("긍정 🟢", vals.count("긍정"))
    sc2.metric("부정 🔴", vals.count("부정"))
    sc3.metric("중립 ⚪", vals.count("중립"))

    # ── 언론사 필터 ────────────────────────────────────────────
    all_press = sorted({a.press for a in articles})
    selected_press = st.multiselect(
        "언론사 필터",
        options=all_press,
        default=[],
        placeholder="선택하지 않으면 전체 표시",
    )
    filtered = [a for a in articles if not selected_press or a.press in selected_press]
    if selected_press:
        st.caption(f"필터 적용 후 {len(filtered)}건 표시")

    # ── 내보내기 버튼 ──────────────────────────────────────────
    fname_kw = "_".join(keywords_used)
    fname_base = f"news_{fname_kw}_{start_d}_{end_d}"
    dl1, dl2, dl3 = st.columns(3)
    dl1.download_button(
        "📥 엑셀 다운로드",
        data=to_excel(filtered),
        file_name=f"{fname_base}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    dl2.download_button(
        "📄 CSV 다운로드",
        data=to_csv(filtered),
        file_name=f"{fname_base}.csv",
        mime="text/csv",
    )
    dl3.download_button(
        "📋 JSON 다운로드",
        data=to_json(filtered),
        file_name=f"{fname_base}.json",
        mime="application/json",
    )

    # ── 하이라이트 테이블 ──────────────────────────────────────
    st.markdown(_render_table(filtered, keywords_used, sent_map), unsafe_allow_html=True)

    # ── 트렌드 차트 ───────────────────────────────────────────
    with st.expander("📈 날짜별 기사 수 트렌드", expanded=False):
        date_series = pd.Series(
            [a.pub_date.date() for a in articles if a.pub_date],
            name="기사 수",
        )
        if not date_series.empty:
            chart_df = date_series.value_counts().rename_axis("날짜").sort_index().reset_index()
            chart_df.columns = ["날짜", "기사 수"]
            chart_df["날짜"] = chart_df["날짜"].astype(str)
            st.bar_chart(chart_df, x="날짜", y="기사 수", use_container_width=True)
