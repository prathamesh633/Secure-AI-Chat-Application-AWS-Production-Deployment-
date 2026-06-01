#!/bin/bash
set -e

REGION="us-east-1"
WAF_NAME="cloudfront-waf-acl"

echo "=== Creating WAFv2 Web ACL ==="
WAF_ARN=$(aws wafv2 list-web-acls --scope CLOUDFRONT --region "$REGION" --query "WebACLs[?Name=='$WAF_NAME'].ARN" --output text)

if [ -z "$WAF_ARN" ] || [ "$WAF_ARN" = "None" ]; then
    RESPONSE=$(aws wafv2 create-web-acl \
      --name "$WAF_NAME" \
      --scope CLOUDFRONT \
      --default-action Allow={} \
      --visibility-config SampledRequestsEnabled=true,CloudWatchMetricsEnabled=true,MetricName="$WAF_NAME" \
      --rules '[
        {
          "Name": "RateLimitRule",
          "Priority": 1,
          "Statement": {
            "RateBasedStatement": {
              "Limit": 2000,
              "AggregateKeyType": "IP"
            }
          },
          "Action": {
            "Block": {}
          },
          "VisibilityConfig": {
            "SampledRequestsEnabled": true,
            "CloudWatchMetricsEnabled": true,
            "MetricName": "RateLimitMetric"
          }
        }
      ]' \
      --region "$REGION" \
      --output json)
    
    WAF_ARN=$(echo "$RESPONSE" | grep -o '"ARN": "[^"]*' | grep -o '[^"]*$')
    echo "WAF Web ACL Created: $WAF_ARN"
else
    echo "WAF Web ACL already exists: $WAF_ARN"
fi

echo "WAF_ACL_ARN=$WAF_ARN"
