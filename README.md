# amazonscraperapi-sdk

[![PyPI version](https://img.shields.io/pypi/v/amazonscraperapi-sdk)](https://pypi.org/project/amazonscraperapi-sdk/)
[![PyPI downloads](https://img.shields.io/pypi/dm/amazonscraperapi-sdk)](https://pypi.org/project/amazonscraperapi-sdk/)
[![license](https://img.shields.io/pypi/l/amazonscraperapi-sdk)](./LICENSE)

Official Python SDK for **[Amazon Scraper API](https://www.amazonscraperapi.com/)**. Flat-priced at $0.50 per 1,000 successful requests, no credits system, pay only for 2xx responses. Drop into any Python project to fetch structured Amazon product data, run keyword searches, or queue async batches with webhook callbacks.

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
# "Apple AirPods Pro (2nd Generation)..."
print(product["price"]["current"])
# 199.00
print(product["rating"]["average"], product["rating"]["count"])
# 4.7 58214
```

### Example output (trimmed)

```python
{
    "asin": "B09HN3Q81F",
    "title": "Apple AirPods Pro (2nd Generation)...",
    "brand": "Apple",
    "price": {"current": 199.00, "currency": "USD", "was": 249.00, "savings_pct": 20},
    "rating": {"average": 4.7, "count": 58214, "distribution": {"5": 0.81, "4": 0.12}},
    "availability": "In Stock",
    "buybox": {"seller": "Amazon.com", "ships_from": "Amazon.com", "prime": True},
    "images": ["https://m.media-amazon.com/images/I/...jpg"],
    "bullets": ["Active Noise Cancellation...", "Adaptive Audio..."],
    "variants": [{"asin": "B0BDHB9Y8H", "name": "USB-C", "price": 249.00}],
    "categories": ["Electronics", "Headphones", "Earbud Headphones"],
    "_meta": {"tier": "direct", "duration_ms": 2634, "marketplace": "amazon.com"},
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

for r in results["results"]:
    print(r["position"], r["asin"], r["title"], r["price"].get("current"))
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
| **Country-matched residential IPs** | `amazon.de` auto-routes through German IPs. Pass `country="DE"` to override. |
| **Rotating proxies + anti-fingerprinting** | TLS fingerprints, headers, cookies handled server-side. |
| **Rate-limit retries** | Transparent exponential backoff. |
| **Structured JSON output** | Title, price, rating, reviews, variants, seller, images. Parsed, typed. |
| **Batch/async jobs** | 1,000 ASINs submitted, webhook-delivered on completion. |

**Time saved:** a greenfield Python Amazon scraper built to this spec takes roughly 80 engineer-hours (including anti-bot handling and marketplace variants). This SDK is 10 minutes.

## Error handling

All failures follow a stable shape so you can match on `code`:

```python
from amazonscraperapi import AmazonScraperAPI, AsaError
import time

asa = AmazonScraperAPI(api_key="asa_live_...")

try:
    product = asa.product(query="INVALID_ASIN", domain="com")
except AsaError as e:
    if e.code == "INSUFFICIENT_CREDITS":
        pass  # top up
    elif e.code == "RATE_LIMITED":
        time.sleep(e.retry_after)
    elif e.code in ("target_unreachable", "amazon-robot-or-human"):
        # non-2xx, you were not charged. safe to retry.
        pass
    else:
        raise
```

| HTTP | `code` | When you see it | Recommended action |
|---|---|---|---|
| 400 | `INVALID_PARAMS` | Missing `query`, unsupported `domain`, bad `sort_by` | Fix request; don't retry |
| 401 | `INVALID_API_KEY` | Missing, malformed, revoked | Verify `ASA_API_KEY`; rotate if leaked |
| 402 | `INSUFFICIENT_CREDITS` | Balance empty | Top up; renews each billing cycle |
| 429 | `RATE_LIMITED` | Over 120 req/60s per user | Honor `Retry-After`; retry |
| 429 | `CONCURRENCY_LIMIT` | Over plan's parallel cap | Reduce parallelism or upgrade. `X-Concurrency-*` headers guide backoff |
| 502 | `target_unreachable` | Amazon down / all proxy tiers blocked | Retry after 30s (already retried through 3 tiers on our side) |
| 502 | `amazon-robot-or-human` | Amazon challenge not resolvable | Retry. Often transient. Not charged |
| 502 | `extraction_failed` | Layout we can't parse | Report with `X-Request-Id`. Not charged |
| 503 | `SERVICE_OVERLOADED` | Global circuit breaker | Honor `Retry-After: 60`. Rare |
| 500 | `INTERNAL_ERROR` | Our bug | Report with `X-Request-Id` |

**Flat-credit promise:** non-2xx responses are free. Every response has `X-Request-Id` for traceability. Quote it in any support ticket.

## Get an API key

[app.amazonscraperapi.com](https://app.amazonscraperapi.com). **1,000 free requests on signup, no credit card required.**

## Links

- **Website:** https://www.amazonscraperapi.com/
- **Docs:** https://amazonscraperapi.com/docs
- **Status:** https://amazonscraperapi.com/status
- **Pricing:** https://amazonscraperapi.com/pricing
- **Node SDK:** [amazon-scraper-api-sdk](https://www.npmjs.com/package/amazon-scraper-api-sdk) · **Go SDK:** [github.com/ChocoData-com/amazon-scraper-api-sdk-go](https://github.com/ChocoData-com/amazon-scraper-api-sdk-go) · **CLI:** [amazon-scraper-api-cli](https://www.npmjs.com/package/amazon-scraper-api-cli) · **MCP server:** [amazon-scraper-api-mcp](https://www.npmjs.com/package/amazon-scraper-api-mcp)

## License

MIT
