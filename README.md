# SMSBower Client API Documentation (Agent/IDE Friendly)

> Source page: `https://smsbower.app/api/?page=client`
> 
> Base handler (for most API calls): `https://smsbower.page/stubs/handler_api.php`
> 
> Method: `GET` or `POST` (query style shown below)

---

## 1) Quick Start

All requests must include:

- `api_key` = your API key
- `action` = API action name

Example:

```bash
curl "https://smsbower.page/stubs/handler_api.php?api_key=YOUR_API_KEY&action=getBalance"
```

Typical plain-text responses:

- `ACCESS_BALANCE:12.34`
- `BAD_KEY`
- `BAD_ACTION`

---

## 2) Endpoints Summary

## 2.1 Get Balance

```http
GET https://smsbower.page/stubs/handler_api.php?api_key=$api_key&action=getBalance
```

**Success:**

- `ACCESS_BALANCE:<balance>`

**Errors:**

- `BAD_KEY`

---

## 2.2 Get Number

```http
GET https://smsbower.page/stubs/handler_api.php?api_key=$api_key&action=getNumber&service=$service&country=$country&maxPrice=$maxPrice&providerIds=$providerIds&exceptProviderIds=$exceptProviderIds&phoneException=$phoneException&ref=$ref
```

**Params:**

- `service` (required): service code
- `country` (required): country code/id
- `maxPrice` (optional): max price
- `providerIds` (optional): e.g. `1,2,3`
- `exceptProviderIds` (optional): e.g. `4,5`
- `phoneException` (optional): blocked prefixes, e.g. `7918,7900111`
- `ref` (optional): referral ID

**Success:**

- `ACCESS_NUMBER:<activationId>:<phoneNumber>`

**Errors:**

- `BAD_KEY`
- `BAD_ACTION`
- `BAD_SERVICE`

---

## 2.3 Get SMS Status

```http
GET https://smsbower.page/stubs/handler_api.php?api_key=$api_key&action=getStatus&id=$id
```

**Params:**

- `id` = activation ID

**Possible responses:**

- `STATUS_WAIT_CODE` (waiting for SMS)
- `STATUS_WAIT_RETRY:<lastCode>` (waiting for next SMS)
- `STATUS_CANCEL` (activation canceled)
- `STATUS_OK:<code>` (code received)

**Errors:**

- `BAD_KEY`
- `BAD_ACTION`
- `NO_ACTIVATION`

---

## 2.4 Set Activation Status

```http
GET https://smsbower.page/stubs/handler_api.php?api_key=$api_key&action=setStatus&status=$status&id=$id
```

**Params:**

- `id` = activation ID
- `status` values:
  - `1` = number ready / SMS sent to number
  - `3` = request another SMS (free)
  - `6` = complete activation
  - `8` = cancel activation

**Success responses:**

- `ACCESS_READY`
- `ACCESS_RETRY_GET`
- `ACCESS_ACTIVATION`
- `ACCESS_CANCEL`

**Errors:**

- `NO_ACTIVATION`
- `BAD_STATUS`
- `BAD_KEY`
- `BAD_ACTION`
- `EARLY_CANCEL_DENIED`

---

## 2.5 Get Prices

```http
GET https://smsbower.page/stubs/handler_api.php?api_key=$api_key&action=getPrices&service=$service&country=$country
```

Returns JSON price/count matrix by country + service.

---

## 2.6 Get Services List

```http
GET https://smsbower.page/stubs/handler_api.php?api_key=$api_key&action=getServicesList
```

Sample:

```json
{
  "status": "success",
  "services": [
    { "code": "kt", "name": "KakaoTalk" }
  ]
}
```

---

## 2.7 Get Countries

```http
GET https://smsbower.page/stubs/handler_api.php?api_key=$api_key&action=getCountries
```

Returns country list with localized names.

---

## 2.8 Get Number V2

```http
GET https://smsbower.page/stubs/handler_api.php?api_key=$api_key&action=getNumberV2&service=$service&country=$country&maxPrice=$maxPrice&providerIds=$providerIds&exceptProviderIds=$exceptProviderIds
```

