
import sys

from pyspark.context import SparkContext
from pyspark.sql.types import DoubleType
from pyspark.sql.functions import col, year, month, dayofmonth

from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame


args = getResolvedOptions(sys.argv, ['JOB_NAME', 's3_output_path', 'database_name', 'table_name'])
s3_output_path = args['s3_output_path']
database_name = args['database_name']
table_name = args['table_name']

sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)


datasource0 = glueContext.create_dynamic_frame\
                .from_catalog(database=database_name, table_name=table_name, transformation_ctx="datasource0")


applymapping1 = ApplyMapping.apply(
    frame=datasource0,
    mappings=[
            ('location', 'string', 'location', 'string'),
            ('city', 'string', 'city', 'string'),
            ('country', 'string', 'alpha_2_code', 'string'),
            ('utc', 'timestamp', 'utc', 'timestamp'),
            ('local', 'timestamp', 'local', 'timestamp'),
            ('parameter', 'string', 'parameter', 'string'),
            ('value', 'double', 'value', 'double'),
            ('unit', 'string', 'unit', 'string'),
            ('latitude', 'double', 'latitude', 'double'),
            ('longitude', 'double', 'longitude', 'double'),
            ('attribution', 'array', 'attribution', 'array'),
        ], transformation_ctx='applymapping1'
   )


resolvechoice2 = ResolveChoice.apply(
    frame=applymapping1,
    choice="make_struct",
    transformation_ctx="resolvechoice2")

partitioned_dataframe = resolvechoice2.toDF().repartition(1)

partitioned_dataframe = partitioned_dataframe.withColumn("year", year(col("local"))) \
        .withColumn("month", month(col("local"))) \
        .withColumn("day", dayofmonth(col("local"))) \
        .withColumn("valueTmp", col("value").cast(DoubleType())) \
        .drop("value").withColumnRenamed("valueTmp", "value") \
        .withColumnRenamed("local", "local_time")\
        .drop(*['utc', 'location']) \
        .filter(col("value") <= 0) \
        .filter(~partitioned_dataframe.parameter.isin(["pm25", "co", "so2"])) \
        .repartition(1)


partitioned_dynamicframe = DynamicFrame.fromDF(partitioned_dataframe, glueContext, "partitioned_df")

datasink4 = glueContext.write_dynamic_frame.from_options(
    frame=partitioned_dynamicframe,
    connection_type="s3",
    connection_options={
        "path": s3_output_path,
        "groupFiles": "inPartition",
        "mode": "append",
        "partitionKeys": ["year", "month", "day"]
    },
    format="parquet",
    transformation_ctx="datasink4")

job.commit()





