# Windows용 오프라인 패키지 다운로드 스크립트
# Python 3.11

param(
    [string]$OutputDir = "rag_batch\rag_batch_offline_windows",
    [string]$PythonVersion = "3.11"
)

# UTF-8 인코딩 설정 (requirements.txt 읽기용)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$ErrorActionPreference = "Stop"

Write-Host "================================================================================`n" -ForegroundColor Cyan
Write-Host " Windows용 패키지 다운로드`n" -ForegroundColor Green
Write-Host "================================================================================`n" -ForegroundColor Cyan

# 1. Python 버전 확인
Write-Host "[1/6] Python 버전 확인...`n" -ForegroundColor Yellow
try {
    $version = & py -$PythonVersion --version 2>&1
    Write-Host "  OK: $version`n" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Python $PythonVersion 을 찾을 수 없습니다!`n" -ForegroundColor Red
    Write-Host "  다운로드: https://www.python.org/downloads/release/python-3119/`n" -ForegroundColor Yellow
    exit 1
}

# 2. 프로젝트 루트 확인
$scriptDir = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path "$scriptDir\requirements.txt")) {
    Write-Host "  ERROR: requirements.txt를 찾을 수 없습니다!`n" -ForegroundColor Red
    exit 1
}

# 3. 출력 디렉토리 생성
Write-Host "`n[2/6] 출력 디렉토리 생성...`n" -ForegroundColor Yellow
$outputPath = Join-Path (Split-Path -Parent $scriptDir) $OutputDir

if (Test-Path $outputPath) {
    Write-Host "  디렉토리가 이미 존재합니다: $outputPath`n" -ForegroundColor Yellow
    $answer = Read-Host "  삭제하고 새로 생성하시겠습니까? (y/n)"
    if ($answer -eq 'y' -or $answer -eq 'Y') {
        Remove-Item -Path $outputPath -Recurse -Force
        Write-Host "  OK: 기존 디렉토리 삭제`n" -ForegroundColor Green
    } else {
        exit 0
    }
}

New-Item -ItemType Directory -Path $outputPath -Force | Out-Null
New-Item -ItemType Directory -Path "$outputPath\packages" -Force | Out-Null
Write-Host "  OK: 디렉토리 생성 - $outputPath`n" -ForegroundColor Green

# 4. requirements.txt 복사
Write-Host "`n[3/6] requirements.txt 복사...`n" -ForegroundColor Yellow
Copy-Item "$scriptDir\requirements.txt" -Destination $outputPath
Write-Host "  OK: requirements.txt 복사 완료`n" -ForegroundColor Green

# 5. Windows용 패키지 다운로드
Write-Host "`n[4/6] Windows용 패키지 다운로드 중...`n" -ForegroundColor Yellow
Write-Host "  플랫폼: Windows (win_amd64)" -ForegroundColor Cyan
Write-Host "  Python: $PythonVersion" -ForegroundColor Cyan
Write-Host "  (시간이 소요될 수 있습니다...)`n`n" -ForegroundColor Gray

