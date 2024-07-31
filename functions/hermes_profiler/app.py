from io import BytesIO
import os
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
from fake_useragent import UserAgent

from typing import Union

dynamodb = boto3.resource('dynamodb')
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

def lambda_handler(event, context):
    table_name = os.environ['DYNAMODB_TABLE']
    s3_bucket_name = os.environ['S3_BUCKET_NAME']
    table = dynamodb.Table(table_name)
    ua = UserAgent()
    user_agent = ua.random

    service = Service(executable_path=r'/opt/chromedriver')
    chrome_options = webdriver.ChromeOptions()
    chrome_options.binary_location = "/opt/chrome/chrome"
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-tools")
    chrome_options.add_argument("--no-zygote")
    chrome_options.add_argument("--single-process")
    chrome_options.add_argument("window-size=2560x1440")
    chrome_options.add_argument("--user-data-dir=/tmp/chrome-user-data")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument(f'--user-agent={user_agent}')
    chrome_options.add_argument("start-maximized")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    chrome = webdriver.Chrome(service=service, options=chrome_options)

    api_gateway_urls = [
        'https://' + os.environ['API_GATEWAY_REGION1'] + '.execute-api.' + os.environ['AWS_REGION'] + '.amazonaws.com/prod/',
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

            # Set the signed headers using execute_cdp_cmd
            chrome.execute_cdp_cmd("Network.enable", {})
            chrome.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": signed_headers})

            chrome.get(url)
            captcha_iframe_selector = "iframe[name^='a-'][src^='https://www.google.com/recaptcha/api2/anchor?']"
            if wait_for_frame(chrome, 10, captcha_iframe_selector):
                # CAPTCHA iframe found, solve the CAPTCHA
                WebDriverWait(chrome, 10).until(EC.element_to_be_clickable((By.XPATH, "//span[@id='recaptcha-anchor']"))).click()
                chrome.switch_to.default_content()  # Switch back to the main content
            else:
                print("CAPTCHA iframe not found on the page.")

            page_source = chrome.page_source
            # print(f"Page source: {page_source}")

            if "Blocked" not in page_source:
                soup = BeautifulSoup(page_source, 'html.parser')
                items.extend(extract_item_info(soup))
            else:
                print(f"Error fetching response from {url}: Request unsuccessful")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching response from {url}: {e}")
    
    unique_items = {item['item_id']: item for item in items}.values()
    if(len(unique_items) == 0):
        print("No items found")
        return {
            'statusCode': 200,
            'body': 'No items found'
        }
    
    # Get previous inventory status
    # response = table.query(
    #     IndexName='TimestampIndex2',
    #     KeyConditionExpression=Key('timestamp').gt(0),
    #     ScanIndexForward=False,
    #     Limit=1
    # )
    # previous_timestamp: Union[int, float] = response['Items'][0]['timestamp'] if response['Items'] else 0
    response = table.get_item(Key={'uuid': 'maxtimestamp'})
    max_timestamp = response.get('Item', {}).get('timestamp', 0)
    print(f"Previous timestamp: {max_timestamp}")
    
    new_items = []
    for item in unique_items:
        uuid = f"{item['item_id']}{timestamp}"
        item_id: str = item['item_id']
        title = item['title']
        color = item['color']
        url = item['url']
        price = item['price']
        unavailable = item['unavailable']
        image_url = item['image_url']

        if not unavailable:
            response = table.get_item(
                Key={
                    'uuid': f"{item['item_id']}{max_timestamp}"
                }
            )
            existing_item = response.get('Item')

            if not existing_item:
                new_items.append(item)

            # Download and upload image to S3
            if image_url:
                object_key = f"{item_id}/{timestamp}.jpg"
                s3_url = download_and_upload_to_s3(image_url, s3_bucket_name, object_key)
            else:
                s3_url = None

            table.put_item(Item={
                'uuid': uuid,
                'item_id': item_id,
                'timestamp': timestamp,
                'title': title,
                'color': color,
                'url': url,
                'price': price,
                's3_image_url': s3_url
            })
            print(f"Added item {item_id} to DynamoDB with S3 image URL: {s3_url}")

    table.put_item(Item={
            'uuid': 'maxtimestamp',
            'timestamp': timestamp
        })
    if new_items:
        new_items_message = "\n\n".join([f"{item['title']} - {item['color']} - {item['price']}\nhttps://hermes.com{item['url']}" for item in new_items])
        try:
            response = sns.publish(
                TopicArn=os.environ['SNS_TOPIC_ARN'],
                Subject="New Items Added",
                Message=f"The following new items have been added:\n{new_items_message}"
            )
            print(f"SNS publish response: {response}\n\n{new_items_message}")
        except Exception as e:
            print(f"Error publishing to SNS: {str(e)}")

    
    return {
        'statusCode': 200,
        'body': 'Lambda function executed successfully'
    }

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
    response = requests.get(image_url)
    if response.status_code == 200:
        s3.upload_fileobj(
            BytesIO(response.content),
            bucket_name,
            object_key,
            ExtraArgs={'ContentType': response.headers['Content-Type']}
        )
        return f"s3://{bucket_name}/{object_key}"
    else:
        print(f"Failed to download image from {image_url}")
        return None