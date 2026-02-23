#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
다운로드 캐시 수동 정리 스크립트

사용법:
  python scripts/clean_download_cache.py              # 7일 이상된 캐시 정리
  python scripts/clean_download_cache.py --days 30    # 30일 이상된 캐시 정리
  python scripts/clean_download_cache.py --all        # 전체 캐시 정리
  python scripts/clean_download_cache.py --db-only    # DB만 정리 (파일 유지)
"""
import sys
import argparse
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from revision_db import RevisionDB
from logger import logger


def main():
    parser = argparse.ArgumentParser(
        description="다운로드 캐시 정리 (DB 레코드 + 실제 파일)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  %(prog)s                    # 기본값: 7일 이상된 캐시 정리
  %(prog)s --days 30          # 30일 이상된 캐시 정리
  %(prog)s --all              # 전체 캐시 정리
  %(prog)s --db-only          # DB만 정리 (파일은 유지)
  %(prog)s --days 14 --db-only  # 14일 이상된 DB만 정리
        """
    )
    
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='보관할 캐시 일수 (이보다 오래된 캐시만 삭제, 기본값: 7일)'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='전체 캐시 삭제 (--days 무시)'
    )
    
    parser.add_argument(
        '--db-only',
        action='store_true',
        help='DB 레코드만 삭제 (실제 파일은 유지)'
    )
    
    args = parser.parse_args()
    
    try:
        # RevisionDB 초기화
        logger.info("=" * 60)
        logger.info("다운로드 캐시 정리 시작")
        logger.info("=" * 60)
        
        revision_db = RevisionDB()
        
        # 정리 전 통계
        stats_before = revision_db.get_statistics()
        logger.info(f"현재 캐시: {stats_before['cached_downloads']}개")
        
        # 캐시 정리
        delete_files = not args.db_only
        
        if args.all:
            logger.info("전체 캐시 정리 중...")
            deleted = revision_db.clear_mt_download_cache(
                older_than_days=None,
                delete_files=delete_files
            )
        else:
            logger.info(f"{args.days}일 이상된 캐시 정리 중...")
            deleted = revision_db.clear_mt_download_cache(
                older_than_days=args.days,
                delete_files=delete_files
            )
        
        # 정리 후 통계
        stats_after = revision_db.get_statistics()
        logger.info(f"정리 후 캐시: {stats_after['cached_downloads']}개")
        
        logger.info("=" * 60)
        logger.info(f"✓ 정리 완료: {deleted}개 삭제")
        logger.info("=" * 60)
        
        revision_db.close()
        
    except KeyboardInterrupt:
        logger.warning("\n사용자에 의해 중단됨")
        sys.exit(1)
    except Exception as e:
        logger.error(f"캐시 정리 중 오류: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

