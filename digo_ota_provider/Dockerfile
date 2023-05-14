# ARG BUILD_FROM
# FROM ${BUILD_FROM}
FROM ubuntu:22.04

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
WORKDIR /root
RUN \
    set -x \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        libglib2.0-dev

COPY scripts /root
COPY chip-ota-provider-app /root
COPY client_controller.py /root
RUN chmod a+x /root/run.sh
CMD [ "/root/run.sh" ]
