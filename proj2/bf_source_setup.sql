CREATE TABLE employees(
  emp_id SERIAL,
  first_name VARCHAR(100),
  last_name VARCHAR(100),
  dob DATE,
  city VARCHAR(100),
  salary INT
);

CREATE TABLE emp_cdc(
  cdc_id SERIAL PRIMARY KEY,
  emp_id INT,
  first_name VARCHAR(100),
  last_name VARCHAR(100),
  dob DATE,
  city VARCHAR(100),
  salary INT,
  action VARCHAR(20),
  changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION log_employee_changes()
RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO emp_cdc(emp_id, first_name, last_name, dob, city, salary, action)
    VALUES (NEW.emp_id, NEW.first_name, NEW.last_name, NEW.dob, NEW.city, NEW.salary, 'INSERT');
    RETURN NEW;

  ELSIF TG_OP = 'UPDATE' THEN
    INSERT INTO emp_cdc(emp_id, first_name, last_name, dob, city, salary, action)
    VALUES (NEW.emp_id, NEW.first_name, NEW.last_name, NEW.dob, NEW.city, NEW.salary, 'UPDATE');
    RETURN NEW;

  ELSIF TG_OP = 'DELETE' THEN
    INSERT INTO emp_cdc(emp_id, first_name, last_name, dob, city, salary, action)
    VALUES (OLD.emp_id, OLD.first_name, OLD.last_name, OLD.dob, OLD.city, OLD.salary, 'DELETE');
    RETURN OLD;
  END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER employee_changes_trigger
AFTER INSERT OR UPDATE OR DELETE
ON employees
FOR EACH ROW
EXECUTE FUNCTION log_employee_changes();

INSERT INTO employees(first_name, last_name, dob, city, salary)
VALUES ('Max','Smith','2002-02-03','Sydney',90432);

INSERT INTO employees(first_name, last_name, dob, city, salary)
VALUES ('Ma','Smh','2022-02-03','NY',100000);

INSERT INTO employees(first_name, last_name, dob, city, salary)
VALUES ('Ma','Sth','2005-02-03','nj',52200);

INSERT INTO employees(first_name, last_name, dob, city, salary)
VALUES ('x','S','2018-02-03','ct',43200);

SELECT * FROM emp_cdc;

UPDATE employees
SET salary = 100000
WHERE emp_id = 4;

SELECT * FROM emp_cdc;

DELETE FROM employees
WHERE emp_id = 2;

SELECT * FROM emp_cdc;

select * from employees;




