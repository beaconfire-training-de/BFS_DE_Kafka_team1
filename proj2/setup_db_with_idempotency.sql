-- Enhanced database setup with idempotency tracking
-- Run this in DESTINATION DATABASE (Port 5433)

-- Drop existing table if needed
DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS processed_events CASCADE;

-- Create employees table
CREATE TABLE employees (
    emp_id INT PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    dob DATE,
    city VARCHAR(100),
    salary INT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create table to track processed CDC events (for idempotency)
CREATE TABLE processed_events (
    action_id INT PRIMARY KEY,
    emp_id INT,
    action VARCHAR(10),
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    kafka_offset BIGINT,
    kafka_partition INT
);

-- Create index for faster lookups
CREATE INDEX idx_processed_events_emp_id ON processed_events(emp_id);
CREATE INDEX idx_processed_events_timestamp ON processed_events(processed_at);

-- Optional: Clean up old processed events (keep last 30 days)
-- Run this periodically
-- DELETE FROM processed_events WHERE processed_at < NOW() - INTERVAL '30 days';

COMMENT ON TABLE processed_events IS 'Tracks processed CDC events to ensure idempotency';
