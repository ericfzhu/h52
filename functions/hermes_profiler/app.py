import boto3
import requests
from botocore.exceptions import ClientError
import os

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

    # Fetch responses from both API Gateways
    responses = []
    for url in api_gateway_urls:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                responses.append(response.json())
        except requests.exceptions.RequestException as e:
            print(f"Error fetching response from {url}: {e}")

    # Process each response
    for response in responses:
        item_id = response['item_id']
        title = response['title']
        url = response['url']
        price = response['price']
        color = response['color']

        # Check if the item already exists in DynamoDB
        try:
            item = table.get_item(Key={'item_id': item_id})
            existing_item = item.get('Item')
        except ClientError as e:
            print(f"Error getting item from DynamoDB: {e}")
            existing_item = None

        if existing_item:
            # Compare the existing item with the new response
            if (
                existing_item['title'] != title or
                existing_item['url'] != url or
                existing_item['price'] != price or
                existing_item['color'] != color
            ):
                # Update the item in DynamoDB
                try:
                    table.put_item(Item={
                        'item_id': item_id,
                        'title': title,
                        'url': url,
                        'price': price,
                        'color': color
                    })
                except ClientError as e:
                    print(f"Error updating item in DynamoDB: {e}")

                # Send a notification via SNS if the title contains a specific word
                if 'keyword' in title.lower():
                    try:
                        sns.publish(
                            TopicArn=os.environ['SNS_TOPIC_ARN'],
                            Message=f"Item updated: {title}"
                        )
                    except ClientError as e:
                        print(f"Error sending SNS notification: {e}")
        else:
            # Add the new item to DynamoDB
            try:
                table.put_item(Item={
                    'item_id': item_id,
                    'title': title,
                    'url': url,
                    'price': price,
                    'color': color
                })
            except ClientError as e:
                print(f"Error adding item to DynamoDB: {e}")

            # Send a notification via SNS if the title contains a specific word
            if 'keyword' in title.lower():
                try:
                    sns.publish(
                        TopicArn=os.environ['SNS_TOPIC_ARN'],
                        Message=f"New item added: {title}"
                    )
                except ClientError as e:
                    print(f"Error sending SNS notification: {e}")

    return {
        'statusCode': 200,
        'body': 'Lambda function executed successfully'
    }