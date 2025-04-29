#!/bin/bash
set -e

# Criar banco de dados users_db se não existir
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE IF NOT EXISTS users_db;
    \c users_db
    CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
EOSQL

# Configurar usuário postgres para ter acesso via socket Unix
cat >> /var/lib/postgresql/data/pg_hba.conf <<-EOF
# Permitir acesso sem senha para usuário postgres
local   all             postgres                                trust
host    all             postgres        127.0.0.1/32            trust
host    all             postgres        ::1/128                 trust
host    all             postgres        0.0.0.0/0               trust
EOF

echo "Configuração do PostgreSQL e usuário postgres realizada com sucesso"
