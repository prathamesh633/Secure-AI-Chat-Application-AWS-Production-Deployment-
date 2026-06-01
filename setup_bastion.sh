#!/bin/bash
set -e

REGION="us-east-1"
CLUSTER_NAME="enterprise-eks"
VPC_ID="YOUR_VPC_ID"
PUBLIC_SUBNET="YOUR_PUBLIC_SUBNET_ID"
CLUSTER_SG="YOUR_CLUSTER_SECURITY_GROUP_ID"
ROLE_NAME="enterprise-eks-bastion-role"
PROFILE_NAME="enterprise-eks-bastion-profile"
SG_NAME="enterprise-eks-bastion-sg"
AMI_ID="ami-00e801948462f718a"

echo "=== 1. Creating IAM Role for Bastion ==="
if aws iam get-role --role-name "$ROLE_NAME" --region "$REGION" >/dev/null 2>&1; then
    echo "IAM Role $ROLE_NAME already exists."
else
    aws iam create-role --role-name "$ROLE_NAME" --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Principal": {
            "Service": "ec2.amazonaws.com"
          },
          "Action": "sts:AssumeRole"
        }
      ]
    }' --region "$REGION"
fi

echo "=== 2. Attaching SSM Managed Instance Core policy ==="
aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore" --region "$REGION"

# Also attach EKS read/describe permission to let bastion run 'update-kubeconfig'
if aws iam get-policy --policy-arn "arn:aws:iam::YOUR_AWS_ACCOUNT_ID:policy/BastionEKSAccessPolicy" >/dev/null 2>&1; then
    echo "EKS Access Policy already exists."
else
    aws iam create-policy --policy-name "BastionEKSAccessPolicy" --policy-document '{
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Action": [
            "eks:DescribeCluster",
            "eks:ListClusters"
          ],
          "Resource": "*"
        }
      ]
    }' --region "$REGION"
fi
aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn "arn:aws:iam::YOUR_AWS_ACCOUNT_ID:policy/BastionEKSAccessPolicy" --region "$REGION"

echo "=== 3. Creating Instance Profile ==="
if aws iam get-instance-profile --instance-profile-name "$PROFILE_NAME" --region "$REGION" >/dev/null 2>&1; then
    echo "Instance Profile $PROFILE_NAME already exists."
else
    aws iam create-instance-profile --instance-profile-name "$PROFILE_NAME" --region "$REGION"
    # Wait for profile creation to propagate
    sleep 5
fi

if aws iam get-instance-profile --instance-profile-name "$PROFILE_NAME" --region "$REGION" --query 'InstanceProfiles[0].Roles[0].RoleName' --output text 2>/dev/null | grep -q "$ROLE_NAME"; then
    echo "Role is already associated with profile."
else
    aws iam add-role-to-instance-profile --instance-profile-name "$PROFILE_NAME" --role-name "$ROLE_NAME" --region "$REGION"
    sleep 5
fi

echo "=== 4. Creating Security Group ==="
SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" --query 'SecurityGroups[0].GroupId' --output text --region "$REGION")
if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
    SG_ID=$(aws ec2 create-security-group --group-name "$SG_NAME" --description "Security group for EKS bastion host" --vpc-id "$VPC_ID" --query 'GroupId' --output text --region "$REGION")
    echo "Created Security Group: $SG_ID"
else
    echo "Security Group already exists: $SG_ID"
fi

# Allow Bastion to access EKS Control Plane on Port 443
echo "=== 5. Allowing Bastion to access EKS Control Plane ==="
aws ec2 authorize-security-group-ingress --group-id "$CLUSTER_SG" --protocol tcp --port 443 --source-group "$SG_ID" --region "$REGION" || true

echo "=== 6. Launching Bastion EC2 Instance ==="
# User data script to install tools
cat << 'EOF' > user-data.sh
#!/bin/bash
sudo yum update -y
sudo yum install -y unzip tar gzip git

# Install kubectl
curl -LO "https://dl.k8s.io/release/v1.30.0/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Install Helm
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh

# Install aws-cli v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Set up kubeconfig for ec2-user
mkdir -p /home/ec2-user/.kube
chown -R ec2-user:ec2-user /home/ec2-user/.kube
sudo -u ec2-user aws eks update-kubeconfig --name enterprise-eks --region us-east-1
EOF

# Launch EC2
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t3.micro \
  --subnet-id "$PUBLIC_SUBNET" \
  --security-group-ids "$SG_ID" \
  --iam-instance-profile Name="$PROFILE_NAME" \
  --user-data file://user-data.sh \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=eks-bastion}]" \
  --query 'Instances[0].InstanceId' \
  --output text \
  --region "$REGION")

rm -f user-data.sh
echo "Bastion Instance Launched: $INSTANCE_ID"

# Get Bastion IAM Role ARN
ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text --region "$REGION")

echo "=== 7. Creating EKS Access Entry for Bastion Role ==="
aws eks create-access-entry \
  --cluster-name "$CLUSTER_NAME" \
  --principal-arn "$ROLE_ARN" \
  --region "$REGION" || true

aws eks associate-access-policy \
  --cluster-name "$CLUSTER_NAME" \
  --principal-arn "$ROLE_ARN" \
  --policy-arn "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy" \
  --access-scope type=cluster \
  --region "$REGION" || true

echo "=== Setup complete! Bastion ID: $INSTANCE_ID ==="
echo "Wait 2-3 minutes for the instance to bootstrap and run commands."
