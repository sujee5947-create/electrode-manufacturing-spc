"""
SPEC Validator Module
Validates SPEC integrity and consistency between SPEC and Raw Data columns.
"""

from typing import List, Tuple
import pandas as pd


class SpecValidationError(Exception):
    """Raised when specification validation fails."""
    pass


def validate_spec_and_raw(spec_df: pd.DataFrame, raw_df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    Validates SPEC contents and checks that all enabled SPEC columns exist in raw_df.
    Returns (is_valid, warning_or_error_messages).
    """
    issues = []

    if spec_df.empty:
        raise SpecValidationError("SPEC sheet contains no enabled items (enabled='Y').")

    if raw_df.empty:
        raise SpecValidationError("Raw Data contains zero measurement rows.")
    if raw_df.columns.duplicated().any():
        raise SpecValidationError("Raw Data has duplicate column names.")
    if spec_df["raw_column"].duplicated().any():
        raise SpecValidationError("Enabled SPEC contains duplicate raw_column entries.")

    allowed_types = {"continuous": "I-MR", "count": "C"}
    for _, row in spec_df.iterrows():
        kind = row["data_type"]
        chart = row["chart_type"]
        if kind not in allowed_types or (kind == "continuous" and chart != "I-MR") or (kind == "count" and chart not in ("C", "U")):
            raise SpecValidationError(f"Unsupported data_type/chart_type for {row['raw_column']}: {kind}/{chart}")
    # 1. Check raw columns presence
    for _, row in spec_df.iterrows():
        col = row["raw_column"]
        if col not in raw_df.columns:
            issues.append(f"SPEC target column '{col}' is not present in Raw Data.")
        else:
            # Check numeric type in raw_df
            if not pd.api.types.is_numeric_dtype(raw_df[col]):
                issues.append(f"Raw data column '{col}' is not numeric.")

    if "timestamp" not in raw_df.columns:
        issues.append("Raw Data timestamp not present")
    if any(x == 'U' for x in spec_df['chart_type']):
        if 'inspection_area_m2' not in raw_df.columns:
            raise SpecValidationError('U-chart requires inspection_area_m2 column.')
        area = pd.to_numeric(raw_df['inspection_area_m2'], errors='coerce')
        if area.isna().any() or (area <= 0).any():
            raise SpecValidationError('U-chart inspection_area_m2 must be positive finite numbers.')
    # 2. Check SPEC limits consistency
    for _, row in spec_df.iterrows():
        col = row["raw_column"]
        data_type = row.get("data_type", "continuous")
        lsl = row.get("LSL")
        usl = row.get("USL")
        target = row.get("TARGET")

        if pd.isna(usl):
            issues.append(f"SPEC error for '{col}': USL cannot be empty.")
        elif not pd.api.types.is_number(usl) and not isinstance(usl, (int, float)):
            issues.append(f"SPEC error for '{col}': USL must be numeric.")

        if data_type == "continuous":
            if not pd.isna(lsl) and not pd.isna(usl) and lsl >= usl:
                issues.append(f"SPEC error for '{col}': LSL ({lsl}) must be less than USL ({usl}).")
            if not pd.isna(target):
                if not pd.isna(lsl) and target < lsl:
                    issues.append(f"SPEC warning for '{col}': TARGET ({target}) is less than LSL ({lsl}).")
                if not pd.isna(usl) and target > usl:
                    issues.append(f"SPEC warning for '{col}': TARGET ({target}) is greater than USL ({usl}).")
        elif data_type == "count":
            if not pd.isna(usl) and (usl < 0 or float(usl) != int(usl)):
                issues.append(f"SPEC error for count characteristic '{col}': USL ({usl}) must be a non-negative integer.")

    critical_errors = [msg for msg in issues if any(flag in msg.lower() for flag in ("error", "not present", "not numeric"))]
    if critical_errors:
        raise SpecValidationError("\n".join(critical_errors))

    return True, issues
