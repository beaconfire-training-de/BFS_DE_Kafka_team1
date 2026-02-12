-- Setup script for Project 2: Kafka CDC Pipeline
-- This script sets up source and destination databases

-- ============================================
-- SOURCE DATABASE SETUP (Port 5432)
-- ============================================
-- Connect to source DB first, then run this section

-- Create employees table in source DB
DROP TABLE IF EXISTS employees CASCADE;
CREATE TABLE employees (
    emp_id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    dob DATE,
    city VARCHAR(100),
    salary INT
);

-- Create emp_cdc (Change Data Capture) table to track all changes
DROP TABLE IF EXISTS emp_cdc CASCADE;
CREATE TABLE emp_cdc (
    action_id SERIAL PRIMARY KEY,
    emp_id INT,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    dob DATE,
    city VARCHAR(100),
    salary INT,
    action VARCHAR(10),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create trigger function for INSERT
CREATE OR REPLACE FUNCTION log_employee_insert()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO emp_cdc (emp_id, first_name, last_name, dob, city, salary, action)
    VALUES (NEW.emp_id, NEW.first_name, NEW.last_name, NEW.dob, NEW.city, NEW.salary, 'INSERT');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger function for UPDATE
CREATE OR REPLACE FUNCTION log_employee_update()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO emp_cdc (emp_id, first_name, last_name, dob, city, salary, action)
    VALUES (NEW.emp_id, NEW.first_name, NEW.last_name, NEW.dob, NEW.city, NEW.salary, 'UPDATE');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger function for DELETE
CREATE OR REPLACE FUNCTION log_employee_delete()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO emp_cdc (emp_id, first_name, last_name, dob, city, salary, action)
    VALUES (OLD.emp_id, OLD.first_name, OLD.last_name, OLD.dob, OLD.city, OLD.salary, 'DELETE');
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

-- Create triggers on employees table
DROP TRIGGER IF EXISTS employee_insert_trigger ON employees;
CREATE TRIGGER employee_insert_trigger
AFTER INSERT ON employees
FOR EACH ROW
EXECUTE FUNCTION log_employee_insert();

DROP TRIGGER IF EXISTS employee_update_trigger ON employees;
CREATE TRIGGER employee_update_trigger
AFTER UPDATE ON employees
FOR EACH ROW
EXECUTE FUNCTION log_employee_update();

DROP TRIGGER IF EXISTS employee_delete_trigger ON employees;
CREATE TRIGGER employee_delete_trigger
AFTER DELETE ON employees
FOR EACH ROW
EXECUTE FUNCTION log_employee_delete();

-- Insert sample data
INSERT INTO employees (first_name, last_name, dob, city, salary) VALUES
('Max', 'Smith', '2002-02-03', 'Sydney', 90432),
('Karl', 'Summers', '2004-04-10', 'Brisbane', 63319),
('Sam', 'Wilde', '2005-02-06', 'Perth', 105846),
('Linda', 'Chen', '1999-11-21', 'Hobart', 103239);

-- ============================================
-- DESTINATION DATABASE SETUP (Port 5433)
-- ============================================
-- Connect to destination DB, then run this section

-- Create employees table in destination DB (same schema as source)
DROP TABLE IF EXISTS employees CASCADE;
CREATE TABLE employees (
    emp_id INT PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    dob DATE,
    city VARCHAR(100),
    salary INT
);

-- Note: No triggers needed on destination DB
-- It will be updated by the Kafka consumer based on CDC events from source DB
