# sg_backup.py
# Lambda to snapshot a security group's rules and store in S3.
import os, json, datetime, uuid, boto3
from helpers import put_s3_json

ec2 = boto3.client("ec2")
STATE_BUCKET = os.environ.get("STATE_BUCKET")
TARGET_SG_ID = os.environ.get("TARGET_SG_ID")

def lambda_handler(event, context):
    if not STATE_BUCKET or not TARGET_SG_ID:
        raise ValueError("STATE_BUCKET and TARGET_SG_ID must be set")
    resp = ec2.describe_security_groups(GroupIds=[TARGET_SG_ID])
    sg = resp["SecurityGroups"][0]
    backup = {
        "backup_id": str(uuid.uuid4()),
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "sg_id": sg["GroupId"],
        "ip_permissions": sg.get("IpPermissions", []),
        "ip_permissions_egress": sg.get("IpPermissionsEgress", []),
        "raw": sg
    }
    key = f"sg-backups/{TARGET_SG_ID}-{backup['backup_id']}.json"
    put_s3_json(STATE_BUCKET, key, backup)
    return {"status":"ok", "s3_key": key}
