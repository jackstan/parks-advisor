from typing import List


def chunk_text(text: str, max_chars: int = 800) -> List[str]:
    """
    Very simple chunker:
    - Split on paragraphs
    - Merge paragraphs until close to max_chars
    """
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks = []
    current = ""

    for p in paragraphs:
        if len(current) + len(p) + 2 <= max_chars:
            current += ("\n" + p) if current else p
        else:
            chunks.append(current)
            current = p

    if current:
        chunks.append(current)

    return chunks
