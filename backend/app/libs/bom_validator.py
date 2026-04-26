"""Bill of Materials (BoM) validator for onboarding wizard.
Parses and validates Excel/CSV device lists against supported hardware catalog.
"""

import io
from typing import Optional
import pandas as pd

from app.libs.deployment_templates import SUPPORTED_SWITCH_MODELS, SUPPORTED_COMPUTE_MODELS


ALL_SUPPORTED_MODELS = SUPPORTED_SWITCH_MODELS + SUPPORTED_COMPUTE_MODELS

# Column name aliases to handle varied spreadsheet formats
MODEL_ALIASES = ["model", "device model", "part number", "part_number", "sku", "product"]
SERIAL_ALIASES = ["serial", "serial number", "serial_number", "sn", "serialnumber"]
QTY_ALIASES = ["quantity", "qty", "count", "amount", "number"]
ROLE_ALIASES = ["role", "type", "device type", "device_type", "function"]


def _find_column(df: pd.DataFrame, aliases: list[str]) -> Optional[str]:
    """Find the first matching column name (case-insensitive)."""
    cols_lower = {c.lower().strip(): c for c in df.columns}
    for alias in aliases:
        if alias.lower() in cols_lower:
            return cols_lower[alias.lower()]
    return None


def _fuzzy_match_model(model_str: str) -> Optional[str]:
    """Try to match a model string to a known supported model."""
    if not model_str:
        return None
    model_upper = str(model_str).upper().strip()
    for known in ALL_SUPPORTED_MODELS:
        if known.upper() in model_upper or model_upper in known.upper():
            return known
    return None


def _infer_role(model_str: str) -> str:
    """Infer device role from model string."""
    model_upper = str(model_str).upper()
    if any(k in model_upper for k in ["MQM", "DCS", "N9K", "SWITCH"]):
        return "Switch"
    if any(k in model_upper for k in ["HGX", "DGX", "H100", "H200", "A100", "GPU", "COMPUTE"]):
        return "Compute Node"
    return "Unknown"


def parse_bom(file_bytes: bytes, filename: str) -> dict:
    """
    Parse a BoM file (CSV or Excel) and validate devices.

    Returns:
        {
          "devices": [{model, serial, quantity, role, supported, matched_model}],
          "warnings": [str],
          "errors": [str],
          "gpu_count": int,
          "switch_count": int,
          "valid": bool,
        }
    """
    warnings = []
    errors = []
    devices = []

    # Parse file
    try:
        ext = filename.lower().rsplit(".", 1)[-1]
        if ext in ("xlsx", "xls"):
            df = pd.read_excel(io.BytesIO(file_bytes))
        elif ext == "csv":
            df = pd.read_csv(io.BytesIO(file_bytes))
        else:
            return {"devices": [], "warnings": [], "errors": [f"Unsupported file type: {ext}. Use .xlsx or .csv"], "gpu_count": 0, "switch_count": 0, "valid": False}
    except Exception as e:
        return {"devices": [], "warnings": [], "errors": [f"Failed to parse file: {str(e)}"], "gpu_count": 0, "switch_count": 0, "valid": False}

    # Strip whitespace from column names
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")

    # Find columns
    model_col = _find_column(df, MODEL_ALIASES)
    serial_col = _find_column(df, SERIAL_ALIASES)
    qty_col = _find_column(df, QTY_ALIASES)
    role_col = _find_column(df, ROLE_ALIASES)

    if not model_col:
        errors.append("Could not find a 'Model' column. Expected one of: Model, Device Model, Part Number, SKU")
        return {"devices": [], "warnings": warnings, "errors": errors, "gpu_count": 0, "switch_count": 0, "valid": False}

    if not qty_col:
        warnings.append("No 'Quantity' column found — assuming 1 unit per row.")

    gpu_count = 0
    switch_count = 0

    for _, row in df.iterrows():
        model = str(row.get(model_col, "")).strip()
        if not model or model.lower() in ("nan", ""):
            continue

        serial = str(row.get(serial_col, "")).strip() if serial_col else ""
        if serial.lower() == "nan":
            serial = ""

        try:
            qty = int(float(str(row.get(qty_col, 1)))) if qty_col else 1
            if qty <= 0:
                qty = 1
        except (ValueError, TypeError):
            qty = 1

        role = str(row.get(role_col, "")).strip() if role_col else ""
        if not role or role.lower() == "nan":
            role = _infer_role(model)

        matched = _fuzzy_match_model(model)
        supported = matched is not None

        if not supported:
            warnings.append(f"Unsupported device model: '{model}' — ZTP config may not be generated.")

        # Count GPUs (8 GPUs per compute node by default)
        if "compute" in role.lower() or "node" in role.lower() or "gpu" in role.lower() or "dgx" in model.upper() or "hgx" in model.upper():
            gpu_count += qty * 8
        elif "switch" in role.lower() or any(k in model.upper() for k in ["MQM", "DCS", "N9K"]):
            switch_count += qty

        devices.append({
            "model": model,
            "matched_model": matched or model,
            "serial": serial,
            "quantity": qty,
            "role": role,
            "supported": supported,
        })

    if not devices:
        errors.append("No valid devices found in the file.")

    return {
        "devices": devices,
        "warnings": warnings,
        "errors": errors,
        "gpu_count": gpu_count,
        "switch_count": switch_count,
        "valid": len(errors) == 0 and len(devices) > 0,
    }
