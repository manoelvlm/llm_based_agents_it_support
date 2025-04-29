FROM ubuntu:22.04

WORKDIR /app

# Evitar interações durante a instalação de pacotes
ENV DEBIAN_FRONTEND=noninteractive

# Configure Python and Prometheus directory
RUN mkdir -p /tmp/prometheus && chmod 777 /tmp/prometheus
ENV PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus

# Install only essential tools for microservice troubleshooting
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    gcc \
    sudo \
    libpq-dev \
    openssh-server \
    procps \
    net-tools \
    curl \
    wget \
    lsof \
    netcat \
    tcpdump \
    rsyslog \
    logrotate \
    ca-certificates \
    postgresql-client \
    iputils-ping \
    jq \
    vim \
    python3-psutil \
    htop \
    && rm -rf /var/lib/apt/lists/*

# Install stress-ng with controlled options
RUN apt-get update && apt-get install -y stress-ng && rm -rf /var/lib/apt/lists/*

# Configure Python as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1

# Install node_exporter for container metrics
RUN mkdir -p /opt/node_exporter && \
    curl -L https://github.com/prometheus/node_exporter/releases/download/v1.6.1/node_exporter-1.6.1.linux-amd64.tar.gz -o /tmp/node_exporter.tar.gz && \
    tar -xzf /tmp/node_exporter.tar.gz -C /opt/node_exporter --strip-components=1 && \
    rm /tmp/node_exporter.tar.gz

# Configure SSH for remote access
RUN mkdir -p /var/run/sshd
RUN useradd -m -s /bin/bash manoel && echo "manoel:Uai6orfGYdKWbif" | chpasswd
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config

# Configure privileged access - enhanced root permissions
RUN mkdir -p /etc/sudoers.d
RUN usermod -aG sudo manoel
RUN echo "manoel ALL=(ALL:ALL) NOPASSWD: ALL" > /etc/sudoers.d/manoel
RUN chmod 0440 /etc/sudoers.d/manoel
RUN echo "%sudo ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Configure logging directories with proper permissions - simplified approach
RUN mkdir -p /var/log/app /var/log/diagnostics /app/logs
RUN touch /var/log/app/application.log /var/log/app/errors.log /var/log/app/access.log /app/app.log /app/error.log /app/access.log
RUN chmod -R 777 /var/log/app /var/log/diagnostics /app/logs
RUN chmod 666 /var/log/app/application.log /var/log/app/errors.log /var/log/app/access.log /app/app.log /app/error.log /app/access.log

# Copy the log permission fix script
COPY services/user-service/scripts/fix_log_permissions.sh /app/fix_log_permissions.sh
RUN chmod +x /app/fix_log_permissions.sh

# Enhanced rsyslog configuration
RUN echo 'local0.*                             /var/log/app/application.log' > /etc/rsyslog.d/app-logging.conf
RUN echo 'local1.*                             /var/log/app/errors.log' >> /etc/rsyslog.d/app-logging.conf
RUN echo 'local2.*                             /var/log/app/access.log' >> /etc/rsyslog.d/app-logging.conf
RUN echo 'input(type="imfile" File="/app/app.log" Tag="python-app:" Severity="info" Facility="local0")' >> /etc/rsyslog.d/app-logging.conf
RUN echo 'input(type="imfile" File="/app/access.log" Tag="python-app-access:" Severity="info" Facility="local2")' >> /etc/rsyslog.d/app-logging.conf
RUN echo 'input(type="imfile" File="/app/error.log" Tag="python-app-error:" Severity="error" Facility="local1")' >> /etc/rsyslog.d/app-logging.conf

# Add log rotation configuration
RUN echo '/var/log/app/*.log {' > /etc/logrotate.d/app-logs
RUN echo '    daily' >> /etc/logrotate.d/app-logs
RUN echo '    rotate 7' >> /etc/logrotate.d/app-logs
RUN echo '    missingok' >> /etc/logrotate.d/app-logs
RUN echo '    notifempty' >> /etc/logrotate.d/app-logs
RUN echo '    compress' >> /etc/logrotate.d/app-logs
RUN echo '    delaycompress' >> /etc/logrotate.d/app-logs
RUN echo '    create 0644 root root' >> /etc/logrotate.d/app-logs
RUN echo '}' >> /etc/logrotate.d/app-logs

# Create Python logger configuration file 
RUN echo '# Python logging configuration' > /app/logging_config.py
RUN echo 'import logging' >> /app/logging_config.py
RUN echo 'import logging.handlers' >> /app/logging_config.py
RUN echo 'import os' >> /app/logging_config.py
RUN echo '' >> /app/logging_config.py
RUN echo 'def setup_logging():' >> /app/logging_config.py
RUN echo '    # Create loggers' >> /app/logging_config.py
RUN echo '    app_logger = logging.getLogger("app")' >> /app/logging_config.py
RUN echo '    access_logger = logging.getLogger("access")' >> /app/logging_config.py
RUN echo '    error_logger = logging.getLogger("error")' >> /app/logging_config.py
RUN echo '' >> /app/logging_config.py
RUN echo '    # Set levels' >> /app/logging_config.py
RUN echo '    app_logger.setLevel(logging.INFO)' >> /app/logging_config.py
RUN echo '    access_logger.setLevel(logging.INFO)' >> /app/logging_config.py
RUN echo '    error_logger.setLevel(logging.ERROR)' >> /app/logging_config.py
RUN echo '' >> /app/logging_config.py
RUN echo '    # Create handlers' >> /app/logging_config.py
RUN echo '    app_handler = logging.FileHandler("/app/app.log")' >> /app/logging_config.py
RUN echo '    access_handler = logging.FileHandler("/app/access.log")' >> /app/logging_config.py
RUN echo '    error_handler = logging.FileHandler("/app/error.log")' >> /app/logging_config.py
RUN echo '' >> /app/logging_config.py
RUN echo '    # Create formatters' >> /app/logging_config.py
RUN echo '    formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")' >> /app/logging_config.py
RUN echo '    access_formatter = logging.Formatter("[%(asctime)s] ACCESS - %(message)s")' >> /app/logging_config.py
RUN echo '' >> /app/logging_config.py
RUN echo '    # Set formatters' >> /app/logging_config.py
RUN echo '    app_handler.setFormatter(formatter)' >> /app/logging_config.py
RUN echo '    access_handler.setFormatter(access_formatter)' >> /app/logging_config.py
RUN echo '    error_handler.setFormatter(formatter)' >> /app/logging_config.py
RUN echo '' >> /app/logging_config.py
RUN echo '    # Add handlers' >> /app/logging_config.py
RUN echo '    app_logger.addHandler(app_handler)' >> /app/logging_config.py
RUN echo '    access_logger.addHandler(access_handler)' >> /app/logging_config.py
RUN echo '    error_logger.addHandler(error_handler)' >> /app/logging_config.py
RUN echo '' >> /app/logging_config.py
RUN echo '    return app_logger, access_logger, error_logger' >> /app/logging_config.py

# Install Python packages
RUN pip3 install --upgrade pip
COPY services/user-service/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt \
    # Add psycopg2 for DB connection exhaustion simulation
    && pip3 install psycopg2-binary \
    # Add additional Python monitoring packages
    && pip3 install structlog python-json-logger prometheus-flask-exporter

# Copy application code
COPY services/user-service/user_service.py .

# Create a wrapper script to start all services
RUN echo '#!/bin/bash' > /app/start.sh
RUN echo 'rsyslogd' >> /app/start.sh
RUN echo '/usr/sbin/sshd' >> /app/start.sh
RUN echo '/opt/node_exporter/node_exporter --web.listen-address=:9100 &' >> /app/start.sh
RUN echo 'cron' >> /app/start.sh
# Run the script to ensure all log files are writable
RUN echo '/app/fix_log_permissions.sh' >> /app/start.sh
# Start the application with proper logging
RUN echo 'python3 user_service.py 2>&1 | tee -a /app/app.log' >> /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 5000 22 9100

# Start services with the wrapper script
CMD ["/app/start.sh"]