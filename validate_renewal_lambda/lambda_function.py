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


def salesforce_get(access_token, instance_url, endpoint):
    """Make a GET request to Salesforce."""
    url = f"{instance_url}/services/data/v59.0{endpoint}"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    req = urllib.request.Request(url, headers=headers, method='GET')
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        error_body = e.read().decode('utf-8')
        raise Exception(f"Salesforce API error: {e.code} - {error_body}")


def describe_object(access_token, instance_url, object_name):
    """Get the describe for an object to find available fields."""
    return salesforce_get(access_token, instance_url, f"/sobjects/{object_name}/describe")


def get_opportunity_fields(access_token, instance_url):
    """Get all field names for Opportunity object."""
    describe = describe_object(access_token, instance_url, "Opportunity")
    if describe:
        return [field['name'] for field in describe.get('fields', [])]
    return []


class ValidationResult:
    def __init__(self):
        self.checks = []
        self.has_issues = False
    
    def add_check(self, name, status, message, details=None):
        """Add a validation check result."""
        check = {
            'name': name,
            'status': status,  # 'PASS', 'FAIL', 'WARNING', 'SKIP', 'INFO'
            'message': message
        }
        if details:
            check['details'] = details
        
        self.checks.append(check)
        
        if status in ['FAIL', 'WARNING']:
            self.has_issues = True
    
    def to_dict(self):
        return {
            'overall_status': 'ISSUES FOUND' if self.has_issues else 'ALL GOOD',
            'total_checks': len(self.checks),
            'passed': len([c for c in self.checks if c['status'] == 'PASS']),
            'failed': len([c for c in self.checks if c['status'] == 'FAIL']),
            'warnings': len([c for c in self.checks if c['status'] == 'WARNING']),
            'skipped': len([c for c in self.checks if c['status'] == 'SKIP']),
            'checks': self.checks
        }


