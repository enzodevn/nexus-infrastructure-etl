from pathlib import Path

from src.ai_analyzer import analyze_servers
from src.extract import extract_servers
from src.load import load_results
from src.transform import transform_servers

PROJECT_NAME = "NEXUS Infrastructure ETL"
BASE_DIR = Path(__file__).resolve().parent
DATA_INPUT_PATH = BASE_DIR / "data" / "input" / "servers.csv"
OUTPUT_DIR = BASE_DIR / "data" / "output"


def main() -> None:
    print(f"[PROJECT] {PROJECT_NAME}")
    print("[EXTRACT] Iniciando extração...")

    dataframe = extract_servers(DATA_INPUT_PATH)
    print(f"[EXTRACT] {len(dataframe)} servidores encontrados.")

    print("[TRANSFORM] Processando métricas...")
    transformed = transform_servers(dataframe)
    print("[TRANSFORM] Classificação concluída.")

    print("[ANALYZE] Analisando servidores com IA ou contingência local...")
    analyzed = analyze_servers(transformed)
    print("[ANALYZE] Análises concluídas.")

    print("[LOAD] Salvando resultados...")
    report = load_results(analyzed, OUTPUT_DIR)
    print("[LOAD] Arquivos gerados com sucesso.")

    print(f"Servidores analisados: {report['servers_analyzed']}")
    print(f"Normal: {report['normal']}")
    print(f"Atenção: {report['attention']}")
    print(f"Crítico: {report['critical']}")
    print("Pipeline finalizado com sucesso!")


if __name__ == "__main__":
    main()
