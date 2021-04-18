
import sys

from pyspark.context import SparkContext

from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job


args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    's3_output_path',
    's3_openaq_data_path',
    's3_iso_countries_data_path'
])

s3_output_path = args['s3_output_path']
s3_openaq_data_path = args['s3_openaq_data_path']
s3_iso_countries_data_path = args['s3_iso_countries_data_path']


sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

openaq_df = \
    glueContext.\
    spark_session.\
    read.option("header", "true")\
        .load(s3_openaq_data_path, format="parquet")

# spark.read.schema(schema).format("parquet").load(root_path).filter(filter_string)

countries_df = \
    glueContext.\
    spark_session.\
    read.option("header", "true")\
        .load(s3_iso_countries_data_path, format="parquet")

# todo: drop non essential columns after the join
openaq_df\
    .join(countries_df, 'alpha_2_code', 'left')\
    .write \
    .format('parquet') \
    .option('header', 'false') \
    .mode('append') \
    .partitionBy("year", "month", "day") \
    .save(s3_output_path)

