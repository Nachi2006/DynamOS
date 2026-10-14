FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 procps && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY workload.py /app/workload.py
ENTRYPOINT ["python3","/app/workload.py"]
CMD ["cpu"]
