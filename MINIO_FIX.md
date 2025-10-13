# MinIO 파일 저장 문제 해결

## 🔍 문제 원인

### 발생한 문제
- API로 업로드한 파일이 RAGFlow UI에서 다운로드 불가 (500 에러)
- 파싱 실패: "저장소 버킷이 존재하지 않습니다"
- MinIO에 파일은 저장되지만 참조 정보가 손상됨

### 근본 원인
```python
# rag_batch/src/ragflow_client.py - upload_document() 메서드

# 1. 파일 업로드 (✅ MinIO에 저장됨)
uploaded_docs = dataset.upload_documents([doc_info])

# 2. 메타데이터 업데이트 (❌ MinIO 참조 손상)
doc.update({"meta_fields": metadata})  # PUT 요청
# → 문서 정보 업데이트 중 MinIO 파일 참조가 덮어쓰기됨
# → 다운로드 시 파일을 찾을 수 없음
# → 파싱 시 파일을 읽을 수 없음
```

### 왜 UI 업로드는 정상인가?
- **UI 업로드**: 메타데이터 업데이트 없이 업로드만 수행
- **API 업로드**: 업로드 후 즉시 `doc.update()` 호출 → 파일 참조 손상

---

## ✅ 해결 방법

### 변경 사항
`rag_batch/src/ragflow_client.py` - `upload_document()` 메서드에서 메타데이터 업데이트 제거:

```python
# 변경 전 (문제 있음)
uploaded_docs = dataset.upload_documents([doc_info])
logger.info(f"✓ 파일 업로드 성공: {display_name}")

if metadata:
    doc = uploaded_docs[0]
    self.set_document_metadata(doc, metadata)  # ❌ MinIO 참조 손상

return True
```

```python
# 변경 후 (해결됨)
uploaded_docs = dataset.upload_documents([doc_info])
logger.info(f"✓ 파일 업로드 성공: {display_name}")

# 메타데이터 업데이트 주석 처리 - MinIO 파일 참조 손상 방지
# if metadata:
#     doc = uploaded_docs[0]
#     self.set_document_metadata(doc, metadata)

if metadata:
    logger.debug(f"메타데이터 (미적용): {metadata}")  # 로그만 기록

return True
```

---

## 🧪 테스트 방법

### 1. 수정된 파일 서버에 업로드 (Windows PowerShell)

```powershell
cd C:\work\철도공사\ragplus\ragflow-plus

scp rag_batch\src\ragflow_client.py root@192.168.10.41:/home/ragflow-batch/korail_batch/src/
scp rag_batch\test_minio_fix.py root@192.168.10.41:/home/ragflow-batch/korail_batch/
```

### 2. 리눅스 서버에서 테스트 실행

```bash
cd /home/ragflow-batch/korail_batch
source venv/bin/activate
python test_minio_fix.py
```

### 3. 예상 결과 (성공)

```
3. 파일 업로드 (메타데이터 업데이트 없이)...
✓ 업로드 성공

4. 업로드된 문서 확인...
   문서 수: 1
   문서 ID: abc123...
   파일 크기: 500 bytes

5. 다운로드 테스트 (MinIO 저장 확인)...
✅ 다운로드 성공!
   다운로드된 크기: 500 bytes
   원본 크기: 500 bytes
✅ 파일 내용 일치! MinIO 저장 정상!

🎉 메타데이터 업데이트 제거로 MinIO 저장 문제 해결!

6. 파싱 테스트...
✓ 파싱 요청 완료
   10초 대기 중...

파싱 결과:
   상태 (run): DONE
   진행률: 1.0
✅ 파싱 완료!
   청크 수: 5
   토큰 수: 120
```

---

## 📊 메타데이터 대안

### 옵션 1: 파일명에 메타데이터 포함 (추천)
```python
# batch_processor.py에서
original_name = "KTX_매뉴얼.pdf"
row_number = 42
display_name = f"[행{row_number}]_{original_name}"

# 업로드 시
client.upload_document(
    dataset=dataset,
    file_path=file_path,
    display_name=display_name,  # "[행42]_KTX_매뉴얼.pdf"
    metadata=None  # 메타데이터 사용 안 함
)
```

### 옵션 2: 별도 CSV/JSON 파일로 관리
```python
# 메타데이터를 별도 파일로 저장
metadata_log = {
    "document_id": "abc123",
    "original_file": "KTX_매뉴얼.pdf",
    "excel_row": 42,
    "hyperlink": "http://..."
}

# metadata.json 또는 metadata.csv로 저장
```

### 옵션 3: RAGFlow가 안정화되면 재시도
- RAGFlow SDK 업데이트 대기
- `doc.update()` 버그 수정 확인 후 메타데이터 다시 활성화

---

## 🎯 최종 확인 사항

### ✅ 해결 확인
- [ ] 파일 다운로드 성공 (RAGFlow UI 및 API)
- [ ] 파싱 완료 (DONE 상태)
- [ ] 청크 및 토큰 생성 확인
- [ ] 실제 배치 프로세스 정상 작동

### ⚠️ 메타데이터 제한 사항
- 원본_파일, 파일_형식, 엑셀_행번호, 하이퍼링크 정보가 RAGFlow에 저장되지 않음
- 필요 시 위의 대안 방법 사용

### 📝 향후 계획
1. 테스트 완료 후 실제 배치 실행
2. 메타데이터 필요 여부 판단
3. 필요 시 파일명에 메타데이터 포함 방식으로 수정

---

## 📞 문제 지속 시 확인 사항

1. **RAGFlow 로그 확인**
   ```bash
   docker logs ragflow-server | tail -100
   ```

2. **MinIO 버킷 확인**
   - MinIO UI: http://192.168.10.41:9001
   - 버킷: `ragflow`
   - 업로드된 파일 존재 여부 확인

3. **데이터베이스 확인**
   ```sql
   SELECT id, name, size, location, status 
   FROM document 
   WHERE dataset_id = 'xxx';
   ```

4. **다운로드 API 직접 테스트**
   ```bash
   curl -X GET "http://192.168.10.41/api/v1/datasets/{dataset_id}/documents/{doc_id}" \
        -H "Authorization: Bearer {api_key}"
   ```

