import uuid
from datetime import datetime
from pathlib import Path

from app.core.settings import LISTINGS_FILE, THREADS_FILE, MESSAGES_DIR
from app.services.storage import read_jsonl, append_jsonl, ensure_storage


def find_listing(listing_id: str):
    for x in read_jsonl(LISTINGS_FILE):
        if x.get("id") == listing_id:
            return x
    return None


def find_thread(thread_id: str):
    for t in read_jsonl(THREADS_FILE):
        if t.get("thread_id") == thread_id:
            return t
    return None


def save_thread(thread: dict):
    ensure_storage()
    append_jsonl(THREADS_FILE, thread)


def create_thread(listing: dict, buyer_uid: str) -> dict:
    thread_id = str(uuid.uuid4())
    owner_uid = listing.get("owner_uid")

    thread = {
        "thread_id": thread_id,
        "listing_id": listing["id"],
        "participants": [buyer_uid, owner_uid],
        "listing_owner_uid": owner_uid,  # legacy/debug
        "buyer_uid": buyer_uid,          # legacy/debug
        "created_at": datetime.utcnow().isoformat(),
        "status": "open",
    }
    save_thread(thread)
    return thread


def find_existing_thread(listing_id: str, buyer_uid: str):
    for t in read_jsonl(THREADS_FILE):
        if t.get("listing_id") != listing_id:
            continue

        # new format
        parts = t.get("participants")
        if isinstance(parts, list) and buyer_uid in parts:
            return t

        # old format (compat)
        if t.get("buyer_uid") == buyer_uid:
            return t

    return None


def thread_messages_path(thread_id: str) -> Path:
    return MESSAGES_DIR / f"{thread_id}.jsonl"


def read_messages(thread_id: str):
    return read_jsonl(thread_messages_path(thread_id))


def add_message(thread_id: str, msg: dict):
    append_jsonl(thread_messages_path(thread_id), msg)