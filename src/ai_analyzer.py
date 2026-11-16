from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from src.risk_rules import classify_risk, identify_attention_indicators

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

PRIORITY_MAP = {
    "Normal": "Baixa",
    "Atenção": "Média",
    "Crítico": "Alta",
}
ANALYSIS_FIELDS = (
    "diagnostico",
    "indicadores_atencao",
    "recomendacao",
    "prioridade",
)
PLACEHOLDER_API_KEYS = {"sua_chave_aqui", "your_api_key_here", "changeme"}


def _build_fallback_analysis(server: dict) -> dict:
    risk_level = classify_risk(server)
    indicators = identify_attention_indicators(server)

    if risk_level == "Normal":
        diagnosis = (
            "Análise local gerada por regras Python: nenhum limite de atenção foi atingido."
        )
        recommendation = (
            "Continuar acompanhando as métricas e manter a rotina de manutenção preventiva."
        )
    elif risk_level == "Crítico":
        diagnosis = (
            "Análise local gerada por regras Python: uma ou mais condições críticas foram atingidas."
        )
        recommendation = (
            "Priorizar a revisão dos indicadores críticos e avaliar ações preventivas; "
            "os dados não comprovam uma causa específica."
        )
    else:
        diagnosis = (
            "Análise local gerada por regras Python: pelo menos um limite de atenção foi atingido."
        )
        recommendation = (
            "Revisar os indicadores apontados e acompanhar sua evolução antes que atinjam "
            "uma condição crítica."
        )

    return {
        "diagnostico": diagnosis,
        "indicadores_atencao": (
            "; ".join(indicators) if indicators else "Nenhum limite de atenção atingido"
        ),
        "recomendacao": recommendation,
        "prioridade": PRIORITY_MAP[risk_level],
        "analysis_source": "contingencia local",
    }


def _safe_json_loads(raw_output: str) -> dict:
    cleaned = raw_output.strip()
    if not cleaned:
        raise ValueError("Resposta vazia da API da OpenAI.")

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end > start:
            payload = json.loads(cleaned[start : end + 1])
        else:
            raise ValueError("Resposta da OpenAI não estava em JSON válido.")
    if not isinstance(payload, dict):
        raise ValueError("Resposta da OpenAI deve ser um objeto JSON.")
    return payload


def _build_openai_prompt(server: dict) -> str:
    payload = {
        "server_id": server.get("server_id", "N/A"),
        "hostname": server.get("hostname", "N/A"),
        "operating_system": server.get("operating_system", "N/A"),
        "cpu_usage": server.get("cpu_usage", 0),
        "memory_usage": server.get("memory_usage", 0),
        "disk_usage": server.get("disk_usage", 0),
        "temperature": server.get("temperature", 0),
        "status": server.get("status", "N/A"),
        "risk_level": server.get("risk_level", "Normal"),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def analyze_server(server: dict) -> dict:
    """Use the official OpenAI Responses API when configured; otherwise fallback to local rules."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if (
        not api_key.startswith("sk-")
        or len(api_key) <= 10
        or api_key.casefold() in PLACEHOLDER_API_KEYS
    ):
        return _build_fallback_analysis(server)

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Você é um assistente de análise de infraestrutura de TI. "
                        "Analise apenas os dados fornecidos, não invente informações, "
                        "e identifique o diagnóstico como uma análise gerada por IA."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Analise este servidor de infraestrutura e responda em JSON com os campos: "
                        "diagnostico, indicadores_atencao, recomendacao e prioridade. "
                        "Use apenas os dados do servidor informado. A prioridade deve ser exatamente "
                        f"'{PRIORITY_MAP[classify_risk(server)]}' conforme a classificação Python fornecida. "
                        "Não afirme comprometimento nem causas comprovadas.\n"
                        f"{_build_openai_prompt(server)}"
                    ),
                },
            ],
            text={"format": {"type": "json_object"}},
        )

        response_text = getattr(response, "output_text", "")
        if not response_text:
            raise ValueError("A API da OpenAI não retornou texto estruturado.")

        payload = _safe_json_loads(response_text)
        for field in ANALYSIS_FIELDS:
            if not isinstance(payload.get(field), str) or not payload[field].strip():
                raise ValueError("A resposta da OpenAI não contém todos os campos válidos.")

        expected_priority = PRIORITY_MAP[classify_risk(server)]
        if payload["prioridade"].strip() != expected_priority:
            raise ValueError("A prioridade retornada não corresponde à classificação Python.")

        diagnosis = payload["diagnostico"].strip()
        if "gerada por ia" not in diagnosis.casefold():
            diagnosis = f"Análise gerada por IA: {diagnosis}"

        return {
            "diagnostico": diagnosis,
            "indicadores_atencao": _format_attention_indicators(server),
            "recomendacao": payload["recomendacao"].strip(),
            "prioridade": expected_priority,
            "analysis_source": "IA",
        }
    except Exception as exc:
        print(
            "[AI] Falha na API ou resposta inválida "
            f"({type(exc).__name__}); contingência local utilizada."
        )
        return _build_fallback_analysis(server)


def _format_attention_indicators(server: dict) -> str:
    indicators = identify_attention_indicators(server)
    return "; ".join(indicators) if indicators else "Nenhum limite de atenção atingido"


def analyze_servers(dataframe):
    """Enrich the DataFrame with AI-generated or fallback analysis for each server."""
    enriched = dataframe.copy()

    for field in ANALYSIS_FIELDS:
        enriched[field] = ""
    enriched["analysis_source"] = ""

    for index, row in enriched.iterrows():
        analysis = analyze_server(row.to_dict())
        for field in ANALYSIS_FIELDS + ("analysis_source",):
            enriched.at[index, field] = analysis[field]

    return enriched
