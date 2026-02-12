CREATE TABLE employees (
    emp_id INT PRIMARY KEY,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    dob DATE,
    city VARCHAR(50),
    salary NUMERIC(10,2)
);

select * from employees;