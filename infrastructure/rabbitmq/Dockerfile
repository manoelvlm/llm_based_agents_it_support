FROM rabbitmq:3-management

# Instalar SSH e utilitários
RUN apt-get update && apt-get install -y \
    openssh-server \
    sudo \
    procps \
    net-tools \
    iputils-ping \
    curl \
    wget \
    vim \
    logrotate \
    rsyslog \
    erlang-base \
    erlang-asn1 \
    erlang-crypto \
    erlang-eldap \
    erlang-ftp \
    erlang-inets \
    erlang-mnesia \
    erlang-os-mon \
    erlang-parsetools \
    erlang-public-key \
    erlang-runtime-tools \
    erlang-snmp \
    erlang-ssl \
    erlang-syntax-tools \
    erlang-tftp \
    erlang-tools \
    erlang-xmerl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configurar usuário de diagnóstico com senha
RUN useradd -m -d /home/manoel -s /bin/bash manoel && \
    echo "manoel:Uai6orfGYdKWbif" | chpasswd && \
    adduser manoel sudo && \
    echo "manoel ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/manoel

# Configurar SSH
RUN mkdir -p /var/run/sshd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Criar diretórios para logs e definir permissões
RUN mkdir -p /var/log/rabbitmq /var/log/app && \
    chown -R rabbitmq:rabbitmq /var/log/rabbitmq && \
    chmod -R 755 /var/log/rabbitmq && \
    chown -R manoel:manoel /var/log/app && \
    chmod -R 755 /var/log/app

# Configurar RabbitMQ CLI Tools corretamente
RUN RABBITMQ_DIR=$(dirname $(find / -name rabbitmqctl -type f 2>/dev/null | head -1)) && \
    if [ -n "$RABBITMQ_DIR" ]; then \
    echo "Found RabbitMQ tools in: $RABBITMQ_DIR" && \
    echo "export PATH=$PATH:$RABBITMQ_DIR" >> /etc/bash.bashrc && \
    echo "export PATH=$PATH:$RABBITMQ_DIR" >> /etc/profile && \
    echo "export PATH=$PATH:$RABBITMQ_DIR" >> /home/manoel/.bashrc && \
    for file in $RABBITMQ_DIR/*; do \
    ln -sf $file /usr/local/bin/$(basename $file); \
    done; \
    else \
    echo "RabbitMQ tools directory not found"; \
    fi

# Copiar configurações personalizadas
COPY infrastructure/rabbitmq/rabbitmq.conf /etc/rabbitmq/rabbitmq.conf
COPY infrastructure/rabbitmq/advanced.config /etc/rabbitmq/advanced.config
COPY infrastructure/rabbitmq/logrotate.conf /etc/logrotate.d/rabbitmq

# Copiar script de inicialização personalizado
COPY infrastructure/base/start-with-ssh.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/start-with-ssh.sh

# Expor porta SSH
EXPOSE 22

# Substituir o comando CMD original
CMD ["/usr/local/bin/start-with-ssh.sh", "docker-entrypoint.sh", "rabbitmq-server"]