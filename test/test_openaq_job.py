
# import pytest
import os
import sys
from typing import Tuple

from pyspark.sql import SparkSession
from awsglue.context import GlueContext
from jobs import process_openaq_data

here = os.path.dirname(os.path.join("..", os.path.abspath(__file__)))


def setup_test() -> Tuple[SparkSession, int]:
    jars = os.path.join(os.path.dirname(__file__), "jars")

    spark_session = SparkSession.builder \
        .appName("test_snapshot_ingestion_job") \
        .config("spark.driver.memory", "8g") \
        .config("spark.cores.max", "3") \
        .config("spark.driver.port", "36551") \
        .config("spark.jars", f"{jars}/AWSGlueETLPython-1.0.0.jar,") \
        .getOrCreate()

    sc = spark_session.sparkContext
    sc.setCheckpointDir(f"{here}/checkpoints")
    GlueContext(sc)

    job_run_id = 'jr1'
    return spark_session, job_run_id


def test_process(caplog):
    pass
