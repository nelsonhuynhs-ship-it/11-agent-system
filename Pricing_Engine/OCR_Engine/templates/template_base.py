# -*- coding: utf-8 -*-
"""
Base Template for Carrier Pricing
"""

class BaseTemplate:
    """
    Base template class for all carriers
    """
    
    def __init__(self):
        self.carrier = "UNKNOWN"
        self.rate_type = "FAK"
        self.container_mapping = {}
        self.columns = {}
    
    def parse_pol(self, text):
        """Parse POL from text"""
        return text.strip()
    
    def parse_pod(self, text):
        """Parse POD from text"""
        return text.strip()
    
    def parse_date(self, text):
        """Parse date from text"""
        return text
    
    def validate(self, data):
        """Validate extracted data"""
        required_fields = ['POL', 'POD', 'Carrier', 'Container_Type', 'Amount']
        
        for field in required_fields:
            if field not in data or data[field] is None:
                raise ValueError(f"Missing required field: {field}")
        
        return True
