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
NS_CONSUMER_KEY     = os.environ.get("NS_CONSUMER_KEY",   "62dcb9b1151f4ce47301b73765b8438874992d57d0ca57fa05f78aa994e14ba0")
NS_CONSUMER_SEC     = os.environ.get("NS_CONSUMER_SEC",   "35f728cf6037c3b422df23233765e2418441f82cba98e90d4bc18ac4b9197cb7")
NS_TOKEN_ID         = os.environ.get("NS_TOKEN_ID",       "19d53555407d9ef6b531720869dd543602fe157e823672a1b368e93215b19223")
NS_TOKEN_SEC        = os.environ.get("NS_TOKEN_SEC",      "89f33464075517f514ccfa2ed30e69afd14acc005efeac595ad235cbbd26e7eb")
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
# Dealer data embedded for fast lookup (no GitHub fetch needed)
_DEALERS = [{"name": "A-1 Archery", "address": "587 Lenertz Rd", "city": "Hudson", "state": "WI", "zip": "54016", "phone": "(715) 386-1217", "lat": 44.9842, "lon": -92.7271}, {"name": "A1A Outdoor Center", "address": "6811 North Atlantic Ave", "city": "Cape Canaveral", "state": "FL", "zip": "32920", "phone": "(321) 505-7455", "lat": 28.3903, "lon": -80.6043}, {"name": "A&A Archery", "address": "2480 PA-103", "city": "Lewistown", "state": "PA", "zip": "17044", "phone": "(717) 363-0092", "lat": 40.5994, "lon": -77.5756}, {"name": "Alaska Ebike Store", "address": "2229 Spenard Rd", "city": "Anchorage", "state": "AK", "zip": "99503", "phone": "(907) 744-6433", "lat": 61.19, "lon": -149.8938}, {"name": "Alaska Ebike Store", "address": "2229 Spenard Rd", "city": "Anchorage", "state": "AK", "zip": "99503", "phone": "(907) 744-6433", "lat": 61.19, "lon": -149.8938}, {"name": "Alpine Valley Bicycle Shop", "address": "1218 Us 62", "city": "Wilmot", "state": "OH", "zip": "44689", "phone": "(330) 359-0236", "lat": 40.6567, "lon": -81.6352}, {"name": "Alton Farm & Home Supply", "address": "2600 Homer Adams Pkwy", "city": "Alton", "state": "IL", "zip": "62002", "phone": "(618) 462-9688", "lat": 38.9087, "lon": -90.1568}, {"name": "Archer's Advantage", "address": "4100 Rixie Rd", "city": "North Little Rock", "state": "AR", "zip": "72117", "phone": "(501) 663-2245", "lat": 34.7658, "lon": -92.1524}, {"name": "Archer's Bikes Gilbert", "address": "761 N Monterey St. STE 109", "city": "Gilbert", "state": "AZ", "zip": "85233", "phone": "nan", "lat": 33.3354, "lon": -111.8153}, {"name": "Archer's Bikes Mesa", "address": "1530 N Country Club Dr #4", "city": "Mesa", "state": "AZ", "zip": "85201", "phone": "(480) 275-5818", "lat": 33.4317, "lon": -111.8469}, {"name": "Archer's Bikes SLC", "address": "490 E 1300 S STE 103", "city": "Salt Lake City", "state": "UT", "zip": "84115", "phone": "(385) 202-3424", "lat": 40.7145, "lon": -111.8931}, {"name": "Archery Country", "address": "28 Division St", "city": "Waite Park", "state": "MN", "zip": "56387", "phone": "(320) 253-4786", "lat": 45.5497, "lon": -94.2245}, {"name": "Archery Country", "address": "21135 S Diamond Lake Rd", "city": "Rogers", "state": "MN", "zip": "55374", "phone": "(763) 400-8826", "lat": 45.1715, "lon": -93.5814}, {"name": "Archery Elements Llc", "address": "818 McCastlen St", "city": "Green Bay", "state": "WI", "zip": "54301", "phone": "(920) 680-3463", "lat": 44.482, "lon": -88.0205}, {"name": "Archery Field & Sports", "address": "3725 E 56th St", "city": "Altoona", "state": "IA", "zip": "50009", "phone": "(515) 265-6500", "lat": 41.6475, "lon": -93.4724}, {"name": "Archery & Fishing Unlimited", "address": "47027 N Morrison Blvd", "city": "Hammond", "state": "LA", "zip": "70401", "phone": "(985) 549-0902", "lat": 30.5191, "lon": -90.4879}, {"name": "Archery HQ", "address": "5277 FM 1044 # 102", "city": "New Bravnfels", "state": "TX", "zip": "78130", "phone": "(830) 221-8904", "lat": 29.7229, "lon": -98.0742}, {"name": "Arride Bikes", "address": "28485 TX-249", "city": "Tomball", "state": "TX", "zip": "77375", "phone": "(832) 369-2524", "lat": 30.0739, "lon": -95.6201}, {"name": "Arrow Outdoors", "address": "341 Baker Ave", "city": "Lisbon", "state": "IA", "zip": "52253", "phone": "(715) 579-6930", "lat": 41.9212, "lon": -91.3861}, {"name": "Bakers Archery", "address": "3231 Peters Mountain Rd", "city": "Halifax", "state": "PA", "zip": "17032", "phone": "(717) 896-8090", "lat": 40.476, "lon": -76.894}, {"name": "Bass Pro Shops", "address": "11550 Lakeridge Parkway", "city": "Ashland", "state": "VA", "zip": "23005", "phone": "(804) 496-4700", "lat": 37.7395, "lon": -77.4784}, {"name": "Bayouland Bowhunters", "address": "518 Albertson Pkwy", "city": "Broussard", "state": "LA", "zip": "70518", "phone": "(337) 837-3000", "lat": 30.1219, "lon": -91.9502}, {"name": "BBD Sport Shop", "address": "207 E Spruce St", "city": "Abbotsford", "state": "WI", "zip": "54405", "phone": "(715) 316-0900", "lat": 44.9641, "lon": -90.2994}, {"name": "Ben's Great Outdoors", "address": "2424 S Van Dyke Rd", "city": "Marlette", "state": "MI", "zip": "48453", "phone": "(989) 635-7548", "lat": 43.3399, "lon": -83.0573}, {"name": "Bickel's Cycling & Fitness", "address": "305 E Agency Rd", "city": "West Burlington", "state": "IA", "zip": "52655", "phone": "(319) 754-4410", "lat": 40.8321, "lon": -91.1799}, {"name": "Bicycle Adventure", "address": "319 Main St", "city": "Fort Morgan", "state": "CO", "zip": "80701", "phone": "(970) 743-3400", "lat": 40.2541, "lon": -103.8031}, {"name": "Big Blue Bike Company", "address": "719 Market St", "city": "Beatrice", "state": "NE", "zip": "68310", "phone": "(402) 230-3035", "lat": 40.2705, "lon": -96.7435}, {"name": "Big Rack ebikes and rentals", "address": "537 Tucker Lane", "city": "Benezette", "state": "PA", "zip": "15821", "phone": "(814) 787-7581", "lat": 41.3253, "lon": -78.3576}, {"name": "Bike4Life", "address": "3601-03 W Armitage Ave", "city": "Chicago", "state": "IL", "zip": "60647", "phone": "(312) 687-8565", "lat": 41.9209, "lon": -87.7043}, {"name": "Bixby Bicycles", "address": "8315 East 111 Street South, Unit C", "city": "Bixby", "state": "OK", "zip": "74008", "phone": "(918) 943-6700", "lat": 35.942, "lon": -95.8833}, {"name": "Black Creek Enterprises", "address": "8028 State Rte 414", "city": "Liberty", "state": "PA", "zip": "16930", "phone": "(570) 324-6503", "lat": 41.5656, "lon": -77.1195}, {"name": "Black flag archery", "address": "7243 N Co Rd 200 W", "city": "Shelburn", "state": "IN", "zip": "47879", "phone": "(217) 251-8588", "lat": 39.1784, "lon": -87.3936}, {"name": "Blue Mountain Bikes", "address": "3716 E 1St St", "city": "Blue Ridge", "state": "GA", "zip": "30513", "phone": "(706) 714-2453", "lat": 34.8555, "lon": -84.3281}, {"name": "Boardwalk Bikes", "address": "1515 N Kings Hwy", "city": "Myrtle Beach", "state": "SC", "zip": "29577", "phone": "(843) 231-0573", "lat": 33.6994, "lon": -78.9137}, {"name": "Borger's Bicycle", "address": "3196 Slavik Rd", "city": "Coldwater", "state": "OH", "zip": "45828", "phone": "(419) 852-9313", "lat": 40.4846, "lon": -84.6517}, {"name": "Bourbon Cyclery LLC", "address": "126 W Pine St Suite C", "city": "Bourbon", "state": "MO", "zip": "65441", "phone": "(573) 732-3467", "lat": 38.172, "lon": -91.2225}, {"name": "Bowtreader", "address": "818 S Main St", "city": "Statesboro", "state": "GA", "zip": "30458", "phone": "(912) 225-1630", "lat": 32.4408, "lon": -81.774}, {"name": "Breakaway Bicycles & Fitness", "address": "4741 Harvey St", "city": "Muskegon", "state": "MI", "zip": "49444", "phone": "(231) 799-0008", "lat": 43.1791, "lon": -86.1989}, {"name": "Breakaway Bicycles & Fitness", "address": "215 N Ferry St", "city": "Grand Haven", "state": "MI", "zip": "49417", "phone": "(616) 844-1199", "lat": 43.0378, "lon": -86.1912}, {"name": "Breakaway Bikes", "address": "215 N Ferry St", "city": "Grand Haven", "state": "MI", "zip": "49417", "phone": "(616) 844-1199", "lat": 43.0378, "lon": -86.1912}, {"name": "Broken Spoke Bike Studio Ledgeview", "address": "2200 Dickinson Rd Unit 21", "city": "De Pere", "state": "WI", "zip": "54115", "phone": "(920) 425-3379", "lat": 44.4388, "lon": -88.0806}, {"name": "Buck Hollow Sports", "address": "776 190th Ave", "city": "Pella", "state": "IA", "zip": "50219", "phone": "(641) 628-4586", "lat": 41.4082, "lon": -92.9172}, {"name": "Buck-N-Beards Game Supplies", "address": "16406 Cedar Ridge Rd", "city": "DUBUQUE", "state": "IA", "zip": "52002", "phone": "(563) 590-7454", "lat": 42.5122, "lon": -90.7384}, {"name": "Bucks & Bulls Archery LLC", "address": "2519 Post Rd", "city": "Plover", "state": "WI", "zip": "54467", "phone": "(715) 341-2825", "lat": 44.4507, "lon": -89.5428}, {"name": "Bull's Eye Sports Shop", "address": "1201 S Central Ave", "city": "Marshfield", "state": "WI", "zip": "54449", "phone": "(715) 384-6580", "lat": 44.6615, "lon": -90.1784}, {"name": "Bullseye Trading LLC", "address": "410 N 39th St", "city": "Bethany", "state": "MO", "zip": "64424", "phone": "(660) 425-7888", "lat": 40.2601, "lon": -94.0189}, {"name": "C & S Hunting Supplies", "address": "76 School House Hill Rd", "city": "Middlebury", "state": "VT", "zip": "05753", "phone": "(802) 388-8401", "lat": 43.9919, "lon": -73.1716}, {"name": "Camp Chet Sports", "address": "888 Pine Hill Cemetery Rd", "city": "Whitwell", "state": "TN", "zip": "37397", "phone": "(615) 586-3478", "lat": 35.1972, "lon": -85.5011}, {"name": "CARS Complete Auto Repair Service", "address": "4849 Howard Gnesen Rd", "city": "Duluth", "state": "MN", "zip": "55803", "phone": "(218) 522-4444", "lat": 46.8749, "lon": -92.0941}, {"name": "Castor Creek Outdoors", "address": "400 Guin Rd", "city": "Castor", "state": "LA", "zip": "71016", "phone": "(318) 548-2884", "lat": 32.2452, "lon": -93.0936}, {"name": "Central E-bikes", "address": "403 Broadway St", "city": "Alexandria", "state": "MN", "zip": "56308", "phone": "(320) 762-8811", "lat": 45.8817, "lon": -95.382}, {"name": "Chesapeake Outdoors", "address": "1707 Main St", "city": "Chester", "state": "MD", "zip": "21619", "phone": "(410) 604-2500", "lat": 38.9583, "lon": -76.2842}, {"name": "Church Road Hardware", "address": "4116 Church Rd", "city": "Millers", "state": "MD", "zip": "21102", "phone": "(443) 271-1031", "lat": 39.6747, "lon": -76.8941}, {"name": "Colorado Electric Bikes", "address": "2751 Riverside Pkwy", "city": "Grand Junction", "state": "CO", "zip": "81501", "phone": "(970) 242-3126", "lat": 39.0783, "lon": -108.5457}, {"name": "Connecticut Yankee Pedaller, Inc", "address": "906 Court Ave", "city": "Chariton", "state": "IA", "zip": "50049", "phone": "(641) 774-5557", "lat": 41.0226, "lon": -93.3042}, {"name": "Cool Springs Powersports", "address": "1096 West McEwen Dr", "city": "Franklin", "state": "TN", "zip": "37067", "phone": "(615) 778-1988", "lat": 35.9121, "lon": -86.7655}, {"name": "Core Cycle and Outdoor - Oxford", "address": "902 Sisk Ave", "city": "Oxford", "state": "MS", "zip": "38655", "phone": "16622380155", "lat": 34.3308, "lon": -89.4835}, {"name": "Core Cycle & Outdoor", "address": "1697 Coley Rd", "city": "Tupelo", "state": "MS", "zip": "38801", "phone": "(662) 260-5266", "lat": 34.2538, "lon": -88.7209}, {"name": "CountrySide Bicycling, LLC", "address": "8663 Cox Rd", "city": "Windsor", "state": "OH", "zip": "44099", "phone": "(440) 487-5018", "lat": 41.5623, "lon": -80.9667}, {"name": "Covered Bridge Bike Rental", "address": "197 S Main St", "city": "Glen Carbon", "state": "IL", "zip": "62034", "phone": "(618) 205-3132", "lat": 38.7609, "lon": -89.9706}, {"name": "Covina Valley Cyclery", "address": "203 S Citrus Ave", "city": "Covina", "state": "CA", "zip": "91723", "phone": "(626) 332-5200", "lat": 34.086, "lon": -117.8843}, {"name": "Crazy Lenny's E-Bikes", "address": "6017 Odana Rd", "city": "Madison", "state": "WI", "zip": "53719", "phone": "(608) 276-5921", "lat": 43.0321, "lon": -89.4993}, {"name": "CSM Power Bikes", "address": "3311 Chellington Dr", "city": "Johnsburg", "state": "IL", "zip": "60051", "phone": "(815) 513-2453", "lat": 42.3542, "lon": -88.2294}, {"name": "Cyclefit Sports", "address": "1006 N Leroy St", "city": "Fenton", "state": "MI", "zip": "48430", "phone": "(810) 750-2348", "lat": 42.7851, "lon": -83.7294}, {"name": "CYCLERIE eBikes and Service", "address": "515 Briggs St Suite D", "city": "Erie", "state": "CO", "zip": "80516", "phone": "(720) 235-8660", "lat": 40.0597, "lon": -105.0686}, {"name": "Cyclone Electric Bikes", "address": "4046 Co Rd 1125", "city": "Farmersville", "state": "TX", "zip": "75442", "phone": "(903) 776-9942", "lat": 33.1659, "lon": -96.3686}, {"name": "Dan's Bike Shop", "address": "350 W Main Street", "city": "Ionia", "state": "MI", "zip": "48846", "phone": "(616) 527-0471", "lat": 42.9859, "lon": -85.071}, {"name": "DNW Outdoors", "address": "1711 E Parker Rd", "city": "Jonesboro", "state": "AR", "zip": "72404", "phone": "(870) 972-5827", "lat": 35.7792, "lon": -90.766}, {"name": "Dover Tactical", "address": "2001 George St", "city": "Dover", "state": "PA", "zip": "17315", "phone": "(717) 467-8185", "lat": 40.0062, "lon": -76.8555}, {"name": "D&R Sports Center", "address": "8178 W Main St", "city": "Kalamazoo", "state": "MI", "zip": "49009", "phone": "(269) 372-2277", "lat": 42.2809, "lon": -85.6863}, {"name": "Dunbar's Taxidermy", "address": "8120 Old Stage Rd", "city": "Central Point", "state": "OR", "zip": "97502", "phone": "(541) 727-1154", "lat": 42.3899, "lon": -122.9222}, {"name": "E Cycle Adventures", "address": "9904 Little Rd", "city": "New Port Richey", "state": "FL", "zip": "34654", "phone": "(727) 819-0627", "lat": 28.3022, "lon": -82.6264}, {"name": "E Power Bike Shop", "address": "137 Sebastian Blvd Suite D", "city": "Sebastian", "state": "FL", "zip": "32958", "phone": "(321) 419-3375", "lat": 27.7901, "lon": -80.4784}, {"name": "Ebike Options LLC", "address": "453 E Wonderview Ave Unit 3-193", "city": "Estes Park", "state": "CO", "zip": "80517", "phone": "(303) 834-7376", "lat": 40.3658, "lon": -105.5142}, {"name": "eBike315", "address": "210 N Main St", "city": "Newark", "state": "NY", "zip": "14513", "phone": "(315) 332-8776", "lat": 43.0519, "lon": -77.0946}, {"name": "Elevated Archery,LLC", "address": "57 Pillar Drive", "city": "Cashiers", "state": "NC", "zip": "28717", "phone": "(828) 342-7029", "lat": 35.0971, "lon": -83.0871}, {"name": "E-Rides", "address": "3230 Frankfort Ave", "city": "Louisville", "state": "KY", "zip": "40205", "phone": "15024924935", "lat": 38.2222, "lon": -85.6885}, {"name": "E-Rides", "address": "500 Fairfield Ave", "city": "Bellevue", "state": "KY", "zip": "41073", "phone": "18596533729", "lat": 39.1024, "lon": -84.4787}, {"name": "F6 Outdoors", "address": "2521 290th st", "city": "Montrose", "state": "IA", "zip": "52639", "phone": "(319) 986-5355", "lat": 40.5139, "lon": -91.424}, {"name": "Farm-Way Inc / Vermont Gear", "address": "286 Waits River Rd", "city": "Bradford", "state": "VT", "zip": "05033", "phone": "(800) 222-9316", "lat": 44.0006, "lon": -72.1406}, {"name": "Frank's Great Outdoors", "address": "1212 N Huron Rd", "city": "Linwood", "state": "MI", "zip": "48634", "phone": "(989) 697-5341", "lat": 43.7714, "lon": -84.0513}, {"name": "Fun Factor Sporting Goods", "address": "312 McInturff Rd", "city": "Limestone", "state": "TN", "zip": "37681", "phone": "(423) 863-1141", "lat": 36.254, "lon": -82.625}, {"name": "Garden State Yacht Sales", "address": "101 NJ-35", "city": "Point Pleasant Beach", "state": "NJ", "zip": "08742", "phone": "(732) 892-4222", "lat": 40.0806, "lon": -74.0595}, {"name": "Gary's Shoe Store", "address": "126 N Main St", "city": "Richfield", "state": "UT", "zip": "84701", "phone": "(435) 896-4931", "lat": 38.7388, "lon": -112.0744}, {"name": "Green Mountain Bikes", "address": "105 N Main St", "city": "Rochester", "state": "VT", "zip": "05767", "phone": "(802) 767-4464", "lat": 43.8804, "lon": -72.8159}, {"name": "Greenbrier Bikes", "address": "926 3rd Ave", "city": "Marlinton", "state": "WV", "zip": "24954", "phone": "13045917021", "lat": 38.2586, "lon": -80.1046}, {"name": "Greensburg Bike Shop", "address": "3 S 4th St", "city": "Youngwood", "state": "PA", "zip": "15697", "phone": "17247552453", "lat": 40.2395, "lon": -79.5823}, {"name": "Grenada Bad Boys", "address": "55 Dubard Rd", "city": "Grenada", "state": "MS", "zip": "38901", "phone": "(662) 307-2729", "lat": 33.7751, "lon": -89.8087}, {"name": "Grumpy's Bike Shop", "address": "193 W Main St", "city": "Spindale", "state": "NC", "zip": "28160", "phone": "(828) 980-2884", "lat": 35.3601, "lon": -81.9251}, {"name": "Hales True Value Hardware", "address": "56216 M-51 S", "city": "Dowagiac", "state": "MI", "zip": "49047", "phone": "(269) 782-3426", "lat": 41.991, "lon": -86.1168}, {"name": "Hannibal Farm & Home Supply", "address": "2959 Palmyra Rd", "city": "Hannibal", "state": "MO", "zip": "63401", "phone": "(573) 221-8444", "lat": 39.7064, "lon": -91.3839}, {"name": "Hardcore Outfitters", "address": "1616 N Stephenson Ave", "city": "Iron Mountain", "state": "MI", "zip": "49801", "phone": "(906) 828-1034", "lat": 45.8219, "lon": -88.0683}, {"name": "Hi-Power Sports", "address": "100 S 4th St", "city": "Bloomfield", "state": "NM", "zip": "87413", "phone": "(505) 333-7684", "lat": 36.6955, "lon": -107.9784}, {"name": "Hit or Miss Archery Center", "address": "2801 Broadbent Pkwy NE STE D", "city": "Albuquerque", "state": "NM", "zip": "87107", "phone": "(505) 200-9650", "lat": 35.1347, "lon": -106.6427}, {"name": "HL Powersports", "address": "19 Lakeside Dr #3273", "city": "Harveys Lake", "state": "PA", "zip": "18618", "phone": "(570) 639-1000", "lat": 41.3592, "lon": -76.0451}, {"name": "House Of Wheels", "address": "814 W Main St", "city": "Owosso", "state": "MI", "zip": "48867", "phone": "(989) 725-8373", "lat": 42.9934, "lon": -84.1595}, {"name": "Hubert's Outdoor Power", "address": "17269 US-59", "city": "Thief River Falls", "state": "MN", "zip": "56701", "phone": "(218) 681-5981", "lat": 48.1191, "lon": -96.1811}, {"name": "Hunt Easy LLC", "address": "4197 Hidden Hls Ln", "city": "Aviston", "state": "IL", "zip": "62216", "phone": "(618) 806-8541", "lat": 38.6089, "lon": -89.6034}, {"name": "Hunt N Gear", "address": "4336 Milton Ave #140", "city": "Janesville", "state": "WI", "zip": "53546", "phone": "(608) 743-4327", "lat": 42.6683, "lon": -89.0025}, {"name": "Hunters Hide", "address": "12054 Curley St", "city": "San Antonio", "state": "FL", "zip": "33576", "phone": "(352) 458-1406", "lat": 28.3371, "lon": -82.2882}, {"name": "Ingram's Archery Supply", "address": "789 Rosebud Rd", "city": "Quitman", "state": "AR", "zip": "72131", "phone": "(501) 589-2697", "lat": 35.405, "lon": -92.1333}, {"name": "Iowa River Outdoors", "address": "2721 120th Street NE Ste C", "city": "Swisher", "state": "IA", "zip": "52338", "phone": "(319) 857-4040", "lat": 41.8268, "lon": -91.6739}, {"name": "J's Archery Pro Shop", "address": "2763 US-45", "city": "Antigo", "state": "WI", "zip": "54409", "phone": "(715) 627-2697", "lat": 45.1314, "lon": -89.1419}, {"name": "Jay's Sporting Goods", "address": "8800 S Clare Ave", "city": "Clare", "state": "MI", "zip": "48617", "phone": "(989) 386-3475", "lat": 43.8223, "lon": -84.7635}, {"name": "Jay's Sporting Goods", "address": "1151 S Otsego Ave", "city": "Gaylord", "state": "MI", "zip": "49735", "phone": "(989) 705-1339", "lat": 45.0125, "lon": -84.6723}, {"name": "JEFF'S PERFORMANCE ARCHERY", "address": "101 N Iowa St", "city": "Dodgeville", "state": "WI", "zip": "53533", "phone": "(608) 574-5916", "lat": 42.9698, "lon": -90.1404}, {"name": "Jerseyville Farm & Home Supply", "address": "725 IL-16", "city": "Jerseyville", "state": "IL", "zip": "62052", "phone": "(618) 498-5514", "lat": 39.1213, "lon": -90.3338}, {"name": "Jim's Sports Center", "address": "26 N 2nd St", "city": "Clearfield", "state": "PA", "zip": "16830", "phone": "(814) 765-3582", "lat": 41.021, "lon": -78.4435}, {"name": "Joe's Sport Center Inc", "address": "909 US-2", "city": "Devils Lake", "state": "ND", "zip": "58301", "phone": "(701) 662-4071", "lat": 48.1132, "lon": -98.8616}, {"name": "Jot Em Down Outdoors", "address": "3425 US Hwy 84 W", "city": "Blackshear", "state": "GA", "zip": "31516", "phone": "(912) 449-0095", "lat": 31.2931, "lon": -82.2617}, {"name": "Kaufman by Design West", "address": "14900 Cantrell Rd", "city": "Little Rock", "state": "AR", "zip": "72223", "phone": "(501) 673-3978", "lat": 34.7902, "lon": -92.5044}, {"name": "Keck's General Store", "address": "1801 Pine Rd", "city": "Newville", "state": "PA", "zip": "17241", "phone": "(717) 486-3474", "lat": 40.1855, "lon": -77.4114}, {"name": "Kentucky Lake Outdoors", "address": "3261 US Hwy 68 E", "city": "Benton", "state": "KY", "zip": "42025", "phone": "(270) 252-9097", "lat": 36.8806, "lon": -88.3548}, {"name": "Kingston Cyclery", "address": "612 Ulster Ave.", "city": "Kingston", "state": "NY", "zip": "12401", "phone": "(845) 383-1600", "lat": 41.9697, "lon": -74.0668}, {"name": "Kittery Trading Post", "address": "301 US-1", "city": "Kittery", "state": "ME", "zip": "03904", "phone": "(207) 439-2700", "lat": 43.0921, "lon": -70.7429}, {"name": "Lake Breeze Bicycle", "address": "10707 Millers Rd", "city": "Lyndonville", "state": "NY", "zip": "14098", "phone": "(585) 735-5678", "lat": 43.3233, "lon": -78.3811}, {"name": "Lakeside Bicycle", "address": "820 W 700 S", "city": "Wolcottville", "state": "IN", "zip": "46795", "phone": "(260) 854-9456", "lat": 41.557, "lon": -85.315}, {"name": "Lebanon Indoor Archery and Supplies", "address": "2 E Lehman St Suite 1", "city": "Lebanon", "state": "PA", "zip": "17046", "phone": "(717) 450-4959", "lat": 40.3812, "lon": -76.4368}, {"name": "LECORCHICKS SPORTING SUPPLIES LLC", "address": "174 SHAWNA RD", "city": "NORTHERN CAMBRIA", "state": "PA", "zip": "15714", "phone": "(814) 948-9409", "lat": 40.6661, "lon": -78.792}, {"name": "Legacy Archery", "address": "5328 US-322", "city": "Brookville", "state": "PA", "zip": "15825", "phone": "(814) 849-1200", "lat": 41.1627, "lon": -79.0816}, {"name": "Lena Swamp Archery", "address": "6640 WI-22", "city": "Oconto Falls", "state": "WI", "zip": "54154", "phone": "(920) 846-0211", "lat": 44.8755, "lon": -88.1555}, {"name": "Little Mountain Outfitters", "address": "225 E Main St", "city": "Richland", "state": "PA", "zip": "17087", "phone": "(717) 346-0652", "lat": 40.3806, "lon": -76.2654}, {"name": "LL Cote Sports Center", "address": "7 Main St", "city": "Errol", "state": "NH", "zip": "03579", "phone": "(800) 287-7700", "lat": 44.8003, "lon": -71.1436}, {"name": "LMB Hauling", "address": "368 SFC 221", "city": "Forrest City", "state": "AR", "zip": "72335", "phone": "nan", "lat": 35.0091, "lon": -90.7886}, {"name": "Locked & Loaded Ltd.", "address": "1299 Jackson St", "city": "Pana", "state": "IL", "zip": "62557", "phone": "(217) 562-7000", "lat": 39.3971, "lon": -89.1048}, {"name": "Lone Oak Outdoors", "address": "1300 Northridge Dr NW", "city": "Pine City", "state": "MN", "zip": "55063", "phone": "(763) 477-2095", "lat": 45.8363, "lon": -92.9042}, {"name": "Long Beach Bicycles", "address": "176 W Park Avenue", "city": "Long Beach", "state": "NY", "zip": "11561", "phone": "(516) 517-2453", "lat": 40.5877, "lon": -73.6595}, {"name": "Long Haul eBike Repair", "address": "3109 W 50th St", "city": "Minneapolis", "state": "MN", "zip": "55410", "phone": "(612) 208-2202", "lat": 44.9124, "lon": -93.3188}, {"name": "Long Range Archery and Firearms LLC", "address": "2530 Van Ommen Dr", "city": "Holland", "state": "MI", "zip": "49424", "phone": "(616) 399-3011", "lat": 42.8135, "lon": -86.1426}, {"name": "Lonnie's Sporting Goods", "address": "700 S Harper Rd", "city": "Corinth", "state": "MS", "zip": "38834", "phone": "(662) 286-5571", "lat": 34.8759, "lon": -88.5916}, {"name": "Lyndons Riverview Sports", "address": "6741 North Carolina 16S", "city": "Taylorsville", "state": "NC", "zip": "28681", "phone": "(828) 632-7889", "lat": 35.901, "lon": -81.2124}, {"name": "Lynn's Archery Pro Shop", "address": "1510 Mahood Rd", "city": "West Sunbury", "state": "PA", "zip": "16061", "phone": "(724) 285-2144", "lat": 41.0026, "lon": -79.8751}, {"name": "M2 Powersports", "address": "2010 S Cedar Ave", "city": "Owatonna", "state": "MN", "zip": "55060", "phone": "(507) 456-8180", "lat": 44.0805, "lon": -93.2191}, {"name": "Mak's Bait Shak", "address": "2095 Kerper Blvd", "city": "Dubuque", "state": "IA", "zip": "52001", "phone": "(563) 582-9395", "lat": 42.515, "lon": -90.6819}, {"name": "Martins Bike & Fitness", "address": "1891 Division Hwy", "city": "Ephrata", "state": "PA", "zip": "17522", "phone": "17173549127", "lat": 40.1756, "lon": -76.1821}, {"name": "Marty's Reliable Cycle of Hackettstown", "address": "251 Main St", "city": "Hackettstown", "state": "NJ", "zip": "07840", "phone": "(908) 852-1650", "lat": 40.8529, "lon": -74.8343}, {"name": "Marty's Reliable Cycle of High Bridge", "address": "99 Main St", "city": "High Bridge", "state": "NJ", "zip": "08829", "phone": "(908) 264-0060", "lat": 40.6684, "lon": -74.8937}, {"name": "Marty's Reliable Cycle of Morristown", "address": "173 Speedwell Ave", "city": "Morristown", "state": "NJ", "zip": "07960", "phone": "(973) 538-7773", "lat": 40.7952, "lon": -74.4873}, {"name": "Mathfab LLC", "address": "101 W Snell Rd", "city": "Oshkosh", "state": "WI", "zip": "54901", "phone": "(920) 231-6060", "lat": 44.022, "lon": -88.5436}, {"name": "Max's Electric Bikes", "address": "200 Wanaque Ave Suite 310", "city": "Pompton Lakes", "state": "NJ", "zip": "07442", "phone": "(862) 774-5997", "lat": 40.9993, "lon": -74.2876}, {"name": "Max's Electric Bikes", "address": "805 W Canal St", "city": "Easton", "state": "PA", "zip": "18042", "phone": "16102482280", "lat": 40.6516, "lon": -75.224}, {"name": "Max's Electric Bikes", "address": "1386 US-22", "city": "Lebanon", "state": "NJ", "zip": "08833", "phone": "19087525201", "lat": 40.6466, "lon": -74.829}, {"name": "Max's Electric Bikes", "address": "540 Route 10 West", "city": "Randolph", "state": "NJ", "zip": "07869", "phone": "(973) 385-8983", "lat": 40.8456, "lon": -74.5725}, {"name": "Max's Electric Bikes", "address": "807 N Easton Rd", "city": "Doylestown", "state": "PA", "zip": "18902", "phone": "(215) 817-7330", "lat": 40.3477, "lon": -75.0968}, {"name": "McCoy's Outdoors", "address": "2823 Jefferson St", "city": "Marianna", "state": "FL", "zip": "32448", "phone": "(850) 526-2921", "lat": 30.6749, "lon": -85.2122}, {"name": "MEDFORD MOTORS", "address": "105 Wisconsin Ave", "city": "Medford", "state": "WI", "zip": "54451", "phone": "(715) 748-3700", "lat": 45.1512, "lon": -90.3503}, {"name": "Midwest Archery", "address": "4725 N State Hwy 13", "city": "Springfield", "state": "MO", "zip": "65803", "phone": "(417) 403-2141", "lat": 37.2593, "lon": -93.2912}, {"name": "Millers Gun Shop", "address": "6945 Nittany Valley Dr", "city": "Mill Hall", "state": "PA", "zip": "17751", "phone": "(570) 726-3030", "lat": 41.0867, "lon": -77.4836}, {"name": "Mineola Bicycle", "address": "475 Jericho Turnpike", "city": "Mineola", "state": "NY", "zip": "11501", "phone": "(516) 742-5253", "lat": 40.7469, "lon": -73.6398}, {"name": "Mobile Ebike Service", "address": "3016 W 44th St Apt 4", "city": "Minneapolis", "state": "MN", "zip": "55410", "phone": "(716) 908-1885", "lat": 44.9124, "lon": -93.3188}, {"name": "Mojo Cycling", "address": "1100 N Walton Blvd", "city": "Bentonville", "state": "AR", "zip": "72712", "phone": "(479) 271-7201", "lat": 36.3577, "lon": -94.2224}, {"name": "Mole Hill Bikes", "address": "440 Main Street", "city": "Dayton", "state": "VA", "zip": "22821", "phone": "15408792011", "lat": 38.4707, "lon": -79.085}, {"name": "Mt George Archery & Quick Stop", "address": "10031 Archers Ln", "city": "Danville", "state": "AR", "zip": "72833", "phone": "(479) 576-2786", "lat": 35.0495, "lon": -93.3929}, {"name": "N+1 cyclery, LLC", "address": "57 Waverly St", "city": "Framingham", "state": "MA", "zip": "01702", "phone": "(508) 620-6600", "lat": 42.2822, "lon": -71.4339}, {"name": "Nichols Store", "address": "1980 Mt Holly Rd", "city": "Rock Hill", "state": "SC", "zip": "29730", "phone": "(803) 328-9792", "lat": 34.9151, "lon": -81.0129}, {"name": "Nocturnal Optics", "address": "484 Holland Farm Rd", "city": "Andrews", "state": "NC", "zip": "28901", "phone": "(828) 342-7018", "lat": 35.1959, "lon": -83.8228}, {"name": "North Lakes Marine & Auto", "address": "3605 Highway 371", "city": "Hackensack", "state": "MN", "zip": "56452", "phone": "(218) 682-2008", "lat": 46.9884, "lon": -94.5033}, {"name": "NUGGET'S NIGHT VISION", "address": "100 E Collins St", "city": "Mendon", "state": "IL", "zip": "62351", "phone": "(217) 242-2399", "lat": 40.0857, "lon": -91.2899}, {"name": "Oceans East Bait & Tackle Shop", "address": "5785 Northampton Blvd #104", "city": "Virginia Beach", "state": "VA", "zip": "23455", "phone": "(757) 464-6544", "lat": 36.8881, "lon": -76.1446}, {"name": "Orange County Archery", "address": "25782 Obrero Dr", "city": "Mission Viejo", "state": "CA", "zip": "92691", "phone": "(949) 916-6855", "lat": 33.6128, "lon": -117.6622}, {"name": "Outdoor Addiction", "address": "819 W Newton St", "city": "Versailles", "state": "MO", "zip": "65084", "phone": "(573) 378-2220", "lat": 38.4365, "lon": -92.8258}, {"name": "Outrageous Outdoors", "address": "902 S State St", "city": "Jerseyville", "state": "IL", "zip": "62052", "phone": "(618) 639-4867", "lat": 39.1213, "lon": -90.3338}, {"name": "Papa Bears Stoves & Outdoor Living", "address": "96 Cortland St", "city": "Marathon", "state": "NY", "zip": "13803", "phone": "(607) 849-6605", "lat": 42.4527, "lon": -76.0395}, {"name": "Paradise Creek Bicycles", "address": "513 S Main St", "city": "Moscow", "state": "ID", "zip": "83843", "phone": "(208) 882-0703", "lat": 46.7309, "lon": -116.9897}, {"name": "Parks Outdoors", "address": "26271 Image Rd", "city": "Brookfield", "state": "MO", "zip": "64628", "phone": "(660) 258-3305", "lat": 39.7846, "lon": -93.0719}, {"name": "Pedego Aiken", "address": "4019 Pavilion Pass", "city": "Aiken", "state": "SC", "zip": "29803", "phone": "(803) 226-9007", "lat": 33.5059, "lon": -81.6951}, {"name": "Pedego Soda City", "address": "521 Meeting St", "city": "West Columbia", "state": "SC", "zip": "29169", "phone": "(803) 563-5636", "lat": 33.995, "lon": -81.0888}, {"name": "Pedersen Bicycle Services", "address": "601 Meadowbrook PL", "city": "Huxley", "state": "IA", "zip": "50124", "phone": "(515) 204-6138", "lat": 41.8994, "lon": -93.6024}, {"name": "Pembroke Stop N Save", "address": "138 Grill Rd", "city": "Pembroke", "state": "VA", "zip": "24136", "phone": "(540) 626-7077", "lat": 37.3312, "lon": -80.5975}, {"name": "Perfect 10 Outdoors, LLC", "address": "W8263 Co Hwy B", "city": "Neillsville", "state": "WI", "zip": "54456", "phone": "(715) 743-2485", "lat": 44.5494, "lon": -90.6112}, {"name": "Petty John's Farm & Builders", "address": "424 W Linden Way", "city": "Heppner", "state": "OR", "zip": "97836", "phone": "(541) 676-9157", "lat": 45.3486, "lon": -119.5369}, {"name": "Pilot Arms", "address": "215 Parkview Dr", "city": "Piperton", "state": "TN", "zip": "38017", "phone": "(202) 812-2357", "lat": 35.0551, "lon": -89.6767}, {"name": "Pine Grove Yamaha", "address": "193 Tremont Rd", "city": "Pine Grove", "state": "PA", "zip": "17963", "phone": "(570) 345-8918", "lat": 40.5671, "lon": -76.3269}, {"name": "Pittsfield Farm & Home Supply", "address": "1343 W Washington St", "city": "Pittsfield", "state": "IL", "zip": "62363", "phone": "(217) 285-4444", "lat": 39.6013, "lon": -90.8073}, {"name": "Power Lodge", "address": "6781 US-10", "city": "Ramsey", "state": "MN", "zip": "55303", "phone": "(763) 576-1706", "lat": 45.2825, "lon": -93.4186}, {"name": "POWER LODGE - Brainerd", "address": "17821 MN-371 N", "city": "Brainerd", "state": "MN", "zip": "56401", "phone": "(218) 822-3500", "lat": 46.3502, "lon": -94.1}, {"name": "POWER LODGE - Mille Lacs", "address": "33972 US-169", "city": "Onamia", "state": "MN", "zip": "56359", "phone": "(320) 532-3860", "lat": 46.0902, "lon": -93.6867}, {"name": "Pozarski Family Farms LLC", "address": "29999 130th Ave", "city": "Boyd", "state": "WI", "zip": "54726", "phone": "(715) 313-3102", "lat": 44.9437, "lon": -91.0294}, {"name": "Presleys Outdoors", "address": "1510 W Garfield Ave", "city": "Bartonville", "state": "IL", "zip": "61607", "phone": "(309) 697-1193", "lat": 40.6321, "lon": -89.6903}, {"name": "Push Pedal Pull", "address": "2300 W 41st St", "city": "Sioux Falls", "state": "SD", "zip": "57105", "phone": "(605) 332-3481", "lat": 43.524, "lon": -96.7341}, {"name": "Quincy Farm & Home Supply", "address": "4625 Broadway St", "city": "Quincy", "state": "IL", "zip": "62305", "phone": "(217) 223-6970", "lat": 39.9601, "lon": -91.3026}, {"name": "Rack Attack Archery", "address": "482 Erlanger Rd", "city": "Erlanger", "state": "KY", "zip": "41018", "phone": "(859) 379-9301", "lat": 39.0082, "lon": -84.5977}, {"name": "Rack N Reel", "address": "5343 Ethan Allen Hwy", "city": "New Haven", "state": "VT", "zip": "05472", "phone": "(802) 453-2000", "lat": 44.1126, "lon": -73.1735}, {"name": "Rambo Bikes Warehouse", "address": "22844 230th Ave", "city": "Centerville", "state": "IA", "zip": "52544", "phone": "(952) 283-0777", "lat": 40.7326, "lon": -92.8728}, {"name": "Ranch Camp", "address": "311 Mountain Rd", "city": "Stowe", "state": "VT", "zip": "05672", "phone": "(802) 253-2753", "lat": 44.4695, "lon": -72.6923}, {"name": "Ranch Camp Woodstock", "address": "431 Woodstock Rd", "city": "Woodstock", "state": "VT", "zip": "05091", "phone": "(802) 457-1561", "lat": 43.6248, "lon": -72.5385}, {"name": "Ray's Sport & Cycle", "address": "20890 US-169", "city": "Grand Rapids", "state": "MN", "zip": "55744", "phone": "(218) 326-9355", "lat": 47.2348, "lon": -93.5115}, {"name": "Redding's Hardware", "address": "279 S Franklin St", "city": "Gettysburg", "state": "PA", "zip": "17325", "phone": "(717) 334-5211", "lat": 39.832, "lon": -77.2223}, {"name": "Redline E-Bikes", "address": "3169 County Line Rd", "city": "Chalfont", "state": "PA", "zip": "18914", "phone": "(267) 576-2545", "lat": 40.2892, "lon": -75.2149}, {"name": "RG Sports and Outdoors", "address": "32392 Dolphin ST NW", "city": "Princeton", "state": "MN", "zip": "55371", "phone": "(844) 281-4868", "lat": 45.5851, "lon": -93.5961}, {"name": "Ricochet Outdoors", "address": "1970 E Oak St", "city": "Conway", "state": "AR", "zip": "72032", "phone": "(501) 327-4457", "lat": 35.0842, "lon": -92.4236}, {"name": "Rides N Motion", "address": "18261 N Pima Rd", "city": "Scottsdale", "state": "AZ", "zip": "85255", "phone": "(623) 688-7429", "lat": 33.6968, "lon": -111.8892}, {"name": "Rides N Motion, Electric Bikes of Flagstaff", "address": "14 E Birch Ave", "city": "Flagstaff", "state": "AZ", "zip": "86001", "phone": "(928) 525-6037", "lat": 35.1859, "lon": -111.662}, {"name": "Rides N Motion, Electric Bikes Of Peoria", "address": "9828 W Northern Ave Suite 1715", "city": "Peoria", "state": "AZ", "zip": "85345", "phone": "(623) 262-4911", "lat": 33.5761, "lon": -112.2344}, {"name": "Rides N Motion, Electric Bikes Of Scottsdale", "address": "8300 N Hayden Rd Ste. C-100", "city": "Scottsdale", "state": "AZ", "zip": "85258", "phone": "(480) 431-2230", "lat": 33.5647, "lon": -111.8931}, {"name": "River Point Taxidermy", "address": "1130 8 1/2 St", "city": "Barron", "state": "WI", "zip": "54812", "phone": "(715) 205-0882", "lat": 45.4005, "lon": -91.85}, {"name": "Riverbrook Bike & Ski", "address": "10538 Main St", "city": "Hayward", "state": "WI", "zip": "54843", "phone": "(715) 634-0437", "lat": 45.9552, "lon": -91.2783}, {"name": "Rize Outdoors", "address": "2 North Landmark Lane Ste 4", "city": "Rigby", "state": "ID", "zip": "83442", "phone": "(208) 520-9658", "lat": 43.6715, "lon": -111.9005}, {"name": "Rocky Mountain Discount Sports", "address": "4706 S Douglas Hwy", "city": "Gillette", "state": "WY", "zip": "82718", "phone": "(307) 686-0221", "lat": 43.9282, "lon": -105.5492}, {"name": "Rocky Mountain Discount Sports", "address": "1351 CY Ave", "city": "Casper", "state": "WY", "zip": "82604", "phone": "(307) 265-6974", "lat": 42.8261, "lon": -106.3896}, {"name": "Rocky Mountain Discount Sports", "address": "709 N Federal Blvd", "city": "Riverton", "state": "WY", "zip": "82501", "phone": "(307) 856-7687", "lat": 43.0351, "lon": -108.2024}, {"name": "Rocky Mountain Discount Sports", "address": "440 Broadway St", "city": "Sheridan", "state": "WY", "zip": "82801", "phone": "(307) 672-3418", "lat": 44.7849, "lon": -106.9648}, {"name": "Rocky Mountain Discount Sports", "address": "1526 Rumsey Ave # 1", "city": "Cody", "state": "WY", "zip": "82414", "phone": "(307) 527-6071", "lat": 44.5231, "lon": -109.0756}, {"name": "Rocky Mountain E-Bike LLC", "address": "2251 Signal Rock Court", "city": "Grand Junction", "state": "CO", "zip": "81505", "phone": "(970) 640-3457", "lat": 39.1071, "lon": -108.5968}, {"name": "Rocky's Bicycle Shop", "address": "20 Rocky's Creekside Lane", "city": "Monroeton", "state": "PA", "zip": "18832", "phone": "(570) 265-9208", "lat": 41.7135, "lon": -76.4872}, {"name": "San Flea Rentals", "address": "4372 Cape San Blas Rd", "city": "Port St Joe", "state": "FL", "zip": "32456", "phone": "(850) 381-3953", "lat": 29.8119, "lon": -85.303}, {"name": "Scott's Outdoors Sports", "address": "3898 FL-4", "city": "Jay", "state": "FL", "zip": "32565", "phone": "(850) 675-4566", "lat": 30.8985, "lon": -87.1332}, {"name": "Scrambler Cycle", "address": "627 3rd St", "city": "Chetek", "state": "WI", "zip": "54728", "phone": "(715) 204-9121", "lat": 45.317, "lon": -91.6542}, {"name": "Seaside Eco Bikes", "address": "16779 Coastal Hwy unit 1", "city": "Lewes", "state": "DE", "zip": "19958", "phone": "(302) 329-8088", "lat": 38.7381, "lon": -75.1747}, {"name": "Sherper's", "address": "225 E Wisconsin Ave", "city": "Oconomowoc", "state": "WI", "zip": "53066", "phone": "(262) 567-6847", "lat": 43.1095, "lon": -88.4862}, {"name": "Simmons Sporting Goods", "address": "918 N Washington Street", "city": "Bastrop", "state": "LA", "zip": "71220", "phone": "(318) 283-2688", "lat": 32.7894, "lon": -91.9078}, {"name": "Smoke Hole Outfitters LLC", "address": "5413 N Fork Hwy", "city": "Cabins", "state": "WV", "zip": "26855", "phone": "(724) 998-5703", "lat": 38.9512, "lon": -79.2783}, {"name": "Southeast Sales Inc.", "address": "302 5th Ave SW", "city": "Red Bay", "state": "AL", "zip": "35582", "phone": "(256) 376-2003", "lat": 34.4513, "lon": -88.1129}, {"name": "Southern Construction Supply", "address": "4385 Wade Hampton Blvd", "city": "Taylors", "state": "SC", "zip": "29687", "phone": "(864) 631-1804", "lat": 34.9245, "lon": -82.3197}, {"name": "Southern Illinois Whitetail Connection", "address": "673 County Rd 1650 E", "city": "Fairfield", "state": "IL", "zip": "62837", "phone": "(618) 599-2463", "lat": 38.3782, "lon": -88.3593}, {"name": "Southern Specialty Products", "address": "615 E Prien Lake Rd", "city": "Lake Charles", "state": "LA", "zip": "70601", "phone": "(337) 474-9090", "lat": 30.2285, "lon": -93.188}, {"name": "Sport Center", "address": "120 2nd Ave S", "city": "Lewistown", "state": "MT", "zip": "59457", "phone": "(406) 535-9308", "lat": 47.0563, "lon": -109.4203}, {"name": "Sportsman's Edge", "address": "292 US-62", "city": "Ash Flat", "state": "AR", "zip": "72513", "phone": "(870) 994-3651", "lat": 36.2201, "lon": -91.6421}, {"name": "Sportsman's Outlet", "address": "500 Chestnut St", "city": "Bradford", "state": "PA", "zip": "16701", "phone": "(814) 362-7700", "lat": 41.9547, "lon": -78.654}, {"name": "Sportsman's Refuge Inc", "address": "696 Fairchance Rd", "city": "Morgantown", "state": "WV", "zip": "26508", "phone": "(304) 594-9126", "lat": 39.5953, "lon": -79.9229}, {"name": "Spotted Dog Sporting Goods", "address": "6441 Highway 165", "city": "Columbia", "state": "LA", "zip": "71418", "phone": "(318) 649-7004", "lat": 32.1022, "lon": -92.1177}, {"name": "Star Valley Ski-Doo", "address": "622 N Main St", "city": "Thayne", "state": "WY", "zip": "83127", "phone": "(307) 883-2714", "lat": 42.933, "lon": -111.0114}, {"name": "Stewart's Bikes & Sports", "address": "102 S 29th Ave W", "city": "Duluth", "state": "MN", "zip": "55806", "phone": "(218) 625-5501", "lat": 46.7715, "lon": -92.1279}, {"name": "Stewarts Archery", "address": "13627 Old State Rd", "city": "Charleston", "state": "IL", "zip": "61920", "phone": "(217) 549-8671", "lat": 39.4869, "lon": -88.1761}, {"name": "Straight Arrow Outdoors", "address": "by appointment only", "city": "Mondovi", "state": "WI", "zip": "54481", "phone": "(715) 347-7740", "lat": 44.5212, "lon": -89.5588}, {"name": "STX Archery & Outdoors", "address": "87 Dincans St", "city": "Inez", "state": "TX", "zip": "77968", "phone": "(361) 781-5200", "lat": 28.8994, "lon": -96.8003}, {"name": "Suamico Bicycle Company", "address": "1790 Riverside Dr", "city": "Suamico", "state": "WI", "zip": "54173", "phone": "(920) 489-8800", "lat": 44.6435, "lon": -88.0317}, {"name": "Sunshine Sports", "address": "304 Moore Lane", "city": "Billings", "state": "MT", "zip": "59101", "phone": "(406) 252-3724", "lat": 45.7745, "lon": -108.5005}, {"name": "Synergy Cycles", "address": "900 E Park Blvd", "city": "Boise", "state": "ID", "zip": "83712", "phone": "(208) 274-8082", "lat": 43.6023, "lon": -116.1649}, {"name": "Telum Concepts LLC", "address": "1583 Sr 239", "city": "Stillwater", "state": "PA", "zip": "17878", "phone": "(570) 337-7166", "lat": 41.1515, "lon": -76.3696}, {"name": "The Bike Shoppe", "address": "4390 Washington Blvd", "city": "Ogden", "state": "UT", "zip": "84403", "phone": "(801) 476-1600", "lat": 41.1894, "lon": -111.9489}, {"name": "The Local Gear", "address": "74 Maple St", "city": "Cornish", "state": "ME", "zip": "04020", "phone": "(207) 625-9400", "lat": 43.7796, "lon": -70.7784}, {"name": "The Moto Stop", "address": "129 Blanco Dr", "city": "De Leon Springs", "state": "FL", "zip": "32130", "phone": "(386) 804-5702", "lat": 29.1166, "lon": -81.3488}, {"name": "The Outdoor Warehouse", "address": "41083 Sandalwood Circle", "city": "Murrieta", "state": "CA", "zip": "92562", "phone": "(800) 593-4124", "lat": 33.5631, "lon": -117.2738}, {"name": "The Outdoorsman", "address": "50 NE 2nd St", "city": "Ontario", "state": "OR", "zip": "97914", "phone": "(541) 889-3135", "lat": 44.0416, "lon": -116.9783}, {"name": "The Rusty Buck - Hunting & Outdoor Lifestyle", "address": "821 S Adams St", "city": "Versailles", "state": "IN", "zip": "47042", "phone": "(812) 609-4064", "lat": 39.0511, "lon": -85.2235}, {"name": "The Spoke Shop", "address": "1910 Broadwater Ave", "city": "Billings", "state": "MT", "zip": "59102", "phone": "(406) 656-8342", "lat": 45.7813, "lon": -108.5727}, {"name": "The Sportsman, Inc", "address": "1511 MS-1", "city": "Greenville", "state": "MS", "zip": "38701", "phone": "(662) 335-5018", "lat": 33.3787, "lon": -91.0468}, {"name": "The Urban Cyclery Shop", "address": "1939 Springfield Ave", "city": "Maplewood", "state": "NJ", "zip": "07040", "phone": "(973) 695-8398", "lat": 40.7279, "lon": -74.2656}, {"name": "Thick Bikes", "address": "62 S 15th St", "city": "Pittsburgh", "state": "PA", "zip": "15203", "phone": "(412) 390-3590", "lat": 40.4254, "lon": -79.9799}, {"name": "Time Out For Sports", "address": "9716 Belair Rd", "city": "Nottingham", "state": "MD", "zip": "21236", "phone": "(410) 248-0068", "lat": 39.3914, "lon": -76.4871}, {"name": "Tongass Trading Co.", "address": "2324 Tongass Ave", "city": "Ketchikan", "state": "AK", "zip": "99901", "phone": "(907) 225-5101", "lat": 55.372, "lon": -131.6832}, {"name": "Tongass Trading Co. Marine & Outdoors", "address": "2521 Marine Works Way", "city": "Ketchikan", "state": "AK", "zip": "99901", "phone": "(907) 225-5101", "lat": 55.372, "lon": -131.6832}, {"name": "Top Shot Archery", "address": "600 E Lincoln Hwy Ste C & D", "city": "New Lenox", "state": "IL", "zip": "60451", "phone": "(815) 320-6077", "lat": 41.5067, "lon": -87.9631}, {"name": "Townsend Outdoors", "address": "2301 S Main St", "city": "Hope", "state": "AR", "zip": "71801", "phone": "(870) 777-3330", "lat": 33.6736, "lon": -93.6068}, {"name": "Tri State E-Bikes", "address": "S3564 County Road M", "city": "Fountain City", "state": "WI", "zip": "54629", "phone": "(507) 459-4962", "lat": 44.1364, "lon": -91.6779}, {"name": "Trophy Adventures", "address": "N23988 Tranberg Ln", "city": "Ettrick", "state": "WI", "zip": "54627", "phone": "(715) 896-0820", "lat": 44.1724, "lon": -91.2635}, {"name": "TW's Bait & Tackle", "address": "3864 N Croatan Hwy", "city": "Kitty Hawk", "state": "NC", "zip": "27949", "phone": "(252) 261-7848", "lat": 36.0646, "lon": -75.7057}, {"name": "Typo Creek Outdoors", "address": "6230 238th Ave NE", "city": "Stacy", "state": "MN", "zip": "55079", "phone": "(651) 208-4462", "lat": 45.3975, "lon": -93.0177}, {"name": "Up North Sports", "address": "2000 Division St W", "city": "Bemidji", "state": "MN", "zip": "56601", "phone": "(218) 444-7669", "lat": 47.572, "lon": -94.8013}, {"name": "VTH Factory Mobile Bike Repair", "address": "500 Whistlestop Circle", "city": "Statesboro", "state": "GA", "zip": "30461", "phone": "(912) 536-9556", "lat": 32.45, "lon": -81.7158}, {"name": "Whale-Tales Archery", "address": "109 N Main Street", "city": "Dousman", "state": "WI", "zip": "53118", "phone": "(262) 965-2825", "lat": 43.0142, "lon": -88.4726}, {"name": "Wheat Ridge Cyclery at Ken Caryl", "address": "12402 C1B W Ken Caryl Ave", "city": "Littleton", "state": "CO", "zip": "80127", "phone": "(719) 628-1771", "lat": 39.592, "lon": -105.1328}, {"name": "Wicked Archery, LLC", "address": "16597 88th Rd N", "city": "Loxahatchee", "state": "FL", "zip": "33470", "phone": "(802) 279-9851", "lat": 26.7383, "lon": -80.276}, {"name": "Wood Sales & Service, Inc.", "address": "N5931 WI-54", "city": "Black River Falls", "state": "WI", "zip": "54615", "phone": "(800) 657-4653", "lat": 44.2954, "lon": -90.8313}, {"name": "Yamaha of Port Washington Inc", "address": "540 W Grand Ave", "city": "Port Washington", "state": "WI", "zip": "53074", "phone": "(262) 284-5995", "lat": 43.3955, "lon": -87.8797}]

