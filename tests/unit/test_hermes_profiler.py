import os
import unittest
from unittest.mock import MagicMock, patch
import boto3
from moto import mock_aws
from functions.hermes_profiler.app import lambda_handler, extract_item_info
from bs4 import BeautifulSoup

class TestHermesProfiler(unittest.TestCase):
    def setUp(self):
        self.mock_aws = mock_aws()
        self.mock_aws.start()

        self.dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        self.sns = boto3.client('sns', region_name='us-west-2')
        self.sqs = boto3.client('sqs', region_name='us-west-2')
        self.table_name = 'test-table'
        # self.topic_arn = 'arn:aws:sns:us-west-2:123456789012:test-topic'try:
        try:
            self.table = self.dynamodb.Table(self.table_name)
            self.table.delete()
            self.table.wait_until_not_exists()
        except self.dynamodb.meta.client.exceptions.ResourceNotFoundException:
            pass

        self.table = self.dynamodb.create_table(
            TableName=self.table_name,
            KeySchema=[
                {'AttributeName': 'item_id', 'KeyType': 'HASH'},
                {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'item_id', 'AttributeType': 'S'},
                {'AttributeName': 'timestamp', 'AttributeType': 'N'}
            ],
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        )

        self.topic = self.sns.create_topic(Name='test-topic')
        self.topic_arn = self.topic['TopicArn']
        self.sqs_url = self.sqs.create_queue(QueueName='test')["QueueUrl"]
        self.sqs_arn = self.sqs.get_queue_attributes(QueueUrl=self.sqs_url, AttributeNames=['QueueArn'])["Attributes"]["QueueArn"]
        self.sns.subscribe(TopicArn=self.topic_arn, Protocol='sqs', Endpoint=self.sqs_arn)
        self.sns.subscribe(TopicArn=self.topic_arn, Protocol='sms', Endpoint="+12223334444")


    def tearDown(self):
        self.mock_aws.stop()

    @patch('functions.hermes_profiler.app.requests.get')
    def test_lambda_handler(self, mock_get):
        # Mock the API Gateway responses
        mock_get.side_effect = [
            MagicMock(status_code=200, text='<html><div class="product-grid-list-item" id="grid-product-1"><span class="product-item-name">Item 1</span><span class="product-item-colors">Color: Red</span><a href="/item-1-url">Link</a><span class="price">AU$100</span></div></html>'),
            MagicMock(status_code=200, text='<html><div class="product-grid-list-item" id="grid-product-2"><span class="product-item-name">Item 2</span><span class="product-item-colors">Color: Blue</span><a href="/item-2-url">Link</a><span class="price">AU$200</span></div></html>')
        ]

        # Set the necessary environment variables
        os.environ['DYNAMODB_TABLE'] = self.table_name
        os.environ['API_GATEWAY_REGION1'] = 'api-gateway-1'
        os.environ['API_GATEWAY_REGION2'] = 'api-gateway-2'
        os.environ['AWS_REGION'] = 'us-west-2'
        os.environ['SNS_TOPIC_ARN'] = self.topic_arn

        # Invoke the Lambda handler
        response = lambda_handler({}, {})

        # Assert the response
        self.assertEqual(response['statusCode'], 200)
        self.assertEqual(response['body'], 'Lambda function executed successfully')

        # Assert that the items are stored in DynamoDB
        items = self.table.scan()['Items']
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]['item_id'], '1')
        self.assertEqual(items[1]['item_id'], '2')

        # Assert that an SNS notification is sent
        notifications = self.sns.list_subscriptions_by_topic(TopicArn=self.topic_arn)['Subscriptions']
        messages = self.sqs.receive_message(QueueUrl=self.sqs_url, MaxNumberOfMessages=10)["Messages"]

        self.assertEqual(len(messages), 1)


    def test_extract_item_info(self):
        with open("tests/unit/sample.html", "r") as file:
            html = file.read()
        
        soup = BeautifulSoup(html, 'html.parser')
        items = extract_item_info(soup)
        self.assertEqual(len(items), 14)
        self.assertEqual(items[0]['item_id'], 'H079086CK0Y')
        self.assertEqual(items[0]['title'], 'Lindy mini bag')
        self.assertEqual(items[0]['color'], 'Yellow')
        self.assertEqual(items[0]['url'], '/au/en/product/lindy-mini-bag-H079086CK0Y/')
        self.assertEqual(items[0]['price'], 11640)
        self.assertTrue(items[0]['unavailable'])


        self.assertEqual(items[6]['item_id'], 'H083618CKAB')
        self.assertEqual(items[6]['title'], 'Steeple 25 bag')
        self.assertEqual(items[6]['color'], 'Multi-colored')
        self.assertEqual(items[6]['url'], '/au/en/product/steeple-25-bag-H083618CKAB/')
        self.assertEqual(items[6]['price'], 7300)
        self.assertFalse(items[6]['unavailable'])