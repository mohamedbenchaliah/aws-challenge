import os
import json
import boto3
import time

from logging import Logger, getLogger
from botocore.exceptions import ClientError


_logger: Logger = getLogger(__name__)

_region = "eu-west-1"
_acc = boto3.client('sts').get_caller_identity().get('Account')
_red = "#d62728"
_green = "#2ca02c"
_purple = "#9467bd"
_orange = "#ff7f0e"
_blue = "#1f77b4"
_grey = "#7f7f7f"


def get_client():
    """Generate a cloudwatch api client. """
    try:
        api = boto3.client('cloudwatch')
    except ClientError as e:
        _logger.error("Client error: %s", e)
        exit(1)
        return e
    else:
        return api


def alarms(**kwargs):
    """Put a CloudWatch Alarm."""
    _CW = get_client()
    for _ in range(3):
        try:
            time.sleep(0.5)
            _CW.put_metric_alarm(**kwargs)
        except Exception as e:
            _logger.error(f"Error : {e} .")
            continue
        break
    else:
        _logger.error('Exception when doing put_metric_alarm.')


def generate_dashboard(client):
    paginator = client.get_paginator('list_metrics')

    response_iterator = paginator.paginate(
        Namespace='Glue'
    )

    job_names = set()
    for response in response_iterator:
        for metric in response['Metrics']:
            for dim in metric['Dimensions']:
                if dim['Name'] == 'JobName':
                    job_names.add(dim['Value'])

    widgets = []
    # start :
    #   The start of the time range to use for each widget on the dashboard.
    #   You can specify start without specifying end to specify a relative time range that ends with the current time.
    #   In this case, the value of start must begin with -PT if you specify a time range in minutes or hours,
    #   and must begin with -P if you specify a time range in days, weeks, or months.
    #   You can then use M, H, D, W and M as abbreviations for minutes, hours, days, weeks and months.
    #   For example, -PT5M shows the last 5 minutes, -PT8H shows the last 8 hours, and -P3M shows the last three months.
    #   If you omit start, the dashboard shows the default time range when it loads.

    # periodOverride:
    #   specifying auto causes the period of all graphs on
    #   the dashboard to automatically adapt to the time range of the dashboard.
    #   Specifying inherit ensures that the period set for each graph is always obeyed.
    #   Valid Values: auto | inherit

    dashboard = {
        "start": "-P7D",
        "periodOverride": "auto",
        "widgets": widgets
    }
    y = 3
    for job_name in sorted(job_names):
        widgets.append({
            "type": "text",
            "x": 0,
            "y": y,
            "width": 24,
            "height": 1,
            "properties": {
                "markdown": f"**{job_name}**\n--------------"
            }
        })

        widgets.append({
                "type": "metric",
                "x": 0,
                "y": y+1,
                "width": 12,
                "height": 5,
                "properties": {
                    "metrics": [
                        ["Glue", "glue.ALL.s3.filesystem.read_bytes",
                         "JobName", job_name,
                         "JobRunId", "ALL",
                         "Type", "count",
                         {"color": _purple,
                          "yAxis": "left",
                          "label": "BytesRead",
                          "visible": False
                          }],
                        ["Glue", "glue.ALL.s3.filesystem.write_bytes",
                         "JobName", job_name,
                         "JobRunId", "ALL",
                         "Type", "count",
                         {"color": _grey,
                          "yAxis": "left",
                          "label": "BytesWrite",
                          "visible": False
                          }],
                    ],
                    "view": "timeSeries",
                    "stacked": False,
                    "liveData": True,
                    "region": "eu-west-1",
                    "title": "Bytes read vs written into S3",
                    "period": 604800,
                    "stat": "Sum"
                }
            }
        )

        widgets.append({
                "type": "metric",
                "x": 12,
                "y": y+1,
                "width": 12,
                "height": 5,
                "properties": {
                    "metrics": [
                        ["Glue", "glue.driver.aggregate.elapsedTime",
                         "JobName", job_name,
                         {"color": _red,
                          "label": "Driver Elapsed Time",
                          }]
                    ],
                    "view": "timeSeries",
                    "stacked": False,
                    "liveData": True,
                    "region": "eu-west-1",
                    "title": "Glue Driver Elapsed Time Agr",
                    "period": 604800,
                    "stat": "Sum"
                }
            }
        )

        widgets.append({
                "type": "metric",
                "x": 0,
                "y": y+2,
                "width": 12,
                "height": 5,
                "properties": {
                    "metrics": [
                        ["Glue", "glue.driver.aggregate.numCompletedTasks", "JobName", job_name,
                         {"color": _green,
                          "yAxis": "left",
                          "label": "Completed Tasks",
                          }],
                        ["Glue", "glue.driver.aggregate.numFailedTasks",
                         "JobName", job_name,
                         {"color": _green,
                          "yAxis": "left",
                          "label": "Failed Tasks",
                          }]
                    ],
                    "view": "timeSeries",
                    "stacked": False,
                    "liveData": True,
                    "region": "eu-west-1",
                    "title": "Completed vs Failed Tasks",
                    "period": 604800,
                    "stat": "Sum"
                }
            }
        )

        widgets.append({
                "type": "metric",
                "x": 12,
                "y": y+2,
                "width": 12,
                "height": 5,
                "properties": {
                    "metrics": [
                        ["Glue", "glue.driver.ExecutorAllocationManager.executors.numberAllExecutors",
                         "JobName", job_name,
                         {"color": _blue,
                          "yAxis": "left",
                          "label": "Sum Of Needed Executors",
                          }],
                        [".", "glue.driver.system.cpuSystemLoad",
                         "JobName", job_name,
                         {"color": _orange,
                          "yAxis": "right",
                          "label": "Driver CPU Load",
                          }]
                    ],
                    "view": "timeSeries",
                    "stacked": False,
                    "liveData": True,
                    "region": "eu-west-1",
                    "title": "Needed Executors vs CPU Usage",
                    "period": 604800,
                    "stat": "Sum"
                }
            }
        )

        y += 10

    widgets.append({
        "type": "text",
        "x": 0,
        "y": 0,
        "width": 24,
        "height": 4,
        "properties": {
            "markdown": f"\n* **Bytes Read** - The number of bytes read from s3 "
                        f"by all completed Spark tasks running in all executors.\n "
                        f"\n* **Records Read** - The number of bytes written into s3 "
                        f"by all completed Spark tasks running in all executors.\n"
                        f"\n* **Driver Elapsed Time** - The ETL elapsed time in milliseconds "
                        f"(does not include the job bootstrap times).\n"
                        f"\n* **Number Of Executors** - The number of actively running job executors.\n"
                        f"\n* **Completed Tasks** - The number of completed tasks in the job.\n"
                        f"\n* **Failed Tasks** – The number of failed tasks.\n\n\n\n\n\n"
                        f"*(*) All metrics are calculated over the past 7 days*\n"
        }
    })

    widgets.append({
        "type": "metric",
        "x": 0,
        "y": 0,
        "width": 24,
        "height": 3,
        "properties":
            {
                "metrics": [
                    [{"expression": "SUM(METRICS())", "label": "Total Jobs", "id": "e1", "region": "eu-west-1"}],
                    ["CustomMetrics", "custom-glue-failedjob", {"id": "m1", "label": "Failed Jobs"}],
                    [".", "custom-glue-succeededjob", {"id": "m2", "label": "Successful Jobs"}]
                ],
                "view": "singleValue",
                "stacked": False,
                "region": "eu-west-1",
                "singleValueFullPrecision": False,
                "setPeriodToTimeRange": True,
                "title": "Glue Jobs Summary - Last 7 days",
                "period": 604800,
                "stat": "Sum"
            }
    })

    return dashboard