**Success (JSON):**

```json
{
  "activationId": "id",
  "phoneNumber": "number",
  "activationCost": "activationCost",
  "countryCode": "countryCode",
  "canGetAnotherSms": true,
  "activationTime": "activationTime",
  "activationOperator": "activationOperator"
}
```

**Errors:** `BAD_KEY`, `BAD_ACTION`, `BAD_SERVICE`

---

## 2.9 Prices V2

```http
GET https://smsbower.page/stubs/handler_api.php?api_key=$api_key&action=getPricesV2&service=$service&country=$country
```

Returns deeper price tiers by country/service.

---

## 2.10 Prices V3

```http
GET https://smsbower.page/stubs/handler_api.php?api_key=$api_key&action=getPricesV3&service=$service&country=$country
```

Returns provider-level price/count details.

**Errors:**

- `BAD_KEY`
- `BAD_ACTION`
- `BAD_SERVICE`
- `BAD_COUNTRY`

---

## 2.11 Get Static Wallet

```http
GET https://smsbower.page/api/payment/getActualWalletAddress?api_key=$api_key&coin=$coin&network=$network
```

**Params:**

- `coin`: `usdt` or `trx`
- `network`: e.g. `tron`

**Sample:**

```json
{ "wallet_address": "TFGMAwTfxtxKvy1mTTHr7XJaXeumjdmhGg" }
```

---

## 2.12 Webhook Notifications

Set your webhook URL in profile settings.

SMS webhook POST payload example:

```json
{
  "activationId": 123456,
  "service": "go",
  "text": "Sms text",
  "code": "12345",
  "country": 2,
  "receivedAt": "2023-01-01 12:00:00"
}
```

Server requirements:

- Must return HTTP `200`
- Retry policy: after ~1 min, then ~5 min if failed

Documented source IP to whitelist:

- `167.235.198.205`

---

## 3) Typical API Flow

1. `getNumber` / `getNumberV2`
2. Optional: `setStatus=1`
3. Poll `getStatus` until `STATUS_OK:<code>`
4. If needed: `setStatus=3` (another SMS)
5. Finish: `setStatus=6`
6. Cancel (if needed): `setStatus=8`

---

## 4) Error Handling Rules (for bots/tools)

- Treat plain-text `BAD_*` as hard errors.
- Treat `STATUS_WAIT_CODE` as retryable state.
- Use backoff polling (e.g., 3s -> 5s -> 8s; max interval 15s).
- Add request timeout (8–15s).
- Never log/store full API key in plaintext logs.

---

## 5) JavaScript (Node.js) Minimal Client

```js
// smsbower-client.js
const BASE = "https://smsbower.page/stubs/handler_api.php";

async function callSmsBower(params) {
  const url = new URL(BASE);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
  });

  const res = await fetch(url, { method: "GET" });
  const text = (await res.text()).trim();

  // Try JSON first
  try {
    return { ok: true, type: "json", data: JSON.parse(text) };
  } catch {
    return { ok: true, type: "text", data: text };
  }
}

async function getBalance(apiKey) {
  return callSmsBower({ api_key: apiKey, action: "getBalance" });
}

async function getNumber(apiKey, service, country, maxPrice) {
  return callSmsBower({
    api_key: apiKey,
    action: "getNumber",
    service,
    country,
    maxPrice,
  });
}

async function getStatus(apiKey, id) {
  return callSmsBower({ api_key: apiKey, action: "getStatus", id });
}

module.exports = { callSmsBower, getBalance, getNumber, getStatus };
```

---

## 6) Telegram Bot Integration Pattern

- `/buy <service> <country>` -> call `getNumber`
- Store `activationId` per chat/user
- Run polling job or webhook-based flow
- When `STATUS_OK:<code>` -> send code to user
- After success -> `setStatus=6`

Pseudo logic:

```text
on /buy:
  activation = getNumber(...)
  every 5s:
    st = getStatus(activationId)
    if STATUS_OK:
      send code
      setStatus(6)
      stop polling
    if STATUS_CANCEL or timeout:
      notify user
      stop polling
```

