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

export GLUE_RESOURCES_STACK_NAME="glue-resources"
export GLUE_RESOURCES_STACK_TEMPLATE="glue-resources.yaml"
export GLUE_RESOURCES_ETL_SCRIPTS_PREFIX="scripts"
export GLUE_RESOURCES_ETL_OUTPUT_PREFIX="output"
export CREATE_GLUE_RESOURCES_STACK=$(jq -r .CREATE_GLUE_RESOURCES_STACK $VALUES)
export DATA_BUCKET_NAME=$(jq -r .DATA_BUCKET_NAME $VALUES)
export ARTIFACT_BUCKET_NAME=$(jq -r .ARTIFACT_BUCKET_NAME $VALUES)


## ----- Generate Parameters File ----- #

cat << EOF > config/glueresources-params.json
[
  {
    "ParameterKey": "ArtifactBucketName",
    "ParameterValue": "$ARTIFACT_BUCKET_NAME"
  },
  {
    "ParameterKey": "ETLScriptsPrefix",
    "ParameterValue": "$GLUE_RESOURCES_ETL_SCRIPTS_PREFIX"
  },
  {
    "ParameterKey": "DataBucketName",
    "ParameterValue": "$DATA_BUCKET_NAME"
  },
  {
    "ParameterKey": "ETLOutputPrefix",
    "ParameterValue": "$GLUE_RESOURCES_ETL_OUTPUT_PREFIX"
  }
]
EOF

## ----- Deploy Stack ----- #

DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"

if $CREATE_GLUE_RESOURCES_STACK
then
  echo "Creating stack..."
  STACK_ID=$( \
    aws cloudformation create-stack \
    --stack-name ${GLUE_RESOURCES_STACK_NAME} \
    --template-body file://${DIR}/cloudformation/${GLUE_RESOURCES_STACK_TEMPLATE} \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameters file://${DIR}/config/glueresources-params.json \
    --tags file://${DIR}/config/tags.json \
    | jq -r .StackId \
  )

  echo "Waiting on ${STACK_ID} create completion..."
  aws cloudformation wait stack-create-complete --stack-name ${STACK_ID}
  aws cloudformation describe-stacks --stack-name ${STACK_ID} | jq .Stacks[0].Outputs
fi