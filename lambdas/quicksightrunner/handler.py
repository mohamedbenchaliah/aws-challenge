
import logging
import os
import json

import awswrangler as wr

from os.path import dirname, abspath

import boto3

from boto3.dynamodb.conditions import Key
from botocore.client import Config


_logger: logging.Logger = logging.getLogger(__name__)

sfn_client_config = Config(connect_timeout=50, read_timeout=70)
sfn = boto3.client('stepfunctions', config=sfn_client_config)
sts = boto3.client('sts')
crawler = boto3.client('glue')
dynamodb = boto3.resource('dynamodb')


# todo : draft function >> work in progress

_config = {
    "sfn_activity_arn": "arn:aws:states:{}:{}:activity:QuickSightRunnerActivity".format(
        os.getenv("REGION", "eu-west-2"),
        sts.get_caller_identity()['Account']
    ),
    "sfn_worker_name": "quicksightrunner",
    "ddb_table": "QuickSightRunnerActiveJobs",
    "quicksight_data_source": "openaq_curated",
    "quicksight_datasets": ["vw_query1", "vw_query2", "vw_query3", "vw_query4"],
    "ddb_query_limit": 50,
    "sfn_max_executions": 100
}


def _read_sql(folder: str, file: str) -> str:
    path = os.path.join(dirname(abspath(__file__)), folder, file)
    with open(file=path, mode="r", encoding="utf-8") as f:
        query = f.read()
        return query


def create_data_source(datasource: str, user: str) -> None:
    """
    Create new data source from database.
    :param datasource: str
    :param user: str
    :return: None
    """
    try:
        sources = wr.quicksight.list_data_sources()
        s = list()
        for source in sources:
            s.append(source['Name'])

        if datasource not in s:
            try:
                wr.quicksight.create_athena_data_source(
                    name=datasource,
                    workgroup="primary",
                    allowed_to_manage=[user]
                )
            except Exception as e:
                _logger.error(f'Error while creating new datasource "{datasource}" in QuickSights. Error : {e}')
                raise

        else:
            _logger.info(f'Datasource "{datasource}" Already created')

    except Exception as e:
        _logger.error(f'Error while retrieving datasources in QuickSights. Error : {e}')
        raise


def create_dataset(datasource: str,
                   user: str,
                   sql: str,
                   dataset_name: str) -> None:
    """
    Create QuickSights Dataset.
    :param datasource:
    :param user: str
    :param sql: str
    :param dataset_name: str
    :return: None
    """
    try:
        datasets = wr.quicksight.list_datasets()
        s = list()
        for dataset in datasets:
            s.append(dataset['Name'])

        if datasets not in s:
            try:
                wr.quicksight.create_athena_dataset(
                    name=dataset_name,
                    sql=sql,
                    sql_name='CustomSQL',
                    data_source_name=datasource,
                    import_mode='SPICE',
                    allowed_to_manage=[user]
                )
            except Exception as e:
                _logger.error(f'Error while creating new dataset "{dataset_name}" in QuickSights. Error : {e}')
                raise

        else:
            _logger.info(f'Datasource "{datasource}" Already created')

    except Exception as e:
        _logger.error(f'Error while retrieving datasets in QuickSights. Error : {e}')
        raise


