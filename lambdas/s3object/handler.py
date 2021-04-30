
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
    # sfn_activity_arn = map_activity_arn(bucket, key)
    sfn_activity_arn = "arn:aws:states:{}:{}:activity:S3objectActivity".format(
        os.getenv("REGION", "eu-west-2"),
        sts.get_caller_identity()['Account']
    )
    sfn_worker_name = 'on_s3_object_created'

    key_elements = [x.strip() for x in key.split('/')]

    if key_elements[0]+'/'+key_elements[1] == 'ingest/openaq':
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


# if __name__ == "__main__":
#     event = {
# 	"Records": [
# 		{
# 			"eventVersion": "2.1",
# 			"eventSource": "aws:s3",
# 			"awsRegion": "eu-west-1",
# 			"eventTime": "2021-04-11T15:04:23.473Z",
# 			"eventName": "ObjectCreated:Put",
# 			"userIdentity": {
# 				"principalId": "AWS:AIDA4H5SWEAPJATCAYKJK"
# 			},
# 			"requestParameters": {
# 				"sourceIPAddress": "46.233.116.242"
# 			},
# 			"responseElements": {
# 				"x-amz-request-id": "BC4DD33287351C20",
# 				"x-amz-id-2": "/S2XbXHr5ynjCNy2f4pWkAyxSqWBCjcvVLl3+JoKgA9TnsyRyGN9/ygB6X1N2lqqSWPe6Zes2ns="
# 			},
# 			"s3": {
# 				"s3SchemaVersion": "1.0",
# 				"configurationId": "dd56e4ae-1b0a-4dbc-86cc-99e7b4d580da",
# 				"bucket": {
# 					"name": "aws-test-data-bucket-070420212230\n",
# 					"ownerIdentity": {
# 						"principalId": "A3GF652PIWJM0B"
# 					},
# 					"arn": "arn:aws:s3:::test-data-platform-dev"
# 				},
# 				"object": {
# 					"key": "ingest/openaq/2018/04/06/openaq.csv",
# 					"size": 32907,
# 					"eTag": "ce44503030055f73da0e8604eb0e2052",
# 					"sequencer": "005D5C0BF758AC2FEC"
# 				}
# 			}
# 		}
# 	]
# }
#
#     lambda_handler(event, "")
