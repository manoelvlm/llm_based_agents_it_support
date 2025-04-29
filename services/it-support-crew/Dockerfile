FROM python:3.11-slim

WORKDIR /app

ENV OTEL_SDK_DISABLED=true

RUN apt-get update && apt-get install -y \
    openssh-client \
    net-tools \
    iputils-ping \
    iproute2 \
    dnsutils \
    traceroute \
    tcpdump \
    telnet \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /root/.ssh && \
    ssh-keygen -t rsa -b 4096 -f /root/.ssh/id_rsa -N "" && \
    touch /root/.ssh/known_hosts

COPY services/it-support-crew/ssh_config /root/.ssh/config

RUN pip install --upgrade pip
COPY services/it-support-crew/requirements.txt .
RUN pip install -r requirements.txt

COPY services/it-support-crew/crew.py .

RUN mkdir -p tools/
COPY services/it-support-crew/tools/__init__.py tools/
COPY services/it-support-crew/tools/user_service_metrics.py tools/
COPY services/it-support-crew/tools/ssh_diagnostic_tool.py tools/

EXPOSE 5002

CMD ["python", "crew.py"]
