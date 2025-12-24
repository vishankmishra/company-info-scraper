#!/usr/bin/env python3
"""
Test reactor state when CrawlerProcess.start() is called from within agent.
"""

# IMPORTANT: Install asyncio reactor BEFORE any Twisted imports
import sys
if 'twisted.internet.reactor' not in sys.modules:
    import asyncio
    from twisted.internet import asyncioreactor
    asyncioreactor.install()

from twisted.internet import reactor
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

print("=" * 60)
print("Testing reactor state")
print("=" * 60)

print(f"Reactor installed: {'twisted.internet.reactor' in sys.modules}")
print(f"Reactor running: {reactor.running}")
print(f"Reactor type: {type(reactor)}")

settings = get_project_settings()
settings.set('FEED_URI', None)
settings.set('LOG_LEVEL', 'WARNING')

print("\nCreating CrawlerProcess...")
process = CrawlerProcess(settings)

print(f"After CrawlerProcess creation:")
print(f"Reactor running: {reactor.running}")

print("\nCalling process.start()...")
print("If reactor is already running, this will fail or hang")

try:
    process.start()
    print("SUCCESS: process.start() returned")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

