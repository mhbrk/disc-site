FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY /builder_agent ./builder_agent
COPY /common ./common

WORKDIR /app/builder_agent

ENV PYTHONPATH=/app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
#CMD "/bin/bash"
EXPOSE 8002