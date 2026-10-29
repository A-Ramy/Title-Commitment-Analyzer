# Title Agent engine (v2) for Google Cloud Run: the Python review engine behind title.totalchb.com.
# Built from GitHub by .github/workflows/deploy-engine.yml. The Streamlit app does not use this file.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /srv

COPY engine/requirements.txt engine/requirements.txt
RUN pip install -r engine/requirements.txt

COPY titleagent titleagent
COPY engine engine
COPY assets assets

# Cloud Run sets PORT; one worker with threads: reviews wait on the AI, not the CPU
RUN useradd --create-home --uid 10001 agent
USER agent
CMD exec uvicorn engine.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --timeout-keep-alive 75
