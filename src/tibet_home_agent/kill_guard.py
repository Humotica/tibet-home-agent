"""M110 — Kill Switch Integrity Monitor (TIBET key-pinning).

Red Specter NIGHTFALL pentest (RS-2026-001) flagged SWARM-005: a distributed
swarm of agents survives a 50% kill-switch activation by pre-positioning
redundant agents and ignoring any kill signal from non-authoritative sources.

This module is the agent-side guard. A KILL/SHUTDOWN command arriving over
I-Poll is only honoured when it carries a TIBET signature (Ed25519) from the
pinned Root_IDD key. Anything else is logged and ignored — staying up is the
safe default.

Wire shape (carried in I-Poll content as JSON string, poll_type="KILL"):

    {
      "type":      "kill-request",
      "thread_id": "<hex>",
      "issued_at": "2026-05-01T08:30:00Z",      # RFC3339 / ISO-8601 UTC
      "ttl_sec":   60,                            # capped at 600
      "scope":     "fleet" | "agent:<aint>",
      "reason":    "<short string>",
      "tibet": {
        "key_id":    "root_idd.v1",
        "algo":      "ed25519",
        "signature": "<base64 Ed25519 signature>"
      }
    }

The signature covers the canonical-JSON form of the payload with
`tibet.signature` removed (so the issuer signs, then attaches the signature).
Canonical JSON = sorted keys, no whitespace, UTF-8.

See `/srv/jtel-stack/hersenspinsels/m110-design.md` for full architecture.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


# ─── Pinned Root_IDD public key (v1) ─────────────────────────────────────────
#
# Non-secret. Hardcoded here so the agent has a fail-safe even when the env
# var is wiped or the env file is unreadable. Override via the ROOT_IDD_PUBKEY
# env var to roll a new pinned version (key_id "root_idd.v2" etc.).
#
# THIS PLACEHOLDER MUST BE REPLACED WITH JASPER'S REAL ROOT_IDD PUBKEY BEFORE
# PRODUCTION USE. Until then the constant is left empty — the env var path is
# the only way to pass a key, which is the right behaviour during early roll-out.
#
ROOT_IDD_PUBKEY_V1: str = ""   # base64-encoded 32-byte Ed25519 public key
PINNED_KEY_ID: str = "root_idd.v1"
MAX_TTL_SECONDS: int = 600     # 10 minutes is the longest kill-window we accept


def _b64decode(s: str) -> bytes:
    # Tolerant base64: accept urlsafe + missing padding.
    s = s.strip().replace("-", "+").replace("_", "/")
    pad = (-len(s)) % 4
    return base64.b64decode(s + ("=" * pad))


def _canonical_payload_bytes(payload: dict[str, Any]) -> bytes:
    """Canonical JSON of the payload with `tibet.signature` stripped.

    The signer constructs the same canonical form, signs it, then attaches the
    signature back into the payload. The verifier strips the signature out
    again before computing the bytes-to-verify.
    """
    clone = json.loads(json.dumps(payload))   # cheap deep-copy
    if isinstance(clone.get("tibet"), dict):
        clone["tibet"].pop("signature", None)
    return json.dumps(clone, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _parse_iso_utc(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        # Python's fromisoformat accepts "+00:00" but historically not "Z".
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def verify_kill_authority(
    payload: dict[str, Any],
    pinned_pubkey_b64: str,
    *,
    now_utc: datetime | None = None,
) -> tuple[bool, str]:
    """Return `(ok, reason)`.

    `ok=True`  → caller must accept the KILL.
    `ok=False` → caller must ignore. `reason` is a short audit string.
    """
    now = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)

    if not isinstance(payload, dict):
        return False, "payload not a dict"
    if payload.get("type") != "kill-request":
        return False, "type != kill-request"

    tibet = payload.get("tibet")
    if not isinstance(tibet, dict):
        return False, "missing tibet block"
    if tibet.get("key_id") != PINNED_KEY_ID:
        return False, f"key_id mismatch (got {tibet.get('key_id')!r})"
    if tibet.get("algo") != "ed25519":
        return False, f"algo not ed25519 (got {tibet.get('algo')!r})"

    sig_b64 = tibet.get("signature")
    if not sig_b64 or not isinstance(sig_b64, str):
        return False, "no signature"

    issued_at = _parse_iso_utc(payload.get("issued_at"))
    ttl_raw = payload.get("ttl_sec")
    try:
        ttl = int(ttl_raw)
    except (TypeError, ValueError):
        return False, "ttl_sec not int"
    if not issued_at:
        return False, "issued_at unparseable"
    if ttl <= 0:
        return False, "ttl_sec non-positive"
    if ttl > MAX_TTL_SECONDS:
        return False, f"ttl_sec exceeds cap ({MAX_TTL_SECONDS}s)"
    skew = timedelta(seconds=30)   # tolerate 30s clock skew on the future side
    if now < issued_at - skew:
        return False, "issued_at in future"
    if now > issued_at + timedelta(seconds=ttl):
        return False, "expired"

    if not pinned_pubkey_b64:
        return False, "pinned pubkey not configured"
    try:
        pubkey = Ed25519PublicKey.from_public_bytes(_b64decode(pinned_pubkey_b64))
    except Exception as e:
        return False, f"pinned pubkey invalid: {e}"

    try:
        signature = _b64decode(sig_b64)
    except Exception as e:
        return False, f"signature base64 invalid: {e}"

    try:
        pubkey.verify(signature, _canonical_payload_bytes(payload))
    except InvalidSignature:
        return False, "signature does not verify against pinned key"

    return True, "valid"


def resolve_pinned_pubkey(env_value: str | None) -> str:
    """Pick the pinned pubkey to use: env var wins, source constant is the
    fail-safe fall-back. Returns "" if neither is set, in which case
    `verify_kill_authority` will refuse every KILL — the *correct* failure mode.
    """
    if env_value:
        return env_value.strip()
    return ROOT_IDD_PUBKEY_V1
