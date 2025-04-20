FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY /generator_agent ./generator_agent
COPY /common ./common

WORKDIR /app/generator_agent/app

ENV PYTHONPATH=/app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
#CMD "/bin/bash"
EXPOSE 8001