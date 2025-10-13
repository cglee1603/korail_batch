"""
샘플 엑셀 파일을 data 폴더로 복사하는 스크립트
"""
import shutil
from pathlib import Path

# 경로 설정 (scripts 폴더 기준)
script_dir = Path(__file__).parent
project_root = script_dir.parent
sample_file = project_root.parent / "sample_excel" / "20250515_KTX-DATA_EMU.xlsx"
dest_dir = project_root / "data"
dest_file = dest_dir / sample_file.name

# 복사
if sample_file.exists():
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sample_file, dest_file)
    print(f"[OK] 파일 복사 완료: {dest_file}")
else:
    print(f"[ERROR] 샘플 파일을 찾을 수 없습니다: {sample_file}")

