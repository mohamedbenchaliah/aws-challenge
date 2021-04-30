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


def generate_dashboard():

    widgets = []
    widgets.append({
        "type": "text",
        "x": 0,
        "y": 0,
        "width": 24,
        "height": 4,
        "properties": {
            "markdown": f"\n* **Invocations** - Measures the number of times the function is invoked. "
                        f"It includes both failed and successful invocations but not failed invocation requests.\n "
                        f"\n* **Errors** - Measures the number of times an invocation failed due to an "
                        f"error in the function, a function timeout, out of memory error, or permission error. "
                        f"It does not include failures due to exceeding concurrency "
                        f"limits or internal service errors.\n"
                        f"\n* **Concurrent Executions** - This metric is an account-wide aggregate metric "
                        f"indicating the max / avg of concurrent executions for the function.\n"
                        f"\n* **Throttles** -  Throttled invocations are counted whenever "
                        f"an invocation attempt fails due to exceeded concurrency limits.\n"
                        f"\n* **Execution Time** – measures the elapsed wall "
                        f"clock time from when the function.\n\n\n\n "
                        f"*(*) All metrics are calculated over the past 7 days*\n"
        }
    })

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
    for function_name in ['gluerunner',
                          'crawlerrunner',
                          'athenarunner',
                          's3object']:
        widgets.append({
            "type": "text",
            "x": 0,
            "y": y,
            "width": 24,
            "height": 1,
            "properties": {
                "markdown": f"# {function_name}\n--------------"
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
                    ["AWS/Lambda", "Invocations",
                     "FunctionName", function_name,
                     "Resource", function_name,
                     {"color": _blue,
                      "label": "Number of Invocations",
                      "stat": "Sum",
                      "id": "m1"
                      }],
                    ["AWS/Lambda", "Errors", "FunctionName", function_name,
                     {"color": _red,
                      "label": "Number of Errors",
                      "stat": "Sum",
                      "id": "m2"
                      }]
                ],
                "view": "timeSeries",
                "liveData": True,
                "stacked": False,
                "region": "eu-west-1",
                "title": "Invocations vs Errors",
                "period": 60,
            }
        })

        widgets.append({
            "type": "metric",
            "x": 12,
            "y": y+1,
            "width": 12,
            "height": 5,
            "properties": {
                "metrics": [
                    ["AWS/Lambda", "ConcurrentExecutions",
                     "FunctionName", function_name,
                     {"stat": "Maximum",
                      "color": _red,
                      "label": "Maximum Concurrent Executions",
                      }],
                    ["AWS/Lambda", "ConcurrentExecutions",
                     "FunctionName", function_name,
                     {"stat": "Average",
                      "color": _purple,
                      "label": "Average Concurrent Executions",
                      }]
                ],
                "view": "timeSeries",
                "liveData": True,
                "stacked": False,
                "region": "eu-west-1",
                "title": "Concurrent Executions",
                "period": 60,
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
                    ["AWS/Lambda", "Throttles",
                     "FunctionName", function_name,
                     {"color": _orange,
                      "stat": "Sum",
                      }]
                ],
                "view": "timeSeries",
                "liveData": True,
                "stacked": False,
                "region": "eu-west-1",
                "title": "Throttles",
                "period": 60
            }
        })

        widgets.append({
            "type": "metric",
            "x": 12,
            "y": y+1,
            "width": 12,
            "height": 5,
            "properties": {
                "metrics": [
                    ["AWS/Lambda", "Duration", "FunctionName", function_name,
                     {"stat": "Maximum",
                      "color": _red,
                      "label": "Maximum Execution Time",
                      }],
                    ["AWS/Lambda", "Duration", "FunctionName", function_name,
                     {"stat": "Average",
                      "color": _purple,
                      "label": "Average Execution Time",
                      }]
                ],
                "view": "timeSeries",
                "liveData": True,
                "stacked": False,
                "region": "eu-west-1",
                "title": "Execution Time",
                "period": 60,
            }
        })

        y += 10

    return dashboard


def generate_alarms():
    for function_name in ['gluerunner',
                          'crawlerrunner',
                          'athenarunner',
                          's3object']:
        alarms(
            AlarmName=function_name + '_concurrent_executions_alarm',
            MetricName='ConcurrentExecutions',
            Namespace='AWS/Lambda',
            Statistic='Sum',
            ComparisonOperator='GreaterThanOrEqualToThreshold',
            Threshold=500,
            Period=300,
            EvaluationPeriods=3,
            Dimensions=[
                {
                    'Name': 'DBClusterIdentifier',
                    'Value': function_name
                }
            ],
            Unit='Count',
            ActionsEnabled=True,
            AlarmActions=[f'arn:aws:sns:{_region}:{_acc}:platform-alert-notifications']
        )

        alarms(
            AlarmName=function_name + '_errors_alarm',
            MetricName='Errors',
            Namespace='AWS/Lambda',
            Statistic='Sum',
            ComparisonOperator='GreaterThanOrEqualToThreshold',
            Threshold=1,
            Period=300,
            EvaluationPeriods=3,
            Dimensions=[
                {
                    'Name': 'DBClusterIdentifier',
                    'Value': function_name
                }
            ],
            Unit='Count',
            ActionsEnabled=True,
            AlarmActions=[f'arn:aws:sns:{_region}:{_acc}:platform-alert-notifications']
        )


def lambda_handler(event, context):
    _CW = get_client()
    dashboard = generate_dashboard()

    try:
        _CW.put_dashboard(
            DashboardName=f'lambdas-monitoring-dashboard',
            DashboardBody=json.dumps(dashboard)
        )
        _logger.info(f"Dashboard lambdas-monitoring-dashboard updated. ")
    except Exception as e:
        _logger.error(f"Failed updating dashboard lambdas-monitoring-dashboard : {e}. ")

    try:
        generate_alarms()
        _logger.info(f"CloudWatch Alarms created successfully for dashboard lambdas-monitoring-dashboard. ")
    except Exception as e:
        _logger.error(f"Failed creating CloudWatch Alarms : {e}. ")


# if __name__ == '__main__':
#     lambda_handler(None, None)
