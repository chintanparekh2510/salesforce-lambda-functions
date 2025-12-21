import json
import sys
import io

# Fix encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from lambda_function import lambda_handler

# Test with the opportunity from earlier
test_event = {
    "opportunity_id": "006au000007dMheAAE"
}

print("=" * 70)
print("RENEWAL OPPORTUNITY VALIDATION REPORT")
print("=" * 70)
print(f"\nOpportunity ID: {test_event['opportunity_id']}\n")

result = lambda_handler(test_event, None)
response = json.loads(result['body'])

if response.get('success'):
    validation = response['validation']
    
    print(f"{'=' * 70}")
    print(f"OVERALL STATUS: {validation['overall_status']}")
    print(f"{'=' * 70}")
    print(f"\nPassed: {validation['passed']} | Failed: {validation['failed']} | Warnings: {validation['warnings']} | Skipped: {validation['skipped']}")
    print(f"\n{'-' * 70}")
    print("DETAILED CHECKS:")
    print(f"{'-' * 70}\n")
    
    status_icons = {
        'PASS': '[OK]',
        'FAIL': '[X]',
        'WARNING': '[!]',
        'SKIP': '[-]',
        'INFO': '[i]'
    }
    
    for check in validation['checks']:
        icon = status_icons.get(check['status'], '*')
        print(f"{icon} [{check['status']}] {check['name']}")
        print(f"   {check['message']}")
        if check.get('details'):
            for key, value in check['details'].items():
                if isinstance(value, list):
                    print(f"   * {key}:")
                    for item in value[:3]:  # Show first 3
                        if isinstance(item, dict):
                            print(f"     - {item}")
                        else:
                            print(f"     - {item}")
                    if len(value) > 3:
                        print(f"     ... and {len(value) - 3} more")
                else:
                    print(f"   * {key}: {value}")
        print()
else:
    print(f"ERROR: {response.get('error')}")

print("=" * 70)
