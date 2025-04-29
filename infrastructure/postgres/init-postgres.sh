#!/bin/bash
set -e

# Garantir que o usuário postgres exista no banco de dados
psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}" --dbname "${POSTGRES_DB:-postgres}" <<-EOSQL
    -- Garantir que o role postgres exista e tenha privilégios de superusuário
    DO \$\$
    BEGIN
        IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'postgres') THEN
            ALTER ROLE postgres WITH SUPERUSER LOGIN;
        ELSE
            CREATE ROLE postgres WITH SUPERUSER LOGIN;
        END IF;
    END \$\$;
    
    -- Confirmar a criação do role (para debugging)
    \echo 'Status do role postgres:'
    SELECT rolname, rolsuper FROM pg_roles WHERE rolname = 'postgres';
    
    -- Criar a extensão pg_stat_statements se não existir
    CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
EOSQL

# Garantir permissões para o diretório de dados
chown -R postgres:postgres /var/lib/postgresql/data
chmod 700 /var/lib/postgresql/data

# Configurar pg_hba.conf para permitir conexões do postgres sem senha
cat > /var/lib/postgresql/data/pg_hba.conf <<-EOF
# Configuração de acesso ao PostgreSQL
# "local" é para conexões Unix domain socket
local   all             all                                     trust
# IPv4 local connections:
host    all             all             127.0.0.1/32            trust
# IPv6 local connections:
host    all             all             ::1/128                 trust
# Permitir conexões de qualquer lugar (ajuste conforme necessidade de segurança)
host    all             all             0.0.0.0/0               trust
EOF

echo "Configuração de acesso PostgreSQL atualizada e role postgres verificado"
