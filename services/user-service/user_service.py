import functools
import json
import logging
import logging.config
import os
import random
import socket
import time
from contextlib import contextmanager
from datetime import timedelta

import pika
import redis
from flask import Flask, Response, jsonify, request
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    jwt_required,
)
from flask_sqlalchemy import SQLAlchemy
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError, TimeoutError

# ================== Configuração do Flask e Serviços ==================
app = Flask(__name__)

# Configurações do Flask
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "postgresql://user:password@db:5432/users_db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET", "your_jwt_secret")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)

# Flag para controlar simulação de falhas
ENABLE_FAILURE_SIMULATION = False
FAILURE_RATE = float(os.getenv("FAILURE_SIMULATION_RATE", "0.1"))

# Inicializações
db = SQLAlchemy(app)
jwt = JWTManager(app)

# Configuração do Redis
redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
cache = redis.Redis.from_url(redis_url)

# ================== Configuração de Logs ==================
# Define os diretórios de log com garantia de que existem
log_directory = "/var/log/app"
app_log_directory = "/app"
os.makedirs(log_directory, exist_ok=True)

# Configuração básica de logging
logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("user-service")

# Configuração de handlers para arquivos de log principais
app_handler = logging.FileHandler(f"{app_log_directory}/app.log")
error_handler = logging.FileHandler(f"{app_log_directory}/error.log")
access_handler = logging.FileHandler(f"{app_log_directory}/access.log")

# Configuração de handlers para diretório /var/log/app
var_app_handler = logging.FileHandler(f"{log_directory}/application.log")
var_error_handler = logging.FileHandler(f"{log_directory}/errors.log")
var_access_handler = logging.FileHandler(f"{log_directory}/access.log")

# Formatador padrão para todos os logs
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(name)s - %(message)s")

# Aplicar formatador e níveis aos handlers
for handler in [app_handler, var_app_handler]:
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)

for handler in [error_handler, var_error_handler]:
    handler.setFormatter(formatter)
    handler.setLevel(logging.ERROR)
    logger.addHandler(handler)

# Configurar logger de acesso separado
access_logger = logging.getLogger("access")
access_logger.setLevel(logging.INFO)
for handler in [access_handler, var_access_handler]:
    handler.setFormatter(formatter)
    access_logger.addHandler(handler)

# Verificar e registrar estado dos arquivos de log
log_files = [
    f"{app_log_directory}/app.log",
    f"{app_log_directory}/error.log",
    f"{app_log_directory}/access.log",
    f"{log_directory}/application.log",
    f"{log_directory}/errors.log",
    f"{log_directory}/access.log",
]

for log_file in log_files:
    try:
        # Verifica se o arquivo existe e é gravável
        if os.path.exists(log_file):
            if os.access(log_file, os.W_OK):
                logger.info(f"Log file {log_file} is writable.")
            else:
                logger.warning(f"Log file {log_file} exists but is not writable!")
        else:
            logger.warning(f"Log file {log_file} does not exist!")
    except Exception as e:
        logger.error(f"Error checking log file {log_file}: {str(e)}")


def should_simulate_failure():
    """Determina se deve simular uma falha com base na flag e na taxa de falha."""
    if not ENABLE_FAILURE_SIMULATION:
        return False
    return random.random() < FAILURE_RATE


# ================== Configuração do Prometheus (simplificada) ==================
registry = CollectorRegistry()
multiprocess.MultiProcessCollector(registry)

# Métricas principais (mantidas as essenciais)
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP Requests",
    ["method", "endpoint", "status"],
    registry=registry,
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP Request latency",
    ["method", "endpoint"],
    registry=registry,
    buckets=(0.1, 0.5, 1, 2, 5, 10),
)

DB_HEALTH = Gauge(
    "database_health", "Health status of database connection", registry=registry
)

REDIS_HEALTH = Gauge(
    "redis_health", "Health status of Redis connection", registry=registry
)

IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "HTTP Requests in progress",
    ["method", "endpoint"],
    registry=registry,
)

# Métricas para o pool SQLAlchemy (essenciais para alertas)
SQL_ALCHEMY_POOL_CONNECTIONS_USED = Gauge(
    "sql_alchemy_pool_connections_used",
    "Number of connections used in the SQLAlchemy pool",
    registry=registry,
)

