#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
구글 뉴스 RSS 기반 종목명 검색 — "모멘텀은 있는데 뉴스가 없다"를 잡기 위한 최소 신호.

별도 인증키 불필요(공개 RSS). 풀텍스트/감성분석은 하지 않음 — 최근 N일 기사 건수만 센다.
"""
import datetime
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests

URL = "https://news.google.com/rss/search"
UA = "Mozilla/5.0"


def count_recent(query: str, days: int = 7) -> int:
    """query(종목명)로 구글뉴스 RSS 검색 후 최근 days일 내 기사 수. 실패 시 0."""
    try:
        r = requests.get(URL, params={"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"},
                          headers={"User-Agent": UA}, timeout=15)
        root = ET.fromstring(r.content)
    except Exception:
        return 0

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    n = 0
    for item in root.iter("item"):
        pub = item.findtext("pubDate")
        if not pub:
            continue
        try:
            dt = parsedate_to_datetime(pub)
        except Exception:
            continue
        if dt >= cutoff:
            n += 1
    return n


if __name__ == "__main__":
    print("삼성전자 최근 7일 기사 수:", count_recent("삼성전자"))
