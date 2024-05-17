#!/bin/bash

# Set the path to the directory containing the Dockerfile and app.py
LAMBDA_FUNCTION_DIR="functions/hermes_profiler"

# Build the Docker image for the Lambda function
docker build -t lambda-function-test -f "${LAMBDA_FUNCTION_DIR}/Dockerfile" "${LAMBDA_FUNCTION_DIR}"

# Create a virtual environment for tests
python -m venv test_venv

# Activate the test virtual environment
source test_venv/bin/activate

# Install the test dependencies
pip install -r tests/requirements.txt

# Run the unittests inside the Docker container
docker run --rm -v "$(pwd)/tests:/var/task/tests" lambda-function-test python -m unittest discover tests/

# Deactivate the test virtual environment
deactivate