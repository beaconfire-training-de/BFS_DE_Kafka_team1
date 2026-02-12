"""
Offset Manager
Tracks the last processed CDC record to avoid full table scans
"""
import os
import json


class OffsetManager:
    """Manages offset tracking for CDC processing"""
    
    def __init__(self, offset_file='cdc_offset.json'):
        self.offset_file = offset_file
        self.last_cdc_id = self._load_offset()
    
    def _load_offset(self):
        """Load last processed CDC ID from file"""
        if os.path.exists(self.offset_file):
            try:
                with open(self.offset_file, 'r') as f:
                    data = json.load(f)
                    return data.get('last_cdc_id', 0)
            except Exception as e:
                print(f"Error loading offset: {e}")
                return 0
        return 0
    
    def save_offset(self, cdc_id):
        """Save last processed CDC ID to file"""
        try:
            with open(self.offset_file, 'w') as f:
                json.dump({'last_cdc_id': cdc_id}, f)
            self.last_cdc_id = cdc_id
        except Exception as e:
            print(f"Error saving offset: {e}")
    
    def get_last_cdc_id(self):
        """Get last processed CDC ID"""
        return self.last_cdc_id
    
    def reset(self):
        """Reset offset to 0"""
        self.save_offset(0)
        print("Offset reset to 0")
