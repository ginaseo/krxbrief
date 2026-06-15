# StockAuto — KRX 모닝 브리핑 & 코스피200 스크리너

한국 주식 모닝 브리핑 데이터와 코스피200 추천 스크리너를 자동 생성하는 파이프라인.
매 영업일 아침 데이터를 수집해 JSON으로 저장하고, Claude Cowork가 읽어 브리핑을 작성한다.

> ⚠️ **면책**: 투자 자문이 아니다. 공개 데이터 기반 단순 스크리닝이며, 모든 투자 판단·손익 책임은 사용자에게 있다.

---

## 1. 최종 구조 (pykrx 비의존)

```
C:\Archive\StockAuto\                     ← 루트 (Cowork 가 여기서 JSON 읽음)
├─ run_morning.ps1            작업 스케줄러 실행 진입점 (브리핑+스크리너 일괄)
├─ register_krx_task.bat      Windows 작업 스케줄러 등록 (월~금 08:05)
├─ briefing_data.json         산출물: 보유종목·지수·NVDA          ← Cowork 읽기
├─ kospi200_screen.json       산출물: 코스피200 추천(팩터 포함)    ← Cowork 읽기
└─ pykrx-free\                코드 + 전용 venv (pykrx 미설치)
    ├─ krx_naver.py            자체 Naver OHLCV 클라 (무인증)
    ├─ krx_login.py            자체 KRX 로그인 PER/PBR 클라 (공식값, 로그인 1회)
    ├─ krx_openapi.py          KRX 공식 OpenAPI 클라 (인증키)
    ├─ krx_dart.py             OpenDART 클라 (성장률/ROE/부채비율)
    ├─ krx_briefing_fetch.py   브리핑 수집 → 루트\briefing_data.json
    ├─ krx_screener_api.py     스크리너 → 루트\kospi200_screen.json
    ├─ corp_map.json           DART 종목코드→corp_code 캐시 (자동 생성)
    ├─ .env                    자격증명/인증키 (git 제외, 절대 커밋 금지)
    ├─ .env.example  .gitignore  README.md
    └─ .venv\                  전용 가상환경 (pandas/numpy/requests/python-dotenv/yfinance)
```

**핵심**
- 스크립트는 `pykrx-free\` 안에 있고, **산출물 JSON 은 항상 루트(`C:\Archive\StockAuto`)에 기록** (출력경로 = 스크립트 폴더의 상위로 고정).
- 작업 스케줄러 `KRX_Morning_Data` → 루트 `run_morning.ps1` → 08:05 실행, Cowork 는 08:15 루트에서 JSON 읽음.
- **pykrx 미사용.** OHLCV·PER/PBR 모두 자체 클라이언트로 직접 호출.

---

## 2. 인증 / 데이터 소스

| 데이터 | 소스 | 인증 |
|--------|------|------|
| 보유종목 OHLCV / 이평 / RSI | `krx_naver.py` (Naver 직접) | **무인증** |
| 지수(KOSPI/KOSDAQ), 전종목 일별 시세 | `krx_openapi.py` (KRX OpenAPI) | `KRX_API` 인증키 |
| PER / PBR / 배당수익률 | `krx_login.py` (KRX 공식값 직접) | **KRX 로그인 1회** (`KRX_ID`/`KRX_PW`) |
| 매출·영업익 성장률 / ROE / 부채비율 | `krx_dart.py` (OpenDART) | `DART_API` 인증키 |
| NVDA (해외) | yfinance | 무인증 |

### `.env` (위치: `pykrx-master/.env`)
```
KRX_ID=<KRX 로그인 ID>
KRX_PW=<KRX 로그인 PW>
KRX_API=<KRX OpenAPI 인증키>     # https://openapi.krx.co.kr
DART_API=<OpenDART 인증키>       # https://opendart.fss.or.kr
```

> **주의**: `.env` 는 비밀번호·키를 평문 저장한다. git 에 절대 커밋하지 말 것 (`.gitignore` 에 등록됨).
> KRX OpenAPI 는 서비스(엔드포인트)별 **이용신청** 필요. 현재 신청: 유가증권/지수 일별시세, 종목기본정보, ETF.
> DART 는 키 1개로 모든 API 접근 (서비스별 신청 불필요).

---

## 3. 실행

### 수동
```powershell
# 브리핑만 (무로그인)
powershell -ExecutionPolicy Bypass -File C:\Archive\StockAuto\run_briefing.ps1

