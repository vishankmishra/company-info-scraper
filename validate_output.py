#!/usr/bin/env python3
"""
Validation script to check CSV output quality
Focuses on Customers, Partnerships, and Case Studies extraction
"""

import csv
import sys
import argparse
from pathlib import Path


def validate_csv(csv_file: str):
    """Validate CSV output file"""
    if not Path(csv_file).exists():
        print(f"Error: File not found: {csv_file}")
        return False
    
    required_fields = ['url', 'products', 'services', 'customers', 'partnerships', 'case_studies', 'extraction_status']
    
    issues = []
    stats = {
        'total_records': 0,
        'has_products': 0,
        'has_services': 0,
        'has_customers': 0,
        'has_partnerships': 0,
        'has_case_studies': 0,
        'all_fields_populated': 0,
        'extraction_success': 0,
        'extraction_failure': 0
    }
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                stats['total_records'] += 1
                
                # Check required fields
                missing_fields = [field for field in required_fields if field not in row]
                if missing_fields:
                    issues.append(f"Row {stats['total_records']}: Missing fields: {missing_fields}")
                
                # Check data quality
                if row.get('products') and row.get('products') != 'N/A':
                    stats['has_products'] += 1
                
                if row.get('services') and row.get('services') != 'N/A':
                    stats['has_services'] += 1
                
                if row.get('customers') and row.get('customers') != 'N/A':
                    stats['has_customers'] += 1
                
                if row.get('partnerships') and row.get('partnerships') != 'N/A':
                    stats['has_partnerships'] += 1
                
                if row.get('case_studies') and row.get('case_studies') != 'N/A':
                    stats['has_case_studies'] += 1
                
                # Check if all critical fields are populated
                critical_fields = ['customers', 'partnerships', 'case_studies']
                if all(row.get(field) and row.get(field) != 'N/A' for field in critical_fields):
                    stats['all_fields_populated'] += 1
                
                # Track extraction status (PH1-S3)
                extraction_status = row.get('extraction_status', 'unknown')
                if extraction_status == 'success':
                    stats['extraction_success'] += 1
                elif extraction_status == 'failure':
                    stats['extraction_failure'] += 1
    
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return False
    
    # Print results
    print(f"\nCSV Validation Results for: {csv_file}")
    print("=" * 60)
    print(f"Total records: {stats['total_records']}")
    
    # Extraction Status Summary (PH1-S3)
    print(f"\nExtraction Status:")
    print(f"  Success: {stats['extraction_success']}/{stats['total_records']} ({stats['extraction_success']*100/max(stats['total_records'],1):.1f}%)")
    print(f"  Failure: {stats['extraction_failure']}/{stats['total_records']} ({stats['extraction_failure']*100/max(stats['total_records'],1):.1f}%)")
    
    print(f"\nField Population:")
    print(f"  Products: {stats['has_products']}/{stats['total_records']} ({stats['has_products']*100/max(stats['total_records'],1):.1f}%)")
    print(f"  Services: {stats['has_services']}/{stats['total_records']} ({stats['has_services']*100/max(stats['total_records'],1):.1f}%)")
    print(f"  Customers: {stats['has_customers']}/{stats['total_records']} ({stats['has_customers']*100/max(stats['total_records'],1):.1f}%)")
    print(f"  Partnerships: {stats['has_partnerships']}/{stats['total_records']} ({stats['has_partnerships']*100/max(stats['total_records'],1):.1f}%)")
    print(f"  Case Studies: {stats['has_case_studies']}/{stats['total_records']} ({stats['has_case_studies']*100/max(stats['total_records'],1):.1f}%)")
    print(f"\nAll critical fields populated: {stats['all_fields_populated']}/{stats['total_records']}")
    
    if issues:
        print(f"\nIssues found: {len(issues)}")
        for issue in issues[:10]:  # Show first 10 issues
            print(f"  - {issue}")
        if len(issues) > 10:
            print(f"  ... and {len(issues) - 10} more issues")
    
    # Quality score
    if stats['total_records'] > 0:
        quality_score = (
            stats['has_customers'] + stats['has_partnerships'] + stats['has_case_studies']
        ) / (stats['total_records'] * 3) * 100
        print(f"\nQuality Score (Customers + Partnerships + Case Studies): {quality_score:.1f}%")
    
    return len(issues) == 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Validate CSV output quality')
    parser.add_argument('csv_file', help='CSV file to validate')
    args = parser.parse_args()
    
    success = validate_csv(args.csv_file)
    sys.exit(0 if success else 1)

