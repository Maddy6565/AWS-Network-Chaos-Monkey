import boto3, json, os, datetime

ec2 = boto3.client('ec2')
s3 = boto3.client('s3')

BUCKET = os.environ['STATE_BUCKET']
SG_ID = os.environ['TARGET_SG_ID']

def lambda_handler(event, context):
    resp = ec2.describe_security_groups(GroupIds=[SG_ID])
    sg = resp['SecurityGroups'][0]
    
    backup = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "sg_id": SG_ID,
        "ip_permissions": sg['IpPermissions'],
        "ip_permissions_egress": sg['IpPermissionsEgress'],
    }

    key = f"sg-backups/{SG_ID}-{backup['timestamp']}.json"
    s3.put_object(Bucket=BUCKET, Key=key, Body=json.dumps(backup).encode('utf-8'))

    return {"status": "ok", "s3_key": key}
