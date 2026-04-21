"""
amazonscraperapi - Official Python client for https://amazonscraperapi.com

Usage:
    from amazonscraperapi import AmazonScraperAPI

    client = AmazonScraperAPI(api_key="asa_live_...")
    product = client.product(query="B09HN3Q81F", domain="com")
    print(product["title"])
"""
from .client import AmazonScraperAPI, AmazonScraperAPIError, verify_webhook_signature

__version__ = "0.1.0"
__all__ = ["AmazonScraperAPI", "AmazonScraperAPIError", "verify_webhook_signature"]
