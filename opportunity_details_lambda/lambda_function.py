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


def get_opportunity_contact_roles(access_token, instance_url, opportunity_id):
    """Get all Contact Roles for an Opportunity."""
    query = f"""
        SELECT Id, ContactId, Contact.Name, Contact.Email, Contact.Phone, 
               Contact.Title, Role, IsPrimary 
        FROM OpportunityContactRole 
        WHERE OpportunityId = '{opportunity_id}'
        ORDER BY IsPrimary DESC
    """
    encoded_query = urllib.parse.quote(query)
    
    result = salesforce_api_call(
        method='GET',
        endpoint=f'/query?q={encoded_query}',
        access_token=access_token,
        instance_url=instance_url
    )
    
    contact_roles = []
    for record in result.get('records', []):
        contact = record.get('Contact', {}) or {}
        contact_roles.append({
            'id': record.get('Id'),
            'contact_id': record.get('ContactId'),
            'contact_name': contact.get('Name'),
            'contact_email': contact.get('Email'),
            'contact_phone': contact.get('Phone'),
            'contact_title': contact.get('Title'),
            'role': record.get('Role'),
            'is_primary': record.get('IsPrimary')
        })
    
    return contact_roles


def extract_url_from_html(html_string):
    """Extract URL from HTML anchor tag."""
    if not html_string:
        return None, None
    
    import re
    # Match href="..." and link text
    href_match = re.search(r'href=["\']([^"\']+)["\']', html_string)
    text_match = re.search(r'>([^<]+)<', html_string)
    
    url = href_match.group(1) if href_match else None
    text = text_match.group(1) if text_match else None
    
    return url, text


def get_opportunity_netsuite_link(access_token, instance_url, opportunity_id):
    """Get the NetSuite Sub Link field from Opportunity."""
    query = f"""
        SELECT Id, Name, NetSuite_Sub_Link__c
        FROM Opportunity 
        WHERE Id = '{opportunity_id}'
    """
    encoded_query = urllib.parse.quote(query)
    
    try:
        result = salesforce_api_call(
            method='GET',
            endpoint=f'/query?q={encoded_query}',
            access_token=access_token,
            instance_url=instance_url
        )
        
        if result.get('records'):
            record = result['records'][0]
            raw_link = record.get('NetSuite_Sub_Link__c')
            url, subscription_id = extract_url_from_html(raw_link)
            
            return {
                'opportunity_id': record.get('Id'),
                'opportunity_name': record.get('Name'),
                'netsuite_sub_link_raw': raw_link,
                'netsuite_sub_url': url,
                'netsuite_subscription_id': subscription_id
            }
    except Exception as e:
        raise e
    
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
    AWS Lambda handler to get Opportunity Contact Roles and NetSuite Sub Link.
    
    Expected event structure:
    {
        "opportunity_id": "006XXXXXXXXXXXXXXX"
    }
    
    Returns:
    {
        "statusCode": 200,
        "body": {
            "success": true,
            "opportunity_name": "...",
            "contact_roles": [...],
            "netsuite_subscription": {
                "show": true/false,
                "label": "NetSuite Subscription",
                "url": "https://..."
            }
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
        
        # Get Contact Roles
        contact_roles = get_opportunity_contact_roles(access_token, instance_url, opportunity_id)
        
        # Get NetSuite Sub Link
        opp_data = get_opportunity_netsuite_link(access_token, instance_url, opportunity_id)
        
        # Format NetSuite Subscription for UI
        netsuite_url = opp_data.get('netsuite_sub_url') if opp_data else None
        subscription_id = opp_data.get('netsuite_subscription_id') if opp_data else None
        
        # If URL exists, show as "NetSuite Subscription" link; if blank, remove it
        if netsuite_url and netsuite_url.strip():
            netsuite_subscription = {
                'show': True,
                'label': 'NetSuite Subscription',
                'url': netsuite_url,
                'subscription_id': subscription_id
            }
        else:
            netsuite_subscription = None  # Remove from UI if blank
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'opportunity_id': opportunity_id,
                'opportunity_name': opp_data.get('opportunity_name') if opp_data else None,
                'contact_roles': contact_roles,
                'netsuite_subscription': netsuite_subscription
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

