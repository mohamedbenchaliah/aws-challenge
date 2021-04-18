Open Air Quality Challenge
==========================


## High Level Design

The solution suggested has the components described below :

* `S3DataBucket` - Bucket hosting raw and curated data
* `S3ArtifactsBucket` - Bucket hosting artifacts for lambda deployments and glue jobs, in addition to additional jars
* `Lambda functions` - responsible for running and tiggering the end 2 end pipeline :
    * `s3objects` -  waits for new raw data created in `S3DataBucket`
    * `GlueRunner` -  triggers 4 glue jobs `process_openaq_data.py` `process_iso_countries_data.py` `process_openaq_Incoherent_data.py` `join_openaq_and_iso_countries_data.py` 
    * `AthenaRunner` -  triggers Athena to create the database (+tables) `openaq_db`
    * `CrawlerRunner` -  triggers parquet crawler to update curated table in Catalog
    * `QuickSightRunner` -  Create QuickSignts Data source pointing to athena DB `openaq_db` and datasets pointing to 4 views `query1` `query2` `query3` `query4`
    
* `Glue Jobs` - 4 pyspark / glue jobs to process data and track incohernce `process_openaq_data.py` `process_iso_countries_data.py` `process_openaq_Incoherent_data.py` `join_openaq_and_iso_countries_data.py` 
* `Glue Metastore` - Contains one database  `openaq_db`
* `Athena` - Contains one database  `openaq_db`, 4 tables and 4 views (one for each question in the use case)
* `DynamoDB` - Used by lambda functions to track the state of the jobs
* `StepFunction State Machine` - to orchestrate the end 2 end pipelines

![High Level Architecture](resources/high-level-design.png?raw=true "High Level Architecture")


## Deploy the environment

This section list configuration files, parameters and default values. The build commands (detailed later) and CloudFormation templates extract their parameters from these files. Also, the  Glue Runner AWS Lambda function extract parameters at runtime from `gluerunner-config.json`.

```json
{
    "CREATE_S3_STACK": true,
    "DEPLOY_LAMBDA_ARTIFACTS": true,
    "UPLOAD_GLUE_SCRIPTS": true,
    "CREATE_SFN_STACK": true,
    "CREATE_GLUE_RESOURCES_STACK": true,
    "CREATE_GLUE_RUNNER_STACK": true,
    "CREATE_ATHENA_RUNNER_STACK": true,
    "CREATE_CRAWLER_RUNNER_STACK": true,
    "CREATE_QUICKSIGHT_RUNNER_STACK": true,
    "ARTIFACT_BUCKET_NAME": "aws-test-artifact-bucket",
    "DATA_BUCKET_NAME": "aws-test-data-bucket",
    "STACK_REGION": "eu-west-1",
    "LAMBDA_FUNC_ROLE_ARN": ""
}
```

>**NOTE: Set values to `true` or `false` to activate or deactivate a specific cloudformation stack creation.**


1. Deploy CloudFormation template `cloudformation/s3-resources.yaml` to deploy Artifacts bucket, 
   by running the command : 

```bash
./scripts/create_s3_resources_cfn_stack.sh --values-file=config/infra-values.json
```

This script will output a config file `s3artifacts-params.json` : 

```json
[
  {
    "ParameterKey": "ArtifactBucketName",
    "ParameterValue": "aws-test-artifact-bucket-XXXXXXXXXXX"
  }
]
```

2. Build and Upload Lambda functions by running :  

```bash
export ARTIFACT_BUCKET_NAME=aws-test-artifact-bucket-2021041717 && ./scripts/build_lambdas.sh && ./scripts/upload_lambdas.sh
```

3. Upload Glue Jobs to the Artifacts Bucket by running :  

```bash
export GLUE_RESOURCES_ETL_SCRIPTS_PREFIX=scripts
aws s3 cp \
    jobs/ \
    s3://$ARTIFACT_BUCKET_NAME/$GLUE_RESOURCES_ETL_SCRIPTS_PREFIX \
    --recursive \
    --exclude "*.pyc" \
    --exclude "__init__py" \
    --include "*_data.py"
```