---

## 7) IDE Agent Tips

- Keep API key in `.env` (`SMSBOWER_API_KEY=...`)
- Build a tiny wrapper module (`smsbower-client`) and reuse it
- Normalize responses into a strict internal shape:
  - `{ ok, state, code, raw }`
- Add unit tests for response parsing (`ACCESS_NUMBER`, `STATUS_OK`, `BAD_KEY`, etc.)

---

## 8) Notes / Caveats

- Source docs contain some formatting inconsistencies (`getN umber` line wraps, typo-like query fragments). URLs in this file are normalized for practical use.
- Always verify latest endpoint behavior from provider panel/docs.

---

## 9) Ready-to-copy .env example

```env
SMSBOWER_API_KEY=your_real_api_key_here
SMSBOWER_BASE_URL=https://smsbower.page/stubs/handler_api.php
```

---

Prepared for: **IDE agents, automation scripts, and Telegram bot development**.

---

## 10) Telegram Bot (Premium UI, 5 Languages)

This repo now includes a ready-to-run Telegram bot:

- Script: `smsbower_premium_bot.py`
- Requirements: `requirements.txt`
- Database: Supabase (persistent cloud database)
- Languages: English, Bengali, Hindi, Arabic, Russian

### Run

```bash
pip install -r requirements.txt
python smsbower_premium_bot.py
```

PowerShell quick run (Windows):

```powershell
.\run-templine-bot.ps1
```

### Optional Environment Variables

```env
BOT_TOKEN=your_telegram_bot_token
TEMPLINE_API_KEY=your_templine_api_key
TEMPLINE_BASE_URL=https://smsbower.page/stubs/handler_api.php
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
# OR
SUPABASE_KEY=your_supabase_secret_or_service_key
ADMIN_USER_ID=5742928021
POLL_INTERVAL_SECONDS=4
```

### Webhook Mode (Optional)

If `WEBHOOK_URL` is set, bot will run in webhook mode.
Otherwise it uses long polling.

---

## 11) 24/7 Deploy (GitHub + Render + Docker)

### Files Added For Deployment

- `Dockerfile`
- `docker-entrypoint.sh`
- `render.yaml`
- `.dockerignore`
- `.gitignore`
- `push-github.ps1`

### Important Note (24/7)

Render free plans can sleep. For true 24/7 uptime use a paid plan (e.g. `Starter` or higher).

### A) Push to GitHub

From project folder:

```powershell
.\push-github.ps1 -RepoUrl "https://github.com/s28626198-sys/otpbotv2.git" -Branch "main"
```

### B) Create Render Web Service

1. Go to Render Dashboard.
2. New + -> Web Service.
3. Connect your GitHub repo: `otpbotv2`.
4. Render will detect `render.yaml` automatically.

### C) Required Render Environment Variables

Set these in Render (or via `render.yaml` where marked `sync: false`):

- `BOT_TOKEN`
- `TEMPLINE_API_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
  - or `SUPABASE_KEY`

Already prefilled in `render.yaml`:

- `SUPABASE_URL`
- `ADMIN_USER_ID`
- `TEMPLINE_BASE_URL`
- `POLL_INTERVAL_SECONDS`
- `CANCEL_LOCK_SECONDS`
- `MAX_MONITOR_SECONDS`
- `WEBHOOK_PATH`

`WEBHOOK_URL` is auto-bound from service URL in `render.yaml`.

### D) Runtime Behavior

- Container starts `docker-entrypoint.sh`
- If `WEBHOOK_URL` is missing, it falls back to `RENDER_EXTERNAL_URL`
- Bot runs webhook mode on Render web service port (`PORT`)

This keeps existing bot flows unchanged while making deployment production-ready.

### E) Supabase One-Time Setup

1. Open Supabase Dashboard -> SQL Editor.
2. Run [`supabase_schema.sql`](./supabase_schema.sql) once (or re-run to apply RLS disable changes).
3. Deploy/redeploy Render service.

Use `Secret/Service Role` key only. `Publishable/Anon` key will fail for server writes.
