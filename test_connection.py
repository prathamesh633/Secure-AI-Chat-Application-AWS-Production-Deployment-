import boto3
import time
import sys

instance_id = "YOUR_BASTION_INSTANCE_ID"
region = "us-east-1"
api_id = "YOUR_API_GATEWAY_ID"

ssm = boto3.client('ssm', region_name=region)

script_content = f"""#!/bin/bash
POD_NAME=$(kubectl get pods -l app=frontend -o jsonpath="{{.items[0].metadata.name}}")
echo "Frontend Pod: $POD_NAME"
echo "Sending request to Private API Gateway: https://{api_id}.execute-api.us-east-1.amazonaws.com/prod/health"
kubectl exec $POD_NAME -- curl -kv https://{api_id}.execute-api.us-east-1.amazonaws.com/prod/health
"""

def run_ssm_command(commands):
    response = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={'commands': commands}
    )
    cmd_id = response['Command']['CommandId']
    
    # Wait for completion
    while True:
        status_resp = ssm.get_command_invocation(
            CommandId=cmd_id,
            InstanceId=instance_id
        )
        status = status_resp['Status']
        if status in ['Success', 'Failed', 'Cancelled', 'TimedOut']:
            print(f"Status: {status}")
            print("Standard Output:")
            print(status_resp.get('StandardOutputContent', ''))
            print("Standard Error:")
            print(status_resp.get('StandardErrorContent', ''))
            return status == 'Success'
        time.sleep(2)

print("=== 1. Writing test script to Bastion ===")
write_cmd = f"cat << 'EOF' > /home/ec2-user/test_connection.sh\n{script_content}\nEOF\nchmod +x /home/ec2-user/test_connection.sh\nchown ec2-user:ec2-user /home/ec2-user/test_connection.sh"
if not run_ssm_command([write_cmd]):
    print("Failed to write test script")
    sys.exit(1)

print("=== 2. Running test script on Bastion ===")
if not run_ssm_command(["sudo -u ec2-user /home/ec2-user/test_connection.sh"]):
    print("Test execution failed")
    sys.exit(1)

print("=== Test finished! ===")
