"""Delimiter 설정 확인"""
import sys
sys.path.insert(0, ".")
from src.config import PARSER_CONFIG, get_delimiter
import json

print("=== PARSER_CONFIG ===")
print(json.dumps(PARSER_CONFIG, indent=2, ensure_ascii=False))

print("\n=== Delimiter Details ===")
delimiter = PARSER_CONFIG['delimiter']
print(f"Delimiter: {repr(delimiter)}")
print(f"Delimiter length: {len(delimiter)}")
print(f"Delimiter bytes: {delimiter.encode('utf-8')}")
print(f"Characters:")
for i, ch in enumerate(delimiter):
    print(f"  [{i}] {repr(ch)} (ord={ord(ch)}, \\u{ord(ch):04x})")

