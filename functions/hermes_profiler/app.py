import os
import boto3
import requests
from bs4 import BeautifulSoup
from boto3.dynamodb.conditions import Key
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

def lambda_handler(event, context):
    # Get the DynamoDB table name from the environment variable
    table_name = os.environ['DYNAMODB_TABLE']
    table = dynamodb.Table(table_name)
    
    # List of API Gateway URLs in different regions
    api_gateway_urls = [
        'https://' + os.environ['API_GATEWAY_REGION1'] + '.execute-api.' + os.environ['AWS_REGION'] + '.amazonaws.com/prod/',
        'https://' + os.environ['API_GATEWAY_REGION2'] + '.execute-api.' + os.environ['AWS_REGION'] + '.amazonaws.com/prod/'
    ]
    
    timestamp = int(datetime.now().timestamp())
    
    items = []
    for url in api_gateway_urls:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_2) AppleWebKit/601.3.9 (KHTML, like Gecko) Version/9.0.2 Safari/601.3.9',
                'Accept-Language': 'en-US,en;q=0.9'
            }
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                items.extend(extract_item_info(soup))
        except requests.exceptions.RequestException as e:
            print(f"Error fetching response from {url}: {e}")
    
    unique_items = {item['item_id']: item for item in items}.values()
    
    # Get the previous greatest timestamp from DynamoDB
    response = table.query(
        KeyConditionExpression=Key('item_id').eq('TIMESTAMP'),
        ScanIndexForward=False,
        Limit=1
    )
    previous_timestamp = response['Items'][0]['timestamp'] if response['Items'] else 0
    
    new_items = []
    for item in unique_items:
        item_id = item['item_id']
        title = item['title']
        color = item['color']
        url = item['url']
        price = item['price']
        unavailable = item['unavailable']
        
        if not unavailable:
            response = table.query(
                KeyConditionExpression=Key('item_id').eq(item_id),
                ScanIndexForward=False,
                Limit=1
            )
            existing_item = response['Items'][0] if response['Items'] else None
            
            if not existing_item or existing_item['timestamp'] < previous_timestamp:
                table.put_item(Item={
                    'item_id': item_id,
                    'timestamp': timestamp,
                    'title': title,
                    'color': color,
                    'url': url,
                    'price': price,
                    'unavailable': unavailable
                })
                new_items.append(item)
    
    if new_items:
        new_items_message = "\n".join([f"- {item['title']}" for item in new_items])
        try:
            response = sns.publish(
                TopicArn=os.environ['SNS_TOPIC_ARN'],
                Subject="New Items Added",
                Message=f"The following new items have been added:\n{new_items_message}"
            )
            print(f"SNS publish response: {response}")
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
        items.append({
            'item_id': item_id,
            'title': title,
            'color': color,
            'url': url,
            'price': price,
            'unavailable': unavailable
        })
    return items