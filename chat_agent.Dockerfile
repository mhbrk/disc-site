FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY /chat_agent/app ./chat_agent
COPY /common ./common

ENV PYTHONPATH=/app

CMD ["python", "chat_agent/main.py"]
#CMD ["sleep", "infinity"]