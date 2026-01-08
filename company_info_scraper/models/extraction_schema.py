"""
Pydantic schema for LLM extraction output validation (Phase 5).
"""

from typing import List, Union
from pydantic import BaseModel, Field, field_validator


class ExtractionSchema(BaseModel):
    """Schema for validated LLM extraction output."""
    
    products: Union[List[str], str] = Field(
        default=[],
        description="List of product names or empty array"
    )
    services: Union[List[str], str] = Field(
        default=[],
        description="List of service names or empty array"
    )
    customers: Union[List[str], str] = Field(
        default=[],
        description="List of customer/client company names or empty array"
    )
    partnerships: Union[List[str], str] = Field(
        default=[],
        description="List of partnership/integration names or empty array"
    )
    case_studies: Union[List[str], str] = Field(
        default=[],
        description="List of case study titles or empty array"
    )
    leadership: Union[List[str], str] = Field(
        default=[],
        description="List of leadership/team member names with titles or empty array"
    )
    emails: Union[List[str], str] = Field(
        default=[],
        description="List of email addresses or empty array"
    )
    phones: Union[List[str], str] = Field(
        default=[],
        description="List of phone numbers or empty array"
    )
    
    @field_validator('products', 'services', 'customers', 'partnerships', 'case_studies', 'leadership', 'emails', 'phones', mode='before')
    @classmethod
    def normalize_field(cls, v):
        """Normalize field values: convert "N/A" to empty list, ensure list format."""
        if v == "N/A" or v is None:
            return []
        if isinstance(v, str):
            # If it's a string that's not "N/A", treat as single-item list
            return [v] if v.strip() else []
        if isinstance(v, list):
            # Filter out "N/A" and empty strings
            return [item for item in v if item and item != "N/A" and str(item).strip()]
        return []
    
    def to_dict(self) -> dict:
        """Convert to dictionary with string-formatted fields."""
        return {
            'products': self.products if isinstance(self.products, list) else [],
            'services': self.services if isinstance(self.services, list) else [],
            'customers': self.customers if isinstance(self.customers, list) else [],
            'partnerships': self.partnerships if isinstance(self.partnerships, list) else [],
            'case_studies': self.case_studies if isinstance(self.case_studies, list) else [],
            'leadership': self.leadership if isinstance(self.leadership, list) else [],
            'emails': self.emails if isinstance(self.emails, list) else [],
            'phones': self.phones if isinstance(self.phones, list) else []
        }

