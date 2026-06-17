# -*- coding: utf-8 -*-
"""사용자 입력 파일 로더 (루트의 portfolio.json / kospi200_members.json).

모든 리더는 BOM 허용(utf-8-sig). 개인정보·명단을 코드에서 분리하기 위한 계층.
"""
import os
import re
import json

from .paths import data_path

PORTFOLIO_FILE = data_path("portfolio.json")
MEMBERS_FILE = data_path("kospi200_members.json")


def load_portfolio():
    """portfolio.json 의 holdings 리스트 반환. 없으면 []. (형식은 README 참조)"""
    if not os.path.exists(PORTFOLIO_FILE):
        return []
    try:
        with open(PORTFOLIO_FILE, encoding="utf-8-sig") as f:   # BOM 허용
            d = json.load(f)
    except Exception:
        return []
    return d.get("holdings") or []


def market_of(h):
    """항목의 시장 판정. market 명시 우선, 없으면 ticker 있으면 US, 아니면 KR."""
    return (h.get("market") or ("US" if h.get("ticker") else "KR")).upper()


def load_held():
    """보유 국내종목 코드 집합(held 표시용). portfolio.json 의 KR 종목코드. 없으면 빈 집합."""
    out = set()
    for h in load_portfolio():
        c = str(h.get("code") or "").strip()
        if len(c) == 6 and c.isdigit():
            out.add(c)
    return out


def load_members():
    """kospi200_members.json 에서 6자리 종목코드 추출(코드배열/객체배열/{코드:이름} 허용).

    수동 폴백용(로그인 자동조회가 우선). 파일 없거나 비면 None.
    """
    if not os.path.exists(MEMBERS_FILE):
        return None
    try:
        with open(MEMBERS_FILE, encoding="utf-8-sig") as f:   # BOM 허용
            data = json.load(f)
    except Exception:
        return None
    items = []
    if isinstance(data, dict):
        items = list(data.keys())
    elif isinstance(data, list):
        for it in data:
            if isinstance(it, str):
                items.append(it)
            elif isinstance(it, dict):
                items.append(it.get("code") or it.get("종목코드") or "")
    seen, codes = set(), []
    for x in items:
        m = re.match(r'\s*(\d{6})', str(x))
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            codes.append(m.group(1))
    return codes or None
