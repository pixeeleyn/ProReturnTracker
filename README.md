# Risk404 CSV upload backend

This package adds a FastAPI API around the three supplied scripts and includes a working upload/results page. The existing hosted Game Boy frontend is unchanged until a backend URL is deployed and connected.

## Run locally (Mac)

1. Extract this folder and open Terminal inside it.
2. Run `python3 -m venv .venv`
3. Run `source .venv/bin/activate`
4. Run `pip install -r requirements.txt`
5. Run `uvicorn main:app --reload`
6. Open http://127.0.0.1:8000 and choose the three example CSVs. Interactive API documentation: http://127.0.0.1:8000/docs

## GitHub and Render

1. Create a private GitHub repository named risk404-backend.
2. Add these files at the repository root (main.py and requirements.txt at top level). Keep scripts/, static/, and examples/ intact. Do not upload .venv or real customer data.
3. Commit the files. Add your partner through Settings > Collaborators if needed.
4. In Render choose New > Web Service, connect GitHub, and select this repository.
5. Runtime: Python. Build command: `pip install -r requirements.txt`. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`. Health check: `/health`.
6. Select your hosting plan and deploy. Open the returned URL; the upload page is usable immediately.
7. Set ALLOWED_ORIGINS to the frontend origin, without trailing slash: `https://zsp-gameboy-lab.burblingisle256.chatgpt.site`. Multiple origins are comma separated.
8. Send the deployed backend URL to connect the Game Boy frontend. GitHub alone does not execute the backend.

## API contract / frontend integration

POST /analyze as multipart/form-data with exactly three file fields: customers, orders, returns. Use `FormData`; do not manually set Content-Type. Example:

```js
const data = new FormData();
data.append('customers', customersInput.files[0]);
data.append('orders', ordersInput.files[0]);
data.append('returns', returnsInput.files[0]);
const response = await fetch(`${BACKEND_URL}/analyze`, {method:'POST', body:data});
const result = await response.json();
if (!response.ok) throw new Error(result.detail);
// Render result.summary, result.product_analysis, result.alerts, etc.
```

Returned keys: summary (object), product_analysis, reason_analysis, damage_analysis, category_analysis, alerts, tasks (arrays), audit (counts), scope (text). All current demo values must be replaced, not left visible after a successful scan. The included page uses uploaded results and safe text rendering.

## Required CSV columns

- customers: customer_id, region, signup_date, segment, payment_terms, credit_limit.
- orders: order_id, customer_id, product, category, region, order_date, payment_date, quantity, unit_price, discount.
- returns: return_id, order_id, return_date, quantity_returned, refund_amount, reason.

Dates: YYYY-MM-DD or MM/DD/YYYY. payment_date may be blank. Discount is a fraction (0.15 = 15%), not 15 or 15%. Numeric values must have no currency symbols or thousands separators. IDs and grouping labels cannot be blank. Returns should not repeat order/customer metadata columns. UTF-8 CSV only; 10 MiB and 100,000 rows maximum per file. Headers-only returns are supported.

## What was missing / limits

The original files are disk-based scripts, not an API. They run in this order: clean_data.py, analyze_return.py, detect_risks.py. This adapter runs them in a temporary isolated directory for each request, validates inputs, returns JSON, and deletes temporary files afterward. It preserves the supplied rules: >10% return rate with >=100 units sold; shipping-damage refund alerts >10,000 and >50,000.

These scripts analyze returns/shipping damage, not revenue growth, margin leakage, or overdue invoices. Those features need additional backend calculations before the old dashboard can truthfully show them.

Task status is not persistent across scans. A database and user/session model are needed for that. The API currently has no authentication or rate limiting; add those before opening it to general public traffic. It does not send emails. The full-file upload is parsed in memory and analyses run synchronously; use a job queue for larger workloads. Application file limits do not replace an ingress request-body limit for public hosting.

The cleaner excludes invalid dated/negative-value rows and reports exclusion counts. Refunds exceeding sale value, returns preceding order date, and unknown customer IDs need business rules beyond the supplied scripts. Those checks are not silently invented here. No original files were modified; the package contains copies.

## Validation

Run `python test_api.py` after installing requirements plus `httpx`. Tests cover real pipeline output, missing columns, invalid numbers, cumulative over-return, and header-only returns.
