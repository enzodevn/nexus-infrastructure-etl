"""Shared infrastructure thresholds and risk classification rules."""

import math

ATTENTION_THRESHOLDS = {
    "cpu_usage": 80,
    "memory_usage": 80,
    "disk_usage": 70,
    "temperature": 60,
}

CRITICAL_THRESHOLDS = {
    "disk_usage": 90,
    "temperature": 75,
    "cpu_and_memory": 90,
    "cpu_memory_disk": 80,
}


def _metric_values(server: dict) -> tuple[float, float, float, float]:
    values = []
    for column in ("cpu_usage", "memory_usage", "disk_usage", "temperature"):
        try:
            value = float(server[column])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Métrica obrigatória inválida: {column}.") from exc
        if not math.isfinite(value):
            raise ValueError(f"Métrica obrigatória inválida: {column} deve ser finita.")
        values.append(value)
    return tuple(values)


def identify_attention_indicators(server: dict) -> list[str]:
    """Return all threshold indicators reached by a server."""
    cpu, memory, disk, temperature = _metric_values(server)
    indicators = []

    if cpu > ATTENTION_THRESHOLDS["cpu_usage"]:
        indicators.append("CPU acima de 80%")
    if memory > ATTENTION_THRESHOLDS["memory_usage"]:
        indicators.append("memória acima de 80%")
    if (
        cpu > CRITICAL_THRESHOLDS["cpu_and_memory"]
        and memory > CRITICAL_THRESHOLDS["cpu_and_memory"]
    ):
        indicators.append("CPU e memória acima de 90% simultaneamente (crítico)")
    if (
        cpu > CRITICAL_THRESHOLDS["cpu_memory_disk"]
        and memory > CRITICAL_THRESHOLDS["cpu_memory_disk"]
        and disk > CRITICAL_THRESHOLDS["cpu_memory_disk"]
    ):
        indicators.append(
            "CPU, memória e disco acima de 80% simultaneamente (crítico)"
        )
    if disk > CRITICAL_THRESHOLDS["disk_usage"]:
        indicators.append("disco acima de 90% (crítico)")
    elif disk > ATTENTION_THRESHOLDS["disk_usage"]:
        indicators.append("disco acima de 70%")
    if temperature > CRITICAL_THRESHOLDS["temperature"]:
        indicators.append("temperatura acima de 75°C (crítica)")
    elif temperature > ATTENTION_THRESHOLDS["temperature"]:
        indicators.append("temperatura acima de 60°C")

    return indicators


def is_critical(server: dict) -> bool:
    """Return whether any critical combination or threshold is reached."""
    cpu, memory, disk, temperature = _metric_values(server)

    return any(
        (
            disk > CRITICAL_THRESHOLDS["disk_usage"],
            temperature > CRITICAL_THRESHOLDS["temperature"],
            cpu > CRITICAL_THRESHOLDS["cpu_and_memory"]
            and memory > CRITICAL_THRESHOLDS["cpu_and_memory"],
            cpu > CRITICAL_THRESHOLDS["cpu_memory_disk"]
            and memory > CRITICAL_THRESHOLDS["cpu_memory_disk"]
            and disk > CRITICAL_THRESHOLDS["cpu_memory_disk"],
        )
    )


def classify_risk(server: dict) -> str:
    """Classify a server; critical conditions always take precedence."""
    if is_critical(server):
        return "Crítico"
    if identify_attention_indicators(server):
        return "Atenção"
    return "Normal"
