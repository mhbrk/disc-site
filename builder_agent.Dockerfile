FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY /builder_agent ./builder_agent
COPY /common ./common

COPY ./builder_agent/start.sh ./start.sh
COPY ./builder_agent/subscribe_to_pubsub.py ./subscribe_to_pubsub.py


RUN chmod +x ./start.sh


ENV PYTHONPATH=/app

CMD ["./start.sh"]