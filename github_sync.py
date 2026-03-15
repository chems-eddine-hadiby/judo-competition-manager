# -*- coding: utf-8 -*-
"""
github_sync.py — Sync competition JSON files to a private GitHub repo.
Uses GitHub Contents API (no external deps).
"""
import base64
import json
import re
import urllib.request
import urllib.error

REPO = "chems-eddine-hadiby/judo-competitions"
API_ROOT = f"https://api.github.com/repos/{REPO}/contents"

def _request(method, path, token="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", data=None):
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
    try:
        with urllib.request.urlopen(req) as resp:
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
