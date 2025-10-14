# 빠른 참조 가이드

## 📦 오프라인 설치 (폐쇄망)

### 인터넷 연결 환경 (패키지 다운로드)

```bash
# 1. 디렉토리 생성
mkdir -p rag_batch_offline/packages
cd rag_batch_offline

# 2. 패키지 다운로드
python -m pip download -r requirements.txt -d packages --python-version 3.11

# 3. 소스 복사
cp -r ../rag_batch ./

# 4. 압축
tar -czf rag_batch_offline.tar.gz .
```

### 폐쇄망 환경 (설치)

```bash
# 1. 압축 해제
tar -xzf rag_batch_offline.tar.gz
cd rag_batch

# 2. 가상환경 생성
python3.11 -m venv venv
source venv/bin/activate

# 3. 패키지 설치
pip install --no-index --find-links=../packages -r requirements.txt

# 4. 설정
cp env.example .env
nano .env

# 5. 실행
python run.py --once
```

---

## 🚀 일반 설치 (인터넷 연결)

```bash
# 1. 가상환경
python3.11 -m venv venv
source venv/bin/activate

# 2. 패키지 설치
pip install -r requirements.txt

# 3. 설정
cp env.example .env
nano .env

# 4. 실행
python run.py --once
```

---

## ⚙️ .env 설정 (필수)

```bash
RAGFLOW_API_KEY=your_api_key_here
RAGFLOW_BASE_URL=http://192.168.10.41
DATASET_PERMISSION=team
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
EXCEL_FILE_PATH=./data/input.xlsx
```

---

## 🎯 명령어

```bash
# 1회 실행
python run.py --once

# 스케줄 실행
python run.py

# 파싱 상태 확인
python diagnose_parsing.py

# 연결 테스트
python test_ragflow.py
```

---

## 📊 Excel 형식

| 컬럼명 | 설명 | 예시 |
|--------|------|------|
| 제목 | 문서 제목 | KTX 매뉴얼 |
| 하이퍼링크 | 파일 URL | http://example.com/file.pdf |
| 비고 | 추가 정보 | 2025년 1월 |

---

## 🔍 문제 해결

### 업로드 실패
```bash
# 로그 확인
tail -f logs/batch_YYYYMMDD.log

# 파일 권한
chmod 644 data/input.xlsx
```

### 파싱 실패
```bash
# 상태 확인
python diagnose_parsing.py

# 임베딩 모델 확인
grep EMBEDDING_MODEL .env
```

---

## 📞 상세 문서

- 전체 가이드: `README_BATCH.md`
- 오프라인 설치: `docs/OFFLINE_INSTALL.md`
- 프로세스 상세: `PROCESS.md`
- 구현 노트: `docs/IMPLEMENTATION_NOTE.md`

