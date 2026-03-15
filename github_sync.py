# -*- coding: utf-8 -*-
"""
github_sync.py — Sync competition JSON files to a private GitHub repo.
Uses GitHub Contents API (no external deps).
"""
import base64
import json
import re
import time
from datetime import datetime, timezone
import urllib.request
import urllib.error
import certifi
import ssl

REPO = "chems-eddine-hadiby/judo-competitions"
API_ROOT = f"https://api.github.com/repos/{REPO}/contents"

def _request(method, path, token, data=None):
    url = f"{API_ROOT}/{path}".rstrip("/")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "JudoManager",
    }
    if token:
        headers["Authorization"] = f"token {token}"
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    ctx = ssl.create_default_context(cafile=certifi.where())
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        status = getattr(e, "code", "unknown")
        body = ""
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = ""
        msg = ""
        try:
            detail = json.loads(body) if body else {}
            msg = detail.get("message") or str(e)
        except Exception:
            msg = str(e)
        raise RuntimeError(f"{status} {msg}".strip())

def sanitize_folder_name(name: str) -> str:
    if not name:
        return ""
    name = re.sub(r"\s+", "-", name.strip())
    name = re.sub(r"[^A-Za-z0-9._-]+", "", name)
    return name.strip("-")

def sanitize_key(name: str) -> str:
    return sanitize_folder_name(name)

def list_competitions(token):
    items = _request("GET", "", token)
    return [it["name"] for it in items if it.get("type") == "dir"]

def get_json(token, folder, filename):
    data = _request("GET", f"{folder}/{filename}", token)
    content = data.get("content", "")
    raw = base64.b64decode(content).decode("utf-8")
    return json.loads(raw)

def _get_sha(token, folder, filename):
    try:
        data = _request("GET", f"{folder}/{filename}", token)
        return data.get("sha")
    except RuntimeError:
        return None

def put_json(token, folder, filename, obj, message):
    content = json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8")
    b64 = base64.b64encode(content).decode("ascii")
    payload = {"message": message, "content": b64}
    sha = _get_sha(token, folder, filename)
    if sha:
        payload["sha"] = sha
    return _request("PUT", f"{folder}/{filename}", token, payload)

def delete_file(token, folder, filename, message):
    sha = _get_sha(token, folder, filename)
    if not sha:
        return False
    payload = {"message": message, "sha": sha}
    _request("DELETE", f"{folder}/{filename}", token, payload)
    return True

def lock_match(token, folder, lock_key, owner, ttl_seconds=900):
    now = time.time()
    expires_at = datetime.fromtimestamp(now + ttl_seconds, tz=timezone.utc).isoformat()
    path = f"locks/{lock_key}.json"
    existing = None
    try:
        existing = get_json(token, folder, path)
    except Exception:
        existing = None
    if isinstance(existing, dict):
        exp = existing.get("expires_at")
        try:
            exp_ts = datetime.fromisoformat(exp.replace("Z", "+00:00")).timestamp() if exp else 0
        except Exception:
            exp_ts = 0
        if exp_ts and exp_ts > now and existing.get("owner") != owner:
            return False, existing
    payload = {
        "owner": owner,
        "expires_at": expires_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    put_json(token, folder, path, payload, f"Lock {lock_key}")
    return True, payload

def release_lock(token, folder, lock_key):
    path = f"locks/{lock_key}.json"
    try:
        return delete_file(token, folder, path, f"Unlock {lock_key}")
    except Exception:
        return False
