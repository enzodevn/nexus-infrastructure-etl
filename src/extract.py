from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = [
    "server_id",
    "hostname",
    "operating_system",
    "cpu_usage",
    "memory_usage",
    "disk_usage",
    "temperature",
    "status",
]
METRIC_COLUMNS = ["cpu_usage", "memory_usage", "disk_usage", "temperature"]
TEXT_COLUMNS = ["server_id", "hostname", "operating_system", "status"]


def _invalid_value(row_number: int, column: str, message: str) -> ValueError:
    return ValueError(f"Linha {row_number}, coluna '{column}': {message}")


def extract_servers(csv_path: str | Path) -> pd.DataFrame:
    """Read server data and reject missing, malformed, or invalid values."""
    file_path = Path(csv_path)

    if not file_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    try:
        dataframe = pd.read_csv(file_path, dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError as exc:
        raise ValueError("O arquivo CSV está vazio e não contém cabeçalho.") from exc

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in dataframe.columns]
    if missing_columns:
        raise ValueError("Colunas obrigatórias ausentes: " + ", ".join(missing_columns))

    if dataframe.empty:
        raise ValueError("Arquivo CSV encontrado, mas não há dados para processar.")

    for row_index, row in dataframe.iterrows():
        row_number = row_index + 2
        for column in REQUIRED_COLUMNS:
            if column in METRIC_COLUMNS:
                continue
            if not row[column].strip():
                raise _invalid_value(row_number, column, "campo obrigatório vazio.")

    for column in TEXT_COLUMNS:
        dataframe[column] = dataframe[column].str.strip()

    duplicate_mask = dataframe["server_id"].duplicated(keep=False)
    if duplicate_mask.any():
        duplicate_row = int(duplicate_mask[duplicate_mask].index[0]) + 2
        duplicate_id = dataframe["server_id"].iloc[duplicate_row - 2]
        raise _invalid_value(
            duplicate_row, "server_id", f"identificador duplicado: '{duplicate_id}'."
        )

    for column in METRIC_COLUMNS:
        numeric_values = pd.to_numeric(dataframe[column].str.strip(), errors="coerce")
        for row_index, value in numeric_values.items():
            row_number = row_index + 2
            raw_value = dataframe.at[row_index, column].strip()
            if not raw_value:
                raise _invalid_value(row_number, column, "métrica numérica ausente.")
            if pd.isna(value):
                raise _invalid_value(
                    row_number, column, f"valor numérico inválido: '{raw_value}'."
                )
            if value in (float("inf"), float("-inf")):
                raise _invalid_value(row_number, column, "o valor deve ser finito.")
            if column != "temperature" and not 0 <= value <= 100:
                raise _invalid_value(
                    row_number, column, "o valor deve estar entre 0 e 100."
                )
            if column == "temperature" and value < 0:
                raise _invalid_value(row_number, column, "a temperatura não pode ser negativa.")

        dataframe[column] = numeric_values

    print(f"[EXTRACT] {len(dataframe)} servidores extraídos com sucesso.")
    return dataframe
