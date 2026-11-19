FROM python:3.13-slim

WORKDIR /app
COPY src/node.py /app/node.py

EXPOSE 7301
ENTRYPOINT ["python", "/app/node.py"]
