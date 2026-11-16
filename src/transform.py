import pandas as pd

from src.risk_rules import classify_risk


def transform_servers(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Classify server risk using Python rules, without performing analysis."""
    transformed = dataframe.copy()
    transformed["risk_level"] = transformed.apply(classify_risk, axis=1)
    return transformed
