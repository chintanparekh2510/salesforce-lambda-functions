import json
import urllib.request
import urllib.parse
import urllib.error
import os
from decimal import Decimal


def convert_floats_to_strings(obj):
    """Recursively convert all float/Decimal values to strings for Bedrock compatibility."""
    if isinstance(obj, dict):
        return {key: convert_floats_to_strings(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_strings(item) for item in obj]
    elif isinstance(obj, (float, Decimal)):
        return str(obj)
    else:
        return obj

# Salesforce OAuth Configuration (from environment variables)
SALESFORCE_INSTANCE_URL = os.environ.get('SALESFORCE_INSTANCE_URL', 'https://nosoftware-speed-9330.my.salesforce.com')
CLIENT_ID = os.environ.get('SALESFORCE_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('SALESFORCE_CLIENT_SECRET', '')
TOKEN_URL = f"{SALESFORCE_INSTANCE_URL}/services/oauth2/token"


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


def salesforce_query(access_token, instance_url, soql):
    """Execute a SOQL query."""
    encoded_query = urllib.parse.quote(soql)
    url = f"{instance_url}/services/data/v59.0/query?q={encoded_query}"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    req = urllib.request.Request(url, headers=headers, method='GET')
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        raise Exception(f"SOQL query error: {e.code} - {error_body}")


def get_opportunity_currency(access_token, instance_url, opportunity_id):
    """Get currency information for an Opportunity."""
    query = f"""
        SELECT Id, Name, CurrencyIsoCode, Amount
        FROM Opportunity
        WHERE Id = '{opportunity_id}'
    """
    
    result = salesforce_query(access_token, instance_url, query)
    
    if result.get('records'):
        return result['records'][0]
    return None


def parse_event_body(event):
    """Parse event body for both direct invocation and Function URL calls."""
    # If called via Function URL, body is a JSON string
    if 'body' in event and isinstance(event.get('body'), str):
        try:
            return json.loads(event['body'])
        except json.JSONDecodeError:
            return {}
    # Direct invocation - event is the payload
    return event


def lambda_handler(event, context):
    """
    AWS Lambda handler to get Opportunity currency based on Opportunity ID.
    
    Expected event structure:
    {
        "opportunity_id": "006XXXXXXXXXXXXXXX"
    }
    
    Returns:
    {
        "statusCode": 200,
        "body": {
            "success": true,
            "opportunity_id": "006...",
            "opportunity_name": "...",
            "currency_iso_code": "USD",
            "amount": 50000.00
        }
    }
    """
    try:
        # Parse event body (handles both direct invocation and Function URL)
        body = parse_event_body(event)
        opportunity_id = body.get('opportunity_id')
        
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
        
        # Get Opportunity currency details
        opp = get_opportunity_currency(access_token, instance_url, opportunity_id)
        
        if not opp:
            return {
                'statusCode': 404,
                'body': json.dumps({
                    'success': False,
                    'error': f'Opportunity {opportunity_id} not found'
                })
            }
        
        # Convert amount to string for Bedrock Agent compatibility
        amount = opp.get('Amount')
        if amount is not None:
            amount = str(float(amount))
        
        response_data = {
            'success': True,
            'opportunity_id': opp.get('Id'),
            'opportunity_name': opp.get('Name'),
            'currency_iso_code': opp.get('CurrencyIsoCode'),
            'amount': amount
        }
        
        # Convert all floats to strings for Bedrock compatibility
        response_data = convert_floats_to_strings(response_data)
        
        return {
            'statusCode': 200,
            'body': json.dumps(response_data, indent=2)
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
    test_event = {
        "opportunity_id": "006au000007dMheAAE"
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(json.loads(result['body']), indent=2))

