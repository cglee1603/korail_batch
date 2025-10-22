"""
엑셀 파일 처리 모듈
시트별 헤더 자동 감지, 하이퍼링크 추출, 숨김 행 제외
"""
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import openpyxl
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.cell.cell import Cell
from logger import logger


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
    
    def process_sheet(self, sheet_name: str) -> List[Dict]:
        """
        시트 처리 - 하이퍼링크와 메타데이터 추출
        
        Returns:
            List[Dict]: [
                {
                    'hyperlink': 'file_url',
                    'metadata': {'col1': 'val1', 'col2': 'val2', ...},
                    'row_number': 5
                },
                ...
            ]
        """
        if not self.workbook:
            logger.error("워크북이 로드되지 않았습니다.")
            return []
        
        sheet = self.workbook[sheet_name]
        logger.log_sheet_start(sheet_name)
        
        # 헤더 행 감지
        header_row = self.detect_header_row(sheet)
        headers = self.get_headers(sheet, header_row)
        logger.info(f"헤더: {headers}")
        
        results = []
        data_start_row = header_row + 1
        
        # 데이터 행 처리
        for row_idx in range(data_start_row, sheet.max_row + 1):
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
            
            # 하이퍼링크가 없으면 건너뛰기
            if not hyperlink:
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
            results.append(result)
            
            logger.debug(f"{row_idx}행 처리 완료 - 하이퍼링크: {hyperlink}")
        
        logger.log_sheet_end(sheet_name, len(results))
        return results
    
    def process_all_sheets(self) -> Dict[str, List[Dict]]:
        """
        모든 시트 처리 (숨겨진 시트 제외)
        
        Returns:
            Dict[str, List[Dict]]: {
                'sheet1': [항목들...],
                'sheet2': [항목들...],
                ...
            }
        """
        if not self.load_workbook():
            return {}
        
        all_results = {}
        sheet_names = self.get_sheet_names()
        
        logger.info(f"총 {len(sheet_names)}개 시트 발견: {sheet_names}")
        
        for sheet_name in sheet_names:
            try:
                sheet = self.workbook[sheet_name]
                
                # 시트가 숨겨져 있는지 확인
                if sheet.sheet_state == 'hidden' or sheet.sheet_state == 'veryHidden':
                    logger.info(f"시트 '{sheet_name}'는 숨김 처리되어 건너뜁니다.")
                    continue
                
                results = self.process_sheet(sheet_name)
                all_results[sheet_name] = results
            except Exception as e:
                logger.error(f"시트 '{sheet_name}' 처리 중 오류: {e}")
                continue
        
        return all_results
    
    def close(self):
        """워크북 닫기"""
        if self.workbook:
            self.workbook.close()
            logger.info("워크북 닫기 완료")

