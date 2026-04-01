# -*- coding: utf-8 -*-
"""
COSCO Reefer Template
"""

from .template_base import BaseTemplate

class CoscoReeferTemplate(BaseTemplate):
    """
    Template for COSCO Reefer pricing images
    """
    
    def __init__(self):
        super().__init__()
        self.carrier = "COSCO"
        self.rate_type = "FAK"
        
        # Container type mapping
        self.container_mapping = {
            '40RQ': '40RF',
            '20RF': '20RF',
            '40RF': '40RF'
        }
        
        # Column positions
        self.columns = {
            'POL': 0,
            'POD': 1,
            '40RQ': 2,
            '20RF': 3
        }
    
    def parse_pol(self, text):
        """
        Parse POL from COSCO format
        Example: 'HCM/Cai Mep/' → 'HCM'
        """
        if '/' in text:
            return text.split('/')[0].strip()
        return text.strip()
    
    def parse_pod(self, text):
        """
        Parse POD from COSCO format
        Example: 'LGB/LA' → 'USLAX'
        """
        # Map common abbreviations
        pod_map = {
            'LGB/LA': 'USLAX',
            'Seattle': 'USSEA',
            'Tacoma': 'USTIW',
            'Oakland': 'USOAK',
            'New York': 'USNYC',
            'Norfolk': 'USNFK',
            'Savannah': 'USSAV',
            'Charleston': 'USCHS',
            'Houston/Mobile': 'USHOU'
        }
        
        return pod_map.get(text.strip(), text.strip())
