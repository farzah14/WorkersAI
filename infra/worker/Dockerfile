FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY apps/worker/pyproject.toml apps/worker/uv.lock ./
RUN uv sync --frozen --no-dev
COPY apps/worker/jobmatch_worker ./jobmatch_worker
CMD ["uv", "run", "--no-dev", "python", "-m", "jobmatch_worker.main"]
