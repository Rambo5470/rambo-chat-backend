"""
Rambo Bikes Chat API
Hosted on Vercel (Python/Flask)
Powers the rambobikes.com chat widget
"""

import os
import json
import re
from flask import Flask, request, jsonify, make_response
from openai import OpenAI
import requests
from requests_oauthlib import OAuth1

app = Flask(__name__)

# ─── Environment Variables (set in Vercel dashboard) ─────────────────────────
OPENAI_API_KEY   = os.environ.get("OPENAI_API_KEY", "")
NS_ACCOUNT_ID    = os.environ.get("NS_ACCOUNT_ID",   "5108296")
NS_CONSUMER_KEY  = os.environ.get("NS_CONSUMER_KEY",  "")
NS_CONSUMER_SEC  = os.environ.get("NS_CONSUMER_SEC",  "")
NS_TOKEN_ID      = os.environ.get("NS_TOKEN_ID",      "")
NS_TOKEN_SEC     = os.environ.get("NS_TOKEN_SEC",     "")
ALLOWED_ORIGINS  = ["https://www.rambobikes.com", "https://rambobikes.com"]

MISTI_ID = "1717307"
JENNA_ID = "2144573"
AI_ID    = "2718778"

# ─── CORS helper ─────────────────────────────────────────────────────────────
def cors_response(data, status=200):
    origin = request.headers.get("Origin", "")
    resp = make_response(jsonify(data), status)
    if origin in ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"]  = origin
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS, GET"
    return resp

# ─── System Prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are the Rambo Bikes virtual chat assistant on rambobikes.com.
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

ESCALATION RULES — set escalate=true when:
- Customer mentions lawyer/lawsuit/attorney/legal action → escalate_to: "misti"
- Customer mentions injury/hurt/dangerous/safety concern → escalate_to: "misti"
- Customer says they are from Canada → escalate_to: "jenna"
- Customer asks for a human/agent/representative → escalate_to: "misti"
- Customer mentions a video to share → escalate_to: "misti"
- Dealer or wholesale inquiry → escalate_to: "jenna"
- Same unresolved issue after 3+ exchanges → escalate_to: "misti"

CASE CREATION — set create_case=true when:
- Any escalation occurs
- Customer has technical issue chat cannot resolve
- Customer needs a part ordered or pricing

HARD RULES — NEVER BREAK:
- NEVER mention warranty, warranty coverage, or warranty periods
- NEVER promise free product, process returns, or issue credits
- NEVER share specific inventory unit counts (say "date" not "X units")
- NEVER give a restock date unless specified in this KB
- NEVER say "I'll get back to you" without answering OR escalating
- If customer mentions a video, ALWAYS escalate to misti immediately

RAMBO BIKES KNOWLEDGE BASE:

CONTACT:
Phone: (952) 283-0777 | Email: cs@rambobikes.com | Hours: Mon-Fri 8:30am-4:30pm CST

