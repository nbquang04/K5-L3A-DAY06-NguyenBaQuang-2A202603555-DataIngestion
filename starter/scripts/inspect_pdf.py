import json
import unicodedata
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
PDF_PATH = ROOT / "data/raw/thinkpython2.pdf"
OUTPUT_DIR = ROOT / "data/processed"


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(PDF_PATH)
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = normalize(page.extract_text() or "")
        pages.append({
            "document_id": "thinkpython2",
            "source": "data/raw/thinkpython2.pdf",
            "page": page_number,
            "text": text,
            "char_count": len(text),
        })

    output = OUTPUT_DIR / "pages.json"
    output.write_text(
        json.dumps(pages, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Total PDF pages: {len(pages)}")
    print(f"Empty pages: {sum(not p['text'] for p in pages)}")
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()