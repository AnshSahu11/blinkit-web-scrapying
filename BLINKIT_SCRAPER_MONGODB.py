import cloudscraper
from scrapy import Selector
import time
import re
from datetime import datetime
import hashlib
import os
import pymongo
from threading import Thread
import sys


class BlinkitScraper:
    def __init__(self):
        """Initialize the Blinkit Scraper with MongoDB"""

        # MongoDB Configuration
        self.con = pymongo.MongoClient('mongodb+srv://sahuansh286_db_user:oGqXeEDysKXz0pT6@cluster0.xhipcwh.mongodb.net/')  # Update with your MongoDB credentials
        self.mydb = self.con['blinkit_scraper_db']
        self.input_table = self.mydb['Input_Blinkit_URLs']

        # Create output table with date
        self.table_date = datetime.now().strftime('%Y_%m_%d')
        self.product_table = self.mydb[f'op_blinkit_data_{self.table_date}']

        # Current date formats
        self.now = datetime.now().strftime("%Y-%m-%d")
        self.now1 = datetime.now().strftime("%Y_%m_%d")
        self.now2 = datetime.now().strftime("%Y-%m-%d")

        # Initialize CloudScraper for Cloudflare bypass
        self.scraper = cloudscraper.create_scraper()

        # Create HTML saves directory
        self.html_dir = f"html_saves/Blinkit/{self.now}/"
        try:
            if not os.path.exists(self.html_dir):
                os.makedirs(self.html_dir)
        except Exception as e:
            print('Exception in makedir config file error: ', e)

        print(f" Blinkit Scraper Initialized")
        print(f" Database: {self.mydb.name}")
        print(f" Output Table: op_blinkit_data_{self.table_date}")

    def fetch_page(self, url, retries=3):
        """Fetch page using CloudScraper with retries"""
        for attempt in range(retries):
            try:
                print(f"🔄 Fetching (attempt {attempt + 1}): {url}")

                if attempt > 0:
                    time.sleep(2 ** attempt)  # Exponential backoff

                response = self.scraper.get(url, timeout=30)

                if response.status_code == 200:
                    return response.text, True
                elif response.status_code == 404:
                    return None, False

            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(exc_type, fname, exc_tb.tb_lineno)
                print(f" Request error: {e}")

        return None, False

    def process_product(self, a, b):
        """Process products with pagination (for threading)"""
        print(f"Thread started: Skip {a}, Limit {b}")

        try:
            # Find products with Status=None
            data = self.input_table.find({f"Status_{self.now2}": None}).skip(int(a)).limit(int(b))

            for j in data:
                row_id = j['_id']
                pro_url = j.get('product_link', j.get('Product Link', ''))

                if not pro_url:
                    print(f"No URL found for ID: {row_id}")
                    continue

                # Extract product ID from URL
                try:
                    if 'prid/' in pro_url:
                        pro_id = pro_url.split('prid/')[-1].split('?')[0]
                    else:
                        pro_id = pro_url.split('/')[-1]

                    if '?' in pro_id:
                        pro_id = pro_id.split('?')[0]
                    if '#' in pro_id:
                        pro_id = pro_id.split('#')[0]

                except Exception as e:
                    print(f"Error in ItemID extraction {pro_url}\n ----> ", e)
                    pro_id = ''

                # Generate HTML filename
                hash_utf8 = pro_url.encode('utf8')
                hash_id = str(int(hashlib.md5(hash_utf8).hexdigest(), 32) % (10 ** 32))
                filename = f'{hash_id}.html'
                path = os.path.join(self.html_dir, filename)

                # Check if HTML exists or fetch new
                if os.path.exists(path):
                    res_data = open(path, encoding='UTF-8').read()
                else:
                    res_data, success = self.fetch_page(pro_url)

                    if not success or not res_data:
                        print(f"Failed to fetch: {pro_url}")
                        self.input_table.update_one({'_id': row_id},
                                                    {"$set": {f'Status_{self.now2}': 'Failed_Fetch'}})
                        continue

                    # Save HTML
                    try:
                        with open(path, 'w', encoding='utf-8') as f:
                            f.write(res_data)
                    except Exception as e:
                        print(f"Error saving HTML: {e}")

                # Parse and extract data
                self.extract_and_save_data(row_id, pro_url, pro_id, res_data, path)

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            print(f"Error in process_product: {e}")

    def extract_and_save_data(self, row_id, pro_url, pro_id, html_content, html_path):
        """Extract data and save to MongoDB"""
        try:
            selector = Selector(text=html_content)

            # Extract Product Name
            pro_name = ''
            try:
                pro_name = selector.xpath(
                    '//div[contains(@class, "tw-text-600") and contains(@class, "tw-font-extrabold")]/text()').get()
                if not pro_name:
                    pro_name = selector.xpath('//h1//text()[normalize-space() and string-length(.) > 5]').get()
                    if not pro_name:
                        pro_name = selector.xpath('//h2[contains(@class, "product")]//text()').get()
                        if not pro_name:
                            pro_name = selector.xpath('//title/text()').get()
                            if pro_name and 'Blinkit' in pro_name:
                                pro_name = pro_name.split('-')[0].strip()

                if pro_name:
                    pro_name = pro_name.strip()
                else:
                    pro_name = ''

            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(exc_type, fname, exc_tb.tb_lineno)
                print(f"Error in product name extraction: {e}")
                pro_name = ''

            # If no product name found, mark as invalid
            if not pro_name:
                print(f"No product name found: {pro_url}")
                self.input_table.update_one({'_id': row_id},
                                            {"$set": {f'Status_{self.now2}': 'No_Name'}})
                os.remove(html_path)
                return

            # Extract Brand
            brand = ''
            try:
                brand = selector.xpath(
                    "//div[contains(@class, 'tw-text-200') and contains(@class, 'tw-font-semibold')]/text()").get()
                if not brand:
                    brand = selector.xpath("//*[contains(@class, 'brand')]//text()").get()
                    if not brand:
                        brand = selector.xpath("//*[contains(text(), 'Brand:')]//following-sibling::*/text()").get()
                        if not brand:
                            brand = ''

                if brand:
                    brand = brand.strip()

            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(exc_type, fname, exc_tb.tb_lineno)
                print(f"Error in brand extraction: {e}")
                brand = ''

            # Extract Prices
            selling_price = ''
            currency = 'INR'
            try:
                price_elements = selector.xpath(
                    "//div[contains(@class,'tw-text-400') and contains(@class,'tw-font-bold')]/text()").getall()
                if not price_elements:
                    price_elements = selector.xpath("//*[contains(text(), '₹')]//text()").getall()

                # Process prices
                numeric_prices = []
                for price in price_elements:
                    if '₹' in price:
                        numbers = re.findall(r'[\d,]+\.?\d*', price.replace('₹', '').replace(',', ''))
                        if numbers:
                            try:
                                numeric_prices.append(float(numbers[0]))
                            except ValueError:
                                continue

                if numeric_prices:
                    selling_price = numeric_prices[0]


            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(exc_type, fname, exc_tb.tb_lineno)
                print(f"Error in price extraction: {e}")
                selling_price = ''


            # Extract Category
            category = ''
            try:
                category_links = selector.xpath(
                    "//a[contains(@class, 'ProductInfoCard__BreadcrumbLink')]/text()").getall()
                if not category_links:
                    category_links = selector.xpath("//a[contains(@class,'ProductInfoCard__BreadcrumbLink') and text()='Flakes & Kids Cereals']").getall()

                if category_links:
                    filtered_cats = [c.strip() for c in category_links if c.strip() and c.strip().lower() != 'home']
                    if filtered_cats:
                        # category = " > ".join(filtered_cats)
                        category = filtered_cats[0]


            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(exc_type, fname, exc_tb.tb_lineno)
                print(f"Error in category extraction: {e}")
                category = ''

            # Extract Weight/Size
            weight_size = ''
            try:
                weight_size = selector.xpath(
                    "//div[contains(@class, 'tw-text-300') and contains(@class, 'tw-font-semibold') and not(contains(text(),'Select Unit'))]/text()").get()
                if not weight_size:
                    weight_elements = selector.xpath(
                        "//div[contains(@class, 'tw-text-300') and contains(@class, 'tw-font-semibold')]/text()").get()
                    if not weight_size:
                        weight_elements = selector.xpath(
                            "(//div[@class='tw-text-200 tw-font-medium tw-text-center' and text()='750 ml']").get()
                        if weight_elements:
                            for elem in weight_elements:
                                weight_pattern = r'\d+\s*(kg|gm?|ml|ltr?|litre|gram)'
                                if re.search(weight_pattern, elem, re.IGNORECASE):
                                    weight_size = elem.strip()
                                    break

                if weight_size:
                    weight_size = weight_size.strip()

            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(exc_type, fname, exc_tb.tb_lineno)
                print(f"Error in weight extraction: {e}")
                weight_size = ''

            # Extract Images
            primary_image = ''
            secondary_images = ''
            try:
                image_urls = selector.xpath("//img[contains(@src, '/cms-assets/cms/product/') and contains(@class, 'tw-h-full') and contains(@class, 'tw-w-full')]/@src").getall()
                if not image_urls:
                    image_urls = selector.xpath("///img[contains(@class, 'tw-h-full') and contains(@class, 'tw-w-full')]/@src").getall()
                    if not image_urls:
                        images = selector.xpath("//img[contains(@src, '/cms-assets/cms/product/') or contains(@data-src, '/cms-assets/cms/product/') or contains(@srcset, '/cms-assets/cms/product/')]")

                        image_urls = []
                        for img in images:
                            img_url = img.xpath("@src").get()
                            if not img_url:
                                img_url = img.xpath("@data-src").get()
                            if not img_url:
                                img_url = img.xpath("@srcset").get()
                            if img_url and img_url not in image_urls:
                                image_urls.append(img_url)

                # Filter valid images
                valid_images = image_urls
                # for img in image_urls:
                #     if img and (img.startswith('http') or img.startswith('/')):
                #         # if img.startswith('/'):
                #         #     img = 'https://blinkit.com' + img
                #         # if img not in valid_images:
                #              valid_images.append(img)

                if valid_images:
                    primary_image = valid_images[0]
                    if len(valid_images) > 1:
                        secondary_images = valid_images[1:]

            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(exc_type, fname, exc_tb.tb_lineno)
                print(f"Error in image extraction: {e}")
                primary_image = ''
                secondary_images = ''

            # Determine stock status
            stock = 'In stock' if selling_price else 'Out of Stock'

            # Save to MongoDB
            self.product_table.update_one(
                {'Product URL': pro_url},
                {"$set": {
                    'htmlpath': html_path,
                    'Product ID': pro_id,
                    'Title': pro_name,
                    'Brand': brand,
                    'Selling Price': selling_price,
                    'Currency': currency,
                    'Category': category,
                    'Weight/Size': weight_size,
                    'Availability': stock,
                    'Product URL': pro_url,
                    'Primary Image': primary_image,
                    'Secondary Images': secondary_images,
                    'When Crawled (Date)': datetime.now().strftime('%Y-%m-%d'),
                    'When Crawled (Time)': datetime.now().strftime('%H:%M:%S'),
                }},
                upsert=True
            )

            # Update status
            self.input_table.update_one({'_id': row_id},
                                        {"$set": {f"Status_{self.now2}": "Done"}})

            print(f" Extracted: {pro_name[:50]}...")

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            print(f"Error in extract_and_save_data: {e}")
            self.input_table.update_one({'_id': row_id},
                                        {"$set": {f'Status_{self.now2}': 'Extract_Error'}})

    def run_scraper(self, num_threads=4):
        """Main scraper function with multithreading"""
        print("\n STARTING ENHANCED SCRAPER WITH MULTITHREADING")
        print("=" * 50)

        run_count = 0
        max_runs = 5

        while self.input_table.count_documents({f"Status_{self.now2}": None}) != 0 and run_count < max_runs:

            total_count = self.input_table.count_documents({f"Status_{self.now2}": None})
            print(f"\n Pending URLs: {total_count}")

            if total_count == 0:
                break

            # Calculate distribution for threads
            variable_count = total_count // num_threads
            if variable_count == 0:
                variable_count = total_count

            # Create and start threads
            threads = []
            for i in range(0, total_count, variable_count):
                thread = Thread(target=self.process_product, args=(i, variable_count))
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            run_count += 1

            # Summary after each run
            done_count = self.input_table.count_documents({f"Status_{self.now2}": "Done"})
            failed_count = self.input_table.count_documents({f"Status_{self.now2}": {"$ne": None, "$ne": "Done"}})

            print(f"\n Run {run_count} Summary:")
            print(f"    Done: {done_count}")
            print(f"    Failed: {failed_count}")
            print(f"    Pending: {self.input_table.count_documents({f'Status_{self.now2}': None})}")

            if run_count < max_runs:
                time.sleep(10)


def main():
    """Main function"""
    scraper = BlinkitScraper()

    # You can adjust the number of threads based on your system
    scraper.run_scraper(num_threads=4)

    print("\n SCRAPING COMPLETED")


if __name__ == "__main__":
    main()
