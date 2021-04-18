#!/bin/bash

set -euo pipefail

usage() { echo "Usage: $0 -f <lambda-function-names> [-b <artefact bucket name>]" 1>&2; exit 1; }

while getopts ":f:b:" arg;
do
  case ${arg} in
    f)
      FUNCTION_NAME=${OPTARG}
      export FUNCTION_NAME
      ;;
    b)
      ARTEFACT_BUCKET=${OPTARG}
      export ARTEFACT_BUCKET
      ;;
    *) usage ;;
  esac
done

cd $(dirname "$0") && cd ../
BUILDS_FOLDER="$PWD/build/lambda"

if [[ -z ${ARTEFACT_BUCKET+x} ]]
then
    ARTEFACT_BUCKET=$ARTIFACT_BUCKET_NAME
fi

if [[ -z ${FUNCTION_NAME+x} ]]
then
  LAMBDAS=$(for path in $(ls -d  lambdas/*/handler.py); do basename $(dirname ${path}); done)
  function join_by { local IFS="$1"; shift; echo "$*"; }
  bash scripts/$(basename "$0") -f $(join_by , ${LAMBDAS})
fi

if [[ ! -z ${FUNCTION_NAME+x} ]]
then
  FUNCTION_NAMES=${FUNCTION_NAME//,/ }

  for f in ${FUNCTION_NAMES}
  do
    echo "Uploading artefact : ${f}..."
    aws s3 cp ${BUILDS_FOLDER}/${f}.zip s3://${ARTEFACT_BUCKET}/src/
  done
fi

exit 0
