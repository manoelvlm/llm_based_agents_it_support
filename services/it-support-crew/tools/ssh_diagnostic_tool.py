import logging
import os
import socket
import time
from typing import Type

import paramiko
import yaml
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SSHDiagnosticToolInput(BaseModel):
    """Input schema for the SSHDiagnosticTool."""

    query: str = Field(
        ...,
        description="Query in format 'server|command' where server is the name from config and command is the command to execute",
    )


class SSHDiagnosticTool(BaseTool):
    name: str = "SSHDiagnosticTool"
    description: str = """
    Tool for executing diagnostic commands via SSH on a server.
    Use this tool to:
    1. Access logs remotely
    2. Execute diagnostic commands on the system
    3. Check processes, resources, and configurations
    
    Input format: "server|command"
    Example: "user-service|ps aux | grep python"
    Available servers: user-service
    """
    args_schema: Type[BaseModel] = SSHDiagnosticToolInput

    def _run(self, query: str) -> str:
        """
        Executes a diagnostic command via SSH on a specific server.

        Args:
            query (str): String in the format "server|command"
                         where server is the name of the server in the configuration
                         and command is the command to be executed.

        Returns:
            str: Result of the command executed via SSH
        """
        try:
            parts = query.split("|", 1)
            if len(parts) != 2:
                return "Error: Incorrect format. Use 'server|command'"

            server_name, command = parts

            # Load server configurations
            # Adjust the path as needed for the local environment
            config_path = "./config/servers.yaml"
            if not os.path.exists(config_path):
                config_path = "/home/manoel/v2_multi_agent_it_support/services/it-support-crew/config/servers.yaml"
                if not os.path.exists(config_path):
                    return "Error: Server configuration file not found"

            with open(config_path, "r") as file:
                config = yaml.safe_load(file)

            servers = config.get("servers", {})
            if server_name not in servers:
                return f"Error: Server '{server_name}' not found in configuration"

            server_config = servers[server_name]

            # For the local environment, we use localhost and the mapped port
            hostname = "localhost"
            port = server_config.get(
                "ssh_port", 2222
            )  # Use ssh_port if set, or default to 2222
            username = server_config["username"]
            password = server_config["password"]

            logger.info(f"Connecting via SSH to {hostname}:{port} with user {username}")

            # Timeouts rigorosos para evitar bloqueios
            connect_timeout = 5  # 5 segundos para conexão
            command_timeout = 8  # 8 segundos para comandos

            # Criar cliente SSH com configurações de timeout rigorosas
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            try:
                logger.info("Iniciando conexão SSH...")
                client.connect(
                    hostname,
                    port=port,
                    username=username,
                    password=password,
                    timeout=connect_timeout,
                    banner_timeout=connect_timeout,
                    auth_timeout=connect_timeout,
                )

                logger.info(f"Executando comando: {command}")

                # Executar comando com timeout explícito
                stdin, stdout, stderr = client.exec_command(
                    command,
                    timeout=command_timeout,
                    # Não alocar um PTY, que pode causar bloqueios
                    get_pty=False,
                )

                # Configurar timeout na leitura - verificando se o método existe antes
                if hasattr(stdout.channel, "settimeout"):
                    stdout.channel.settimeout(command_timeout)
                if hasattr(stderr.channel, "settimeout"):
                    stderr.channel.settimeout(command_timeout)

                # Leitura com tratamento de timeout
                try:
                    output = stdout.read().decode("utf-8", errors="replace")
                except socket.timeout:
                    output = "[Timeout na leitura da saída do comando]"
                except Exception as e:
                    output = f"[Erro ao ler saída: {str(e)}]"

                try:
                    errors = stderr.read().decode("utf-8", errors="replace")
                except socket.timeout:
                    errors = "[Timeout na leitura de erros]"
                except Exception as e:
                    errors = f"[Erro ao ler erros: {str(e)}]"

                # Checar status do canal de maneira segura
                try:
                    # Verifique se o método existe antes de chamá-lo
                    if (
                        hasattr(stdout.channel, "exit_status_ready")
                        and stdout.channel.exit_status_ready()
                    ):
                        exit_status = stdout.channel.recv_exit_status()
                        if exit_status != 0:
                            errors += (
                                f"\n[Comando retornou código de erro: {exit_status}]"
                            )
                except Exception:
                    # Ignora erros ao tentar obter status
                    pass

                # Fechar o canal com segurança
                try:
                    # Somente tente fechar se houver o método
                    if hasattr(stdout.channel, "close"):
                        stdout.channel.close()
                    if hasattr(stderr.channel, "close"):
                        stderr.channel.close()
                except Exception:
                    # Ignora erros ao fechar os canais
                    pass

                # Processar resultado e retornar
                result = output
                if errors and not errors.isspace() and errors.strip():
                    result += f"\nErros: {errors}"

                return result

            except paramiko.SSHException as e:
                return f"Erro SSH: {str(e)}"
            except socket.timeout:
                return "Timeout na operação SSH. O servidor pode estar sobrecarregado."
            except Exception as e:
                return f"Erro executando comando: {str(e)}"
            finally:
                # Garantir que a conexão seja fechada corretamente
                try:
                    client.close()
                    logger.info("Conexão SSH encerrada")
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Erro na ferramenta SSH: {str(e)}")
            return f"Erro na ferramenta SSH: {str(e)}"
