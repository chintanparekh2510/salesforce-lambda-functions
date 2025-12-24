# Salesforce Lambda Functions

AWS Lambda functions for Salesforce integration - handles Opportunities, Contacts, Accounts, and Renewal validation.

## 🔗 Lambda Function URLs

| Function | URL |
|----------|-----|
| Get Account Address | `https://cjgg44a5kcl6nvtpo2ga2utbm40pibua.lambda-url.us-east-1.on.aws/` |
| Create Primary Contact | `https://pnftoxyldkuoefhr6gcxp27que0xzuda.lambda-url.us-east-1.on.aws/` |
| Opportunity Details | `https://ctbppan2hfcwrathbfot5fttim0vtqaq.lambda-url.us-east-1.on.aws/` |
| Update Opportunity Stage | `https://hdeh36q5q63qwxijz2tf7qjtku0hxgzt.lambda-url.us-east-1.on.aws/` |
| Validate Renewal | `https://yvbo5jb5d5vlanobzyqgb4qgvq0mjixu.lambda-url.us-east-1.on.aws/` |

---

## 📚 API Documentation

### 1. Get Account Address

**URL:** `https://cjgg44a5kcl6nvtpo2ga2utbm40pibua.lambda-url.us-east-1.on.aws/`

**Method:** POST

**Description:** Retrieves billing and shipping address for an Account linked to an Opportunity.

**Input Parameters:**
```json
{
    "opportunity_id": "006XXXXXXXXXXXXXXX"  // Required - Salesforce Opportunity ID
}
```

**Output:**
```json
{
    "statusCode": 200,
    "body": {
        "success": true,
        "opportunity_id": "006XXXXXXXXXXXXXXX",
        "opportunity_name": "Acme Corp Renewal",
        "account_id": "001XXXXXXXXXXXXXXX",
        "account_name": "Acme Corporation",
        "phone": "555-1234",
        "website": "https://acme.com",
        "billing_address": {
            "street": "123 Main St",
            "city": "San Francisco",
            "state": "CA",
            "postal_code": "94105",
            "country": "USA"
        },
        "billing_address_formatted": "123 Main St\nSan Francisco, CA, 94105\nUSA",
        "shipping_address": {
            "street": "456 Warehouse Ave",
            "city": "Oakland",
            "state": "CA",
            "postal_code": "94612",
            "country": "USA"
        },
        "shipping_address_formatted": "456 Warehouse Ave\nOakland, CA, 94612\nUSA"
    }
}
```

---

### 2. Create Contact

**URL:** `https://pnftoxyldkuoefhr6gcxp27que0xzuda.lambda-url.us-east-1.on.aws/`

**Method:** POST

**Description:** Creates a new Contact and links it to an Opportunity. Can be set as primary or normal contact.

**Input Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `opportunity_id` | string | Yes | Salesforce Opportunity ID |
| `firstname` | string | No | Contact's first name |
| `lastname` | string | Yes | Contact's last name |
| `email` | string | No | Contact's email address |
| `primary` | boolean | No | Set as primary contact (default: true) |

```json
{
    "opportunity_id": "006XXXXXXXXXXXXXXX",
    "firstname": "John",
    "lastname": "Doe",
    "email": "john.doe@example.com",
    "primary": true
}
```

**Output:**
```json
{
    "statusCode": 200,
    "body": {
        "success": true,
        "contact_id": "003XXXXXXXXXXXXXXX",
        "opportunity_contact_role_id": "00KXXXXXXXXXXXXXXX",
        "opportunity_name": "Acme Corp Renewal",
        "is_primary": true,
        "message": "Primary contact created successfully for opportunity: Acme Corp Renewal"
    }
}
```

---

### 3. Opportunity Details

**URL:** `https://ctbppan2hfcwrathbfot5fttim0vtqaq.lambda-url.us-east-1.on.aws/`

**Method:** POST

**Description:** Gets Contact Roles and NetSuite Subscription link for an Opportunity.

**Input Parameters:**
```json
{
    "opportunity_id": "006XXXXXXXXXXXXXXX"  // Required - Salesforce Opportunity ID
}
```

