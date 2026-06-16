import re
import tiktoken

def count_tokens(text):
    encoder = tiktoken.get_encoding("cl100k_base")
    return len(encoder.encode(text))


def _normalize_inline_spaces(text):
    lines = []
    for line in (text or "").splitlines():
        lines.append(re.sub(r"\s+", " ", line).strip())
    return "\n".join([l for l in lines if l])


def _format_description(text):
    """Keep descriptions readable for UI and metadata JSON."""
    formatted = _normalize_inline_spaces(text)
    if not formatted:
        return ""

    # Create visual breaks for sub-points and notes.
    formatted = re.sub(r"\s([a-z]\))\s", r"\n\1 ", formatted)
    formatted = re.sub(r"\s(\d+\))\s", r"\n\1 ", formatted)
    formatted = re.sub(r"\s(NOTE(?:\s+\d+)?)\s", r"\n\1 ", formatted)
    formatted = re.sub(r"\s([—-])\s", r"\n- ", formatted)
    formatted = re.sub(r"\n{3,}", "\n\n", formatted)
    return formatted.strip()

def chunk_text(text):
    print("Chunking text...")
    chunks = []
    
    pattern = r'\n(?=\d+(?:\.\d+)*\s*\n?[A-Za-z])'
    
    raw_chunks = re.split(pattern, text)
    
    for raw_chunk in raw_chunks:
        raw_chunk = raw_chunk.strip()
        if not raw_chunk:
            continue
            
        # Extract ID and Title
        match = re.match(r'^(\d+(?:\.\d+)*)\s*\n?(.*?)(?:\n|$)', raw_chunk)
        
        if match:
            control_id = match.group(1).strip()
            
            # Check for Annex A control pattern where "Control" acts as a delimiter
            # between the multi-line title and the description.
            control_match = re.match(r'^(\d+(?:\.\d+)*)\s*\n([\s\S]*?)\nControl\b\s*\n?([\s\S]*)', raw_chunk)
            if control_match:
                title = _normalize_inline_spaces(control_match.group(2))
                description = "Control\n" + control_match.group(3).strip()
            else:
                title = _normalize_inline_spaces(match.group(2))
                description = raw_chunk[match.end():].strip()
        else:
            control_id = "General"
            title = "General Content"
            description = raw_chunk

        description = _format_description(description)
            
        # Ignore chunks that are practically empty
        if count_tokens(description) < 5 and count_tokens(title) < 5:
            continue
            
        theme = "ISO 27001 Requirement"
        
        # Chunk large descriptions
        tokens = count_tokens(description)
        if tokens > 500:
            paragraphs = [p.strip() for p in re.split(r"\n{2,}", description) if p.strip()]
            current_desc = ""
            for p in paragraphs:
                candidate = f"{current_desc}\n\n{p}".strip() if current_desc else p
                if count_tokens(candidate) < 400:
                    current_desc = candidate
                else:
                    if current_desc.strip():
                        chunks.append({
                            "control_id": control_id,
                            "title": title,
                            "description": current_desc.strip(),
                            "theme": theme
                        })
                    current_desc = p
            if current_desc.strip():
                chunks.append({
                    "control_id": control_id,
                    "title": title,
                    "description": current_desc.strip(),
                    "theme": theme
                })
        else:
            chunks.append({
                "control_id": control_id,
                "title": title,
                "description": description,
                "theme": theme
            })
            
    return chunks