Push-Location $outputPath
try {
    & py -$PythonVersion -m pip download `
        -r requirements.txt `
        -d packages `
        --platform win_amd64 `
        --python-version $PythonVersion `
        --only-binary=:all:
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n  OK: 패키지 다운로드 완료`n" -ForegroundColor Green
    } else {
        Write-Host "`n  ERROR: 패키지 다운로드 실패 (exit code: $LASTEXITCODE)`n" -ForegroundColor Red
        Pop-Location
        exit 1
    }
} catch {
    Write-Host "`n  ERROR: 오류 발생 - $_`n" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location

# 6. 다운로드 확인
Write-Host "`n[5/6] 다운로드된 패키지 확인...`n" -ForegroundColor Yellow
$packageFiles = Get-ChildItem "$outputPath\packages\*.whl"
$packageCount = $packageFiles.Count
$totalSize = ($packageFiles | Measure-Object -Property Length -Sum).Sum / 1MB

Write-Host "  OK: 패키지 수 - $packageCount 개" -ForegroundColor Green
Write-Host "  OK: 전체 크기 - $([math]::Round($totalSize, 2)) MB`n" -ForegroundColor Green

# Check Windows-specific packages
Write-Host "  Windows-specific packages:`n" -ForegroundColor Cyan
$windowsPackages = @(
    @{Name="pywin32"; Pattern="pywin32-*-win_amd64.whl"},
    @{Name="python-magic-bin"; Pattern="python_magic_bin-*.whl"},
    @{Name="psycopg2"; Pattern="psycopg2-*-win_amd64.whl"},
    @{Name="pyodbc"; Pattern="pyodbc-*-win_amd64.whl"}
)

foreach ($pkg in $windowsPackages) {
    $found = Get-ChildItem "$outputPath\packages\$($pkg.Pattern)" -ErrorAction SilentlyContinue
    if ($found) {
        Write-Host "    OK: $($pkg.Name)" -ForegroundColor Green
    } else {
        Write-Host "    SKIP: $($pkg.Name) (optional)" -ForegroundColor Yellow
    }
}

# 7. Copy project files
Write-Host "`n[6/6] Copying project files...`n" -ForegroundColor Yellow

$itemsToCopy = @(
    "src",
    "scripts",
    "docs",
    "data",
    "run.py",
    "requirements.txt",
    "env.example",
    "README.md",
    "PROCESS.md",
    "OFFLINE_INSTALL_QUICK.md",
    "LIBRARY_CHECK_RESULT.md"
)

New-Item -ItemType Directory -Path "$outputPath\rag_batch" -Force | Out-Null

foreach ($item in $itemsToCopy) {
    $sourcePath = Join-Path $scriptDir $item
    if (Test-Path $sourcePath) {
        Copy-Item $sourcePath -Destination "$outputPath\rag_batch\" -Recurse -Force
        Write-Host "  OK: $item" -ForegroundColor Green
    } else {
        Write-Host "  SKIP: $item" -ForegroundColor Yellow
    }
}

# Create empty directories
New-Item -ItemType Directory -Path "$outputPath\rag_batch\logs" -Force | Out-Null
Write-Host "  OK: logs (empty directory)`n" -ForegroundColor Green

# Create ZIP file
Write-Host "`n================================================================================" -ForegroundColor Cyan
$createZip = Read-Host "Create ZIP file? (y/n)"

if ($createZip -eq 'y' -or $createZip -eq 'Y') {
    Write-Host "`nCreating ZIP file...`n" -ForegroundColor Yellow
    $zipPath = "$outputPath.zip"
    
    if (Test-Path $zipPath) {
        Remove-Item $zipPath -Force
    }
    
    Compress-Archive -Path "$outputPath\*" -DestinationPath $zipPath -CompressionLevel Optimal
    
    $zipSize = (Get-Item $zipPath).Length / 1MB
    Write-Host "  OK: ZIP created" -ForegroundColor Green
    Write-Host "  File: $zipPath" -ForegroundColor Cyan
    Write-Host "  Size: $([math]::Round($zipSize, 2)) MB`n" -ForegroundColor Cyan
}

# Complete
Write-Host "`n================================================================================" -ForegroundColor Cyan
Write-Host " Download Complete!" -ForegroundColor Green
Write-Host "================================================================================`n" -ForegroundColor Cyan

Write-Host "Output: $outputPath" -ForegroundColor Cyan
Write-Host "Packages: $packageCount" -ForegroundColor Cyan
Write-Host "Size: $([math]::Round($totalSize, 2)) MB`n" -ForegroundColor Cyan

Write-Host "Next steps (on offline Windows PC):`n" -ForegroundColor Yellow
Write-Host "  1. Transfer ZIP file via USB" -ForegroundColor White
Write-Host "  2. Extract ZIP file" -ForegroundColor White
Write-Host "  3. Install commands:`n" -ForegroundColor White
Write-Host "     cd rag_batch" -ForegroundColor Gray
Write-Host "     py -$PythonVersion -m venv venv" -ForegroundColor Gray
Write-Host "     .\venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host "     python -m pip install --no-index --find-links=..\packages -r requirements.txt`n" -ForegroundColor Gray