**Output:**
```json
{
    "statusCode": 200,
    "body": {
        "success": true,
        "opportunity_id": "006XXXXXXXXXXXXXXX",
        "opportunity_name": "Acme Corp Renewal",
        "contact_roles": [
            {
                "id": "00KXXXXXXXXXXXXXXX",
                "contact_id": "003XXXXXXXXXXXXXXX",
                "contact_name": "John Doe",
                "contact_email": "john.doe@example.com",
                "contact_phone": "555-1234",
                "contact_title": "CEO",
                "role": "Decision Maker",
                "is_primary": true
            }
        ],
        "netsuite_subscription": {
            "show": true,
            "label": "NetSuite Subscription",
            "url": "https://netsuite.com/sub/12345",
            "subscription_id": "12345"
        }
    }
}
```

---

### 4. Update Opportunity Stage

**URL:** `https://hdeh36q5q63qwxijz2tf7qjtku0hxgzt.lambda-url.us-east-1.on.aws/`

**Method:** POST

**Description:** Gets current stage or updates the Opportunity stage.

**Input Parameters:**
```json
{
    "opportunity_id": "006XXXXXXXXXXXXXXX",  // Required - Salesforce Opportunity ID
    "stage": "Engaged"                        // Optional - If omitted, returns current stage
}
```

**Valid Stages:**
- `Pending`
- `Outreach`
- `Engaged`
- `Proposal`
- `Quote Follow-Up`
- `Finalizing`
- `Closed Won`
- `Closed Lost`

**Output (GET - no stage provided):**
```json
{
    "statusCode": 200,
    "body": {
        "success": true,
        "action": "get",
        "opportunity_id": "006XXXXXXXXXXXXXXX",
        "opportunity_name": "Acme Corp Renewal",
        "current_stage": "Outreach",
        "valid_stages": ["Pending", "Outreach", "Engaged", "Proposal", "Quote Follow-Up", "Finalizing", "Closed Won", "Closed Lost"]
    }
}
```

**Output (UPDATE - stage provided):**
```json
{
    "statusCode": 200,
    "body": {
        "success": true,
        "action": "update",
        "opportunity_id": "006XXXXXXXXXXXXXXX",
        "opportunity_name": "Acme Corp Renewal",
        "previous_stage": "Outreach",
        "new_stage": "Engaged",
        "message": "Stage updated from \"Outreach\" to \"Engaged\""
    }
}
```

---

### 5. Validate Renewal

**URL:** `https://yvbo5jb5d5vlanobzyqgb4qgvq0mjixu.lambda-url.us-east-1.on.aws/`

**Method:** POST

**Description:** Validates a renewal opportunity against multiple criteria including NetSuite ID, Parent Subscription, Quotes, Upsells, Price Reset, Auto-Renewal, and Cancellation handling.

**Input Parameters:**
```json
{
    "opportunity_id": "006XXXXXXXXXXXXXXX"  // Required - Salesforce Opportunity ID
}
```

**Output:**
```json
{
    "statusCode": 200,
    "body": {
        "success": true,
        "opportunity_id": "006XXXXXXXXXXXXXXX",
        "validation": {
            "overall_status": "ALL GOOD",
            "total_checks": 10,
            "passed": 6,
            "failed": 0,
            "warnings": 2,
            "skipped": 2,
            "checks": [
                {
                    "name": "Opportunity Found",
                    "status": "INFO",
                    "message": "Validating: Acme Corp Renewal",
                    "details": {
                        "Stage": "Proposal",
                        "Amount": 50000,
                        "Close Date": "2025-03-15"
                    }
                },
                {
                    "name": "O2C - NetSuite ID",
                    "status": "PASS",
                    "message": "NetSuite ID is populated: 12345"
                },
                {
                    "name": "Parent Subscription ID",
                    "status": "PASS",
                    "message": "Parent Subscription is valid: SUB-001"
                },
                {
                    "name": "Renewal Data vs Signed Quote",
                    "status": "PASS",
                    "message": "Opportunity amount matches signed quote"
                },
                {
                    "name": "Upsells in Current Term",
                    "status": "PASS",
                    "message": "No open upsell/expansion opportunities found"
                },
                {
                    "name": "Price Reset Checkbox",
                    "status": "SKIP",
                    "message": "Not a Price Reset opportunity"
                },
                {
                    "name": "Auto-Renewed Last Term",
                    "status": "INFO",
                    "message": "Auto-Renewed Last Term: No"
                },
                {
                    "name": "Cancellation Handling",
                    "status": "SKIP",
                    "message": "Customer did not send cancellation"
                },
                {
                    "name": "Auto-Renewal Clause",
                    "status": "SKIP",
                    "message": "Previous quote does not have AR clause"
                },
                {
                    "name": "Field Discovery",
                    "status": "INFO",
                    "message": "Found 8 of 11 expected custom fields"
                }
            ]
        }
    }
}
```

