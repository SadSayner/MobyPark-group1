import traceback
from elasticsearch import Elasticsearch
from datetime import datetime

es = Elasticsearch("http://elasticsearch:9200")


def log_event(level: str, event: str, message: str ="", **extra):
    doc = {
        "@timestamp": datetime.now().isoformat(),
        "level": level,
        "event": event,
        "message": message,
        "service": "fastapi-v1",
    }

    doc.update(extra)

    doc["traceback"] = traceback.format_exc()

    es.index(index="fastapi-v1-logs", document=doc)

    try:
        es.index(index="fastapi-v1-logs", document=doc)
    except ConnectionError:
        print(f"[{level}] {event}: {extra}")
