FROM python:3.12.14-slim-trixie@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg=7:7.1.5-0+deb13u1 nodejs ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && echo 'e8a8d46f5225f3062cec7c07fb145d58ae73c603cb740dcd5bad34bfb54e455a  /usr/bin/ffmpeg' | sha256sum -c - \
    && echo 'cefc5f81c0b18429cdbf8fa5a89e1e9c759235e10f93f9b329ff1b2fdff26f46  /usr/bin/ffprobe' | sha256sum -c -
COPY studio/runtime-requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --only-binary=:all: --require-hashes -r /tmp/requirements.lock
WORKDIR /app
COPY opencv-ready /app/opencv-ready
COPY studio /app/studio
COPY Dockerfile /app/Dockerfile
RUN python studio/run.py --check
EXPOSE 8877
USER 10001:10001
CMD ["python", "studio/run.py", "--serve", "--port", "8877", "--data-dir", "/tmp/creator-jobs"]
