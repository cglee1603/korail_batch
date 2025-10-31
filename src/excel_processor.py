"""
엑셀 파일 처리 모듈
시트별 헤더 자동 감지, 하이퍼링크 추출, 숨김 행 제외, 시트 타입 감지
"""
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from enum import Enum
import openpyxl
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.cell.cell import Cell
from logger import logger
from config import (
    TEST_MODE, TEST_MAX_SHEETS, TEST_MAX_ROWS,
    SHEET_TYPE_KEYWORDS, COLUMN_NAME_MAPPINGS,
    MAX_TEXT_LENGTH, ROW_SEPARATOR, TEXT_ENCODING
)


class SheetType(Enum):
    """시트 타입 분류"""
    TOC = "목차"  # 목차 시트 (처리 안 함)
    REV_MANAGED = "REV관리"  # REV + WBS 컬럼 존재
    VERSION_MANAGED = "작성버전관리"  # 작성버전 + 관리번호 컬럼 존재
    ATTACHMENT = "첨부파일"  # 하이퍼링크만 존재
    HISTORY = "이력관리"  # 이력관리 시트
    SOFTWARE = "소프트웨어형상"  # 소프트웨어 형상기록 시트
    UNKNOWN = "미분류"  # 알 수 없는 타입


class ExcelProcessor:
    """엑셀 파일 처리 클래스"""
    
    def __init__(self, excel_path: str):
        self.excel_path = Path(excel_path)
        self.workbook = None
        
    def load_workbook(self):
        """엑셀 파일 로드"""
        try:
            self.workbook = openpyxl.load_workbook(
                self.excel_path, 
                data_only=False,  # 하이퍼링크 읽기 위해 False
                keep_vba=False
            )
            logger.info(f"엑셀 파일 로드 완료: {self.excel_path}")
            return True
        except Exception as e:
            logger.error(f"엑셀 파일 로드 실패: {e}")
            return False
    
    def get_sheet_names(self) -> List[str]:
        """모든 시트 이름 반환"""
        if not self.workbook:
            return []
        return self.workbook.sheetnames
    
    def detect_header_row(self, sheet: Worksheet) -> int:
        """
        헤더 행 자동 감지 (개선된 로직)
        
        헤더의 특징:
        1. 여러 컬럼에 값이 채워져 있음 (최소 3개)
        2. 괄호나 의미있는 단어 포함 (예: "년도(1)", "제목", "구분")
        3. 단순 숫자나 짧은 텍스트만 있으면 제목일 가능성 높음
        4. 다음 행부터 규칙적인 데이터가 있음
        """
        max_search_row = min(15, sheet.max_row + 1)
        candidates = []
        
        for row_idx in range(1, max_search_row):
            row = list(sheet.iter_rows(min_row=row_idx, max_row=row_idx, values_only=True))[0]
            
            # 비어있지 않은 셀 개수
            non_empty_cells = [cell for cell in row if cell is not None and str(cell).strip()]
            non_empty_count = len(non_empty_cells)
            
            # 최소 3개 이상의 값이 있어야 함
            if non_empty_count < 3:
                continue
            
            # 헤더 점수 계산
            score = 0
            
            # 1. 비어있지 않은 셀이 많을수록 점수 증가
            score += non_empty_count
            
            # 2. 헤더 특성 분석
            for cell in non_empty_cells[:10]:  # 처음 10개 컬럼만 분석
                cell_str = str(cell).strip()
                
                # 괄호가 있으면 헤더일 가능성 높음 (예: "년도(1)")
                if '(' in cell_str and ')' in cell_str:
                    score += 5
                
                # 단순 숫자 1~2자리면 제목일 가능성 높음 (감점)
                if cell_str.isdigit() and len(cell_str) <= 2:
                    score -= 3
                
                # 일반적인 헤더 키워드
                header_keywords = ['년도', '제목', '구분', '번호', '이름', '코드', '상태', 
                                 '날짜', '작성', '담당', '버전', 'WBS', '종별', '관리']
                if any(keyword in cell_str for keyword in header_keywords):
                    score += 3
                
                # 너무 긴 텍스트는 제목일 가능성 높음 (감점)
                if len(cell_str) > 30:
                    score -= 2
            
            # 3. 다음 행에 데이터가 있는지 확인
            if row_idx < sheet.max_row:
                next_row = list(sheet.iter_rows(min_row=row_idx+1, max_row=row_idx+1, values_only=True))[0]
                next_non_empty = sum(1 for cell in next_row if cell is not None and str(cell).strip())
                
                # 다음 행에도 비슷한 개수의 데이터가 있으면 헤더일 가능성 높음
                if next_non_empty >= non_empty_count * 0.5:
                    score += 3
            
            candidates.append((row_idx, score, non_empty_count))
            logger.debug(f"{row_idx}행 점수: {score} (비어있지 않은 셀: {non_empty_count}개)")
        
        # 가장 높은 점수의 행을 헤더로 선택
        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            best_row, best_score, best_count = candidates[0]
            logger.info(f"헤더 행 감지: {best_row}행 (점수: {best_score}, 비어있지 않은 셀: {best_count}개)")
            return best_row
        
        # 기본값: 1행
        logger.warning("헤더 행을 찾지 못했습니다. 1행을 헤더로 사용합니다.")
        return 1
    
    def get_headers(self, sheet: Worksheet, header_row: int) -> List[str]:
        """헤더 행에서 컬럼명 추출"""
        headers = []
        for cell in sheet[header_row]:
            value = cell.value
            if value is not None:
                headers.append(str(value).strip())
            else:
                headers.append(f"Column_{cell.column}")
        return headers
    
    def _find_column_by_keywords(self, headers: List[str], keywords: List[str]) -> Optional[int]:
        """
        키워드 리스트로 헤더에서 컬럼 인덱스 찾기 (첫 번째만)
        
        Args:
            headers: 헤더 리스트
            keywords: 찾을 키워드 리스트
        
        Returns:
            컬럼 인덱스 (0-based) 또는 None
        """
        for idx, header in enumerate(headers):
            header_normalized = header.strip().replace(' ', '').lower()
            for keyword in keywords:
                keyword_normalized = keyword.strip().replace(' ', '').lower()
                if keyword_normalized in header_normalized:
                    return idx
        return None
    
    def _find_all_columns_by_keywords(self, headers: List[str], keywords: List[str]) -> List[int]:
        """
        키워드 리스트로 헤더에서 모든 매칭 컬럼 인덱스 찾기
        
        Args:
            headers: 헤더 리스트
            keywords: 찾을 키워드 리스트
        
        Returns:
            컬럼 인덱스 리스트 (0-based)
        """
        matching_indices = []
        for idx, header in enumerate(headers):
            header_normalized = header.strip().replace(' ', '').lower()
            for keyword in keywords:
                keyword_normalized = keyword.strip().replace(' ', '').lower()
                if keyword_normalized in header_normalized:
                    matching_indices.append(idx)
                    break  # 하나라도 매칭되면 추가하고 다음 헤더로
        return matching_indices
    
    def detect_sheet_type(self, sheet: Worksheet, sheet_name: str, headers: List[str]) -> SheetType:
        """
        시트 타입 자동 감지
        
        판별 기준:
        1. 목차: 시트명 + 헤더에 목차 키워드
        2. 소프트웨어: 시트명에 "소프트웨어" 포함
        3. 이력관리: 시트명에 "이력" 관련 키워드
        4. REV 관리: 헤더에 "REV" + "WBS" 컬럼 존재
        5. 작성버전 관리: 헤더에 "작성버전" + "관리번호" 컬럼 존재
        6. 첨부파일: 하이퍼링크가 존재하고 REV/작성버전 없음
        
        Args:
            sheet: 워크시트 객체
            sheet_name: 시트 이름
            headers: 헤더 리스트
        
        Returns:
            SheetType enum
        """
        sheet_name_lower = sheet_name.lower()
        
        # 1. 목차 시트 (시트명 + 헤더 키워드)
        for keyword in SHEET_TYPE_KEYWORDS['toc']:
            if keyword.lower() in sheet_name_lower:
                # 헤더에도 목차 관련 키워드가 있는지 확인
                header_text = ' '.join(headers).lower()
                if any(kw.lower() in header_text for kw in SHEET_TYPE_KEYWORDS['toc']):
                    logger.info(f"시트 타입 감지: {sheet_name} → 목차 (시트명+헤더 키워드)")
                    return SheetType.TOC
        
        # 2. 소프트웨어 형상기록 시트 (시트명 우선)
        for keyword in SHEET_TYPE_KEYWORDS['software']:
            if keyword.lower() in sheet_name_lower:
                logger.info(f"시트 타입 감지: {sheet_name} → 소프트웨어 형상기록 (시트명)")
                return SheetType.SOFTWARE
        
        # 3. 이력관리 시트 (시트명)
        for keyword in SHEET_TYPE_KEYWORDS['history']:
            if keyword.lower() in sheet_name_lower:
                logger.info(f"시트 타입 감지: {sheet_name} → 이력관리 (시트명)")
                return SheetType.HISTORY
        
        # 4. REV 관리 문서 (헤더에 REV + WBS 컬럼)
        rev_col_idx = self._find_column_by_keywords(headers, COLUMN_NAME_MAPPINGS['rev'])
        wbs_col_idx = self._find_column_by_keywords(headers, COLUMN_NAME_MAPPINGS['wbs'])
        
        if rev_col_idx is not None and wbs_col_idx is not None:
            logger.info(f"시트 타입 감지: {sheet_name} → REV 관리 (REV+WBS 컬럼)")
            return SheetType.REV_MANAGED
        
        # 5. 작성버전 관리 문서 (헤더에 작성버전 + 관리번호 컬럼)
        version_col_idx = self._find_column_by_keywords(headers, COLUMN_NAME_MAPPINGS['version'])
        manage_no_col_idx = self._find_column_by_keywords(headers, COLUMN_NAME_MAPPINGS['manage_no'])
        
        if version_col_idx is not None and manage_no_col_idx is not None:
            logger.info(f"시트 타입 감지: {sheet_name} → 작성버전 관리 (작성버전+관리번호 컬럼)")
            return SheetType.VERSION_MANAGED
        
        # 6. 첨부파일 시트 (하이퍼링크 존재 여부 확인)
        # 최대 10개 행만 확인 (빠른 판별)
        has_hyperlink = False
        for row_idx in range(1, min(sheet.max_row + 1, 20)):
            for cell in sheet[row_idx]:
                if self.extract_hyperlink(cell):
                    has_hyperlink = True
                    break
            if has_hyperlink:
                break
        
        if has_hyperlink:
            logger.info(f"시트 타입 감지: {sheet_name} → 첨부파일 (하이퍼링크 존재)")
            return SheetType.ATTACHMENT
        
        # 기본값: 미분류
        logger.warning(f"시트 타입 감지: {sheet_name} → 미분류 (알 수 없는 타입)")
        return SheetType.UNKNOWN
    
    def is_row_hidden(self, sheet: Worksheet, row_idx: int) -> bool:
        """행이 숨겨져 있거나 높이가 0인지 확인"""
        try:
            row_dimension = sheet.row_dimensions[row_idx]
            # 숨김 처리되었거나 높이가 0인 경우
            if row_dimension.hidden:
                return True
            if row_dimension.height is not None and row_dimension.height == 0:
                return True
            return False
        except:
            return False
    
    def extract_hyperlink(self, cell: Cell) -> Optional[str]:
        """셀에서 하이퍼링크 추출"""
        if cell.hyperlink:
            # 하이퍼링크 객체가 있는 경우
            target = cell.hyperlink.target
            if target:
                return target
        
        # 수식에서 하이퍼링크 추출 시도
        if cell.value and isinstance(cell.value, str):
            if cell.value.startswith('=HYPERLINK'):
                # =HYPERLINK("url", "display") 형식 파싱
                try:
                    start = cell.value.index('"') + 1
                    end = cell.value.index('"', start)
                    return cell.value[start:end]
                except:
                    pass
        
        return None
    
    def generate_document_key(
        self, 
        sheet_type: SheetType, 
        sheet_name: str, 
        row_data: Dict[str, str],
        headers: List[str]
    ) -> Optional[str]:
        """
        문서 고유 키 생성 (Revision 관리용)
        
        Args:
            sheet_type: 시트 타입
            sheet_name: 시트 이름
            row_data: 행 데이터 (헤더: 값)
            headers: 헤더 리스트
        
        Returns:
            문서 키 또는 None
        """
        if sheet_type == SheetType.REV_MANAGED:
            # REV 관리: 모든 WBS 컬럼 값 합치기 + 시트명
            wbs_col_indices = self._find_all_columns_by_keywords(headers, COLUMN_NAME_MAPPINGS['wbs'])
            
            if wbs_col_indices:
                wbs_values = []
                for idx in wbs_col_indices:
                    if idx < len(headers):
                        wbs_header = headers[idx]
                        wbs_value = row_data.get(wbs_header, '').strip()
                        if wbs_value:
                            wbs_values.append(wbs_value)
                
                if wbs_values:
                    # 모든 WBS 값을 '-'로 연결
                    combined_wbs = '-'.join(wbs_values)
                    # 공백, 특수문자 정규화
                    key = f"{combined_wbs}_{sheet_name}"
                    key = key.replace(' ', '_').replace('/', '_').replace('\\', '_')
                    logger.debug(f"생성된 문서 키 (WBS 컬럼 {len(wbs_values)}개): {key}")
                    return key
        
        elif sheet_type == SheetType.VERSION_MANAGED:
            # 작성버전 관리: 관리번호 + 시트명
            manage_no_col_idx = self._find_column_by_keywords(headers, COLUMN_NAME_MAPPINGS['manage_no'])
            if manage_no_col_idx is not None and manage_no_col_idx < len(headers):
                manage_no_header = headers[manage_no_col_idx]
                manage_no_value = row_data.get(manage_no_header, '').strip()
                if manage_no_value:
                    # 공백, 특수문자 정규화
                    key = f"{manage_no_value}_{sheet_name}"
                    key = key.replace(' ', '_').replace('/', '_').replace('\\', '_')
                    return key
        
        return None
    
    def get_revision_value(
        self, 
        sheet_type: SheetType, 
        row_data: Dict[str, str],
        headers: List[str],
        row_cells: List[Cell] = None
    ) -> Optional[str]:
        """
        행에서 revision 값 추출
        
        Args:
            sheet_type: 시트 타입
            row_data: 행 데이터 (헤더: 값)
            headers: 헤더 리스트
            row_cells: 행의 셀 리스트 (하이퍼링크 텍스트 추출용, 선택)
        
        Returns:
            revision 값 또는 None
            
        Note:
            - REV 관리: rev 컬럼의 하이퍼링크 텍스트가 revision 명
            - 작성버전 관리: 관리번호 컬럼의 하이퍼링크 텍스트가 revision 명
        """
        if sheet_type == SheetType.REV_MANAGED:
            # REV 컬럼에서 값 추출 (하이퍼링크 텍스트 우선)
            rev_col_idx = self._find_column_by_keywords(headers, COLUMN_NAME_MAPPINGS['rev'])
            if rev_col_idx is not None and rev_col_idx < len(headers):
                # 1. 셀이 제공된 경우: 하이퍼링크 텍스트(셀 표시 텍스트) 추출
                if row_cells and rev_col_idx < len(row_cells):
                    cell = row_cells[rev_col_idx]
                    if cell.value is not None:
                        rev_value = str(cell.value).strip()
                        if rev_value:
                            logger.debug(f"REV 컬럼에서 하이퍼링크 텍스트 추출: {rev_value}")
                            return rev_value
                
                # 2. 폴백: row_data에서 추출
                rev_header = headers[rev_col_idx]
                rev_value = row_data.get(rev_header, '').strip()
                return rev_value if rev_value else None
        
        elif sheet_type == SheetType.VERSION_MANAGED:
            # 작성버전 컬럼에서 값 추출
            version_col_idx = self._find_column_by_keywords(headers, COLUMN_NAME_MAPPINGS['version'])
            if version_col_idx is not None and version_col_idx < len(headers):
                # 1. 셀이 제공된 경우: 하이퍼링크 텍스트(셀 표시 텍스트) 추출
                if row_cells and version_col_idx < len(row_cells):
                    cell = row_cells[version_col_idx]
                    if cell.value is not None:
                        version_value = str(cell.value).strip()
                        if version_value:
                            logger.debug(f"작성버전 컬럼에서 하이퍼링크 텍스트 추출: {version_value}")
                            return version_value
                
                # 2. 폴백: row_data에서 추출
                version_header = headers[version_col_idx]
                version_value = row_data.get(version_header, '').strip()
                return version_value if version_value else None
        
        return None
    
    def extract_sheet_as_excel(self, sheet_name: str, output_dir: Path) -> Optional[Path]:
        """
        특정 시트를 독립된 Excel 파일로 추출
        
        Args:
            sheet_name: 추출할 시트 이름
            output_dir: 출력 디렉토리
        
        Returns:
            추출된 Excel 파일 경로 또는 None
        """
        if not self.workbook:
            logger.error("워크북이 로드되지 않았습니다.")
            return None
        
        try:
            # 새 워크북 생성
            new_wb = openpyxl.Workbook()
            new_wb.remove(new_wb.active)  # 기본 시트 제거
            
            # 원본 시트 복사
            source_sheet = self.workbook[sheet_name]
            target_sheet = new_wb.create_sheet(sheet_name)
            
            # 모든 셀 복사 (값, 스타일 포함)
            for row in source_sheet.iter_rows():
                for cell in row:
                    target_cell = target_sheet[cell.coordinate]
                    target_cell.value = cell.value
                    
                    # 스타일 복사 (간단 버전)
                    if cell.has_style:
                        target_cell.font = cell.font.copy()
                        target_cell.border = cell.border.copy()
                        target_cell.fill = cell.fill.copy()
                        target_cell.number_format = cell.number_format
                        target_cell.protection = cell.protection.copy()
                        target_cell.alignment = cell.alignment.copy()
            
            # 컬럼 너비 복사
            for col_letter in source_sheet.column_dimensions:
                if col_letter in source_sheet.column_dimensions:
                    target_sheet.column_dimensions[col_letter].width = \
                        source_sheet.column_dimensions[col_letter].width
            
            # 행 높이 복사
            for row_num in source_sheet.row_dimensions:
                if row_num in source_sheet.row_dimensions:
                    target_sheet.row_dimensions[row_num].height = \
                        source_sheet.row_dimensions[row_num].height
            
            # 파일 저장
            output_path = output_dir / f"{sheet_name}.xlsx"
            new_wb.save(output_path)
            new_wb.close()
            
            logger.info(f"시트 '{sheet_name}'를 Excel 파일로 추출: {output_path}")
            return output_path
        
        except Exception as e:
            logger.error(f"시트 '{sheet_name}' Excel 추출 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def convert_sheet_to_text_chunks(
        self, 
        sheet_name: str, 
        max_length: int = MAX_TEXT_LENGTH
    ) -> List[str]:
        """
        시트 전체를 텍스트로 변환 (이력관리/소프트웨어 형상기록용)
        Row 단위로 체크하여 max_length를 초과하면 여러 청크로 분할
        
        형식:
        헤더1: 값1
        헤더2: 값2
        ---
        헤더1: 값3
        헤더2: 값4
        ...
        
        Args:
            sheet_name: 시트 이름
            max_length: 청크당 최대 문자 수 (토큰 제한)
        
        Returns:
            변환된 텍스트 청크 리스트
        """
        if not self.workbook:
            logger.error("워크북이 로드되지 않았습니다.")
            return []
        
        sheet = self.workbook[sheet_name]
        
        # 헤더 행 감지
        header_row = self.detect_header_row(sheet)
        headers = self.get_headers(sheet, header_row)
        
        chunks = []
        current_chunk_rows = []
        current_length = 0
        data_start_row = header_row + 1
        
        for row_idx in range(data_start_row, sheet.max_row + 1):
            # 숨겨진 행 제외
            if self.is_row_hidden(sheet, row_idx):
                continue
            
            row_cells = list(sheet[row_idx])
            
            # 빈 행 건너뛰기
            if all(cell.value is None for cell in row_cells):
                continue
            
            # 행 데이터를 텍스트로 변환
            row_text_parts = []
            for col_idx, cell in enumerate(row_cells):
                if col_idx < len(headers):
                    header = headers[col_idx]
                    value = cell.value
                    if value is not None:
                        value_str = str(value).strip()
                        if value_str:
                            row_text_parts.append(f"{header}: {value_str}")
            
            if row_text_parts:
                row_text = '\n'.join(row_text_parts)
                row_length = len(row_text) + len(ROW_SEPARATOR)
                
                # 현재 청크에 추가했을 때 max_length를 초과하는지 체크
                if current_length + row_length > max_length and current_chunk_rows:
                    # 현재 청크 저장하고 새 청크 시작
                    chunk_text = ROW_SEPARATOR.join(current_chunk_rows)
                    chunks.append(chunk_text)
                    logger.debug(f"청크 {len(chunks)} 완료: {len(chunk_text)}자, {len(current_chunk_rows)}개 행")
                    
                    # 새 청크 시작
                    current_chunk_rows = [row_text]
                    current_length = row_length
                else:
                    # 현재 청크에 추가
                    current_chunk_rows.append(row_text)
                    current_length += row_length
        
        # 마지막 청크 추가
        if current_chunk_rows:
            chunk_text = ROW_SEPARATOR.join(current_chunk_rows)
            chunks.append(chunk_text)
            logger.debug(f"청크 {len(chunks)} 완료: {len(chunk_text)}자, {len(current_chunk_rows)}개 행")
        
        logger.info(f"시트 '{sheet_name}' 텍스트 변환 완료: 총 {len(chunks)}개 청크, "
                   f"총 {sum(len(c) for c in chunks)}자")
        return chunks
    
    def process_sheet(self, sheet_name: str) -> Tuple[SheetType, List[Dict], List[str]]:
        """
        시트 처리 - 시트 타입 감지, 하이퍼링크와 메타데이터 추출
        
        Returns:
            Tuple[SheetType, List[Dict], List[str]]: (
                시트 타입,
                [
                    {
                        'hyperlink': 'file_url',
                        'metadata': {'col1': 'val1', 'col2': 'val2', ...},
                        'row_number': 5,
                        'document_key': 'WBS-1.2.3_시트명' (revision 관리 시트만),
                        'revision': '1.0' (revision 관리 시트만)
                    },
                    ...
                ],
                헤더 리스트
            )
        """
        if not self.workbook:
            logger.error("워크북이 로드되지 않았습니다.")
            return SheetType.UNKNOWN, [], []
        
        sheet = self.workbook[sheet_name]
        logger.log_sheet_start(sheet_name)
        
        # 헤더 행 감지
        header_row = self.detect_header_row(sheet)
        headers = self.get_headers(sheet, header_row)
        logger.info(f"헤더: {headers}")
        
        # 시트 타입 감지
        sheet_type = self.detect_sheet_type(sheet, sheet_name, headers)
        
        results = []
        data_start_row = header_row + 1
        
        # 데이터 행 처리
        for row_idx in range(data_start_row, sheet.max_row + 1):
            # 테스트 모드: 행 수 제한 확인
            if TEST_MODE and TEST_MAX_ROWS > 0 and len(results) >= TEST_MAX_ROWS:
                logger.warning(f"[테스트 모드] 시트 '{sheet_name}': {TEST_MAX_ROWS}개 행 제한 도달, 나머지 행 건너뜀")
                break
            
            # 숨겨진 행 또는 높이가 0인 행 제외
            if self.is_row_hidden(sheet, row_idx):
                logger.debug(f"{row_idx}행은 숨김 처리되었거나 높이가 0이어서 건너뜁니다.")
                continue
            
            row_cells = list(sheet[row_idx])
            
            # 빈 행 건너뛰기
            if all(cell.value is None for cell in row_cells):
                continue
            
            # 하이퍼링크 찾기
            hyperlink = None
            for cell in row_cells:
                link = self.extract_hyperlink(cell)
                if link:
                    hyperlink = link
                    break
            
            # 하이퍼링크가 없으면 건너뛰기 (첨부파일 시트만 해당)
            if not hyperlink and sheet_type in [SheetType.ATTACHMENT, SheetType.REV_MANAGED, SheetType.VERSION_MANAGED]:
                continue
            
            # 메타데이터 구성
            metadata = {}
            for col_idx, cell in enumerate(row_cells):
                if col_idx < len(headers):
                    header = headers[col_idx]
                    value = cell.value
                    if value is not None:
                        metadata[header] = str(value).strip()
            
            result = {
                'hyperlink': hyperlink,
                'metadata': metadata,
                'row_number': row_idx,
                'sheet_name': sheet_name
            }
            
            # Revision 관리 시트인 경우: document_key와 revision 추가
            if sheet_type in [SheetType.REV_MANAGED, SheetType.VERSION_MANAGED]:
                document_key = self.generate_document_key(sheet_type, sheet_name, metadata, headers)
                # row_cells를 전달하여 하이퍼링크 텍스트에서 revision 명 추출
                revision = self.get_revision_value(sheet_type, metadata, headers, row_cells)
                
                if document_key:
                    result['document_key'] = document_key
                if revision:
                    result['revision'] = revision
                
                logger.debug(f"{row_idx}행: 문서키={document_key}, revision={revision}")
            
            results.append(result)
            
            if hyperlink:
                logger.debug(f"{row_idx}행 처리 완료 - 하이퍼링크: {hyperlink}")
        
        logger.log_sheet_end(sheet_name, len(results))
        return sheet_type, results, headers
    
    def process_all_sheets(self) -> Dict[str, Tuple[SheetType, List[Dict], List[str]]]:
        """
        모든 시트 처리 (숨겨진 시트 제외)
        
        Returns:
            Dict[str, Tuple[SheetType, List[Dict], List[str]]]: {
                'sheet1': (시트타입, [항목들...], [헤더들...]),
                'sheet2': (시트타입, [항목들...], [헤더들...]),
                ...
            }
        """
        if not self.load_workbook():
            return {}
        
        all_results = {}
        sheet_names = self.get_sheet_names()
        
        logger.info(f"총 {len(sheet_names)}개 시트 발견: {sheet_names}")
        
        # 테스트 모드 알림
        if TEST_MODE:
            logger.warning(f"[테스트 모드] 활성화됨 - 최대 {TEST_MAX_SHEETS}개 시트, 시트당 {TEST_MAX_ROWS}개 행만 처리")
        
        processed_sheet_count = 0
        for sheet_name in sheet_names:
            # 테스트 모드: 시트 수 제한 확인
            if TEST_MODE and TEST_MAX_SHEETS > 0 and processed_sheet_count >= TEST_MAX_SHEETS:
                logger.warning(f"[테스트 모드] {TEST_MAX_SHEETS}개 시트 제한 도달, 나머지 시트 건너뜀")
                break
            
            try:
                sheet = self.workbook[sheet_name]
                
                # 시트가 숨겨져 있는지 확인
                if sheet.sheet_state == 'hidden' or sheet.sheet_state == 'veryHidden':
                    logger.info(f"시트 '{sheet_name}'는 숨김 처리되어 건너뜁니다.")
                    continue
                
                sheet_type, results, headers = self.process_sheet(sheet_name)
                all_results[sheet_name] = (sheet_type, results, headers)
                processed_sheet_count += 1
            except Exception as e:
                logger.error(f"시트 '{sheet_name}' 처리 중 오류: {e}")
                import traceback
                logger.error(traceback.format_exc())
                continue
        
        return all_results
    
    def close(self):
        """워크북 닫기"""
        if self.workbook:
            self.workbook.close()
            logger.info("워크북 닫기 완료")

