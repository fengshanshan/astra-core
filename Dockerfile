FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1

WORKDIR /app

# Some dependencies may need compilation headers (kept minimal)
RUN apt-get update \
  && apt-get install -y --no-install-recommends gcc build-essential \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

# 国内构建（阿里云 ECS）时直连 PyPI CDN 易超时；可改 ARG 换镜像源
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ARG PIP_TRUSTED_HOST=mirrors.aliyun.com
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir \
  --default-timeout=300 \
  -i "${PIP_INDEX_URL}" \
  --trusted-host "${PIP_TRUSTED_HOST}" \
  -r /app/requirements.txt

# Copy the whole app (includes frontend/ and ephemeris/)
COPY . /app

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PORT=8000
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]

