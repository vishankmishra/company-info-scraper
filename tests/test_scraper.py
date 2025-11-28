"""
Test cases for Company Info Scraper
Focus on validating Customers, Partnerships, and Case Studies extraction
"""

import unittest
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from company_info_scraper.agents import OrchestratorAgent, LLMExtractionAgent


class TestLLMExtraction(unittest.TestCase):
    """Test LLM extraction agent"""
    
    def setUp(self):
        self.llm_agent = LLMExtractionAgent()
    
    def test_extraction_with_sample_text(self):
        """Test extraction with sample website text"""
        sample_text = """
        Our company provides enterprise software solutions.
        
        Customers: We serve Fortune 500 companies including Microsoft, Amazon, and Google.
        
        Partnerships: We have strategic partnerships with Salesforce, Oracle, and IBM.
        
        Case Studies: 
        - How Microsoft increased efficiency by 40% using our platform
        - Amazon's digital transformation success story
        """
        
        result = self.llm_agent.execute({'text': sample_text, 'url': 'test.com'})
        
        self.assertTrue(result.get('success'))
        self.assertIn('products', result)
        self.assertIn('customers', result)
        self.assertIn('partnerships', result)
        self.assertIn('case_studies', result)
    
    def test_extraction_with_empty_text(self):
        """Test extraction with empty text"""
        result = self.llm_agent.execute({'text': '', 'url': 'test.com'})
        
        self.assertTrue(result.get('success'))
        self.assertEqual(result.get('products'), 'N/A')
        self.assertEqual(result.get('customers'), 'N/A')
    
    def test_extraction_with_missing_fields(self):
        """Test extraction when required fields are missing"""
        result = self.llm_agent.execute({'url': 'test.com'})
        
        self.assertFalse(result.get('success'))
        self.assertIn('error', result)


class TestOrchestrator(unittest.TestCase):
    """Test orchestrator agent"""
    
    def setUp(self):
        config = {
            'project_root': str(project_root),
            'output_file': 'test_output.csv'
        }
        self.orchestrator = OrchestratorAgent(config)
    
    def test_orchestrator_with_valid_domain(self):
        """Test orchestrator with a valid domain"""
        # Note: This test requires Ollama to be running
        # Skip if Ollama is not available
        try:
            import ollama
            # Quick check if Ollama is accessible
            ollama.list()
        except:
            self.skipTest("Ollama not available")
        
        # Use a simple, fast-loading domain for testing
        result = self.orchestrator.execute({'domain': 'example.com'})
        
        # Should return a result (may succeed or fail, but should not crash)
        self.assertIn('success', result)
        self.assertIn('domain', result)


class TestDataValidation(unittest.TestCase):
    """Test data validation and quality checks"""
    
    def test_csv_output_structure(self):
        """Test that CSV output has correct structure"""
        # This would require running a scrape first
        # Placeholder for CSV validation logic
        pass
    
    def test_customers_extraction_quality(self):
        """Test that customer names are extracted correctly"""
        # Placeholder for customer extraction quality tests
        pass
    
    def test_partnerships_extraction_quality(self):
        """Test that partnerships are extracted correctly"""
        # Placeholder for partnerships extraction quality tests
        pass
    
    def test_case_studies_extraction_quality(self):
        """Test that case studies are extracted correctly"""
        # Placeholder for case studies extraction quality tests
        pass


if __name__ == '__main__':
    unittest.main()

