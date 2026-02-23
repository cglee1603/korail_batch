"""
파일 다운로드 및 변환 처리 모듈
"""
import os
import shutil
import subprocess
import zipfile
import stat
import time
import threading
import html
from pathlib import Path
from typing import Any, Optional, List, Tuple
from urllib.parse import urlparse, unquote
import requests
from logger import logger
from config import DOWNLOAD_DIR, TEMP_DIR, TEXT_ENCODING, PDF_SPLIT_SIZE_MB, PDF_SPLIT_MAX_PAGES

# Excel 단순화용 (지연 import로 순환 참조 방지)
_ExcelProcessor = None

def _get_excel_processor():
    """ExcelProcessor 지연 로드 (순환 참조 방지)"""
    global _ExcelProcessor
    if _ExcelProcessor is None:
        from excel_processor import ExcelProcessor
        _ExcelProcessor = ExcelProcessor
    return _ExcelProcessor

# Windows 전용 모듈 (조건부 import)
try:
    import win32gui
    import win32api
    import win32con
    import win32file
except ImportError:
    win32gui = None
    win32api = None
    win32con = None
    win32file = None


class FileHandler:
    """파일 다운로드 및 변환 처리 클래스"""
    
    def __init__(self, revision_db=None, crypto_handler=None):
        self.download_dir = DOWNLOAD_DIR
        self.temp_dir = TEMP_DIR
        self.revision_db = revision_db  # 다운로드 캐시용
        self.crypto_handler = crypto_handler  # 암복호화 처리용
    
    def is_url(self, path: str) -> bool:
        """URL인지 파일 경로인지 판별"""
        try:
            result = urlparse(path)
            return result.scheme in ('http', 'https', 'ftp')
        except:
            return False
    
    def download_file(self, url: str, save_name: Optional[str] = None) -> Optional[Path]:
        """
        URL에서 파일 다운로드 (캐시 지원)
        
        Args:
            url: 다운로드할 파일 URL
            save_name: 저장할 파일명 (None이면 URL에서 추출)
        
        Returns:
            다운로드된 파일 경로 또는 None
        """
        try:
            # 다운로드 캐시 확인 (revision_db가 있는 경우)
            if self.revision_db:
                cached = self.revision_db.get_cached_download(url)
                if cached:
                    cached_path = Path(cached['file_path'])
                    # 파일이 실제로 존재하고 유효한지 확인
                    if cached_path.exists():
                        file_size = cached_path.stat().st_size
                        cached_size = cached.get('file_size', 0)
                        
                        # 파일 크기가 동일하면 캐시 사용
                        if file_size > 0 and (cached_size is None or file_size == cached_size):
                            logger.info(f"✓ 다운로드 캐시 사용 (스킵): {url}")
                            logger.debug(f"  캐시된 파일: {cached_path}")
                            return cached_path
                        else:
                            logger.warning(f"캐시된 파일 손상 ({file_size} bytes): 재다운로드")
                    else:
                        logger.warning(f"캐시된 파일 없음: 재다운로드")
            
            # 파일명 결정
            if not save_name:
                # URL에서 파일명 추출
                parsed = urlparse(url)
                save_name = unquote(Path(parsed.path).name)
                if not save_name:
                    save_name = f"download_{os.urandom(4).hex()}"
            
            # 파일명에서 앞뒤 불필요한 따옴표 제거 (작은따옴표, 큰따옴표)
            save_name = save_name.strip("'").strip('"')
            
            save_path = self.download_dir / save_name
            
            logger.info(f"파일 다운로드 시작: {url}")
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"파일 다운로드 완료: {save_path}")
            
            # 다운로드 후 파일 잠금 해제
            self.unlock_file(save_path)
            
            # 다운로드 캐시 저장 (revision_db가 있는 경우)
            if self.revision_db:
                file_size = save_path.stat().st_size
                success = self.revision_db.save_download_cache(
                    url=url,
                    file_path=str(save_path),
                    file_size=file_size
                )
                if success:
                    logger.debug(f"다운로드 캐시 저장 완료: {url}")
                else:
                    logger.warning(f"다운로드 캐시 저장 실패: {url}")
            
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
            
            # 복사 후 파일 잠금 해제
            self.unlock_file(dest_path)
            
            return dest_path
        
        except Exception as e:
            logger.error(f"파일 복사 실패 ({file_path}): {e}")
            return None
    
    def get_file(self, path: str) -> Optional[Path]:
        """
        URL 또는 로컬 파일 경로에서 파일 가져오기 (암복호화 포함)
        
        Args:
            path: URL 또는 로컬 파일 경로
        
        Returns:
            파일 경로 또는 None
        
        처리 흐름:
            1. 다운로드 또는 복사
            2. 암호화 체크
            3. 반환
        """
        # 1. 파일 다운로드/복사
        if self.is_url(path):
            file_path = self.download_file(path)
        else:
            file_path = self.copy_local_file(path)
        
        if not file_path:
            return None
        
        # 2. 암복호화 처리 (활성화된 경우)
        if self.crypto_handler:
            decrypted_file, was_encrypted = self.crypto_handler.process_file_with_decryption(file_path)
            
            if was_encrypted:
                logger.info(f"✓ 파일 복호화 완료: {file_path.name} → {decrypted_file.name}")
                return decrypted_file
            else:
                return file_path
        
        return file_path

    def unlock_file(self, file_path: Path):
        """파일 잠금 해제 (읽기 전용 속성 제거 등)"""
        try:
            # 파일 권한 변경 (쓰기 가능하게)
            os.chmod(file_path, stat.S_IWRITE | stat.S_IREAD)
        except Exception as e:
            logger.debug(f"파일 잠금 해제 실패 (무시됨): {e}")
    
    def convert_hwp_to_pdf(self, hwp_path: Path) -> Optional[Path]:
        """
        HWP 파일을 PDF로 변환 (암호화는 이미 해제된 상태)
        
        Windows: 한글 프로그램 COM 우선 시도 → 실패 시 LibreOffice
        Linux: LibreOffice 사용
        
        Note:
            - 암호화 체크/해제는 process_file() 또는 extract_zip()에서 이미 수행됨
            - 여기서는 변환만 수행
        """
        try:
            import platform
            
            # 원본 경로에 생성하면 중복 처리될 수 있으므로 임시 디렉토리 사용
            converted_dir = self.temp_dir / "converted_pdf"
            converted_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = converted_dir / hwp_path.with_suffix('.pdf').name
            
            logger.info(f"HWP->PDF 변환 시작: {hwp_path} -> {pdf_path}")
            

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
        hwp = None
        try:
            # pywin32 패키지 필요
            import win32com.client
            import pythoncom
            import time
            
            logger.info("한글 프로그램 COM 초기화 시작")
            
            # 파일 경로 검증
            if not hwp_path.exists():
                logger.error(f"HWP 파일이 존재하지 않습니다: {hwp_path}")
                return False
            
            # COM 초기화
            pythoncom.CoInitialize()
            
            try:
                # 한글 프로그램 COM 객체 생성 (DispatchEx로 새 인스턴스 생성)
                logger.info("HWP COM 객체 생성 중...")
                try:
                    hwp = win32com.client.DispatchEx("HWPFrame.HwpObject")
                    logger.info("DispatchEx로 COM 객체 생성 완료")
                except Exception as e:
                    logger.warning(f"DispatchEx 실패, Dispatch 시도: {e}")
                    hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
                    logger.info("Dispatch로 COM 객체 생성 완료")
                
                # HWP 객체 정보 로깅
                logger.info(f"HWP 객체 타입: {type(hwp)}")
                logger.info(f"HWP 객체 속성: {dir(hwp)[:10]}...")  # 처음 10개만
                
                # 한글 프로그램 창 숨기기 시도
                try:
                    # HWP 버전에 따라 다른 속성 사용
                    if hasattr(hwp, 'XVisible'):
                        hwp.XVisible = False
                        logger.info("한글 프로그램 창 숨김 설정 (XVisible)")
                    elif hasattr(hwp, 'Visible'):
                        hwp.Visible = False
                        logger.info("한글 프로그램 창 숨김 설정 (Visible)")
                    else:
                        logger.warning("창 숨김 속성을 찾을 수 없습니다")
                        # 사용 가능한 속성 확인
                        visible_attrs = [attr for attr in dir(hwp) if 'visible' in attr.lower()]
                        logger.info(f"Visible 관련 속성: {visible_attrs}")
                except Exception as e:
                    logger.warning(f"창 숨김 설정 실패: {e}")
                
                # 메시지 박스 억제 (경고 대화상자 방지) - 가장 중요!
                try:
                    # 0x00000010: 메시지박스 표시 안함
                    # 0x00000020: 모든 대화상자를 기본값으로 자동 처리
                    if hasattr(hwp, 'SetMessageBoxMode'):
                        hwp.SetMessageBoxMode(0x00000030)
                        logger.info("메시지 박스 억제 설정 완료 (0x00000030)")
                    else:
                        logger.warning("SetMessageBoxMode 메서드를 찾을 수 없습니다")
                except Exception as e:
                    logger.warning(f"메시지 박스 억제 설정 실패: {e}")
                
                stop_clicking = [False]
                processed_dialogs = set()  # 처리한 대화상자 추적
                
                def auto_click_dialog():
                    """보안 대화상자 및 오류 대화상자를 자동으로 클릭"""
                    last_click_time = 0  # 마지막 클릭 시간 추적
                    
                    while not stop_clicking[0]:
                        try:
                            time.sleep(0.3)
                            current_time = time.time()
                            
                            # 마지막 클릭 후 2초 이내면 스킵 (대화상자 닫힐 시간 확보)
                            if current_time - last_click_time < 2.0:
                                continue
                            
                            windows = []
                            win32gui.EnumWindows(lambda hwnd, result: result.append(hwnd) if win32gui.IsWindowVisible(hwnd) else None, windows)
                            
                            for hwnd in windows:
                                texts = []

                                def enum_child(child_hwnd, result):
                                    text = win32gui.GetWindowText(child_hwnd)
                                    if text:
                                        result.append(text)
                                try:
                                    win32gui.EnumChildWindows(hwnd, enum_child, texts)
                                except Exception as e:
                                    logger.warning(f"자식 창 열거 실패: {e}")
                                    
                                all_texts = ' '.join(texts)
                                
                                # 보안 경고 대화상자 키워드
                                security_keywords = [
                                    "접근하려는 시도(파일의 손상 또는 유출의 위험 등)가 있습니다."
                                ]
                                
                                # 종료 시 오류 대화상자 키워드
                                error_keywords = [
                                    "오류",
                                    "에러",
                                    "Error",
                                    "문제가 발생",
                                    "저장하시겠습니까",
                                    "변경 내용",
                                    "저장",
                                    "종료"
                                ]
                                
                                # 보안 경고 대화상자 처리 (N 키)
                                if any(keyword in all_texts for keyword in security_keywords):
                                    title = win32gui.GetWindowText(hwnd)
                                    logger.info(f"보안 대화상자 발견 (hwnd: {hwnd}): {title}")
                                    
                                    # 창이 포커스되도록 대기
                                    time.sleep(0.2)
                                    
                                    # N키 입력
                                    win32api.keybd_event(ord('N'), 0, 0, 0)
                                    win32api.keybd_event(ord('N'), 0, win32con.KEYEVENTF_KEYUP, 0)
                                    
                                    last_click_time = time.time()
                                    logger.info(f"N 키 클릭 완료 (hwnd: {hwnd})")
                                    
                                    # 대화상자가 닫힐 시간 확보
                                    time.sleep(1.0)
                                    break  # 한 번에 하나씩만 처리
                                
                                # 오류/종료 대화상자 처리 (Y 키)
                                elif any(keyword in all_texts for keyword in error_keywords):
                                    title = win32gui.GetWindowText(hwnd)
                                    logger.info(f"오류/종료 대화상자 발견 (hwnd: {hwnd}): {title}")
                                    logger.info(f"대화상자 내용: {all_texts[:100]}...")  # 처음 100자만 로깅
                                    
                                    # 창이 포커스되도록 대기
                                    time.sleep(0.2)
                                    
                                    # Y키 입력
                                    win32api.keybd_event(ord('Y'), 0, 0, 0)
                                    win32api.keybd_event(ord('Y'), 0, win32con.KEYEVENTF_KEYUP, 0)
                                    
                                    last_click_time = time.time()
                                    logger.info(f"Y 키 클릭 완료 (hwnd: {hwnd})")
                                    
                                    # 대화상자가 닫힐 시간 확보
                                    time.sleep(1.0)
                                    break  # 한 번에 하나씩만 처리
                                    
                        except Exception as e:
                            logger.warning(f"대화상자 자동 클릭 실패: {e}")
                            # 에러가 발생해도 계속 시도
                            time.sleep(1.0)
                
                click_thread = threading.Thread(target=auto_click_dialog, daemon=True)
                click_thread.start()
                # 보안 경고 무시 설정 시도
                try:
                    if hasattr(hwp, 'RegisterModule'):
                        hwp.RegisterModule("FilePathCheckDLL", "SecurityModule")
                        logger.info("보안 모듈 등록 완료")
                    else:
                        logger.warning("RegisterModule 메서드를 찾을 수 없습니다")
                except Exception as e:
                    logger.warning(f"보안 모듈 등록 실패: {e}")
                
                # HWP 파일 열기 (Windows 경로 형식 사용)
                abs_hwp_path = str(hwp_path.resolve()).replace('/', '\\')
                logger.info(f"HWP 파일 열기 시도: {abs_hwp_path}")
                logger.info(f"파일 존재 확인: {hwp_path.exists()}")
                logger.info(f"파일 크기: {hwp_path.stat().st_size} bytes")
                logger.info(f"파일 확장자: {hwp_path.suffix}")
                
                # 파일 열기 옵션 설정 (더 단순하게)
                # Open(Path, Format, Arg)
                # Format: "" (빈 문자열로 자동 감지), "HWP", "HWPX" 등
                # Arg: "" (빈 문자열로 기본값)
                logger.info("hwp.Open() 호출 시작 (옵션: 빈 문자열)...")
                
                # 파일 열기 - 가장 단순한 형태로 시도
                try:
                    result = hwp.Open(abs_hwp_path, "", "")
                    logger.info(f"hwp.Open() 반환 완료: {result}")
                except Exception as e:
                    logger.error(f"hwp.Open() 예외 발생 (빈 옵션): {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    
                    # 실패 시 "HWP" 포맷으로 재시도
                    logger.info("hwp.Open() 재시도 (포맷: HWP)...")
                    try:
                        result = hwp.Open(abs_hwp_path, "HWP", "")
                        logger.info(f"hwp.Open() 재시도 성공: {result}")
                    except Exception as e2:
                        logger.error(f"hwp.Open() 재시도 실패: {e2}")
                        try:
                            hwp.Quit()
                        except:
                            pass
                        return False
                
                if not result:
                    logger.error("HWP 파일 열기 실패 - Open() 반환값이 False")
                    try:
                        hwp.Quit()
                        
                    except:
                        pass
                    return False
                
                logger.info("HWP 파일 열기 성공")
                stop_clicking[0]=True
                
                # 잠시 대기 (파일 로딩 완료 대기)
                time.sleep(0.5)
                
                # PDF로 저장
                abs_pdf_path = str(pdf_path.resolve())
                logger.info(f"PDF로 저장 시도: {abs_pdf_path}")
                
                # SaveAs 메서드: path, format, arg
                # PDF 포맷 코드: "PDF"
                save_result = hwp.SaveAs(abs_pdf_path, "PDF", "")
                logger.info(f"SaveAs() 결과: {save_result}")
                
                # 한글 프로그램 종료
                logger.info("한글 프로그램 종료 중...")
                hwp.Quit()
                hwp = None
                
                # 파일 저장 대기
                time.sleep(0.5)
                
                # PDF 파일 생성 확인
                if pdf_path.exists():
                    logger.info(f"한글 프로그램으로 PDF 변환 성공: {pdf_path}")
                    return True
                else:
                    logger.error(f"PDF 파일이 생성되지 않았습니다: {pdf_path}")
                    return False
            
            finally:
                # COM 정리
                if hwp is not None:
                    try:
                        logger.info("한글 프로그램 강제 종료 시도...")
                        hwp.Quit()
                    except Exception as e:
                        logger.warning(f"한글 프로그램 종료 실패: {e}")
                
                try:
                    pythoncom.CoUninitialize()
                except Exception as e:
                    logger.warning(f"COM 정리 실패: {e}")
        
        except ImportError:
            logger.warning("pywin32 패키지가 설치되지 않았습니다.")
            logger.warning("설치 방법: pip install pywin32")
            return False
        
        except Exception as e:
            logger.error(f"한글 프로그램 COM 변환 중 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # 비정상 종료 시 한글 프로세스 정리
            if hwp is not None:
                try:
                    hwp.Quit()
                except:
                    pass
            
            return False
    
    def _convert_with_libreoffice(self, hwp_path: Path, pdf_path: Path) -> bool:
        """
        Python API를 사용한 HWP → PDF 변환 (Linux 전용)
        
        Args:
            hwp_path: 원본 HWP 파일 경로
            pdf_path: 출력 PDF 파일 경로
        
        Returns:
            변환 성공 여부
        """
        try:
            import platform
            from config import HWP_CONVERTER_PYTHON, HWP_CONVERTER_SCRIPT
            
            # Linux에서만 실행
            if platform.system() != 'Linux':
                logger.error("HWP 변환은 Linux에서만 지원됩니다.")
                logger.error(f"현재 운영체제: {platform.system()}")
                return False
            
            # Python 변환 스크립트 경로 (절대 경로로 변환)
            conversion_script = Path(HWP_CONVERTER_SCRIPT).resolve()
            
            # 변환 스크립트가 존재하는지 확인
            if not conversion_script.exists():
                logger.error(f"변환 스크립트를 찾을 수 없습니다: {conversion_script}")
                logger.error("libre-converter가 설치되어 있는지 확인하세요.")
                return False
            
            # 출력 디렉토리 생성 (절대 경로로 변환)
            pdf_absolute = pdf_path.resolve()
            output_dir = pdf_absolute.parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # hwp_path를 먼저 절대 경로로 변환 (chdir 전에!)
            hwp_absolute = hwp_path.resolve()
            
            # 변환 스크립트의 디렉토리로 이동하여 실행
            # (변환된 PDF가 호출 경로에 생성되므로)
            original_cwd = Path.cwd()
            
            try:
                # 출력 디렉토리로 이동
                os.chdir(output_dir)
                
                # Python 변환 명령 실행 (환경변수에서 Python 경로 가져오기)
                cmd = [
                    HWP_CONVERTER_PYTHON,
                    str(conversion_script),
                    str(hwp_absolute)
                ]
                
                logger.info(f"HWP 변환 Python API 호출: {' '.join(cmd)}")
                logger.info(f"Python 인터프리터: {HWP_CONVERTER_PYTHON}")
                logger.info(f"작업 디렉토리: {output_dir}")
                logger.debug(f"실제 전달되는 cmd 리스트: {cmd}")
                logger.debug(f"HWP 파일 경로: {hwp_absolute}")
                logger.debug(f"HWP 파일 존재 확인: {hwp_absolute.exists()}")
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5분 타임아웃
                )
                
                # 출력 로그 확인
                if result.stdout:
                    logger.info(f"변환 출력: {result.stdout.strip()}")
                if result.stderr:
                    logger.warning(f"변환 경고: {result.stderr.strip()}")
                
                if result.returncode == 0:
                    # 변환된 PDF 파일명 확인
                    # test_conversion.py는 스크립트 실행 위치(cwd)에 생성하거나 
                    # 원본과 같은 위치에 생성할 수 있음 (스크립트 구현에 따라 다름)
                    
                    # 1. 예상 경로 (output_dir 내)
                    expected_pdf = output_dir / f"{hwp_path.stem}.pdf"
                    
                    
                    found_pdf = None
                    # 2. 원본 HWP 파일과 같은 위치에 생성되었을 경우
                    # (hwp_absolute가 가리키는 원본 경로 기준)
                    original_location_pdf = hwp_absolute.with_suffix('.pdf')

                    if expected_pdf.exists() and expected_pdf.stat().st_size > 0:
                        found_pdf = expected_pdf
                    elif original_location_pdf.exists() and original_location_pdf.stat().st_size > 0:
                        found_pdf = original_location_pdf
                    
                    # PDF 파일이 생성되었는지 확인
                    if found_pdf:
                        # 원하는 경로로 이동 (다른 경우에만)
                        # found_pdf와 pdf_absolute가 다른 경로일 때 이동
                        if found_pdf.resolve() != pdf_absolute:
                            import shutil
                            # 이미 목적지에 파일이 있으면 삭제
                            if pdf_absolute.exists():
                                pdf_absolute.unlink()
                            
                            shutil.move(str(found_pdf), str(pdf_absolute))
                            logger.info(f"PDF 이동: {found_pdf} → {pdf_absolute}")
                        
                        logger.info(f"✓ HWP → PDF 변환 성공: {pdf_absolute}")
                        return True
                    else:
                        logger.error(f"✗ PDF 파일이 생성되지 않았거나 크기가 0입니다")
                        logger.error(f"   예상 경로: {expected_pdf}")
                        return False
                else:
                    logger.error(f"✗ HWP 변환 실패 (exit code: {result.returncode})")
                    return False
            
            finally:
                # 원래 디렉토리로 복귀
                os.chdir(original_cwd)
        
        except subprocess.TimeoutExpired:
            logger.error(f"HWP 변환 타임아웃 (5분 초과): {hwp_path}")
            # 원래 디렉토리로 복귀
            try:
                os.chdir(original_cwd)
            except:
                pass
            return False
        except Exception as e:
            logger.error(f"HWP 변환 중 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # 원래 디렉토리로 복귀
            try:
                os.chdir(original_cwd)
            except:
                pass
            return False
    
    def extract_zip(self, zip_path: Path) -> List[Path]:
        """
        ZIP 파일 압축 해제 (한글 파일명 지원 + 암호화 파일 자동 해제)
        
        Args:
            zip_path: ZIP 파일 경로
        
        Returns:
            압축 해제된 파일 목록 (암호화 해제 완료)
        """
        try:
            import sys
            
            extract_dir = self.temp_dir / zip_path.stem
            extract_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"ZIP 압축 해제 시작: {zip_path}")
            # Python 버전 확인
            python_version = sys.version_info
            
            # Python 3.11 이상: metadata_encoding 파라미터 사용
            if python_version >= (3, 11):
                try:
                    # CP949 인코딩 시도 (Windows ZIP)
                    with zipfile.ZipFile(zip_path, 'r', metadata_encoding='cp949') as zip_ref:
                        zip_ref.extractall(extract_dir)
                    logger.info("ZIP 파일 압축 해제 완료 (CP949 인코딩)")
                except Exception as e:
                    logger.warning(f"CP949 인코딩 실패, UTF-8로 재시도: {e}")
                    # UTF-8 인코딩 시도
                    with zipfile.ZipFile(zip_path, 'r', metadata_encoding='utf-8') as zip_ref:
                        zip_ref.extractall(extract_dir)
                    logger.info("ZIP 파일 압축 해제 완료 (UTF-8 인코딩)")
            
            # Python 3.10 이하: 수동 인코딩 처리
            else:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    for member in zip_ref.namelist():
                        try:
                            # CP949로 인코딩된 파일명을 UTF-8로 변환
                            member_bytes = member.encode('cp437')  # ZIP의 기본 인코딩
                            member_name = member_bytes.decode('cp949')  # Windows 한글 인코딩
                        except (UnicodeDecodeError, UnicodeEncodeError):
                            # 변환 실패 시 원본 이름 사용
                            member_name = member
                        
                        # 파일 추출
                        source = zip_ref.open(member)
                        target_path = extract_dir / member_name
                        
                        # 디렉토리 생성
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # 파일 쓰기
                        with open(target_path, 'wb') as target:
                            shutil.copyfileobj(source, target)
                
                logger.info("ZIP 파일 압축 해제 완료 (수동 인코딩 변환)")
            
            # 압축 해제된 파일 목록 및 암호화 처리
            extracted_files = []
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    file_path = Path(root) / file
                    
                    # 1. 압축 해제된 파일의 잠금 해제
                    self.unlock_file(file_path)
                    
                    # 2. 암호화 체크 및 복호화 (crypto_handler 사용)
                    if self.crypto_handler and self.crypto_handler.enabled:
                        try:
                            decrypted_file, was_encrypted = self.crypto_handler.process_file_with_decryption(file_path)
                            if was_encrypted and decrypted_file:
                                logger.info(f"  ✓ ZIP 내부 파일 복호화: {file_path.name} → {decrypted_file.name}")
                                # 복호화된 파일을 리스트에 추가
                                extracted_files.append(decrypted_file)
                            else:
                                # 암호화되지 않은 파일
                                extracted_files.append(file_path)
                        except Exception as e:
                            logger.warning(f"  ⚠ ZIP 내부 파일 암호화 체크 실패 (원본 사용): {file_path.name} - {e}")
                            extracted_files.append(file_path)
                    else:
                        # crypto_handler가 없으면 원본 파일 사용
                        extracted_files.append(file_path)
            
            logger.info(f"ZIP 압축 해제 완료: {len(extracted_files)}개 파일 (암호화 체크 완료)")
            return extracted_files
        
        except Exception as e:
            logger.error(f"ZIP 압축 해제 실패 ({zip_path}): {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    def _split_pdf_if_large(self, pdf_path: Path, max_size_mb: int = None, max_pages: int = None) -> List[Path]:
        """
        PDF 파일이 지정된 크기 또는 페이지 수보다 크면 분할

        Args:
            pdf_path: PDF 파일 경로
            max_size_mb: 최대 허용 크기 (MB), None이면 설정값 사용
            max_pages: 최대 허용 페이지 수, None이면 설정값 사용

        Returns:
            분할된 파일 경로 리스트 (분할 안 된 경우 원본 1개 포함)
        """
        if max_size_mb is None:
            max_size_mb = PDF_SPLIT_SIZE_MB

        # 둘 다 비활성화된 경우 분할하지 않음
        if max_size_mb <= 0 and max_pages <= 0:
            return [pdf_path]
            
        try:
            try:
                import PyPDF2
                import io
            except ImportError:
                logger.warning("PyPDF2가 설치되지 않아 PDF 분할을 건너뜁니다. (pip install PyPDF2)")
                return [pdf_path]

            # PDF 리더로 페이지 수 확인
            with open(pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                total_pages = len(reader.pages)

            # 파일 크기 확인 (MB)
            file_size_mb = pdf_path.stat().st_size / (1024 * 1024)

            # 분할 필요 여부 확인
            needs_split_by_size = max_size_mb > 0 and file_size_mb > max_size_mb
            needs_split_by_pages = max_pages > 0 and total_pages > max_pages

            if not needs_split_by_size and not needs_split_by_pages:
                logger.debug(f"PDF 분할 불필요 (크기/페이지 조건 미달): {pdf_path.name}")
                return [pdf_path]

            # 분할 이유 로깅
            split_reason = []
            if needs_split_by_size:
                split_reason.append(f"용량 초과 ({file_size_mb:.2f}MB > {max_size_mb}MB)")
            if needs_split_by_pages:
                split_reason.append(f"페이지 수 초과 ({total_pages} > {max_pages})")

            logger.info(f"PDF 파일 분할 시작 - {pdf_path.name}: {', '.join(split_reason)}")

            split_files = []

            # 분할 폴더 생성 (무한 루프 방지를 위해 임시 디렉토리 사용)
            # 원본 경로 하위에 생성하면 파일 감시가 다시 동작하여 중복 처리될 수 있음
            split_dir = self.temp_dir / "split_output" / pdf_path.stem
            if split_dir.exists():
                shutil.rmtree(split_dir)
            split_dir.mkdir(parents=True, exist_ok=True)

            # 목표 크기 (bytes) - 90% 수준에서 분할하여 초과 방지
            target_size = int(max_size_mb * 1024 * 1024 * 0.9) if max_size_mb > 0 else 0

            with open(pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)

                if total_pages == 0:
                    logger.warning("PDF 페이지가 0입니다.")
                    return [pdf_path]

                logger.info(f"총 {total_pages}페이지 분할 처리 시작")

                # 분할 단위 결정 (페이지 수 또는 크기 중 우선순위가 높은 것 사용)
                if needs_split_by_pages:
                    # 페이지 수 기준 분할
                    pages_per_split = max_pages
                    logger.info(f"페이지 수 기준 분할: 각 파일당 최대 {pages_per_split}페이지")
                else:
                    # 크기 기준 분할 (기존 로직)
                    pages_per_split = float('inf')  # 크기 기준으로 동적 분할
                    logger.info(f"크기 기준 분할: 각 파일당 최대 {max_size_mb}MB")

                current_writer = PyPDF2.PdfWriter()
                current_pages = 0
                part_num = 1
                pages_since_last_check = 0
                
                for i, page in enumerate(reader.pages):
                    current_writer.add_page(page)
                    current_pages += 1
                    pages_since_last_check += 1
                    
                    # 체크 주기: 초기 5페이지는 매번, 이후에는 10페이지마다
                    should_check = (current_pages < 5) or (pages_since_last_check >= 10)
                    
                    if should_check:
                        # 현재 크기 측정 (메모리상)
                        temp_buffer = io.BytesIO()
                        current_writer.write(temp_buffer)
                        current_size = temp_buffer.tell()
                        
                        if current_size >= target_size:
                            # 목표 크기 도달 -> 파일 저장
                            split_name = f"{pdf_path.stem}_part{part_num}{pdf_path.suffix}"
                            split_path = split_dir / split_name
                            
                            with open(split_path, 'wb') as out_f:
                                current_writer.write(out_f)
                            
                            split_files.append(split_path)
                            logger.info(f"  분할 파일 생성: {split_name} ({current_pages}페이지, {current_size/1024/1024:.2f}MB)")
                            
                            # 초기화 및 다음 파트 준비
                            current_writer = PyPDF2.PdfWriter()
                            part_num += 1
                            current_pages = 0
                            pages_since_last_check = 0
                
                # 남은 페이지 저장
                if current_pages > 0:
                    split_name = f"{pdf_path.stem}_part{part_num}{pdf_path.suffix}"
                    split_path = split_dir / split_name
                    
                    with open(split_path, 'wb') as out_f:
                        current_writer.write(out_f)
                    
                    split_files.append(split_path)
                    logger.info(f"  마지막 분할 파일 생성: {split_name} ({current_pages}페이지)")
            
            logger.info(f"PDF 분할 완료: 총 {len(split_files)}개 파일 생성됨")
            return split_files
            
        except Exception as e:
            logger.error(f"PDF 분할 중 오류 발생: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return [pdf_path]

    def process_file(self, file_path: Path, skip_decryption: bool = False) -> List[Tuple[Path, str]]:
        """
        파일 처리 (암호화 해제 + 형식 변환 + PDF 분할)
        
        Args:
            file_path: 처리할 파일 경로
            skip_decryption: 암호화 해제 건너뛰기 (extract_zip에서 이미 처리된 경우)
        
        Returns:
            List[(처리된 파일 경로, 파일 형식), ...]
        """
        # 파일명에 불필요한 따옴표가 있으면 제거하고 파일명 변경
        if file_path.name.startswith(("'", '"')) or file_path.name.endswith(("'", '"')):
            normalized_name = file_path.name.strip('\'"')
            normalized_path = file_path.parent / normalized_name
            if file_path.exists() and not normalized_path.exists():
                try:
                    file_path.rename(normalized_path)
                    logger.info(f"파일명 정규화: {file_path.name} → {normalized_name}")
                    file_path = normalized_path
                except Exception as e:
                    logger.warning(f"파일명 정규화 실패: {e}")
        
        # 파일 처리 전 잠금 해제

        
        # 암호화 체크 및 복호화 (extract_zip에서 이미 처리하지 않은 경우만)
        if not skip_decryption:
            try:
                if self.crypto_handler and self.crypto_handler.enabled:
                    decrypted_file, was_encrypted = self.crypto_handler.process_file_with_decryption(file_path)
                    if was_encrypted and decrypted_file:
                        logger.info(f"✓ 파일 복호화 완료: {file_path.name} → {decrypted_file.name}")
                        file_path = decrypted_file
            except Exception as e:
                logger.warning(f"복호화 처리 중 경고 (원본 파일로 계속 진행): {e}")
        
        results = []
        ext = file_path.suffix.lower().lstrip('.')
        
        if ext in ['txt', 'pdf']:
            if ext == 'pdf':
                # PDF 파일 크기 체크 및 분할
                split_pdf_paths = self._split_pdf_if_large(file_path)
                for p in split_pdf_paths:
                    results.append((p, 'pdf'))
                    if p != file_path: # 분할된 경우 로그
                        logger.info(f"PDF 분할 파일 추가: {p.name}")
            else:
                # TXT는 그대로 사용
                results.append((file_path, ext))
                logger.info(f"{ext.upper()} 파일 - 변환 없이 사용: {file_path.name}")
        
        elif ext in ['xlsx', 'xls', 'xlsm']:
            # Excel 파일 - 모든 시트를 단순화된 Excel로 변환 (RAGFlow Table 파서 호환)
            simplified_path = self._simplify_excel_for_table_parser(file_path)
            if simplified_path:
                results.append((simplified_path, 'xlsx'))
                logger.info(f"Excel 파일 - 단순화 완료 (Table 파서용): {file_path.name} → {simplified_path.name}")
            else:
                # 단순화 실패 시 원본 사용
                results.append((file_path, ext))
                logger.warning(f"Excel 단순화 실패, 원본 사용: {file_path.name}")
        
        elif ext in ['hwp', 'hwpx', 'doc', 'docx', 'docm', 'odt', 'rtf', 'wps', 
                     'ods', 'csv', 
                     'ppt', 'pptx', 'pptm', 'odp', 
                     'odg', 'vsd', 'vsdx']:
            # Office -> PDF 변환 (암호화는 이미 해제됨)
            pdf_path = self.convert_hwp_to_pdf(file_path)
            if pdf_path:
                # 변환된 PDF도 크기 체크 및 분할
                split_pdf_paths = self._split_pdf_if_large(pdf_path)
                for p in split_pdf_paths:
                    results.append((p, 'pdf'))
            else:
                logger.error(f"Office 변환 실패, 원본 파일 사용: {file_path.name}")
                results.append((file_path, ext))
        
        elif ext == 'zip':
            # ZIP 압축 해제 (extract_zip에서 암호화 해제도 수행)
            extracted_files = self.extract_zip(file_path)
            for extracted_file in extracted_files:
                # 재귀 호출 시 skip_decryption=True (extract_zip에서 이미 처리됨)
                sub_results = self.process_file(extracted_file, skip_decryption=True)
                results.extend(sub_results)
        
        else:
            # 지원하지 않는 형식
            logger.warning(f"지원하지 않는 파일 형식: {ext} ({file_path.name})")
            results.append((file_path, ext))
        
        return results
    
    def _simplify_excel_for_table_parser(self, file_path: Path) -> Optional[Path]:
        """
        Excel 파일을 RAGFlow Table 파서에 맞게 단순화
        
        ExcelProcessor.extract_all_sheets_as_simplified_excel() 호출
        
        Args:
            file_path: 원본 Excel 파일 경로
            
        Returns:
            단순화된 Excel 파일 경로 (실패 시 None)
        """
        try:
            ExcelProcessor = _get_excel_processor()
            processor = ExcelProcessor(str(file_path))
            
            if not processor.load_workbook():
                logger.error(f"Excel 워크북 로드 실패: {file_path.name}")
                return None
            
            result = processor.extract_sheet_as_simplified_excel(self.temp_dir)
            processor.close()
            
            return result
            
        except Exception as e:
            logger.error(f"Excel 단순화 중 오류: {file_path.name} - {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def create_text_file(self, content: str, filename: str) -> Optional[Path]:
        """
        텍스트 파일 생성 (이력관리/소프트웨어 형상기록용)
        
        Args:
            content: 텍스트 내용
            filename: 파일명 (확장자 .txt 자동 추가)
        
        Returns:
            생성된 파일 경로 또는 None
        """
        try:
            # 파일명에 .txt 확장자가 없으면 추가
            if not filename.endswith('.txt'):
                filename = f"{filename}.txt"
            
            # TEMP_DIR에 파일 생성
            file_path = self.temp_dir / filename
            
            # 텍스트 파일 쓰기
            with open(file_path, 'w', encoding=TEXT_ENCODING) as f:
                f.write(content)
            
            logger.info(f"텍스트 파일 생성 완료: {file_path} ({len(content)}자)")
            return file_path
        
        except Exception as e:
            logger.error(f"텍스트 파일 생성 실패 ({filename}): {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def convert_text_to_pdf(self, content: Any, filename: str) -> Optional[Path]:
        """
        텍스트를 PDF로 변환 (이력관리/소프트웨어 형상기록용)
        
        Args:
            content: 텍스트 내용 (str 또는 List[str])
                     List[str]인 경우 각 요소를 하나의 Row로 취급하여 페이지 넘김 제어
            filename: 파일명 (확장자 .pdf 자동 추가)
        
        Returns:
            생성된 PDF 파일 경로 또는 None
        """
        try:
            # reportlab 사용
            try:
                from reportlab.lib.pagesizes import A4
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import cm
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
                from reportlab.pdfbase.cidfonts import UnicodeCIDFont
                from reportlab.lib.enums import TA_LEFT
            except ImportError:
                logger.error("reportlab 패키지가 설치되지 않았습니다.")
                logger.error("설치 방법: pip install reportlab")
                return None
            
            # 파일명에 .pdf 확장자가 없으면 추가
            if not filename.endswith('.pdf'):
                filename = f"{filename}.pdf"
            
            # TEMP_DIR에 파일 생성
            file_path = self.temp_dir / filename
            
            logger.info(f"텍스트를 PDF로 변환 중 (타입: {type(content)})")
            
            # PDF 문서 생성
            doc = SimpleDocTemplate(
                str(file_path),
                pagesize=A4,
                leftMargin=2*cm,
                rightMargin=2*cm,
                topMargin=2*cm,
                bottomMargin=2*cm
            )
            
            # 스타일 설정
            styles = getSampleStyleSheet()
            # 기본 폰트명 초기화
            font_name = 'Helvetica'
            
            try:
                # 프로젝트 루트 추정: src/ 파일 기준 두 단계 상위
                project_root = Path(__file__).resolve().parent.parent
                fonts_dir = project_root / 'fonts'
                embedded = False
                if fonts_dir.exists() and fonts_dir.is_dir():
                    # 우선순위 높은 후보명 먼저 시도 후, 나머지 .ttf/.otf 전체 스캔
                    priority_names = [
                        'H2GTRE.TTF',
                    ]
                    candidates = []
                    for name in priority_names:
                        p = fonts_dir / name
                        if p.exists():
                            candidates.append(p)
                    # 기타 ttf/otf 파일도 추가
                    for p in sorted(fonts_dir.iterdir()):
                        if p.is_file() and p.suffix.lower() in {'.ttf', '.otf'} and p not in candidates:
                            candidates.append(p)
                    # 등록 시도
                    for ttf_path in candidates:
                        try:
                            pdfmetrics.registerFont(TTFont('EmbeddedKR', str(ttf_path)))
                            font_name = 'EmbeddedKR'
                            embedded = True
                            logger.info(f"임베디드 한글 폰트 사용: {ttf_path}")
                            break
                        except Exception as ttf_err:
                            logger.debug(f"임베디드 폰트 등록 실패({ttf_path}): {ttf_err}")
                else:
                    logger.debug(f"프로젝트 폰트 폴더 미존재: {fonts_dir}")
            except Exception as any_err:
                logger.debug(f"임베디드 폰트 처리 중 오류: {any_err}")
                
            
            # 커스텀 스타일 생성
            custom_style = ParagraphStyle(
                'CustomStyle',
                parent=styles['Normal'],
                fontName=font_name,
                fontSize=10,
                leading=14,
                alignment=TA_LEFT,
                spaceAfter=6
            )
            
            # 내용을 단락으로 분할
            story = []
            
            if isinstance(content, list):
                # Row 리스트로 전달된 경우 (강력한 페이지 넘김 제어)
                for row_text in content:
                    if not row_text.strip():
                        continue
                        
                    # Row 내 줄바꿈은 <br/>로 변환하여 하나의 Paragraph로 유지
                    # html.escape를 먼저 하고 <br/>로 치환해야 함
                    escaped_text = html.escape(row_text).replace('\n', '<br/>')
                    
                    para = Paragraph(escaped_text, custom_style)
                    # Row 단위로 페이지 넘김 제어
                    story.append(KeepTogether([para]))
                    
                    # Row 간 간격
                    story.append(Spacer(1, 0.2*cm))
            else:
                # 기존 문자열 처리 로직 (하위 호환)
                lines = content.split('\n')
                
                for line in lines:
                    if line.strip():
                        # 특수 문자 이스케이프 (html.escape 사용으로 안전성 확보)
                        escaped_line = html.escape(line)
                        para = Paragraph(escaped_line, custom_style)
                        # KeepTogether를 사용하여 문단이 페이지 경계에서 잘리지 않고 
                        # 통째로 다음 페이지로 넘어가도록 설정
                        story.append(KeepTogether([para]))
                    else:
                        # 빈 줄은 간격으로
                        story.append(Spacer(1, 0.2*cm))
            
            # PDF 생성
            doc.build(story)
            
            logger.info(f"PDF 변환 완료: {file_path}")
            return file_path
        
        except Exception as e:
            logger.error(f"텍스트 → PDF 변환 실패 ({filename}): {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def cleanup_processed_files(self, processed_files: List[Tuple[Path, str]]):
        """
        처리된 파일 목록 중 임시 파일(TEMP_DIR 내)을 삭제
        
        Args:
            processed_files: (파일경로, 타입) 튜플 리스트
        """
        if not processed_files:
            return

        try:
            temp_root = self.temp_dir.resolve()
            
            for file_path, _ in processed_files:
                if not isinstance(file_path, Path):
                    file_path = Path(file_path)
                
                # 파일이 존재하지 않으면 스킵
                if not file_path.exists():
                    continue

                # 임시 디렉토리 내에 있는 파일인지 확인 (resolve()로 절대 경로 비교)
                try:
                    # is_relative_to는 Python 3.9+ 부터 지원하므로 parents 확인으로 대체 가능하나
                    # 안전하게 parents 체크 방식 사용
                    abs_path = file_path.resolve()
                    if temp_root in abs_path.parents:
                        # 임시 파일 삭제
                        file_path.unlink()
                        logger.debug(f"임시 파일 삭제 완료: {file_path.name}")
                        
                except Exception as e:
                    logger.warning(f"파일 정리 중 오류 무시 ({file_path.name}): {e}")
                    
        except Exception as e:
            logger.warning(f"임시 파일 정리 실패: {e}")

    def cleanup_temp(self):
        """임시 파일 정리"""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                self.temp_dir.mkdir(parents=True, exist_ok=True)
                logger.info("임시 파일 정리 완료")
        except Exception as e:
            logger.error(f"임시 파일 정리 실패: {e}")
