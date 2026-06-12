ARG BUILD_FROM=python:3.12-slim
FROM ${BUILD_FROM}

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /usr/src/solar-brain

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY run.sh /run.sh
# sed guards against CRLF line endings from Windows git checkouts
RUN sed -i 's/\r$//' /run.sh && chmod a+x /run.sh

EXPOSE 8099

CMD ["/run.sh"]
