import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
SRC_DIR = BASE_DIR / "kb_src"
OUT_FILE = BASE_DIR / "kb.json"

CHUNK_WORDS = 220
OVERLAP_WORDS = 40

def chunk_words(text: str, chunk_words=220, overlap_words=40):
    words = text.split()
    chunks = []
    step = max(1, chunk_words - overlap_words)
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_words]).strip()
        if chunk:
            chunks.append(chunk)
        i += step
    return chunks

def main():
    if not SRC_DIR.exists():
        raise SystemExit(f"❌ Folder not found: {SRC_DIR}")

    items = []
    files = sorted(SRC_DIR.glob("*.txt"))
    if not files:
        raise SystemExit(f"❌ No .txt files in: {SRC_DIR}")

    idx = 0
    for p in files:
        raw = p.read_text(encoding="utf-8", errors="ignore")
        raw = raw.replace("\r\n", "\n").strip()

        # تقسيم مبدئي حسب فواصل كبيرة لو موجودة
        blocks = [b.strip() for b in raw.split("========================================") if b.strip()]
        for b_i, block in enumerate(blocks, start=1):
            chunks = chunk_words(block, CHUNK_WORDS, OVERLAP_WORDS)
            for c_i, c in enumerate(chunks, start=1):
                idx += 1
                items.append({
                    "id": f"{p.stem}_{b_i}_{c_i}",
                    "source": p.name,
                    "text": c
                })

    OUT_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Built KB: {OUT_FILE} (items={len(items)})")

if __name__ == "__main__":
    main()
