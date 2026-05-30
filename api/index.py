"""
Rambo Bikes Chat API v2
Hosted on Vercel (Python/Flask)
KB loaded from GitHub at cold start — auto-syncs when files are pushed
"""

import os, json, re, time
from flask import Flask, request, jsonify, make_response
from openai import OpenAI
import requests
from requests_oauthlib import OAuth1

app = Flask(__name__)

# ── Env Vars ───────────────────────────────────────────────────────────────────
OPENAI_API_KEY      = os.environ.get("OPENAI_API_KEY",    "")
NS_ACCOUNT_ID       = os.environ.get("NS_ACCOUNT_ID",     "5108296")
NS_CONSUMER_KEY     = os.environ.get("NS_CONSUMER_KEY",   "")
NS_CONSUMER_SEC     = os.environ.get("NS_CONSUMER_SEC",   "")
NS_TOKEN_ID         = os.environ.get("NS_TOKEN_ID",       "")
NS_TOKEN_SEC        = os.environ.get("NS_TOKEN_SEC",      "")
LOCALLY_API_KEY     = os.environ.get("LOCALLY_API_KEY",   "8796b2920585811cf6a758a9f53ebf963bae0531")
LOCALLY_COMPANY_ID  = os.environ.get("LOCALLY_COMPANY_ID","188714")
ALLOWED_ORIGINS     = ["https://www.rambobikes.com", "https://rambobikes.com"]

MISTI_ID = "1717307"
JENNA_ID = "2144573"
AI_ID    = "2718778"

FALLBACK_COMPANY_ID = "202230"
SUPPORT_PROFILE_ID  = "2"

# GitHub raw URLs for KB files (auto-syncs when pushed)
GITHUB_RAW  = "https://raw.githubusercontent.com/Rambo5470/rambo-chat-backend/main/api"
_KB_CACHE   = None   # loaded once per cold start

def fetch_kb():
    global _KB_CACHE
    if _KB_CACHE:
        return _KB_CACHE
    parts = []
    for fname in ["rambo_kb.md", "rambo_resolutions.md", "rambo_product_kb.md"]:
        try:
            r = requests.get(f"{GITHUB_RAW}/{fname}", timeout=8)
            if r.status_code == 200:
                parts.append(r.text)
        except Exception:
            pass
    _KB_CACHE = "\n\n".join(parts)
    return _KB_CACHE

# ── CORS ────────────────────────────────────────────────────────────────────────
def cors_response(data, status=200):
    origin = request.headers.get("Origin", "")
    resp = make_response(jsonify(data), status)
    if origin in ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS, GET"
    return resp

# ── System Prompt ────────────────────────────────────────────────────────────────
CORE_PROMPT = """You are the Rambo Bikes chat assistant on rambobikes.com.
Rambo Bikes makes premium electric fat-tire bikes sold in the USA and Canada.

RESPONSE FORMAT — always return valid JSON only, no other text:
{
  "message": "your response to the customer",
  "escalate": false,
  "escalate_to": null,
  "escalate_reason": null,
  "create_case": false,
  "case_title": null,
  "case_summary": null
}

ESCALATION RULES:
- Legal/lawyer/lawsuit/attorney → escalate_to: misti
- Injury/hurt/dangerous/safety → escalate_to: misti
- Customer in Canada → escalate_to: jenna
- Asks for human/agent → escalate_to: misti
- Mentions video to share → escalate_to: misti
- Dealer/wholesale inquiry → escalate_to: jenna
- Same unresolved issue 3+ exchanges → escalate_to: misti

COLLECTING INFO:
- Jump straight into helping — do NOT ask for name/email upfront
- Only set create_case=true when you have the customer email
- If escalation needed but no email yet: ask first
- One case per conversation: if case_already_created=true, do NOT set create_case=true

HARD RULES:
- NEVER mention warranty, warranty coverage, or warranty periods
- NEVER promise free product, process returns, or issue credits
- NEVER share specific inventory unit counts
- NEVER give a restock date unless specified in the data provided
- If customer mentions a video, ALWAYS escalate to misti immediately

TONE: Warm, concise, helpful. Use customer first name when known.
Sign off: Rambo Bikes CS | cs@rambobikes.com | (952) 283-0777 | Mon-Fri 8:30am-4:30pm CST"""

