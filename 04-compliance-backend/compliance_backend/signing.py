import hashlib
import hmac
import os
from datetime import UTC, datetime


# reads form env var SIGNING_KEY
def get_signing_key():
    return os.environ.get("SIGNING_KEY", "dev-secret")


# turns a datetime into text in one fixed format
def format_timestamp(timestamp: datetime) -> str:
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return timestamp.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# returns an HMAC-SHA256 signature over the key fields of an event.
# only someone who knows the secret key can create a matching signature, so a changed row no longer matches its signature.
def sign(
    event_id: str,
    timestamp: datetime,
    model_name: str,
    model_version: str,
    input_data_hash: str,
) -> str:
    message = "|".join([
        event_id,
        format_timestamp(timestamp),
        model_name,
        model_version,
        input_data_hash,
    ])
    return hmac.new(
        get_signing_key().encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
