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


def get_opportunity_with_account(access_token, instance_url, opportunity_id):
    """Get Opportunity with Account details including address."""
    query = f"""
        SELECT Id, Name, AccountId,
               Account.Id,
               Account.Name,
               Account.BillingStreet,
               Account.BillingCity,
               Account.BillingState,
               Account.BillingPostalCode,
               Account.BillingCountry,
               Account.ShippingStreet,
               Account.ShippingCity,
               Account.ShippingState,
               Account.ShippingPostalCode,
               Account.ShippingCountry,
               Account.Phone,
               Account.Website
        FROM Opportunity
        WHERE Id = '{opportunity_id}'
    """
    
    result = salesforce_query(access_token, instance_url, query)
    
    if result.get('records'):
        return result['records'][0]
    return None


def format_address(street, city, state, postal_code, country):
    """Format address components into a readable string."""
    parts = []
    if street:
        parts.append(street)
    
    city_state_zip = []
    if city:
        city_state_zip.append(city)
    if state:
        city_state_zip.append(state)
    if postal_code:
        city_state_zip.append(postal_code)
    
    if city_state_zip:
        parts.append(', '.join(city_state_zip))
    
    if country:
        parts.append(country)
    
    return '\n'.join(parts) if parts else None


def lambda_handler(event, context):
    """
    AWS Lambda handler to get Account address from Opportunity ID.
    
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
            "account_id": "001...",
            "account_name": "...",
            "billing_address": {...},
            "shipping_address": {...},
            "billing_address_formatted": "...",
            "shipping_address_formatted": "..."
        }
    }
    """
    try:
        opportunity_id = event.get('opportunity_id')
        
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
        
        # Get Opportunity with Account details
        opp = get_opportunity_with_account(access_token, instance_url, opportunity_id)
        
        if not opp:
            return {
                'statusCode': 404,
                'body': json.dumps({
                    'success': False,
                    'error': f'Opportunity {opportunity_id} not found'
                })
            }
        
        account = opp.get('Account') or {}
        
        if not account:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'success': True,
                    'opportunity_id': opportunity_id,
                    'opportunity_name': opp.get('Name'),
                    'account_id': None,
                    'account_name': None,
                    'message': 'No Account associated with this Opportunity'
                })
            }
        
        # Build billing address object
        billing_address = {
            'street': account.get('BillingStreet'),
            'city': account.get('BillingCity'),
            'state': account.get('BillingState'),
            'postal_code': account.get('BillingPostalCode'),
            'country': account.get('BillingCountry')
        }
        
        # Build shipping address object
        shipping_address = {
            'street': account.get('ShippingStreet'),
            'city': account.get('ShippingCity'),
            'state': account.get('ShippingState'),
            'postal_code': account.get('ShippingPostalCode'),
            'country': account.get('ShippingCountry')
        }
        
        # Format addresses as readable strings
        billing_formatted = format_address(
            billing_address['street'],
            billing_address['city'],
            billing_address['state'],
            billing_address['postal_code'],
            billing_address['country']
        )
        
        shipping_formatted = format_address(
            shipping_address['street'],
            shipping_address['city'],
            shipping_address['state'],
            shipping_address['postal_code'],
            shipping_address['country']
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'opportunity_id': opportunity_id,
                'opportunity_name': opp.get('Name'),
                'account_id': account.get('Id'),
                'account_name': account.get('Name'),
                'phone': account.get('Phone'),
                'website': account.get('Website'),
                'billing_address': billing_address,
                'billing_address_formatted': billing_formatted,
                'shipping_address': shipping_address,
                'shipping_address_formatted': shipping_formatted
            }, indent=2)
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


