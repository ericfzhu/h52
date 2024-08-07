import csv
from io import BytesIO, StringIO
import os
import time
import boto3
import requests
from bs4 import BeautifulSoup
from boto3.dynamodb.conditions import Key
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver import ActionChains
from fake_useragent import UserAgent
from botocore.exceptions import ClientError
import undetected_chromedriver as uc

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from typing import Union

sns = boto3.client('sns')
s3 = boto3.client('s3')

def wait_for_frame(driver, timeout, selector):
    try:
        frame = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        driver.switch_to.frame(frame)
        return True
    except (TimeoutException, NoSuchElementException):
        return False

def main():
    s3_bucket_name = os.environ['S3_BUCKET_NAME']
    sns_topic_arn = os.environ['SNS_TOPIC_ARN']
    ua = UserAgent()
    user_agent = ua.random

    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=2560,1440")
    options.add_argument(f'user-agent={user_agent}')

    driver = uc.Chrome(options=options, use_subprocess=True)

    api_gateway_urls = [
        # 'https://' + os.environ['API_GATEWAY_REGION1'] + '.execute-api.' + os.environ['AWS_REGION'] + '.amazonaws.com/prod/',
        os.environ['API_GATEWAY_URL'],
        # os.environ['SECOND_API_GATEWAY_URL']
        'https://fu5te2nc0l.execute-api.ap-southeast-2.amazonaws.com/prod/'
    ]
    
    timestamp = int(datetime.now().timestamp())
    items = []

    for url in api_gateway_urls:
        try:
            print(f"Fetching response from {url}")

            # Sign request with SigV4
            region = url.split('.')[2]
            request = AWSRequest(method='GET', url=url, headers={'Content-Type': 'application/json'})
            credentials = boto3.Session().get_credentials()
            SigV4Auth(credentials, 'execute-api', region).add_auth(request)
            signed_headers = dict(request.headers.items())

            # Set the signed headers
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": signed_headers})

            driver.get(url)

            screenshot = driver.get_screenshot_as_png()
            screenshot_key = f"screenshots/{timestamp}.png"
            try:
                s3.upload_fileobj(
                    BytesIO(screenshot),
                    s3_bucket_name,
                    screenshot_key,
                    ExtraArgs={'ContentType': 'image/png'}
                )
                print(f"Successfully uploaded screenshot to s3://{s3_bucket_name}/{screenshot_key}")
            except Exception as e:
                print(f"Failed to upload screenshot: {e}")
            
            # Check for CAPTCHA
            if check_and_solve_captcha(driver):
                print("CAPTCHA solved successfully")
            else:
                print("No CAPTCHA detected or unable to solve")

            page_source = driver.page_source
            print(f"Page source length: {len(page_source)}")

            if "Blocked" not in page_source:
                soup = BeautifulSoup(page_source, 'html.parser')
                items.extend(extract_item_info(soup))
            else:
                print(f"Error fetching response from {url}: Request unsuccessful")
        except Exception as e:
            print(f"Error fetching response from {url}: {e}")
    
    driver.quit()

    unique_items = {item['item_id']: item for item in items}.values()
    if len(unique_items) == 0:
        print("No items found")
        return

    csv_file_name = 'hermes_inventory.csv'
    csv_content = get_csv_from_s3(s3_bucket_name, csv_file_name)
    last_run_timestamp = get_last_run_timestamp(csv_content)
    print(f"Last run timestamp: {last_run_timestamp}")

    new_items = []
    csv_rows = []

    if csv_content:
        reader = csv.DictReader(StringIO(csv_content))
        csv_rows = list(reader)

    last_run_items = {row['item_id'] for row in csv_rows if int(row['timestamp']) == last_run_timestamp}

    for item in unique_items:
        item_id = item['item_id']
        title = item['title']
        color = item['color']
        url = item['url']
        price = item['price']
        unavailable = item['unavailable']
        image_url = item.get('image_url')

        if not unavailable and item_id not in last_run_items:
            new_items.append(item)

        # Download and upload image to S3
        if image_url:
            object_key = f"{item_id}.jpg"
            s3_url = download_and_upload_to_s3(image_url, s3_bucket_name, object_key)
        else:
            s3_url = None

        csv_rows.append({
            'uuid': f"{item_id}{timestamp}",
            'item_id': item_id,
            'timestamp': str(timestamp),
            'title': title,
            'color': color,
            'url': url,
            'price': price,
            's3_image_url': s3_url,
            'available': str(not unavailable)
        })
        print(f"Added item {item_id} to CSV with S3 image URL: {s3_url}, Available: {not unavailable}")

    # Write updated CSV to S3
    output = StringIO()
    fieldnames = ['uuid', 'item_id', 'timestamp', 'title', 'color', 'url', 'price', 's3_image_url', 'available']
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(csv_rows)

    put_csv_to_s3(s3_bucket_name, csv_file_name, output.getvalue())

    if new_items:
        new_items_message = "\n\n".join([f"{item['title']} - {item['color']} - {item['price']}\nhttps://hermes.com{item['url']}" for item in new_items])
        try:
            response = sns.publish(
                TopicArn=sns_topic_arn,
                Subject="New Items Added",
                Message=f"The following new items have been added:\n{new_items_message}"
            )
            print(f"SNS publish response: {response}\n\n{new_items_message}")
        except Exception as e:
            print(f"Error publishing to SNS: {str(e)}")

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

