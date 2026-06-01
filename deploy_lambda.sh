#!/bin/bash
set -e

REGION="us-east-1"
ROLE_NAME="cloudfront-edge-auth-role"
FUNCTION_NAME="cloudfront-auth-lambda"
ZIP_FILE="lambda_function.zip"

echo "=== 1. Creating Lambda@Edge trust IAM Role ==="
if aws iam get-role --role-name "$ROLE_NAME" --region "$REGION" >/dev/null 2>&1; then
    echo "IAM Role $ROLE_NAME already exists."
else
    aws iam create-role --role-name "$ROLE_NAME" --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Principal": {
            "Service": [
              "lambda.amazonaws.com",
              "edgelambda.amazonaws.com"
            ]
          },
          "Action": "sts:AssumeRole"
        }
      ]
    }' --region "$REGION"
fi

aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" --region "$REGION"

echo "=== 2. Creating lambda_function.zip ==="
cat << 'EOF' > index.js
const https = require('https');

const CONFIG = {
    ISSUER: "https://YOUR_OIDC_ISSUER_DOMAIN/",
    CLIENT_ID: "your-auth0-client-id",
    CLIENT_SECRET: "your-auth0-client-secret",
    REDIRECT_URI: "https://YOUR_DOMAIN_NAME/callback"
};

function parseCookies(cookieHeader) {
    const cookies = {};
    if (!cookieHeader) return cookies;
    cookieHeader.split(';').forEach(cookie => {
        const parts = cookie.split('=');
        if (parts.length === 2) {
            cookies[parts[0].trim()] = parts[1].trim();
        }
    });
    return cookies;
}

function postRequest(url, data) {
    return new Promise((resolve, reject) => {
        const urlObj = new URL(url);
        const options = {
            hostname: urlObj.hostname,
            path: urlObj.pathname,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(data)
            }
        };
        const req = https.request(options, (res) => {
            let body = '';
            res.on('data', (chunk) => body += chunk);
            res.on('end', () => resolve(JSON.parse(body)));
        });
        req.on('error', (e) => reject(e));
        req.write(data);
        req.end();
    });
}

exports.handler = async (event) => {
    const request = event.Records[0].cf.request;
    const headers = request.headers;
    const uri = request.uri;

    if (uri === '/callback') {
        const queryParams = new URLSearchParams(request.querystring);
        const code = queryParams.get('code');
        if (!code) {
            return { status: '400', statusDescription: 'Bad Request', body: 'Missing authorization code' };
        }

        try {
            const tokenResponse = await postRequest(`${CONFIG.ISSUER}oauth/token`, JSON.stringify({
                grant_type: 'authorization_code',
                client_id: CONFIG.CLIENT_ID,
                client_secret: CONFIG.CLIENT_SECRET,
                code: code,
                redirect_uri: CONFIG.REDIRECT_URI
            }));

            const idToken = tokenResponse.id_token;
            if (!idToken) {
                return { status: '400', statusDescription: 'Bad Request', body: 'Failed to retrieve token' };
            }

            return {
                status: '302',
                statusDescription: 'Found',
                headers: {
                    'location': [{ key: 'Location', value: '/' }],
                    'set-cookie': [{ key: 'Set-Cookie', value: `auth_token=${idToken}; Path=/; Secure; HttpOnly; Max-Age=86400` }]
                }
            };
        } catch (err) {
            return { status: '500', statusDescription: 'Internal Server Error', body: err.message };
        }
    }

    const cookieHeader = headers.cookie ? headers.cookie[0].value : '';
    const cookies = parseCookies(cookieHeader);
    const authToken = cookies['auth_token'];

    if (authToken) {
        try {
            const payloadBase64 = authToken.split('.')[1];
            const payload = JSON.parse(Buffer.from(payloadBase64, 'base64').toString('utf8'));
            const now = Math.floor(Date.now() / 1000);
            if (payload.exp > now) {
                return request;
            }
        } catch (e) {
            // Invalid
        }
    }

    const state = uri;
    const loginUrl = `${CONFIG.ISSUER}authorize?` + new URLSearchParams({
        response_type: 'code',
        client_id: CONFIG.CLIENT_ID,
        redirect_uri: CONFIG.REDIRECT_URI,
        state: state,
        scope: 'openid profile email'
    }).toString();

    return {
        status: '302',
        statusDescription: 'Found',
        headers: {
            'location': [{ key: 'Location', value: loginUrl }]
        }
    };
};
EOF

zip -q "$ZIP_FILE" index.js
rm -f index.js

# Give IAM role time to propagate
sleep 5

echo "=== 3. Creating/Updating Lambda Function ==="
ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text --region "$REGION")

if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" >/dev/null 2>&1; then
    echo "Lambda function exists. Updating code..."
    aws lambda update-function-code --function-name "$FUNCTION_NAME" --zip-file fileb://"$ZIP_FILE" --region "$REGION"
else
    echo "Creating new Lambda function..."
    aws lambda create-function \
      --function-name "$FUNCTION_NAME" \
      --runtime nodejs18.x \
      --role "$ROLE_ARN" \
      --handler index.handler \
      --zip-file fileb://"$ZIP_FILE" \
      --publish \
      --region "$REGION"
fi

rm -f "$ZIP_FILE"

# Wait for function update to complete/be active
sleep 10

echo "=== 4. Publishing Lambda Version ==="
VERSION_ARN=$(aws lambda publish-version --function-name "$FUNCTION_NAME" --query 'FunctionArn' --output text --region "$REGION")
echo "LAMBDA_EDGE_VERSION_ARN: $VERSION_ARN"
