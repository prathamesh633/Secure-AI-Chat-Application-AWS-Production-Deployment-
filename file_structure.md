# Project File Structure

Below is the directory structure of this repository along with explanations for the important files and directories.

```text
TEST_APP/
├── Backedn/                          # Backend Application Service
│   ├── app.py                        # Flask API application with Azure OpenAI SDK
│   ├── Dockerfile                    # Containerization instructions for backend
│   ├── requirements.txt              # Python dependency list (Flask, openai)
│   └── .env                          # Local environment config (Azure OpenAI keys)
│
├── Frontend/                         # Frontend Application Service
│   ├── index.html                    # HTML/JS static chat web application
│   ├── nginx.conf                    # Nginx routing configuration for Frontend proxy
│   └── Dockerfile                    # Containerization instructions for frontend
│
├── cluster-config.yaml               # eksctl configuration manifest to build EKS VPC and cluster
│
├── app-configmap.yaml                # Kubernetes ConfigMaps for Frontend and Backend services
│
├── backend-deployment.yaml           # Deployment manifest for Backend pods (private subnets)
├── backend-service.yaml              # ClusterIP Service manifest for the Backend
├── backend-secret.yaml               # Secret configuration for Azure OpenAI keys
│
├── frontend-deployment.yaml          # Deployment manifest for Frontend pods (private subnets)
├── frontend-service.yaml             # NodePort Service manifest for the Frontend (targeted by ALB)
├── frontend-ingress.yaml             # Basic ALB Ingress configuration manifest
├── frontend-ingress-okta.example.yaml # ALB Ingress configuration integrated with Okta OIDC
│
├── okta-oidc-secret.example.yaml     # Kubernetes Secret holding Okta OIDC credentials
├── okta-secret-access.yaml           # RBAC rules (Role & RoleBinding) for ALB controller secret access
│
├── deploy_lambda.sh                  # Shell script to build, zip, and deploy Lambda@Edge viewer-request OIDC auth
├── redeploy_auth.py                  # Python utility to rebuild, package, and hot-reload Lambda@Edge with custom OIDC credentials
│
├── deploy_cloudfront.py              # Automation script to configure CloudFront distribution with a VPC Origin and WAFv2 Web ACL
├── deploy_waf.sh                     # Helper script to create CloudFront WAFv2 Web ACL with rate-limiting
│
├── setup_bastion.sh                  # Automates SSM Bastion Host deployment, security rules, and tool configurations
├── test_connection.py                # Validation script to test EKS Pod connection to Private API Gateway via Bastion host
├── deploy_k8s.py                     # Convenience script to upload and apply k8s manifests via Bastion host
│
├── api_patch.json                    # API Gateway Resource Policy definition payload
├── r53_change.json                   # Route 53 A-Alias record update payload
│
├── final_architecture_report.md      # Comprehensive step-by-step production architecture deployment guide
├── credential.md                     # Documentation mapping all placeholders to actual values
├── file_structure.md                 # Project structure and file layout documentation (this file)
└── README.md                         # Main repository entrypoint overview
```

---

## Important Files Overview

* **`cluster-config.yaml`**: The blueprint used by `eksctl` to provision a secure VPC network across multiple availability zones, EKS control plane, and private managed worker nodes.
* **`Backedn/app.py`**: Handles incoming chat prompts, routes requests to the Azure OpenAI service, and formats responses.
* **`Frontend/index.html`**: A clean, single-page web app using HTML5/Vanilla JS that fetches and handles chat sessions asynchronously, pointing requests to the local ingress host or local development server.
* **`setup_bastion.sh`**: Provisions a t3.micro EC2 bastion host in a public subnet, authorizes it for EKS cluster administration, installs tools (kubectl, Helm, aws-cli), and setups kubeconfig access over secure SSM sessions.
* **`redeploy_auth.py`**: A Python helper to package client-side JS into a zip, upload it to Lambda, publish a version, and update a CloudFront distribution's cache behaviors dynamically.
* **`deploy_cloudfront.py`**: Fully automates creation of an edge CDN cache behavior, referencing a custom VPC Origin pointing to an internal ALB.
* **`final_architecture_report.md`**: Provides the definitive operational manual for deploying, maintaining, and scaling the entire hybrid infrastructure setup.
