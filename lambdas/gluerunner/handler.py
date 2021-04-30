
import os
import logging
import json
import boto3

from botocore.client import Config
from boto3.dynamodb.conditions import Key


_logger: logging.Logger = logging.getLogger(__name__)

sfn_client_config = Config(connect_timeout=50, read_timeout=70)
sfn = boto3.client('stepfunctions', config=sfn_client_config)
glue = boto3.client('glue')
dynamodb = boto3.resource('dynamodb')
sts = boto3.client('sts')


_config = {
    "sfn_activity_arn": "arn:aws:states:{}:{}:activity:GlueRunnerActivity".format(
        os.getenv("REGION", "eu-west-2"),
        sts.get_caller_identity()['Account']
    ),
    "sfn_worker_name": "gluerunner",
    "ddb_table": "GlueRunnerActiveJobs",
    "ddb_query_limit": 50,
    "glue_job_capacity": 10
}


def start_glue_jobs(config):
    """Function to lunch the glue job.
    :param config: json file w/ config params
    :return: None
    """
    ddb_table = dynamodb.Table(config["ddb_table"])
    glue_job_capacity = config['glue_job_capacity']
    sfn_activity_arn = config['sfn_activity_arn']
    sfn_worker_name = config['sfn_worker_name']

    while True:
        try:
            response = sfn.get_activity_task(
                activityArn=sfn_activity_arn,
                workerName=sfn_worker_name
            )

        except Exception as e:
            _logger.critical(f'Error unrecoverable while invoking get_activity_task for {sfn_activity_arn}: {e}')
            raise

        task_token = response.get('taskToken', '')
        if not task_token:
            _logger.info('No tasks to process.')
            return

        _logger.info(f'Received task. Task token: {task_token}.')

        task_input = ''
        try:
            task_input = json.loads(response['input'])
            task_input_dict = json.loads(task_input)
            glue_job_name = task_input_dict['GlueJobName']
            glue_job_capacity = int(task_input_dict.get('GlueJobCapacity', glue_job_capacity))

        except (KeyError, Exception):
            _logger.critical('Invalid inputs. Make sure the required parameters are specified properly.')
            raise

        glue_job_args = task_input_dict
        _logger.info(f'Running Glue job "{glue_job_name}"..')

        try:
            response = glue.start_job_run(
                JobName=glue_job_name,
                Arguments=glue_job_args,
                # Arguments={
                #     'string': 'string'
                # },
                AllocatedCapacity=glue_job_capacity
            )

            glue_job_run_id = response['JobRunId']

            # Store the Task Token and Glue Run Id in DynamoDB
            ddb_table.put_item(Item={
                'sfn_activity_arn': sfn_activity_arn,
                'glue_job_name': glue_job_name,
                'glue_job_run_id': glue_job_run_id,
                'sfn_task_token': task_token
                }
            )

        except Exception as e:
            _logger.error(f'Failed to start Glue job "{glue_job_name}". {e}')
            _logger.info('Returning "Task Failed" signal to SFN.')
            response = sfn.send_task_failure(
                taskToken=task_token,
                error='Failed to start Glue job.'
            )
            return

        _logger.info('Glue job run started. Run Id: {}'.format(glue_job_run_id))


def check_glue_jobs(config):
    """Function to check the glue job status.
    :param config: json file w/ config params
    :return: None
    """
    ddb_table = dynamodb.Table(config['ddb_table'])
    sfn_activity_arn = config['sfn_activity_arn']

    ddb_resp = ddb_table.query(
        KeyConditionExpression=Key('sfn_activity_arn').eq(sfn_activity_arn),
        Limit=config['ddb_query_limit']
    )

    for item in ddb_resp['Items']:
        glue_job_run_id = item['glue_job_run_id']
        glue_job_name = item['glue_job_name']
        sfn_task_token = item['sfn_task_token']

        try:
            _logger.info('Polling Glue job run status..')
            glue_resp = glue.get_job_run(
                JobName=glue_job_name,
                RunId=glue_job_run_id,
                PredecessorsIncluded=False
            )

            job_run_state = glue_resp['JobRun']['JobRunState']
            job_run_error_message = glue_resp['JobRun'].get('ErrorMessage', '')
            _logger.info(f'Job with Run Id {glue_job_run_id} is currently in state "{job_run_state}".')

            if job_run_state in ['SUCCEEDED']:
                _logger.info(f'Job with Run Id {glue_job_run_id} SUCCEEDED.')
                _logger.info('Sending "Task Succeeded" signal to SFN.')
                task_output_dict = {
                    "GlueJobName": glue_job_name,
                    "GlueJobRunId": glue_job_run_id,
                    "GlueJobRunState": job_run_state,
                    "GlueJobStartedOn": glue_resp['JobRun'].get('StartedOn', '').strftime('%x, %-I:%M %p %Z'),
                    "GlueJobCompletedOn": glue_resp['JobRun'].get('CompletedOn', '').strftime('%x, %-I:%M %p %Z'),
                    "GlueJobLastModifiedOn": glue_resp['JobRun'].get('LastModifiedOn', '').strftime('%x, %-I:%M %p %Z')
                }
                task_output_json = json.dumps(task_output_dict)
                sfn_resp = sfn.send_task_success(
                    taskToken=sfn_task_token,
                    output=task_output_json
                )

                resp = ddb_table.delete_item(
                    Key={
                        'sfn_activity_arn': sfn_activity_arn,
                        'glue_job_run_id': glue_job_run_id
                    }
                )

            elif job_run_state in ['STARTING', 'RUNNING', 'STOPPING']:
                sfn_resp = sfn.send_task_heartbeat(
                    taskToken=sfn_task_token
                )
                _logger.info(f'Job with Run Id {glue_job_run_id} hasn\'t finished yet.')

            elif job_run_state in ['FAILED', 'STOPPED']:
                message_json = {
                    'glue_job_name': glue_job_name,
                    'glue_job_run_id': glue_job_run_id,
                    'glue_job_run_state': job_run_state,
                    'glue_job_run_error_msg': job_run_error_message
                }

                sfn_resp = sfn.send_task_failure(
                    taskToken=sfn_task_token,
                    cause=json.dumps(message_json),
                    error='GlueJobFailedError'
                )

                resp = ddb_table.delete_item(
                    Key={
                        'sfn_activity_arn': sfn_activity_arn,
                        'glue_job_run_id': glue_job_run_id
                    }
                )

                _logger.error(f'Glue job "{glue_job_name}" run with Run Id "{glue_job_run_id[:8]}" failed.'
                              f'Last state: {job_run_state}. Error message: {job_run_error_message}.')

        except Exception as e:
            _logger.error(f'There was a problem checking status of Glue job "{glue_job_name}". {e}')


def lambda_handler(event, _):
    """
    Main handler.
    :param event: S3 Json Put Object Event string
    :param _: Empty Context
    :return: None
    """
    _logger.info('Glue Runner lambda function starting. ')

    try:
        start_glue_jobs(_config)
        check_glue_jobs(_config)
        _logger.info('Master Glue Runner terminating. ')

    except Exception as e:
        _logger.critical(f'ERROR: Glue runner lambda function failed. {e}')
        raise

