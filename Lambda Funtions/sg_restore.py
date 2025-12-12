# sg_restore.py
# Simple lambda to restore the latest SG backup
import os, json, boto3
ec2 = boto3.client("ec2")
s3 = boto3.client("s3")

STATE_BUCKET = os.environ.get("STATE_BUCKET")
TARGET_SG_ID = os.environ.get("TARGET_SG_ID")

def find_latest_backup_key():
    resp = s3.list_objects_v2(Bucket=STATE_BUCKET, Prefix=f"sg-backups/{TARGET_SG_ID}-")
    if "Contents" not in resp:
        return None
    items = resp["Contents"]
    items.sort(key=lambda x: x["LastModified"], reverse=True)
    return items[0]["Key"]

def restore_from_key(key):
    obj = s3.get_object(Bucket=STATE_BUCKET, Key=key)
    backup = json.loads(obj["Body"].read())
    ip_perms = backup.get("ip_permissions", [])
    ip_perms_egress = backup.get("ip_permissions_egress", [])
    current = ec2.describe_security_groups(GroupIds=[TARGET_SG_ID])["SecurityGroups"][0]
    cur_ing = current.get("IpPermissions", [])
    if cur_ing:
        try:
            ec2.revoke_security_group_ingress(GroupId=TARGET_SG_ID, IpPermissions=cur_ing)
        except Exception as e:
            print("Warning revoke:", e)
    if ip_perms:
        ec2.authorize_security_group_ingress(GroupId=TARGET_SG_ID, IpPermissions=ip_perms)
    cur_eg = current.get("IpPermissionsEgress", [])
    if cur_eg:
        try:
            ec2.revoke_security_group_egress(GroupId=TARGET_SG_ID, IpPermissions=cur_eg)
        except Exception as e:
            print("Warning revoke egress:", e)
    if ip_perms_egress:
        ec2.authorize_security_group_egress(GroupId=TARGET_SG_ID, IpPermissions=ip_perms_egress)

def lambda_handler(event, context):
    key = find_latest_backup_key()
    if not key:
        return {"status": "no_backup_found"}
    restore_from_key(key)
    return {"status": "restored", "key": key}
