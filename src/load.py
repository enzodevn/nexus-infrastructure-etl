from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd


def load_results(dataframe: pd.DataFrame, output_dir: str | Path) -> dict:
    """Persist analyzed data and generate a JSON summary report."""
    output_path = Path(output_dir)
    dataframe = dataframe.copy()

    if dataframe.empty:
        overall_source = None
    else:
        if "analysis_source" not in dataframe.columns:
            raise ValueError("Origem de análise ausente nos resultados.")
        if dataframe["analysis_source"].isna().any():
            raise ValueError("Origem de análise ausente em um ou mais servidores.")
        source_values = set(dataframe["analysis_source"])
        if not source_values.issubset({"IA", "contingencia local"}):
            raise ValueError("Origem de análise inválida encontrada nos resultados.")
        if source_values == {"IA"}:
            overall_source = "IA"
        elif source_values == {"contingencia local"}:
            overall_source = "contingencia local"
        else:
            overall_source = "mista"

    summary = {
        "execution_datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "servers_analyzed": int(len(dataframe)),
        "normal": int((dataframe.get("risk_level", pd.Series(dtype=str)) == "Normal").sum()),
        "attention": int((dataframe.get("risk_level", pd.Series(dtype=str)) == "Atenção").sum()),
        "critical": int((dataframe.get("risk_level", pd.Series(dtype=str)) == "Crítico").sum()),
        "results": [
            {
                "server_id": row.get("server_id"),
                "hostname": row.get("hostname"),
                "risk_level": row.get("risk_level"),
                "diagnostico": row.get("diagnostico", ""),
                "recomendacao": row.get("recomendacao", ""),
                "prioridade": row.get("prioridade", ""),
                "analysis_source": row.get("analysis_source", "contingencia local"),
            }
            for _, row in dataframe.iterrows()
        ],
        "analysis_source": overall_source,
    }

    output_path.mkdir(parents=True, exist_ok=True)
    csv_path = output_path / "processed_servers.csv"
    dataframe.to_csv(csv_path, index=False)

    report_path = output_path / "infrastructure_report.json"
    with report_path.open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)

    return summary
