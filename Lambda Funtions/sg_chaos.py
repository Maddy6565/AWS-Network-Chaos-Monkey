# sg_chaos.py
# Lambda: remove public HTTP/HTTPS ingress (0.0.0.0/0) then restore after a wait.
import os, json, time, datetime, uuid, boto3
from helpers import put_s3_json, push_metric

ec2 = boto3.client("ec2")
s3 = boto3.client("s3")

STATE_BUCKET = os.environ.get("STATE_BUCKET")
TARGET_SG_ID = os.environ.get("TARGET_SG_ID")
CHAOS_DURATION = int(os.environ.get("CHAOS_DURATION_SECONDS", "30"))
METRIC_NAMESPACE = os.environ.get("METRIC_NAMESPACE", "ChaosMonkey")

PORTS_TO_TARGET = [80, 443]

def permission_matches_http(perm):
    # Return True if perm allows 0.0.0.0/0 for port 80 or 443 (or range containing them)
    from_port = perm.get("FromPort")
    to_port = perm.get("ToPort")
    if from_port is None or to_port is None:
        return False
    if not any(from_port <= p <= to_port for p in PORTS_TO_TARGET):
        return False
    for r in perm.get("IpRanges", []) or []:
        if r.get("CidrIp") == "0.0.0.0/0":
            return True
    for r in perm.get("Ipv6Ranges", []) or []:
        if r.get("CidrIpv6") == "::/0":
            return True
    # Skip rules that reference other security groups (UserIdGroupPairs)
    if perm.get("UserIdGroupPairs"):
        return False
    return False

def create_backup():
    resp = ec2.describe_security_groups(GroupIds=[TARGET_SG_ID])
    sg = resp["SecurityGroups"][0]
    backup = {"backup_id": str(uuid.uuid4()), "timestamp": datetime.datetime.utcnow().isoformat(),
              "sg_id": sg["GroupId"], "ip_permissions": sg.get("IpPermissions", []),
              "ip_permissions_egress": sg.get("IpPermissionsEgress", [])}
    key = f"sg-backups/{TARGET_SG_ID}-{backup['backup_id']}.json"
    put_s3_json(STATE_BUCKET, key, backup)
    return key

def restore_from_backup_key(key):
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
            print("Warning revoke current ingress:", e)
    if ip_perms:
        ec2.authorize_security_group_ingress(GroupId=TARGET_SG_ID, IpPermissions=ip_perms)
    cur_eg = current.get("IpPermissionsEgress", [])
    if cur_eg:
        try:
            ec2.revoke_security_group_egress(GroupId=TARGET_SG_ID, IpPermissions=cur_eg)
        except Exception as e:
            print("Warning revoke current egress:", e)
    if ip_perms_egress:
        ec2.authorize_security_group_egress(GroupId=TARGET_SG_ID, IpPermissions=ip_perms_egress)

def lambda_handler(event, context):
    if not STATE_BUCKET or not TARGET_SG_ID:
        raise ValueError("STATE_BUCKET and TARGET_SG_ID must be set")
    backup_key = create_backup()
    event_id = str(uuid.uuid4())
    put_s3_json(STATE_BUCKET, f"logs/{TARGET_SG_ID}-{event_id}.json",
                {"event_id": event_id, "start": datetime.datetime.utcnow().isoformat(), "backup": backup_key})
    push_metric(METRIC_NAMESPACE, "ChaosStarted", 1)

    sg = ec2.describe_security_groups(GroupIds=[TARGET_SG_ID])["SecurityGroups"][0]
    ip_perms = sg.get("IpPermissions", [])
    perms_to_revoke = [p for p in ip_perms if permission_matches_http(p)]

    if not perms_to_revoke:
        put_s3_json(STATE_BUCKET, f"logs/{TARGET_SG_ID}-{event_id}.json",
                    {"event_id": event_id, "status": "no_rule", "time": datetime.datetime.utcnow().isoformat()})
        push_metric(METRIC_NAMESPACE, "ChaosNoRule", 1)
        return {"status":"no_rule"}

    try:
        ec2.revoke_security_group_ingress(GroupId=TARGET_SG_ID, IpPermissions=perms_to_revoke)
        print("Revoked matching ingress rules")
    except Exception as e:
        print("Revoke failed:", e)
        put_s3_json(STATE_BUCKET, f"logs/{TARGET_SG_ID}-{event_id}.json",
                    {"event_id": event_id, "status": "revoke_failed", "error": str(e)})
        push_metric(METRIC_NAMESPACE, "ChaosRevokeFailed", 1)
        # try immediate restore
        try:
            restore_from_backup_key(backup_key)
        except Exception as re:
            print("Immediate restore failed:", re)
        return {"status":"revoke_failed", "error": str(e)}

    # Chaos window
    time.sleep(CHAOS_DURATION)

    # Restore
    try:
        restore_from_backup_key(backup_key)
        put_s3_json(STATE_BUCKET, f"logs/{TARGET_SG_ID}-{event_id}.json",
                    {"event_id": event_id, "status": "restored", "end": datetime.datetime.utcnow().isoformat()})
        push_metric(METRIC_NAMESPACE, "ChaosRestored", 1)
        return {"status":"done", "event_id": event_id}
    except Exception as e:
        put_s3_json(STATE_BUCKET, f"logs/{TARGET_SG_ID}-{event_id}.json",
                    {"event_id": event_id, "status": "restore_failed", "error": str(e)})
        push_metric(METRIC_NAMESPACE, "ChaosRestoreFailed", 1)
        return {"status":"restore_failed", "error": str(e)}
