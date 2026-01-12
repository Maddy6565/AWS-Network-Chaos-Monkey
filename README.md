# AWS-Network-Chaos-Monkey
Lambda-driven AWS network chaos toolkit. Programmatically remove &amp; restore Security Group rules and Route Table entries, snapshot state to S3, integrate with CloudWatch alarms, and run safe resilience experiments for cloud networking and security portfolios.

## Files you need
- `lambda/helpers.py`              - small S3 + CloudWatch helpers
- `lambda/sg_backup.py`            - backup SG snapshot to S3
- `lambda/sg_chaos.py`             - remove HTTP/HTTPS ingress, wait, restore
- `lambda/routetable_chaos`        - remove IGW connection, wait, restore
- `lambda/sg_restore.py`           - restore latest SG backup (panic restore)
- `scripts/deploy_lambda.sh`       - optional helper to zip & deploy Lambdas
- `.env.example`                   - example env vars (do not commit secrets)

- ## Steps 
1. Create an S3 bucket: `aws s3 mb s3://chaos-monkey-state-<yourname>`
2. Create IAM role for Lambda:
   - Console: IAM → Roles → Create role → Lambda
   - Attach managed policy: `AWSLambdaBasicExecutionRole`
   - Add inline policy (allow EC2 Describe/Modify, S3 Put/Get, CloudWatch logs). Use least privilege later.
3. Create Lambda functions in console:
   - `sg_backup` (handler `sg_backup.lambda_handler`)
   - `sg_chaos` (handler `sg_chaos.lambda_handler`)
   - `routetable_chaos` (handler `routetable_chaos.lambda_handler`)
   - `sg_restore` (handler `sg_restore.lambda_handler`)
   - Paste `helpers.py` and each function file in the Lambda inline editor (create multiple files in the console editor)
4. Set Environment variables for each Lambda:
   - `STATE_BUCKET` = `chaos-monkey-state-<yourname>`
   - `TARGET_SG_ID` = `sg-xxxxxxxxxxxx`
   - `CHAOS_DURATION_SECONDS` = `10`
   - `METRIC_NAMESPACE` = `ChaosMonkey`
5. Test:
   - Run `sg_backup` → check S3 `sg-backups/`
   - Run `sg_chaos`, `routetable_chaos` → observe downtime in browser and restored after duration
   - Run `sg_restore` to manually restore the latest backup
6. Safety: Run only in test VPC. Keep duration small. Stop EC2 when not testing.
