FROM python:3.11-slim

WORKDIR /app

# Install required OS packages - enhanced with packages needed for simulations
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    iproute2 \
    stress-ng \
    procps \
    net-tools \
    iputils-ping \
    postgresql-client \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Create directory structure
RUN mkdir -p /app/simulations

# Copy requirements file
COPY services/failure_simulation/requirements.txt .

# Install Python dependencies - update to include psycopg2 for DB simulations
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install psycopg2-binary

# Copy controller and simulation scripts
COPY services/failure_simulation/failure_controller.py .
COPY services/failure_simulation/simulations/ ./simulations/

# Create a startup script to ensure container has all tools
RUN echo '#!/bin/bash' > /app/entrypoint.sh \
    && echo 'echo "Checking for required tools..."' >> /app/entrypoint.sh \
    && echo 'if ! command -v tc &> /dev/null; then apt-get update && apt-get install -y iproute2; fi' >> /app/entrypoint.sh \
    && echo 'if ! command -v stress-ng &> /dev/null; then apt-get update && apt-get install -y stress-ng; fi' >> /app/entrypoint.sh \
    && echo 'python failure_controller.py' >> /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

EXPOSE 5010

CMD ["/app/entrypoint.sh"]