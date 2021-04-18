import pytest
from moto import mock_s3, mock_logs

import boto3


@pytest.fixture
def artifact_s3_bucket():
    with mock_s3():
        boto3.client('s3').create_bucket(Bucket='test-bucket')
        yield boto3.resource('s3').Bucket('artifact-bucket')


@pytest.fixture
def data_s3_bucket():
    with mock_s3():
        boto3.client('s3').create_bucket(Bucket='test-bucket')
        yield boto3.resource('s3').Bucket('data-bucket')


@pytest.skip("test in progress")
@pytest.fixture
def cw_client():
    with mock_logs():
        yield boto3.client('logs')
