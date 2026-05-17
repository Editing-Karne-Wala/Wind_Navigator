FROM python:3.12-slim

# Set the working directory
WORKDIR /code

# Copy the requirements and install them
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Create necessary directories for the app and ensure write permissions
RUN mkdir -p /code/uploads /code/reports /code/public \
    && chmod -R 777 /code/uploads \
    && chmod -R 777 /code/reports

# Copy the rest of the application code
COPY . /code

# Grant permissions so the non-root user in Hugging Face can write temporary files
RUN chmod -R 777 /code

# Hugging Face Spaces exposes port 7860
EXPOSE 7860

# Run the FastAPI app on port 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
