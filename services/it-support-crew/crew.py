import logging
import os
import sys
import threading

from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, llm, task
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from tools.ssh_diagnostic_tool import SSHDiagnosticTool
from tools.user_service_metrics import UserServiceMetricsTool

load_dotenv()

os.environ["OTEL_SDK_DISABLED"] = "true"

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

logging.getLogger("paramiko").setLevel(logging.WARNING)

app = Flask(__name__)

crew_lock = threading.Lock()
crew_running = False


@CrewBase
class ItSupportCrew:
    agents_config = "./config/agents.yaml"
    tasks_config = "./config/tasks.yaml"
    servers_config = "services/it-support-crew/config/servers.yaml"

    @llm
    def general_llm(self) -> LLM:
        return LLM(
            model="gpt-4o",
            api_key=os.environ["OPENAI_API_KEY"],
            temperature=0.1,
        )

    @llm
    def report_llm(self) -> LLM:
        return LLM(
            model="gpt-4o",
            api_key=os.environ["OPENAI_API_KEY"],
            temperature=0.1,
        )

    @agent
    def level_1_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["level_1_agent"],
            verbose=True,
            llm=self.general_llm(),
            tools=[UserServiceMetricsTool(), SSHDiagnosticTool()],
            cache=False,
            function_calling_llm="gpt-4o-mini",
        )

    @agent
    def level_2_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["level_2_agent"],
            verbose=True,
            llm=self.general_llm(),
            tools=[SSHDiagnosticTool()],
            cache=False,
            function_calling_llm="gpt-4o-mini",
        )

    @agent
    def level_3_specialist(self) -> Agent:
        return Agent(
            config=self.agents_config["level_3_agent"],
            verbose=True,
            llm=self.general_llm(),
            tools=[
                UserServiceMetricsTool(),
                SSHDiagnosticTool(),
            ],
            cache=False,
            function_calling_llm="gpt-4o-mini",
        )

    @agent
    def support_team(self) -> Agent:
        return Agent(
            config=self.agents_config["support_team_agent"],
            verbose=True,
            llm=self.report_llm(),
            cache=False,
        )

    # ===== Definições de Tasks =====

    # Tarefas de Nível 1
    @task
    def l1_triage_alert(self) -> Task:
        """Tarefa para o Agente de Suporte Nível 1 realizar a triagem inicial do alerta de recursos."""
        return Task(
            config=self.tasks_config["l1_triage_alert"],
            agent=self.level_1_analyst(),
        )

    @task
    def l1_basic_process_survey(self) -> Task:
        """Tarefa para o Agente de Suporte Nível 1 realizar levantamento básico de processos."""
        return Task(
            config=self.tasks_config["l1_basic_process_survey"],
            agent=self.level_1_analyst(),
            context=[self.l1_triage_alert()],
        )

    # Tarefas de Nível 2
    @task
    def l2_process_identification(self) -> Task:
        """Tarefa para o Agente de Suporte Nível 2 identificar e categorizar processos de alto consumo de recursos."""
        return Task(
            config=self.tasks_config["l2_process_identification"],
            agent=self.level_2_analyst(),
            context=[self.l1_basic_process_survey()],
        )

    # Tarefas de Nível 3
    @task
    def l3_resource_intensive_process_analysis(self) -> Task:
        """Tarefa para o Especialista de Nível 3 analisar profundamente processos intensivos em recursos."""
        return Task(
            config=self.tasks_config["l3_resource_intensive_process_analysis"],
            agent=self.level_3_specialist(),
            context=[self.l2_process_identification()],
        )

    @task
    def l3_process_termination_plan(self) -> Task:
        """Tarefa para o Especialista de Nível 3 criar um plano de encerramento para processos não relacionados."""
        return Task(
            config=self.tasks_config["l3_process_termination_plan"],
            agent=self.level_3_specialist(),
            context=[self.l3_resource_intensive_process_analysis()],
        )

    @task
    def l3_process_termination_execution(self) -> Task:
        """Tarefa para o Especialista de Nível 3 executar o plano de encerramento para processos não relacionados."""
        return Task(
            config=self.tasks_config["l3_process_termination_execution"],
            agent=self.level_3_specialist(),
            context=[self.l3_process_termination_plan()],
        )

    @task
    def l3_post_termination_verification(self) -> Task:
        """Tarefa para o Especialista de Nível 3 verificar a estabilidade do sistema após o encerramento."""
        return Task(
            config=self.tasks_config["l3_post_termination_verification"],
            agent=self.level_3_specialist(),
            context=[self.l3_process_termination_execution()],
        )

    # Support Team Task
    @task
    def support_document_process_management(self) -> Task:
        """Tarefa para o Especialista em Análie e Documentação documentar a intervenção de gerenciamento de processos."""
        return Task(
            config=self.tasks_config["support_document_process_management"],
            agent=self.support_team(),
            context=[
                self.l1_triage_alert(),
                self.l1_basic_process_survey(),
                self.l2_process_identification(),
                self.l3_resource_intensive_process_analysis(),
                self.l3_process_termination_plan(),
                self.l3_process_termination_execution(),
                self.l3_post_termination_verification(),
            ],
        )

    @crew
    def it_support_crew(self) -> Crew:
        """Orquestra a execução dos agentes e tasks."""
        return Crew(
            agents=[
                self.level_1_analyst(),
                self.level_2_analyst(),
                self.level_3_specialist(),
                self.support_team(),
            ],
            tasks=[
                self.l1_triage_alert(),
                self.l1_basic_process_survey(),
                self.l2_process_identification(),
                self.l3_resource_intensive_process_analysis(),
                self.l3_process_termination_plan(),
                self.l3_process_termination_execution(),
                self.l3_post_termination_verification(),
                self.support_document_process_management(),
            ],
            verbose=True,
            process=Process.sequential,
            cache=False,
            memory=True,
        )