SQL_ALCHEMY_POOL_CONNECTIONS_TOTAL = Gauge(
    "sql_alchemy_pool_connections_total",
    "Total number of connections in the SQLAlchemy pool",
    registry=registry,
)

SQL_ALCHEMY_CONNECTION_TIMEOUTS = Counter(
    "sql_alchemy_connection_timeouts_total",
    "Total SQLAlchemy connection timeouts",
    registry=registry,
)

DATABASE_ERRORS = Counter(
    "database_error_total",
    "Database errors by type",
    ["error_type"],
    registry=registry,
)

DATABASE_QUERY_DURATION = Histogram(
    "database_query_duration_seconds",
    "Database query duration in seconds",
    ["status"],
    registry=registry,
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

# Métrica para erros RabbitMQ (simplificada)
RABBITMQ_CONNECTION_ERRORS = Counter(
    "rabbitmq_connection_errors_total",
    "Total RabbitMQ connection errors",
    registry=registry,
)


def update_sqlalchemy_pool_metrics():
    """Atualiza as métricas do pool de conexões SQLAlchemy"""
    try:
        engine = db.engine
        if hasattr(engine, "pool"):
            pool = engine.pool
            SQL_ALCHEMY_POOL_CONNECTIONS_USED.set(pool.checkedout())
            SQL_ALCHEMY_POOL_CONNECTIONS_TOTAL.set(pool.size() + pool.overflow())
    except Exception as e:
        logger.error(f"Erro ao coletar métricas do pool SQLAlchemy: {str(e)}")


@contextmanager
def monitor_db_query():
    """Contextmanager para monitorar duração e erros das queries"""
    update_sqlalchemy_pool_metrics()
    start_time = time.time()
    status = "success"
    try:
        yield
    except TimeoutError as e:
        status = "error"
        DATABASE_ERRORS.labels("timeout").inc()
        SQL_ALCHEMY_CONNECTION_TIMEOUTS.inc()
        logger.error(f"Timeout na conexão SQLAlchemy: {str(e)}")
        raise
    except SQLAlchemyError as e:
        status = "error"
        error_type = type(e).__name__
        DATABASE_ERRORS.labels(error_type).inc()
        logger.error(f"Erro SQLAlchemy {error_type}: {str(e)}")
        raise
    except Exception as e:
        status = "error"
        DATABASE_ERRORS.labels("other").inc()
        logger.error(f"Erro de banco de dados: {str(e)}")
        raise
    finally:
        duration = time.time() - start_time
        DATABASE_QUERY_DURATION.labels(status).observe(duration)
        update_sqlalchemy_pool_metrics()


# ================== Configuração do RabbitMQ (simplificada) ==================
rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://user:password@rabbitmq:5672/")
params = pika.URLParameters(rabbitmq_url)
params.heartbeat = 60
params.blocked_connection_timeout = 60
params.socket_timeout = 5

# Simplificação do gerenciamento da conexão RabbitMQ
connection = None
channel = None


def get_rabbitmq_connection():
    """Obter uma conexão RabbitMQ com tratamento simplificado de erros."""
    global connection

    if connection is not None and connection.is_open:
        return connection

    try:
        connection = pika.BlockingConnection(params)
        logger.info("Conexão com o RabbitMQ estabelecida com sucesso.")
        return connection
    except Exception as e:
        logger.error(f"Erro ao conectar com RabbitMQ: {str(e)}")
        connection = None
        return None


def publish_event(event, routing_key="user_events"):
    """Publica um evento no RabbitMQ com tratamento simplificado de erros."""
    global channel, connection

    try:
        # Tentar obter conexão se não existir
        if connection is None or not connection.is_open:
            connection = get_rabbitmq_connection()
            if not connection:
                RABBITMQ_CONNECTION_ERRORS.inc()
                return False
            channel = None

        # Criar canal se necessário
        if channel is None or not channel.is_open:
            channel = connection.channel()
            channel.queue_declare(queue="user_events", durable=True)

        # Publicar evento
        channel.basic_publish(
            exchange="",
            routing_key=routing_key,
            body=json.dumps(event),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        return True
    except Exception as e:
        logger.error(f"Erro ao publicar evento: {str(e)}")
        RABBITMQ_CONNECTION_ERRORS.inc()
        channel = None
        connection = None
        return False


@contextmanager
def track_in_progress(method, endpoint):
    """Rastreia requisições em andamento para métricas."""
    IN_PROGRESS.labels(method, endpoint).inc()
    try:
        yield
    finally:
        IN_PROGRESS.labels(method, endpoint).dec()


# ================== Modelo de Usuário ==================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    profile_data = db.Column(db.JSON, nullable=True)

    def to_dict(self):
        result = {"id": self.id, "username": self.username, "email": self.email}
        if self.profile_data:
            result["profile"] = self.profile_data
        return result


# ================== Endpoints com Instrumentação Simplificada ==================
@app.route("/register", methods=["POST"])
def register():
    method = request.method
    endpoint = request.endpoint
    with track_in_progress(method, endpoint), REQUEST_LATENCY.labels(
        method, endpoint
    ).time():
        # Simulação de falha
        if should_simulate_failure():
            logger.warning("Simulated failure on /register endpoint")
            response = jsonify({"error": "Simulated failure"})
            response.status_code = 500
            REQUEST_COUNT.labels(method, endpoint, response.status_code).inc()
            return response

        data = request.get_json()
        if not data or not all(k in data for k in ("username", "password", "email")):
            response = jsonify({"error": "Invalid data"})
            response.status_code = 400
        elif (
            User.query.filter_by(username=data["username"]).first()
            or User.query.filter_by(email=data["email"]).first()
        ):
            response = jsonify({"error": "User already exists"})
            response.status_code = 409
        else:
            user = User(
                username=data["username"],
                password=data["password"],
                email=data["email"],
                profile_data=data.get("profile"),
            )

            try:
                with monitor_db_query():
                    db.session.add(user)
                    db.session.commit()

                event = {"event": "user_registered", "user": user.to_dict()}
                if not publish_event(event):
                    logger.error("Falha ao publicar evento de registro")

                logger.info(f"User registered: {user.username}")
                response = jsonify(user.to_dict())
                response.status_code = 201

            except Exception as e:
                error_msg = f"Database error: {str(e)}"
                logger.error(error_msg)
                response = jsonify({"error": "Database error occurred"})
                response.status_code = 500

        REQUEST_COUNT.labels(method, endpoint, response.status_code).inc()
        return response


@app.route("/login", methods=["POST"])
def login():
    method = request.method
    endpoint = request.endpoint
    with track_in_progress(method, endpoint), REQUEST_LATENCY.labels(
        method, endpoint
    ).time():
        # Simulação de falha
        if should_simulate_failure():
            logger.warning("Simulated failure on /login endpoint")
            response = jsonify({"error": "Simulated failure"})
            response.status_code = 500
            REQUEST_COUNT.labels(method, endpoint, response.status_code).inc()
            return response

        data = request.get_json()
        if not data or not all(k in data for k in ("username", "password")):
            response = jsonify({"error": "Invalid data"})
            response.status_code = 400
        else:
            try:
                with monitor_db_query():
                    user = User.query.filter_by(username=data["username"]).first()

                if not user or user.password != data["password"]:
                    response = jsonify({"error": "Invalid credentials"})
                    response.status_code = 401
                else:
                    access_token = create_access_token(identity=str(user.id))
                    cache.setex(f"token:{access_token}", timedelta(hours=1), user.id)

                    event = {"event": "user_logged_in", "user_id": user.id}
                    publish_event(event)

                    logger.info(f"User logged in: {user.username}")
                    response = jsonify(access_token=access_token)
                    response.status_code = 200

            except Exception as e:
                error_msg = f"Database error: {str(e)}"
                logger.error(error_msg)
                response = jsonify({"error": "Database error occurred"})
                response.status_code = 500

        REQUEST_COUNT.labels(method, endpoint, response.status_code).inc()
        return response


@app.route("/profile", methods=["GET"])
@jwt_required()
def profile():
    method = request.method
    endpoint = request.endpoint
    with track_in_progress(method, endpoint), REQUEST_LATENCY.labels(
        method, endpoint
    ).time():
        if should_simulate_failure():
            logger.warning("Simulated failure on /profile endpoint")
            response = jsonify({"error": "Simulated failure"})
            response.status_code = 500
            REQUEST_COUNT.labels(method, endpoint, response.status_code).inc()
            return response

        try:
            user_id = int(get_jwt_identity())
            with monitor_db_query():
                user = User.query.get(user_id)

            if not user:
                response = jsonify({"error": "User not found"})
                response.status_code = 404
            else:
                response = jsonify(user.to_dict())
                response.status_code = 200

        except Exception as e:
            error_msg = f"Error retrieving profile: {str(e)}"
            logger.error(error_msg)
            response = jsonify({"error": "Error retrieving profile"})
            response.status_code = 500

        REQUEST_COUNT.labels(method, endpoint, response.status_code).inc()
        return response


@app.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    method = request.method
    endpoint = request.endpoint
    with track_in_progress(method, endpoint), REQUEST_LATENCY.labels(
        method, endpoint
    ).time():
        if should_simulate_failure():
            logger.warning("Simulated failure on /profile PUT endpoint")
            response = jsonify({"error": "Simulated failure"})
            response.status_code = 500
            REQUEST_COUNT.labels(method, endpoint, response.status_code).inc()
            return response

        try:
            user_id = int(get_jwt_identity())
            with monitor_db_query():
                user = User.query.get(user_id)

            if not user:
                response = jsonify({"error": "User not found"})
                response.status_code = 404
            else:
                data = request.get_json()
                if not data:
                    response = jsonify({"error": "No data provided"})
                    response.status_code = 400
                else:
                    # Atualizar profile
                    if user.profile_data:
                        profile_data = user.profile_data.copy()
                        profile_data.update(data)
                    else:
                        profile_data = data

                    with monitor_db_query():
                        user.profile_data = profile_data
                        db.session.commit()

                    publish_event({"event": "user_profile_updated", "user_id": user.id})
                    logger.info(f"User profile updated: {user.username}")

                    response = jsonify(
                        {"status": "success", "profile": user.profile_data}
                    )
                    response.status_code = 200

        except Exception as e:
            logger.error(f"Error updating profile: {str(e)}")
            response = jsonify({"error": "Error updating profile"})
            response.status_code = 500

        REQUEST_COUNT.labels(method, endpoint, response.status_code).inc()
        return response


@app.route("/health", methods=["GET"])
def health():
    method = request.method
    endpoint = request.endpoint
    with track_in_progress(method, endpoint), REQUEST_LATENCY.labels(
        method, endpoint
    ).time():
        if should_simulate_failure():
            logger.warning("Simulated failure on /health endpoint")
            response = jsonify({"status": "unhealthy", "reason": "Simulated failure"})
            response.status_code = 500
            REQUEST_COUNT.labels(method, endpoint, response.status_code).inc()
            return response

        healthy = True
        db_status = "healthy"
        redis_status = "healthy"
        pool_status = "healthy"

        try:
            with monitor_db_query():
                db.session.execute(text("SELECT 1"))
            DB_HEALTH.set(1)
        except Exception as e:
            db_status = f"unhealthy: {str(e)}"
            DB_HEALTH.set(0)
            healthy = False

        try:
            update_sqlalchemy_pool_metrics()
        except Exception as e:
            pool_status = f"error: {str(e)}"
            healthy = False

        try:
            cache.ping()
            REDIS_HEALTH.set(1)
        except Exception as e:
            redis_status = f"unhealthy: {str(e)}"
            REDIS_HEALTH.set(0)
            healthy = False

        health_data = {
            "status": "healthy" if healthy else "unhealthy",
            "components": {
                "database": db_status,
                "redis": redis_status,
                "db_pool": pool_status,
            },
        }

        response = jsonify(health_data)
        response.status_code = 200 if healthy else 500

        REQUEST_COUNT.labels(method, endpoint, response.status_code).inc()
        return response


@app.route("/users", methods=["GET"])
def get_users():
    method = request.method
    endpoint = request.endpoint
    with track_in_progress(method, endpoint), REQUEST_LATENCY.labels(
        method, endpoint
    ).time():
        if should_simulate_failure():
            logger.warning("Simulated failure on /users endpoint")
            response = jsonify({"error": "Simulated failure"})
            response.status_code = 500
            REQUEST_COUNT.labels(method, endpoint, response.status_code).inc()
            return response

        try:
            page = request.args.get("page", 1, type=int)
            per_page = min(request.args.get("per_page", 10, type=int), 1000)

            with monitor_db_query():
                pagination = User.query.paginate(
                    page=page, per_page=per_page, error_out=False
                )
                users = pagination.items

            response = jsonify(
                {
                    "users": [user.to_dict() for user in users],
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total": pagination.total,
                        "pages": pagination.pages,
                    },
                }
            )
            response.status_code = 200
        except Exception as e:
            logger.error(f"Error listing users: {str(e)}")
            response = jsonify({"error": "Error listing users"})
            response.status_code = 500

        REQUEST_COUNT.labels(method, endpoint, response.status_code).inc()
        return response


# Endpoint para testar carga de memória (usado pelo teste de stress)
@app.route("/debug/echo", methods=["POST"])
def debug_echo():
    method = request.method
    endpoint = request.endpoint
    with track_in_progress(method, endpoint), REQUEST_LATENCY.labels(
        method, endpoint
    ).time():
        if should_simulate_failure():
            logger.warning("Simulated failure on /debug/echo endpoint")
            response = jsonify({"error": "Simulated failure"})
            response.status_code = 500
            REQUEST_COUNT.labels(method, endpoint, response.status_code).inc()
            return response

        # Obter os dados e simplesmente devolvê-los
        data = request.get_json()
        # Simular processamento
        time.sleep(0.5)

        # Log de acesso para demonstrar que o logging está funcionando
        access_logger.info(f"Echo request received with payload size: {len(str(data))}")

        # Retornar os mesmos dados
        response = jsonify(data)
        response.status_code = 200
        REQUEST_COUNT.labels(method, endpoint, response.status_code).inc()
        return response


@app.route("/debug/toggle_failures", methods=["POST"])
def toggle_failures():
    global ENABLE_FAILURE_SIMULATION, FAILURE_RATE

    method = request.method
    endpoint = request.endpoint
    with track_in_progress(method, endpoint), REQUEST_LATENCY.labels(
        method, endpoint
    ).time():
        data = request.get_json()
        if data and "enable" in data:
            ENABLE_FAILURE_SIMULATION = bool(data["enable"])

        if data and "rate" in data:
            try:
                new_rate = float(data["rate"])
                if 0 <= new_rate <= 1:
                    FAILURE_RATE = new_rate
                else:
                    return jsonify({"error": "Rate must be between 0 and 1"}), 400
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid rate value"}), 400

        response = jsonify(
            {
                "failure_simulation": {
                    "enabled": ENABLE_FAILURE_SIMULATION,
                    "rate": FAILURE_RATE,
                }
            }
        )
        response.status_code = 200
        REQUEST_COUNT.labels(method, endpoint, response.status_code).inc()
        return response


# Endpoint para acessar o arquivo de métricas
@app.route("/metrics")
def metrics():
    update_sqlalchemy_pool_metrics()  # Atualiza métricas do pool antes de retornar
    return Response(generate_latest(registry), mimetype="text/plain")


# Adicionar um endpoint específico para verificar o status do logging
@app.route("/debug/log_test", methods=["GET"])
def log_test():
    """Endpoint para testar se o sistema de logging está funcionando corretamente."""
    method = request.method
    endpoint = request.endpoint

    # Gerar logs em todos os níveis e para todos os loggers
    logger.debug("Debug message test")
    logger.info("Info message test")
    logger.warning("Warning message test")
    logger.error("Error message test")
    access_logger.info("Access log test message")

    # Verificar existência e permissões dos arquivos de log
    log_status = {}
    for log_file in log_files:
        exists = os.path.exists(log_file)
        writable = os.access(log_file, os.W_OK) if exists else False
        size = os.path.getsize(log_file) if exists else 0
        log_status[log_file] = {
            "exists": exists,
            "writable": writable,
            "size_bytes": size,
        }

    response = jsonify(
        {
            "message": "Log test executed, check log files for results",
            "log_files_status": log_status,
        }
    )
    response.status_code = 200
    REQUEST_COUNT.labels(method, endpoint, response.status_code).inc()
    return response


with app.app_context():
    db.create_all()

# ================== Execução do Serviço ==================
if __name__ == "__main__":
    # Log de inicialização sobre a simulação de falhas
    if ENABLE_FAILURE_SIMULATION:
        logger.info(f"Failure simulation ENABLED with rate: {FAILURE_RATE}")
    else:
        logger.info("Failure simulation DISABLED")

    # Criar tabelas se não existirem
    with app.app_context():
        db.create_all()

    logger.info("User service starting up...")
    # Iniciar o servidor Flask
    app.run(host="0.0.0.0", port=int(os.getenv("SERVICE_PORT", 5000)))
