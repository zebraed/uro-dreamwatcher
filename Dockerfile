FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml .
COPY README.md .
COPY requirements.txt .

COPY dreamwatcher ./dreamwatcher

RUN pip install --no-cache-dir .

ENTRYPOINT ["python", "-m", "dreamwatcher.main"]
