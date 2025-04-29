# simulations/db_connection_exhaustion_simulation.py
import logging
import time

logger = logging.getLogger("chaos-engineering.db_connection_exhaustion")


def implement(container, intensity):
    """
    Implement database connection exhaustion simulation on the target container.

    Args:
        container: Docker container object
        intensity: Level of intensity (low, medium, high)
    """
    logger.info(
        f"Implementing database connection exhaustion with {intensity} intensity"
    )

    # IMPORTANTE: Aumentar drasticamente o número de conexões
    connections = 50  # Default para low intensity
    if intensity == "medium":
        connections = 100
    elif intensity == "high":
        connections = 200  # Número muito elevado para estressar o pool

    logger.info(f"Opening {connections} database connections")

    # Check if Python is installed
    check_result = container.exec_run("which python3")
    if check_result.exit_code != 0:
        logger.info("Python3 not found, installing...")
        install_cmd = "apt-get update && apt-get install -y python3 python3-pip"
        install_result = container.exec_run(install_cmd)
        logger.debug(f"Python installation result: {install_result.exit_code}")

        if install_result.exit_code != 0:
            logger.error(
                f"Failed to install Python3: {install_result.output.decode('utf-8', errors='ignore')}"
            )
            raise Exception("Failed to install Python3")

    # Install psycopg2 if needed - assegurar instalação sem erros
    container.exec_run("apt-get update && apt-get install -y libpq-dev gcc")
    container.exec_run("pip3 install --upgrade pip")
    container.exec_run("pip3 install psycopg2-binary --no-cache-dir")

    # Script mais agressivo com execução de queries contínua
    script = f"""
import os
import time
import psycopg2
import threading
import random
import signal
import sys

# Configurações do banco de dados
db_host = os.getenv('DATABASE_HOST', 'db')
db_port = os.getenv('DATABASE_PORT', '5432')
db_name = os.getenv('DATABASE_NAME', 'users_db')
db_user = os.getenv('DATABASE_USER', 'user')
db_pass = os.getenv('DATABASE_PASSWORD', 'password')

# Armazenar conexões e cursores ativos
active_connections = []
stop_event = threading.Event()

def execute_continuous_queries(conn, conn_id):
    cursor = conn.cursor()
    
    # Lista de queries para executar - inclui queries pesadas
    queries = [
        "SELECT * FROM pg_stat_activity",
        "SELECT * FROM pg_stat_database",
        "SELECT * FROM information_schema.tables",
        "SELECT * FROM information_schema.columns",
        "SELECT * FROM \"user\"",
        "SELECT * FROM \"user\" ORDER BY id",
        "SELECT COUNT(*) FROM \"user\" GROUP BY username",
        "SELECT pg_sleep(0.1)",  # Query que bloqueia por 100ms
        "BEGIN; SELECT * FROM \"user\" FOR UPDATE", # Bloqueio de linha
    ]
    
    long_queries = [
        "SELECT pg_sleep(1)",  # Query que bloqueia por 1s
        "SELECT pg_sleep(2)",  # Query que bloqueia por 2s
        "SELECT * FROM information_schema.columns CROSS JOIN information_schema.tables",  # Query pesada
    ]
    
    try:
        while not stop_event.is_set():
            try:
                # Escolhe uma query aleatória
                if random.random() < 0.2 and conn_id % 5 == 0:  # 20% de chance para conexões específicas
                    query = random.choice(long_queries)
                else:
                    query = random.choice(queries)
                
                print(f"Conn {{conn_id}}: Executing {{query[:30]}}")
                cursor.execute(query)
                
                # Para algumas queries, recupera todos os resultados para consumir mais memória
                if not query.startswith("SELECT pg_sleep") and not query.startswith("BEGIN"):
                    results = cursor.fetchall()
                    # Manter resultados em memória para aumentar consumo
                    if random.random() < 0.3:  # 30% de chance
                        # Leak de memória proposital
                        global all_results
                        try:
                            all_results.append(results)
                        except:
                            all_results = [results]
                
                # Adiciona um pequeno delay entre queries (não muito para ser agressivo)
                time.sleep(random.uniform(0.05, 0.2))
                
                # Ocasionalmente faz um commit ou rollback (10% de chance)
                if random.random() < 0.1:
                    if random.random() < 0.5:
                        conn.commit()
                        print(f"Conn {{conn_id}}: Transaction committed")
                    else:
                        conn.rollback()
                        print(f"Conn {{conn_id}}: Transaction rolled back")
                        
            except Exception as e:
                print(f"Conn {{conn_id}} query error: {{e}}")
                try:
                    # Tentar recuperar a conexão
                    conn.rollback()
                except:
                    # Se não conseguir recuperar, pular para a próxima iteração
                    pass
                time.sleep(0.5)
                    
    except Exception as e:
        print(f"Thread {{conn_id}} failed: {{e}}")
    finally:
        try:
            cursor.close()
        except:
            pass


def create_connections(total_connections):
    print(f"Starting DB connection exhaustion with {{total_connections}} connections")
    
    for i in range(total_connections):
        try:
            # Configurar uma nova conexão
            conn = psycopg2.connect(
                host=db_host,
                port=db_port,
                dbname=db_name,
                user=db_user,
                password=db_pass
            )
            
            # Desativar autocommit para criar transações explícitas
            conn.autocommit = False
            
            # Adicionar à lista de conexões ativas
            active_connections.append(conn)
            
            # Iniciar thread para executar queries contínuas
            thread = threading.Thread(
                target=execute_continuous_queries,
                args=(conn, i)
            )
            thread.daemon = True
            thread.start()
            
            print(f"Connection {{i+1}} established")
            
            # Pequeno delay entre criação de conexões para evitar sobrecarga imediata
            time.sleep(0.05)
            
        except Exception as e:
            print(f"Failed to create connection {{i+1}}: {{e}}")
    
    print(f"Established {{len(active_connections)}} out of {{total_connections}} connections")


def cleanup_handler(signum, frame):
    print("Recebido sinal de terminação, limpando conexões...")
    stop_event.set()
    
    for conn in active_connections:
        try:
            conn.close()
        except:
            pass
    
    print("Todas as conexões fechadas")
    sys.exit(0)


# Configurar manipuladores de sinal
signal.signal(signal.SIGTERM, cleanup_handler)
signal.signal(signal.SIGINT, cleanup_handler)

# Iniciar criação de conexões
create_connections({connections})

# Manter o processo principal em execução
try:
    while True:
        active = sum(1 for conn in active_connections if not conn.closed)
        print(f"Status: {{active}} active connections")
        time.sleep(5)
        
        # Adicionar novas conexões se algumas forem fechadas pelo servidor
        if active < {connections} and not stop_event.is_set():
            try:
                to_add = min({connections} - active, 10)  # Adiciona até 10 por vez
                create_connections(to_add)
            except:
                pass
            
except KeyboardInterrupt:
    cleanup_handler(None, None)
"""

    # Write script to a file in the container
    container.exec_run("bash -c 'mkdir -p /tmp/simulations'")
    container.exec_run(
        f"bash -c 'cat > /tmp/simulations/db_exhaust.py << \"EOL\"\n{script}\nEOL'"
    )

    # Run the script in the background with higher priority
    run_cmd = (
        "cd /tmp/simulations && python3 db_exhaust.py > db_exhaust.log 2>&1 & echo $!"
    )
    result = container.exec_run(f"bash -c '{run_cmd}'")

    # Store PID for later cleanup
    pid = result.output.decode("utf-8").strip()
    logger.info(f"Started DB connection exhaustion process with PID: {pid}")
    container.exec_run(f"bash -c 'echo {pid} > /tmp/db_exhaust.pid'")

    # Verificar se o script está rodando após 2 segundos
    time.sleep(2)
    check_cmd = f"ps -p {pid} || (cat /tmp/simulations/db_exhaust.log && echo 'Process failed to start')"
    container.exec_run(f"bash -c '{check_cmd}'")


def recover(container):
    """
    Recover from database connection exhaustion simulation.

    Args:
        container: Docker container object
    """
    logger.info("Recovering database connections in container")

    # Kill the Python script and all related processes
    container.exec_run(
        "bash -c 'if [ -f /tmp/db_exhaust.pid ]; then pid=$(cat /tmp/db_exhaust.pid); kill -9 $pid 2>/dev/null || true; pkill -P $pid 2>/dev/null || true; rm /tmp/db_exhaust.pid; fi'"
    )

    # Garante que todos os processos python relacionados sejam mortos
    container.exec_run("pkill -f db_exhaust.py || true")
    container.exec_run("pkill -f 'python.*db_exhaust' || true")

    # Exibe log para diagnóstico
    container.exec_run("tail -n 20 /tmp/simulations/db_exhaust.log || true")

    logger.debug("DB connection recovery completed")
