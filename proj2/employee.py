import json

class Employee:
    def __init__(self, action_id: int, emp_id: int, emp_FN: str, emp_LN: str,
                 emp_dob: str, emp_city: str, emp_salary: int, action: str):
        self.action_id = action_id
        self.emp_id = emp_id
        self.emp_FN = emp_FN
        self.emp_LN = emp_LN
        self.emp_dob = emp_dob
        self.emp_city = emp_city
        self.emp_salary = emp_salary
        self.action = action

    def to_json(self):
        return json.dumps(self.__dict__)

    def __repr__(self):
        return f"Employee(id={self.emp_id}, action={self.action}, name={self.emp_FN} {self.emp_LN})"
