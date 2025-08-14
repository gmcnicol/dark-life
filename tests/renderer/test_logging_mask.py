import json
import logging

from shared.config import settings
from shared.logging import log_info


def test_log_masks_secrets(monkeypatch, caplog):
    """Ensure secret tokens are not emitted in log entries."""

    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "sekrit")
    monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", "apikey")

    caplog.set_level(logging.INFO)
    log_info("test", api_token=settings.API_AUTH_TOKEN, other=settings.ELEVENLABS_API_KEY)

    record = caplog.records[0]
    msg = json.loads(record.message)
    assert msg["api_token"] == "[MASKED]"
    assert msg["other"] == "[MASKED]"
    assert "sekrit" not in record.message
    assert "apikey" not in record.message

