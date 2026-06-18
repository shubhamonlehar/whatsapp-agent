# Mock WhatsApp Provider

TrustSignal-compatible WhatsApp mock server for recruitment QA workflows. It lets an ATS test delivery events, read events, candidate replies, CV uploads, failed delivery, retry/replay, and scripted scenarios without real WhatsApp numbers.

Visible UI banner: **Mock WhatsApp Provider · Not connected to real WhatsApp**.

## TrustSignal Contract Summary

The WhatsApp contract was derived from `Trustsignal API Collection.postman_collection.json`.

Implemented send endpoints:

- `POST /api/v1/whatsapp/single?api_key=...`
- `POST /api/v1/whatsapp/bulk?api_key=...`
- `POST /api/v1/whatsapp/agent-reply?api_key=...`
- `POST /api/v1/whatsapp/otp?api_key=...`
- `POST /api/v1/whatsapp/typing-indicator?api_key=...`
- `POST /api/v1/whatsapp/mark-read?api_key=...`

Supported query parameters include `api_key`, `sval`, and any extra TrustSignal query values. Extra values are stored with the outbound request.

Success responses follow the collection shape:

```json
{
  "message": "Request process successfully",
  "results": {
    "to": "919999999999",
    "transaction_id": "173144958289308830991789517202528921"
  },
  "success": true
}
```

Errors follow the collection shape:

```json
{
  "errors": [
    {
      "code": "114",
      "codeMsg": "INVALID_SENDERID",
      "message": "Invalid senderid"
    }
  ],
  "success": false
}
```

Webhook payloads follow the collection examples:

- Status callbacks use `webhook_type: "whatsapp_template"` with `value.statuses[]`.
- Candidate replies use `webhook_type: "customer_response"` with `value.contacts[]` and `value.messages[]`.
- Media/document replies include top-level `fileurl`.

## Switch The ATS

Change only:

```json
{
  "sender": "9810330589",
  "api_base_url": "http://localhost:8080",
  "default_language": "en"
}
```

## Backend Setup

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
python seed.py
uvicorn app.main:app --reload --port 8080
```

The backend also creates tables on startup to make first local runs forgiving.

OpenAPI docs:

```text
http://localhost:8080/docs
```

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

## Environment

Copy `.env.example` to `.env` and edit values as needed.

Important defaults:

- `DATABASE_URL=sqlite:///./mock_trustsignal.db`
- `PUBLIC_BASE_URL=http://localhost:8080`
- `DEFAULT_SENDER=9810330589`
- `STRICT_API_KEY=false`
- `VALID_API_KEYS=test-api-key`
- `VALID_SENDERS=9810330589`
- `ATS_WEBHOOK_URL=http://localhost:3000/api/webhooks/whatsapp`
- `ATS_WEBHOOK_ENABLED=true`

If `ATS_WEBHOOK_URL` is empty, webhook events are still stored locally and can be replayed later.

## Mock APIs

- `GET /health`
- `GET /mock/dashboard`
- `GET /mock/messages`
- `GET /mock/candidates`
- `GET /mock/candidates/{id}`
- `POST /mock/candidates/{id}/reply`
- `POST /mock/candidates/{id}/upload-cv`
- `POST /mock/messages/{transactionId}/status`
- `POST /mock/messages/{transactionId}/replay-webhook`
- `GET /mock/webhook-events`
- `POST /mock/webhook-events/{id}/retry`
- `GET /mock/scenarios`
- `POST /mock/scenarios`
- `GET /mock/settings`
- `PATCH /mock/settings`
- `POST /mock/settings/test-ats-connection`

## File Uploads

Uploads are stored in:

```text
storage/uploads
```

Public URLs are exposed as:

```text
http://localhost:8080/files/{filename}
```

Allowed CV/media extensions: `pdf`, `doc`, `docx`, `jpg`, `jpeg`, `png`.

In the UI, open **Candidates**, choose a candidate, and use the WhatsApp-style chat view. The **Attach** button and **Choose local files** action upload real local files from your machine and generate the same candidate-response webhooks as simulated CV uploads.

## Tests

```bash
.venv\Scripts\python.exe -m pytest backend/tests -q
```

Covered behavior includes send, webhook generation, unknown candidate creation, CV upload, webhook retry, invalid sender, invalid API key, scenario execution, and invalid JSON bodies.
