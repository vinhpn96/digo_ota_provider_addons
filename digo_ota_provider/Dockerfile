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
        libglib2.0-dev \
        apt install python3-pip \
    && pip3 install "python-matter-server"

COPY scripts /root
COPY chip-ota-provider-app /root
COPY client_controller.py /root
RUN chmod a+x /root/run.sh
CMD [ "/root/run.sh" ]
