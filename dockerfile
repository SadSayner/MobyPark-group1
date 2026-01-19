FROM python:3.14-slim

WORKDIR /MOBYPARK-GROUP1

ENV PYTHONPATH=/MOBYPARK-GROUP1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY fix-permissions.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/fix-permissions.sh

ENTRYPOINT ["/usr/local/bin/fix-permissions.sh"]
CMD ["uvicorn", "v1.server.app:app", "--host", "0.0.0.0", "--port", "8000"]