**Validation Check Statuses:**
- `PASS` - Check passed successfully
- `FAIL` - Check failed, action required
- `WARNING` - Potential issue, review recommended
- `SKIP` - Check not applicable
- `INFO` - Informational only

---

## 📝 Example cURL Requests

```bash
# Get Account Address
curl -X POST https://cjgg44a5kcl6nvtpo2ga2utbm40pibua.lambda-url.us-east-1.on.aws/ \
  -H "Content-Type: application/json" \
  -d '{"opportunity_id": "006au000007dMheAAE"}'

# Create Primary Contact
curl -X POST https://pnftoxyldkuoefhr6gcxp27que0xzuda.lambda-url.us-east-1.on.aws/ \
  -H "Content-Type: application/json" \
  -d '{"opportunity_id": "006au000007dMheAAE", "contact": {"FirstName": "Jane", "LastName": "Smith", "Email": "jane@example.com"}, "role": "Decision Maker"}'

# Get Opportunity Details
curl -X POST https://ctbppan2hfcwrathbfot5fttim0vtqaq.lambda-url.us-east-1.on.aws/ \
  -H "Content-Type: application/json" \
  -d '{"opportunity_id": "006au000007dMheAAE"}'

# Get Current Stage
curl -X POST https://hdeh36q5q63qwxijz2tf7qjtku0hxgzt.lambda-url.us-east-1.on.aws/ \
  -H "Content-Type: application/json" \
  -d '{"opportunity_id": "006au000007dMheAAE"}'

# Update Opportunity Stage
curl -X POST https://hdeh36q5q63qwxijz2tf7qjtku0hxgzt.lambda-url.us-east-1.on.aws/ \
  -H "Content-Type: application/json" \
  -d '{"opportunity_id": "006au000007dMheAAE", "stage": "Engaged"}'

# Validate Renewal
curl -X POST https://yvbo5jb5d5vlanobzyqgb4qgvq0mjixu.lambda-url.us-east-1.on.aws/ \
  -H "Content-Type: application/json" \
  -d '{"opportunity_id": "006au000007dMheAAE"}'
```

---

## 🏗️ Project Structure

```
├── create_primary_contact_lambda/
│   └── lambda_function.py
├── get_account_address_lambda/
│   └── lambda_function.py
├── opportunity_details_lambda/
│   └── lambda_function.py
├── update_opportunity_stage_lambda/
│   └── lambda_function.py
├── validate_renewal_lambda/
│   └── lambda_function.py
└── README.md
```

---

## ⚙️ Deployment

All functions are deployed to AWS Lambda in `us-east-1` region with:
- **Runtime:** Python 3.11
- **Role:** `fionn-dashboard-lambda-role`
- **Timeout:** 30-60 seconds
- **Memory:** 128-256 MB

## 🔐 Environment Variables

Each Lambda function requires the following environment variables:

| Variable | Description |
|----------|-------------|
| `SALESFORCE_INSTANCE_URL` | Salesforce instance URL (e.g., `https://your-org.my.salesforce.com`) |
| `SALESFORCE_CLIENT_ID` | Connected App Consumer Key |
| `SALESFORCE_CLIENT_SECRET` | Connected App Consumer Secret |

### Setting Environment Variables via AWS CLI

```bash
aws lambda update-function-configuration \
  --function-name salesforce-get-account-address \
  --environment "Variables={SALESFORCE_INSTANCE_URL=https://your-org.my.salesforce.com,SALESFORCE_CLIENT_ID=your-client-id,SALESFORCE_CLIENT_SECRET=your-client-secret}"
```

