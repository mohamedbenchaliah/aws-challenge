#!/bin/bash

set -e



VALUES=
for i in "$@"
do
case ${i} in
	-values-file=*|--values-file=*)
    VALUES="${i#*=}"
    ;;
esac
done

if [ -z "$VALUES" ]
then
      echo "Please supply a json values file."
      exit 1
fi
# ----- Env variables ----- #

export ATHENA_RUNNER_STACK_NAME="athenarunner-lambda"
export ATHENA_RUNNER_STACK_TEMPLATE="athenarunner-lambda.yaml"
export ATHENA_RUNNER_LAMBDA_SOURCE_S3_KEY="src/athenarunner.zip"
export ATHENA_RUNNER_DDB_TABLE_NAME="AthenaRunnerActiveJobs"
export ATHENA_RUNNER_LAMBDA_FUNCTION_NAME="athenarunner"
export ARTIFACT_BUCKET_NAME=$(jq -r .ARTIFACT_BUCKET_NAME $VALUES)
export CREATE_ATHENA_RUNNER_STACK=$(jq -r .CREATE_ATHENA_RUNNER_STACK $VALUES)
export STACK_REGION=$(jq -r .STACK_REGION $VALUES)

## ----- Generate Parameters File ----- #

cat << EOF > config/athenarunner-params.json
[
  {
    "ParameterKey": "Region",
    "ParameterValue": "$STACK_REGION"
  },
  {
    "ParameterKey": "ArtifactBucketName",
    "ParameterValue": "$ARTIFACT_BUCKET_NAME"
  },
  {
    "ParameterKey": "LambdaSourceS3Key",
    "ParameterValue": "$ATHENA_RUNNER_LAMBDA_SOURCE_S3_KEY"
  },
  {
    "ParameterKey": "DDBTableName",
    "ParameterValue": "$ATHENA_RUNNER_DDB_TABLE_NAME"
  },
  {
    "ParameterKey": "AthenaRunnerLambdaFunctionName",
    "ParameterValue": "$ATHENA_RUNNER_LAMBDA_FUNCTION_NAME"
  }
]
EOF

## ----- Deploy Stack ----- #

DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"

if $CREATE_ATHENA_RUNNER_STACK
then
  echo "Creating stack..."
  STACK_ID=$( \
    aws cloudformation create-stack \
    --stack-name ${ATHENA_RUNNER_STACK_NAME} \
    --template-body file://${DIR}/cloudformation/${ATHENA_RUNNER_STACK_TEMPLATE} \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameters file://${DIR}/config/athenarunner-params.json \
    --tags file://${DIR}/config/tags.json \
    | jq -r .StackId \
  )

  echo "Waiting on ${STACK_ID} create completion..."
  aws cloudformation wait stack-create-complete --stack-name ${STACK_ID}
  aws cloudformation describe-stacks --stack-name ${STACK_ID} | jq .Stacks[0].Outputs
fi