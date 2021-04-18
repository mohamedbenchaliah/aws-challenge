
import os
import logging
import json

import boto3

from botocore.client import Config


_logger: logging.Logger = logging.getLogger(__name__)


sfn_client_config = Config(connect_timeout=50, read_timeout=70)
sfn = boto3.client('stepfunctions', config=sfn_client_config)

sts = boto3.client('sts')
account_id = sts.get_caller_identity().get('Account')
region_name = os.getenv("REGION", "eu-west-2")


def map_activity_arn(bucket, key):
    """
    Map s3 key to activity ARN based on a convention.
    :param bucket: S3 bucket name
    :param key: S3 bucket key
    :return: activity ARN
    """
    key_elements = [x.strip() for x in key.split('/')]
    activity_name = '{}-{}-raw-data-created'.format(bucket, key_elements[0])
    return 'arn:aws:states:{}:{}:activity:{}'.format(region_name, account_id, activity_name)


def lambda_handler(event, context):
    """
    Main handler.
    :param event: S3 Json Put Object Event string
    :param context: S3 Put Object Context
    """
    _logger.info("Received event: " + json.dumps(event, indent=2))
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']
    sfn_activity_arn = map_activity_arn(bucket, key)
    sfn_worker_name = 'on_s3_object_created'

    try:
        try:
            response = sfn.get_activity_task(
                activityArn=sfn_activity_arn,
                workerName=sfn_worker_name
            )

        except Exception as e:
            _logger.critical('Unrecoverable error invoking get_activity_task for {}.'.format(sfn_activity_arn))
            raise

        sfn_task_token = response.get('taskToken', '')
        _logger.info('Sending "Task Succeeded" signal to Step Functions..')
        task_output_dict = {
            'S3BucketName': bucket,
            'S3Key': key,
            'SFNActivityArn': sfn_activity_arn
        }
        task_output_json = json.dumps(task_output_dict)
        sfn_resp = sfn.send_task_success(
            taskToken=sfn_task_token,
            output=task_output_json
        )

    except Exception as e:
        _logger.critical(e)
        raise e

