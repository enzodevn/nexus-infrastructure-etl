# NEXUS Infrastructure ETL

Projeto acadêmico de demonstração de ETL em Python, com dados fictícios de infraestrutura de TI e análise opcional pela API da OpenAI. Não monitora servidores reais.

## Objetivo e problema simulado

O projeto simula a leitura de métricas operacionais de servidores (CPU, memória, disco e temperatura), classifica possíveis situações de atenção e gera recomendações. Os dados são fictícios e não representam um ambiente real.

## Conceito e etapas

ETL significa Extract, Transform e Load. Neste projeto, a análise é uma etapa explícita entre Transform e Load:

1. **Extract** (`src/extract.py`): lê `data/input/servers.csv` e valida colunas, campos obrigatórios, métricas e identificadores.
2. **Transform** (`src/transform.py`): aplica as regras Python e adiciona `risk_level`.
3. **Analyze** (`src/ai_analyzer.py`): usa a OpenAI Responses API se uma chave válida estiver configurada; caso contrário, utiliza análise local por regras Python.
4. **Load** (`src/load.py`): salva o CSV processado e o relatório JSON em `data/output/`.

### Regras de classificação

Os limites são centralizados em `src/risk_rules.py`:

- **Atenção:** CPU > 80%, memória > 80%, disco > 70% ou temperatura > 60 °C.
- **Crítico:** disco > 90%, temperatura > 75 °C, CPU e memória > 90% simultaneamente, ou CPU, memória e disco > 80% simultaneamente.
- **Normal:** nenhum limite de atenção ou crítico atingido.

Uma condição crítica sempre tem precedência. Os mesmos limites alimentam a identificação dos indicadores da análise local. A classificação de risco é calculada em Python e não é substituída pela IA.

## Tecnologias e dependências

- Python 3.11
- Pandas
- OpenAI Python SDK
- Python-dotenv
- Biblioteca padrão do Python

Instale as dependências em um ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configuração da OpenAI

Copie `.env.example` para `.env` e preencha sua própria chave:

```env
OPENAI_API_KEY=sua_chave_aqui
OPENAI_MODEL=gpt-4.1-mini
```

O `.env` é ignorado pelo Git. Sem chave válida, a análise usa a contingência local, identificada como `contingencia local`. Falhas da API ou respostas inválidas também acionam a contingência, sem expor detalhes sensíveis.

## Execução no Windows

Na pasta do projeto, execute:

```powershell
python main.py
```

Para executar os testes:

```powershell
python -m unittest discover -s tests -v
```

## Resultados gerados

- `data/output/processed_servers.csv`: dados de entrada, classificação, diagnóstico, indicadores, recomendação, prioridade e origem individual da análise.
- `data/output/infrastructure_report.json`: horário de execução, contagem por classificação, resultados individuais e origem geral (`IA`, `contingencia local`, `mista` ou `null` quando não há registros).

## Estrutura de diretórios

```text
nexus-infrastructure-etl/
├── data/
│   ├── input/
│   │   └── servers.csv
│   └── output/
├── src/
│   ├── __init__.py
│   ├── extract.py
│   ├── transform.py
│   ├── risk_rules.py
│   ├── ai_analyzer.py
│   └── load.py
├── tests/
│   └── test_pipeline.py
├── main.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Limitações

- Dados apenas fictícios: não há monitoramento de servidores reais ou em tempo real.
- As regras de classificação são simplificadas e têm finalidade didática.
- A análise da OpenAI é complementar; as regras Python determinam a classificação e a prioridade.
- A disponibilidade e o conteúdo da análise da API dependem do modelo e do serviço configurados.
