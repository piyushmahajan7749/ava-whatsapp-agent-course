"""Google Sheets integration for booking logs."""

from ai_companion.modules.sheets.sheets_manager import (
    log_consultation_booking,
    log_product_order,
    get_sheets_config,
)

__all__ = [
    "log_consultation_booking",
    "log_product_order",
    "get_sheets_config",
]