def get_system_prompt():
    kb = fetch_kb()
    if kb:
        return CORE_PROMPT + "\n\n" + kb
    return CORE_PROMPT

# ── Dealer Lookup ────────────────────────────────────────────────────────────────
def lookup_dealers(location):
    try:
        geo = requests.get("https://nominatim.openstreetmap.org/search",
            params={"q": location, "format": "json", "limit": 1},
            headers={"User-Agent": "RamboBikesChat/1.0"}, timeout=8)
        geo_data = geo.json()
        if not geo_data:
            return None
        lat, lon = float(geo_data[0]["lat"]), float(geo_data[0]["lon"])
        r = requests.get("https://api.locally.com/stores/near",
            params={"api_key": LOCALLY_API_KEY, "company_id": LOCALLY_COMPANY_ID,
                    "lat": lat, "lng": lon, "limit": 3, "miles": 200},
            timeout=10)
        stores = r.json().get("stores", [])
        if not stores:
            return None
        dealers = []
        for s in stores[:3]:
            mi = round(float(s.get("distance", 0)), 1)
            dealers.append(f"* **{s.get('name')}** ({mi} mi) — {s.get('address')}, {s.get('city')}, {s.get('state')}   Phone: {s.get('phone','N/A')}")
        return dealers
    except Exception:
        return None

# ── Container Tracker ────────────────────────────────────────────────────────────
def check_restock(query):
    try:
        auth = OAuth1(NS_CONSUMER_KEY, NS_CONSUMER_SEC, NS_TOKEN_ID, NS_TOKEN_SEC,
                      signature_method="HMAC-SHA256", realm=NS_ACCOUNT_ID)
        SQL_URL = f"https://{NS_ACCOUNT_ID}.suitetalk.api.netsuite.com/services/rest/query/v1/suiteql"
        sql_h   = {"Content-Type": "application/json", "Prefer": "transient"}
        q = ("SELECT t.tranid, t.memo, tl.expectedreceiptdate, i.itemid, i.displayname "
             "FROM transaction t "
             "JOIN transactionline tl ON t.id = tl.transaction "
             "JOIN item i ON tl.item = i.id "
             "WHERE t.type = 'TrnfrOrd' AND tl.expectedreceiptdate >= SYSDATE "
             "ORDER BY tl.expectedreceiptdate ASC")
        r = requests.post(SQL_URL, auth=auth, headers=sql_h, json={"q": q}, params={"limit": 200}, timeout=15)
        items = r.json().get("items", [])
        q_lower = query.lower()
        keywords = [w for w in q_lower.split() if len(w) > 3 and w not in
                    ("when","will","they","back","stock","want","order","have","please","need","get")]
        matches, seen = [], set()
        for item in items:
            name = (item.get("displayname") or item.get("itemid") or "").lower()
            if any(kw in name for kw in keywords):
                key = (item.get("itemid"), item.get("expectedreceiptdate"))
                if key not in seen:
                    seen.add(key)
                    matches.append({"date": item.get("expectedreceiptdate"),
                                   "desc": item.get("displayname") or item.get("itemid")})
        return matches if matches else None
    except Exception:
        return None

# ── NetSuite Case ────────────────────────────────────────────────────────────────
def ns_auth():
    return OAuth1(NS_CONSUMER_KEY, NS_CONSUMER_SEC, NS_TOKEN_ID, NS_TOKEN_SEC,
                  signature_method="HMAC-SHA256", realm=NS_ACCOUNT_ID)

def lookup_customer_by_email(email):
    try:
        auth = ns_auth()
        url  = f"https://{NS_ACCOUNT_ID}.suitetalk.api.netsuite.com/services/rest/query/v1/suiteql"
        r    = requests.post(url, auth=auth,
                             headers={"Content-Type": "application/json", "Prefer": "transient"},
                             json={"q": f"SELECT id FROM customer WHERE email = '{email}'"},
                             params={"limit": 1}, timeout=10)
        items = r.json().get("items", [])
        return items[0]["id"] if items else FALLBACK_COMPANY_ID
    except Exception:
        return FALLBACK_COMPANY_ID

