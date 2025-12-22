+++"""
Java 기반 암복호화 툴 래퍼 모듈
"""
import os
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Tuple, List
from logger import logger
from config import (
    ENABLE_DECRYPTION,
    JAVA_EXECUTABLE,
    DECRYPTION_JAR_PATH,
    DECRYPTION_CLASS,
    CHECK_CLASS,
    DECRYPTED_DIR,
    DECRYPTION_TIMEOUT
)


class CryptoHandler:
    """Java 기반 암복호화 처리 클래스"""
    
    def __init__(self):
        self.enabled = ENABLE_DECRYPTION
        self.java_executable = JAVA_EXECUTABLE
        # 멀티 클래스패스 지원: OS 구분자(os.pathsep) 기준으로 분리
        self.classpath_raw = DECRYPTION_JAR_PATH or ""
        self.classpath_entries: List[Path] = self._parse_classpath_entries(self.classpath_raw)
        self.decryption_class = DECRYPTION_CLASS
        self.check_class = CHECK_CLASS
        self.decrypted_dir = DECRYPTED_DIR
        self.timeout = DECRYPTION_TIMEOUT
        
        # 초기화 확인
        if self.enabled:
            self._validate_configuration()
    
    def _parse_classpath_entries(self, raw: str) -> List[Path]:
        """환경변수에서 읽은 클래스패스 문자열을 OS 구분자로 분리하여 Path 리스트로 변환"""
        try:
            if not raw:
                return []
            # Windows: ';', POSIX: ':' 구분자 사용
            parts = [p for p in raw.split(os.pathsep) if p.strip()]
            expanded = [Path(os.path.expanduser(os.path.expandvars(p.strip()))) for p in parts]
            return expanded
        except Exception as e:
            logger.warning(f"클래스패스 파싱 실패: {e}")
            return []
    
    def _classpath_string(self) -> str:
        """subprocess 호출용 클래스패스 문자열 생성"""
        # subprocess.run()은 리스트 전달 시 자동으로 공백 처리하므로 따옴표 불필요
        return os.pathsep.join(str(p) for p in self.classpath_entries)
    
    def _validate_configuration(self) -> bool:
        """암복호화 설정 검증"""
        issues = []
        
        # Java 실행 파일 확인
        if not shutil.which(self.java_executable):
            issues.append(f"Java 실행 파일을 찾을 수 없습니다: {self.java_executable}")
        
        # 클래스패스 항목 확인 (JAR 또는 디렉터리)
        if not self.classpath_entries:
            issues.append("클래스패스가 비어 있습니다 (DECRYPTION_JAR_PATH)")
        else:
            missing = [p for p in self.classpath_entries if not p.exists()]
            if missing:
                for p in missing:
                    issues.append(f"클래스패스 경로가 존재하지 않습니다: {p}")
        
        # 클래스명 확인
        if not self.decryption_class:
            issues.append("복호화 클래스명이 설정되지 않았습니다 (DECRYPTION_CLASS)")
        
        if issues:
            logger.warning("="*80)
            logger.warning("암복호화 설정 문제 발견:")
            for issue in issues:
                logger.warning(f"  - {issue}")
            logger.warning("암복호화 기능이 비활성화됩니다.")
            logger.warning("="*80)
            self.enabled = False
            return False
        
        logger.info(f"✓ 암복호화 기능 활성화됨 (CLASSPATH: {self._classpath_string()})")
        return True
    
    def is_file_encrypted(self, file_path: Path) -> bool:
        """
        파일이 암호화되어 있는지 확인
        
        Args:
            file_path: 확인할 파일 경로
        
        Returns:
            True: 암호화됨, False: 암호화 안 됨
        """
        if not self.enabled:
            return False
        
        try:
            # CHECK_CLASS가 지정된 경우 사용
            if self.check_class:
                result = self._run_java_check(file_path)
                return result
            
        
        except Exception as e:
            logger.warning(f"암호화 체크 실패 ({file_path.name}): {e}")
            # 에러 시 안전하게 암호화되지 않은 것으로 간주
            return False
    
    def _run_java_check(self, file_path: Path) -> bool:
        """
        Java CHECK 클래스를 실행하여 암호화 여부 확인
        
        Args:
            file_path: 확인할 파일 경로
        
        Returns:
            True: 암호화됨, False: 암호화 안 됨
        """
        try:
            # Java 명령어 구성
            # 예: java -cp crypto.jar CheckClass "file_path"
            # subprocess.run()은 리스트 전달 시 자동으로 공백 처리하므로 따옴표 불필요
            cmd = [
                self.java_executable,
                '-cp',
                self._classpath_string(),
                self.check_class,
                str(file_path.resolve())
            ]
            
            logger.debug(f"암호화 체크 명령: {' '.join(cmd)}")
            
            # Java 프로세스 실행
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                encoding='utf-8',
                errors='ignore'
            )
            
            # 반환 코드로 판단
            # 0: 암호화 안 됨, 1: 암호화됨 (또는 그 반대, 실제 툴 동작에 맞게 수정)
            is_encrypted = result.returncode == 1
            
            if is_encrypted:
                logger.debug(f"파일 암호화 감지: {file_path.name}")
            else:
                logger.debug(f"파일 암호화 안 됨: {file_path.name}")
            
            return is_encrypted
        
        except subprocess.TimeoutExpired:
            logger.error(f"암호화 체크 타임아웃 ({self.timeout}초): {file_path.name}")
            return False
        
        except Exception as e:
            logger.error(f"암호화 체크 실패: {e}")
            return False
    
    def decrypt_file(self, encrypted_file: Path, output_name: str = None) -> Optional[Path]:
        """
        암호화된 파일 복호화
        
        Args:
            encrypted_file: 암호화된 파일 경로
            output_name: 복호화된 파일명 (None이면 원본명 사용)
        
        Returns:
            복호화된 파일 경로 또는 None (실패 시)
        """
        if not self.enabled:
            logger.warning("암복호화 기능이 비활성화되어 있습니다.")
            return None
        
        try:
            # 출력 파일명 결정
            if not output_name:
                output_name = encrypted_file.name
            
            # 복호화된 파일은 임시로 _dec 접미사를 붙여서 생성
            # (암호화 파일과 복호화 파일 이름이 달라야 하는 제약사항)
            file_stem = Path(output_name).stem
            file_suffix = Path(output_name).suffix
            temp_output_name = f"{file_stem}_dec{file_suffix}"
            
            # 복호화된 파일 저장 경로 (임시)
            decrypted_file_temp = self.decrypted_dir / temp_output_name
            # 최종 복호화 파일 경로
            decrypted_file_final = self.decrypted_dir / output_name
            
            logger.info(f"파일 복호화 시작: {encrypted_file.name}")
            
            # Java 명령어 구성
            # 방법 1: java -cp crypto.jar Dec "input_file" "output_file"
            # subprocess.run()은 리스트 전달 시 자동으로 공백 처리하므로 따옴표 불필요
            cmd = [
                self.java_executable,
                '-cp',
                self._classpath_string(),
                self.decryption_class,
                str(encrypted_file.resolve()),
                str(decrypted_file_temp.resolve())
            ]
            
            logger.debug(f"복호화 명령: {' '.join(cmd)}")
            
            # Java 프로세스 실행
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                encoding='utf-8',
                errors='ignore'
            )
            
            # 실행 결과 확인
            if result.returncode == 0 and decrypted_file_temp.exists():
                file_size = decrypted_file_temp.stat().st_size
                logger.info(f"✓ 파일 복호화 성공: {decrypted_file_temp.name} ({file_size} bytes)")
                
                # 후처리: 원본 암호화 파일 삭제 후 복호화 파일을 원본 이름으로 변경
                try:
                    # 1. 원본 암호화 파일 삭제
                    if encrypted_file.exists():
                        encrypted_file.unlink()
                        logger.debug(f"원본 암호화 파일 삭제: {encrypted_file.name}")
                    
                    # 2. 복호화 파일을 원본 이름으로 변경
                    decrypted_file_temp.rename(decrypted_file_final)
                    logger.info(f"복호화 파일 이름 변경: {temp_output_name} → {output_name}")
                    
                    return decrypted_file_final
                
                except Exception as e:
                    logger.error(f"후처리 중 오류 발생: {e}")
                    # 복호화는 성공했으므로 임시 파일이라도 반환
                    return decrypted_file_temp
            else:
                logger.error(f"✗ 파일 복호화 실패: {encrypted_file.name}")
                logger.error(f"   반환 코드: {result.returncode}")
                if result.stdout:
                    logger.debug(f"   stdout: {result.stdout}")
                if result.stderr:
                    logger.error(f"   stderr: {result.stderr}")
                return None
        
        except subprocess.TimeoutExpired:
            logger.error(f"파일 복호화 타임아웃 ({self.timeout}초): {encrypted_file.name}")
            return None
        
        except Exception as e:
            logger.error(f"파일 복호화 중 오류: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    
    def process_file_with_decryption(self, file_path: Path) -> Tuple[Path, bool]:
        """
        파일 처리 (암호화 체크 → 복호화)
        
        Args:
            file_path: 처리할 파일 경로
        
        Returns:
            (처리된 파일 경로, 복호화 여부)
            - 암호화 안 된 경우: (원본 파일, False)
            - 복호화 성공: (복호화된 파일, True)
            - 복호화 실패: (원본 파일, False)
        """
        if not self.enabled:
            return (file_path, False)
        
        try:
            # 1. 암호화 여부 확인
            if not self.is_file_encrypted(file_path):
                logger.debug(f"암호화되지 않은 파일: {file_path.name}")
                return (file_path, False)
            
            # 2. 암호화된 파일 → 복호화 시도
            logger.info(f"암호화된 파일 감지, 복호화 시작: {file_path.name}")
            decrypted_file = self.decrypt_file(file_path)
            
            if decrypted_file:
                return (decrypted_file, True)
            else:
                logger.warning(f"복호화 실패, 원본 파일 사용: {file_path.name}")
                return (file_path, False)
        
        except Exception as e:
            logger.error(f"암복호화 처리 중 오류: {e}")
            return (file_path, False)
    
    def cleanup_decrypted_files(self):
        """복호화된 파일 정리"""
        try:
            if self.decrypted_dir.exists():
                import shutil
                for file in self.decrypted_dir.iterdir():
                    if file.is_file():
                        file.unlink()
                logger.info("복호화된 파일 정리 완료")
        except Exception as e:
            logger.error(f"복호화된 파일 정리 실패: {e}")

