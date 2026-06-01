import boto3
import time
import sys

vpc_origin_id = "YOUR_VPC_ORIGIN_ID"
alb_dns = "YOUR_ALB_INTERNAL_DNS"
lambda_arn = "arn:aws:lambda:us-east-1:YOUR_AWS_ACCOUNT_ID:function:cloudfront-auth-lambda:1"
waf_acl_arn = "arn:aws:wafv2:us-east-1:YOUR_AWS_ACCOUNT_ID:global/webacl/cloudfront-waf-acl/YOUR_WAF_ACL_ID"
acm_cert_arn = "arn:aws:acm:us-east-1:YOUR_AWS_ACCOUNT_ID:certificate/YOUR_ACM_CERTIFICATE_ID"
domain_name = "YOUR_DOMAIN_NAME"

cf = boto3.client('cloudfront', region_name='us-east-1')

print("=== 1. Waiting for VPC Origin to be deployed ===")
while True:
    resp = cf.get_vpc_origin(Id=vpc_origin_id)
    status = resp['VpcOrigin']['Status']
    print(f"VPC Origin Status: {status}")
    if status == 'Deployed':
        break
    elif status == 'Failed':
        print("VPC Origin deployment failed!")
        sys.exit(1)
    time.sleep(10)

print("=== 2. Creating CloudFront Distribution ===")
dist_config = {
    'CallerReference': str(time.time()),
    'Aliases': {
        'Quantity': 1,
        'Items': [domain_name]
    },
    'DefaultRootObject': '',
    'Origins': {
        'Quantity': 1,
        'Items': [
            {
                'Id': 'alb-vpc-origin',
                'DomainName': alb_dns,
                'VpcOriginConfig': {
                    'VpcOriginId': vpc_origin_id
                },
                # For custom headers or other settings if needed
                'CustomHeaders': {
                    'Quantity': 0,
                    'Items': []
                }
            }
        ]
    },
    'OriginGroups': {
        'Quantity': 0,
        'Items': []
    },
    'DefaultCacheBehavior': {
        'TargetOriginId': 'alb-vpc-origin',
        'TrustedSigners': {
            'Enabled': False,
            'Quantity': 0,
            'Items': []
        },
        'TrustedKeyGroups': {
            'Enabled': False,
            'Quantity': 0,
            'Items': []
        },
        'ViewerProtocolPolicy': 'redirect-to-https',
        'AllowedMethods': {
            'Quantity': 7,
            'Items': ['GET', 'HEAD', 'OPTIONS', 'PUT', 'POST', 'PATCH', 'DELETE'],
            'CachedMethods': {
                'Quantity': 2,
                'Items': ['GET', 'HEAD']
            }
        },
        'SmoothStreaming': False,
        'Compress': True,
        'LambdaFunctionAssociations': {
            'Quantity': 1,
            'Items': [
                {
                    'LambdaFunctionARN': lambda_arn,
                    'EventType': 'viewer-request',
                    'IncludeBody': False
                }
            ]
        },
        'FieldLevelEncryptionId': '',
        'CachePolicyId': '4135ea2d-6df8-44a3-9df3-4b5a84be39ad', # CachingDisabled Policy ID
        'OriginRequestPolicyId': '216adef6-5c7f-47e4-b989-5492eafa07d3' # AllViewerAndCloudFrontHeaders-2022-06 Policy ID
    },
    'CacheBehaviors': {
        'Quantity': 0,
        'Items': []
    },
    'CustomErrorResponses': {
        'Quantity': 0,
        'Items': []
    },
    'Comment': 'Fully Private EKS Chat App Distribution',
    'Logging': {
        'Enabled': False,
        'IncludeCookies': False,
        'Bucket': '',
        'Prefix': ''
    },
    'PriceClass': 'PriceClass_All',
    'Enabled': True,
    'ViewerCertificate': {
        'ACMCertificateArn': acm_cert_arn,
        'SSLSupportMethod': 'sni-only',
        'MinimumProtocolVersion': 'TLSv1.2_2021',
        'Certificate': acm_cert_arn,
        'CertificateSource': 'acm'
    },
    'Restrictions': {
        'GeoRestriction': {
            'RestrictionType': 'none',
            'Quantity': 0,
            'Items': []
        }
    },
    'WebACLId': waf_acl_arn,
    'HttpVersion': 'http2',
    'IsIPV6Enabled': True
}

response = cf.create_distribution(DistributionConfig=dist_config)
dist_id = response['Distribution']['Id']
dist_dns = response['Distribution']['DomainName']

print(f"=== CloudFront Distribution Created Successfully! ===")
print(f"Distribution ID: {dist_id}")
print(f"Distribution Domain Name: {dist_dns}")
