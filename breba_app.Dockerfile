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
COPY ./requirements.txt .
# Public direcotry is used by chainlit to get files. Needs to be on the level of working directory
COPY breba_app/public ./public
COPY breba_app/.chainlit ./.chainlit
COPY breba_app/chainlit.md ./chainlit.md

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Command to run the app with uvicorn
CMD ["python", "breba_app/main.py"]

EXPOSE 8080
