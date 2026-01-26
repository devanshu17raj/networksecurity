# Use a lightweight official Python image
FROM python:3.10-slim-buster

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first (for better caching)
COPY requirements.txt .

# Install dependencies
# We use --no-cache-dir to keep the image size small
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port 8000 (FastAPI default)
EXPOSE 7860

# Command to run the application
# "app:app" assumes your file is named app.py and the FastAPI instance is named app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]