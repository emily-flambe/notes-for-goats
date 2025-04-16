# Use Python 3.9 as a base image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Run the application
CMD ["sh", "-c", "python notes_for_goats/manage.py migrate && python notes_for_goats/manage.py runserver 0.0.0.0:8000"] 