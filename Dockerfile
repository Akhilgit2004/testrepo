# 1. Use an official Python image
FROM python:3.11-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Copy the requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy your script into the container
COPY . .

# 5. Tell the container to run your app
CMD ["uvicorn", "app:main", "--host", "0.0.0.0", "--port", "8000"]
