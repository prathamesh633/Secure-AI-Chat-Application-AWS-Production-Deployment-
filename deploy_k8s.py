import boto3
import json
import sys
import time

instance_id = "YOUR_BASTION_INSTANCE_ID"
region = "us-east-1"
files_to_deploy = [
    "frontend-deployment.yaml",
    "frontend-service.yaml",
    "frontend-ingress.yaml"
]

ssm = boto3.client('ssm', region_name=region)

def run_ssm_command(commands):
    response = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={'commands': commands}
    )
    cmd_id = response['Command']['CommandId']
    print(f"Sent SSM Command: {cmd_id}")
    
    # Wait for completion
    while True:
        status_resp = ssm.get_command_invocation(
            CommandId=cmd_id,
            InstanceId=instance_id
        )
        status = status_resp['Status']
        if status in ['Success', 'Failed', 'Cancelled', 'TimedOut']:
            print(f"Command finished with status: {status}")
            if status != 'Success':
                print("Error output:")
                print(status_resp.get('StandardErrorContent', ''))
            print("Output:")
            print(status_resp.get('StandardOutputContent', ''))
            return status == 'Success'
        time.sleep(2)

print("=== 1. Writing manifest files to Bastion ===")
for filename in files_to_deploy:
    with open(filename, 'r') as f:
        content = f.read()
    
    # Write to bastion
    print(f"Uploading {filename}...")
    write_cmd = f"cat << 'EOF' > /home/ec2-user/{filename}\n{content}\nEOF\nchown ec2-user:ec2-user /home/ec2-user/{filename}"
    
    if not run_ssm_command([write_cmd]):
        print(f"Failed to upload {filename}")
        sys.exit(1)

print("=== 2. Applying manifests to Kubernetes ===")
apply_cmd = "sudo -u ec2-user kubectl apply -f /home/ec2-user/frontend-deployment.yaml -f /home/ec2-user/frontend-service.yaml -f /home/ec2-user/frontend-ingress.yaml"

if not run_ssm_command([apply_cmd]):
    print("Failed to apply manifests")
    sys.exit(1)

print("=== Deployment successful! ===")
