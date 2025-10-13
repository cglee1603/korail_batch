# RAGFlow Plus 배치 프로그램 시작 스크립트 (PowerShell)

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "RAGFlow Plus 배치 프로그램" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# 프로젝트 루트로 이동
Set-Location $PSScriptRoot\..

# 가상환경 활성화 (있는 경우)
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "가상환경 활성화 중..." -ForegroundColor Yellow
    & "venv\Scripts\Activate.ps1"
}

# 배치 프로그램 실행
python run.py $args

