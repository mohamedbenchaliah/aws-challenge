
import os
import logging
import json

import boto3

from botocore.client import Config
from boto3.dynamodb.conditions import Key


_logger: logging.Logger = logging.getLogger(__name__)

sfn_client_config = Config(connect_timeout=50, read_timeout=70)
sfn = boto3.client('stepfunctions', config=sfn_client_config)
athena = boto3.client('athena')
dynamodb = boto3.resource('dynamodb')
sts = boto3.client('sts')


_config = {
    "sfn_activity_arn": "arn:aws:states:{}:{}:activity:AthenaRunnerActivity".format(
        os.getenv("REGION", "eu-west-2"),
        sts.get_caller_identity()['Account']
    ),
    "sfn_worker_name": "athenarunner",
    "ddb_table": "AthenaRunnerActiveJobs",
    "ddb_query_limit": 50,
    "sfn_max_executions": 100
}


def start_athena_queries(config):
    """Function to lunch Athena queries.
    :param config: json file w/ config params
    :return: None
    """
    ddb_table = dynamodb.Table(config["ddb_table"])
    sfn_activity_arn = config['sfn_activity_arn']
    sfn_worker_name = config['sfn_worker_name']

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

        task_input = ''
        try:
            task_input = json.loads(response['input'])
            task_input_dict = json.loads(task_input)
            athena_named_query = task_input_dict.get('AthenaNamedQuery', None)

            if athena_named_query is None:
                athena_query_string = task_input_dict['AthenaQueryString']
                athena_database = task_input_dict['AthenaDatabase']
            else:
                _logger.info(f'Retrieving details of named query "{athena_named_query}" from Athena.')

                response = athena.get_named_query(
                    NamedQueryId=athena_named_query
                )

                athena_query_string = response['NamedQuery']['QueryString']
                athena_database = response['NamedQuery']['Database']

            athena_result_output_location = task_input_dict['AthenaResultOutputLocation']
            athena_result_encryption_option = task_input_dict.get('AthenaResultEncryptionOption', None)
            athena_result_kms_key = task_input_dict.get('AthenaResultKmsKey', "NONE").capitalize()

            athena_result_encryption_config = {}
            if athena_result_encryption_option is not None:

                athena_result_encryption_config['EncryptionOption'] = athena_result_encryption_option

                if athena_result_encryption_option in ["SSE_KMS", "CSE_KMS"]:
                    athena_result_encryption_config['KmsKey'] = athena_result_kms_key

        except (KeyError, Exception):
            _logger.critical('Invalid inputs. Make sure the required athena parameters are specified properly.')
            raise

        try:
            response = athena.start_query_execution(
                QueryString=athena_query_string,
                QueryExecutionContext={
                    'Database': athena_database
                },
                ResultConfiguration={
                    'OutputLocation': athena_result_output_location,
                    'EncryptionConfiguration': athena_result_encryption_config
                }
            )

            athena_query_execution_id = response['QueryExecutionId']

            ddb_table.put_item(Item={
                'sfn_activity_arn': sfn_activity_arn,
                'athena_query_execution_id': athena_query_execution_id,
                'sfn_task_token': task_token
                }
            )

        except Exception as e:
            _logger.error(f'Failed to query Athena database "{athena_database}" with query "{athena_query_string}". '
                          f'Error : {e}')
            _logger.info('Sending "Task Failed" signal to Step Functions.')

            response = sfn.send_task_failure(
                taskToken=task_token,
                error='Failed to start Athena query.'
            )
            return

        _logger.info(f'Athena query started. Query Execution Id: {athena_query_execution_id}.')


