# =====================================================================
# run_morning.ps1  — 작업 스케줄러용 진입점 (automation/ 위치)
#   저장소 루트의 전용 venv 로 브리핑+스크리너 패키지 실행.
#   산출 JSON 은 루트의 results\ 에 생성된다.
#
# 수동 실행:  powershell -ExecutionPolicy Bypass -File automation\run_morning.ps1
# =====================================================================
$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
$env:PYTHONIOENCODING = "utf-8"

$Root = Split-Path $PSScriptRoot -Parent       # automation -> 저장소 루트
$Out  = Join-Path $Root "results"
$Py   = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { Write-Error "venv 파이썬 없음: $Py"; exit 1 }
Set-Location $Root                              # 패키지(krxfree) import 가능하도록 루트에서 실행

Write-Host "[run_morning] 1/2 briefing..." -ForegroundColor Cyan
& $Py -m krxfree.briefing
if (-not (Test-Path (Join-Path $Out "briefing_data.json"))) { Write-Error "briefing 실패"; exit 1 }

Write-Host "[run_morning] 2/2 screener..." -ForegroundColor Cyan
& $Py -m krxfree.screener
if (-not (Test-Path (Join-Path $Out "kospi200_screen.json"))) { Write-Error "screener 실패"; exit 1 }

Write-Host "[run_morning] 완료 -> $Out\briefing_data.json + kospi200_screen.json" -ForegroundColor Green
