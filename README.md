# amazonscraperapi-sdk

[![PyPI version](https://img.shields.io/pypi/v/amazonscraperapi-sdk)](https://pypi.org/project/amazonscraperapi-sdk/)
[![PyPI downloads](https://img.shields.io/pypi/dm/amazonscraperapi-sdk)](https://pypi.org/project/amazonscraperapi-sdk/)
[![license](https://img.shields.io/pypi/l/amazonscraperapi-sdk)](./LICENSE)

Official Python SDK for **[Amazon Scraper API](https://www.amazonscraperapi.com/)**. Pay only for successful (2xx) responses — non-2xx never cost you anything. Pricing starts at $0.90 per 1,000 requests on pay-as-you-go, drops to a flat **$0.50 per 1,000 requests** on Custom plans. 1,000 free requests on signup, no card. Drop into any Python project to fetch structured Amazon product data, run keyword searches, or queue async batches with webhook callbacks.

## Benchmark (live production, 2026-04)

Measured on our own infrastructure against a 30-query mixed international set:

| Metric | Value |
|---|---|
| Median latency (product, US) | **~2.6 s** |
| P95 latency | **~6 s** |
| P99 latency | ~10.5 s |
| Price / 1,000 Amazon products | **$0.50** flat |
| Concurrent threads (entry paid plan) | **50** |
| Marketplaces supported | **20+** |
| Billing unit | per successful (2xx) response |

---

## Install

```bash
pip install amazonscraperapi-sdk
```

Requires Python >= 3.9. Built on `httpx`.

## Quick start - single product

```python
from amazonscraperapi import AmazonScraperAPI

asa = AmazonScraperAPI(api_key="asa_live_...")

product = asa.product(query="B09HN3Q81F", domain="com")

print(product["title"])
# "LEGEND COOKWARE 5-Ply Stainless Steel Cookware Set, 14-Piece..."
print(product["price"], product["currency"])
# 549.99 USD
print(product["rating"], product["reviews_count"])
# 4.5 865
```

### Example output (trimmed, ~55 fields in total)

```python
{
    "asin": "B09HN3Q81F",
    "title": "LEGEND COOKWARE 5-Ply Stainless Steel Cookware Set, 14-Piece...",
    "brand": "LEGEND COOKWARE",
    "price": 549.99,
    "price_strikethrough": None,
    "currency": "USD",
    "rating": 4.5,
    "reviews_count": 865,
    "stock": "In Stock",
    "is_prime": True,
    "images": ["https://m.media-amazon.com/images/I/71Q3a8JH5NL._AC_SY355_.jpg", "..."],
    "bullet_points": "5-PLY STAINLESS STEEL COOKWARE HEATS EVENLY - Five layers of steel...",
    "sales_rank": [
        {"ladder": [{"name": "Kitchen & Dining", "url": None}], "rank": 36177},
        {"ladder": [{"name": "Kitchen Cookware Sets", "url": None}], "rank": 174},
    ],
}
```

## Keyword search

```python
results = asa.search(
    query="wireless headphones",
    domain="co.uk",
    sort_by="avg_customer_review",
    pages=1,
)

for p in results["products"]:
    # Sponsored cards have sponsored_position instead of organic_position.
    print(p["organic_position"], p["asin"], p["title"], p["price"], p["rating"])
```

## Async batch (up to 1,000 ASINs with webhook callback)

```python
batch = asa.create_batch(
    endpoint="amazon.product",
    items=[
        {"query": "B09HN3Q81F", "domain": "com"},
        {"query": "B000ALVUM6", "domain": "de", "language": "de_DE"},
        # ... up to 1,000
    ],
    webhook_url="https://your.server/webhooks/asa",
)

print("batch id:", batch["id"])
# SAVE THIS. Webhook signing secret is returned only once:
print("webhook secret:", batch["webhook_signature_secret"])

# Alternative: poll
status = asa.get_batch(batch["id"])
print(f"{status['processed_count']}/{status['total_count']}")
```

## Verifying webhook signatures

```python
from amazonscraperapi import verify_webhook_signature
from fastapi import FastAPI, Request, HTTPException
import json, os

app = FastAPI()

@app.post("/webhooks/asa")
async def asa_webhook(request: Request):
    raw = await request.body()
    signature = request.headers.get("X-ASA-Signature")
    if not verify_webhook_signature(signature, raw, secret=os.environ["WEBHOOK_SECRET"]):
        raise HTTPException(401, "invalid signature")
    payload = json.loads(raw)
    # process payload["results"]
```

## What the API solves for you

Building a production-grade Amazon scraper in-house is a 2-4 week engineering project plus permanent maintenance. This SDK wraps [Amazon Scraper API](https://www.amazonscraperapi.com/), which has already solved:

| Pain point | What we handle |
|---|---|
| **Amazon CAPTCHAs / robot pages** | Auto-detected, retried through a heavier proxy tier (datacenter, residential, premium) |
| **Brittle CSS selectors** | Extractors update as Amazon changes layouts. Your code stays the same. |
| **20+ marketplaces** | `amazon.de`, `.co.uk`, `.co.jp`, `.com.br`, and more. Each with marketplace-specific parsing quirks. |
| **Country-matched residential IPs** | `amazon.de` auto-routes through German IPs. |
| **Rotating proxies + anti-fingerprinting** | TLS fingerprints, headers, cookies handled server-side. |
| **Structured JSON output** | Title, price, rating, reviews, variants, seller, images. Parsed. |
| **Batch/async jobs** | 1,000 ASINs submitted, webhook-delivered on completion. |

**Time saved:** a greenfield Python Amazon scraper built to this spec takes roughly 80 engineer-hours (including anti-bot handling and marketplace variants). This SDK is 10 minutes.

## Error handling

Every failed call raises `AmazonScraperAPIError` with `status_code`, `code` (the API's error code, or `None`) and `body` (the parsed JSON body). The SDK does not retry on its own, so match on `e.code` and decide:

```python
import time
from amazonscraperapi import AmazonScraperAPI, AmazonScraperAPIError

asa = AmazonScraperAPI(api_key="asa_live_...")

try:
    product = asa.product(query="B09HN3Q81F", domain="com")
except AmazonScraperAPIError as e:
    if e.code == "INSUFFICIENT_CREDITS":
        pass  # top up
    elif e.code == "RATE_LIMITED":
        time.sleep(e.body["error"].get("retry_after_ms", 1000) / 1000)
    elif e.code == "target_unreachable":
        time.sleep(60)  # not charged; retry once
    else:
        raise
```

| HTTP | `code` | When you see it | Recommended action |
|---|---|---|---|
| 400 | `invalid_params` | Missing `query`, unsupported `domain`, bad `sort_by` | Fix request; don't retry |
| 401 | `INVALID_API_KEY` | Missing, malformed, revoked | Verify `ASA_API_KEY`; rotate if leaked |
| 402 | `INSUFFICIENT_CREDITS` | Balance empty | Top up; renews each billing cycle |
| 404 | `product_not_found` | ASIN delisted, malformed, or not on this marketplace | Don't retry; drop the ASIN |
| 429 | `RATE_LIMITED` | Over request-rate budget | Wait `error.retry_after_ms`; retry |
| 429 | `CONCURRENCY_LIMIT` | Over plan's parallel cap | Reduce parallelism or upgrade. `X-Concurrency-*` headers guide backoff |
| 502 | `target_unreachable` | Amazon blocked every internal retry (`last_block_reason` says why) | Retry after 60s or more. Not charged |
| 502 | `extraction_failed` | Layout we can't parse | Retry later; report with `X-Request-Id` if it persists. Not charged |
| 503 | `SERVICE_OVERLOADED` | Global circuit breaker | Honor `Retry-After: 60`. Rare |
| 500 | `INTERNAL_ERROR` | Our bug | Report with `X-Request-Id` |

The default request timeout is 120s (the API's own ceiling); override it with `AmazonScraperAPI(api_key=..., timeout=...)`.

**Flat-credit promise:** non-2xx responses are free. A basic request costs 5 credits (billing unit; end-customer price is $0.90 per 1,000 basic requests PAYG). Future JS-rendered calls will cost 15 credits. Every response has `X-Request-Id` for traceability — quote it in any support ticket.

## Get an API key

[app.amazonscraperapi.com](https://app.amazonscraperapi.com). **1,000 free requests on signup, no credit card required.**

## Links

- **Website:** https://www.amazonscraperapi.com/
- **Docs:** https://amazonscraperapi.com/docs
- **Pricing:** https://amazonscraperapi.com/pricing
- **Node SDK:** [amazon-scraper-api-sdk](https://www.npmjs.com/package/amazon-scraper-api-sdk) · **Go SDK:** [github.com/ChocoData-com/amazon-scraper-api-sdk-go](https://github.com/ChocoData-com/amazon-scraper-api-sdk-go) · **CLI:** [amazon-scraper-api-cli](https://www.npmjs.com/package/amazon-scraper-api-cli) · **MCP server:** [amazon-scraper-api-mcp](https://www.npmjs.com/package/amazon-scraper-api-mcp)

## License

MIT
