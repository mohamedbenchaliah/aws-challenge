#!/bin/bash

set -euo pipefail


ARTEFACT_BUCKET=$ARTIFACT_BUCKET_NAME
BUILDS_FOLDER="$PWD/build/layer"


echo "Uploading layer to s3..."
aws s3 cp ${BUILDS_FOLDER}/awswrangler-layer-2.6.0-py3.7.zip s3://${ARTEFACT_BUCKET}/src/


#aws lambda publish-layer-version \
#    --layer-name aws-wrangler \
#    --description "aws-wrangler layer" \
#    --compatible-runtimes python3.7 \
#    --content S3Bucket=${ARTEFACT_BUCKET},S3Key=src/awswrangler-layer-2.6.0-py3.7.zip
