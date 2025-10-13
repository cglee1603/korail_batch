# 변경 이력

## [1.1.0] - 2025-10-13

### 추가
- ✅ **HWP → PDF 자동 변환 기능 완전 구현**
  - LibreOffice를 사용한 실제 변환 기능
  - Windows/Linux 환경 모두 지원
  - 타임아웃 및 오류 처리
  - 변환 실패 시 원본 업로드 대체 로직
  
- ✅ **Linux 환경 완전 지원**
  - systemd 서비스 설정 예시
  - cron 작업 설정 예시
  - 자동 시작 스크립트
  
- ✅ **Docker 배포 지원**
  - Dockerfile 및 docker-compose.yml
  - 컨테이너 환경 최적화
  
- ✅ **문서 추가**
  - HWP_CONVERSION.md (HWP 변환 상세 가이드)
  - LINUX_DEPLOYMENT.md (Linux 배포 가이드)
  
- ✅ **프로젝트 구조 개선**
  - src/, scripts/, docs/ 디렉토리로 재구성
  - run.py 진입점 추가
  - 더 명확한 모듈 구조

### 변경
- requirements.txt에서 hwp5 제거 (Windows 호환성 문제)
- Python 지원 버전 명시 (3.10, 3.11, 3.12)

### 수정
- LibreOffice 실행 파일 자동 감지 개선
- 한글 폰트 지원 확인 로직 추가
- 변환 타임아웃 설정 (기본 5분)

### 제거
- HWP 변환 스터브 제거 (실제 구현으로 대체)

## [1.0.0] - 2025-05-15

### 추가
- 엑셀 파일 자동 처리 기능
  - 다중 시트 지원
  - 헤더 자동 감지
  - 하이퍼링크 자동 추출
  - 숨김 행 자동 제외
  
- 파일 처리 기능
  - 로컬 파일 복사
  - URL 파일 다운로드
  - HWP → PDF 변환 (스터브)
  - ZIP 압축 해제 및 개별 처리
  
- RAGFlow 연동 기능
  - 지식베이스 자동 생성
  - 파일 자동 업로드
  - 메타데이터 자동 추가
  - 일괄 파싱 실행
  
- 스케줄링 기능
  - 특정 시간 실행
  - 주기적 실행
  - 다중 시간대 실행
  
- 로깅 시스템
  - 날짜별 로그 파일
  - 콘솔 및 파일 출력
  - 상세 처리 내역
  - 통계 정보
  
- 문서
  - README.md (상세 가이드)
  - QUICK_START.md (빠른 시작)
  - EXAMPLES.md (사용 예시)
  - TROUBLESHOOTING.md (문제 해결)
  
- 유틸리티
  - setup.py (초기 설정)
  - test_excel_read.py (엑셀 테스트)
  - copy_sample.py (샘플 복사)
  - start.bat, start.ps1 (시작 스크립트)

### 알려진 제한사항
- 대용량 파일 처리 시 메모리 사용량 증가

### 구현 완료
- ✅ 메타데이터 설정: RAGFlow SDK의 `document.update()` 메서드 사용
  - 엑셀 행 데이터를 메타데이터로 자동 추가
  - 원본 파일 정보, 파일 형식, 행번호 등 자동 추가
- ✅ HWP 파일 변환: LibreOffice를 통한 완전 구현

### 향후 계획
- 멀티스레딩을 통한 성능 개선
- 재시도 로직 추가
- 진행률 표시
- 웹 대시보드
- tar.gz, tar.xz 압축 형식 지원

