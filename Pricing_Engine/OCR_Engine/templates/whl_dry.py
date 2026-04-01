# -*- coding: utf-8 -*-
"""
WHL Dry Template
"""

from .template_base import BaseTemplate

class WhlDryTemplate(BaseTemplate):
    """
    Template for WHL Dry pricing images
    """
    
    def __init__(self):
        super().__init__()
        self.carrier = "WHL"
        self.rate_type = "FAK"
        
        # Container type mapping
        self.container_mapping = {
            "20'SD": '20GP',
            "40'SD": '40GP',
            "40'HC": '40HQ',
            "45'HC": "45'HQ"
        }
        
        # Region to POD mapping
        self.regions = {
            'WC': {
                'LAX, LGB, OAK (USBP)': ['USLAX', 'USLGB', 'USOAK'],
                'CHI (Chicago via LAX/LGB)': ['USCHI'],
                'DAL (Dallas via LAX/LGB)': ['USDAL'],
                'MEM (Memphis via LAX/LGB)': ['USMEM'],
                'KCK (Kansas via LAX/LGB)': ['USKCK']
            },
            'EC': {
                'NYC, ORF, CHS, SAV (USBP)': ['USNYC', 'USORF', 'USCHS', 'USSAV'],
                'CHI (Chicago via ORF)': ['USCHI'],
                'CLE (Cleveland via ORF)': ['USCLE'],
                'CVG (Cincinnati via ORF)': ['USCVG'],
                'LUI (Louisville via ORF)': ['USLUI']
            }
        }
    
    def parse_destination(self, text, region):
        """
        Parse destination from WHL format
        """
        for dest_group, pod_list in self.regions.get(region, {}).items():
            if text.strip() in dest_group:
                return pod_list[0]  # Return first POD
        
        return text.strip()
