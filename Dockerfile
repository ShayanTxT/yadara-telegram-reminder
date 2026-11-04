FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN pip install --no-cache-dir tzdata
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY yadara ./yadara
RUN useradd -m app && mkdir -p /app/data && chown app:app /app/data
USER app
CMD ["python", "-m", "yadara"]
