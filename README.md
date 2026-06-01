# Enterprise Secure AI Chat Application (AWS Production Deployment)

An enterprise-grade, secure hybrid AI Chat application deployed on AWS EKS with comprehensive perimeter security, identity management, and private networking boundaries.

![Architecture Diagram](aws_architecture_diagram.png)

---

## 🚀 Key Highlights & Architecture

This repository contains the full infrastructure-as-code manifests, automation deployment scripts, and application source code for running a multi-tier chat interface backed by Azure OpenAI. The setup is designed around a Zero Trust posture:

* **Identity Integration (OIDC)**: Client requests are authenticated at the edge/ingress layer using **Okta / Auth0** integration before any requests reach the compute layer.
* **Perimeter Protection**: Protected globally by **AWS WAFv2** and delivered through **Amazon CloudFront** to ensure low-latency static delivery and edge-routing.
* **Private Compute Boundary**: Deployed inside private subnets on **AWS EKS**. The Kubernetes application pods are fully private, with the backend container only accessible internally via ClusterIP endpoints.
* **Secure Ops Management**: Administration and resource management are fully isolated using a dedicated **SSM Bastion Host**, eliminating the need to expose SSH or EKS public endpoints to the open internet.

---

## 🛠️ Tech Stack

* **Front-end**: HTML5 / CSS3 / Vanilla Javascript (served via Nginx proxy).
* **Back-end**: Python Flask REST API with Azure OpenAI SDK.
* **Orchestration & Compute**: AWS Elastic Kubernetes Service (EKS) on managed private node groups.
* **Content Delivery & Edge**: Amazon CloudFront with VPC Origins, Lambda@Edge viewer-request OIDC authentication.
* **Security & Network**: AWS VPC, AWS WAFv2 (Global Web ACL), AWS SSM Session Manager, ACM SSL/TLS Certificates.

---

## 📂 Quick Repository Directory

* [**final_architecture_report.md**](final_architecture_report.md): Definitive step-by-step deployer's playbook and operational guidelines.
* [**file_structure.md**](file_structure.md): Detailed map and explanations of the files in this project.
* [**credential.md**](credential.md): Guide mapping project configuration placeholders to production values.
* [**Backedn/**](Backedn/): Python backend API flask application and environment configs.
* [**Frontend/**](Frontend/): Nginx-served static front-end chat interface.

---

## 🚀 Quick-Start Deployment Overview

### Step 1: Network & Compute Initialization
Use `eksctl` to provision the EKS VPC network infrastructure and private cluster:
```bash
eksctl create cluster -f cluster-config.yaml
```

### Step 2: Establish Secure Operations (SSM Bastion)
Bootstrap the SSM Bastion host to establish a private administrative tunnel:
```bash
./setup_bastion.sh
```

### Step 3: Deploy Application Pods
Apply the Kubernetes deployments, services, and configs:
```bash
python3 deploy_k8s.py
```

### Step 4: Configure Edge Authentication & CloudFront Delivery
Deploy the Lambda@Edge handler and create the CloudFront distribution pointing to the internal ALB:
```bash
# Deploys auth handler
./deploy_lambda.sh
# Deploys CDN distribution with VPC Origin
python3 deploy_cloudfront.py
```

For complete CLI details, IAM policies, and configuration payloads, review the full [Final Architecture Report](final_architecture_report.md).
