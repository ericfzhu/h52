import os
import sys
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import time
import json
import logging
import csv
from datetime import datetime
import schedule
import signal

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variable to control the script's execution
running = True

def main():
    logger.info("Starting script")
    logger.info(f"Python version: {sys.version}")

    ua = UserAgent()
    user_agent = ua.random

    chrome_options = uc.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f'user-agent={user_agent}')

    try:
        logger.info("Attempting to create Chrome driver")
        driver = uc.Chrome(options=chrome_options)
        logger.info("Successfully created Chrome driver")
    except Exception as e:
        logger.error(f"Error creating Chrome driver: {str(e)}")
        return

    # Replace these with your actual URLs
    urls = [
        'https://www.hermes.com/au/en/category/women/bags-and-small-leather-goods/bags-and-clutches/#|',
    ]
    
    timestamp = int(datetime.now().timestamp())
    items = []

    for url in urls:
        try:
            logger.info(f"Fetching response from {url}")

            driver.get(url)
            
            # Check for CAPTCHA
            if check_and_solve_captcha(driver):
                logger.info("CAPTCHA solved successfully")
            else:
                logger.info("No CAPTCHA detected or unable to solve")

            page_source = driver.page_source
            driver.save_screenshot(f'screenshots/{timestamp}.png')
            logger.info(f"Page source length: {len(page_source)}")

            if "Blocked" not in page_source:
                soup = BeautifulSoup(page_source, 'html.parser')
                items.extend(extract_item_info(soup))
            else:
                logger.error(f"Error fetching response from {url}: Request unsuccessful")
        except Exception as e:
            logger.error(f"Error fetching response from {url}: {str(e)}")
    
    driver.quit()

    unique_items = {item['item_id']: item for item in items}.values()
    if len(unique_items) == 0:
        logger.info("No items found")
        return

    # Process items and store in CSV
    csv_filename = 'hermes_inventory.csv'
    save_items_to_csv(unique_items, timestamp, csv_filename)
    logger.info(f"Data saved to {csv_filename}")

def check_and_solve_captcha(driver):
    try:
        # Check for Datadome CAPTCHA
        datadome_frame = driver.find_element_by_css_selector("iframe[src*='captcha-delivery']")
        driver.switch_to.frame(datadome_frame)
        
        logger.info("Datadome CAPTCHA detected. Manual intervention required.")
        input("Please solve the CAPTCHA manually and press Enter to continue...")
        
        driver.switch_to.default_content()
        return True
    except:
        try:
            # Check for reCAPTCHA
            recaptcha_frame = driver.find_element_by_css_selector("iframe[name^='a-'][src^='https://www.google.com/recaptcha/api2/anchor?']")
            driver.switch_to.frame(recaptcha_frame)
            
            # Click on reCAPTCHA checkbox
            driver.find_element_by_xpath("//span[@id='recaptcha-anchor']").click()
            
            driver.switch_to.default_content()
            return True
        except:
            return False


def extract_item_info(soup):
    items = []
    for div in soup.find_all('div', class_='product-grid-list-item'):
        item_id = div['id'].replace('grid-product-', '')
        title = div.find('span', class_='product-item-name').text.strip()
        color = div.find('span', class_='product-item-colors').text.split(':')[-1].strip()
        url = div.find('a')['href']
        price = int(div.find('span', class_='price').text.replace('AU$', '').replace(',', ''))
        unavailable = 'Unavailable' in div.text
        
        # Extract image URL
        img_tag = div.find('img')
        image_url = img_tag['src'] if img_tag else None
        
        items.append({
            'item_id': item_id,
            'title': title,
            'color': color,
            'url': url,
            'price': price,
            'unavailable': unavailable,
            'image_url': image_url
        })
    return items

def save_items_to_csv(items, timestamp, filename):
    file_exists = os.path.isfile(filename)
    
    with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['item_id', 'timestamp', 'title', 'color', 'url', 'price', 'available']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
        
        for item in items:
            item['timestamp'] = timestamp
            writer.writerow(item)

def run_scraper():
    logger.info("Running scraper")
    main()

def signal_handler(signum, frame):
    global running
    logger.info("Stopping the script...")
    running = False

if __name__ == "__main__":
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Schedule the job
    schedule.every(10).minutes.do(run_scraper)

    # Run the scraper immediately on start
    run_scraper()

    # Keep the script running
    while running:
        schedule.run_pending()
        time.sleep(1)

    logger.info("Script stopped")