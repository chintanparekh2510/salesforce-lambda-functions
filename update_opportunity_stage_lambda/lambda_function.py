import json
import urllib.request
import urllib.parse
import urllib.error
import os

# Salesforce OAuth Configuration (from environment variables)
SALESFORCE_INSTANCE_URL = os.environ.get('SALESFORCE_INSTANCE_URL', 'https://nosoftware-speed-9330.my.salesforce.com')
CLIENT_ID = os.environ.get('SALESFORCE_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('SALESFORCE_CLIENT_SECRET', '')
TOKEN_URL = f"{SALESFORCE_INSTANCE_URL}/services/oauth2/token"

# Valid Opportunity Stages
VALID_STAGES = [
    "Pending",
    "Outreach",
    "Engaged",
    "Proposal",
    "Quote Follow-Up",
    "Finalizing",
    "Closed Won",
    "Closed Lost"
]


def get_access_token():
    """Authenticate with Salesforce using client_credentials flow."""
    data = urllib.parse.urlencode({
        'grant_type': 'client_credentials',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }).encode('utf-8')
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    req = urllib.request.Request(TOKEN_URL, data=data, headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('access_token'), result.get('instance_url', SALESFORCE_INSTANCE_URL)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        raise Exception(f"Failed to get access token: {e.code} - {error_body}")


def salesforce_api_call(method, endpoint, access_token, instance_url, data=None):
    """Make an API call to Salesforce."""
    url = f"{instance_url}/services/data/v59.0{endpoint}"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    body = json.dumps(data).encode('utf-8') if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 204:
                return None
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        raise Exception(f"Salesforce API error: {e.code} - {error_body}")


def get_opportunity(access_token, instance_url, opportunity_id):
    """Get Opportunity details."""
    result = salesforce_api_call(
        method='GET',
        endpoint=f'/sobjects/Opportunity/{opportunity_id}?fields=Id,Name,StageName',
        access_token=access_token,
        instance_url=instance_url
    )
    return result


def update_opportunity_stage(access_token, instance_url, opportunity_id, new_stage):
    """Update the Opportunity stage."""
    salesforce_api_call(
        method='PATCH',
        endpoint=f'/sobjects/Opportunity/{opportunity_id}',
        access_token=access_token,
        instance_url=instance_url,
        data={'StageName': new_stage}
    )
    return True


def lambda_handler(event, context):
    """
    AWS Lambda handler to get or update Opportunity stage.
    
    GET CURRENT STAGE (no stage provided):
    {
        "opportunity_id": "006XXXXXXXXXXXXXXX"
    }
    
    UPDATE STAGE:
    {
        "opportunity_id": "006XXXXXXXXXXXXXXX",
        "stage": "Engaged"
    }
    
    Valid stages:
    - Pending
    - Outreach
    - Engaged
    - Proposal
    - Quote Follow-Up
    - Finalizing
    - Closed Won
    - Closed Lost
    
    Returns:
    {
        "statusCode": 200,
        "body": {
            "success": true,
            "opportunity_id": "006XXXXXXXXXXXXXXX",
            "opportunity_name": "...",
            "current_stage": "Engaged",
            ...
        }
    }
    """
    try:
        opportunity_id = event.get('opportunity_id')
        new_stage = event.get('stage')
        
        # Validate required fields
        if not opportunity_id:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'success': False,
                    'error': 'opportunity_id is required'
                })
            }
        
        # Get access token
        access_token, instance_url = get_access_token()
        
        # Get current Opportunity details
        opp = get_opportunity(access_token, instance_url, opportunity_id)
        
        if not opp:
            return {
                'statusCode': 404,
                'body': json.dumps({
                    'success': False,
                    'error': f'Opportunity {opportunity_id} not found'
                })
            }
        
        current_stage = opp.get('StageName')
        opp_name = opp.get('Name')
        
        # If no stage provided, just return current stage (GET operation)
        if not new_stage:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'success': True,
                    'action': 'get',
                    'opportunity_id': opportunity_id,
                    'opportunity_name': opp_name,
                    'current_stage': current_stage,
                    'valid_stages': VALID_STAGES
                })
            }
        
        # Validate stage value for UPDATE operation
        if new_stage not in VALID_STAGES:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'success': False,
                    'error': f'Invalid stage: "{new_stage}"',
                    'valid_stages': VALID_STAGES
                })
            }
        
        # Check if already at the target stage
        if current_stage == new_stage:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'success': True,
                    'action': 'update',
                    'opportunity_id': opportunity_id,
                    'opportunity_name': opp_name,
                    'current_stage': new_stage,
                    'message': f'Opportunity is already at stage: {new_stage}'
                })
            }
        
        # Update the stage
        update_opportunity_stage(access_token, instance_url, opportunity_id, new_stage)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'action': 'update',
                'opportunity_id': opportunity_id,
                'opportunity_name': opp_name,
                'previous_stage': current_stage,
                'new_stage': new_stage,
                'message': f'Stage updated from "{current_stage}" to "{new_stage}"'
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }


# For local testing
if __name__ == "__main__":
    import sys
    
    # Default test opportunity
    test_opp_id = "006au000007dMheAAE"
    
    # Check command line args
    if len(sys.argv) > 1:
        test_opp_id = sys.argv[1]
    
    # GET current stage (no stage parameter)
    print("=" * 50)
    print("GET CURRENT STAGE:")
    print("=" * 50)
    get_event = {"opportunity_id": test_opp_id}
    result = lambda_handler(get_event, None)
    print(json.dumps(json.loads(result['body']), indent=2))
    
    # Example UPDATE (uncomment to test)
    # print("\n" + "=" * 50)
    # print("UPDATE STAGE:")
    # print("=" * 50)
    # update_event = {"opportunity_id": test_opp_id, "stage": "Engaged"}
    # result = lambda_handler(update_event, None)
    # print(json.dumps(json.loads(result['body']), indent=2))