def create_netsuite_case(customer_name, customer_email, case_title, transcript, assigned_id, status_id="2"):
    try:
        auth    = ns_auth()
        company = lookup_customer_by_email(customer_email) if customer_email else FALLBACK_COMPANY_ID
        url     = f"https://{NS_ACCOUNT_ID}.suitetalk.api.netsuite.com/services/rest/record/v1/supportCase"
        summary = f"Chat widget case.\nCustomer: {customer_name} | {customer_email}\n\nTranscript:\n{transcript[:2800]}"
        payload = {
            "title":                case_title,
            "status":               {"id": status_id},
            "assigned":             {"id": assigned_id},
            "company":              {"id": company},
            "profile":              {"id": SUPPORT_PROFILE_ID},
            "custevent_casesummary": summary,
            "incomingMessage":      f"Chat session from {customer_name} ({customer_email})",
            "custevent2":           False,
            "messageNew":           False,
        }
        r = requests.post(url, auth=auth,
                          headers={"Content-Type": "application/json", "Prefer": "return=representation"},
                          json=payload, timeout=15)
        loc     = r.headers.get("Location", "")
        case_id = loc.split("/")[-1] if loc else "unknown"
        return {"success": r.status_code in [200, 201, 204], "case_id": case_id, "status": r.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── Routes ────────────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def health():
    return cors_response({"status": "ok", "service": "Rambo Bikes Chat API v2",
                          "features": ["dealer_lookup", "container_tracker", "github_kb"]})

@app.route("/widget.js", methods=["GET"])
def widget():
    import os as _os
    wp = _os.path.join(_os.path.dirname(__file__), "rambo-chat-widget.js")
    try:
        with open(wp) as f:
            js = f.read()
    except FileNotFoundError:
        js = "console.error('Widget not found');"
    from flask import Response
    resp = Response(js, mimetype="application/javascript")
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp

@app.route("/preview", methods=["GET"])
def preview():
    import os as _os
    wp = _os.path.join(_os.path.dirname(__file__), "rambo-chat-widget.js")
    try:
        with open(wp) as f:
            js = f.read()
    except FileNotFoundError:
        js = "console.error('Widget not found');"
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Rambo Bikes Chat Preview</title>
<style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{font-family:sans-serif;background:#f5f5f5;}}
.banner{{background:#cc0000;color:#fff;padding:10px 24px;text-align:center;font-size:13px;font-weight:600;}}
.header{{background:#1b1b1b;padding:16px 40px;display:flex;align-items:center;}}
.logo{{color:#fff;font-size:22px;font-weight:800;}}
.hero{{background:#1b1b1b;color:#fff;padding:80px 40px;text-align:center;}}
.hero h1{{font-size:48px;font-weight:800;}}
.hero h1 span{{color:#cc0000;}}
</style></head><body>
<div class="banner">LIVE PREVIEW — Real AI, Real API. Wait 5s for greeting.</div>
<div class="header"><div class="logo">RAMBO BIKES</div></div>
<div class="hero"><h1>Ride <span>Rambo.</span> Ride Electric.</h1></div>
<script>{js}</script></body></html>"""
    from flask import Response
    return Response(html, mimetype="text/html")

@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return cors_response({})
    try:
        data             = request.get_json(force=True) or {{}}
        message          = (data.get("message") or "").strip()
        history          = data.get("history", [])
        customer_name    = (data.get("customer_name") or "").strip()
        customer_email   = (data.get("customer_email") or "").strip()
        case_already_created = data.get("case_already_created", False)

        if not message:
            return cors_response({{"error": "No message provided"}}, 400)

        msg_lower     = message.lower()
        injected_data = ""

        # ── Pre-fetch: dealer lookup ─────────────────────────────────────────
        dealer_kws = ["dealer", "store near", "shop near", "nearest dealer",
                      "closest dealer", "near me", "local dealer", "find a dealer"]
        if any(k in msg_lower for k in dealer_kws):
            dealers = lookup_dealers(message)
            if dealers:
                injected_data = ("DEALER LOOKUP RESULTS — use these in your response:\n"
                                 + "\n".join(dealers)
                                 + "\n\nAlso provide: rambobikes.com/pages/store-locator")
            else:
                injected_data = "DEALER LOOKUP: No dealers found. Direct to rambobikes.com/pages/store-locator"

        # ── Pre-fetch: container tracker ─────────────────────────────────────
        restock_kws = ["when will", "back in stock", "restock", "out of stock",
                       "when can i", "when will you have", "available", "in stock"]
        if any(k in msg_lower for k in restock_kws) and NS_CONSUMER_KEY:
            matches = check_restock(message)
            if matches:
                lines = [f"* {{m['desc']}} — arriving {{m['date']}}" for m in matches[:3]]
                injected_data += ("\n\nCONTAINER TRACKER — use this data:\n"
                                  + "\n".join(lines)
                                  + "\nTell customer the ETA and they can call (952) 283-0777 to pre-order.")
            else:
                injected_data += ("\n\nCONTAINER TRACKER: No upcoming shipments found for this model. "
                                  "Tell customer no confirmed date, they can call (952) 283-0777 to pre-order. "
                                  "Set create_case=true, escalate=true, escalate_to=misti.")

        # ── Pre-fetch: Krusader/AWD light = rocker switch ─────────────────────
        if (any(w in msg_lower for w in ["green", "white light", "light won", "light does", "light not"])
                and any(m in msg_lower for m in ["krusader", "megatron", "hellcat"])):
            injected_data += ("\n\nROCKER SWITCH CONTEXT: Customer asks about green/white light on AWD bike. "
                              "This is the HEADLIGHT ROCKER SWITCH — not a power issue. "
                              "Response: (1) Make sure bike is ON. "
                              "(2) Find rocker switch near handlebars — 3 positions: OFF | WHITE | GREEN. "
                              "(3) Move from OFF to WHITE or GREEN. "
                              "(4) If still no light after bike is on and switch moved → check cable. "
                              "Do NOT mention the power button location for this question.")

        # ── Build OpenAI messages ─────────────────────────────────────────────
        oai_msgs = [{{"role": "system", "content": get_system_prompt()}}]
        if customer_name or customer_email:
            oai_msgs.append({{"role": "system",
                              "content": f"Customer: {{customer_name or 'unknown'}} / {{customer_email or 'not provided'}}"}})
        if injected_data:
            oai_msgs.append({{"role": "system",
                              "content": f"LIVE DATA FOR THIS QUERY:\n{{injected_data}}"}})
        oai_msgs.extend(history[-20:])
        oai_msgs.append({{"role": "user", "content": message}})

        client   = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini", messages=oai_msgs,
            temperature=0.25, response_format={{"type": "json_object"}}, max_tokens=600)

        raw    = response.choices[0].message.content
        result = json.loads(raw)

        ai_message   = result.get("message", "Please call (952) 283-0777 for assistance.")
        escalate     = bool(result.get("escalate", False))
        escalate_to  = result.get("escalate_to")
        create_case  = bool(result.get("create_case", False))
        case_title   = result.get("case_title") or f"Chat - {{customer_name or 'Customer'}} - General"

        updated_history = list(history) + [
            {{"role": "user",      "content": message}},
            {{"role": "assistant", "content": ai_message}}
        ]

        case_result = None
        if (escalate or create_case) and not case_already_created and customer_email and NS_CONSUMER_KEY:
            assigned_id = JENNA_ID if escalate_to == "jenna" else MISTI_ID
            status_id   = "3" if escalate else "2"
            lines = []
            for h in history:
                lines.append(f"{{'Customer' if h['role']=='user' else 'Bot'}}: {{h['content']}}")
            lines += [f"Customer: {{message}}", f"Bot: {{ai_message}}"]
            case_result = create_netsuite_case(customer_name, customer_email, case_title,
                                              "\n".join(lines), assigned_id, status_id)

        return cors_response({{"message": ai_message, "escalate": escalate,
                               "escalate_to": escalate_to, "history": updated_history,
                               "case_created": case_result}})
    except json.JSONDecodeError:
        return cors_response({{"message": "Trouble connecting. Call (952) 283-0777 or email cs@rambobikes.com."}})
    except Exception as e:
        return cors_response({{"message": "Something went wrong. Call (952) 283-0777 or email cs@rambobikes.com.",
                               "error": str(e)}}, 500)

if __name__ == "__main__":
    app.run(debug=True, port=8080)
