#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
한국 주식 모닝 브리핑 데이터 수집.

[실행]  저장소 루트에서:  python -m krxfree.briefing
[결과]  results/briefing_data.json → AI(클로드)가 읽어 브리핑 작성.

[개인 포트폴리오]
    보유종목·평단·해외종목은 코드가 아니라 portfolio.json 에서 읽는다(형식은 README).
    파일이 없으면 지수만 산출. 미국(US) 시세는 yfinance 필요 — 미설치/실패 시 해당
    종목은 시세 없이 기록한다(임의 추정 금지: 주가는 실측값만 사용).
"""

import os
import json
import datetime

from .clients import naver
from .loaders import load_portfolio, market_of
from .paths import RESULTS_DIR

OUT_DIR = RESULTS_DIR
os.makedirs(OUT_DIR, exist_ok=True)

# KRX 공식 OpenAPI (인증키, 무로그인). 지수 조회용. 미설치/실패 시 지수 생략.
try:
    from .clients import openapi
except Exception:
    openapi = None


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    return (100 - 100 / (1 + gain / loss)).iloc[-1]


def analyze(code):
    """국내 종목 시세·기술지표(Naver). dict 또는 None."""
    end = datetime.datetime.now().strftime("%Y%m%d")
    start = (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y%m%d")
    df = naver.ohlcv(code, start, end)
    df = df[df["거래량"] > 0]
    if df.empty:
        return None
    close = df["종가"].astype(float)
    last = df.iloc[-1]
    cur = float(last["종가"])
    have_prev = len(close) > 1
    prev_close = float(close.iloc[-2]) if have_prev else None   # 전일 없으면 추측 안 함
    H, L, C = float(last["고가"]), float(last["저가"]), cur
    P = (H + L + C) / 3
    return {
        "date": df.index[-1].strftime("%Y-%m-%d"),
        "current": cur, "prev_close": prev_close,
        "pct": round((cur - prev_close) / prev_close * 100, 2) if have_prev else None,
        "rsi14": round(float(rsi(close)), 1),
        "ma5": round(float(close.rolling(5).mean().iloc[-1]), 1),
        "ma20": round(float(close.rolling(20).mean().iloc[-1]), 1),
        "ma50": round(float(close.rolling(50).mean().iloc[-1]), 1),
        "ma200": round(float(close.rolling(200).mean().iloc[-1]), 1) if len(close) >= 200 else None,
        "pivot_s1": round(2 * P - H, 1), "pivot_p": round(P, 1), "pivot_r1": round(2 * P - L, 1),
    }


def _recent_trading_day():
    """주말/오늘 데이터 없을 때 대비해 최근 영업일 후보를 역순으로."""
    base = datetime.datetime.now()
    out = []
    for i in range(0, 7):
        d = base - datetime.timedelta(days=i)
        if d.weekday() < 5:
            out.append(d.strftime("%Y%m%d"))
    return out


def index_snapshot(market, idx_name):
    """KRX OpenAPI(idx)로 지수 스냅샷. 로그인 불필요. 미신청/오류면 사유 반환."""
    if openapi is None:
        return {"note": "openapi 모듈 없음"}
    last_err = None
    for d in _recent_trading_day():
        try:
            df = openapi.index_daily(d, market)
        except Exception as e:
            last_err = str(e)
            continue
        if df is None or df.empty:
            continue
        row = df[df["IDX_NM"] == idx_name]
        if row.empty:
            row = df.iloc[[0]]  # 종합지수가 첫 행인 경우 대비
        r = row.iloc[0]
        cur = float(r["CLSPRC_IDX"])
        rt = r.get("FLUC_RT")
        pct = float(rt) if rt not in (None, "") else None   # 없으면 추측 0 대신 None
        return {"date": f"{d[:4]}-{d[4:6]}-{d[6:]}", "current": round(cur, 2), "pct": pct}
    return {"note": f"지수 조회 실패(idx 서비스 이용신청 필요?): {last_err}"}


_yf = None
def _yfin():
    """yfinance 지연 로드. 미설치면 None."""
    global _yf
    if _yf is None:
        try:
            import yfinance as yf
            _yf = yf
        except Exception:
            _yf = False
    return _yf or None


def analyze_us(ticker):
    """해외 종목 시세(yfinance). {current, pct} 또는 None."""
    yf = _yfin()
    if yf is None or not ticker:
        return None
    try:
        hist = yf.Ticker(ticker).history(period="5d")
        cur = float(hist["Close"].iloc[-1]); prev = float(hist["Close"].iloc[-2])
        return {"current": round(cur, 2), "pct": round((cur - prev) / prev * 100, 2)}
    except Exception:
        return None


def main():
    out = {"generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M KST"),
           "data_policy": "모든 수치는 실측값. 누락은 note 로 표기되며 추정·임의 보완 금지(주가).",
           "holdings": [], "indices": {}}

    # 보유종목: 단일 리스트, market 으로 KR(Naver)/US(yfinance) 분기. 손익 KR=pnl_krw, US=pnl.
    for h in load_portfolio():
        mkt = market_of(h)
        name, avg, shares = h.get("name"), h.get("avg"), h.get("shares")
        if mkt == "KR":
            item = {"market": "KR", "name": name or h.get("code"), "code": h.get("code")}
            a = analyze(h.get("code"))
            if a:
                item.update(a)
                if avg and shares is not None:
                    item.update({"avg": avg, "shares": shares,
                                 "return_pct": round((a["current"] - avg) / avg * 100, 2),
                                 "pnl_krw": round((a["current"] - avg) * shares)})
            else:
                item["error"] = "no data"
        else:  # US (yfinance)
            ticker = h.get("ticker") or h.get("code")
            item = {"market": "US", "name": name or ticker, "ticker": ticker}
            a = analyze_us(ticker)
            if a:
                item.update(a)
                if avg and shares is not None:
                    item.update({"avg": avg, "shares": shares,
                                 "return_pct": round((a["current"] - avg) / avg * 100, 2),
                                 "pnl": round((a["current"] - avg) * shares, 2)})
            else:
                item["note"] = "시세 미수집(yfinance 미설치 또는 조회 실패) — 추정 금지, 데이터 없음으로 처리."
        out["holdings"].append(item)

    for nm, idxnm in (("KOSPI", "코스피"), ("KOSDAQ", "코스닥")):
        out["indices"][nm] = index_snapshot(nm, idxnm)

    with open(os.path.join(OUT_DIR, "briefing_data.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("저장 완료 -> briefing_data.json")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
