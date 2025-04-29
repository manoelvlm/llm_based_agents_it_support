FROM redis:6

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

# Criar diretórios para logs e garantir permissões
RUN mkdir -p /var/log/redis /var/log/app && \
    chown -R redis:redis /var/log/redis && \
    chmod -R 755 /var/log/redis && \
    chown -R manoel:manoel /var/log/app && \
    chmod -R 755 /var/log/app

# Copiar configurações personalizadas
COPY infrastructure/redis/redis.conf /usr/local/etc/redis/redis.conf
COPY infrastructure/redis/logrotate.conf /etc/logrotate.d/redis

# Copiar script de inicialização
COPY infrastructure/base/start-with-ssh.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/start-with-ssh.sh

# Expor porta SSH
EXPOSE 22

# Substituir o comando CMD original
CMD ["/usr/local/bin/start-with-ssh.sh", "redis-server", "/usr/local/etc/redis/redis.conf"]
