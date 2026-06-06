FROM python:3.12-slim
WORKDIR /app
COPY requirement.txt .
RUN pip install --no-cache-dir -r requirement.txt
COPY backend.py index.html favicon.png ./
RUN mkdir -p /app/data
CMD ["uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "8000"]