# Projeto de Automação de Incidentes de TI com Arquitetura Multi-Agente

Este repositório reúne a implementação de um sistema de suporte de TI automatizado, desenvolvido em um Trabalho de Conclusão de Curso (TCC). Ele combina práticas de ITSM/ITIL com agentes inteligentes baseados em Modelos de Linguagem de Grande Porte (LLMs), simulando uma equipe de analistas de três níveis (N1, N2 e N3) e um agente de documentação.

## Visão Geral

A crescente complexidade dos ambientes de TI e a forte dependência dos sistemas nas operações empresariais tornaram essencial a gestão eficiente de incidentes. Este projeto propõe uma arquitetura multiagente baseada em LLMs para automatizar o ciclo de tratamento de alertas:

- **Triagem (N1):** Detecta e classifica o recurso afetado (CPU, memória ou ambos).
- **Investigação (N2):** Identifica processos intensivos de recursos e avalia sua criticidade.
- **Intervenção (N3):** Executa remediações seguras, encerrando processos não relacionados.
- **Documentação:** Registra todas as ações e resultados para auditoria.

A solução integra-se ao Prometheus para receber alertas e dispara ﬂuxos de resposta via framework CrewAI.

## Pré-requisitos

- Docker (>= 20.10) e Docker Compose
- Python 3.9+
- Chave de API OpenAI configurada na variável de ambiente `OPENAI_API_KEY`

## Arquitetura de Contêineres

Todos os serviços são orquestrados via `docker-compose.yml`:

- **user-service:** Microserviço principal em Flask (porta 5001)
- **db:** Banco PostgreSQL
- **redis:** Cache Redis
- **rabbitmq:** Susbistema de mensageria
- **prometheus:** Coleta métricas e dispara alertas (porta 9090)
- **grafana:** Dashboards de visualização (porta 3000)
- **chaos_monkey:** Gera falhas aleatórias de CPU
- **failure-controller:** Orquestra simulações de falhas (CPU, memória, exaustão de conexões)
- **it-support-crew:** Serviço Flask que expõe endpoints para iniciar o ﬂuxo multiagente

## Como Executar o Ambiente Docker

1. Clone o repositório e navegue até sua raiz:
   ```bash
   git clone <URL_DO_REPOSITORIO>
   cd v2_multi_agent_it_support
   ```
2. Configure a variável de ambiente com sua chave OpenAI:
   ```bash
   export OPENAI_API_KEY="sua_chave_aqui"
   ```
3. Inicialize os serviços:
   ```bash
   docker-compose up -d --build
   ```
4. Verifique status:
   - Prometheus: http://localhost:9090
   - Grafana:    http://localhost:3000 (usuário: `username`, senha: `password`)
   - User Service: http://localhost:5001/health

## Simulação de Incidentes

### Chaos Monkey (sobrecarga de CPU)

O serviço `chaos_monkey` dispara eventos a cada 2 minutos, simulando falhas de CPU em `user-service`. Para inspecionar os logs:
```bash
docker logs -f chaos_monkey
```

### Simulações Controladas

O serviço `failure-controller` coordena simulações de:
- Sobrecarga de CPU
- Memory Leak
- Exaustão de conexões de banco

Para disparar manualmente uma simulação:
```bash
docker exec -it failure-controller python failure_controller.py --type cpu_overload --intensity 0.8
```

### Testes de Stress

Na pasta `stress_tests/`, há scripts Python para gerar cargas de CPU, memória e profile:
```bash
python stress_tests/stress_user_service.py --mode cpu
python stress_tests/stress_user_service.py --mode memory
```

## Configuração de Credenciais SSH para a Crew

Antes de iniciar o serviço de suporte multiagente, ajuste as credenciais no arquivo `services/it-support-crew/config/servers.yaml`:

- Localize a seção `servers -> user-service`.
- Substitua os campos `username` e `password` pelos valores corretos de acesso SSH ao container `user-service`.
- Confira também o mapeamento de portas (`ssh_port: 2222` por padrão) para conectar via SSH.

Exemplo de configuração:
```yaml
servers:
  user-service:
    hostname: user-service
    port: 22
    username: <USUARIO_SSH>
    password: <SENHA_SSH>
    ssh_port: 2222
    # ...demais campos inalterados
```

## Execução da Crew de Suporte

1. Instale as dependências do serviço de suporte:
   ```bash
   cd services/it-support-crew
   pip install -r requirements.txt
   ```
2. Execute a API Flask da crew:
   ```bash
   python crew.py
   ```
3. Interaja com os endpoints:
   - POST `/event` para enviar um alerta JSON e acionar o fluxo
   - GET `/queue` para verificar a fila de tarefas

## Observabilidade e Dashboards

- Prometheus: coleta métricas via `prometheus.yml` e regras de alerta em `alerts.yml`.
- Grafana: dashboards automaticamente carregados em `infrastructure/grafana/provisioning/dashboards`.
- Loki & Promtail: centralizam logs de contêineres.

## Scripts Auxiliares

- `services/user-service/scripts/fix_log_permissions.sh`: corrige permissões de arquivos de log.
- `services/user-service/debug_logs.py`: diagnostica caminhos, permissões e escrita de logs dentro do contêiner.

## Estrutura do Projeto

A organização principal deste repositório:

- **docker-compose.yml**: definição de todos os contêineres e redes.
- **services/**: código-fonte dos serviços:
  - `user-service`: aplicação Flask e scripts auxiliares.
  - `it-support-crew`: API Flask para o fluxo multiagente (CrewAI).
  - `failure_simulation`: orquestrador de simulações de falha.
  - `chaos_monkey`: gerador de falhas periódicas.
- **infrastructure/**: configuração de observabilidade, banco de dados e logs.
- **stress_tests/**: scripts Python para gerar carga de CPU e memória.

## Configurações e Volumes

- Volume `db-data`: armazena dados persistentes do PostgreSQL.
- Volume `ssh-keys`: chaves SSH para acesso aos contêineres (montado em `user-service`).
- Variáveis de ambiente adicionais:
  - `DATABASE_URL`, `REDIS_URL`, `RABBITMQ_URL`, `JWT_SECRET` (configuradas no Docker Compose).
  - `OPENAI_API_KEY` (obrigatória para o CrewAI).

## Solução de Problemas Comuns

- **Permissões de log**: se o `user-service` não conseguir criar ou escrever em logs, execute:
  ```bash
  docker exec -it user-service bash -c "services/user-service/scripts/fix_log_permissions.sh"
  ```
- **Checagem de saúde**:
  - `docker ps` para verificar contêineres rodando.
  - Logs via `docker logs <nome_do_container>`.
  - Endpoints de health:
    - User Service: `http://localhost:5001/health`
    - Prometheus: `http://localhost:9090/health` (se configurado)
- **Falhas no CrewAI**:
  - Verifique se `OPENAI_API_KEY` está setada.
  - Monitore logs da API de suporte: `docker logs -f it-support-crew` ou `python crew.py` localmente.

```text
# Exemplo de debug de permissão de log
$ docker exec -it user-service bash
# dentro do container:
root@user-service:/app# bash services/user-service/scripts/fix_log_permissions.sh
```

## Contribuição

Este projeto foi desenvolvido como prova de conceito de TCC. Sinta-se à vontade para abrir issues, enviar PRs ou sugerir melhorias. Para mais detalhes, consulte a documentação interna e o sumário do TCC.