# sg_chaos_lambda.py
import os
import json
import time
import datetime
import boto3
import uuid

ec2 = boto3.client("ec2")
s3 = boto3.client("s3")
cloudwatch = boto3.client("cloudwatch")

STATE_BUCKET = os.environ.get("STATE_BUCKET")
TARGET_SG_ID = os.environ.get("TARGET_SG_ID")
CHAOS_DURATION = int(os.environ.get("CHAOS_DURATION_SECONDS", "60"))
METRIC_NAMESPACE = os.environ.get("METRIC_NAMESPACE", "ChaosMonkey")
METRIC_NAME = os.environ.get("METRIC_NAME", "ChaosEvent")

def create_backup():
    if not STATE_BUCKET or not TARGET_SG_ID:
        raise ValueError("STATE_BUCKET and TARGET_SG_ID must be set in environment variables")
    resp = ec2.describe_security_groups(GroupIds=[TARGET_SG_ID])
    sg = resp["SecurityGroups"][0]
    backup = {
        "backup_id": str(uuid.uuid4()),
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "sg_id": sg["GroupId"],
        "ip_permissions": sg.get("IpPermissions", []),
        "ip_permissions_egress": sg.get("IpPermissionsEgress", []),
    }
    key = f"sg-backups/{TARGET_SG_ID}-{backup['backup_id']}.json"
    s3.put_object(Bucket=STATE_BUCKET, Key=key, Body=json.dumps(backup).encode("utf-8"))
    return key

def restore_from_s3(key):
    obj = s3.get_object(Bucket=STATE_BUCKET, Key=key)
    backup = json.loads(obj["Body"].read())
    ip_perms = backup.get("ip_permissions", [])
    ip_perms_egress = backup.get("ip_permissions_egress", [])
    current = ec2.describe_security_groups(GroupIds=[TARGET_SG_ID])["SecurityGroups"][0]
    current_ingress = current.get("IpPermissions", [])
    if current_ingress:
        try:
            ec2.revoke_security_group_ingress(GroupId=TARGET_SG_ID, IpPermissions=current_ingress)
        except Exception as e:
            print(f"Warning while revoking current ingress: {e}")
    if ip_perms:
        try:
            ec2.authorize_security_group_ingress(GroupId=TARGET_SG_ID, IpPermissions=ip_perms)
        except Exception as e:
            print(f"Error restoring ingress: {e}")
    current_egress = current.get("IpPermissionsEgress", [])
    if current_egress:
        try:
            ec2.revoke_security_group_egress(GroupId=TARGET_SG_ID, IpPermissions=current_egress)
        except Exception as e:
            print(f"Warning while revoking current egress: {e}")
    if ip_perms_egress:
        try:
            ec2.authorize_security_group_egress(GroupId=TARGET_SG_ID, IpPermissions=ip_perms_egress)
        except Exception as e:
            print(f"Error restoring egress: {e}")
    return True

def publish_event_log(event_meta):
    key = f"logs/{TARGET_SG_ID}-{event_meta['event_id']}.json"
    s3.put_object(Bucket=STATE_BUCKET, Key=key, Body=json.dumps(event_meta).encode("utf-8"))
    print(f"Event logged at s3://{STATE_BUCKET}/{key}")

def push_metric(name, value, details=None):
    dims = []
    instance_id = os.environ.get("INSTANCE_ID")
    if instance_id:
        dims.append({"Name": "InstanceId", "Value": instance_id})
    cloudwatch.put_metric_data(
        Namespace=METRIC_NAMESPACE,
        MetricData=[{
            "MetricName": name,
            "Dimensions": dims,
            "Timestamp": int(time.time()),
            "Value": value,
            "Unit": "Count"
        }]
    )

def lambda_handler(event, context):
    print("Starting SG chaos event")
    # Validate env
    if not STATE_BUCKET or not TARGET_SG_ID:
        raise ValueError("STATE_BUCKET and TARGET_SG_ID must be set in environment variables")
    # 1. Create backup
    backup_key = create_backup()
    print(f"Backup saved: {backup_key}")

    event_id = str(uuid.uuid4())
    event_meta = {
        "event_id": event_id,
        "start_time": datetime.datetime.utcnow().isoformat(),
        "target_sg": TARGET_SG_ID,
        "chaos_duration_seconds": CHAOS_DURATION,
        "backup_key": backup_key,
        "status": "started"
    }
    publish_event_log(event_meta)
    push_metric("ChaosStarted", 1)

    # 2. Identify HTTP ingress rules to remove
    sg = ec2.describe_security_groups(GroupIds=[TARGET_SG_ID])["SecurityGroups"][0]
    ip_perms = sg.get("IpPermissions", [])
    rules_to_remove = []
    for perm in ip_perms:
        proto = perm.get("IpProtocol")
        from_port = perm.get("FromPort")
        to_port = perm.get("ToPort")
        if proto in ["tcp","6","-1", None]:
            if from_port is not None and to_port is not None and from_port <= 80 <= to_port:
                rules_to_remove.append(perm)

    if not rules_to_remove:
        print("No matching HTTP rule found to remove; marking event failed.")
        event_meta["status"] = "no_http_rule"
        event_meta["end_time"] = datetime.datetime.utcnow().isoformat()
        publish_event_log(event_meta)
        push_metric("ChaosNoRule", 1)
        return {"status": "no_rule"}

    # 3. Remove selected rules (revoke)
    try:
        ec2.revoke_security_group_ingress(GroupId=TARGET_SG_ID, IpPermissions=rules_to_remove)
        print("Revoked HTTP ingress rules.")
    except Exception as e:
        print(f"Error revoking ingress: {e}")
        event_meta["status"] = "revoke_failed"
        event_meta["error"] = str(e)
        event_meta["end_time"] = datetime.datetime.utcnow().isoformat()
        publish_event_log(event_meta)
        push_metric("ChaosRevokeFailed", 1)
        try:
            restore_from_s3(backup_key)
        except Exception as re:
            print("Immediate restore failed:", re)
        return {"status": "revoke_failed", "error": str(e)}

    # 4. Wait (chaos)
    print(f"Chaos active for {CHAOS_DURATION} seconds...")
    time.sleep(CHAOS_DURATION)

    # 5. Restore from backup
    try:
        restore_from_s3(backup_key)
        event_meta["status"] = "restored"
    except Exception as e:
        event_meta["status"] = "restore_failed"
        event_meta["error"] = str(e)
    event_meta["end_time"] = datetime.datetime.utcnow().isoformat()
    publish_event_log(event_meta)
    push_metric("ChaosRestored", 1)

    print("Chaos event completed.")
    return {"status": "done", "event_id": event_id}
