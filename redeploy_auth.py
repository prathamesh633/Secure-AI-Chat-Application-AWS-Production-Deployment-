import boto3
import sys
import zipfile
import io
import time

if len(sys.argv) < 3:
    print("Usage: python3 redeploy_auth.py <CLIENT_ID> <CLIENT_SECRET>")
    sys.exit(1)

client_id = sys.argv[1]
client_secret = sys.argv[2]
function_name = "cloudfront-auth-lambda"
distribution_id = "YOUR_CLOUDFRONT_DISTRIBUTION_ID"
region = "us-east-1"

lambda_client = boto3.client('lambda', region_name=region)
cf_client = boto3.client('cloudfront', region_name=region)

print(f"=== 1. Packaging Lambda code with new credentials and PKCE flow ===")
lambda_code = f"""
const https = require('https');
const crypto = require('crypto');

const CONFIG = {{
    ISSUER: "https://YOUR_OIDC_ISSUER_DOMAIN/",
    CLIENT_ID: "{client_id}",
    CLIENT_SECRET: "{client_secret}",
    REDIRECT_URI: "https://YOUR_DOMAIN_NAME/callback"
}};

function parseCookies(cookieHeader) {{
    const cookies = {{}};
    if (!cookieHeader) return cookies;
    cookieHeader.split(';').forEach(cookie => {{
        const parts = cookie.split('=');
        if (parts.length === 2) {{
            cookies[parts[0].trim()] = parts[1].trim();
        }}
    }});
    return cookies;
}}

function postRequest(url, data) {{
    return new Promise((resolve, reject) => {{
        const urlObj = new URL(url);
        const options = {{
            hostname: urlObj.hostname,
            path: urlObj.pathname,
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(data)
            }}
        }};
        const req = https.request(options, (res) => {{
            let body = '';
            res.on('data', (chunk) => body += chunk);
            res.on('end', () => resolve(JSON.parse(body)));
        }});
        req.on('error', (e) => reject(e));
        req.write(data);
        req.end();
    }});
}}

exports.handler = async (event) => {{
    const request = event.Records[0].cf.request;
    const headers = request.headers;
    const uri = request.uri;

    if (uri === '/callback') {{
        const queryParams = new URLSearchParams(request.querystring);
        const code = queryParams.get('code');
        if (!code) {{
            return {{ status: '400', statusDescription: 'Bad Request', body: 'Missing authorization code' }};
        }}

        const cookieHeader = headers.cookie ? headers.cookie[0].value : '';
        const cookies = parseCookies(cookieHeader);
        const codeVerifier = cookies['pkce_verifier'];
        if (!codeVerifier) {{
            return {{ status: '400', statusDescription: 'Bad Request', body: 'Missing code verifier. Session expired.' }};
        }}

        try {{
            const tokenResponse = await postRequest(`${{CONFIG.ISSUER}}oauth/token`, JSON.stringify({{
                grant_type: 'authorization_code',
                client_id: CONFIG.CLIENT_ID,
                client_secret: CONFIG.CLIENT_SECRET,
                code: code,
                redirect_uri: CONFIG.REDIRECT_URI,
                code_verifier: codeVerifier
            }}));

            const idToken = tokenResponse.id_token;
            if (!idToken) {{
                return {{ status: '400', statusDescription: 'Bad Request', body: 'Failed to retrieve token' }};
            }}

            return {{
                status: '302',
                statusDescription: 'Found',
                headers: {{
                    'location': [{{ key: 'Location', value: '/' }}],
                    'set-cookie': [
                        {{ key: 'Set-Cookie', value: `auth_token=${{idToken}}; Path=/; Secure; HttpOnly; Max-Age=86400` }},
                        {{ key: 'Set-Cookie', value: `pkce_verifier=; Path=/; Secure; HttpOnly; Max-Age=0` }}
                    ]
                }}
            }};
        }} catch (err) {{
            return {{ status: '500', statusDescription: 'Internal Server Error', body: err.message }};
        }}
    }}

    const cookieHeader = headers.cookie ? headers.cookie[0].value : '';
    const cookies = parseCookies(cookieHeader);
    const authToken = cookies['auth_token'];

    if (authToken) {{
        try {{
            const payloadBase64 = authToken.split('.')[1];
            const payload = JSON.parse(Buffer.from(payloadBase64, 'base64').toString('utf8'));
            const now = Math.floor(Date.now() / 1000);
            if (payload.exp > now) {{
                return request;
            }}
        }} catch (e) {{
            // Invalid
        }}
    }}

    // Generate PKCE code verifier and challenge
    const codeVerifier = crypto.randomBytes(32).toString('base64url');
    const codeChallenge = crypto.createHash('sha256').update(codeVerifier).digest('base64url');

    const state = uri;
    const loginUrl = `${{CONFIG.ISSUER}}authorize?` + new URLSearchParams({{
        response_type: 'code',
        client_id: CONFIG.CLIENT_ID,
        redirect_uri: CONFIG.REDIRECT_URI,
        state: state,
        scope: 'openid profile email',
        code_challenge: codeChallenge,
        code_challenge_method: 'S256'
    }}).toString();

    return {{
        status: '302',
        statusDescription: 'Found',
        headers: {{
            'location': [{{ key: 'Location', value: loginUrl }}],
            'set-cookie': [{{ key: 'Set-Cookie', value: `pkce_verifier=${{codeVerifier}}; Path=/; Secure; HttpOnly; Max-Age=300` }}]
        }}
    }};
}};
"""

zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED) as zip_file:
    zip_file.writestr('index.js', lambda_code)
zip_buffer.seek(0)
zip_data = zip_buffer.read()

print("=== 2. Updating Lambda function code ===")
lambda_client.update_function_code(
    FunctionName=function_name,
    ZipFile=zip_data
)
print("Waiting for update to complete...")
time.sleep(5)

print("=== 3. Publishing new Lambda version ===")
publish_resp = lambda_client.publish_version(FunctionName=function_name)
new_version_arn = publish_resp['FunctionArn']
print(f"Published Version ARN: {new_version_arn}")

print("=== 4. Updating CloudFront Distribution configuration ===")
dist_config_resp = cf_client.get_distribution_config(Id=distribution_id)
etag = dist_config_resp['ETag']
dist_config = dist_config_resp['DistributionConfig']

# Update default cache behavior Lambda association
associations = dist_config['DefaultCacheBehavior']['LambdaFunctionAssociations']
updated = False
for item in associations['Items']:
    if item['EventType'] == 'viewer-request':
        item['LambdaFunctionARN'] = new_version_arn
        updated = True

if not updated:
    associations['Items'].append({
        'LambdaFunctionARN': new_version_arn,
        'EventType': 'viewer-request',
        'IncludeBody': False
    })
    associations['Quantity'] = len(associations['Items'])

print("Sending update request to CloudFront...")
cf_client.update_distribution(
    DistributionConfig=dist_config,
    Id=distribution_id,
    IfMatch=etag
)

print("\n=== Update Complete! ===")
print("CloudFront distribution configuration is updating. It will take a few minutes to propagate.")
