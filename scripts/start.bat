@echo off
REM RAGFlow Plus 배치 프로그램 시작 스크립트 (Windows)

echo ====================================
echo RAGFlow Plus 배치 프로그램
echo ====================================
echo.

REM 프로젝트 루트로 이동
cd /d %~dp0\..

REM 가상환경 활성화 (있는 경우)
if exist venv\Scripts\activate.bat (
    echo 가상환경 활성화 중...
    call venv\Scripts\activate.bat
)

REM 배치 프로그램 실행
python run.py %*

pause

