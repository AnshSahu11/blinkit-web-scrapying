Blinkit ScraperA multithreaded Blinkit product scraper built with Python, CloudScraper, and Scrapy’s Selector.
The scraper bypasses Cloudflare, fetches product pages, extracts structured data (title, brand, price, category, size, images, etc.), and stores results in MongoDB.

🚀 Features

✅ Cloudflare bypass using CloudScraper

✅ Extracts product details:

Product ID

Title & Brand

Selling Price & Currency

Category & Weight/Size

Stock availability

Primary & Secondary images

✅ Saves raw HTML snapshots for each product

✅ Stores clean data into MongoDB with timestamps

✅ Supports multithreading for faster scraping

✅ Handles retries & exponential backoff on request failures
