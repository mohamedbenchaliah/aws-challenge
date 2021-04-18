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

q1=$(cat sql/vw_v100_query1.sql)
q2=$(cat sql/vw_v100_query2.sql)
q3=$(cat sql/vw_v100_query3.sql)
q4=$(cat sql/vw_v100_query4.sql)

export VIEW1_CONTENT=$(echo  $q1|tr -s '\n' ' ')
export VIEW2_CONTENT=$(echo  $q2|tr -s '\n' ' ')
export VIEW3_CONTENT=$(echo  $q3|tr -s '\n' ' ')
export VIEW4_CONTENT=$(echo  $q4|tr -s '\n' ' ')
export SFN_STACK_NAME="step-functions-resources"
export SFN_STACK_TEMPLATE="step-functions-resources.yaml"
export SFN_LAMBDA_SOURCE_S3_KEY="src/s3object.zip"
export SFN_ACTIVITY_NAME="GlueRunnerActivity"
export DATA_BUCKET_NAME=$(jq -r .DATA_BUCKET_NAME $VALUES)
export ARTIFACT_BUCKET_NAME=$(jq -r .ARTIFACT_BUCKET_NAME $VALUES)
export CREATE_SFN_STACK=$(jq -r .CREATE_SFN_STACK $VALUES)
export STACK_REGION=$(jq -r .STACK_REGION $VALUES)


## ----- Generate Parameters File ----- #

cat << EOF > config/sfn-params.json
[
  {
    "ParameterKey": "CreateView1",
    "ParameterValue": "$VIEW1_CONTENT"
  },
  {
    "ParameterKey": "CreateView2",
    "ParameterValue": "$VIEW2_CONTENT"
  },
  {
    "ParameterKey": "CreateView3",
    "ParameterValue": "$VIEW3_CONTENT"
  },
  {
    "ParameterKey": "CreateView4",
    "ParameterValue": "$VIEW4_CONTENT"
  },
  {
    "ParameterKey": "ArtifactBucketName",
    "ParameterValue": "$ARTIFACT_BUCKET_NAME"
  },
  {
    "ParameterKey": "GlueRunnerActivityName",
    "ParameterValue": "$SFN_ACTIVITY_NAME"
  },
  {
    "ParameterKey": "DataBucketName",
    "ParameterValue": "$DATA_BUCKET_NAME"
  },
  {
    "ParameterKey": "LambdaSourceS3Key",
    "ParameterValue": "src/s3object.zip"
  },
  {
    "ParameterKey": "Region",
    "ParameterValue": "$STACK_REGION"
  }
]
EOF

## ----- Deploy Stack ----- #

DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"

if $CREATE_SFN_STACK
then
  echo "Creating stack..."
  STACK_ID=$( \
    aws cloudformation create-stack \
    --stack-name ${SFN_STACK_NAME} \
    --template-body file://${DIR}/cloudformation/${SFN_STACK_TEMPLATE} \
    --capabilities CAPABILITY_IAM \
    --parameters file://${DIR}/config/sfn-params.json \
    --tags file://${DIR}/config/tags.json \
    | jq -r .StackId \
  )

  echo "Waiting on ${STACK_ID} create completion..."
  aws cloudformation wait stack-create-complete --stack-name ${STACK_ID}
  aws cloudformation describe-stacks --stack-name ${STACK_ID} | jq .Stacks[0].Outputs
fi