"""
Data Loader Module
Loads SPEC Excel and Raw Data CSV files with robust validation and parsing.
"""

from pathlib import Path
from typing import Optional, Tuple
import pandas as pd
import numpy as np


def resolve_path(preferred_path: str | Path, fallback_filename: str) -> Path:
    """
    Resolves data file path by checking:
    1. preferred_path as given
    2. 'raw data/' folder
    3. 'data/' folder
    """
    # Do not silently fall back to an unrelated file: that can produce a valid
    # looking report for the WRONG production lot.
    return Path(preferred_path)



def load_spec(spec_path: str | Path) -> pd.DataFrame:
    """
    Loads and validates the SPEC sheet from Electrode_Quality_SPEC.xlsx.
    Only returns enabled ('Y') specifications.
    """
    spec_file = resolve_path(spec_path, "Electrode_Quality_SPEC.xlsx")
    if not spec_file.exists():
        raise FileNotFoundError(
            f"SPEC 파일을 찾을 수 없습니다. 지정한 경로: {spec_file.resolve()}"
        )

    # Read SPEC sheet
    spec_df = pd.read_excel(spec_file, sheet_name="SPEC")
    spec_df.columns = [str(c).strip() for c in spec_df.columns]
    if spec_df.columns.duplicated().any():
        raise ValueError('SPEC has duplicate column headers.')

    # Required columns in SPEC sheet
    required_cols = [
        "raw_column", "characteristic", "unit", "data_type",
        "LSL", "TARGET", "USL", "chart_type", "enabled"
    ]
    missing_cols = [c for c in required_cols if c not in spec_df.columns]
    if missing_cols:
        raise ValueError(f"SPEC sheet is missing required columns: {missing_cols}")

    # Strip whitespace from string columns
    str_cols = ["raw_column", "characteristic", "unit", "data_type", "chart_type", "enabled"]
    for col in str_cols:
        if col in spec_df.columns:
            spec_df[col] = spec_df[col].astype(str).str.strip()

    # Filter enabled
    spec_df = spec_df[spec_df["enabled"].str.upper() == "Y"].copy()

    if spec_df['raw_column'].eq('').any() or spec_df['raw_column'].str.lower().eq('nan').any():
        raise ValueError('Enabled SPEC has an empty raw_column.')

    # Do not silently convert a misspelled numeric specification into missing
    # (which would otherwise disable the boundary and produce false OK rows).
    for bound in ['LSL', 'TARGET', 'USL']:
        vals = spec_df[bound]
        nonempty = vals.notna() & vals.astype(str).str.strip().ne('')
        invalid = nonempty & pd.to_numeric(vals, errors='coerce').isna()
        if invalid.any():
            raise ValueError(f'Non-numeric {bound} specification in enabled rows: {spec_df.loc[invalid, "raw_column"].tolist()}')

    # Convert numeric thresholds
    for col in ["LSL", "TARGET", "USL", "inspection_area_m2"]:
        if col in spec_df.columns:
            spec_df[col] = pd.to_numeric(spec_df[col], errors="coerce")

    return spec_df.reset_index(drop=True)


def load_raw_data(raw_path: str | Path) -> pd.DataFrame:
    """
    Loads and validates Raw Data CSV.
    Parses timestamps, sorts in chronological order.
    """
    raw_file = resolve_path(raw_path, "Electrode_Quality_Raw_Data.csv")
    if not raw_file.exists():
        raise FileNotFoundError(
            f"Raw Data 파일을 찾을 수 없습니다. 지정한 경로: {raw_file.resolve()}"
        )

    raw_df = pd.read_csv(raw_file)
    raw_df.columns = [str(c).strip() for c in raw_df.columns]
    if raw_df.columns.duplicated().any():
        raise ValueError('Raw Data has duplicate column headers.')
    if 'machine_id' in raw_df.columns and (
        raw_df['machine_id'].isna().any() or raw_df['machine_id'].astype(str).str.strip().eq('').any()
    ):
        raise ValueError('machine_id is present but contains missing/blank values. Equipment identification is required for per-machine SPC.')

    if "timestamp" not in raw_df.columns:
        raise ValueError("Raw data missing required 'timestamp' column.")

    raw_df["timestamp"] = pd.to_datetime(raw_df["timestamp"], errors="coerce")
    if raw_df["timestamp"].isna().any():
        invalid_ts_count = raw_df["timestamp"].isna().sum()
        raise ValueError(f"Found {invalid_ts_count} rows with invalid timestamps.")

    # Sort chronologically
    raw_df = raw_df.sort_values("timestamp").reset_index(drop=True)
    return raw_df


def load_equipment_event_log(event_path: Optional[str | Path] = None) -> Optional[pd.DataFrame]:
    """
    Loads optional equipment event log.
    Expected fields: timestamp, machine_id, event_type, event_description.
    Returns None if file not provided or does not exist.
    """
    if event_path is None:
        return None

    path = Path(event_path)
    if not path.exists():
        raise FileNotFoundError(f'Explicit event log file not found: {path}')

    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.sort_values("timestamp").reset_index(drop=True)
    return df
