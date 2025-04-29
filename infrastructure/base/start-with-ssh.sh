#!/bin/bash
set -e

# Iniciar o serviço SSH
service ssh start
status=$?
if [ $status -ne 0 ]; then
    echo "Falha ao iniciar o serviço SSH: $status"
    exit $status
fi

echo "Serviço SSH iniciado com sucesso"

# Garantir que os diretórios de log existam com permissões corretas
if [ -d "/var/log/postgres" ]; then
  chown -R postgres:postgres /var/log/postgres
fi

if [ -d "/var/log/redis" ]; then
  chown -R redis:redis /var/log/redis
fi

if [ -d "/var/log/rabbitmq" ]; then
  chown -R rabbitmq:rabbitmq /var/log/rabbitmq
fi

# Garantir que o diretório de logs da aplicação exista
mkdir -p /var/log/app
chown -R manoel:manoel /var/log/app

# Iniciar serviço de log se disponível
if command -v rsyslogd &> /dev/null; then
  rsyslogd
fi

# Iniciar logrotate diariamente em background se disponível
if command -v logrotate &> /dev/null; then
  (
    while true; do
      logrotate /etc/logrotate.conf --state /var/lib/logrotate/status
      sleep 86400 # 24 horas
    done
  ) &
fi

# Exibir mensagem informando que os logs estão configurados
echo "Log collection is configured and active."
echo "Logs are stored in service-specific directories under /var/log/"

# Verificar usuário postgres
if id postgres &>/dev/null; then
    echo "Usuário postgres existe no sistema"
else
    echo "AVISO: Usuário postgres não encontrado no sistema"
fi

# Executar o comando principal passado como argumento
echo "Iniciando PostgreSQL..."
exec "$@"
