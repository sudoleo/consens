"""Alerts fuer unerwartete Fehler, die ein Codepfad abfaengt und nur loggt.

Die SSE-Streams fangen ihre Fehler selbst (der Nutzer bekommt ein sauberes
Fehler-Event statt eines abgerissenen Streams). Damit erreicht ein echter
Programmierfehler dort nie den globalen Exception-Handler und blieb bisher
eine Log-Zeile, die niemand sieht. ``report_server_exception`` schickt genau
diese Faelle in dieselbe Alert-Form wie ein 500er -- und nur diese:
Abbrueche, Provider-/Netzfehler, Timeouts und Domaenenfehler sind erwartbar
und bleiben beim Log (siehe ``error_context.is_unexpected_exception``).
"""

from __future__ import annotations

import logging

from app.core.error_context import is_unexpected_exception, server_error_report
from app.core.observability import safe_exception
from app.services.telegram_notifier import dispatch_critical_error_notification


def report_server_exception(exc: BaseException, *, where: str, phase: str = "stream") -> dict | None:
    """Alarmiert bei einem Programmierfehler; gibt sonst ``None`` zurueck.

    ``where`` ist ein fester Bezeichner der Codestelle (z. B.
    ``"chat.consensus_stream"``), nie ein Wert aus dem Request. Wirft nie.
    """
    if not is_unexpected_exception(exc):
        return None
    try:
        return dispatch_critical_error_notification(server_error_report(
            exc,
            phase=phase,
            path=where,
            message="Unexpected exception in a handled server path (the request continued).",
        ))
    except Exception as alert_error:
        logging.warning(
            "Server exception alert failed where=%s category=%s",
            where,
            safe_exception(alert_error),
        )
        return None
