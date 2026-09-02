# Smart Bill Reader

This is a simple web application created for the COREnergy Software Engineering Intern examination. Users can upload a PNG, JPG/JPEG, or PDF copy of a utility bill or invoice. The backend sends the document to the Gemini API for document analysis and returns a validated JSON response containing the requested fields.

## Features

- File upload for PNG, JPG/JPEG, and PDF
- Drag-and-drop upload zone
- Loading state while AI extraction is running
- User-friendly validation and error messages
- Server-side file size and file signature checks
- AI-based rejection of files that are clearly not bills/invoices
- Structured display of:
  - `vendor_name`
  - `invoice_date`
  - `total_amount`
  - `tax_amount`
  - `line_items`
- Model-estimated readability confidence shown in the UI
- Dockerized application

> Note: the displayed confidence values are **model-estimated readability confidence**. It is not calibrated confidence scores returned natively by the Gemini API.

## Technology Stack

- **Frontend:** Plain HTML, CSS, and JavaScript
- **Backend:** Python + FastAPI
- **AI/OCR:** Google Gemini Developer API (`gemini-3.6-flash` by default)
- **Container:** Docker / Docker Compose

## Why Gemini, and not other AI?

Gemini was chosen because it offers a practical balance of multimodal document understanding, structured JSON output, speed, and low setup complexity. It can process both images and PDFs directly, which makes it suitable for extracting fields like vendor name, invoice date, tax, totals, and line items in one workflow. Compared with more specialized services such as AWS Textract or Google Document AI, Gemini requires less cloud infrastructure and configuration for a prototype of this scale. It was also a cost-effective choice for development and testing.

The model name is stored in an environment variable (`GEMINI_MODEL`) so it can be changed later without modifying application code.

## Project Structure

```text
.
├── app/
│   ├── main.py                     # FastAPI routes and upload validation
│   ├── models.py                   # Pydantic response models
│   ├── services/
│   │   └── gemini_extractor.py     # Gemini request, prompt, schema, parsing
│   └── static/
│       ├── index.html              # UI
│       ├── styles.css              # Styling
│       └── app.js                  # Upload and results behavior
├── samples/                        # Sample test bills
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Run with Docker (Recommended)

### 1. Prerequisites

Install:

- Docker Desktop
- A Gemini API key from Google AI Studio

### 2. Configure the API key

Copy the sample environment file:

```bash
cp .env.example .env
```

Open `.env` and replace:

```env
GEMINI_API_KEY=replace_with_your_api_key
```

with your actual key.

### 3. Build and start

```bash
docker compose up --build
```

Open:

```text
http://localhost:8000
```

To stop the app:

```bash
docker compose down
```

## Run Without Docker (Development Only)

The examination requires the application to run with container technology, so Docker is the recommended submission method. For development, it can also be run directly:

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate       # Windows
pip install -r requirements.txt
cp .env.example .env
```

Set the environment variables from `.env`, then run:

```bash
uvicorn app.main:app --reload
```

## API

### `POST /api/extract`

Multipart form-data field:

- `file`: PNG, JPG/JPEG, or PDF

Example successful response:

```json
{
  "is_bill_or_invoice": true,
  "validation_reason": "Document contains an issuer, billing date, itemized charges, and a total amount due.",
  "vendor_name": "Sample Electric Company",
  "invoice_date": "2026-08-15",
  "total_amount": 2543.75,
  "tax_amount": 272.54,
  "line_items": [
    {
      "description": "Electricity consumption",
      "amount": 2271.21
    }
  ],
  "estimated_confidence": {
    "vendor_name": 0.99,
    "invoice_date": 0.98,
    "total_amount": 0.99,
    "tax_amount": 0.95,
    "line_items": 0.94
  }
}
```

### `GET /health`

Returns:

```json
{"status":"ok"}
```

## Prompt Engineering Approach

The AI is instructed to:

1. Classify whether the uploaded document is actually a bill/invoice/receipt-like document.
2. Treat the uploaded document as the only source of truth.
3. Use `null` instead of guessing unreadable or missing values.
4. Distinguish invoice date from due date/payment date.
5. Use the final amount due/payable as `total_amount`.
6. Extract tax only when it is explicitly printed, rather than calculating it.
7. Return line items without totals/subtotals unless those are the only available charges.
8. Return numeric values without currency symbols or commas.
9. Follow a strict JSON Schema so the backend receives predictable types.

## Error Handling / Resilience

The application handles:

- Unsupported MIME types → HTTP 415
- Empty uploads → HTTP 400
- Files larger than 10 MB → HTTP 413
- Files whose binary signature does not match the declared type → HTTP 400
- Clearly non-bill files → HTTP 422
- AI/API failures → HTTP 502 with a user-friendly frontend message
- Missing server API key → HTTP 500

Temporary Gemini API failures are retried up to three total attempts using exponential backoff. Retries are limited to transient errors such as HTTP 429, 500, 502, 503, and 504. Permanent failures such as invalid authentication are returned immediately rather than retried.

## Assumptions and Trade-offs

- The maximum upload size is set to **10 MB** because the exam requires a file-size failure state but does not prescribe a specific limit.
- Currency is not returned because it is not part of the required extraction target. The amounts are therefore displayed as plain numbers to avoid incorrectly assuming PHP/USD/etc.
- The app uses one FastAPI container that serves both the API and static frontend. This reduces deployment complexity while still keeping frontend and backend responsibilities separated in the source code.
- The application does not permanently store uploaded bills. The file is read in memory, sent to the AI service, and discarded after the request.
- Confidence values are explicitly labeled as model-estimated rather than native/calibrated API confidence.

## Suggested Test Cases

1. A clear PDF utility bill.
2. A phone photo of an invoice.
3. A bill with no explicit tax line (expect `tax_amount: null`).
4. A blurred bill (expect lower confidence or null fields).
5. A non-bill image such as a pet/photo (expect rejection).
6. A renamed invalid file with a `.pdf` or `.jpg` extension (expect rejection).
7. A file larger than 10 MB (expect rejection).

## Security Notes

- Do **not** commit `.env` or the API key to GitHub.
- `.env` is already included in `.gitignore`.
- For a production application, additional controls such as authentication, rate limiting, malware scanning, logging policies, and tighter data-retention/privacy controls would be appropriate.
