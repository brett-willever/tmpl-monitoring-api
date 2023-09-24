FROM python:3.10-bookworm AS base

RUN apt-get update && \
    apt-get install -y postgresql-client && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN python setup.py sdist && pip install ./dist/*

EXPOSE $API_PORT

CMD ["monitoring-api", "run"]
