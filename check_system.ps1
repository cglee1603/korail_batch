# 시스템 환경 확인 스크립트
Write-Host "=" * 80
Write-Host "시스템 환경 정보 확인"
Write-Host "=" * 80

Write-Host "`n[1] Python 버전"
python --version

Write-Host "`n[2] Python 상세 정보"
python -c "import sys; import platform; print(f'Python: {sys.version}'); print(f'Architecture: {platform.architecture()}'); print(f'Platform: {sys.platform}'); print(f'Machine: {platform.machine()}')"

Write-Host "`n[3] pip 버전"
pip --version

Write-Host "`n[4] 현재 설치된 패키지 목록 (pywin32 관련)"
pip list | Select-String -Pattern "pywin32"

Write-Host "`n[5] pip로 설치 가능한 pywin32 버전 확인"
pip index versions pywin32

Write-Host "`n[6] 가상환경 확인"
python -c "import sys; print('가상환경:', hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))"

Write-Host "`n[7] 현재 작업 디렉토리"
Get-Location

Write-Host "`n" + "=" * 80
Write-Host "확인 완료"
Write-Host "=" * 80


