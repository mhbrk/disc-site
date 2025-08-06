FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire app into the image
COPY breba_app ./breba_app

# Install Python dependencies
RUN pip install --no-cache-dir -r breba_app/requirements.txt

# Command to run the app with uvicorn
CMD ["python", "breba_app/main.py"]

EXPOSE 8080
