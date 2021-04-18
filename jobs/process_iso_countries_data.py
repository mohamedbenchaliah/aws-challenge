
import sys

from pyspark.context import SparkContext
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job


args = getResolvedOptions(sys.argv, ['JOB_NAME', 's3_output_path', 'database_name', 'table_name'])
s3_output_path = args['s3_output_path']
database_name = args['database_name']
table_name = args['table_name']


sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)


countries_dyf = glueContext.create_dynamic_frame\
    .from_catalog(database=database_name, table_name=table_name)

countries_dyf = ApplyMapping.apply(frame=countries_dyf, mappings=[
            ('English short name', 'string', 'english_short_name', 'string'),
            ('Alpha-2 code', 'string', 'alpha_2_code', 'string'),
            ('Alpha-3 code', 'string', 'alpha_3_code', 'string'),
            ('Numeric code', 'string', 'numeric_code', 'string'),
            ('ISO 3166-2', 'string', 'iso_3166_2', 'string'),
        ], transformation_ctx='applymapping1')

countries_df = countries_dyf.toDF()

countries_df.write\
    .format('parquet')\
    .mode('overwrite')\
    .save(s3_output_path)

job.commit()
