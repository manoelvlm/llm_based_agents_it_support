#!/bin/bash

# Script para verificar e corrigir permissões de arquivos de log

LOG_DIRS=("/var/log/app" "/app" "/app/logs")
LOG_FILES=(
  "/var/log/app/application.log"
  "/var/log/app/errors.log"
  "/var/log/app/access.log"
  "/app/app.log"
  "/app/error.log"
  "/app/access.log"
)

echo "Verificando e corrigindo permissões de diretórios de log..."
for dir in "${LOG_DIRS[@]}"; do
  if [ -d "$dir" ]; then
    echo "Diretório $dir existe, ajustando permissões..."
    chmod -R 755 "$dir"
  else
    echo "Criando diretório $dir..."
    mkdir -p "$dir"
    chmod -R 755 "$dir"
  fi
done

echo "Verificando e corrigindo permissões de arquivos de log..."
for file in "${LOG_FILES[@]}"; do
  if [ -f "$file" ]; then
    echo "Arquivo $file existe, ajustando permissões..."
    chmod 666 "$file"
  else
    echo "Criando arquivo $file..."
    touch "$file"
    chmod 666 "$file"
  fi
done

echo "Verificação concluída."
echo "Estado atual dos arquivos de log:"
for file in "${LOG_FILES[@]}"; do
  if [ -f "$file" ]; then
    size=$(du -h "$file" | cut -f1)
    perms=$(ls -la "$file" | awk '{print $1}')
    echo "$file: $perms, tamanho: $size"
  else
    echo "$file: não existe!"
  fi
done
