# Rambo Bikes Chat Widget
## Deployment Guide

---

## STEP 1 — Get an OpenAI API Key

1. Go to: https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Name it: "Rambo Chat"
4. Copy the key (starts with sk-...)
5. Save it — you'll need it in Step 3

Estimated API cost: ~$15-30/month at normal chat volume (uses gpt-4o-mini)

---

## STEP 2 — Deploy Backend to Vercel

1. Create a free GitHub account if you don't have one: https://github.com
2. Create a new repo named: rambo-chat-backend
3. Upload all files from the /api folder + vercel.json + requirements.txt
   (Drag and drop into GitHub — no coding needed)
4. Go to: https://vercel.com → Sign up with GitHub
5. Click "Add New Project" → Import your rambo-chat-backend repo
6. Vercel auto-detects Python — click Deploy
7. Your API URL will be: https://rambo-chat-backend.vercel.app

---

## STEP 3 — Set Environment Variables in Vercel

In your Vercel project → Settings → Environment Variables, add:

| Variable            | Value                                          |
|---------------------|------------------------------------------------|
| OPENAI_API_KEY      | sk-... (your OpenAI key from Step 1)           |
| NS_ACCOUNT_ID       | 5108296                                        |
| NS_CONSUMER_KEY     | 62dcb9b1151f4ce47301b73765b8438874992d57d0ca57fa05f78aa994e14ba0 |
| NS_CONSUMER_SEC     | 35f728cf6037c3b422df23233765e2418441f82cba98e90d4bc18ac4b9197cb7 |
| NS_TOKEN_ID         | 19d53555407d9ef6b531720869dd543602fe157e823672a1b368e93215b19223 |
| NS_TOKEN_SEC        | 89f33464075517f514ccfa2ed30e69afd14acc005efeac595ad235cbbd26e7eb |

After adding all variables → click "Redeploy" in Vercel.

---

## STEP 4 — Update Widget with Your API URL

Open: shopify/rambo-chat-widget.js
Line 13: Change CHAT_API_URL to your actual Vercel URL:
  const CHAT_API_URL = 'https://YOUR-PROJECT.vercel.app/api/chat';

---

## STEP 5 — Add Widget to Shopify

1. In Shopify admin → Online Store → Themes
2. Click the "..." menu next to your active theme → Edit code
3. Find: layout/theme.liquid
4. Find the closing </body> tag near the bottom of the file
5. Paste the entire contents of shopify/rambo-chat-widget.js inside a <script> tag:

   <script>
   [paste entire contents of rambo-chat-widget.js here]
   </script>

6. Click Save

The widget will appear on all pages of rambobikes.com immediately.

---

## HOW IT STAYS UPDATED AUTOMATICALLY

The chat agent uses the same knowledge base as the email agent (rambo_kb_v2.md).
When the Gumloop email agent's KB is updated, the chat agent system prompt in
api/index.py gets updated at the same time — one update, everywhere.

To update the chat KB:
1. Update SYSTEM_PROMPT in api/index.py
2. Push to GitHub
3. Vercel auto-deploys in ~30 seconds

No manual work in a chat platform. No copy/paste. Just one file.

---

## HOW NETSUITE CASES ARE CREATED

Automatically when:
- Customer asks to speak to a human
- Customer mentions legal/safety issues
- Customer is from Canada (→ Jenna)
- Unresolved after 3+ exchanges
- Any technical issue the bot can't fully resolve

Case includes:
- Customer name + email
- Full chat transcript
- Auto-assigned to Misti (1717307) or Jenna (2144573) per routing rules
- Status: Escalated (3) for urgent, In Progress (2) for standard

---

## ESTIMATED COSTS

| Service         | Cost           |
|-----------------|----------------|
| Vercel hosting  | FREE           |
| OpenAI API      | ~$15-30/month  |
| Tidio           | $0 (cancelled) |
| **Total**       | **~$15-30/mo** |

vs Tidio Plus: $499/month

---

## TESTING

After deploy, test your API directly:
curl -X POST https://YOUR-PROJECT.vercel.app/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What tube size does my Rambo bike use?","history":[],"customer_name":"Test","customer_email":"test@test.com"}'

---

*Rambo Bikes Chat System | Built May 2026*
