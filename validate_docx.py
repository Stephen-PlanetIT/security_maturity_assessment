from docx import Document
from docx.opc.exceptions import PackageNotFoundError
import sys

try:
    doc = Document('/Users/Bradley.Collis/Downloads/Allerton_Grange_School_Cybersecurity_Maturity_Report (1).docx')
    print("Successfully loaded document with python-docx!")
except Exception as e:
    print(f"Error loading document: {type(e).__name__}: {e}")
    sys.exit(1)
