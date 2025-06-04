FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements first (if you have a requirements.txt)
COPY ./breba_app/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire app into the image
COPY ./breba_app/app .
COPY ./common ./common
#COPY ./act_agent ./act_agent


# Command to run the app with uvicorn
CMD ["python", "main.py"]

EXPOSE 8080
