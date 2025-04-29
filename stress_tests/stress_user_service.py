import json
import logging
import os
import random
import signal
import string
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

# Configuração de logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("stress-test")

# Configurações
BASE_URL = "http://localhost:5001"
NUM_THREADS = 1
REQUEST_TIMEOUT = 2
MIN_DELAY = 0.01
MAX_DELAY = 0.05
running = True
access_tokens = []


# Função para gerar string aleatória
def random_string(length):
    letters = string.ascii_letters + string.digits
    return "".join(random.choice(letters) for _ in range(length))


# Função para registrar usuários intensivamente
def stress_register():
    while running:
        try:
            username = f"user_{random_string(8)}"
            data = {
                "username": username,
                "password": "password123",
                "email": f"{username}@example.com",
                "profile": {
                    "first_name": random_string(8),
                    "last_name": random_string(8),
                    "bio": random_string(500),  # Bio grande para aumentar payload
                },
            }
            response = requests.post(
                f"{BASE_URL}/register", json=data, timeout=REQUEST_TIMEOUT
            )

            if response.status_code == 201:
                logger.info(f"Registered user: {username}")
                # Tente fazer login imediatamente após o registro
                login_response = requests.post(
                    f"{BASE_URL}/login",
                    json={"username": username, "password": "password123"},
                    timeout=REQUEST_TIMEOUT,
                )
                if login_response.status_code == 200:
                    token = login_response.json().get("access_token")
                    if token:
                        access_tokens.append(token)
                        if (
                            len(access_tokens) > 1000
                        ):  # Manter lista em tamanho razoável
                            access_tokens.pop(0)
            else:
                logger.warning(f"Failed to register: {response.status_code}")

            # Delay mínimo entre requisições
            time.sleep(MIN_DELAY)

        except Exception as e:
            logger.error(f"Error in register stress: {str(e)}")
            time.sleep(0.1)  # Breve pausa em caso de erro


# Função para estressar o endpoint de perfil
def stress_profile():
    while running:
        try:
            if not access_tokens:
                time.sleep(0.5)
                continue

            token = random.choice(access_tokens)
            headers = {"Authorization": f"Bearer {token}"}

            # 70% GET, 30% PUT para atualização
            if random.random() < 0.7:
                # GET profile
                response = requests.get(
                    f"{BASE_URL}/profile", headers=headers, timeout=REQUEST_TIMEOUT
                )
            else:
                # PUT profile (update)
                data = {
                    "first_name": random_string(8),
                    "last_name": random_string(8),
                    "bio": random_string(500),
                    "extra_data": {
                        "field1": random_string(100),
                        "field2": random_string(100),
                        "field3": random_string(100),
                    },
                }
                response = requests.put(
                    f"{BASE_URL}/profile",
                    headers=headers,
                    json=data,
                    timeout=REQUEST_TIMEOUT,
                )

            if 200 <= response.status_code < 300:
                logger.debug(f"Profile request successful: {response.status_code}")
            else:
                logger.warning(f"Profile request failed: {response.status_code}")

            # Delay mínimo entre requisições
            time.sleep(MIN_DELAY)

        except Exception as e:
            logger.error(f"Error in profile stress: {str(e)}")
            time.sleep(0.1)


# Função para estressar listagem de usuários
def stress_users_list():
    while running:
        try:
            # Solicitar páginas grandes de usuários
            page = random.randint(1, 10)
            per_page = random.choice([50, 100, 200, 500, 1000])

            response = requests.get(
                f"{BASE_URL}/users",
                params={"page": page, "per_page": per_page},
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code == 200:
                users = response.json().get("users", [])
                logger.info(
                    f"Listed {len(users)} users (page {page}, per_page {per_page})"
                )
            else:
                logger.warning(f"Failed to list users: {response.status_code}")

            # Delay mínimo entre requisições
            time.sleep(MIN_DELAY)

        except Exception as e:
            logger.error(f"Error in users list stress: {str(e)}")
            time.sleep(0.1)


# Função para testar saúde do serviço
def stress_health():
    while running:
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                logger.debug("Health check passed")
            else:
                logger.warning(f"Health check failed: {response.status_code}")

            # Delay curto entre health checks
            time.sleep(0.2)

        except Exception as e:
            logger.error(f"Error in health check: {str(e)}")
            time.sleep(0.5)


# Função para pressionar a memória
def stress_memory():
    while running:
        try:
            # Gerar payload grande (5-10MB)
            size_kb = random.randint(5000, 10000)

            # Criar dados aninhados para aumentar processamento
            payload = {
                "data": random_string(size_kb * 1024 // 2),
                "nested": {
                    "level1": {"level2": {"level3": random_string(size_kb * 1024 // 2)}}
                },
            }

            response = requests.post(
                f"{BASE_URL}/debug/echo",
                json=payload,
                timeout=REQUEST_TIMEOUT * 2,  # Timeout maior para payloads grandes
            )

            if response.status_code == 200:
                logger.info(f"Memory stress: sent {size_kb}KB payload")
            else:
                logger.warning(f"Memory stress failed: {response.status_code}")

            # Delay moderado entre requisições de memória
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"Error in memory stress: {str(e)}")
            time.sleep(0.5)


# Handler para sinal de interrupção
def signal_handler(sig, frame):
    global running
    logger.info("Received interrupt signal. Shutting down...")
    running = False
    # Forçar término após 5 segundos se as threads não terminarem graciosamente
    threading.Timer(5.0, lambda: os._exit(0)).start()


def main():
    global running
    signal.signal(signal.SIGINT, signal_handler)

    logger.info(
        f"Starting simplified high-intensity stress test with {NUM_THREADS} threads"
    )
    logger.info("Press Ctrl+C to stop")

    # Distribuição de threads por tipo de estresse
    register_threads = NUM_THREADS // 5  # 20% para registro
    profile_threads = NUM_THREADS // 5 * 2  # 40% para perfil
    users_threads = NUM_THREADS // 5  # 20% para listagem
    health_threads = NUM_THREADS // 10  # 10% para health
    memory_threads = NUM_THREADS // 10  # 10% para pressão de memória

    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = []

        # Submeter tarefas para cada tipo de estresse
        for _ in range(register_threads):
            futures.append(executor.submit(stress_register))

        for _ in range(profile_threads):
            futures.append(executor.submit(stress_profile))

        for _ in range(users_threads):
            futures.append(executor.submit(stress_users_list))

        for _ in range(health_threads):
            futures.append(executor.submit(stress_health))

        for _ in range(memory_threads):
            futures.append(executor.submit(stress_memory))

        # Aguardar até que o usuário pressione Ctrl+C
        try:
            while running:
                # Verificar se alguma thread terminou e reativá-la
                for i, future in enumerate(futures):
                    if future.done() and running:
                        # Determinar qual tipo de estresse reativar
                        if i < register_threads:
                            futures[i] = executor.submit(stress_register)
                        elif i < register_threads + profile_threads:
                            futures[i] = executor.submit(stress_profile)
                        elif i < register_threads + profile_threads + users_threads:
                            futures[i] = executor.submit(stress_users_list)
                        elif (
                            i
                            < register_threads
                            + profile_threads
                            + users_threads
                            + health_threads
                        ):
                            futures[i] = executor.submit(stress_health)
                        else:
                            futures[i] = executor.submit(stress_memory)

                # Status periódico
                logger.info(
                    f"Active tokens: {len(access_tokens)}, Stress test running with {NUM_THREADS} threads"
                )
                time.sleep(5)

        except KeyboardInterrupt:
            running = False

    logger.info("Stress test complete")
    sys.exit(0)


if __name__ == "__main__":
    main()
