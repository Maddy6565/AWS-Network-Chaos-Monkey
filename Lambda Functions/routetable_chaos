import os
import json
import boto3
import datetime

s3 = boto3.client("s3")
ec2 = boto3.client("ec2")

STATE_BUCKET = os.environ["STATE_BUCKET"]
TARGET_SG_ID = os.environ["TARGET_SG_ID"]

def find_latest_backup_key():
    resp = s3.list_objects_v2(Bucket=STATE_BUCKET, Prefix=f"sg-backups/{TARGET_SG_ID}-")
    if "Contents" not in resp:
        return None
    # find newest by LastModified
    items = resp["Contents"]
    items.sort(key=lambda x: x["LastModified"], reverse=True)
    return items[0]["Key"]

def restore_from_key(key):
    obj = s3.get_object(Bucket=STATE_BUCKET, Key=key)
    backup = json.loads(obj["Body"].read())
    ip_perms = backup.get("ip_permissions", [])
    ip_perms_egress = backup.get("ip_permissions_egress", [])
    # Revoke all current then reapply
    current = ec2.describe_security_groups(GroupIds=[TARGET_SG_ID])["SecurityGroups"][0]
    current_ingress = current.get("IpPermissions", [])
    if current_ingress:
        try:
            ec2.revoke_security_group_ingress(GroupId=TARGET_SG_ID, IpPermissions=current_ingress)
        except Exception as e:
            print("Warning revoke:", e)
    if ip_perms:
        ec2.authorize_security_group_ingress(GroupId=TARGET_SG_ID, IpPermissions=ip_perms)
    current_egress = current.get("IpPermissionsEgress", [])
    if current_egress:
        try:
            ec2.revoke_security_group_egress(GroupId=TARGET_SG_ID, IpPermissions=current_egress)
        except Exception as e:
            print("Warning revoke egress:", e)
    if ip_perms_egress:
        ec2.authorize_security_group_egress(GroupId=TARGET_SG_ID, IpPermissions=ip_perms_egress)
    return True

def lambda_handler(event, context):
    key = find_latest_backup_key()
    if not key:
        return {"status": "no_backup_found"}
    restore_from_key(key)
    return {"status": "restored", "key": key}
