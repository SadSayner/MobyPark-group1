import os
from datetime import datetime

try:
    from elasticsearch import Elasticsearch
except Exception:  # elasticsearch is optional for local dev/tests
    Elasticsearch = None


_ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
_DISABLE_ELASTIC = os.getenv("MOBYPARK_DISABLE_ELASTIC_LOGS", "").strip().lower() in {"1", "true", "yes"}


def _get_es_client():
    if _DISABLE_ELASTIC or Elasticsearch is None:
        return None
    # Use small timeouts and no retries so missing ES never blocks app startup.
    return Elasticsearch(
        _ES_URL,
        request_timeout=1,
        retry_on_timeout=False,
        max_retries=0,
    )


_es = _get_es_client()


def log_event(level: str, event: str, **fields):
    if _es is None:
        return

    doc = {
        "@timestamp": datetime.now().isoformat(),
        "level": level,
        "event": event,
        "service": "fastapi-v1",
        **fields,
    }

    try:
        _es.index(index="fastapi-v1-logs", document=doc, request_timeout=1)
    except Exception:
        # Logging must never take down or stall the API.
        return
