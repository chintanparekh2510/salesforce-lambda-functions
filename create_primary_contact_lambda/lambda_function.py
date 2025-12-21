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


def create_contact(access_token, instance_url, contact_data):
    """Create a new Contact in Salesforce."""
    result = salesforce_api_call(
        method='POST',
        endpoint='/sobjects/Contact',
        access_token=access_token,
        instance_url=instance_url,
        data=contact_data
    )
    return result.get('id')


def get_opportunity_account(access_token, instance_url, opportunity_id):
    """Get the AccountId from an Opportunity."""
    result = salesforce_api_call(
        method='GET',
        endpoint=f'/sobjects/Opportunity/{opportunity_id}?fields=AccountId,Name',
        access_token=access_token,
        instance_url=instance_url
    )
    return result.get('AccountId'), result.get('Name')


def create_opportunity_contact_role(access_token, instance_url, opportunity_id, contact_id, is_primary=True, role=None):
    """Create an OpportunityContactRole to link Contact to Opportunity."""
    role_data = {
        'OpportunityId': opportunity_id,
        'ContactId': contact_id,
        'IsPrimary': is_primary
    }
    
    if role:
        role_data['Role'] = role
    
    result = salesforce_api_call(
        method='POST',
        endpoint='/sobjects/OpportunityContactRole',
        access_token=access_token,
        instance_url=instance_url,
        data=role_data
    )
    return result.get('id')


def lambda_handler(event, context):
    """
    AWS Lambda handler to create a new primary contact for a given opportunity.
    
    Expected event structure:
    {
        "opportunity_id": "006XXXXXXXXXXXXXXX",
        "contact": {
            "FirstName": "John",
            "LastName": "Doe",
            "Email": "john.doe@example.com",
            "Phone": "555-1234",
            "Title": "CEO"
        },
        "role": "Decision Maker"  # Optional: Role for OpportunityContactRole
    }
    
    Returns:
    {
        "statusCode": 200,
        "body": {
            "success": true,
            "contact_id": "003XXXXXXXXXXXXXXX",
            "opportunity_contact_role_id": "00KXXXXXXXXXXXXXXX",
            "message": "Primary contact created successfully"
        }
    }
    """
    try:
        # Validate required fields
        opportunity_id = event.get('opportunity_id')
        contact_data = event.get('contact', {})
        role = event.get('role')
        
        if not opportunity_id:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'success': False,
                    'error': 'opportunity_id is required'
                })
            }
        
        if not contact_data.get('LastName'):
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'success': False,
                    'error': 'contact.LastName is required'
                })
            }
        
        # Get access token
        access_token, instance_url = get_access_token()
        
        # Get the AccountId from the Opportunity to associate the Contact
        account_id, opp_name = get_opportunity_account(access_token, instance_url, opportunity_id)
        
        # Add AccountId to contact data if available
        if account_id:
            contact_data['AccountId'] = account_id
        
        # Create the Contact
        contact_id = create_contact(access_token, instance_url, contact_data)
        
        # Create OpportunityContactRole to link Contact as Primary
        ocr_id = create_opportunity_contact_role(
            access_token=access_token,
            instance_url=instance_url,
            opportunity_id=opportunity_id,
            contact_id=contact_id,
            is_primary=True,
            role=role
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'contact_id': contact_id,
                'opportunity_contact_role_id': ocr_id,
                'opportunity_name': opp_name,
                'message': f'Primary contact created successfully for opportunity: {opp_name}'
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
    # Example test event
    test_event = {
        "opportunity_id": "006XXXXXXXXXXXXXXX",  # Replace with actual Opportunity ID
        "contact": {
            "FirstName": "Jane",
            "LastName": "Smith",
            "Email": "jane.smith@example.com",
            "Phone": "555-9876",
            "Title": "VP of Sales"
        },
        "role": "Decision Maker"
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(json.loads(result['body']), indent=2))