# 브리핑 + 스크리너 (KRX 로그인 1회 + DART)
powershell -ExecutionPolicy Bypass -File C:\Archive\StockAuto\run_morning.ps1
```

### 자동 (Windows 작업 스케줄러)
- 작업명 `KRX_Morning_Data`, 매 영업일(월~금) **08:05** 실행 → `run_morning.ps1`
- 등록: `register_krx_task.bat` 우클릭 > 관리자 권한 실행 (또는 이미 등록됨)
- 확인: `schtasks /query /tn KRX_Morning_Data`
- 삭제: `schtasks /delete /tn KRX_Morning_Data /f`
- PC 가 08:05 에 켜져 있어야 함. **잠금(lock) 상태는 OK**, 로그오프/재시작은 안 됨.

### Cowork 연계
- 08:15 (스크립트 완료 후) Cowork 가 `briefing_data.json` + `kospi200_screen.json` 을 읽어 브리핑 작성.
- 각 JSON 의 `generated`/`as_of` 시각 확인 → 오래되면 갱신 경고.

---

## 4. 스크리너 방법론

- **유니버스**: KOSPI 시총 상위 200 (코스피200 근사. KRX OpenAPI 에 정확한 구성종목 명단 없음)
- **스코어**: 모멘텀 30 / 가치(PER·PBR) 25 / 유동성 25 / 사이즈 20
- **가점**: 기술적(이평 정배열·RSI 40~70·MA20 상회) + DART(영업익 성장 / 매출 성장 / ROE≥8 / 고부채 감점)
- **2단계**: 1차 벌크 스코어 → 상위 ~25 후보만 OHLCV(Naver)·DART 호출로 정밀 보정

### 호출량 (1회 실행)
- KRX OpenAPI: 스냅샷 2~5콜
- KRX 로그인: 1회 (PER/PBR)
- Naver OHLCV: ~25콜
- DART: ~25콜 (corp_map 은 캐시)

---

## 5. 한계 / 확장 여지

- **코스피200 정확 명단** 미제공 → 시총 상위 200 근사 사용
- **업종 분류** 없음 (KRX OpenAPI 미제공). 보험사 등 고부채 업종은 부채 감점이 다소 불리
- **수정주가**: pykrx 기간조회는 Naver 수정주가 적용 → 과거 분할 종목은 KRX 원시값과 과거 구간 상이 가능 (현재가는 동일)
- **무로그인 전환**: DART 로 PER/PBR 대체 시 KRX 로그인 제거 가능하나, 종목당 재무 호출(~200콜)+근사 계산이라 비권장

---

## 6. 데이터 교차검증

KRX OpenAPI vs pykrx 동일 일자 비교 결과 종가·거래량·거래대금·등락률·시가총액 **완전 일치** (동일 KRX 원천).
단일일자 EOD 는 동일, 기간 범위는 수정주가 차이 가능.

---

## 7. 데이터 접근 방식 의사결정 기록 (2026-06)

### 7.1 KRX 데이터 접근 경로 3가지
| 경로 | 정체 | PER/PBR | 인증(2026) |
|------|------|---------|-----------|
| ① 공식 OpenAPI (`openapi.krx`, `/svc/apis`) | 거래소 정식 개방. `krx_openapi.py` | ❌ 엔드포인트 없음 | 인증키 |
| ② 내부 AJAX (`getJsonData.cmd`) | 사이트 화면용 내부 API 스크래핑 = pykrx, `krx_login.py` | ✅ MDCSTAT03501 | **로그인 필요** |
| ③ OTP 다운로드 (`comm/fileDn`) | 사이트 다운로드 버튼 스크래핑 = 옛 블로그/quant_cookbook | ✅ | **로그인 필요** |

### 7.2 검증 결과
- **무로그인 OTP 다운로드(③)** 는 2026-06 현재 **로그인 차단**됨. 테스트 3회 모두 실패(GET→403, GET+워밍업→LOGOUT, POST→403). 과거 블로그 방식 전부 死.
- **공식 OpenAPI(①)** 는 시세·매매정보·지수만 제공, **PER/PBR 없음**.
- 결론: **무로그인으로 KRX 공식 PER/PBR 획득 불가.** PER/PBR 선택지는 (L) 로그인 스크래핑 또는 (N) DART 재무로 직접 계산(근사)뿐.
- DART 근사 검증: 지배주주 기준 적용 시 단순종목은 KRX와 거의 일치(±0~7%), 지주사·소수지분 종목은 ±10~20% 잔차(원인: KRX는 TTM/연결 기준).

#### DART 계산 PER/PBR vs KRX 공식값 실측 (2026-06-12, DART 2025 사업보고서·지배주주 기준)
| 종목 | PER(KRX) | PER(DART) | PERΔ | PBR(KRX) | PBR(DART) | PBRΔ |
|------|---------:|----------:|-----:|---------:|----------:|-----:|
| 기아 | 8.6 | 8.6 | 0.0% | 1.06 | 1.06 | 0.0% |
| SK스퀘어 | 20.4 | 20.3 | -0.5% | 6.48 | 6.48 | 0.0% |
| SK하이닉스 | 34.6 | 35.7 | +3.2% | 12.52 | 12.71 | +1.5% |
| NAVER | 19.0 | 19.8 | +4.2% | 1.34 | 1.40 | +4.5% |
| KB금융 | 10.5 | 9.8 | -6.7% | 0.98 | 0.97 | -1.0% |
| 신한지주 | 10.2 | 9.5 | -6.9% | 0.82 | 0.82 | 0.0% |
| 삼성생명 | 30.1 | 33.5 | +11.3% | 1.10 | 1.23 | +11.8% |
| 삼성전자 | 48.8 | 42.6 | -12.7% | 5.04 | 4.44 | -11.9% |
| 현대차 | 16.8 | 13.2 | -21.4% | 1.38 | 1.08 | -21.7% |

→ 9종목 중 6개 ±7% 이내(단순 사업구조), 3개(삼성전자·삼성생명·현대차) ±10~22% 잔차(지주/소수지분/보험·TTM 차이). 가치 팩터는 상대순위 정규화라 스크리너 랭킹 영향은 미미.

### 7.3 트레이드오프와 결정
| 안 | PER/PBR | 로그인 | pykrx | 정확도 |
|----|---------|--------|-------|--------|
| **N. 무로그인/API only** | DART 계산 | 0 | 0 | 근사 (일부 ±10~20%) |
| **L. 자체 KRX 로그인** (`krx_login.py`) | KRX 공식값 | 1회/실행 | 0 | 정확 |

**→ 결정: L 선택.** 무로그인(N)과 정확도(L) 두 트레이드오프에서, **정확도를 위해 어쩔 수 없이 로그인 방식(L)을 채택**했다. KRX 공식 PER/PBR 을 그대로 쓰기 위함이며, 로그인은 일 1회(스케줄 08:05)뿐이라 계정 잠금 위험이 낮다. pykrx 의존은 제거하고, 자체 클라이언트(`krx_login.py`)로 `getJsonData.cmd` 를 직접 호출한다.

### 7.4 비고
- `krx_login.py` = KRX 로그인 + 내부 JSON API 자체 호출 (pykrx 비의존). PER/PBR/EPS/BPS/DPS/배당수익률 = MDCSTAT03501.
- 업종/섹터는 KRX 무로그인 불가 → 필요 시 WiseIndex(`wiseindex.com`, 별도 서버) 검토.
- 무로그인 전환을 원하면 언제든 N(DART 계산)으로 스위치 가능 (코드는 양쪽 다 보유).
