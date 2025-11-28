#!/usr/bin/env python3
"""
Test script for Health Check functionality (PH6-S1)

Verifies that health checks work correctly.
Run with: python -m pytest tests/test_health.py -v
Or directly: python tests/test_health.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_health_imports():
    """Test health module can be imported."""
    try:
        from company_info_scraper.health import (
            HealthChecker,
            HealthStatus,
            CheckResult,
            HealthCheckStatus,
            check_health,
            check_ollama,
            print_health_status,
            run_health_check_cli
        )
        print("✓ Health module imports successful")
        return True
    except ImportError as e:
        print(f"✗ Failed to import health module: {e}")
        return False


def test_health_checker_instantiation():
    """Test HealthChecker can be instantiated."""
    try:
        from company_info_scraper.health import HealthChecker
        
        # Default config
        checker = HealthChecker()
        assert checker.ollama_host == 'http://localhost:11434'
        
        # Custom config
        checker = HealthChecker({
            'ollama_host': 'http://custom:11434',
            'ollama_model': 'mistral'
        })
        assert checker.ollama_host == 'http://custom:11434'
        assert checker.ollama_model == 'mistral'
        
        print("✓ HealthChecker instantiation successful")
        return True
    except Exception as e:
        print(f"✗ HealthChecker instantiation failed: {e}")
        return False


def test_check_result_dataclass():
    """Test CheckResult dataclass."""
    try:
        from company_info_scraper.health import CheckResult, HealthCheckStatus
        
        # Create a result
        result = CheckResult(
            name='test_check',
            status=HealthCheckStatus.HEALTHY,
            message='Test passed',
            details={'key': 'value'},
            elapsed_ms=10.5
        )
        
        assert result.name == 'test_check'
        assert result.is_healthy == True
        assert result.elapsed_ms == 10.5
        
        # Test to_dict
        d = result.to_dict()
        assert d['name'] == 'test_check'
        assert d['status'] == 'healthy'
        
        print("✓ CheckResult dataclass working correctly")
        return True
    except Exception as e:
        print(f"✗ CheckResult test failed: {e}")
        return False


def test_health_status_dataclass():
    """Test HealthStatus dataclass."""
    try:
        from company_info_scraper.health import (
            HealthStatus, 
            CheckResult, 
            HealthCheckStatus
        )
        
        checks = [
            CheckResult('check1', HealthCheckStatus.HEALTHY, 'OK'),
            CheckResult('check2', HealthCheckStatus.HEALTHY, 'OK'),
            CheckResult('check3', HealthCheckStatus.UNHEALTHY, 'Failed'),
        ]
        
        status = HealthStatus(
            status=HealthCheckStatus.UNHEALTHY,
            checks=checks,
            timestamp='2024-01-01T00:00:00'
        )
        
        assert status.healthy_count == 2
        assert status.total_count == 3
        assert status.is_healthy == False
        
        # Test to_dict and to_json
        d = status.to_dict()
        assert d['status'] == 'unhealthy'
        assert d['summary'] == '2/3 checks passed'
        
        j = status.to_json()
        assert '"status": "unhealthy"' in j
        
        print("✓ HealthStatus dataclass working correctly")
        return True
    except Exception as e:
        print(f"✗ HealthStatus test failed: {e}")
        return False


def test_check_imports():
    """Test import check functionality."""
    try:
        from company_info_scraper.health import HealthChecker
        
        checker = HealthChecker()
        result = checker.check_imports()
        
        # Should pass if running in the project
        print(f"  Import check: {result.status.value}")
        print(f"  Message: {result.message}")
        
        if result.details.get('missing'):
            print(f"  Missing: {result.details['missing']}")
        
        print("✓ Import check executed")
        return True
    except Exception as e:
        print(f"✗ Import check failed: {e}")
        return False


def test_check_config():
    """Test config check functionality."""
    try:
        from company_info_scraper.health import HealthChecker
        
        checker = HealthChecker()
        result = checker.check_config()
        
        print(f"  Config check: {result.status.value}")
        print(f"  Message: {result.message}")
        
        print("✓ Config check executed")
        return True
    except Exception as e:
        print(f"✗ Config check failed: {e}")
        return False


def test_check_disk_space():
    """Test disk space check functionality."""
    try:
        from company_info_scraper.health import HealthChecker
        
        checker = HealthChecker()
        result = checker.check_disk_space()
        
        assert result.details.get('free_gb') is not None
        print(f"  Disk space: {result.details['free_gb']:.1f}GB free")
        print(f"  Status: {result.status.value}")
        
        print("✓ Disk space check working")
        return True
    except Exception as e:
        print(f"✗ Disk space check failed: {e}")
        return False


def test_check_all():
    """Test running all checks."""
    try:
        from company_info_scraper.health import check_health
        
        status = check_health()
        
        print(f"\n  Overall status: {status.status.value}")
        print(f"  Checks passed: {status.healthy_count}/{status.total_count}")
        
        for check in status.checks:
            emoji = "✓" if check.is_healthy else "✗"
            print(f"    {emoji} {check.name}: {check.message}")
        
        print("\n✓ All checks executed")
        return True
    except Exception as e:
        print(f"✗ Check all failed: {e}")
        return False


def main():
    """Run all tests."""
    print("Testing Health Check (PH6-S1)")
    print("="*60)
    
    results = []
    
    results.append(("Health Imports", test_health_imports()))
    results.append(("HealthChecker Instantiation", test_health_checker_instantiation()))
    results.append(("CheckResult Dataclass", test_check_result_dataclass()))
    results.append(("HealthStatus Dataclass", test_health_status_dataclass()))
    results.append(("Import Check", test_check_imports()))
    results.append(("Config Check", test_check_config()))
    results.append(("Disk Space Check", test_check_disk_space()))
    results.append(("Check All", test_check_all()))
    
    # Summary
    print("\n" + "="*60)
    print("Test Results")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())

