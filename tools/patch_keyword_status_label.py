from pathlib import Path

path = Path("index.html")
text = path.read_text(encoding="utf-8")
old = "function methodName(status){const s=String(status||'');if(s.startsWith('ok_openai'))return 'OpenAI-assisted PDF extraction';if(s.startsWith('ok_pdf_text'))return 'PDF text extraction';if(s.startsWith('ok_pdfplumber'))return 'PDF table extraction';return 'automated extraction'}"
new = "function methodName(status){const s=String(status||'');if(s.startsWith('ok_openai'))return 'OpenAI-assisted PDF extraction';if(s.startsWith('ok_pdf_keyword_table'))return 'keyword-aware PDF table extraction';if(s.startsWith('ok_pdf_text'))return 'PDF text extraction';if(s.startsWith('ok_pdfplumber'))return 'PDF table extraction';return 'automated extraction'}"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit("Could not find methodName function")
path.write_text(text, encoding="utf-8")
print("keyword status label patched")
