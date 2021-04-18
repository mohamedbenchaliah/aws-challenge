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
CREATE_S3_STACK=$(jq -r .CREATE_S3_STACK $VALUES)
UNIQUE_KEY="$(date +%s)"

export ARTIFACT_BUCKET_NAME=$(jq -r .ARTIFACT_BUCKET_NAME $VALUES)
export S3_STACK_NAME="s3-resources"
export S3_STACK_TEMPLATE="s3-resources.yaml"
export CREATE_S3_STACK=$(jq -r .CREATE_S3_STACK $VALUES)

## ----- Generate Parameters File ----- #

cat << EOF > config/s3artifacts-params.json
[
  {
    "ParameterKey": "ArtifactBucketName",
    "ParameterValue": "$ARTIFACT_BUCKET_NAME"
  }
]
EOF

## ----- Deploy stack ----- #


DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"


if $CREATE_S3_STACK
then
  echo "Creating stack..."
  STACK_ID=$( \
    aws cloudformation create-stack \
    --stack-name ${S3_STACK_NAME} \
    --template-body file://${DIR}/cloudformation/${S3_STACK_TEMPLATE} \
    --capabilities CAPABILITY_IAM \
    --parameters file://${DIR}/config/s3artifacts-params.json \
    --tags file://${DIR}/config/tags.json \
    | jq -r .StackId \
  )

  echo "Waiting on ${STACK_ID} create completion..."
  aws cloudformation wait stack-create-complete --stack-name ${STACK_ID}
  aws cloudformation describe-stacks --stack-name ${STACK_ID} | jq .Stacks[0].Outputs
fi