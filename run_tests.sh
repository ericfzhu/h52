#!/bin/bash

# Set the path to the directory containing the Dockerfile and app.py
LAMBDA_FUNCTION_DIR="functions/hermes_profiler"

# Build the Docker image for the Lambda function
docker build -t lambda-function-test -f "${LAMBDA_FUNCTION_DIR}/Dockerfile" "${LAMBDA_FUNCTION_DIR}"

# Run the unittests inside the Docker container
docker run --rm \
  -v "$(pwd)/tests:/var/task/tests" \
  -v "$(pwd)/functions:/var/task/functions" \
  -v "$(pwd)/tests/requirements.txt:/var/task/requirements.txt" \
  -e AWS_DEFAULT_REGION='us-west-2' \
  --entrypoint "" \
  lambda-function-test /bin/bash -c "pip install -r /var/task/requirements.txt && python -m unittest discover tests/"