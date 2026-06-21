"""감성 분류 — KR-FinBert-SC (transformers) 우선, 미설치 시 키워드 사전 폴백.

첫 실행 시 snunlp/KR-FinBert-SC 모델(~440MB)을 HuggingFace 캐시에 다운로드한다.
이후 실행부터는 캐시에서 즉시 로드.
"""

from __future__ import annotations

from functools import lru_cache

_POSITIVE = {
    "상승", "급등", "호재", "성장", "개선", "확대", "돌파", "신고가", "흑자",
    "기대", "회복", "반등", "강세", "호조", "증가", "최고", "혁신", "기회",
    "수익", "이익", "흑자전환", "상향", "강화", "달성", "성공", "승인", "허가",
    "체결", "협력", "투자유치", "상장", "수주", "돌파구", "쾌거", "호평",
    "긍정적", "낙관", "기록", "최대", "최초", "선정", "수상", "인정",
}

_NEGATIVE = {
    "하락", "급락", "악재", "위기", "감소", "축소", "붕괴", "신저가", "적자",
    "우려", "폭락", "약세", "부진", "손실", "손해", "적자전환", "하향", "약화",
    "실패", "리스크", "경고", "제재", "규제강화", "벌금", "소송", "파산",
    "도산", "해고", "구조조정", "사기", "횡령", "비리", "논란", "갈등",
    "충돌", "피해", "사고", "폐업", "중단", "취소", "버블",
    "침체", "불황", "둔화", "부담", "악화", "저하", "부정적",
}

_LABEL_MAP = {
    "긍정": "긍정", "부정": "부정", "중립": "중립",
    "LABEL_0": "부정", "LABEL_1": "중립", "LABEL_2": "긍정",
}


def _keyword_classify(title: str) -> str:
    pos = sum(1 for w in _POSITIVE if w in title)
    neg = sum(1 for w in _NEGATIVE if w in title)
    if pos > neg:
        return "긍정"
    if neg > pos:
        return "부정"
    return "중립"


try:
    from transformers import pipeline as _hf_pipeline  # type: ignore[import]

    @lru_cache(maxsize=1)
    def _load_pipeline():
        return _hf_pipeline(
            "text-classification",
            model="snunlp/KR-FinBert-SC",
            truncation=True,
            max_length=128,
            device=-1,  # CPU
        )

    def classify(title: str) -> str:
        return classify_many([title])[0]

    def classify_many(titles: list[str]) -> list[str]:
        if not titles:
            return []
        try:
            results = _load_pipeline()(titles, batch_size=8)
            return [_LABEL_MAP.get(r["label"], "중립") for r in results]
        except Exception:
            return [_keyword_classify(t) for t in titles]

except ImportError:
    classify = _keyword_classify  # type: ignore[assignment]

    def classify_many(titles: list[str]) -> list[str]:  # type: ignore[misc]
        return [_keyword_classify(t) for t in titles]