def lookup_dealers(location):
    """Find 3 nearest Rambo dealers using geocoding + embedded dealer list."""
    import math
    try:
        geo = requests.get("https://nominatim.openstreetmap.org/search",
            params={"q": location, "format": "json", "limit": 1},
            headers={"User-Agent": "RamboBikesChat/1.0"}, timeout=6)
        geo_data = geo.json()
        if not geo_data:
            return None
        clat = float(geo_data[0]["lat"])
        clon = float(geo_data[0]["lon"])

        def haversine(lat1, lon1, lat2, lon2):
            R, d = 3958.8, math.radians
            a = math.sin(d(lat2-lat1)/2)**2 + math.cos(d(lat1))*math.cos(d(lat2))*math.sin(d(lon2-lon1)/2)**2
            return R * 2 * math.asin(math.sqrt(a))

        nearby = sorted([(haversine(clat, clon, d["lat"], d["lon"]), d) for d in _DEALERS if d.get("lat")],
                        key=lambda x: x[0])
        return [f"* **{d['name']}** ({round(mi,1)} mi) — {d['address']}, {d['city']}, {d['state']}   📞 {d['phone']}"
                for mi, d in nearby[:3]] or None
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
<style>*{margin:0;padding:0;box-sizing:border-box;}body{font-family:sans-serif;background:#f5f5f5;}
.banner{background:#cc0000;color:#fff;padding:10px 24px;text-align:center;font-size:13px;font-weight:600;}
.header{background:#1b1b1b;padding:16px 40px;display:flex;align-items:center;}
.logo{color:#fff;font-size:22px;font-weight:800;}
.hero{background:#1b1b1b;color:#fff;padding:80px 40px;text-align:center;}
.hero h1{font-size:48px;font-weight:800;}
.hero h1 span{color:#cc0000;}
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
        data             = request.get_json(force=True) or {}
        message          = (data.get("message") or "").strip()
        history          = data.get("history", [])
        customer_name    = (data.get("customer_name") or "").strip()
        customer_email   = (data.get("customer_email") or "").strip()
        case_already_created = data.get("case_already_created", False)

        if not message:
            return cors_response({"error": "No message provided"}, 400)

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
                lines = [f"* {m['desc']} — arriving {m['date']}" for m in matches[:3]]
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
        oai_msgs = [{"role": "system", "content": get_system_prompt()}]
        if customer_name or customer_email:
            oai_msgs.append({"role": "system",
                              "content": f"Customer: {customer_name or 'unknown'} / {customer_email or 'not provided'}"})
        if injected_data:
            oai_msgs.append({"role": "system",
                              "content": f"LIVE DATA FOR THIS QUERY:\n{injected_data}"})
        oai_msgs.extend(history[-20:])
        oai_msgs.append({"role": "user", "content": message})

        client   = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini", messages=oai_msgs,
            temperature=0.25, response_format={"type": "json_object"}, max_tokens=600)

        raw    = response.choices[0].message.content
        result = json.loads(raw)

        ai_message   = result.get("message", "Please call (952) 283-0777 for assistance.")
        escalate     = bool(result.get("escalate", False))
        escalate_to  = result.get("escalate_to")
        create_case  = bool(result.get("create_case", False))
        case_title   = result.get("case_title") or f"Chat - {customer_name or 'Customer'} - General"

        updated_history = list(history) + [
            {"role": "user",      "content": message},
            {"role": "assistant", "content": ai_message}
        ]

        case_result = None
        if (escalate or create_case) and not case_already_created and customer_email and NS_CONSUMER_KEY:
            assigned_id = JENNA_ID if escalate_to == "jenna" else MISTI_ID
            status_id   = "3" if escalate else "2"
            lines = []
            for h in history:
                lines.append(f"{'Customer' if h['role']=='user' else 'Bot'}: {h['content']}")
            lines += [f"Customer: {message}", f"Bot: {ai_message}"]
            case_result = create_netsuite_case(customer_name, customer_email, case_title,
                                              "\n".join(lines), assigned_id, status_id)

        return cors_response({"message": ai_message, "escalate": escalate,
                               "escalate_to": escalate_to, "history": updated_history,
                               "case_created": case_result})
    except json.JSONDecodeError:
        return cors_response({"message": "Trouble connecting. Call (952) 283-0777 or email cs@rambobikes.com."})
    except Exception as e:
        return cors_response({"message": "Something went wrong. Call (952) 283-0777 or email cs@rambobikes.com.",
                               "error": str(e)}, 500)

if __name__ == "__main__":
    app.run(debug=True, port=8080)