3. Create Step Functions stack by running :  

```bash
./scripts/create_sfn_resources_cfn_stack.sh --values-file=config/infra-values.json
```

This script will output a config file `sfn-params.json` : 

```json
[
  {
    "ParameterKey": "CreateView1",
    "ParameterValue": "create or replace view query_1 as WITH base_query as ( SELECT city, local_time, year, month, day, max(if(parameter='co', if(unit='µg/m³', value*0.000873, value), 0)) AS co, max(if(parameter='so2', if(unit='µg/m³', value*0.000382, value), 0)) AS so2, max(if(parameter='pm25', value, 0)) AS pm25 FROM ${GlueTableName} GROUP BY 1,2,3,4,5 ORDER BY max(if(parameter='pm25', value, 0)) DESC ), avg_query AS ( SELECT city, year, month, avg(co) AS co_avg, avg(so2) AS so_avg FROM base_query GROUP BY 1,2,3 ) SELECT city, year, month, co_avg, so_avg FROM avg_query GROUP BY 1,2,3,4,5 having co_avg >= approx_percentile(co_avg,0.9) and so_avg >= approx_percentile(so_avg,0.9) order by 4 desc,5 desc "
  },
  {
    "ParameterKey": "CreateView2",
    "ParameterValue": "create or replace view query_2 as WITH base_query as ( SELECT city, local_time, year, month, day, max(if(parameter='co', if(unit='µg/m³', value*0.000873, value), 0)) AS co, max(if(parameter='so2', if(unit='µg/m³', value*0.000382, value), 0)) AS so2, max(if(parameter='pm25', value, 0)) AS pm25 FROM ${GlueTableName} GROUP BY 1,2,3,4,5 ORDER BY max(if(parameter='pm25', value, 0)) DESC ), top5_cities as ( select city, year, month, day, avg(pm25) as pm25_avg, rank() over (partition by year, month, day order by avg(pm25) desc) as rank from base_query group by 1,2,3,4 order by 5 desc ) select city, year, month, day, pm25_avg from top5_cities where rank <= 5 order by day "
  },
  {
    "ParameterKey": "CreateView3",
    "ParameterValue": "create or replace view query_3 as with base_query as ( SELECT city, from_iso8601_timestamp(local_time) as date, year, month, day, max(if(parameter='co', if(unit='µg/m³', value*0.000873, value), 0)) AS co, max(if(parameter='so2', if(unit='µg/m³', value*0.000382, value), 0)) AS so2, max(if(parameter='pm25', value, 0)) AS pm25 FROM ${GlueTableName} GROUP BY 1,2,3,4,5 ORDER BY max(if(parameter='pm25', value, 0)) DESC ), high_hourly_avg as ( select city, year, month, day, pm25_avg from ( select city, year, month, day, avg(pm25) as pm25_avg, rank() over (partition by year, month, day, extract(hour from date) order by avg(pm25) desc) as rank from base_query group by 1,2,3,4, extract(hour from date) order by 5 desc ) where rank <= 10 ) select b.city, b.year, b.month, b.day, avg(b.so2) AS mean_so2, avg(b.co) AS mean_co, count(distinct b.co) AS mode_co, count(distinct b.so2) AS mode_so2, approx_percentile(b.so2,0.5) AS median_so2, approx_percentile(b.co,0.5) AS median_co from base_query b inner join high_hourly_avg h on h.city = b.city and h.year=b.year and h.month= b.month and h.day=b.day group by 1,2,3,4 "
  },
  {
    "ParameterKey": "CreateView4",
    "ParameterValue": "create or replace view query_4 as WITH base_query as ( SELECT english_short_name as country, from_iso8601_timestamp(local_time) as date, year, month, day, max(if(parameter='co', if(unit='µg/m³', value*0.000873, value), 0)) AS co, max(if(parameter='so2', if(unit='µg/m³', value*0.000382, value), 0)) AS so2, max(if(parameter='pm25', value, 0)) AS pm25 FROM ${GlueTableName} GROUP BY 1,2,3,4,5 ORDER BY max(if(parameter='pm25', value, 0)) DESC ), IndexGrid AS ( select 1 as level, 15 as pm25, 4 as co, 0.02 as so2 union select 2 as level, 30 as pm25, 6 as co, 0.06 as so2 union select 3 as level, 55 as pm25, 8 as co, 0.12 as so2 ), IndexStatus AS ( SELECT 1 AS level, 'LOW' AS status UNION SELECT 2 AS level, 'MEDIUM' AS status UNION SELECT 3 AS level, 'HIGH' AS status ) SELECT country, extract(hour from date) as hour, year, month, day, qr.co, qr.so2, qr.pm25, status, MAX(index.level) as index FROM IndexGrid index JOIN base_query qr on 1=1 JOIN IndexStatus qi on index.level = qi.level WHERE index.pm25 < qr.pm25 OR index.co < qr.co OR index.so2 < qr.so2 group by 1,2,3,4,5,6,7,8,9 order by index desc --todo : fix US Diplomatic Post: Pristina join code "
  },
  {
    "ParameterKey": "ArtifactBucketName",
    "ParameterValue": "aws-test-artifact-bucket-XXXXXXXXXX"
  },
  {
    "ParameterKey": "GlueRunnerActivityName",
    "ParameterValue": "GlueRunnerActivity"
  },
  {
    "ParameterKey": "DataBucketName",
    "ParameterValue": "aws-test-data-bucket-XXXXXXXXXX"
  }
]
```

