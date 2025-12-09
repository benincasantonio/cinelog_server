FROM python:3.12-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5009

# Run uvicorn
# Note: --reload is removed for production; use docker-compose.local.yml for local development with reload
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5009"]

