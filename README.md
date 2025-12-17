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


## Future Work & Contributions
This project is intentionally kept minimal and safe for learning and experimentation.
Future improvements focus on making the chaos scenarios more realistic, configurable, and observable.

## Planned Enhancements
1. Additional chaos experiments:
   - ALB listener and target group failures
   - Fork ACL misconfiguration scenarios
   - Partial subnet isolation experiments

2. Parameter-driven experiments:
   - JSON-based experiment definitions
   - Configurable targets (port, CIDR, duration)

3. Improved monitoring
   - Custom application health-check Lambda
   - Additional CloudWatch metrics and alarms

4. Stronger safety controls
   - Advanced tag-based resource filtering
   - Pre-flight validation and sanity checks

5. Automation
   - Scheduled chaos runs using EventBridge
   - Automatic rollback on alarm breach

## Contributions Welcome
Contributions are welcome and encouraged, especially in the following areas:
New chaos experiment scenarios
Code cleanup and refactoring
Documentation and diagram improvements
Test coverage and validation scripts
Security and safety enhancements

## How to Contribute
Fork the repository
Create a feature branch
Keep changes small and well-documented
Ensure safety checks remain intact
Submit a pull request with a clear description

## Contribution Principles
Safety first — no destructive changes
All chaos must be reversible
Lab / non-production environments only
Clear documentation is required