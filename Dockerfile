FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5009

# Run uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5009", "--reload"]

