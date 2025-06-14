from flask import Flask, request, jsonify
from flask_cors import CORS
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, GeolocationConfig
import asyncio
import pandas as pd
from typing import List, Dict, Any
import uuid
import logging

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes to allow frontend access from anywhere

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Helper function to validate URL
def is_valid_url(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ["http", "https"]
    except Exception:
        return False

# Helper function to process crawl result
def format_crawl_result(result: Any) -> Dict:
    return {
        "success": result.success,
        "url": result.url,
        "markdown": result.markdown,
        "extracted_content": result.extracted_content,
        "tables": [
            {
                "headers": table.get("headers", []),
                "rows": table.get("rows", []),
            }
            for table in result.media.get("tables", [])
        ] if result.media else [],
        "error": result.error if not result.success else None
    }

@app.route('/api/health', methods=['GET'])
def health_check():
    """Check if the server is running."""
    return jsonify({"status": "healthy", "message": "Server is up and running"}), 200

@app.route('/api/crawl/single', methods=['POST'])
async def crawl_single():
    """Crawl a single URL with optional configurations."""
    try:
        data = request.get_json()
        if not data or not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON payload"}), 400

        url = data.get("url")
        if not url or not is_valid_url(url):
            return jsonify({"error": "Valid URL is required"}), 400

        # Extract optional configurations
        config = data.get("config", {})
        crawl_config = CrawlerRunConfig(
            locale=config.get("locale", "en-US"),
            timezone_id=config.get("timezone_id", "America/Los_Angeles"),
            geolocation=GeolocationConfig(
                latitude=config.get("geolocation", {}).get("latitude", 34.0522),
                longitude=config.get("geolocation", {}).get("longitude", -118.2437),
                accuracy=config.get("geolocation", {}).get("accuracy", 10.0)
            ) if config.get("geolocation") else None,
            table_score_threshold=config.get("table_score_threshold", 8),
            capture_network=config.get("capture_network", False),
            capture_console=config.get("capture_console", False),
            mhtml=config.get("mhtml", False),
            max_pages=config.get("max_pages", 1),
            deep_crawl_strategy=config.get("deep_crawl_strategy", "bfs") if config.get("deep_crawl", False) else None
        )

        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url, config=crawl_config)
            return jsonify({
                "task_id": str(uuid.uuid4()),
                "result": format_crawl_result(result)
            }), 200

    except Exception as e:
        logger.error(f"Error in crawl_single: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/api/crawl/multiple', methods=['POST'])
async def crawl_multiple():
    """Crawl multiple URLs with shared or per-URL configurations."""
    try:
        data = request.get_json()
        if not data or not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON payload"}), 400

        urls = data.get("urls")
        if not urls or not isinstance(urls, list) or not all(is_valid_url(url) for url in urls):
            return jsonify({"error": "Valid URLs array is required"}), 400

        # Extract shared configuration or per-URL configs
        configs = data.get("configs", {})
        if isinstance(configs, list) and len(configs) != len(urls):
            return jsonify({"error": "Configs array must match URLs array length"}), 400

        results = []
        async with AsyncWebCrawler() as crawler:
            for i, url in enumerate(urls):
                # Use per-URL config if provided, else shared config
                config = configs[i] if isinstance(configs, list) else configs
                crawl_config = CrawlerRunConfig(
                    locale=config.get("locale", "en-US"),
                    timezone_id=config.get("timezone_id", "America/Los_Angeles"),
                    geolocation=GeolocationConfig(
                        latitude=config.get("geolocation", {}).get("latitude", 34.0522),
                        longitude=config.get("geolocation", {}).get("longitude", -118.2437),
                        accuracy=config.get("geolocation", {}).get("accuracy", 10.0)
                    ) if config.get("geolocation") else None,
                    table_score_threshold=config.get("table_score_threshold", 8),
                    capture_network=config.get("capture_network", False),
                    capture_console=config.get("capture_console", False),
                    mhtml=config.get("mhtml", False),
                    max_pages=config.get("max_pages", 1),
                    deep_crawl_strategy=config.get("deep_crawl_strategy", "bfs") if config.get("deep_crawl", False) else None
                )
                result = await crawler.arun(url=url, config=crawl_config)
                results.append(format_crawl_result(result))

        return jsonify({
            "task_id": str(uuid.uuid4()),
            "results": results
        }), 200

    except Exception as e:
        logger.error(f"Error in crawl_multiple: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
