"""
Health Check Module for Company Info Scraper (PH6-S1)

Provides health check functionality for production deployment:
- Ollama connectivity and model availability
- Dependency verification
- Configuration validation
- System resources (disk, memory)

Usage:
    # CLI
    python main.py --health
    
    # Programmatic
    from company_info_scraper.health import check_health, HealthStatus
    status = check_health()
    print(f"Healthy: {status.is_healthy}")
"""

import os
import sys
import json
import time
import shutil
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class HealthCheckStatus(Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"  # Some non-critical checks failed
    UNHEALTHY = "unhealthy"  # Critical checks failed


@dataclass
class CheckResult:
    """Result of a single health check."""
    name: str
    status: HealthCheckStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    elapsed_ms: float = 0.0
    
    @property
    def is_healthy(self) -> bool:
        return self.status == HealthCheckStatus.HEALTHY
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'status': self.status.value,
            'message': self.message,
            'details': self.details,
            'elapsed_ms': self.elapsed_ms
        }


@dataclass
class HealthStatus:
    """Overall health status."""
    status: HealthCheckStatus
    checks: List[CheckResult] = field(default_factory=list)
    timestamp: str = ""
    version: str = "1.0.0"
    
    @property
    def is_healthy(self) -> bool:
        return self.status == HealthCheckStatus.HEALTHY
    
    @property
    def healthy_count(self) -> int:
        return sum(1 for c in self.checks if c.is_healthy)
    
    @property
    def total_count(self) -> int:
        return len(self.checks)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'status': self.status.value,
            'healthy': self.is_healthy,
            'timestamp': self.timestamp,
            'version': self.version,
            'summary': f"{self.healthy_count}/{self.total_count} checks passed",
            'checks': [c.to_dict() for c in self.checks]
        }
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class HealthChecker:
    """
    Health checker for the scraper system.
    
    Performs various health checks:
    - ollama: Ollama server connectivity
    - model: LLM model availability
    - config: Configuration file validity
    - disk: Disk space availability
    - imports: Required module imports
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.ollama_host = self.config.get('ollama_host', 'http://localhost:11434')
        self.ollama_model = self.config.get('ollama_model', 'llama3')
        self.min_disk_gb = self.config.get('min_disk_gb', 1.0)
    
    def check_all(self, include_optional: bool = True) -> HealthStatus:
        """
        Run all health checks.
        
        Args:
            include_optional: Include optional checks (disk, memory)
            
        Returns:
            HealthStatus with all check results
        """
        from datetime import datetime
        
        checks = []
        
        # Critical checks
        checks.append(self.check_ollama_connectivity())
        checks.append(self.check_ollama_model())
        checks.append(self.check_imports())
        checks.append(self.check_config())
        
        # Optional checks
        if include_optional:
            checks.append(self.check_disk_space())
            checks.append(self.check_output_directory())
        
        # Determine overall status
        critical_checks = checks[:4]  # First 4 are critical
        critical_failed = any(not c.is_healthy for c in critical_checks)
        optional_failed = any(not c.is_healthy for c in checks[4:])
        
        if critical_failed:
            overall_status = HealthCheckStatus.UNHEALTHY
        elif optional_failed:
            overall_status = HealthCheckStatus.DEGRADED
        else:
            overall_status = HealthCheckStatus.HEALTHY
        
        return HealthStatus(
            status=overall_status,
            checks=checks,
            timestamp=datetime.now().isoformat(),
            version=self._get_version()
        )
    
    def check_ollama_connectivity(self) -> CheckResult:
        """Check if Ollama server is reachable."""
        start = time.time()
        
        try:
            import httpx
            
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.ollama_host}/api/tags")
                
                if response.status_code == 200:
                    data = response.json()
                    models = [m.get('name', '') for m in data.get('models', [])]
                    return CheckResult(
                        name="ollama_connectivity",
                        status=HealthCheckStatus.HEALTHY,
                        message="Ollama server is reachable",
                        details={
                            'host': self.ollama_host,
                            'available_models': models[:5]  # First 5
                        },
                        elapsed_ms=(time.time() - start) * 1000
                    )
                else:
                    return CheckResult(
                        name="ollama_connectivity",
                        status=HealthCheckStatus.UNHEALTHY,
                        message=f"Ollama returned status {response.status_code}",
                        details={'host': self.ollama_host},
                        elapsed_ms=(time.time() - start) * 1000
                    )
                    
        except ImportError:
            return CheckResult(
                name="ollama_connectivity",
                status=HealthCheckStatus.UNHEALTHY,
                message="httpx not installed",
                elapsed_ms=(time.time() - start) * 1000
            )
        except Exception as e:
            return CheckResult(
                name="ollama_connectivity",
                status=HealthCheckStatus.UNHEALTHY,
                message=f"Cannot connect to Ollama: {str(e)}",
                details={
                    'host': self.ollama_host,
                    'error': str(e)
                },
                elapsed_ms=(time.time() - start) * 1000
            )
    
    def check_ollama_model(self) -> CheckResult:
        """Check if the configured LLM model is available."""
        start = time.time()
        
        try:
            import httpx
            
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.ollama_host}/api/tags")
                
                if response.status_code == 200:
                    data = response.json()
                    models = [m.get('name', '').split(':')[0] for m in data.get('models', [])]
                    
                    # Check if our model is available (handle name variations)
                    model_base = self.ollama_model.split(':')[0]
                    model_available = any(
                        model_base in m or m in model_base 
                        for m in models
                    )
                    
                    if model_available:
                        return CheckResult(
                            name="ollama_model",
                            status=HealthCheckStatus.HEALTHY,
                            message=f"Model '{self.ollama_model}' is available",
                            details={'model': self.ollama_model},
                            elapsed_ms=(time.time() - start) * 1000
                        )
                    else:
                        return CheckResult(
                            name="ollama_model",
                            status=HealthCheckStatus.UNHEALTHY,
                            message=f"Model '{self.ollama_model}' not found",
                            details={
                                'requested_model': self.ollama_model,
                                'available_models': models
                            },
                            elapsed_ms=(time.time() - start) * 1000
                        )
                else:
                    return CheckResult(
                        name="ollama_model",
                        status=HealthCheckStatus.UNHEALTHY,
                        message="Cannot list Ollama models",
                        elapsed_ms=(time.time() - start) * 1000
                    )
                    
        except Exception as e:
            return CheckResult(
                name="ollama_model",
                status=HealthCheckStatus.UNHEALTHY,
                message=f"Model check failed: {str(e)}",
                elapsed_ms=(time.time() - start) * 1000
            )
    
    def check_imports(self) -> CheckResult:
        """Check if required modules can be imported."""
        start = time.time()
        
        required_modules = [
            ('scrapy', 'Web scraping framework'),
            ('bs4', 'HTML parsing'),
            ('httpx', 'HTTP client'),
            ('yaml', 'Configuration'),
            ('ollama', 'LLM client'),
        ]
        
        missing = []
        available = []
        
        for module, description in required_modules:
            try:
                __import__(module)
                available.append(module)
            except ImportError:
                missing.append(f"{module} ({description})")
        
        if missing:
            return CheckResult(
                name="imports",
                status=HealthCheckStatus.UNHEALTHY,
                message=f"Missing {len(missing)} required modules",
                details={
                    'missing': missing,
                    'available': available
                },
                elapsed_ms=(time.time() - start) * 1000
            )
        
        return CheckResult(
            name="imports",
            status=HealthCheckStatus.HEALTHY,
            message=f"All {len(available)} required modules available",
            details={'modules': available},
            elapsed_ms=(time.time() - start) * 1000
        )
    
    def check_config(self) -> CheckResult:
        """Check if configuration is valid."""
        start = time.time()
        
        config_path = Path('config.yaml')
        
        if not config_path.exists():
            return CheckResult(
                name="config",
                status=HealthCheckStatus.DEGRADED,
                message="config.yaml not found (using defaults)",
                elapsed_ms=(time.time() - start) * 1000
            )
        
        try:
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)
            
            if not config:
                return CheckResult(
                    name="config",
                    status=HealthCheckStatus.DEGRADED,
                    message="config.yaml is empty",
                    elapsed_ms=(time.time() - start) * 1000
                )
            
            # Validate required keys
            required_keys = ['ollama_model', 'ollama_timeout']
            missing_keys = [k for k in required_keys if k not in config]
            
            if missing_keys:
                return CheckResult(
                    name="config",
                    status=HealthCheckStatus.DEGRADED,
                    message=f"Missing config keys: {missing_keys}",
                    details={'missing_keys': missing_keys},
                    elapsed_ms=(time.time() - start) * 1000
                )
            
            return CheckResult(
                name="config",
                status=HealthCheckStatus.HEALTHY,
                message="Configuration is valid",
                details={
                    'ollama_model': config.get('ollama_model'),
                    'ollama_timeout': config.get('ollama_timeout'),
                    'auto_detect': config.get('auto_detect', True)
                },
                elapsed_ms=(time.time() - start) * 1000
            )
            
        except Exception as e:
            return CheckResult(
                name="config",
                status=HealthCheckStatus.UNHEALTHY,
                message=f"Config error: {str(e)}",
                elapsed_ms=(time.time() - start) * 1000
            )
    
    def check_disk_space(self) -> CheckResult:
        """Check available disk space."""
        start = time.time()
        
        try:
            usage = shutil.disk_usage('.')
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            
            if free_gb < self.min_disk_gb:
                return CheckResult(
                    name="disk_space",
                    status=HealthCheckStatus.DEGRADED,
                    message=f"Low disk space: {free_gb:.1f}GB free",
                    details={
                        'free_gb': round(free_gb, 2),
                        'total_gb': round(total_gb, 2),
                        'min_required_gb': self.min_disk_gb
                    },
                    elapsed_ms=(time.time() - start) * 1000
                )
            
            return CheckResult(
                name="disk_space",
                status=HealthCheckStatus.HEALTHY,
                message=f"Disk space OK: {free_gb:.1f}GB free",
                details={
                    'free_gb': round(free_gb, 2),
                    'total_gb': round(total_gb, 2)
                },
                elapsed_ms=(time.time() - start) * 1000
            )
            
        except Exception as e:
            return CheckResult(
                name="disk_space",
                status=HealthCheckStatus.DEGRADED,
                message=f"Cannot check disk: {str(e)}",
                elapsed_ms=(time.time() - start) * 1000
            )
    
    def check_output_directory(self) -> CheckResult:
        """Check if output directory is writable."""
        start = time.time()
        
        output_file = self.config.get('output_file', 'output_data.csv')
        output_dir = Path(output_file).parent
        
        if output_dir == Path('.'):
            output_dir = Path('.')
        
        try:
            # Check if directory exists or can be created
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Check if writable
            test_file = output_dir / '.health_check_test'
            test_file.write_text('test')
            test_file.unlink()
            
            return CheckResult(
                name="output_directory",
                status=HealthCheckStatus.HEALTHY,
                message=f"Output directory is writable",
                details={'path': str(output_dir.absolute())},
                elapsed_ms=(time.time() - start) * 1000
            )
            
        except Exception as e:
            return CheckResult(
                name="output_directory",
                status=HealthCheckStatus.DEGRADED,
                message=f"Output directory issue: {str(e)}",
                details={'path': str(output_dir)},
                elapsed_ms=(time.time() - start) * 1000
            )
    
    def _get_version(self) -> str:
        """Get package version."""
        try:
            from company_info_scraper import __version__
            return __version__
        except:
            return "unknown"


# =============================================================================
# Convenience Functions
# =============================================================================

def check_health(config: Optional[Dict[str, Any]] = None) -> HealthStatus:
    """
    Run all health checks.
    
    Args:
        config: Optional configuration dict
        
    Returns:
        HealthStatus with all results
    """
    checker = HealthChecker(config)
    return checker.check_all()


def check_ollama(host: str = "http://localhost:11434") -> bool:
    """
    Quick check if Ollama is reachable.
    
    Args:
        host: Ollama host URL
        
    Returns:
        True if Ollama is reachable
    """
    checker = HealthChecker({'ollama_host': host})
    result = checker.check_ollama_connectivity()
    return result.is_healthy


def print_health_status(status: HealthStatus, verbose: bool = False):
    """
    Print health status to console.
    
    Args:
        status: HealthStatus to print
        verbose: Include detailed information
    """
    # Status emoji
    status_emoji = {
        HealthCheckStatus.HEALTHY: "✓",
        HealthCheckStatus.DEGRADED: "⚠",
        HealthCheckStatus.UNHEALTHY: "✗"
    }
    
    print(f"\n{'='*60}")
    print(f"Health Check - {status.timestamp}")
    print(f"{'='*60}")
    
    emoji = status_emoji.get(status.status, "?")
    print(f"\nOverall Status: {emoji} {status.status.value.upper()}")
    print(f"Summary: {status.healthy_count}/{status.total_count} checks passed")
    print(f"Version: {status.version}")
    
    print(f"\n{'-'*60}")
    print("Check Results:")
    print(f"{'-'*60}")
    
    for check in status.checks:
        emoji = status_emoji.get(check.status, "?")
        print(f"  {emoji} {check.name}: {check.message}")
        
        if verbose and check.details:
            for key, value in check.details.items():
                print(f"      {key}: {value}")
    
    print(f"\n{'='*60}\n")


def run_health_check_cli(
    config: Optional[Dict[str, Any]] = None,
    verbose: bool = False,
    json_output: bool = False
) -> int:
    """
    Run health check from CLI.
    
    Args:
        config: Configuration dict
        verbose: Verbose output
        json_output: Output as JSON
        
    Returns:
        Exit code (0 = healthy, 1 = unhealthy)
    """
    status = check_health(config)
    
    if json_output:
        print(status.to_json())
    else:
        print_health_status(status, verbose=verbose)
    
    return 0 if status.is_healthy else 1

