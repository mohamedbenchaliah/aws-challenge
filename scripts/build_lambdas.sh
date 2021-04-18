#!/bin/bash

set -euo pipefail


usage() { echo "Usage: $0 [-f <lambda-function-names>]" 1>&2; exit 1; }

while getopts ":f:" arg;
do
  case ${arg} in
    f)
      FUNCTION_NAME=${OPTARG}
      ;;
    *)
      usage
      ;;
  esac
done


cd "$(dirname "$0")" && cd ../

mkdir -p build
mkdir -p build/lambda
BUILD_FOLDER="$PWD/build"

ROOT_DIR=${PWD}
if [[ -z ${FUNCTION_NAME+x} ]]
then
  LAMBDAS=$(for path in $(ls -d  lambdas/*/handler.py); do basename $(dirname ${path}); done)
  function join_by { local IFS="$1"; shift; echo "$*"; }
  bash scripts/$(basename "$0") -f $(join_by , ${LAMBDAS})
fi

if [[ ! -z ${FUNCTION_NAME+x} ]]
then
  FUNCTION_NAMES=${FUNCTION_NAME//,/ }

  rm -rf "${BUILD_FOLDER}" && mkdir -p "${BUILD_FOLDER}"/lambda

  for function_name in ${FUNCTION_NAMES}
  do
    echo "Building artefact for job: ${function_name}..."

    cd lambdas/"${function_name}"

    files=$(ls | grep -v -e __init__.py -e __pycache__)
    if [[ -f "requirements.txt" ]]; then
        echo -e "[install]\nprefix=" > setup.cfg
        pip3 install -t $OLDPWD/package -r requirements.txt > /dev/null
        cp $files $OLDPWD/package/
        cp -r ../../sql $OLDPWD/package/
        cd $OLDPWD
        (cd package && zip -rq "${BUILD_FOLDER}"/lambda/"${function_name}".zip .)
        rm lambdas/"${function_name}"/setup.cfg
        rm -rf package
    fi

  done
fi

exit 0
