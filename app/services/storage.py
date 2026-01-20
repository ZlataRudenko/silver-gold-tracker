import json
from pathlib import Path
from app.core.settings import DATA_DIR, MESSAGES_DIR, LISTINGS_FILE, THREADS_FILE, INQUIRIES_FILE, SELL_REQUESTS_FILE


def ensure_storage():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MESSAGES_DIR.mkdir(parents=True, exist_ok=True)

    for p in (LISTINGS_FILE, THREADS_FILE, INQUIRIES_FILE, SELL_REQUESTS_FILE):
        if not p.exists():
            p.write_text("", encoding="utf-8")


def read_jsonl(path: Path):
    if not path.exists():
        return []
    items = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                pass
    return items


def append_jsonl(path: Path, obj: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def update_jsonl_by_id(path: Path, item_id: str, updates: dict, id_field="id"):
    items = read_jsonl(path)
    changed = False
    for x in items:
        if x.get(id_field) == item_id:
            x.update(updates)
            changed = True
            break
    if changed:
        with path.open("w", encoding="utf-8") as f:
            for x in items:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    return changed


def save_listing(listing: dict):
    ensure_storage()
    append_jsonl(LISTINGS_FILE, listing)


def load_listings():
    ensure_storage()
    return read_jsonl(LISTINGS_FILE)
