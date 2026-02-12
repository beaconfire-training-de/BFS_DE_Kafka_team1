-- ================================================
-- Setup Script for CDC Project
-- Run this on BOTH databases (source and destination)
-- ================================================

-- 1. Create employees table (business table)
CREATE TABLE IF NOT EXISTS employees(
    emp_id SERIAL PRIMARY KEY,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    dob DATE,
    city VARCHAR(100),
    salary INT
);

-- ================================================
-- Run ONLY on SOURCE database (db-source, port 5435)
-- ================================================

-- 2. Create CDC table (change log table)
CREATE TABLE IF NOT EXISTS emp_cdc(
    cdc_id SERIAL PRIMARY KEY,           -- Auto-increment ID for tracking
    emp_id INT,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    dob DATE,
    city VARCHAR(100),
    salary INT,
    action VARCHAR(20),                  -- 'INSERT', 'UPDATE', 'DELETE'
    created_at TIMESTAMP DEFAULT NOW()   -- Timestamp
);

-- 3. Create function to log changes
CREATE OR REPLACE FUNCTION log_employee_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'DELETE') THEN
        -- Log DELETE operation with OLD values
        INSERT INTO emp_cdc(emp_id, first_name, last_name, dob, city, salary, action)
        VALUES (OLD.emp_id, OLD.first_name, OLD.last_name, OLD.dob, OLD.city, OLD.salary, 'DELETE');
        RETURN OLD;
        
    ELSIF (TG_OP = 'UPDATE') THEN
        -- Log UPDATE operation with NEW values
        INSERT INTO emp_cdc(emp_id, first_name, last_name, dob, city, salary, action)
        VALUES (NEW.emp_id, NEW.first_name, NEW.last_name, NEW.dob, NEW.city, NEW.salary, 'UPDATE');
        RETURN NEW;
        
    ELSIF (TG_OP = 'INSERT') THEN
        -- Log INSERT operation with NEW values
        INSERT INTO emp_cdc(emp_id, first_name, last_name, dob, city, salary, action)
        VALUES (NEW.emp_id, NEW.first_name, NEW.last_name, NEW.dob, NEW.city, NEW.salary, 'INSERT');
        RETURN NEW;
    END IF;
    
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- 4. Create trigger on employees table
DROP TRIGGER IF EXISTS employee_cdc_trigger ON employees;

CREATE TRIGGER employee_cdc_trigger
AFTER INSERT OR UPDATE OR DELETE ON employees
FOR EACH ROW
EXECUTE FUNCTION log_employee_changes();

-- ================================================
-- Test the setup
-- ================================================

-- Insert test data
INSERT INTO employees (first_name, last_name, dob, city, salary)
VALUES ('John', 'Doe', '1990-01-15', 'Boston', 75000);

-- Check if CDC captured the insert
SELECT * FROM emp_cdc;

-- Update test
UPDATE employees SET salary = 80000 WHERE first_name = 'John';

-- Check CDC again (should have INSERT and UPDATE)
SELECT * FROM emp_cdc ORDER BY cdc_id;

-- Delete test
DELETE FROM employees WHERE first_name = 'John';

-- Final check (should have INSERT, UPDATE, and DELETE)
SELECT * FROM emp_cdc ORDER BY cdc_id;

-- Clean up test data
TRUNCATE emp_cdc;
TRUNCATE employees RESTART IDENTITY;

SELECT 'Setup completed successfully!' AS status;
