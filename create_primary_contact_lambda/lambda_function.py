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
    AWS Lambda handler to create a new contact for a given opportunity.
    
    Expected event structure:
    {
        "opportunity_id": "006XXXXXXXXXXXXXXX",  // Required
        "firstname": "John",                      // Optional
        "lastname": "Doe",                        // Required
        "email": "john.doe@example.com",          // Optional
        "primary": true                           // Optional (default: true)
    }
    
    Returns:
    {
        "statusCode": 200,
        "body": {
            "success": true,
            "contact_id": "003XXXXXXXXXXXXXXX",
            "opportunity_contact_role_id": "00KXXXXXXXXXXXXXXX",
            "is_primary": true,
            "message": "Primary contact created successfully"
        }
    }
    """
    try:
        # Parse event body (handles both direct invocation and Function URL)
        body = parse_event_body(event)
        
        # Get flat input parameters
        opportunity_id = body.get('opportunity_id')
        firstname = body.get('firstname', '')
        lastname = body.get('lastname', '')
        email = body.get('email', '')
        is_primary = body.get('primary', True)
        
        # Handle string "false" or "true" values
        if isinstance(is_primary, str):
            is_primary = is_primary.lower() == 'true'
        
        # Validate required fields
        if not opportunity_id:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'success': False,
                    'error': 'opportunity_id is required'
                })
            }
        
        if not lastname:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'success': False,
                    'error': 'lastname is required'
                })
            }
        
        # Build contact data
        contact_data = {
            'LastName': lastname
        }
        if firstname:
            contact_data['FirstName'] = firstname
        if email:
            contact_data['Email'] = email
        
        # Get access token
        access_token, instance_url = get_access_token()
        
        # Get the AccountId from the Opportunity to associate the Contact
        account_id, opp_name = get_opportunity_account(access_token, instance_url, opportunity_id)
        
        # Add AccountId to contact data if available
        if account_id:
            contact_data['AccountId'] = account_id
        
        # Create the Contact
        contact_id = create_contact(access_token, instance_url, contact_data)
        
        # Create OpportunityContactRole to link Contact
        ocr_id = create_opportunity_contact_role(
            access_token=access_token,
            instance_url=instance_url,
            opportunity_id=opportunity_id,
            contact_id=contact_id,
            is_primary=is_primary,
            role=None
        )
        
        # Build response message based on primary status
        contact_type = "Primary contact" if is_primary else "Contact"
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'contact_id': contact_id,
                'opportunity_contact_role_id': ocr_id,
                'opportunity_name': opp_name,
                'is_primary': is_primary,
                'message': f'{contact_type} created successfully for opportunity: {opp_name}'
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
        "firstname": "Jane",
        "lastname": "Smith",
        "email": "jane.smith@example.com",
        "primary": True  # Set to False to add as normal contact
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(json.loads(result['body']), indent=2))

