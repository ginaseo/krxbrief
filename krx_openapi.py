#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRX 공식 OpenAPI 클라이언트 (https://openapi.krx.co.kr)

- 로그인 불필요. HTTP 헤더 'AUTH_KEY' 에 발급 인증키만 넣으면 됨.
- 인증키는 .env 의 API= 값에서 읽음 (KRX_ID/KRX_PW 불필요).
- 서비스(엔드포인트)별로 '이용신청' 해야 권한 생김. 미신청 호출은 실패.

[신청 위치] https://openapi.krx.co.kr  -> API 서비스 목록 -> 이용신청
"""

import os
import requests
import pandas as pd

def _load_api_key():
    """`.env` 에서 API 인증키만 읽음. KRX_ID/KRX_PW 는 env 에 주입하지 않음
    (pykrx 가 불필요한 로그인을 시도하지 않도록 -> 계정 잠금 방지)."""
    names = ("KRX_API", "API", "KRX_API_KEY")
    # 이미 환경변수로 주어졌으면 그대로 사용
    for n in names:
        if os.getenv(n):
            return os.getenv(n)
    try:
        from dotenv import dotenv_values
        here = os.path.dirname(os.path.abspath(__file__))
        for cand in (
            os.path.join(here, ".env"),
            os.path.join(here, "pykrx-master", ".env"),
        ):
            if os.path.exists(cand):
                vals = dotenv_values(cand)
                for n in names:
                    if vals.get(n):
                        return vals[n]
    except Exception:
        pass
    return None


BASE = "https://data-dbg.krx.co.kr/svc/apis"
AUTH_KEY = _load_api_key()


class KrxApiError(RuntimeError):
    pass


def _get(path: str, params: dict) -> list:
    """KRX OpenAPI 호출 -> OutBlock_1 리스트 반환. 권한/오류 시 KrxApiError."""
    if not AUTH_KEY:
        raise KrxApiError(".env 에 API=<인증키> 가 없습니다.")
    url = f"{BASE}/{path}"
    try:
        r = requests.get(url, headers={"AUTH_KEY": AUTH_KEY}, params=params, timeout=30)
    except requests.RequestException as e:
        raise KrxApiError(f"요청 실패: {e}") from e
    if r.status_code == 401:
        raise KrxApiError(f"401 권한 없음 - '{path}' 서비스 이용신청 필요")
    if r.status_code == 404:
        raise KrxApiError(f"404 - '{path}' 미신청이거나 경로 오류")
    if r.status_code != 200:
        raise KrxApiError(f"HTTP {r.status_code} - {path}")
    try:
        data = r.json()
    except ValueError:
        raise KrxApiError(f"JSON 파싱 실패 - {path}: {r.text[:200]}")
    block = data.get("OutBlock_1")
    if block is None:
        raise KrxApiError(f"OutBlock_1 없음 - {path}: {str(data)[:200]}")
    return block


# 숫자형으로 바꿀 컬럼
_NUM_COLS = {
    "TDD_CLSPRC", "CMPPREVDD_PRC", "FLUC_RT", "TDD_OPNPRC", "TDD_HGPRC",
    "TDD_LWPRC", "ACC_TRDVOL", "ACC_TRDVAL", "MKTCAP", "LIST_SHRS",
    "CLSPRC_IDX", "CMPPREVDD_IDX", "OPNPRC_IDX", "HGPRC_IDX", "LWPRC_IDX",
}


def _to_df(rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for c in df.columns:
        if c in _NUM_COLS:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "", regex=False),
                                  errors="coerce")
    return df


def _df_indexed(rows: list, key: str) -> pd.DataFrame:
    """빈 응답(휴장/미집계)이면 빈 DataFrame 반환, 아니면 key 로 set_index."""
    df = _to_df(rows)
    if df.empty or key not in df.columns:
        return df
    return df.set_index(key)


# ----- 신청 완료된 서비스 -----
def stock_daily(bas_dd: str, market: str = "KOSPI") -> pd.DataFrame:
    """일별 전종목 매매정보.

    market: KOSPI(stk) / KOSDAQ(ksq) / KONEX(knx).
    반환 컬럼: ISU_CD, ISU_NM, TDD_OPNPRC/HGPRC/LWPRC/CLSPRC, FLUC_RT,
              ACC_TRDVOL, ACC_TRDVAL, MKTCAP, LIST_SHRS ...
    """
    api = {"KOSPI": "stk", "KOSDAQ": "ksq", "KONEX": "knx"}[market.upper()]
    rows = _get(f"sto/{api}_bydd_trd", {"basDd": bas_dd})
    return _df_indexed(rows, "ISU_CD")


def stock_base_info(bas_dd: str, market: str = "KOSPI") -> pd.DataFrame:
    """종목기본정보 (소속/구분/상장일/액면 등). market: KOSPI/KOSDAQ/KONEX.

    필드 예: ISU_CD, ISU_SRT_CD, ISU_NM, MKT_TP_NM, SECUGRP_NM,
            SECT_TP_NM(소속부), KIND_STKCERT_TP_NM, LIST_DD, LIST_SHRS ...
    (실제 필드는 첫 실행 시 확인)
    """
    api = {"KOSPI": "stk", "KOSDAQ": "ksq", "KONEX": "knx"}[market.upper()]
    rows = _get(f"sto/{api}_isu_base_info", {"basDd": bas_dd})
    df = _to_df(rows)
    # base_info 의 ISU_CD 는 표준코드(KR7..12자리). 단축코드(ISU_SRT_CD)로 인덱싱해야
    # stk_bydd_trd(6자리)와 매칭됨.
    key = "ISU_SRT_CD" if "ISU_SRT_CD" in df.columns else "ISU_CD"
    if df.empty or key not in df.columns:
        return df
    return df.set_index(key)


def etf_daily(bas_dd: str) -> pd.DataFrame:
    """ETF 일별매매정보 (NAV/기초지수/괴리 등 포함). KODEX 200 직접 조회용."""
    rows = _get("etp/etf_bydd_trd", {"basDd": bas_dd})
    return _df_indexed(rows, "ISU_CD")


# ----- (신청 시 사용) 지수 -----
def index_daily(bas_dd: str, market: str = "KOSPI") -> pd.DataFrame:
    """일별 지수 시세. (idx 서비스 이용신청 필요)

    market: KOSPI(kospi) / KOSDAQ(kosdaq) / KRX(krx).
    """
    api = {"KOSPI": "kospi", "KOSDAQ": "kosdaq", "KRX": "krx"}[market.upper()]
    rows = _get(f"idx/{api}_dd_trd", {"basDd": bas_dd})
    return _to_df(rows)


if __name__ == "__main__":
    import sys
    d = sys.argv[1] if len(sys.argv) > 1 else "20240105"
    df = stock_daily(d, "KOSPI")
    print(f"[stock_daily KOSPI {d}] rows={len(df)}")
    print(df[["ISU_NM", "TDD_CLSPRC", "FLUC_RT", "MKTCAP"]].head())
