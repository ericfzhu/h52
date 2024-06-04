import boto3
import csv
import io
import os
import requests
import pandas as pd
from collections import deque

dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

def lambda_handler(event, context):
    table_name = os.environ['DYNAMODB_TABLE_NAME']
    bucket_name = os.environ['S3_BUCKET_NAME']
    webhook = os.environ['WEBHOOK_URL']

    table = dynamodb.Table(table_name)
    csv_file_key = 'hermes_export.csv'
    
    # Scan the table to retrieve all items
    response = table.scan()
    items = response['Items']
    
    # Fetch additional items if there are more pages
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response['Items'])

    # Sort the items based on the 'timestamp' attribute
    items.sort(key=lambda x: x['timestamp'])
    
    # Create a dictionary to store the latest occurrence of each item_id
    latest_items = {}

    timestamp_queue = deque([items[0]['timestamp']])
    
    # Iterate over the sorted items and mark new items for each timestamp
    for item in items:
        if item['uuid'] == 'maxtimestamp':
            continue
        
        item_id = item['item_id']
        timestamp = item['timestamp']
        
        if timestamp not in latest_items:
            latest_items[timestamp] = set()
        
        if timestamp_queue[0] != timestamp and timestamp not in timestamp_queue:
            timestamp_queue.append(timestamp)
            if len(timestamp_queue) > 2:
                timestamp_queue.popleft()
        
        prev_max_timestamp = timestamp_queue[0]
        
        if item_id not in latest_items[prev_max_timestamp]:
            item['is_new'] = '1'
            latest_items[timestamp].add(item_id)
        else:
            item['is_new'] = '0'

    csv_buffer = io.StringIO()
    fieldnames = ['uuid', 'item_id', 'timestamp', 'title', 'color', 'url', 'price', 'is_new']
    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)

    writer.writeheader()
    writer.writerows(items)

    s3.put_object(Body=csv_buffer.getvalue(), Bucket=bucket_name, Key=csv_file_key)
    print(f'Exported {len(items)} items to S3 bucket {bucket_name}/{csv_file_key}')

    response = requests.post(webhook)
    print(f'Initiated build with status code {response.status_code}')

    return {
        'statusCode': 200,
        'body': f'Exported {len(items)} items to S3 bucket {bucket_name}/{csv_file_key}'
    }