FROM python:3.12-slim

WORKDIR /MOBYPARK-GROUP1

ENV PYTHONPATH=/MOBYPARK-GROUP1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "v1.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
