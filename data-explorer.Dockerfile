# Use an official Python runtime as a parent image
#FROM 142496269814.dkr.ecr.us-west-2.amazonaws.com/python:3.9-slim
FROM python:3.9-slim

# Install system dependencies required for psycopg2
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Define environment variable
ENV NAME World

ENV PYTHONPATH /usr/src/app

# Run app.py when the container launches
CMD ["python3", "-m", "data_explorer"]

