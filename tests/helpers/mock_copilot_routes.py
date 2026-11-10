"""tests.helpers.mock_copilot_routes -- the POST routes of tests/helpers/mock_copilot.py (Halo 3.3.17.0 R1).

Failure modes (`mock.scenario[<endpoint>] = <mode>`, consumed by one call; a trailing "!" keeps it):

    token        consent (AADSTS65001 on any grant)
    workiq       401 | 403-consent | 403-licence | 402 | 429 (Retry-After: 0) | rpc-error
    chat         401 | 403-licence | 429
"""

from __future__ import annotations

from tests.helpers.mock_copilot import CLIENT_ID, pkce_ok


def _bearer(handler) -> str:
    auth = handler.headers.get("Authorization") or ""
    return auth[7:] if auth.startswith("Bearer ") else ""


def token(mock, h, body):
    if body.get("client_id") != CLIENT_ID:
        return h._send(400, {"error": "unauthorized_client", "error_description": "AADSTS700016: unknown app"})
    if mock.take("token") == "consent":
        return h._send(400, {"error": "invalid_grant", "error_description": "AADSTS65001: The user or administrator "
                             "has not consented to use the application with ID '00000000-0000-0000-0000-000000000000'."})
    grant = body.get("grant_type")
    if grant == "authorization_code":
        got = mock.codes.pop(body.get("code"), None)
        if got is None:
            return h._send(400, {"error": "invalid_grant", "error_description": "AADSTS70000: unknown code"})
        challenge, redirect_uri, method = got
        if method != "S256" or not pkce_ok(body.get("code_verifier", ""), challenge):
            return h._send(400, {"error": "invalid_grant", "error_description": "AADSTS501481: the code_verifier "
                                 "does not match the code_challenge"})
        if body.get("redirect_uri") != redirect_uri:
            return h._send(400, {"error": "invalid_grant", "error_description": "AADSTS50148: redirect_uri mismatch"})
        return h._send(200, mock.tokens())
    if grant == "refresh_token":
        rt = body.get("refresh_token")
        if rt in mock.revoked or rt not in mock.refresh:
            return h._send(400, {"error": "invalid_grant", "error_description": "AADSTS70008: The provided "
                                 "authorization code or refresh token has expired due to inactivity."})
        return h._send(200, mock.tokens())
    if grant == "urn:ietf:params:oauth:grant-type:device_code":
        mock.device_polls += 1
        if mock.device_polls <= 2:
            return h._send(400, {"error": "authorization_pending", "error_description": "AADSTS70016: pending"})
        return h._send(200, mock.tokens())
    return h._send(400, {"error": "unsupported_grant_type"})


def devicecode(mock, h, body):
    mock.device_polls = 0
    return h._send(200, {"device_code": "dc-1", "user_code": "PRETEND1", "verification_uri":
                         "https://microsoft.com/devicelogin", "interval": 0, "expires_in": 900,
                         "message": "To sign in, open https://microsoft.com/devicelogin and enter PRETEND1."})


def _authorized(mock, h) -> bool:
    if _bearer(h) in mock.access:
        return True
    h._send(401, {"error": {"code": "InvalidAuthenticationToken", "message": "Access token is empty or invalid."}})
    return False


def workiq(mock, h, body):
    mode = mock.take("workiq")
    if mode == "401":
        return h._send(401, {"error": {"code": "Unauthorized", "message": "The token is not valid for Work IQ."}})
    if mode == "403-consent":
        return h._send(403, {"error": {"code": "Forbidden", "message": "AADSTS65001: consent required for the Work IQ scope"}})
    if mode == "403-licence":
        return h._send(403, {"error": {"code": "Forbidden", "message": "The user has no Microsoft 365 Copilot license."}})
    if mode == "402":
        return h._send(402, {"error": {"code": "PaymentRequired", "message": "Consumptive billing is not enabled for this tenant."}})
    if mode == "429":
        return h._send(429, {"error": {"code": "TooManyRequests", "message": "slow down"}}, {"Retry-After": "0"})
    if h.headers.get("A2A-Version") != "1.0":
        return h._send(400, {"error": {"code": "BadRequest", "message": "A2A-Version 1.0 required"}})
    if not _authorized(mock, h):
        return None
    if mode == "rpc-error":
        return h._send(200, {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32001, "message":
                             "Consumptive billing is not enabled", "data": {"status": 402}}})
    msg = (body.get("params") or {}).get("message") or {}
    ctx = msg.get("contextId") or "ctx-1"
    tz = (((body.get("params") or {}).get("metadata") or {}).get("Location") or {}).get("timeZone")
    text = " ".join(p.get("text", "") for p in msg.get("parts") or [])
    return h._send(200, {"jsonrpc": "2.0", "id": body.get("id"), "result": {"message": {
        "role": "ROLE_AGENT", "messageId": "m-reply", "contextId": ctx,
        "parts": [{"text": f"Work IQ heard: {text} (tz {tz})"},
                  {"data": {"citations": [{"title": "Q3 plan.docx", "url": "https://pretend.sharepoint.com/q3.docx"},
                                          {"title": "Standup notes", "url": "https://pretend.sharepoint.com/notes"}]}}],
        "metadata": {"sensitivityLabel": {"displayName": "General"}}}}})


def chat(mock, h, body, path):
    mode = mock.take("chat")
    if mode == "401":
        return h._send(401, {"error": {"code": "InvalidAuthenticationToken", "message": "expired"}})
    if mode == "403-licence":
        return h._send(403, {"error": {"code": "Forbidden", "message": "The user does not have a Microsoft 365 Copilot license."}})
    if mode == "429":
        return h._send(429, {"error": {"code": "TooManyRequests", "message": "throttled"}}, {"Retry-After": "0"})
    if not _authorized(mock, h):
        return None
    if path.rstrip("/") == "/beta/copilot/conversations":
        return h._send(201, {"id": "conv-1", "state": "active"})
    text = (body.get("message") or {}).get("text") or ""
    res = body.get("contextualResources") or {}
    files = [f.get("uri") for f in res.get("files") or []]
    web = (res.get("webContext") or {}).get("isWebEnabled")
    tz = (body.get("locationHint") or {}).get("timeZone")
    said = f"Copilot heard: {text} (tz {tz})" + (f" files: {', '.join(files)}" if files else "") + ("" if web else " web off")
    return h._send(200, {"id": "conv-1", "messages": [
        {"@odata.type": "#microsoft.graph.copilotConversationRequestMessage", "id": "u1", "text": text},
        {"@odata.type": "#microsoft.graph.copilotConversationResponseMessage", "id": "r1", "text": said,
         "attributions": [{"attributionType": "citation", "providerDisplayName": "Budget.xlsx",
                           "seeMoreWebUrl": "https://pretend.sharepoint.com/budget.xlsx"},
                          {"attributionType": "citation", "providerDisplayName": "Team meeting",
                           "seeMoreWebUrl": "https://pretend.sharepoint.com/meeting"}],
         "sensitivityLabel": {"displayName": "Confidential"}}]})
