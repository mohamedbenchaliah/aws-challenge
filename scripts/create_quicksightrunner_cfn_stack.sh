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

export QUICKSIGHT_RUNNER_STACK_NAME="quicksightrunner-lambda"
export QUICKSIGHT_RUNNER_STACK_TEMPLATE="quicksightrunner-lambda.yaml"
export QUICKSIGHT_RUNNER_LAMBDA_SOURCE_S3_KEY="src/quicksightrunner.zip"
export QUICKSIGHT_RUNNER_LAMBDA_FUNCTION_NAME="quicksightrunner"
export CREATE_QUICKSIGHT_RUNNER_STACK=$(jq -r .CREATE_QUICKSIGHT_RUNNER_STACK $VALUES)
export ARTIFACT_BUCKET_NAME=$(jq -r .ARTIFACT_BUCKET_NAME $VALUES)
export STACK_REGION=$(jq -r .STACK_REGION $VALUES)


## ----- Generate Parameters File ----- #

cat << EOF > config/quicksightrrunner-params.json
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
    "ParameterValue": "$QUICKSIGHT_RUNNER_LAMBDA_SOURCE_S3_KEY"
  },
  {
    "ParameterKey": "QuickSightsRunnerLambdaFunctionName",
    "ParameterValue": "$QUICKSIGHT_RUNNER_LAMBDA_FUNCTION_NAME"
  }
]
EOF

## ----- Deploy Stack ----- #

DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"

if $CREATE_QUICKSIGHT_RUNNER_STACK
then
  echo "Creating stack..."
  STACK_ID=$( \
    aws cloudformation create-stack \
    --stack-name ${QUICKSIGHT_RUNNER_STACK_NAME} \
    --template-body file://${DIR}/cloudformation/${QUICKSIGHT_RUNNER_STACK_TEMPLATE} \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameters file://${DIR}/config/quicksightrrunner-params.json \
    --tags file://${DIR}/config/tags.json \
    | jq -r .StackId \
  )

  echo "Waiting on ${STACK_ID} create completion..."
  aws cloudformation wait stack-create-complete --stack-name ${STACK_ID}
  aws cloudformation describe-stacks --stack-name ${STACK_ID} | jq .Stacks[0].Outputs
fi