import html
import re
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from crawler.dedup import dedup
from crawler.export import to_csv, to_excel, to_json
from crawler.favorites import (
    RSS_PRESETS,
    load_kw_favorites,
    load_rss_favorites,
    save_kw_favorites,
    save_rss_favorites,
)
from crawler.sentiment import classify
from crawler.sources import GoogleNewsSource, NaverNewsSource, RssSource

load_dotenv()

st.set_page_config(page_title="뉴스 크롤러", page_icon="📰", layout="wide")
st.title("📰 뉴스기사 크롤러")

# ── 세션 초기화 ────────────────────────────────────────────────────────────────
_DEFAULTS: dict = {
    "custom_sources": [],
    "search_history": [],
    "keyword_input": "",
    "press_blacklist": set(),
    "articles": [],
    "keywords_used": [],
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# 즐겨찾기는 파일에서 한 번만 로드
if "kw_favorites" not in st.session_state:
    st.session_state.kw_favorites = load_kw_favorites()
if "rss_favorites" not in st.session_state:
    st.session_state.rss_favorites = load_rss_favorites()

naver = NaverNewsSource()

# ── 헬퍼 ───────────────────────────────────────────────────────────────────────
_SENTIMENT_STYLE = {
    "긍정": "background:#c6efce;border-radius:4px;padding:1px 6px",
    "부정": "background:#ffc7ce;border-radius:4px;padding:1px 6px",
    "중립": "color:#888",
}

_SORT_OPTIONS = ["최신순", "오래된순", "언론사순", "긍정 먼저", "부정 먼저"]
_SENT_ORDER = {"긍정": 0, "부정": 1, "중립": 2}
_EPOCH = datetime.min


def _sort(articles, opt: str, sent_map: dict[str, str]):
    if opt == "최신순":
        return sorted(articles, key=lambda a: a.pub_date or _EPOCH, reverse=True)
    if opt == "오래된순":
        return sorted(articles, key=lambda a: a.pub_date or _EPOCH)
    if opt == "언론사순":
        return sorted(articles, key=lambda a: a.press)
    if opt == "긍정 먼저":
        return sorted(articles, key=lambda a: _SENT_ORDER.get(sent_map.get(a.url, "중립"), 2))
    if opt == "부정 먼저":
        return sorted(articles, key=lambda a: (0 if sent_map.get(a.url) == "부정" else 1))
    return articles


def _highlight(text: str, keywords: list[str]) -> str:
    escaped = html.escape(text)
    for kw in keywords:
        if kw:
            pattern = re.compile(re.escape(html.escape(kw)), re.IGNORECASE)
            escaped = pattern.sub(lambda m: f"<mark>{m.group()}</mark>", escaped)
    return escaped


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


# ═══════════════════════════════════════════════════════════════════════════════
# 검색 설정
# ═══════════════════════════════════════════════════════════════════════════════

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

# ── 키워드 즐겨찾기 ────────────────────────────────────────────────────────────
kw_favs: list[str] = st.session_state.kw_favorites

fav_c1, fav_c2 = st.columns([1, 5])
if fav_c1.button("⭐ 즐겨찾기 추가", key="kw_fav_add"):
    kw_stripped = keyword_raw.strip()
    if kw_stripped and kw_stripped not in kw_favs:
        kw_favs.append(kw_stripped)
        save_kw_favorites(kw_favs)
        st.rerun()

if kw_favs:
    with fav_c2.container():
        st.caption("즐겨찾기 — 클릭하면 검색어에 입력")
        rows_of_5 = [kw_favs[i : i + 5] for i in range(0, len(kw_favs), 5)]
        for row in rows_of_5:
            btn_cols = st.columns(len(row))
            for col, kw in zip(btn_cols, row):
                if col.button(f"⭐ {kw}", key=f"kw_fav_btn_{kw}"):
                    st.session_state.keyword_input = kw
                    st.rerun()

with st.expander("즐겨찾기 키워드 관리"):
    if not kw_favs:
        st.caption("저장된 즐겨찾기 없음.")
    else:
        for kw in list(kw_favs):
            mc1, mc2 = st.columns([5, 1])
            mc1.write(kw)
            if mc2.button("삭제", key=f"kw_fav_del_{kw}"):
                kw_favs.remove(kw)
                save_kw_favorites(kw_favs)
                st.rerun()

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

# ── RSS 소스 관리 ──────────────────────────────────────────────────────────────
with st.expander("📡 RSS 소스 관리"):
    tab_session, tab_preset, tab_fav, tab_custom = st.tabs(
        ["현재 세션 소스", "프리셋", "즐겨찾기", "직접 추가"]
    )

    with tab_session:
        if not st.session_state.custom_sources:
            st.caption("추가된 RSS 소스 없음.")
        for i, (n, u) in enumerate(st.session_state.custom_sources):
            sc1, sc2 = st.columns([5, 1])
            sc1.write(f"**{n}** — {u}")
            if sc2.button("삭제", key=f"sess_del_{i}"):
                st.session_state.custom_sources.pop(i)
                st.rerun()

    with tab_preset:
        st.caption("기본 미선택. 원하는 소스를 추가하세요.")
        for preset in RSS_PRESETS:
            in_sess = any(u == preset["url"] for _, u in st.session_state.custom_sources)
            pc1, pc2 = st.columns([5, 1])
            pc1.write(f"**{preset['name']}** — {preset['url']}")
            if in_sess:
                if pc2.button("제거", key=f"preset_rm_{preset['name']}"):
                    st.session_state.custom_sources = [
                        (n, u) for n, u in st.session_state.custom_sources
                        if u != preset["url"]
                    ]
                    st.rerun()
            else:
                if pc2.button("추가", key=f"preset_add_{preset['name']}"):
                    st.session_state.custom_sources.append((preset["name"], preset["url"]))
                    st.rerun()

    with tab_fav:
        rss_favs: list[dict] = st.session_state.rss_favorites
        if not rss_favs:
            st.caption("저장된 RSS 즐겨찾기 없음. 직접 추가 탭에서 저장하세요.")
        for fav in list(rss_favs):
            in_sess = any(u == fav["url"] for _, u in st.session_state.custom_sources)
            fc1, fc2, fc3 = st.columns([4, 1, 1])
            fc1.write(f"**{fav['name']}** — {fav['url']}")
            if in_sess:
                fc2.write("✓")
            else:
                if fc2.button("추가", key=f"rfav_add_{fav['name']}"):
                    st.session_state.custom_sources.append((fav["name"], fav["url"]))
                    st.rerun()
            if fc3.button("삭제", key=f"rfav_del_{fav['name']}"):
                st.session_state.rss_favorites = [
                    f for f in rss_favs if f["url"] != fav["url"]
                ]
                save_rss_favorites(st.session_state.rss_favorites)
                st.rerun()

    with tab_custom:
        cc1, cc2 = st.columns(2)
        new_name = cc1.text_input("소스 이름", key="rss_name")
        new_url = cc2.text_input("RSS URL", key="rss_url")
        btn1, btn2 = st.columns(2)
        if btn1.button("세션에 추가", key="rss_add"):
            if new_name and new_url:
                st.session_state.custom_sources.append((new_name, new_url))
                st.rerun()
        if btn2.button("⭐ 즐겨찾기에 저장", key="rss_save_fav"):
            if new_name and new_url:
                entry = {"name": new_name, "url": new_url}
                if not any(f["url"] == new_url for f in st.session_state.rss_favorites):
                    st.session_state.rss_favorites.append(entry)
                    save_rss_favorites(st.session_state.rss_favorites)
                if not any(u == new_url for _, u in st.session_state.custom_sources):
                    st.session_state.custom_sources.append((new_name, new_url))
                st.rerun()

# ── 언론사 블랙리스트 ──────────────────────────────────────────────────────────
with st.expander("🚫 언론사 블랙리스트"):
    bl = st.session_state.press_blacklist
    bl_input = st.text_input("언론사명 입력 후 Enter", key="bl_manual")
    if bl_input:
        bl.add(bl_input.strip())
        st.session_state.bl_manual = ""
        st.rerun()
    if bl:
        st.caption(f"블랙리스트 {len(bl)}개 — 검색 결과에서 자동 제외")
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

    st.session_state.articles = sorted(
        dedup(collected), key=lambda a: a.pub_date or _EPOCH, reverse=True
    )
    st.session_state.keywords_used = keywords

# ═══════════════════════════════════════════════════════════════════════════════
# 결과 표시
# ═══════════════════════════════════════════════════════════════════════════════
articles_all: list = st.session_state.articles
keywords_used: list[str] = st.session_state.keywords_used

if not articles_all:
    st.stop()

bl = st.session_state.press_blacklist
articles = [a for a in articles_all if a.press not in bl]
hidden = len(articles_all) - len(articles)

msg = f"총 {len(articles_all)}건 (중복 제거 후)"
if hidden:
    msg += f" — 블랙리스트 {hidden}건 제외"
st.success(msg)

# 감성 1회 계산 (테이블·요약 공유)
with st.spinner("감성 분석 중…"):
    sent_map: dict[str, str] = {a.url: classify(a.title) for a in articles}

# ── 감성 요약 ──────────────────────────────────────────────────────────────────
vals = list(sent_map.values())
sc1, sc2, sc3 = st.columns(3)
sc1.metric("긍정 🟢", vals.count("긍정"))
sc2.metric("부정 🔴", vals.count("부정"))
sc3.metric("중립 ⚪", vals.count("중립"))

# ── 언론사 필터 ────────────────────────────────────────────────────────────────
all_press = sorted({a.press for a in articles})
selected_press = st.multiselect(
    "언론사 필터",
    options=all_press,
    default=[],
    placeholder="선택하지 않으면 전체 표시",
)
filtered = [a for a in articles if not selected_press or a.press in selected_press]
if selected_press:
    st.caption(f"필터 적용 후 {len(filtered)}건")

# ── 정렬 + 결과 내 검색 ────────────────────────────────────────────────────────
sort_col, search_col = st.columns([1, 2])
sort_opt = sort_col.selectbox("정렬", _SORT_OPTIONS, key="sort_opt")
result_search = search_col.text_input(
    "🔍 결과 내 검색", placeholder="제목·언론사 내 검색어", key="result_search"
)

filtered = _sort(filtered, sort_opt, sent_map)

if result_search:
    q = result_search.lower()
    filtered = [a for a in filtered if q in a.title.lower() or q in a.press.lower()]
    st.caption(f"검색어 '{result_search}' 일치 {len(filtered)}건")

# ── 내보내기 버튼 ──────────────────────────────────────────────────────────────
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

# ── 하이라이트 테이블 ──────────────────────────────────────────────────────────
st.markdown(_render_table(filtered, keywords_used, sent_map), unsafe_allow_html=True)

# ── 트렌드 차트 ───────────────────────────────────────────────────────────────
with st.expander("📈 날짜별 기사 수 트렌드", expanded=False):
    date_series = pd.Series(
        [a.pub_date.date() for a in articles if a.pub_date],
        name="기사 수",
    )
    if not date_series.empty:
        chart_df = (
            date_series.value_counts()
            .rename_axis("날짜")
            .sort_index()
            .reset_index()
        )
        chart_df.columns = ["날짜", "기사 수"]
        chart_df["날짜"] = chart_df["날짜"].astype(str)
        st.bar_chart(chart_df, x="날짜", y="기사 수", use_container_width=True)