>**NOTE: 4 queries are red from the folder `/sql` and passed to CloudFormation as parameters to be deployed into the state machine.**

>**TODO : Automate the generate of the state machine configuration for every new SQL script created in the folder `/sql`.**

4. Create Glue resources stack by running :  

```bash
./scripts/create_glue_resources_cfn_stack.sh --values-file=config/infra-values.json
```

This script will output a config file `glueresources-params.json` : 

```json
[
  {
    "ParameterKey": "ArtifactBucketName",
    "ParameterValue": "aws-test-artifact-bucket-XXXXXXXXX"
  },
  {
    "ParameterKey": "ETLScriptsPrefix",
    "ParameterValue": "scripts"
  },
  {
    "ParameterKey": "DataBucketName",
    "ParameterValue": "aws-test-data-bucket-XXXXXXXXX"
  },
  {
    "ParameterKey": "ETLOutputPrefix",
    "ParameterValue": "output"
  }
]
```

5. Create Glue runner stack by running :  

```bash
./scripts/create_gluerunner_cfn_stack.sh --values-file=config/infra-values.json
```

This script will output a config file `gluerunner-params.json` : 

```json
[
  {
    "ParameterKey": "Region",
    "ParameterValue": "eu-west-1"
  },
  {
    "ParameterKey": "ArtifactBucketName",
    "ParameterValue": "aws-test-artifact-bucket-XXXXXXXX"
  },
  {
    "ParameterKey": "LambdaSourceS3Key",
    "ParameterValue": "src/gluerunner.zip"
  },
  {
    "ParameterKey": "DDBTableName",
    "ParameterValue": "GlueRunnerActiveJobs"
  },
  {
    "ParameterKey": "GlueRunnerLambdaFunctionName",
    "ParameterValue": "gluerunner"
  }
]
```


6. Create Parquet Crawler runner stack by running :  

```bash
./scripts/create_crawlerrunner_cfn_stack.sh --values-file=config/infra-values.json
```

This script will output a config file `crawlerrunner-params.json` : 

```json
[
  {
    "ParameterKey": "Region",
    "ParameterValue": "eu-west-1"
  },
  {
    "ParameterKey": "ArtifactBucketName",
    "ParameterValue": "aws-test-artifact-bucket-XXXXXXXXX"
  },
  {
    "ParameterKey": "LambdaSourceS3Key",
    "ParameterValue": "src/crawlerrunner.zip"
  },
  {
    "ParameterKey": "CrawlerRunnerLambdaFunctionName",
    "ParameterValue": "crawlerrunner"
  }
]
```

