"""
MinIO 저장소에서 실제 파일 경로 확인
"""
import sys
from pathlib import Path

# src 디렉토리를 Python 경로에 추가
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from ragflow_sdk import RAGFlow
from config import RAGFLOW_API_KEY, RAGFLOW_BASE_URL
from logger import logger
import subprocess


def check_minio_paths():
    """RAGFlow 문서의 MinIO 저장 경로 확인"""
    logger.info("="*80)
    logger.info("MinIO 저장 경로 확인")
    logger.info("="*80)
    
    try:
        rag = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)
        
        # 모든 지식베이스 조회
        datasets = rag.list_datasets()
        logger.info(f"\n총 {len(datasets)}개 지식베이스 발견\n")
        
        all_locations = []
        
        for idx, dataset in enumerate(datasets, 1):
            logger.info(f"{'='*80}")
            logger.info(f"[{idx}/{len(datasets)}] 지식베이스: {dataset.name}")
            logger.info(f"{'='*80}")
            logger.info(f"Dataset ID: {dataset.id}")
            
            # 문서 목록 조회
            documents = dataset.list_documents()
            logger.info(f"문서 수: {len(documents)}\n")
            
            for doc_idx, doc in enumerate(documents, 1):
                logger.info(f"  [{doc_idx}/{len(documents)}] 문서: {doc.name}")
                logger.info(f"  {'-'*70}")
                logger.info(f"    문서 ID: {doc.id}")
                logger.info(f"    Dataset ID: {doc.dataset_id if hasattr(doc, 'dataset_id') else 'N/A'}")
                logger.info(f"    파일 크기: {doc.size} bytes")
                logger.info(f"    타입: {doc.type}")
                
                # location 속성 확인
                if hasattr(doc, 'location') and doc.location:
                    logger.info(f"    Location: {doc.location}")
                    all_locations.append({
                        'kb_name': dataset.name,
                        'doc_name': doc.name,
                        'location': doc.location,
                        'doc_id': doc.id,
                        'dataset_id': doc.dataset_id if hasattr(doc, 'dataset_id') else None
                    })
                else:
                    logger.warning(f"    Location: 없음")
                
                # 기타 저장소 관련 속성 확인
                for attr in ['kb_id', 'tenant_id', 'created_by', 'source_type']:
                    if hasattr(doc, attr):
                        value = getattr(doc, attr)
                        logger.info(f"    {attr}: {value}")
                
                # 가능한 MinIO 경로 추측
                possible_paths = []
                
                # 패턴 1: tenant_id/kb_id/doc_id
                if hasattr(doc, 'created_by') and hasattr(doc, 'dataset_id'):
                    path1 = f"{doc.created_by}/{doc.dataset_id}/{doc.id}"
                    possible_paths.append(path1)
                
                # 패턴 2: kb_id/doc_id
                if hasattr(doc, 'dataset_id'):
                    path2 = f"{doc.dataset_id}/{doc.id}"
                    possible_paths.append(path2)
                
                # 패턴 3: doc_id
                path3 = f"{doc.id}"
                possible_paths.append(path3)
                
                # 패턴 4: doc_id.확장자
                if doc.type:
                    path4 = f"{doc.id}.{doc.type}"
                    possible_paths.append(path4)
                
                if possible_paths:
                    logger.info(f"\n    예상 MinIO 경로:")
                    for p in possible_paths:
                        logger.info(f"      - {p}")
                
                logger.info("")
        
        # MinIO 실제 내용 확인
        logger.info(f"\n{'='*80}")
        logger.info("MinIO 버킷 내용 확인")
        logger.info(f"{'='*80}\n")
        
        # MinIO 버킷 목록
        logger.info("1. MinIO 버킷 목록:")
        try:
            result = subprocess.run(
                ["docker", "exec", "ragflow-minio", "mc", "ls", "local/"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info(result.stdout)
            else:
                logger.warning(f"mc ls 실패: {result.stderr}")
        except Exception as e:
            logger.warning(f"MinIO CLI 명령 실패: {e}")
            logger.info("Docker 명령어로 직접 확인:")
            logger.info("  docker exec ragflow-minio mc ls local/")
        
        # ragflow 버킷 내용
        logger.info("\n2. ragflow 버킷 내용:")
        try:
            result = subprocess.run(
                ["docker", "exec", "ragflow-minio", "mc", "ls", "local/ragflow/"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info(result.stdout)
                
                # 첫 번째 레벨 디렉토리들 확인
                lines = result.stdout.strip().split('\n')
                dirs = [line.split()[-1].strip('/') for line in lines if 'DIR' in line or line.endswith('/')]
                
                if dirs:
                    logger.info(f"\n3. ragflow 버킷 하위 디렉토리 ({len(dirs)}개):")
                    for dir_name in dirs[:5]:  # 처음 5개만
                        logger.info(f"\n   디렉토리: {dir_name}")
                        try:
                            sub_result = subprocess.run(
                                ["docker", "exec", "ragflow-minio", "mc", "ls", f"local/ragflow/{dir_name}/"],
                                capture_output=True,
                                text=True,
                                timeout=10
                            )
                            if sub_result.returncode == 0:
                                # 처음 3줄만 표시
                                sub_lines = sub_result.stdout.strip().split('\n')[:3]
                                for line in sub_lines:
                                    logger.info(f"     {line}")
                                if len(sub_result.stdout.strip().split('\n')) > 3:
                                    logger.info(f"     ... (더 많은 파일)")
                        except:
                            pass
            else:
                logger.warning(f"ragflow 버킷 조회 실패: {result.stderr}")
        except Exception as e:
            logger.warning(f"MinIO 버킷 조회 실패: {e}")
        
        # 요약
        logger.info(f"\n{'='*80}")
        logger.info("요약")
        logger.info(f"{'='*80}")
        logger.info(f"총 문서 수: {len(all_locations)}")
        
        if all_locations:
            logger.info(f"\nLocation 속성이 있는 문서:")
            for loc_info in all_locations:
                logger.info(f"\n  KB: {loc_info['kb_name']}")
                logger.info(f"  문서: {loc_info['doc_name']}")
                logger.info(f"  Location: {loc_info['location']}")
        
        logger.info(f"\n{'='*80}")
        logger.info("MinIO 직접 확인 명령어:")
        logger.info(f"{'='*80}")
        logger.info("# 버킷 목록")
        logger.info("docker exec ragflow-minio mc ls local/")
        logger.info("")
        logger.info("# ragflow 버킷 내용")
        logger.info("docker exec ragflow-minio mc ls local/ragflow/")
        logger.info("")
        logger.info("# 특정 경로 확인 (예시)")
        if all_locations and all_locations[0].get('doc_id'):
            doc_id = all_locations[0]['doc_id']
            logger.info(f"docker exec ragflow-minio mc ls local/ragflow/ | grep {doc_id[:8]}")
        
        logger.info(f"\n{'='*80}")
    
    except Exception as e:
        logger.error(f"오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    check_minio_paths()

