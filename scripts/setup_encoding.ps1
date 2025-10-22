# PowerShell 한글 인코딩 설정 스크립트
# 프로젝트 실행 전에 이 스크립트를 실행하거나 프로필에 추가하세요

Write-Host "=" -NoNewline; Write-Host ("=" * 68)
Write-Host "PowerShell 한글 인코딩 설정"
Write-Host "=" -NoNewline; Write-Host ("=" * 68)
Write-Host ""

# 현재 인코딩 상태 표시
Write-Host "[현재 설정]" -ForegroundColor Cyan
Write-Host "  코드 페이지: " -NoNewline
chcp
Write-Host "  출력 인코딩: $([Console]::OutputEncoding.EncodingName)"
Write-Host "  PowerShell 인코딩: $($OutputEncoding.EncodingName)"
Write-Host ""

# UTF-8로 설정
Write-Host "[UTF-8로 변경]" -ForegroundColor Green
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$global:OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 > $null

# Python 환경변수 설정
$env:PYTHONIOENCODING = "utf-8"

# 기본 인코딩 파라미터 설정
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
$PSDefaultParameterValues['Set-Content:Encoding'] = 'utf8'

Write-Host "  코드 페이지: UTF-8 (65001)"
Write-Host "  출력 인코딩: $([Console]::OutputEncoding.EncodingName)"
Write-Host "  PowerShell 인코딩: $($OutputEncoding.EncodingName)"
Write-Host "  Python 인코딩: $env:PYTHONIOENCODING"
Write-Host ""

# 테스트
Write-Host "[한글 테스트]" -ForegroundColor Yellow
Write-Host "  한글이 정상적으로 표시됩니다: 가나다라마바사 ✓"
Write-Host "  특수문자: ✓ ✗ ⚠ ★ ☆"
Write-Host ""

# 프로필 추가 안내
Write-Host "[영구 적용 방법]" -ForegroundColor Magenta
Write-Host "  다음 내용을 PowerShell 프로필에 추가하세요:"
Write-Host ""
Write-Host "  # PowerShell 프로필 편집" -ForegroundColor Gray
Write-Host "  notepad `$PROFILE" -ForegroundColor Gray
Write-Host ""
Write-Host "  # 아래 내용 추가" -ForegroundColor Gray
Write-Host "  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8" -ForegroundColor DarkGray
Write-Host "  `$OutputEncoding = [System.Text.Encoding]::UTF8" -ForegroundColor DarkGray
Write-Host "  chcp 65001 > `$null" -ForegroundColor DarkGray
Write-Host "  `$env:PYTHONIOENCODING = `"utf-8`"" -ForegroundColor DarkGray
Write-Host ""

# 프로필 자동 추가 옵션
Write-Host "[자동 추가]" -ForegroundColor Cyan
$response = Read-Host "PowerShell 프로필에 자동으로 추가하시겠습니까? (Y/N)"

if ($response -eq 'Y' -or $response -eq 'y') {
    # 프로필 파일 경로
    $profilePath = $PROFILE
    
    # 프로필 디렉토리 생성 (없는 경우)
    $profileDir = Split-Path -Parent $profilePath
    if (!(Test-Path $profileDir)) {
        New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
    }
    
    # 프로필 파일 생성 (없는 경우)
    if (!(Test-Path $profilePath)) {
        New-Item -ItemType File -Path $profilePath -Force | Out-Null
    }
    
    # 설정 내용
    $encodingConfig = @"

# ============================================================
# 한글 인코딩 설정 (UTF-8)
# 자동 추가됨: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
# ============================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
`$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 > `$null

# Python 인코딩 설정
`$env:PYTHONIOENCODING = "utf-8"

# 파일 작업 기본 인코딩
`$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
`$PSDefaultParameterValues['Set-Content:Encoding'] = 'utf8'

"@
    
    # 기존 프로필에 추가 (중복 방지)
    $profileContent = Get-Content -Path $profilePath -Raw -ErrorAction SilentlyContinue
    
    if ($profileContent -notlike "*한글 인코딩 설정*") {
        Add-Content -Path $profilePath -Value $encodingConfig -Encoding UTF8
        Write-Host ""
        Write-Host "✓ 프로필에 인코딩 설정이 추가되었습니다." -ForegroundColor Green
        Write-Host "  파일: $profilePath"
        Write-Host ""
        Write-Host "다음 PowerShell 세션부터 자동으로 적용됩니다." -ForegroundColor Yellow
    }
    else {
        Write-Host ""
        Write-Host "⚠ 프로필에 이미 인코딩 설정이 존재합니다." -ForegroundColor Yellow
        Write-Host "  파일: $profilePath"
    }
}
else {
    Write-Host ""
    Write-Host "현재 세션에만 적용되었습니다." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=" -NoNewline; Write-Host ("=" * 68)
Write-Host "설정 완료"
Write-Host "=" -NoNewline; Write-Host ("=" * 68)
Write-Host ""

