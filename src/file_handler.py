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
from config import DOWNLOAD_DIR, TEMP_DIR, TEXT_ENCODING


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
        ZIP 파일 압축 해제 (한글 파일명 지원)
        
        Args:
            zip_path: ZIP 파일 경로
        
        Returns:
            압축 해제된 파일 목록
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
            import traceback
            logger.debug(traceback.format_exc())
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
    
    def convert_text_to_pdf(self, content: str, filename: str) -> Optional[Path]:
        """
        텍스트를 PDF로 변환 (이력관리/소프트웨어 형상기록용)
        
        Args:
            content: 텍스트 내용
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
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
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
            
            logger.info(f"텍스트를 PDF로 변환 중: {len(content)}자")
            
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
            
            # 한글 폰트 등록 시도 (Windows)
            try:
                import platform
                if platform.system() == 'Windows':
                    # Windows 기본 한글 폰트 (맑은 고딕)
                    font_path = 'C:\\Windows\\Fonts\\malgun.ttf'
                    if Path(font_path).exists():
                        pdfmetrics.registerFont(TTFont('Malgun', font_path))
                        font_name = 'Malgun'
                        logger.debug("한글 폰트 등록 성공: 맑은 고딕")
                    else:
                        font_name = 'Helvetica'
                        logger.warning("한글 폰트를 찾을 수 없습니다. 기본 폰트 사용")
                else:
                    # Linux - 나눔폰트 시도
                    nanum_paths = [
                        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
                        '/usr/share/fonts/nanum/NanumGothic.ttf'
                    ]
                    font_registered = False
                    for font_path in nanum_paths:
                        if Path(font_path).exists():
                            pdfmetrics.registerFont(TTFont('Nanum', font_path))
                            font_name = 'Nanum'
                            logger.debug("한글 폰트 등록 성공: 나눔고딕")
                            font_registered = True
                            break
                    
                    if not font_registered:
                        font_name = 'Helvetica'
                        logger.warning("한글 폰트를 찾을 수 없습니다. 기본 폰트 사용")
            except Exception as font_error:
                logger.warning(f"폰트 등록 중 오류: {font_error}")
                font_name = 'Helvetica'
            
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
            lines = content.split('\n')
            
            for line in lines:
                if line.strip():
                    # 특수 문자 이스케이프
                    escaped_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    para = Paragraph(escaped_line, custom_style)
                    story.append(para)
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
    
    def cleanup_temp(self):
        """임시 파일 정리"""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                self.temp_dir.mkdir(parents=True, exist_ok=True)
                logger.info("임시 파일 정리 완료")
        except Exception as e:
            logger.error(f"임시 파일 정리 실패: {e}")