def check_athena_queries(config):
    """Function to check the athena query status.
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
        athena_query_execution_id = item['athena_query_execution_id']
        sfn_task_token = item['sfn_task_token']
        try:
            _logger.info('Polling Athena query execution status..')
            athena_resp = athena.get_query_execution(
                QueryExecutionId=athena_query_execution_id
            )

            query_exec_resp = athena_resp['QueryExecution']
            query_exec_state = query_exec_resp['Status']['State']
            query_state_change_reason = query_exec_resp['Status'].get('StateChangeReason', '')

            _logger.info(f'Query with Execution Id {query_exec_state} '
                         f'is currently in state "{query_state_change_reason}".')

            if query_exec_state in ['SUCCEEDED']:
                _logger.info(f'Query with Execution Id {athena_query_execution_id} SUCCEEDED.')

                task_output_dict = {
                    "AthenaQueryString": query_exec_resp['Query'],
                    "AthenaQueryExecutionId": athena_query_execution_id,
                    "AthenaQueryExecutionState": query_exec_state,
                    "AthenaQueryExecutionStateChangeReason": query_state_change_reason,
                    "AthenaQuerySubmissionDateTime": query_exec_resp['Status'].get('SubmissionDateTime', '').strftime(
                        '%x, %-I:%M %p %Z'),
                    "AthenaQueryCompletionDateTime": query_exec_resp['Status'].get('CompletionDateTime', '').strftime(
                        '%x, %-I:%M %p %Z'),
                    "AthenaQueryEngineExecutionTimeInMillis": query_exec_resp['Statistics'].get(
                        'EngineExecutionTimeInMillis', 0),
                    "AthenaQueryDataScannedInBytes": query_exec_resp['Statistics'].get('DataScannedInBytes', 0)
                }

                task_output_json = json.dumps(task_output_dict)

                sfn_resp = sfn.send_task_success(
                    taskToken=sfn_task_token,
                    output=task_output_json
                )

                resp = ddb_table.delete_item(
                    Key={
                        'sfn_activity_arn': sfn_activity_arn,
                        'athena_query_execution_id': athena_query_execution_id
                    }
                )

            elif query_exec_state in ['RUNNING', 'QUEUED']:
                _logger.info(f'Query with Execution Id {athena_query_execution_id} is in state hasn\'t completed yet.')

                sfn_resp = sfn.send_task_heartbeat(
                    taskToken=sfn_task_token
                )

            elif query_exec_state in ['FAILED', 'CANCELLED']:
                message_json = {
                    "AthenaQueryString": query_exec_resp['Query'],
                    "AthenaQueryExecutionId": athena_query_execution_id,
                    "AthenaQueryExecutionState": query_exec_state,
                    "AthenaQueryExecutionStateChangeReason": query_state_change_reason,
                    "AthenaQuerySubmissionDateTime": query_exec_resp['Status'].get('SubmissionDateTime', '').strftime(
                        '%x, %-I:%M %p %Z'),
                    "AthenaQueryCompletionDateTime": query_exec_resp['Status'].get('CompletionDateTime', '').strftime(
                        '%x, %-I:%M %p %Z'),
                    "AthenaQueryEngineExecutionTimeInMillis": query_exec_resp['Statistics'].get(
                        'EngineExecutionTimeInMillis', 0),
                    "AthenaQueryDataScannedInBytes": query_exec_resp['Statistics'].get('DataScannedInBytes', 0)
                }

                sfn_resp = sfn.send_task_failure(
                    taskToken=sfn_task_token,
                    cause=json.dumps(message_json),
                    error='AthenaQueryFailedError'
                )

                resp = ddb_table.delete_item(
                    Key={
                        'sfn_activity_arn': sfn_activity_arn,
                        'athena_query_execution_id': athena_query_execution_id
                    }
                )

                _logger.error(f'Athena query with Execution Id "{athena_query_execution_id}" failed. '
                              f'Last state: {query_exec_state}. Error message: {query_state_change_reason}')

        except Exception as e:
            _logger.error(f'There was a problem checking status of Athena query "{athena_query_execution_id}".'
                          f'Error: {e}')


def lambda_handler(event, _):
    """
    Main handler.
    :param event: S3 Json Put Object Event string
    :param _: S3 Put Object Empty Context
    :return: None
    """
    try:
        start_athena_queries(_config)
        check_athena_queries(_config)
        _logger.info('Athena Runner terminating.')

    except Exception as e:
        _logger.critical(f'ERROR: Athena runner lambda function failed. {e}')
        raise
