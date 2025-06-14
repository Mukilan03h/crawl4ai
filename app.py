from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from crawl4ai import WebCrawler, CrawlerRunConfig, GeolocationConfig
import uuid
import logging
from typing import List, Dict, Any
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access from anywhere

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Helper function to validate URL
def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ["http", "https"]
    except Exception:
        return False

# Helper function to format crawl result
def format_crawl_result(result: Any) -> Dict:
    return {
        "success": result.success,
        "url": result.url,
        "markdown": result.markdown,
        "extracted_content": result.extracted_content,
        "tables": [
            {
                "headers": table.get("headers", []),
                "rows": table.get("rows", [])
            }
            for table in result.media.get("tables", [])
        ] if result.media else [],
        "error": result.error if not result.success else None
    }

@app.route('/', methods=['GET'])
def home():
    """Return a welcome message for the root route."""
    return jsonify({
        "message": "Welcome to Crawl4AI API!",
        "endpoints": {
            "health": "GET /api/health",
            "crawl_single": "POST /api/crawl/single",
            "crawl_multiple": "POST /api/crawl/multiple"
        },
        "docs": "Visit https://github.com/unclecode/crawl4ai for more info"
    }), 200

@app.route('/favicon.ico', methods=['GET'])
def favicon():
    """Serve a favicon or return 204 to avoid 404 errors."""
    return '', 204

@app.route('/api/health', methods=['GET'])
def health_check():
    """Check if the server is running."""
    return jsonify({"status": "healthy", "message": "Server is up and running"}), 200

@app.route('/api/crawl/single', methods=['POST'])
def crawl_single():
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
        use_browser = config.get("use_browser", False)  # Toggle browser-based crawling
        crawl_config = CrawlerRunConfig(
            locale=config.get("locale", "en-US"),
            timezone_id=config.get("timezone_id", "America/Los_Angeles") if use_browser else None,
            geolocation=GeolocationConfig(
                latitude=config.get("geolocation", {}).get("latitude", 34.0522),
                longitude=config.get("geolocation", {}).get("longitude", -118.2437),
                accuracy=config.get("geolocation", {}).get("accuracy", 10.0)
            ) if use_browser and config.get("geolocation") else None,
            table_score_threshold=config.get("table_score_threshold", 8),
            capture_network=config.get("capture_network", False),
            capture_console=config.get("capture_console", False) if use_browser else None,
            mhtml=config.get("mhtml", False) if use_browser else None,
            max_pages=config.get("max_pages", 1),
            deep_crawl_strategy=config.get("deep_crawl_strategy", "bfs") if config.get("deep_crawl", False) else None,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        logger.info(f"Crawling URL: {url}, Browser: {use_browser}")
        with WebCrawler() as crawler:
            result = crawler.run(url=url, config=crawl_config, bypass_browser=not use_browser)
            return jsonify({
                "task_id": str(uuid.uuid4()),
                "result": format_crawl_result(result)
            }), 200

    except Exception as e:
        logger.error(f"Error in crawl_single: {str(e)}", exc_info=True)
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/api/crawl/multiple', methods=['POST'])
def crawl_multiple():
    """Crawl multiple URLs with shared or per-URL configurations."""
    try:
        data = request.get_json()
        if not data or not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON payload"}), 400

        urls = data.get("urls")
        if not urls or not isinstance(urls, list) or not all(is_valid_url(url) for url in urls):
            return jsonify({"error": "Valid URLs array is required"}), 400

        # Extract shared or per-URL configs
        configs = data.get("configs", {})
        if isinstance(configs, list) and len(configs) != len(urls):
            return jsonify({"error": "Configs array must match URLs array length"}), 400

        results = []
        with WebCrawler() as crawler:
            for i, url in enumerate(urls):
                config = configs[i] if isinstance(configs, list) else configs
                use_browser = config.get("use_browser", False)
                crawl_config = CrawlerRunConfig(
                    locale=config.get("locale", "en-US"),
                    timezone_id=config.get("timezone_id", "America/Los_Angeles") if use_browser else None,
                    geolocation=GeolocationConfig(
                        latitude=config.get("geolocation", {}).get("latitude", 34.0522),
                        longitude=config.get("geolocation", {}).get("longitude", -118.2437),
                        accuracy=config.get("geolocation", {}).get("accuracy", 10.0)
                    ) if use_browser and config.get("geolocation") else None,
                    table_score_threshold=config.get("table_score_threshold", 8),
                    capture_network=config.get("capture_network", False),
                    capture_console=config.get("capture_console", False) if use_browser else None,
                    mhtml=config.get("mhtml", False) if use_browser else None,
                    max_pages=config.get("max_pages", 1),
                    deep_crawl_strategy=config.get("deep_crawl_strategy", "bfs") if config.get("deep_crawl", False) else None,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                logger.info(f"Crawling URL: {url}, Browser: {use_browser}")
                result = crawler.run(url=url, config=crawl_config, bypass_browser=not use_browser)
                results.append(format_crawl_result(result))

        return jsonify({
            "task_id": str(uuid.uuid4()),
            "results": results
        }), 200

    except Exception as e:
        logger.error(f"Error in crawl_multiple: {str(e)}", exc_info=True)
        return jsonify({"error": f"Server error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