def download_and_upload_to_s3(image_url, bucket_name, object_key):
    # First, check if the object already exists
    try:
        s3.head_object(Bucket=bucket_name, Key=object_key)
        print(f"Object {object_key} already exists in bucket {bucket_name}. Skipping upload.")
        return f"s3://{bucket_name}/{object_key}"
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            # The object does not exist, proceed with download and upload
            response = requests.get(image_url)
            if response.status_code == 200:
                s3.upload_fileobj(
                    BytesIO(response.content),
                    bucket_name,
                    object_key,
                    ExtraArgs={'ContentType': response.headers['Content-Type']}
                )
                print(f"Successfully uploaded {object_key} to bucket {bucket_name}")
                return f"s3://{bucket_name}/{object_key}"
            else:
                print(f"Failed to download image from {image_url}")
                return None
        else:
            # Something else went wrong
            print(f"Error checking object existence: {e}")
            return None
        

def wait_for_frame(driver, timeout, selector):
    try:
        WebDriverWait(driver, timeout).until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, selector)))
        return True
    except TimeoutException:
        return False

def solve_captcha(chrome):
    try:
        # Wait for the CAPTCHA iframe to be present
        captcha_iframe_selector = "iframe[src^='https://geo.captcha-delivery.com/captcha/']"
        WebDriverWait(chrome, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, captcha_iframe_selector)))
        
        # Switch to the CAPTCHA iframe
        captcha_iframe = chrome.find_element(By.CSS_SELECTOR, captcha_iframe_selector)
        chrome.switch_to.frame(captcha_iframe)
        
        # Wait for the CAPTCHA to be interactive
        WebDriverWait(chrome, 20).until(EC.presence_of_element_located((By.ID, "captcha-container")))
        
        # Check for different types of CAPTCHAs
        if chrome.find_elements(By.CLASS_NAME, "geetest_canvas_slice"):
            print("Detected slider CAPTCHA")
            # Implement slider CAPTCHA solving logic here
        elif chrome.find_elements(By.CLASS_NAME, "geetest_item_wrap"):
            print("Detected image selection CAPTCHA")
            # Implement image selection CAPTCHA solving logic here
        else:
            print("Unknown CAPTCHA type, looking for submit button")
            submit_button = WebDriverWait(chrome, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
            )
            submit_button.click()

        
        diagnose_captcha(chrome)
        
        # Wait for CAPTCHA verification
        time.sleep(5)
        
        # Check if CAPTCHA was solved successfully
        if "https://www.hermes.com" in chrome.current_url:
            print("CAPTCHA solved successfully")
            return True
        else:
            print("CAPTCHA solution unsuccessful")
            return False
        
    except Exception as e:
        print(f"Error solving CAPTCHA: {str(e)}")
        return False
    finally:
        # Switch back to the default content
        chrome.switch_to.default_content()


