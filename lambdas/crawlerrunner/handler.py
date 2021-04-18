
import os
import logging
import json

import boto3

from boto3.dynamodb.conditions import Key
from botocore.client import Config


_logger: logging.Logger = logging.getLogger(__name__)

sfn_client_config = Config(connect_timeout=50, read_timeout=70)
sfn = boto3.client('stepfunctions', config=sfn_client_config)
sts = boto3.client('sts')
crawler = boto3.client('glue')
dynamodb = boto3.resource('dynamodb')


_config = {
    "sfn_activity_arn": "arn:aws:states:{}:{}:activity:CrawlerRunnerActivity".format(
        os.getenv("REGION", "eu-west-2"),
        sts.get_caller_identity()['Account']
    ),
    "sfn_worker_name": "crawlerrunner",
    "crawler_name": "openaq_curated_crawler",
    "ddb_table": "CrawlerRunnerActiveJobs",
    "ddb_query_limit": 50,
    "sfn_max_executions": 100
}


def start_crawler(config):
    """Start the Crawler for curated tables.
    :param config: json
    :return: None
    """
    ddb_table = dynamodb.Table(config["ddb_table"])
    sfn_activity_arn = config['sfn_activity_arn']
    sfn_worker_name = config['sfn_worker_name']
    crawler_name = config['crawler_name']

    while True:
        _logger.info(f'Polling for Athena tasks for Step Functions Activity ARN: {sfn_activity_arn}.')
        try:
            response = sfn.get_activity_task(
                activityArn=sfn_activity_arn,
                workerName=sfn_worker_name
            )

        except Exception as e:
            _logger.critical(f'Error unrecoverable while invoking get_activity_task for {sfn_activity_arn}.')
            raise

        task_token = response.get('taskToken', '')
        if not task_token:
            _logger.info('No tasks available.')
            return

        _logger.info(f'Task received. Token: {task_token}.')

        try:
            _logger.info(f'Starting Glue Crawler: {crawler_name}.')
            response = crawler.start_crawler(Name=crawler_name)
            crawler_request_id = crawler.get_crawler_metrics(CrawlerNameList=[crawler_name]) \
                ['ResponseMetadata']['RequestId']

            ddb_table.put_item(Item={
                'sfn_activity_arn': sfn_activity_arn,
                'crawler_request_id': crawler_request_id,
                'crawler_name': crawler_name,
                'sfn_task_token': task_token
                }
            )

        except Exception as e:
            _logger.error(f'Failed to invoke crawler {crawler_name}.Error : {e}')
            _logger.info('Sending "Task Failed" signal to Step Functions.')

            response = sfn.send_task_failure(
                taskToken=task_token,
                error='Failed to start Glue Crawler.'
            )
            return

        _logger.info(f'Glue Crawler "{crawler_name}" in progress... ')


def check_crawler_state(config):
    """Check the Crawler state.
    :param config: json
    :return: None
    """
    ddb_table = dynamodb.Table(config['ddb_table'])
    sfn_activity_arn = config['sfn_activity_arn']
    ddb_resp = ddb_table.query(
        KeyConditionExpression=Key('sfn_activity_arn').eq(sfn_activity_arn),
        Limit=config['ddb_query_limit']
    )

    for item in ddb_resp['Items']:
        crawler_request_id = item['crawler_request_id']
        crawler_name = item['crawler_name']
        sfn_task_token = item['sfn_task_token']

        try:
            _logger.info('Polling Crawler execution status..')

            response = crawler.get_crawler_metrics(CrawlerNameList=[crawler_name])
            # _logger.info(f'Crawler with Execution Id {crawler_request_id} is currently in state "{job_run_state}".')

            response1 = response['CrawlerMetricsList'][0]['StillEstimating']
            response2 = response['CrawlerMetricsList'][0]['LastRuntimeSeconds']
            res = response['ResponseMetadata']['HTTPHeaders'].get('date', '')

            # task = sfn.get_activity_task(activityArn=sfn_activity_arn, workerName=sfn_worker_name)

            if response['CrawlerMetricsList'][0]['TimeLeftSeconds'] == 0 and \
                    response['CrawlerMetricsList'][0]['LastRuntimeSeconds'] > 0:

                _logger.info(f'Crawler with Execution Id {crawler_request_id} SUCCEEDED.')
                _logger.info('Sending "Task Succeeded" signal to SFN.')
                task_output_dict = {
                    "CrawlerName": crawler_name,
                    "CrawlerRequestId": crawler_request_id,
                    "CrawlerRunState": 'SUCCEEDED',
                    "CrawlerCompletedOn": response['ResponseMetadata']['HTTPHeaders'].get('date', ''),
                    "CrawlerTableUpdated": response['CrawlerMetricsList'][0]['TablesUpdated']
                }

                task_output_json = json.dumps(task_output_dict)
                sfn_resp = sfn.send_task_success(
                    taskToken=sfn_task_token,
                    output=task_output_json
                )

                resp = ddb_table.delete_item(
                    Key={
                        'sfn_activity_arn': sfn_activity_arn,
                        'crawler_request_id': crawler_request_id
                    }
                )

            elif response['CrawlerMetricsList'][0]['StillEstimating'] or \
                    response['CrawlerMetricsList'][0]['TimeLeftSeconds'] > 0:
                sfn_resp = sfn.send_task_heartbeat(
                    taskToken=sfn_task_token
                )
                _logger.info(f'Crawler with Execution Id {crawler_request_id} hasn\'t finished yet.')

            else:
                message_json = {
                    'crawler_name': crawler_name,
                    'crawler_request_id': crawler_request_id,
                    'crawler_run_state': 'FAILED',
                    'glue_job_run_error_msg': f'Crawler {crawler_name} Failed'
                }

                sfn_resp = sfn.send_task_failure(
                    taskToken=sfn_task_token,
                    cause=json.dumps(message_json),
                    error='CrawlerFailedError'
                )

                resp = ddb_table.delete_item(
                    Key={
                        'sfn_activity_arn': sfn_activity_arn,
                        'crawler_request_id': crawler_request_id
                    }
                )

                _logger.error(f'Crawler "{crawler_name}" failed. ')

        except Exception as e:
            _logger.error(f'There was a problem checking status of Glue Crawler "{crawler_name}".'
                          f'Error: {e}')


def lambda_handler(event, _):
    """
    Main handler.
    :param event:
    :param _:
    :return: None
    """
    try:
        start_crawler(_config)
        check_crawler_state(_config)
        _logger.info('Crawler Runner terminating.')

    except Exception as e:
        _logger.critical(f'ERROR: Crawler runner lambda function failed. {e}')
        raise


# if __name__ == "__main__":
#     lambda_handler("", "")
