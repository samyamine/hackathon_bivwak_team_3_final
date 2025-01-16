# Use the official Python image
FROM python:3.10

# Set the working directory
WORKDIR /app

# Copy the Python dependencies file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the FastAPI application code
COPY backend.py .

# Expose the application port
EXPOSE 8000

# Command to run the FastAPI server
CMD ["uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "8000"]