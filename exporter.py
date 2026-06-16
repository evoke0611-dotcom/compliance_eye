import json
import os
import re


def _normalize_title(title):
    txt = re.sub(r"\s+", " ", str(title or "")).strip()
    return txt


def _normalize_description(desc):
    txt = str(desc or "")
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")
    txt = "\n".join([re.sub(r"\s+", " ", line).strip() for line in txt.split("\n")])
    txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
    return txt


def _sort_key(control_id):
    raw = str(control_id or "").strip()
    raw = raw.upper().replace("A.", "")
    parts = []
    for token in raw.split("."):
        if token.isdigit():
            parts.append((0, int(token)))
        else:
            parts.append((1, token))
    return parts

def export_to_jsonl(chunks, output_path):
    print(f"Exporting to {output_path}...")
    normalized_records = []

    for chunk in chunks:
        record = {
            "control_id": str(chunk.get("control_id", "")).strip(),
            "title": _normalize_title(chunk.get("title", "")),
            "description": _normalize_description(chunk.get("description", "")),
            "theme": chunk.get("theme", "ISO 27001 Requirement"),
        }
        normalized_records.append(record)

    normalized_records.sort(key=lambda r: _sort_key(r.get("control_id")))

    with open(output_path, 'w', encoding='utf-8') as f:
        for record in normalized_records:
            json_record = json.dumps(record, ensure_ascii=False)
            f.write(json_record + '\n')

    # Also export pretty metadata JSON for UI/readability.
    metadata_path = os.path.splitext(output_path)[0] + "_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as mf:
        json.dump(normalized_records, mf, ensure_ascii=False, indent=2)

    print(f"Done! Wrote JSONL and metadata to {metadata_path}")
