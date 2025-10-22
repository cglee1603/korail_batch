"""
파일 다운로드 및 변환 처리 모듈
"""
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Optional, List, Tuple
from urllib.parse import urlparse, unquote
import requests
from logger import logger
from config import DOWNLOAD_DIR, TEMP_DIR


class FileHandler:
    """파일 다운로드 및 변환 처리 클래스"""
    
    def __init__(self):
        self.download_dir = DOWNLOAD_DIR
        self.temp_dir = TEMP_DIR
    
    def is_url(self, path: str) -> bool:
        """URL인지 파일 경로인지 판별"""
        try:
            result = urlparse(path)
            return result.scheme in ('http', 'https', 'ftp')
        except:
            return False
    
    def download_file(self, url: str, save_name: Optional[str] = None) -> Optional[Path]:
        """
        URL에서 파일 다운로드
        
        Args:
            url: 다운로드할 파일 URL
            save_name: 저장할 파일명 (None이면 URL에서 추출)
        
        Returns:
            다운로드된 파일 경로 또는 None
        """
        try:
            if not save_name:
                # URL에서 파일명 추출
                parsed = urlparse(url)
                save_name = unquote(Path(parsed.path).name)
                if not save_name:
                    save_name = f"download_{os.urandom(4).hex()}"
            
            save_path = self.download_dir / save_name
            
            logger.info(f"파일 다운로드 시작: {url}")
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"파일 다운로드 완료: {save_path}")
            return save_path
        
        except Exception as e:
            logger.error(f"파일 다운로드 실패 ({url}): {e}")
            return None
    
    def copy_local_file(self, file_path: str) -> Optional[Path]:
        """
        로컬 파일을 작업 디렉토리로 복사
        
        Args:
            file_path: 로컬 파일 경로
        
        Returns:
            복사된 파일 경로 또는 None
        """
        try:
            src_path = Path(file_path)
            if not src_path.exists():
                logger.error(f"파일이 존재하지 않습니다: {file_path}")
                return None
            
            # 목적지 경로
            dest_path = self.download_dir / src_path.name
            
            # 파일 복사
            shutil.copy2(src_path, dest_path)
            logger.info(f"파일 복사 완료: {src_path} -> {dest_path}")
            
            return dest_path
        
        except Exception as e:
            logger.error(f"파일 복사 실패 ({file_path}): {e}")
            return None
    
    def get_file(self, path: str) -> Optional[Path]:
        """
        URL 또는 로컬 파일 경로에서 파일 가져오기
        
        Args:
            path: URL 또는 로컬 파일 경로
        
        Returns:
            파일 경로 또는 None
        """
        if self.is_url(path):
            return self.download_file(path)
        else:
            return self.copy_local_file(path)
    
    def convert_hwp_to_pdf(self, hwp_path: Path) -> Optional[Path]:
        """
        HWP 파일을 PDF로 변환
        
        Windows: 한글 프로그램 COM 우선 시도 → 실패 시 LibreOffice
        Linux: LibreOffice 사용
        """
        try:
            import platform
            
            pdf_path = hwp_path.with_suffix('.pdf')
            
            logger.info(f"HWP->PDF 변환 시작: {hwp_path}")
            
            result = False
            
            # Windows에서 한글 프로그램 우선 시도
            if platform.system() == 'Windows':
                logger.info("Windows 환경 감지 - 한글 프로그램으로 변환 시도")
                result = self._convert_with_hwp_com(hwp_path, pdf_path)
                
                if result:
                    logger.info(f"한글 프로그램으로 변환 완료: {pdf_path}")
                    return pdf_path
                else:
                    logger.warning("한글 프로그램 변환 실패 - LibreOffice로 재시도")
            
            # 한글 프로그램 실패 또는 Linux인 경우 LibreOffice 사용
            result = self._convert_with_libreoffice(hwp_path, pdf_path)
            
            if result:
                logger.info(f"HWP->PDF 변환 완료: {pdf_path}")
                return pdf_path
            else:
                logger.error(f"HWP->PDF 변환 실패: {hwp_path}")
                # 변환 실패 시 원본 파일 반환
                logger.warning(f"원본 HWP 파일을 그대로 사용: {hwp_path}")
                return hwp_path
        
        except Exception as e:
            logger.error(f"HWP->PDF 변환 실패 ({hwp_path}): {e}")
            return hwp_path  # 원본 반환
    
    def _convert_with_hwp_com(self, hwp_path: Path, pdf_path: Path) -> bool:
        """
        Windows 한글 프로그램 COM을 사용한 HWP → PDF 변환
        
        Args:
            hwp_path: 원본 HWP 파일 경로
            pdf_path: 출력 PDF 파일 경로
        
        Returns:
            변환 성공 여부
        """
        try:
            # pywin32 패키지 필요
            import win32com.client
            import pythoncom
            
            logger.info("한글 프로그램 COM 초기화 시작")
            
            # COM 초기화
            pythoncom.CoInitialize()
            
            try:
                # 한글 프로그램 COM 객체 생성
                hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
                
                # HWP 파일 열기
                abs_hwp_path = str(hwp_path.resolve())
                logger.info(f"HWP 파일 열기: {abs_hwp_path}")
                
                # Open 메서드: path, format, arg
                result = hwp.Open(abs_hwp_path, "HWP", "")
                
                if not result:
                    logger.error("HWP 파일 열기 실패")
                    hwp.Quit()
                    return False
                
                # PDF로 저장
                abs_pdf_path = str(pdf_path.resolve())
                logger.info(f"PDF로 저장: {abs_pdf_path}")
                
                # SaveAs 메서드: path, format, arg
                # PDF 포맷 코드: "PDF"
                hwp.SaveAs(abs_pdf_path, "PDF", "")
                
                # 한글 프로그램 종료
                hwp.Quit()
                
                # PDF 파일 생성 확인
                if pdf_path.exists():
                    logger.info(f"한글 프로그램으로 PDF 변환 성공: {pdf_path}")
                    return True
                else:
                    logger.error(f"PDF 파일이 생성되지 않았습니다: {pdf_path}")
                    return False
            
            finally:
                # COM 정리
                pythoncom.CoUninitialize()
        
        except ImportError:
            logger.warning("pywin32 패키지가 설치되지 않았습니다.")
            logger.warning("설치 방법: pip install pywin32")
            return False
        
        except Exception as e:
            logger.error(f"한글 프로그램 COM 변환 중 오류: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def _convert_with_libreoffice(self, hwp_path: Path, pdf_path: Path) -> bool:
        """
        LibreOffice를 사용한 HWP → PDF 변환
        
        Args:
            hwp_path: 원본 HWP 파일 경로
            pdf_path: 출력 PDF 파일 경로
        
        Returns:
            변환 성공 여부
        """
        try:
            import platform
            
            # LibreOffice 실행 파일 찾기
            if platform.system() == 'Windows':
                # Windows 경로
                soffice_paths = [
                    r"C:\Program Files\LibreOffice\program\soffice.exe",
                    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
                    "soffice",  # PATH에 있는 경우
                ]
            else:
                # Linux/Mac 경로
                soffice_paths = [
                    "/usr/bin/soffice",
                    "/usr/bin/libreoffice",
                    "soffice",
                    "libreoffice",
                ]
            
            soffice_cmd = None
            for path in soffice_paths:
                if shutil.which(path) or Path(path).exists():
                    soffice_cmd = path
                    break
            
            if not soffice_cmd:
                logger.error("LibreOffice를 찾을 수 없습니다. 설치 필요:")
                logger.error("  Ubuntu/Debian: sudo apt-get install libreoffice")
                logger.error("  CentOS/RHEL: sudo yum install libreoffice")
                logger.error("  Windows: https://www.libreoffice.org/download/download/")
                return False
            
            # 출력 디렉토리
            output_dir = pdf_path.parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # LibreOffice 명령 실행
            cmd = [
                soffice_cmd,
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', str(output_dir),
                str(hwp_path)
            ]
            
            logger.info(f"LibreOffice 명령 실행: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5분 타임아웃
            )
            
            if result.returncode == 0:
                # LibreOffice는 원본 파일명.pdf로 저장하므로 확인
                generated_pdf = output_dir / f"{hwp_path.stem}.pdf"
                
                if generated_pdf.exists():
                    # 목표 경로와 다르면 이동
                    if generated_pdf != pdf_path:
                        shutil.move(str(generated_pdf), str(pdf_path))
                    
                    logger.info(f"LibreOffice 변환 성공: {pdf_path}")
                    return True
                else:
                    logger.error(f"PDF 파일이 생성되지 않았습니다: {generated_pdf}")
                    return False
            else:
                logger.error(f"LibreOffice 변환 실패 (exit code: {result.returncode})")
                logger.error(f"stdout: {result.stdout}")
                logger.error(f"stderr: {result.stderr}")
                return False
        
        except subprocess.TimeoutExpired:
            logger.error(f"HWP 변환 타임아웃 (5분 초과): {hwp_path}")
            return False
        except Exception as e:
            logger.error(f"LibreOffice 변환 중 오류: {e}")
            return False
    
    def extract_zip(self, zip_path: Path) -> List[Path]:
        """
        ZIP 파일 압축 해제
        
        Args:
            zip_path: ZIP 파일 경로
        
        Returns:
            압축 해제된 파일 목록
        """
        try:
            extract_dir = self.temp_dir / zip_path.stem
            extract_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"ZIP 압축 해제 시작: {zip_path}")
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # 압축 해제된 파일 목록
            extracted_files = []
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    file_path = Path(root) / file
                    extracted_files.append(file_path)
            
            logger.info(f"ZIP 압축 해제 완료: {len(extracted_files)}개 파일")
            return extracted_files
        
        except Exception as e:
            logger.error(f"ZIP 압축 해제 실패 ({zip_path}): {e}")
            return []
    
    def process_file(self, file_path: Path) -> List[Tuple[Path, str]]:
        """
        파일 처리 (형식에 따라 변환)
        
        Args:
            file_path: 처리할 파일 경로
        
        Returns:
            List[(처리된 파일 경로, 파일 형식), ...]
        """
        results = []
        ext = file_path.suffix.lower().lstrip('.')
        
        if ext in ['txt', 'pdf']:
            # TXT, PDF는 그대로 사용
            results.append((file_path, ext))
            logger.info(f"{ext.upper()} 파일 - 변환 없이 사용: {file_path.name}")
        
        elif ext == 'hwp':
            # HWP -> PDF 변환
            pdf_path = self.convert_hwp_to_pdf(file_path)
            if pdf_path:
                results.append((pdf_path, 'pdf'))
            else:
                logger.error(f"HWP 변환 실패, 원본 파일 사용: {file_path.name}")
                results.append((file_path, 'hwp'))
        
        elif ext == 'zip':
            # ZIP 압축 해제 후 각 파일 처리
            extracted_files = self.extract_zip(file_path)
            for extracted_file in extracted_files:
                # 재귀적으로 각 파일 처리
                sub_results = self.process_file(extracted_file)
                results.extend(sub_results)
        
        else:
            # 지원하지 않는 형식
            logger.warning(f"지원하지 않는 파일 형식: {ext} ({file_path.name})")
            results.append((file_path, ext))
        
        return results
    
    def cleanup_temp(self):
        """임시 파일 정리"""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                self.temp_dir.mkdir(parents=True, exist_ok=True)
                logger.info("임시 파일 정리 완료")
        except Exception as e:
            logger.error(f"임시 파일 정리 실패: {e}")

