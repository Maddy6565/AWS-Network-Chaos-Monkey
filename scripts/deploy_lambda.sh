#!/usr/bin/env bash
# deploy_lambda.sh
# Usage:
#   ./scripts/deploy_lambda.sh <function-name> <source-py-file> <role-arn> [region]
# Example:
#   ./scripts/deploy_lambda.sh route_chaos lambda/route_chaos.py arn:aws:iam::123456789012:role/chaos-lambda-role us-east-1

set -euo pipefail

FN="$1"         # function name (eg route_chaos)
SRC="$2"        # source python file path (eg lambda/route_chaos.py)
ROLE_ARN="$3"   # IAM role ARN for lambda
REGION="${4:-us-east-1}"

ZIPFILE="/tmp/${FN}.zip"

# Clean
rm -f "$ZIPFILE"

# Package: include source and helpers
zip -j "$ZIPFILE" "$SRC" "lambda/helpers.py"

# Deploy: create or update
if aws lambda get-function --function-name "$FN" --region "$REGION" >/dev/null 2>&1; then
  echo "Updating existing Lambda: $FN"
  aws lambda update-function-code --function-name "$FN" --zip-file "fileb://$ZIPFILE" --region "$REGION"
else
  echo "Creating Lambda: $FN"
  aws lambda create-function \
    --function-name "$FN" \
    --runtime python3.11 \
    --handler "$(basename "$SRC" .py).lambda_handler" \
    --zip-file "fileb://$ZIPFILE" \
    --role "$ROLE_ARN" \
    --timeout 300 \
    --memory-size 256 \
    --region "$REGION"
fi

echo "Deployed $FN"
