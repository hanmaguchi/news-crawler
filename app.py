from datetime import date, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from crawler.dedup import dedup
from crawler.export import to_excel
from crawler.sources import GoogleNewsSource, NaverNewsSource, RssSource

load_dotenv()

st.set_page_config(page_title="뉴스 크롤러", page_icon="📰", layout="wide")
st.title("📰 뉴스기사 크롤러")

if "custom_sources" not in st.session_state:
    st.session_state.custom_sources = []  # list[(name, url)]

naver = NaverNewsSource()

# ── 입력 영역 ─────────────────────────────────────────────
keyword = st.text_input("검색어", placeholder="예: 인공지능")

c1, c2 = st.columns(2)
start_d = c1.date_input("시작일", value=date.today() - timedelta(days=7))
end_d = c2.date_input("종료일", value=date.today())

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

# ── 검색 실행 ─────────────────────────────────────────────
if st.button("🔍 검색", type="primary"):
    if not keyword.strip():
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

    collected = []
    for src in sources:
        try:
            with st.spinner(f"{src.name} 수집 중…"):
                collected += src.search(keyword, start_d, end_d)
        except Exception as e:  # noqa: BLE001 - 소스별 실패는 명시적으로 알린다
            st.warning(f"{src.name} 수집 실패: {e}")

    articles = sorted(dedup(collected), key=lambda a: a.pub_date, reverse=True)
    st.session_state.articles = articles

# ── 결과 표시 ─────────────────────────────────────────────
articles = st.session_state.get("articles", [])
if articles:
    st.success(f"총 {len(articles)}건 (중복 제거 후)")
    df = pd.DataFrame(
        {
            "제목": [a.title for a in articles],
            "언론사": [a.press for a in articles],
            "배포일자": [a.pub_date for a in articles],
            "출처": [a.source for a in articles],
            "링크": [a.url for a in articles],
        }
    )
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "링크": st.column_config.LinkColumn("링크", display_text="기사보기")
        },
    )
    st.download_button(
        "📥 엑셀 다운로드",
        data=to_excel(articles),
        file_name=f"news_{keyword}_{start_d}_{end_d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