7. Create Athena runner stack by running :  

```bash
./scripts/create_athenarunner_cfn_stack.sh --values-file=config/infra-values.json
```

This script will output a config file `athenarunner-params.json` : 

```json
[
  {
    "ParameterKey": "Region",
    "ParameterValue": "eu-west-1"
  },
  {
    "ParameterKey": "ArtifactBucketName",
    "ParameterValue": "aws-test-artifact-bucket-XXXXXXXX"
  },
  {
    "ParameterKey": "LambdaSourceS3Key",
    "ParameterValue": "src/athenarunner.zip"
  },
  {
    "ParameterKey": "DDBTableName",
    "ParameterValue": "AthenaRunnerActiveJobs"
  },
  {
    "ParameterKey": "AthenaRunnerLambdaFunctionName",
    "ParameterValue": "athenarunner"
  }
]
```

8. Create Quicksights runner stack by running :  

```bash
./scripts/create_quicksightrunner_cfn_stack.sh --values-file=config/infra-values.json
```

This script will output a config file `quicksightrrunner-params.json` : 

```json
[
  {
    "ParameterKey": "Region",
    "ParameterValue": "eu-west-1"
  },
  {
    "ParameterKey": "ArtifactBucketName",
    "ParameterValue": "aws-test-artifact-bucket-XXXXXXXXX"
  },
  {
    "ParameterKey": "LambdaSourceS3Key",
    "ParameterValue": "src/crawlerrunner.zip"
  },
  {
    "ParameterKey": "CrawlerRunnerLambdaFunctionName",
    "ParameterValue": "crawlerrunner"
  }
]
```

9. Upload data to s3 partition from the URL :

```bash
wget -qO- https://openaq-data.s3.amazonaws.com/2018-04-06.csv | aws s3 cp - s3://aws-test-data-bucket-2021041717/2018/04/06/openaq.csv
```


## Orchestration

The deployment will create the configuration bellow : 

![stepfunctions-workflow](resources/stepfunctions-flow.png?raw=true "stepfunctions-workflow")

>**TODO : Need to add a csv crawler runner to run each time `s3objects function` is triggered to add new location in Glue Metastore.**


## End to end Data Flow

The end to end orchestration pipeline listens to new event triggered by a new csv file created in s3 data bucket.
The state machine is then triggered ro run 3 Glue jobs : `process_openaq_data.py` `process_iso_countries_data.py` `process_openaq_Incoherent_data.py`
`process_iso_countries_data.py` job is used to mac country codes into an english iso full name. 
This is stored and a parquet file to be used / upgraded as a dimension to the fact table.

![end-to-end-dataflow](resources/e2e-flow.png?raw=true "end-to-end-dataflow")

Once these 3 jobs end successfully and the parquet crawler updated the metastore, a fourth job starts to curate the end data `join_openaq_and_iso_countries_data.py`

## Prepare the analytics environment

In order to give the end user a full analytics experience, the solution suggested allow the access to the curated parquet files through Athena to run custom SQL queries,
and through QuickSights datasets to build reports using Athena Tables / Views.
For this specific use case, we have made available many tables in Athena (ingestion and curated tables) and 4 views, one view for each question.
Below a demo output of the views executed : 

![view1](resources/view1.png?raw=true "view1")

![view2](resources/view2.png?raw=true "view2")

![view3](resources/view3.png?raw=true "view3")

![view4](resources/view4.png?raw=true "view4")


## Pipeline Enhancement 

Due to time, I didn't have time to fix few remaining bugs and add capabilities : 
- trigger Glue job to read from a specific partition : GlueRunner lambda should pass the partition day to Glue Jobs as parameter.
- Some Data types need to be fixed and unneeded columns to be dropped.
- Fix QuickSight Runner Deployment : The function unzipped size exceeds 250 mb >> workaround : use dependencies as a lambda layer and attach it to `quicksightrunner` function
