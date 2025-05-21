FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY /generator_agent/app ./app
COPY /common ./common
# Now we have app/app and app/common

COPY ./generator_agent/start.sh ./start.sh
RUN chmod +x ./start.sh

COPY ./generator_agent/subscribe_to_pubsub.py ./subscribe_to_pubsub.py
# Final /app directory structure:
# ├── app/                   # Contains the generator agent application code
# ├── common/                # Shared utilities and model
# ├── start.sh              # Entry-point script to launch the server
# └── subscribe_to_pubsub.py # Script to subscribe to pubsub

ENV PYTHONPATH=/app

CMD ["./start.sh"]
#CMD ["sleep", "infinity"]