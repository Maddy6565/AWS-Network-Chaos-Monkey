# helpers.py
# Shared helpers: S3 put and CloudWatch metric helper.
import json, time, boto3
s3 = boto3.client("s3")
cloudwatch = boto3.client("cloudwatch")

def put_s3_json(bucket, key, obj):
    """Write JSON to S3. Returns s3://... path."""
    s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(obj, default=str).encode("utf-8"))
    return f"s3://{bucket}/{key}"

def push_metric(namespace, name, value):
    """Publish a simple CloudWatch metric (Count)."""
    cloudwatch.put_metric_data(
        Namespace=namespace,
        MetricData=[{"MetricName": name, "Timestamp": int(time.time()), "Value": value, "Unit": "Count"}]
    )
