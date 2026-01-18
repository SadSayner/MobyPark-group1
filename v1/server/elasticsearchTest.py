from elasticsearch import Elasticsearch

es = Elasticsearch(hosts=["http://localhost:9200"])

doc = {
    "message": "hello from Python",
    "service": "fastapi-v1",
}

es.index(index="fastapi-v1-logs", document=doc)
print("log send")
