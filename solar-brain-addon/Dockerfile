ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.21
FROM ${BUILD_FROM}

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Home Assistant base images are Alpine and ship NO Python.
# Install it explicitly; --break-system-packages is the standard add-on
# pattern for a single-purpose container (avoids PEP 668 refusal).
RUN apk add --no-cache python3 py3-pip

WORKDIR /usr/src/solar-brain

COPY requirements.txt ./
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY app/ ./app/
COPY run.sh /run.sh
# sed guards against CRLF line endings from Windows git checkouts
RUN sed -i 's/\r$//' /run.sh && chmod a+x /run.sh

EXPOSE 8099

CMD ["/run.sh"]
