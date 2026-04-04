FROM python:3.11-slim

WORKDIR /app

# Install deps first (cache layer)
COPY api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared + db + email_engine + api code
COPY shared/ /app/shared/
COPY db/ /app/db/
COPY email_engine/ /app/email_engine/
COPY intelligence/ /app/intelligence/
COPY api/ /app/

# Environment
ENV NELSON_MACHINE=vps
ENV NELSON_DATA_DIR=/data
ENV NELSON_LOCAL_DIR=/local
ENV NELSON_CODE_DIR=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8100

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8100"]
