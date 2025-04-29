FROM postgres:13

# Definir variáveis de ambiente para configuração do PostgreSQL
ENV POSTGRES_USER=postgres
ENV POSTGRES_PASSWORD=postgres
ENV POSTGRES_DB=postgres

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

# Criar diretórios para logs e garantir permissões corretas
RUN mkdir -p /var/log/postgres /var/log/app && \
    chown -R postgres:postgres /var/log/postgres && \
    chmod -R 755 /var/log/postgres && \
    chown -R manoel:manoel /var/log/app && \
    chmod -R 755 /var/log/app

# Copiar configurações personalizadas
COPY infrastructure/postgres/postgresql.conf /etc/postgresql/postgresql.conf
COPY infrastructure/postgres/logrotate.conf /etc/logrotate.d/postgres
COPY infrastructure/postgres/rsyslog.conf /etc/rsyslog.d/postgres.conf
COPY infrastructure/postgres/init-postgres.sh /docker-entrypoint-initdb.d/

# Modificar a configuração do PostgreSQL para usuário postgres
RUN mkdir -p /docker-entrypoint-initdb.d/
COPY infrastructure/postgres/setup-postgres-user.sh /docker-entrypoint-initdb.d/
RUN chmod +x /docker-entrypoint-initdb.d/setup-postgres-user.sh

# Copiar script de inicialização
COPY infrastructure/base/start-with-ssh.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/start-with-ssh.sh

# Expor porta SSH
EXPOSE 22

# Substituir o comando CMD original e usar nossa configuração personalizada
CMD ["/usr/local/bin/start-with-ssh.sh", "docker-entrypoint.sh", "postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]
