# Shared image for the ingest and model services (they differ only by command).
FROM python:3.12-slim AS build
WORKDIR /build
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir build && python -m build --wheel --outdir /wheels

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 pmq
# The fitted model artifact (a small JSON file) ships inside the image.
COPY --chown=pmq:pmq models /home/pmq/models
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels
USER pmq
WORKDIR /home/pmq
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import pmq" || exit 1
CMD ["python", "-c", "import pmq; print('pmq', pmq.__version__)"]