def start_quicksight_datasets(config):
    """Start the Crawler for curated tables.
    :param config: json
    :return: None
    """
    ddb_table = dynamodb.Table(config["ddb_table"])
    sfn_activity_arn = config['sfn_activity_arn']
    sfn_worker_name = config['sfn_worker_name']
    quicksight_data_source = config['quicksight_data_source']
    quicksight_datasets = config['quicksight_dataset']
    account = sts.get_caller_identity()['Account']

    while True:
        _logger.info(f'Polling for QuickSights tasks for Step Functions Activity ARN: {sfn_activity_arn}.')
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
            sources = wr.quicksight.list_data_sources()
            s = list()
            for source in sources:
                s.append(source['Name'])

            if quicksight_data_source not in s:
                wr.quicksight.create_athena_data_source(
                    name=quicksight_data_source,
                    workgroup="primary",
                    allowed_to_manage=[account]
                )
            else:
                _logger.info(f'Dataset "{quicksight_data_source}"already exists. Continue !')

        except Exception as e:
            _logger.error(f'Error while retrieving datasources from QuickSights. Error : {e}')
            raise

        datasets = wr.quicksight.list_datasets()
        s = list()
        for dataset in datasets:
            s.append(dataset['Name'])

        for dataset in quicksight_datasets:
            try:

                if dataset in s:
                    _logger.info(f'Starting the deletion of dataset "{dataset}".')
                    wr.quicksight.delete_dataset(name=dataset)

                _logger.info(f'Starting the creation of dataset "{dataset}".')

                wr.quicksight.create_athena_dataset(
                    name=dataset,
                    table=dataset,
                    data_source_name=quicksight_data_source,
                    database="openaq_db",
                    import_mode='DIRECT_QUERY',
                    allowed_to_manage=[account]
                )

                dataset_id = wr.quicksight.get_dataset_id(name=dataset)
                _logger.info(f'Dataset "{dataset}" created successfully.')

                ddb_table.put_item(Item={
                    'sfn_activity_arn': sfn_activity_arn,
                    'dataset_id': dataset_id,
                    'dataset_name': dataset,
                    'data_source_name': quicksight_data_source,
                    'sfn_task_token': task_token
                    }
                )

            except Exception as e:
                _logger.error(f'Failed to createdataset "{dataset}". Error : {e}')
                _logger.info('Sending "Task Failed" signal to Step Functions.')

                response = sfn.send_task_failure(
                    taskToken=task_token,
                    error='Failed to create quicksights dataset.'
                )
                return


def check_quicksight_state(config):
    """Check the datasets state.
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
        dataset_id = item['dataset_id']
        dataset_name = item['dataset_name']

        sfn_task_token = item['sfn_task_token']

        try:
            _logger.info('Polling QuickSights Dataset execution status..')

            description = wr.quicksight.describe_dataset("dataset_name")

            if description['CreatedTime'].timestamp() <= datetime.datetime.now().timestamp():
                _logger.info(f'Dataset with Id {dataset_id} SUCCEEDED.')
                _logger.info('Sending "Task Succeeded" signal to SFN.')
                task_output_dict = {
                    "DatasetName": dataset_name,
                    "DatasetId": dataset_id,
                    "DataCreationState": 'SUCCEEDED',
                    "DatasetCompletedOn": description['CreatedTime']
                }

                task_output_json = json.dumps(task_output_dict)
                sfn_resp = sfn.send_task_success(
                    taskToken=sfn_task_token,
                    output=task_output_json
                )

                resp = ddb_table.delete_item(
                    Key={
                        'sfn_activity_arn': sfn_activity_arn,
                        'dataset_id': dataset_id
                    }
                )

            else:
                message_json = {
                    "DatasetName": dataset_name,
                    "DatasetId": dataset_id,
                    "DataCreationState": 'FAILED',
                    "ErrorMessage": f'dataset {dataset_name} creation failed'
                }

                sfn_resp = sfn.send_task_failure(
                    taskToken=sfn_task_token,
                    cause=json.dumps(message_json),
                    error='QuickSightFailedError'
                )

                resp = ddb_table.delete_item(
                    Key={
                        'sfn_activity_arn': sfn_activity_arn,
                        "DatasetId": dataset_id,
                    }
                )

                _logger.error(f'Dataset "{dataset_name}" failed. ')

        except Exception as e:
            _logger.error(f'There was a problem checking status of QuickSight Dataset "{dataset_name}".'
                          f'Error: {e}')


def lambda_handler(event, _):
    """
    Main handler.
    :param event:
    :param _:
    :return: None
    """
    try:
        start_quicksight_datasets(_config)
        check_quicksight_state(_config)
        _logger.info('Crawler Runner terminating.')

    except Exception as e:
        _logger.critical(f'ERROR: Crawler runner lambda function failed. {e}')
        raise


# if __name__ == "__main__":
#     lambda_handler("", "")
