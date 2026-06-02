# Enterprise AWS Architecture Diagram Generator Prompt

This document provides a highly detailed prompt designed for AI diagram generators (such as Eraser.io, Terrastruct, Mermaid, or Draw.io AI) or for a graphic designer to produce a professional, enterprise-grade cloud architecture diagram.

---

## The AI Prompt

```text
Create a highly professional, enterprise-grade AWS cloud architecture diagram for a "Secure Multi-Tier AI Chat Application". 

### 1. General Layout and Theme
- Styling: Modern, clean, dark-mode themed with clear bounding boxes for logical zones.
- Color Coding: Use a subtle color palette (e.g., light blue for public/edge layer, light orange for private compute layer, purple for identity/auth).
- Grid/Layout: Vertical flow showing the path of a request from top to bottom (Client -> Edge Layer -> API/Ingress Layer -> Private Compute Layer -> LLM backend).

### 2. Layers and Subnet Boundaries

#### Layer A: Client and Edge Layer (Public Internet)
- Component 1: "User Browser / Client"
- Component 2: "Route 53" (resolves DNS for app.yourdomain.com)
- Component 3: "AWS WAFv2" (Global Web ACL protecting CloudFront)
- Component 4: "Amazon CloudFront CDN" (Handles HTTPS delivery)
- Component 5: "Lambda@Edge" (Triggered on 'viewer-request' to run OIDC check)
- Component 6: "Auth0 / Okta" (External Identity Provider, connected via OIDC redirect flow)

#### Layer B: VPC Networking Boundary (AWS VPC: 192.168.0.0/16)
Draw a large bounding box for the "AWS VPC". Inside this VPC, split it into two subnet zones:

- **Zone 1: Public Subnets (192.168.0.0/19, 192.168.32.0/19)**
  - Component 7: "AWS SSM Bastion Host" (EC2 t3.micro inside public subnet)
  - Component 8: "AWS NAT Gateway" (Handles outbound private traffic)
  
- **Zone 2: Private Subnets (192.168.64.0/19, 192.168.96.0/19)**
  - Component 9: "AWS Elastic Kubernetes Service (EKS) Cluster" (enterprise-eks)
    - Sub-component: "AWS Application Load Balancer (ALB)" (Internal scheme, target IP type)
    - Sub-component: "Frontend Service Pods" (Nginx web app running in private subnets)
    - Sub-component: "Backend Service Pods" (Flask API running in private subnets, only accessible via Frontend pods)
  - Component 10: "AWS Network Load Balancer (NLB)" (Internal scheme, targeting Frontend Service)
  - Component 11: "AWS execute-api VPC Interface Endpoint" (vpce-xxxx)
  - Component 12: "AWS API Gateway VPC Link" (Connects API Gateway to the internal NLB)

#### Layer C: API Integration layer
- Component 13: "Amazon API Gateway (Private REST API)" (Invoked only through the VPC interface endpoint)

#### Layer D: Downstream Integrations (External/Third-Party)
- Component 14: "Azure OpenAI Service" (External target for backend LLM queries, reached securely via NAT Gateway)

---

### 3. Request Flow & Connection Paths

Draw arrows showing the following exact step-by-step workflow:
1. **Client Request**: Client queries "Route 53" to resolve domain, then sends HTTPS request to "Amazon CloudFront".
2. **Edge Auth Check**: "CloudFront" triggers "Lambda@Edge" on viewer-request. 
   - If unauthenticated: Redirects client to "Auth0 / Okta" login.
   - If authenticated: "Lambda@Edge" validates JWT token and allows traffic.
3. **Private Endpoint Tunnel**: "CloudFront" forwards authenticated requests to "Amazon API Gateway (Private REST API)".
4. **VPC Endpoint Invocation**: API Gateway routes requests into the VPC via the "execute-api VPC Interface Endpoint".
5. **Private Routing**: The VPC Endpoint routes traffic to the "VPC Link", which forwards it to the "Internal NLB".
6. **EKS Compute Access**: "Internal NLB" routes requests to the "Frontend Pods" inside EKS private subnets.
7. **Secure API Call**: "Frontend Pods" communicate internally with "Backend Pods" (ClusterIP).
8. **LLM Connection**: "Backend Pods" make API calls to "Azure OpenAI" using the "NAT Gateway" for secure internet egress.

---

### 4. Admin and Operations Layer (Side Flow)
- Draw a separate flow for the "SSM Bastion Host":
  - "Developer / Administrator" connects securely via "AWS SSM Systems Manager" (No public port 22).
  - "SSM Bastion Host" has "BastionEKSAccessPolicy" (IAM Role) and runs kubectl commands to administer "EKS Cluster" control plane.

### 5. Architectural Annotations
- Include security labels: "IAM Policies & RBAC", "WAF Rules (Rate Limiting)", "Transit Policies (Private API Gateway Resource Policy denying non-VPCE traffic)".
- Explicitly mark boundaries: "Public Subnet Boundary", "Private Subnet Boundary", "AWS VPC Boundary".
```
