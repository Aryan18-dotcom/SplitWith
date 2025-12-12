# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the entire project
COPY . .

# Create directories for uploads if they don't exist
RUN mkdir -p static/uploads/groups static/uploads/users_profile_pic

# Expose port 5000
EXPOSE 5000

# Set Flask app
ENV FLASK_APP=wsgi.py

# Run the Flask application
CMD ["python", "-m", "gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "wsgi:app"]
