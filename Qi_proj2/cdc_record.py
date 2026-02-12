"""
CDC Record Data Model
Represents a change data capture record
"""
import json
from datetime import date


class CDCRecord:
    """Represents a CDC record from emp_cdc table"""
    
    def __init__(self, cdc_id, emp_id, first_name, last_name, dob, city, salary, action, created_at=None):
        self.cdc_id = cdc_id
        self.emp_id = emp_id
        self.first_name = first_name
        self.last_name = last_name
        self.dob = dob if isinstance(dob, str) else dob.strftime('%Y-%m-%d')
        self.city = city
        self.salary = salary
        self.action = action
        self.created_at = created_at
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'cdc_id': self.cdc_id,
            'emp_id': self.emp_id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'dob': self.dob,
            'city': self.city,
            'salary': self.salary,
            'action': self.action
        }
    
    def to_json(self):
        """Convert to JSON string"""
        return json.dumps(self.to_dict())
    
    @staticmethod
    def from_json(json_str):
        """Create CDCRecord from JSON string"""
        data = json.loads(json_str)
        return CDCRecord(**data)
    
    @staticmethod
    def from_db_row(row):
        """Create CDCRecord from database row tuple"""
        return CDCRecord(
            cdc_id=row[0],
            emp_id=row[1],
            first_name=row[2],
            last_name=row[3],
            dob=row[4],
            city=row[5],
            salary=row[6],
            action=row[7],
            created_at=row[8] if len(row) > 8 else None
        )
    
    def __repr__(self):
        return f"CDCRecord(cdc_id={self.cdc_id}, emp_id={self.emp_id}, action={self.action})"