def validate_renewal_opportunity(access_token, instance_url, opportunity_id):
    """Validate a renewal opportunity against all criteria."""
    
    result = ValidationResult()
    
    # First, get the Opportunity fields available
    opp_fields = get_opportunity_fields(access_token, instance_url)
    
    # Build dynamic query based on available fields
    # Standard fields we always query
    base_fields = ['Id', 'Name', 'StageName', 'AccountId', 'Amount', 'CloseDate', 'Type', 'IsClosed', 'IsWon']
    
    # Custom fields we're looking for (with various possible naming conventions)
    custom_field_mappings = {
        'netsuite_id': ['NetSuite_ID__c', 'NetSuiteID__c', 'Netsuite_Id__c', 'NS_ID__c', 'NetSuite_Internal_ID__c'],
        'parent_sub_id': ['Parent_Subscription_ID__c', 'Parent_Sub_ID__c', 'ParentSubscriptionId__c', 'Parent_Subscription__c'],
        'price_reset': ['Price_Reset__c', 'Is_Price_Reset__c', 'PriceReset__c'],
        'auto_renewed_last_term': ['Auto_Renewed_Last_Term__c', 'AutoRenewedLastTerm__c', 'Auto_Renewal_Last_Term__c'],
        'cancelled_before_renewal': ['Cancelled_before_Renewal_Cycle__c', 'Cancelled_Before_Renewal__c', 'CancelledBeforeRenewal__c'],
        'cancellation_notice': ['Cancellation_Notice__c', 'CancellationNotice__c', 'Cancellation_Notice_Link__c'],
        'auto_renewal_clause': ['Auto_Renewal_Clause__c', 'AutoRenewalClause__c', 'AR_Clause__c'],
        'prev_quote_ar_clause': ['Prev_Quote_w_AR_Clause__c', 'Previous_Quote_AR_Clause__c', 'Prev_Quote_AR__c'],
        'o2c_processed': ['O2C_Processed__c', 'Processed_via_O2C__c', 'O2C__c'],
        'subscription_id': ['SBQQ__RenewedContract__c', 'Subscription__c', 'Subscription_ID__c', 'CPQ_Subscription__c'],
        'previous_quote': ['Previous_Quote__c', 'Prev_Quote__c', 'Prior_Quote__c', 'SBQQ__RenewedQuote__c'],
    }
    
    # Find which custom fields actually exist
    found_fields = {}
    for field_key, possible_names in custom_field_mappings.items():
        for field_name in possible_names:
            if field_name in opp_fields:
                found_fields[field_key] = field_name
                break
    
    # Build query with available fields
    query_fields = base_fields.copy()
    query_fields.extend(found_fields.values())
    
    # Query the Opportunity
    opp_query = f"SELECT {', '.join(query_fields)} FROM Opportunity WHERE Id = '{opportunity_id}'"
    opp_result = salesforce_query(access_token, instance_url, opp_query)
    
    if not opp_result.get('records'):
        result.add_check("Opportunity Exists", "FAIL", f"Opportunity {opportunity_id} not found")
        return result
    
    opp = opp_result['records'][0]
    
    result.add_check("Opportunity Found", "INFO", f"Validating: {opp.get('Name')}", {
        'Stage': opp.get('StageName'),
        'Amount': opp.get('Amount'),
        'Close Date': opp.get('CloseDate')
    })
    
    # ============================================
    # CHECK 1: NetSuite ID (if O2C processed)
    # ============================================
    o2c_field = found_fields.get('o2c_processed')
    netsuite_field = found_fields.get('netsuite_id')
    
    if o2c_field:
        is_o2c = opp.get(o2c_field)
        if is_o2c:
            if netsuite_field:
                netsuite_id = opp.get(netsuite_field)
                if netsuite_id:
                    # TODO: Could add NetSuite API validation here
                    result.add_check(
                        "O2C - NetSuite ID", 
                        "PASS", 
                        f"NetSuite ID is populated: {netsuite_id}",
                        {"NetSuite_ID": netsuite_id}
                    )
                else:
                    result.add_check(
                        "O2C - NetSuite ID", 
                        "FAIL", 
                        "O2C processed but NetSuite ID is missing - should point to valid draft Renewal sub"
                    )
            else:
                result.add_check(
                    "O2C - NetSuite ID", 
                    "WARNING", 
                    f"NetSuite ID field not found. Looked for: {custom_field_mappings['netsuite_id']}"
                )
        else:
            result.add_check("O2C - NetSuite ID", "SKIP", "Not processed via O2C")
    else:
        result.add_check(
            "O2C - NetSuite ID", 
            "SKIP", 
            f"O2C field not found. Looked for: {custom_field_mappings['o2c_processed']}"
        )
    
    # ============================================
    # CHECK 2: Parent Subscription ID
    # ============================================
    parent_sub_field = found_fields.get('parent_sub_id')
    
    if parent_sub_field:
        parent_sub_id = opp.get(parent_sub_field)
        if parent_sub_id:
            # Try to validate the subscription exists
            sub_query = f"SELECT Id, Name, SBQQ__Contract__c FROM SBQQ__Subscription__c WHERE Id = '{parent_sub_id}' LIMIT 1"
            try:
                sub_result = salesforce_query(access_token, instance_url, sub_query)
                if sub_result.get('records'):
                    sub = sub_result['records'][0]
                    result.add_check(
                        "Parent Subscription ID", 
                        "PASS", 
                        f"Parent Subscription is valid: {sub.get('Name', parent_sub_id)}",
                        {"Subscription_ID": parent_sub_id}
                    )
                else:
                    result.add_check(
                        "Parent Subscription ID", 
                        "FAIL", 
                        f"Parent Subscription ID {parent_sub_id} not found in system"
                    )
            except Exception as e:
                result.add_check(
                    "Parent Subscription ID", 
                    "WARNING", 
                    f"Could not validate subscription: {str(e)}",
                    {"Parent_Sub_ID": parent_sub_id}
                )
        else:
            result.add_check(
                "Parent Subscription ID", 
                "FAIL", 
                "Parent Subscription ID is not populated"
            )
    else:
        result.add_check(
            "Parent Subscription ID", 
            "WARNING", 
            f"Parent Sub ID field not found. Looked for: {custom_field_mappings['parent_sub_id']}"
        )
    
    # ============================================
    # CHECK 3: Validate Renewal Data Against Signed Quote
    # ============================================
    prev_quote_field = found_fields.get('previous_quote')
    
    # Query for quotes related to this opportunity
    quote_query = f"""
        SELECT Id, Name, SBQQ__Status__c, SBQQ__NetAmount__c, SBQQ__StartDate__c, SBQQ__EndDate__c 
        FROM SBQQ__Quote__c 
        WHERE SBQQ__Opportunity2__c = '{opportunity_id}' 
        ORDER BY CreatedDate DESC
    """
    try:
        quotes_result = salesforce_query(access_token, instance_url, quote_query)
        quotes = quotes_result.get('records', [])
        
        if quotes:
            signed_quotes = [q for q in quotes if q.get('SBQQ__Status__c') in ['Accepted', 'Signed', 'Approved']]
            
            if signed_quotes:
                signed_quote = signed_quotes[0]
                quote_amount = signed_quote.get('SBQQ__NetAmount__c')
                opp_amount = opp.get('Amount')
                
                if quote_amount and opp_amount:
                    if abs(float(quote_amount) - float(opp_amount)) < 0.01:
                        result.add_check(
                            "Renewal Data vs Signed Quote",
                            "PASS",
                            f"Opportunity amount matches signed quote",
                            {
                                "Quote": signed_quote.get('Name'),
                                "Quote_Amount": quote_amount,
                                "Opp_Amount": opp_amount
                            }
                        )
                    else:
                        result.add_check(
                            "Renewal Data vs Signed Quote",
                            "WARNING",
                            f"Amount mismatch between Opp ({opp_amount}) and Quote ({quote_amount})",
                            {
                                "Quote": signed_quote.get('Name'),
                                "Quote_Amount": quote_amount,
                                "Opp_Amount": opp_amount,
                                "Difference": abs(float(quote_amount) - float(opp_amount))
                            }
                        )
                else:
                    result.add_check(
                        "Renewal Data vs Signed Quote",
                        "INFO",
                        f"Signed quote found: {signed_quote.get('Name')}",
                        {"Quote_Status": signed_quote.get('SBQQ__Status__c')}
                    )
            else:
                result.add_check(
                    "Renewal Data vs Signed Quote",
                    "WARNING",
                    f"No signed/accepted quote found. {len(quotes)} quote(s) in other statuses.",
                    {"Available_Quotes": [q.get('Name') for q in quotes[:5]]}
                )
        else:
            result.add_check(
                "Renewal Data vs Signed Quote",
                "WARNING",
                "No quotes found for this opportunity"
            )
    except Exception as e:
        result.add_check(
            "Renewal Data vs Signed Quote",
            "SKIP",
            f"Could not query quotes: {str(e)}"
        )
    
    # ============================================
    # CHECK 4: Upsells in Current Term
    # ============================================
    account_id = opp.get('AccountId')
    if account_id:
        upsell_query = f"""
            SELECT Id, Name, Amount, StageName, Type, CloseDate 
            FROM Opportunity 
            WHERE AccountId = '{account_id}' 
            AND Id != '{opportunity_id}'
            AND (Type LIKE '%Upsell%' OR Type LIKE '%Expansion%' OR Type LIKE '%Add-on%')
            AND IsClosed = false
            ORDER BY CloseDate DESC
            LIMIT 10
        """
        try:
            upsell_result = salesforce_query(access_token, instance_url, upsell_query)
            upsells = upsell_result.get('records', [])
            
            if upsells:
                result.add_check(
                    "Upsells in Current Term",
                    "WARNING",
                    f"Found {len(upsells)} open upsell/expansion opportunities - ensure they're included in renewal",
                    {
                        "Upsells": [
                            {
                                "Name": u.get('Name'),
                                "Amount": u.get('Amount'),
                                "Stage": u.get('StageName'),
                                "Close_Date": u.get('CloseDate')
                            } for u in upsells
                        ]
                    }
                )
            else:
                result.add_check(
                    "Upsells in Current Term",
                    "PASS",
                    "No open upsell/expansion opportunities found"
                )
        except Exception as e:
            result.add_check(
                "Upsells in Current Term",
                "SKIP",
                f"Could not query upsells: {str(e)}"
            )
    
    # ============================================
    # CHECK 5: Price Reset Opportunity
    # ============================================
    price_reset_field = found_fields.get('price_reset')
    
    # Check if this looks like a price reset opp (by name or type)
    opp_name = opp.get('Name', '').lower()
    is_likely_price_reset = 'price reset' in opp_name or 'price-reset' in opp_name
    
    if price_reset_field:
        price_reset_checked = opp.get(price_reset_field)
        
        if is_likely_price_reset:
            if price_reset_checked:
                result.add_check(
                    "Price Reset Checkbox",
                    "PASS",
                    "Price Reset checkbox is checked"
                )
            else:
                result.add_check(
                    "Price Reset Checkbox",
                    "FAIL",
                    "This appears to be a Price Reset opportunity but checkbox is NOT checked"
                )
        else:
            if price_reset_checked:
                result.add_check(
                    "Price Reset Checkbox",
                    "INFO",
                    "Price Reset checkbox is checked"
                )
            else:
                result.add_check(
                    "Price Reset Checkbox",
                    "SKIP",
                    "Not a Price Reset opportunity"
                )
    else:
        result.add_check(
            "Price Reset Checkbox",
            "SKIP",
            f"Price Reset field not found. Looked for: {custom_field_mappings['price_reset']}"
        )
    
    # ============================================
    # CHECK 6: Auto-Renewed Last Term
    # ============================================
    auto_renewed_field = found_fields.get('auto_renewed_last_term')
    
    if auto_renewed_field:
        auto_renewed = opp.get(auto_renewed_field)
        result.add_check(
            "Auto-Renewed Last Term",
            "INFO",
            f"Auto-Renewed Last Term: {'Yes' if auto_renewed else 'No'}",
            {"Value": auto_renewed}
        )
    else:
        result.add_check(
            "Auto-Renewed Last Term",
            "SKIP",
            f"Field not found. Looked for: {custom_field_mappings['auto_renewed_last_term']}"
        )
    
    # ============================================
    # CHECK 7: Cancellation Handling
    # ============================================
    cancelled_field = found_fields.get('cancelled_before_renewal')
    cancellation_notice_field = found_fields.get('cancellation_notice')
    
    is_lost = opp.get('StageName', '').lower() in ['closed lost', 'lost', 'cancelled']
    
    if cancelled_field:
        cancelled_before_renewal = opp.get(cancelled_field)
        
        if cancelled_before_renewal:
            issues = []
            details = {"Cancelled_Before_Renewal": True}
            
            # Check if cancellation notice is attached
            if cancellation_notice_field:
                notice = opp.get(cancellation_notice_field)
                if notice:
                    details["Cancellation_Notice"] = notice
                else:
                    issues.append("Cancellation Notice not attached")
            
            # Check if Lost button was used (stage should be Closed Lost)
            if not is_lost:
                issues.append(f"Stage is '{opp.get('StageName')}' - should use Lost Button")
            else:
                details["Stage"] = opp.get('StageName')
            
            if issues:
                result.add_check(
                    "Cancellation Handling",
                    "FAIL",
                    f"Cancellation issues: {'; '.join(issues)}",
                    details
                )
            else:
                result.add_check(
                    "Cancellation Handling",
                    "PASS",
                    "Cancellation properly documented",
                    details
                )
        else:
            result.add_check(
                "Cancellation Handling",
                "SKIP",
                "Customer did not send cancellation"
            )
    else:
        result.add_check(
            "Cancellation Handling",
            "SKIP",
            f"Cancellation field not found. Looked for: {custom_field_mappings['cancelled_before_renewal']}"
        )
    
    # ============================================
    # CHECK 8: Auto-Renewal Clause from Previous Quote
    # ============================================
    ar_clause_field = found_fields.get('auto_renewal_clause')
    prev_quote_ar_field = found_fields.get('prev_quote_ar_clause')
    
    if ar_clause_field:
        has_ar_clause = opp.get(ar_clause_field)
        
        if has_ar_clause:
            if prev_quote_ar_field:
                prev_quote_link = opp.get(prev_quote_ar_field)
                if prev_quote_link:
                    result.add_check(
                        "Auto-Renewal Clause",
                        "PASS",
                        "AR Clause checked and previous quote link provided",
                        {
                            "AR_Clause": True,
                            "Prev_Quote_Link": prev_quote_link
                        }
                    )
                else:
                    result.add_check(
                        "Auto-Renewal Clause",
                        "FAIL",
                        "AR Clause is checked but 'Prev Quote w/ AR Clause' link is missing"
                    )
            else:
                result.add_check(
                    "Auto-Renewal Clause",
                    "WARNING",
                    "AR Clause is checked. Could not verify prev quote link field.",
                    {"AR_Clause": True}
                )
        else:
            result.add_check(
                "Auto-Renewal Clause",
                "SKIP",
                "Previous quote does not have AR clause"
            )
    else:
        result.add_check(
            "Auto-Renewal Clause",
            "SKIP",
            f"AR Clause field not found. Looked for: {custom_field_mappings['auto_renewal_clause']}"
        )
    
    # ============================================
    # SUMMARY: Available Custom Fields
    # ============================================
    result.add_check(
        "Field Discovery",
        "INFO",
        f"Found {len(found_fields)} of {len(custom_field_mappings)} expected custom fields",
        {
            "Found_Fields": found_fields,
            "Missing_Fields": [k for k in custom_field_mappings.keys() if k not in found_fields]
        }
    )
    
    return result


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
    AWS Lambda handler to validate a renewal opportunity.
    
    Expected event structure:
    {
        "opportunity_id": "006XXXXXXXXXXXXXXX"
    }
    
    Returns detailed validation report.
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
        
        # Run validation
        validation_result = validate_renewal_opportunity(access_token, instance_url, opportunity_id)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'opportunity_id': opportunity_id,
                'validation': validation_result.to_dict()
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
        "opportunity_id": "006XXXXXXXXXXXXXXX"  # Replace with actual ID
    }
    
    result = lambda_handler(test_event, None)
    print(result['body'])

