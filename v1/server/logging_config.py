import os
import traceback
from datetime import datetime

try:
    from elasticsearch import Elasticsearch
except Exception:  # pragma: no cover
    Elasticsearch = None  # type: ignore[assignment]


_ES_CLIENT = None


def _is_truthy_env(var_name: str) -> bool:
    value = os.getenv(var_name, "").strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def _get_es_client():
    global _ES_CLIENT
    if _ES_CLIENT is not None:
        return _ES_CLIENT

    if _is_truthy_env("MOBYPARK_DISABLE_ELASTIC_LOGS"):
        _ES_CLIENT = False
        return None

    if Elasticsearch is None:
        _ES_CLIENT = False
        return None

    _ES_CLIENT = Elasticsearch(os.getenv("MOBYPARK_ELASTIC_URL", "http://elasticsearch:9200"))
    return _ES_CLIENT


def log_event(level: str, event: str, message: str = "", **extra):
    doc = {
        "@timestamp": datetime.now().isoformat(),
        "level": level,
        "event": event,
        "message": message,
        "service": "fastapi-v1",
    }

    doc.update(extra)
    doc["traceback"] = traceback.format_exc()

    es = _get_es_client()
    if es is None:
        print(f"[{level}] {event}: {message} {extra}")
        return

    try:
        es.index(index="fastapi-v1-logs", document=doc)
    except Exception:
        print(f"[{level}] {event}: {message} {extra}")
