# 1. Use an official, lightweight Python runtime as the base image
FROM python:3.11-slim

# 2. Set system environment variables to optimize Python inside Docker
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing .pyc files to disk
# PYTHONUNBUFFERED: Forces logs to stream straight to the console without buffering
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# 3. Set the working directory inside the container
WORKDIR /app

# 4. Copy only the requirements file first to leverage Docker layer caching
COPY requirements.txt /app/

# 5. Install dependencies cleanly without caching the install files (saves disk space)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copy the rest of your local application code into the container
COPY . /app/

# 7. Expose the port that FastAPI will run on
EXPOSE 8000

# 8. Run the application using Uvicorn when the container starts
# Using string interpolation for the port allows cloud providers to override it easily
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