def generate_alarms(client):
    paginator = client.get_paginator('list_metrics')
    response_iterator = paginator.paginate(
        Namespace='Glue'
    )

    job_names = set()
    for response in response_iterator:
        for metric in response['Metrics']:
            for dim in metric['Dimensions']:
                if dim['Name'] == 'JobName':
                    job_names.add(dim['Value'])

    for job_name in sorted(job_names):
        alarms(
            AlarmName=job_name + '_number_failed_tasks_alarm',
            MetricName='glue.driver.aggregate.numFailedTasks',
            Namespace='Glue',
            Statistic='Sum',
            ComparisonOperator='GreaterThanOrEqualToThreshold',
            Threshold=1,
            Period=300,
            EvaluationPeriods=1,
            Dimensions=[
                {
                    'Name': 'DBClusterIdentifier',
                    'Value': job_name
                }
            ],
            Unit='Count',
            ActionsEnabled=True,
            AlarmActions=[f'arn:aws:sns:{_region}:{_acc}:platform-alert-notifications']
        )

        alarms(
            AlarmName=job_name + '_cpu_system_load_percentage_alarm',
            MetricName='glue.ALL.system.cpuSystemLoad',
            Namespace='Glue',
            Statistic='Sum',
            ComparisonOperator='GreaterThanOrEqualToThreshold',
            Threshold=0.8,
            Period=300,
            EvaluationPeriods=1,
            Dimensions=[
                {
                    'Name': 'DBClusterIdentifier',
                    'Value': job_name
                }
            ],
            Unit='Percent',
            ActionsEnabled=True,
            AlarmActions=[f'arn:aws:sns:{_region}:{_acc}:platform-alert-notifications']
        )


def lambda_handler(event, context):
    _CW = get_client()
    dashboard = generate_dashboard(_CW)
    try:
        _CW.put_dashboard(
            DashboardName=f'glue-monitoring-dashboard',
            DashboardBody=json.dumps(dashboard)
        )
        _logger.info(f"Dashboard glue-monitoring-dashboard updated. ")
    except Exception as e:
        _logger.error(f"Failed updating dashboard glue-monitoring-dashboard : {e}. ")
    try:
        generate_alarms(_CW)
        _logger.info(f"CloudWatch Alarms created successfully for dashboard glue-monitoring-dashboard. ")
    except Exception as e:
        _logger.error(f"Failed creating CloudWatch Alarms : {e}. ")

#
# if __name__ == '__main__':
#     lambda_handler(None, None)