def get_csv_from_s3(bucket_name, file_name):
    try:
        response = s3.get_object(Bucket=bucket_name, Key=file_name)
        return response['Body'].read().decode('utf-8')
    except s3.exceptions.NoSuchKey:
        return None

def put_csv_to_s3(bucket_name, file_name, csv_content):
    s3.put_object(Bucket=bucket_name, Key=file_name, Body=csv_content.encode('utf-8'))

def get_last_run_timestamp(csv_content):
    if not csv_content:
        return 0
    reader = csv.DictReader(StringIO(csv_content))
    timestamps = [int(row['timestamp']) for row in reader if row['timestamp'].isdigit()]
    return max(timestamps) if timestamps else 0

def diagnose_captcha(chrome):
    try:
        logger.info("Starting CAPTCHA diagnosis")
        
        # Check for Datadome script
        datadome_script = chrome.find_elements(By.XPATH, "//script[contains(@src, 'datadome')]")
        if datadome_script:
            logger.info("Datadome script detected")
        
        # Look for the CAPTCHA iframe
        captcha_iframe = chrome.find_elements(By.CSS_SELECTOR, "iframe[src*='captcha-delivery']")
        if captcha_iframe:
            logger.info(f"CAPTCHA iframe found: {captcha_iframe[0].get_attribute('src')}")
            
            # Switch to the iframe and inspect its contents
            chrome.switch_to.frame(captcha_iframe[0])
            
            # Look for specific elements within the CAPTCHA
            captcha_elements = {
                "container": chrome.find_elements(By.ID, "captcha-container"),
                "slider": chrome.find_elements(By.CLASS_NAME, "geetest_slider_button"),
                "image_select": chrome.find_elements(By.CLASS_NAME, "geetest_item_wrap"),
                "submit_button": chrome.find_elements(By.CSS_SELECTOR, "button[type='submit']")
            }
            
            for element_name, elements in captcha_elements.items():
                if elements:
                    logger.info(f"Found {element_name} in CAPTCHA iframe")
                else:
                    logger.info(f"{element_name} not found in CAPTCHA iframe")
            
            chrome.switch_to.default_content()
        else:
            logger.info("CAPTCHA iframe not found")
        
        # Check for any error messages on the page
        error_messages = chrome.find_elements(By.XPATH, "//*[contains(text(), 'error') or contains(text(), 'Error')]")
        for error in error_messages:
            logger.info(f"Possible error message found: {error.text}")
        
        # Log the current URL
        logger.info(f"Current URL: {chrome.current_url}")
        
        # Log the page source (be cautious with sensitive information)
        # logger.debug(f"Page source: {chrome.page_source}")
        
    except Exception as e:
        logger.error(f"Error during CAPTCHA diagnosis: {str(e)}")

def check_and_solve_captcha(driver):
    try:
        # Check for Datadome CAPTCHA
        datadome_frame = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='captcha-delivery']"))
        )
        driver.switch_to.frame(datadome_frame)
        
        # Implement Datadome CAPTCHA solving logic here
        # This is a placeholder and needs to be implemented based on the specific CAPTCHA type
        print("Attempting to solve Datadome CAPTCHA")
        time.sleep(5)  # Wait for CAPTCHA to load fully
        # Add your CAPTCHA solving logic here
        
        driver.switch_to.default_content()
        return True
    except:
        try:
            # Check for reCAPTCHA
            recaptcha_frame = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[name^='a-'][src^='https://www.google.com/recaptcha/api2/anchor?']"))
            )
            driver.switch_to.frame(recaptcha_frame)
            
            # Click on reCAPTCHA checkbox
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//span[@id='recaptcha-anchor']"))).click()
            
            driver.switch_to.default_content()
            return True
        except:
            return False
        


if __name__ == "__main__":
    main()