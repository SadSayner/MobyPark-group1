from elasticsearch import Elasticsearch
from datetime import datetime

es = Elasticsearch("httpL//localhost:9200")


def log_event(level: str, event: str, **fields):
    doc = {
        "@timestamp": datetime.now().isoformat(),
        "level": level,
        "event": event,
        "service": "fastapi-v1",
        **fields,
    }
    es.index(index="fastapi-v1-logs", document=doc)
