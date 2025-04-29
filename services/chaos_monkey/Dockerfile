FROM python:3.11-slim

WORKDIR /app

# Add healthcheck capability
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies with specific versions for stability
RUN pip install --upgrade pip
COPY services/chaos_monkey/requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY services/chaos_monkey/chaos_monkey.py .

# Add healthcheck script to ensure chaos monkey is running
RUN echo '#!/bin/sh' > /app/healthcheck.sh \
    && echo 'ps aux | grep "python chaos_monkey.py" | grep -v grep > /dev/null' >> /app/healthcheck.sh \
    && echo 'if [ $? -ne 0 ]; then exit 1; fi' >> /app/healthcheck.sh \
    && echo 'exit 0' >> /app/healthcheck.sh \
    && chmod +x /app/healthcheck.sh

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD ["/app/healthcheck.sh"]

CMD [ "python", "chaos_monkey.py" ]