# LibreOffice Windows 오프라인 설치 파일 다운로드 스크립트
# 인터넷 연결된 PC에서 실행

$ErrorActionPreference = "Stop"

# 다운로드 디렉토리 설정
$downloadDir = ".\libreoffice_offline_windows"
if (-not (Test-Path $downloadDir)) {
    New-Item -ItemType Directory -Path $downloadDir | Out-Null
}

Write-Host "=" * 70
Write-Host "LibreOffice Windows 오프라인 설치 파일 다운로드"
Write-Host "=" * 70
Write-Host ""

# 버전 설정 (필요시 변경)
$version = "24.8.4"
$baseUrl = "https://download.documentfoundation.org/libreoffice/stable/$version/win/x86_64"

# 다운로드할 파일 목록
$files = @(
    @{
        Name = "LibreOffice_${version}_Win_x64.msi"
        Url = "$baseUrl/LibreOffice_${version}_Win_x64.msi"
        Description = "LibreOffice 메인 설치 파일"
        Required = $true
    },
    @{
        Name = "LibreOffice_${version}_Win_x64_langpack_ko.msi"
        Url = "$baseUrl/LibreOffice_${version}_Win_x64_langpack_ko.msi"
        Description = "한글 언어팩"
        Required = $false
    },
    @{
        Name = "LibreOffice_${version}_Win_x64_helppack_ko.msi"
        Url = "$baseUrl/LibreOffice_${version}_Win_x64_helppack_ko.msi"
        Description = "한글 도움말"
        Required = $false
    }
)

# 다운로드 함수
function Download-File {
    param(
        [string]$Url,
        [string]$OutputPath
    )
    
    try {
        Write-Host "다운로드 중: $OutputPath" -ForegroundColor Cyan
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($Url, $OutputPath)
        
        $fileSize = (Get-Item $OutputPath).Length / 1MB
        Write-Host "  완료: $([math]::Round($fileSize, 2)) MB" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "  실패: $_" -ForegroundColor Red
        return $false
    }
}

# 파일 다운로드
$downloadCount = 0
foreach ($file in $files) {
    $outputPath = Join-Path $downloadDir $file.Name
    
    Write-Host ""
    Write-Host "[$($file.Description)]"
    
    if (Test-Path $outputPath) {
        Write-Host "  이미 존재: $outputPath" -ForegroundColor Yellow
        $downloadCount++
        continue
    }
    
    $success = Download-File -Url $file.Url -OutputPath $outputPath
    
    if ($success) {
        $downloadCount++
    }
    elseif ($file.Required) {
        Write-Host ""
        Write-Host "필수 파일 다운로드 실패!" -ForegroundColor Red
        exit 1
    }
}

# 설치 스크립트 생성
$installScript = @"
@echo off
REM LibreOffice 오프라인 설치 스크립트
REM 관리자 권한으로 실행하세요

echo ============================================================
echo LibreOffice 오프라인 설치
echo ============================================================
echo.

REM 메인 설치
echo [1/3] LibreOffice 메인 설치...
msiexec /i LibreOffice_${version}_Win_x64.msi /qb ALLUSERS=1
if %errorlevel% neq 0 (
    echo 메인 설치 실패!
    pause
    exit /b %errorlevel%
)
echo 완료!
echo.

REM 언어팩 설치 (파일이 있는 경우)
if exist LibreOffice_${version}_Win_x64_langpack_ko.msi (
    echo [2/3] 한글 언어팩 설치...
    msiexec /i LibreOffice_${version}_Win_x64_langpack_ko.msi /qb ALLUSERS=1
    echo 완료!
) else (
    echo [2/3] 한글 언어팩 건너뛰기 (파일 없음)
)
echo.

REM 도움말 설치 (파일이 있는 경우)
if exist LibreOffice_${version}_Win_x64_helppack_ko.msi (
    echo [3/3] 한글 도움말 설치...
    msiexec /i LibreOffice_${version}_Win_x64_helppack_ko.msi /qb ALLUSERS=1
    echo 완료!
) else (
    echo [3/3] 한글 도움말 건너뛰기 (파일 없음)
)
echo.

echo ============================================================
echo LibreOffice 설치 완료!
echo ============================================================
echo.
echo 설치 확인: "C:\Program Files\LibreOffice\program\soffice.exe" --version
echo.
pause
"@

$installScriptPath = Join-Path $downloadDir "install.bat"
$installScript | Out-File -FilePath $installScriptPath -Encoding ASCII

Write-Host ""
Write-Host "=" * 70
Write-Host "다운로드 완료!" -ForegroundColor Green
Write-Host "=" * 70
Write-Host ""
Write-Host "다운로드된 파일: $downloadDir"
Write-Host "  - 다운로드 파일 수: $downloadCount"
Write-Host ""
Write-Host "오프라인 PC로 전달 방법:"
Write-Host "  1. '$downloadDir' 폴더를 USB에 복사"
Write-Host "  2. 오프라인 PC로 USB 연결 후 폴더 복사"
Write-Host "  3. install.bat 파일을 관리자 권한으로 실행"
Write-Host ""
Write-Host "설치 파일 경로: $((Resolve-Path $downloadDir).Path)"
Write-Host ""