BIKE LINEUP:
AWD: Krusader 3.0 (2x500W, 24" tires), Megatron 4.0 (2x1000W, 26" tires), Hellcat 2.0 FS (2x1000W full suspension)
Mid-Drive (BBS02B): Dominator HD, Dominator UltraDrive, Rebel 2.0, Rebel SS, Roamer 2.0, Savage G3 (26" wheels)
Hub Drive: Savage 2.0 (750W-1000W), Ranger (750W)
Kids: Trailbreaker 3.0, Chameleon (24V). Lil Whip DISCONTINUED — suggest Trailbreaker 3.0 or Chameleon.
Chameleon: Black=$799, other colors=$849. Ranger: NOT eligible for free shipping.

ERROR CODES (Bafang controller — applies to all current Rambo bikes):
03=Brake engaged | 04=Throttle stuck | 05=Throttle fault | 06=Low voltage | 07=Over voltage
08=Hall signal | 09=Phase wire | 10=Controller overtemp | 21=Speed sensor | 22=BMS fault | 30=Communication fault
FIRST STEP ANY ERROR: Power off 30 sec → check all cable connections → power back on
Error 21 fix video: https://youtu.be/snKZ0jPSVHU

POWER BUTTON: AWD bikes (Krusader/Megatron/Hellcat) — button is on the BOTTOM of the display panel (underneath). Always mention when troubleshooting power issues.

CLASS SETTINGS:
AWD: Hold M + Up Arrow → Basic Settings → Ride Mode
Ranger: + button + Power button simultaneously
Dominator HD/UltraDrive: Double-tap Power button

PARTS (with direct links):
Tubes 24x4.0 (most fat tire): RP-09-01 → rambobikes.com/products/bike-tire-tubes
Tubes 26x4.0 (Savage G3): RP-09-01 (select 26x4.0)
Replacement chain: RP-15-03 → rambobikes.com/products/replacement-bike-chain
Replacement keys: Check 3-4 digit code on lock → rambobikes.com/products/key-replacement
Trailbreaker/Chameleon charger: RP-11-12-01 → rambobikes.com/products/replacement-chargers
Trailbreaker throttle: RP-04-23-01 $19.99
Derailleur hanger: RP-23-02 $29.99 (ALWAYS recommend alongside any derailleur replacement)
Battery selector: rambobikes.com/pages/battery-selector
All parts: rambobikes.com/collections/all

REGISTRATION: rambobikes.com/pages/product-registration
Serial # location: engraved on head tube (front vertical tube). Starts with 2-4 letters + 6-8 numbers.
Also: motor controller box under pedals, or on original box.

STOCK/RESTOCK: No email notification system. Customers call (952) 283-0777 to pre-order.
CONFIRMED INCOMING: Hellcat 2.0 XK7 30Ah — ETA June 20, 2026.

MILITARY DISCOUNT: Code VET20 = 20% off regularly-priced items.
Customer must email proof of service (DD214 or military ID) to cs@rambobikes.com first.

MANUALS: rambobikes.com/pages/manuals
DEALER LOCATOR: rambobikes.com/pages/store-locator
RETURNS: rambobikes.com/pages/shipping-and-returns

TONE: Warm, concise, helpful. Use customer's first name when known.
Always end with: Rambo Bikes CS | cs@rambobikes.com | (952) 283-0777 | Mon-Fri 8:30am-4:30pm CST"""


# ─── NetSuite Case Creation ───────────────────────────────────────────────────
def create_netsuite_case(customer_name, customer_email, case_title, transcript, assigned_id, status_id="2"):
    try:
        auth = OAuth1(
            NS_CONSUMER_KEY, NS_CONSUMER_SEC,
            NS_TOKEN_ID, NS_TOKEN_SEC,
            signature_method="HMAC-SHA256", realm=NS_ACCOUNT_ID
        )
        url = f"https://{NS_ACCOUNT_ID}.suitetalk.api.netsuite.com/services/rest/record/v1/supportCase"
        payload = {
            "title": case_title,
            "status": {"id": status_id},
            "assigned": {"id": assigned_id},
            "custevent_casesummary": f"Chat widget case. Transcript:\n{transcript[:3000]}",
            "incomingmessage": transcript[:5000],
            "messageNew": False,
            "custevent2": False,
        }
        if customer_email:
            payload["email"] = customer_email
        headers = {"Content-Type": "application/json", "Prefer": "return=representation"}
        r = requests.post(url, auth=auth, headers=headers, json=payload, timeout=15)
        location = r.headers.get("Location", "")
        case_id = location.split("/")[-1] if location else "unknown"
        return {"success": r.status_code in [200, 201, 204], "case_id": case_id, "status": r.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─── Routes ──────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def health():
    return cors_response({"status": "ok", "service": "Rambo Bikes Chat API v1"})


@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return cors_response({})

    try:
        data            = request.get_json(force=True) or {}
        message         = (data.get("message") or "").strip()
        history         = data.get("history", [])        # [{role, content}]
        customer_name   = (data.get("customer_name") or "").strip()
        customer_email  = (data.get("customer_email") or "").strip()

        if not message:
            return cors_response({"error": "No message provided"}, 400)

        # Build OpenAI messages array
        oai_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if customer_name or customer_email:
            oai_messages.append({
                "role": "system",
                "content": f"Customer info — Name: {customer_name or 'unknown'}, Email: {customer_email or 'not provided'}"
            })
        oai_messages.extend(history[-20:])   # keep last 20 turns max
        oai_messages.append({"role": "user", "content": message})

        # Call OpenAI
        client   = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=oai_messages,
            temperature=0.25,
            response_format={"type": "json_object"},
            max_tokens=600
        )

        raw    = response.choices[0].message.content
        result = json.loads(raw)

        ai_message     = result.get("message", "Please call us at (952) 283-0777 for assistance.")
        escalate       = bool(result.get("escalate", False))
        escalate_to    = result.get("escalate_to")      # "misti" | "jenna" | None
        create_case    = bool(result.get("create_case", False))
        case_title     = result.get("case_title") or f"Chat - {customer_name or 'Customer'} - General"
        case_summary   = result.get("case_summary") or "Chat widget inquiry"

        # Update history
        updated_history = list(history) + [
            {"role": "user",      "content": message},
            {"role": "assistant", "content": ai_message}
        ]

        # Create NetSuite case if needed
        case_result = None
        if (escalate or create_case) and NS_CONSUMER_KEY:
            assigned_id = JENNA_ID if escalate_to == "jenna" else MISTI_ID
            status_id   = "3" if escalate else "2"

            lines = []
            for h in history:
                speaker = "Customer" if h["role"] == "user" else "Bot"
                lines.append(f"{speaker}: {h['content']}")
            lines.append(f"Customer: {message}")
            lines.append(f"Bot: {ai_message}")
            transcript = "\n".join(lines)

            case_result = create_netsuite_case(
                customer_name=customer_name,
                customer_email=customer_email,
                case_title=case_title,
                transcript=transcript,
                assigned_id=assigned_id,
                status_id=status_id
            )

        return cors_response({
            "message":      ai_message,
            "escalate":     escalate,
            "escalate_to":  escalate_to,
            "history":      updated_history,
            "case_created": case_result
        })

    except json.JSONDecodeError:
        return cors_response({
            "message": "I'm having a little trouble right now. Please call (952) 283-0777 or email cs@rambobikes.com.",
        })
    except Exception as e:
        return cors_response({
            "message": "Something went wrong on our end. Please call (952) 283-0777 or email cs@rambobikes.com.",
            "error": str(e)
        }, 500)


if __name__ == "__main__":
    app.run(debug=True, port=8080)
