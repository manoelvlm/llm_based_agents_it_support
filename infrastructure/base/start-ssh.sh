#!/bin/bash

# Iniciar o servidor SSH em background
/usr/sbin/sshd

# Se houver um comando passado, executá-lo
if [ $# -gt 0 ]; then
  exec "$@"
else
  # Caso contrário, manter o container rodando
  echo "SSH server is running. Use 'docker exec' to interact with this container."
  tail -f /dev/null
fi
