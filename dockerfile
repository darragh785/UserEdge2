# Base image
FROM python:3.11-slim

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Turn off buffering for easier logging
ENV PYTHONUNBUFFERED=1

# Install dependencies
COPY requirements.txt .
RUN python -m pip install -r requirements.txt

# Configure working directory
WORKDIR /app
COPY . /app

# Create a non-root user for security
RUN adduser --uid 5678 --disabled-password --gecos "" appuser && \
    chown -R appuser /app
USER appuser

# Expose NiceGUI default port
EXPOSE 8080

# Startup command
CMD ["python", "main.py"]
