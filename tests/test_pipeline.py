import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd

from src.ai_analyzer import analyze_server, analyze_servers
from src.extract import extract_servers
from src.load import load_results
from src.risk_rules import classify_risk, identify_attention_indicators
from src.transform import transform_servers

VALID_ROW = {
    "server_id": "SRV-TEST",
    "hostname": "test-host",
    "operating_system": "Linux",
    "cpu_usage": 30,
    "memory_usage": 40,
    "disk_usage": 50,
    "temperature": 35,
    "status": "Online",
}

CSV_HEADER = (
    "server_id,hostname,operating_system,cpu_usage,memory_usage,"
    "disk_usage,temperature,status\n"
)


class RiskClassificationTests(unittest.TestCase):
    def test_classifies_normal_attention_and_critical(self):
        normal = VALID_ROW.copy()
        attention = {**VALID_ROW, "cpu_usage": 81}
        critical = {**VALID_ROW, "disk_usage": 91}

        self.assertEqual(classify_risk(normal), "Normal")
        self.assertEqual(classify_risk(attention), "Atenção")
        self.assertEqual(classify_risk(critical), "Crítico")

    def test_transform_only_adds_python_risk_classification(self):
        transformed = transform_servers(pd.DataFrame([VALID_ROW]))

        self.assertEqual(transformed.loc[0, "risk_level"], "Normal")
        self.assertNotIn("diagnostico", transformed.columns)
        self.assertNotIn("analysis_source", transformed.columns)

    def test_incomplete_metrics_cannot_be_classified_as_normal(self):
        incomplete = VALID_ROW.copy()
        del incomplete["temperature"]

        with self.assertRaisesRegex(ValueError, "temperature"):
            classify_risk(incomplete)

    def test_critical_combinations_are_reported_as_indicators(self):
        cpu_memory_critical = {
            **VALID_ROW,
            "cpu_usage": 91,
            "memory_usage": 91,
        }
        cpu_memory_disk_critical = {
            **VALID_ROW,
            "cpu_usage": 81,
            "memory_usage": 81,
            "disk_usage": 81,
        }

        self.assertEqual(classify_risk(cpu_memory_critical), "Crítico")
        self.assertIn(
            "CPU e memória acima de 90% simultaneamente (crítico)",
            identify_attention_indicators(cpu_memory_critical),
        )
        self.assertEqual(classify_risk(cpu_memory_disk_critical), "Crítico")
        self.assertIn(
            "CPU, memória e disco acima de 80% simultaneamente (crítico)",
            identify_attention_indicators(cpu_memory_disk_critical),
        )


class ExtractionValidationTests(unittest.TestCase):
    def extract_csv(self, content):
        temporary_file = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".csv", delete=False
        )
        try:
            temporary_file.write(content)
            temporary_file.close()
            return extract_servers(temporary_file.name)
        finally:
            Path(temporary_file.name).unlink(missing_ok=True)

    def test_rejects_missing_metric_with_row_and_column(self):
        row = "SRV-1,host,Linux,,40,50,35,Online"

        with self.assertRaisesRegex(ValueError, "Linha 2, coluna 'cpu_usage'.*ausente"):
            self.extract_csv(CSV_HEADER + row + "\n")

    def test_rejects_out_of_range_and_non_finite_metrics(self):
        out_of_range = "SRV-1,host,Linux,101,40,50,35,Online"
        with self.assertRaisesRegex(ValueError, "cpu_usage.*entre 0 e 100"):
            self.extract_csv(CSV_HEADER + out_of_range + "\n")

        nan_value = "SRV-1,host,Linux,NaN,40,50,35,Online"
        with self.assertRaisesRegex(ValueError, "cpu_usage.*inválido"):
            self.extract_csv(CSV_HEADER + nan_value + "\n")

        infinite = "SRV-1,host,Linux,inf,40,50,35,Online"
        with self.assertRaisesRegex(ValueError, "cpu_usage.*finito"):
            self.extract_csv(CSV_HEADER + infinite + "\n")

        negative_temperature = "SRV-1,host,Linux,30,40,50,-1,Online"
        with self.assertRaisesRegex(ValueError, "temperature.*negativa"):
            self.extract_csv(CSV_HEADER + negative_temperature + "\n")
    def test_rejects_non_numeric_metric_and_duplicate_ids(self):
        non_numeric = "SRV-1,host,Linux,alta,40,50,35,Online"
        with self.assertRaisesRegex(ValueError, "cpu_usage.*inválido"):
            self.extract_csv(CSV_HEADER + non_numeric + "\n")

        duplicate_rows = (
            "SRV-1,host-a,Linux,30,40,50,35,Online\n"
            "SRV-1,host-b,Linux,30,40,50,35,Online\n"
        )
        with self.assertRaisesRegex(ValueError, "server_id.*duplicado"):
            self.extract_csv(CSV_HEADER + duplicate_rows)

    def test_normalizes_text_fields_and_server_id_before_returning(self):
        row = " SRV-1 , host-1 , Linux ,30,40,50,35, Online "
        extracted = self.extract_csv(CSV_HEADER + row + "\n")

        self.assertEqual(extracted.loc[0, "server_id"], "SRV-1")
        self.assertEqual(extracted.loc[0, "hostname"], "host-1")
        self.assertEqual(extracted.loc[0, "operating_system"], "Linux")
        self.assertEqual(extracted.loc[0, "status"], "Online")

    def test_duplicate_ids_are_detected_after_text_normalization(self):
        duplicate_rows = (
            "SRV-1,host-a,Linux,30,40,50,35,Online\n"
            " SRV-1 ,host-b,Linux,30,40,50,35,Online\n"
        )

        with self.assertRaisesRegex(ValueError, "server_id.*duplicado"):
            self.extract_csv(CSV_HEADER + duplicate_rows)