# Execução síncrona da crew
def crew_execution(crew_obj, inputs):
    global crew_running

    try:
        logger.info("======= INICIANDO EXECUÇÃO DA CREW =======")

        result = crew_obj.kickoff(inputs)

        logger.info("======= CREW EXECUTADA COM SUCESSO =======")

        return result
    except Exception as e:
        logger.exception(f"Erro na execução da crew: {e}")
        return None
    finally:
        with crew_lock:
            crew_running = False


def process_alert(event_data):
    """
    Processa um alerta, iniciando a execução da crew.
    Esta função assume que o lock já foi adquirido e crew_running já foi definido como True.
    """
    global crew_running

    try:
        logger.info("Iniciando execução da crew para novo alerta")
        input_dict = {"input": event_data}
        crew_instance = ItSupportCrew()

        # Executa a crew em uma thread separada para não bloquear a API
        thread = threading.Thread(
            target=crew_execution, args=(crew_instance.it_support_crew(), input_dict)
        )
        thread.daemon = True
        thread.start()

    except Exception as e:
        logger.exception(f"Erro ao iniciar execução da crew: {e}")
        with crew_lock:
            crew_running = False


@app.post("/event")
def alert_manager_event():
    """
    Endpoint que recebe um evento (por exemplo, do Alertmanager)
    e inicia o pipeline de suporte apenas se não houver crew em execução.
    """
    global crew_running

    try:
        event_data = request.get_json()
        logger.debug("Dados recebidos no endpoint /event:")
        logger.debug(event_data)

        with crew_lock:
            if crew_running:
                # Se a crew já estiver em execução, rejeita o alerta
                logger.info("Crew já em execução. Novo alerta foi rejeitado.")
                return (
                    jsonify(
                        {
                            "message": "Alerta rejeitado",
                            "status": "rejected",
                        }
                    ),
                    429,
                )
            else:
                crew_running = True

        process_alert(event_data)
        return (
            jsonify(
                {"message": "Processamento do alerta iniciado", "status": "accepted"}
            ),
            200,
        )

    except Exception as e:
        logger.exception(f"Erro ao processar o evento: {e}")
        return jsonify({"error": str(e)}), 500


@app.get("/queue")
def get_queue_status():
    """Endpoint para verificar o status da equipe de suporte"""
    with crew_lock:
        return jsonify({"crew_running": crew_running})


if __name__ == "__main__":
    logger.info("Iniciando servidor IT Support Crew na porta 5002")
    app.run(host="0.0.0.0", port=5002, threaded=True)