class AnalysisAndLoadTests(unittest.TestCase):
    def test_uses_local_fallback_without_valid_api_key(self):
        server = {**VALID_ROW, "risk_level": "Atenção", "cpu_usage": 85}
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sua_chave_aqui"}):
            analysis = analyze_server(server)

        self.assertEqual(analysis["analysis_source"], "contingencia local")
        self.assertIn("CPU acima de 80%", analysis["indicadores_atencao"])
        self.assertEqual(analysis["prioridade"], "Média")

    def test_api_failure_falls_back_without_exposing_exception_text(self):
        server = {**VALID_ROW, "risk_level": "Normal"}
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key-not-real"}):
            with patch("src.ai_analyzer.OpenAI", side_effect=RuntimeError("secret-value")):
                with patch("builtins.print") as print_mock:
                    analysis = analyze_server(server)

        self.assertEqual(analysis["analysis_source"], "contingencia local")
        printed = " ".join(str(call) for call in print_mock.call_args_list)
        self.assertNotIn("secret-value", printed)

    def test_valid_api_json_is_marked_as_ai_and_keeps_python_indicators(self):
        server = {**VALID_ROW, "risk_level": "Atenção", "cpu_usage": 85}
        api_response = SimpleNamespace(
            output_text=json.dumps(
                {
                    "diagnostico": "A utilização da CPU está elevada.",
                    "indicadores_atencao": "CPU elevada",
                    "recomendacao": "Acompanhar a carga.",
                    "prioridade": "Média",
                }
            )
        )
        create = Mock(return_value=api_response)
        fake_client = SimpleNamespace(
            responses=SimpleNamespace(create=create)
        )
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key-not-real"}):
            with patch("src.ai_analyzer.OpenAI", return_value=fake_client):
                analysis = analyze_server(server)

        self.assertEqual(analysis["analysis_source"], "IA")
        self.assertTrue(analysis["diagnostico"].startswith("Análise gerada por IA:"))
        self.assertEqual(analysis["indicadores_atencao"], "CPU acima de 80%")
        self.assertEqual(create.call_args.kwargs["text"]["format"]["type"], "json_object")

    def test_invalid_api_json_uses_local_fallback(self):
        server = {**VALID_ROW, "risk_level": "Normal"}
        fake_client = SimpleNamespace(
            responses=SimpleNamespace(
                create=Mock(return_value=SimpleNamespace(output_text="inválido"))
            )
        )
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key-not-real"}):
            with patch("src.ai_analyzer.OpenAI", return_value=fake_client):
                analysis = analyze_server(server)

        self.assertEqual(analysis["analysis_source"], "contingencia local")
        self.assertIn("regras Python", analysis["diagnostico"])

    def test_report_source_aggregates_all_mixed_and_empty_cases(self):
        analyzed = analyze_servers(pd.DataFrame([VALID_ROW]))
        with tempfile.TemporaryDirectory() as output_dir:
            report = load_results(analyzed, output_dir)
            self.assertEqual(report["analysis_source"], "contingencia local")
            self.assertEqual(report["results"][0]["analysis_source"], "contingencia local")

        for sources, expected in (
            (["IA"], "IA"),
            (["contingencia local"], "contingencia local"),
            (["IA", "contingencia local"], "mista"),
            ([], None),
        ):
            dataframe = pd.DataFrame(
                {
                    "risk_level": ["Normal"] * len(sources),
                    "analysis_source": sources,
                }
            )
            with tempfile.TemporaryDirectory() as output_dir:
                report = load_results(dataframe, output_dir)
                self.assertEqual(report["analysis_source"], expected)
                with open(
                    Path(output_dir) / "infrastructure_report.json",
                    encoding="utf-8",
                ) as report_file:
                    self.assertEqual(
                        json.load(report_file)["analysis_source"], expected
                    )

    def test_invalid_analysis_source_fails_before_writing_outputs(self):
        dataframe = pd.DataFrame(
            {
                "server_id": ["SRV-TEST"],
                "risk_level": ["Normal"],
                "analysis_source": ["desconhecida"],
            }
        )
        with tempfile.TemporaryDirectory() as output_dir:
            with self.assertRaisesRegex(ValueError, "Origem de análise inválida"):
                load_results(dataframe, output_dir)

            self.assertFalse((Path(output_dir) / "processed_servers.csv").exists())
            self.assertFalse((Path(output_dir) / "infrastructure_report.json").exists())


if __name__ == "__main__":
    unittest.main()
