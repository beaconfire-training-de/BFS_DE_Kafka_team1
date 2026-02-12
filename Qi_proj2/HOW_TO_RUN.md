# How to Run the Kafka CDC Project

Complete guide for running, testing, and resetting the project.

---

## 📋 Table of Contents

1. [Initial Setup](#initial-setup)
2. [Running the Project](#running-the-project)
3. [Testing the Sync](#testing-the-sync)
4. [Resetting the Project](#resetting-the-project)
5. [Stopping the Project](#stopping-the-project)
6. [Common Issues](#common-issues)

---

## 🚀 Initial Setup

### Step 1: Clone the Repository

```bash
git clone <your-repo-url>
cd kafka-cdc-project
```

### Step 2: Verify Prerequisites

Check that you have:
- Docker Desktop installed and running
- Python 3.7+ installed
- At least 2GB free memory

```bash
# Verify Docker
docker --version
docker-compose --version

# Verify Python
python3 --version
```

### Step 3: Start Docker Services

```bash
# Start all containers
docker-compose up -d

# Verify all containers are running (should see 4 containers)
docker ps
```

**Expected containers:**
- `kafka-1` (port 29092)
- `zookeeper-1` (port 2181)
- `db-source` (port 5435)
- `db-destination` (port 5436)

### Step 4: Initialize Source Database

Create tables, triggers, and functions:

```bash
docker exec -i db-source psql -U postgres -d postgres < setup_cdc.sql
```

**This creates:**
- `employees` table (business table)
- `emp_cdc` table (change log table)
- `log_employee_changes()` function
- `employee_cdc_trigger` trigger

**Verify trigger was created:**

```bash
docker exec -i db-source psql -U postgres -d postgres -c "\d employees"
```

You should see:
```
Triggers:
    employee_cdc_trigger AFTER INSERT OR DELETE OR UPDATE ON employees ...
```

### Step 5: Initialize Destination Database

Create the employees table (without triggers):

```bash
docker exec -i db-destination psql -U postgres -d postgres << 'EOF'
CREATE TABLE IF NOT EXISTS employees(
    emp_id SERIAL PRIMARY KEY,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    dob DATE,
    city VARCHAR(100),
    salary INT
);
EOF
```

### Step 6: Create Kafka Topic

```bash
docker exec -it kafka-1 kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic employee_cdc \
  --partitions 1 \
  --replication-factor 1
```

**Verify topic was created:**

```bash
docker exec -it kafka-1 kafka-topics --list --bootstrap-server localhost:9092
```

You should see: `employee_cdc`

### Step 7: Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Or install individually:**

```bash
pip install confluent-kafka psycopg2-binary
```

---

## 🏃 Running the Project

### Important: Run Order

**Always start Consumer BEFORE Producer!**

Why? Consumer needs to subscribe to the Kafka topic first to receive all messages.

### Terminal 1: Start Consumer (First!)

```bash
cd kafka-cdc-project
python3 consumer.py
```

**Expected output:**

```
============================================================
CDC Consumer Started
============================================================
Database: localhost:5436
Topic: employee_cdc
Consumer Group: cdc_sync_group
============================================================

Waiting for CDC messages...
```

**Keep this terminal running!**

---

### Terminal 2: Start Producer (Second!)

```bash
cd kafka-cdc-project
python3 producer.py
```

**Expected output:**

```
============================================================
CDC Producer Started
============================================================
Database: localhost:5435
Topic: employee_cdc
Poll Interval: 0.5s
Starting from CDC ID: 0
============================================================

Waiting for changes in emp_cdc table...
```

**Keep this terminal running!**

---

## 🧪 Testing the Sync

### Test 1: Single INSERT

**Terminal 3 (new terminal):**

```bash
docker exec -i db-source psql -U postgres -d postgres << 'EOF'
INSERT INTO employees (first_name, last_name, dob, city, salary)
VALUES ('Alice', 'Johnson', '1990-05-15', 'Boston', 75000);
EOF
```

**Expected behavior:**

**Producer terminal shows:**
```
📦 Found 1 new CDC record(s)
Processing: INSERT - emp_id=1, cdc_id=1
✓ Message delivered: cdc_id=1, partition=0, offset=0
✅ Processed 1 record(s), offset updated to 1
```

**Consumer terminal shows:**
```
✓ INSERT: emp_id=1, Alice Johnson
```

**Verify sync (should complete in < 1 second):**

```bash
# Check destination database
docker exec -i db-destination psql -U postgres -d postgres -c \
  "SELECT * FROM employees;"
```

You should see Alice Johnson!

---

### Test 2: UPDATE

```bash
docker exec -i db-source psql -U postgres -d postgres << 'EOF'
UPDATE employees 
SET salary = 85000, city = 'Cambridge'
WHERE first_name = 'Alice';
EOF
```

**Verify:**

```bash
docker exec -i db-destination psql -U postgres -d postgres -c \
  "SELECT * FROM employees WHERE first_name = 'Alice';"
```

Salary should be 85000, city should be Cambridge!

---

### Test 3: DELETE

```bash
docker exec -i db-source psql -U postgres -d postgres << 'EOF'
DELETE FROM employees 
WHERE first_name = 'Alice';
EOF
```

**Verify:**

```bash
docker exec -i db-destination psql -U postgres -d postgres -c \
  "SELECT COUNT(*) FROM employees;"
```

Count should be 0!

---

### Test 4: Batch INSERT

```bash
docker exec -i db-source psql -U postgres -d postgres << 'EOF'
INSERT INTO employees (first_name, last_name, dob, city, salary) VALUES
('Bob', 'Smith', '1985-03-22', 'New York', 85000),
('Charlie', 'Brown', '1992-07-10', 'San Francisco', 95000),
('Diana', 'Davis', '1988-11-30', 'Seattle', 70000),
('Eve', 'Wilson', '1995-05-18', 'Austin', 65000),
('Frank', 'Miller', '1987-06-20', 'Chicago', 80000);
EOF
```

**Expected:**
- Producer captures 5 INSERT records
- Consumer applies 5 inserts
- Destination DB has 5 employees

**Verify:**

```bash
docker exec -i db-destination psql -U postgres -d postgres -c \
  "SELECT first_name, city, salary FROM employees ORDER BY emp_id;"
```

---

## 🔄 Resetting the Project

### When to Reset?

Reset when you want to:
- Start fresh for testing
- Clear all data
- Fix offset sync issues

### Method 1: Using the Reset Script (Recommended)

```bash
./reset_all.sh
```

**This script:**
1. Deletes `cdc_offset.json` file
2. Truncates Source DB tables (`employees` and `emp_cdc`)
3. Truncates Destination DB table (`employees`)

**After running, you must:**
1. Restart Producer (Ctrl+C, then `python3 producer.py`)
2. Consumer can keep running

---

### Method 2: Manual Reset (Step by Step)

#### Step 1: Delete Offset File

```bash
rm -f cdc_offset.json
```

**Why?** The offset file tracks which CDC records have been processed. If you truncate the CDC table, the offset becomes invalid.

#### Step 2: Clear Source Database

```bash
docker exec -i db-source psql -U postgres -d postgres << 'EOF'
TRUNCATE employees RESTART IDENTITY;
TRUNCATE emp_cdc RESTART IDENTITY;
EOF
```

**Explanation:**
- `TRUNCATE employees`: Removes all employee records
- `TRUNCATE emp_cdc`: Removes all CDC records
- `RESTART IDENTITY`: Resets the auto-increment ID back to 1

#### Step 3: Clear Destination Database

```bash
docker exec -i db-destination psql -U postgres -d postgres << 'EOF'
TRUNCATE employees RESTART IDENTITY;
EOF
```

#### Step 4: Restart Producer

In the Producer terminal:
1. Press `Ctrl+C` to stop
2. Run `python3 producer.py` again

**Consumer can keep running - no need to restart!**

---

### Method 3: Complete Reset (Including Docker)

If you want to completely reset everything including Docker volumes:

```bash
# Stop all services
docker-compose down -v

# Start fresh
docker-compose up -d

# Re-run all initialization steps from "Initial Setup"
```

⚠️ **Warning:** This deletes all Docker volumes and data!

---

## 🛑 Stopping the Project

### Step 1: Stop Python Programs

**In Producer terminal:**
- Press `Ctrl+C`

**In Consumer terminal:**
- Press `Ctrl+C`

You'll see statistics:
```
Processing Statistics:
INSERT: 10
UPDATE: 5
DELETE: 2
TOTAL: 17
```

### Step 2: Stop Docker Services

```bash
# Stop containers (data preserved)
docker-compose down

# Or stop and delete all data
docker-compose down -v
```

---

## ❓ Common Issues

### Issue 1: "Topic not found" Error

**Symptom:**
```
KafkaException: Subscribed topic not available: employee_cdc
```

**Solution:**

```bash
# Create the topic
docker exec -it kafka-1 kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic employee_cdc \
  --partitions 1 \
  --replication-factor 1
```

---

### Issue 2: Producer Not Capturing Changes

**Symptom:** Producer shows "Found 0 new CDC record(s)" after inserting data

**Diagnostic Steps:**

1. Check if CDC table has records:
```bash
docker exec -i db-source psql -U postgres -d postgres -c "SELECT * FROM emp_cdc;"
```

2. If CDC table is empty, trigger isn't working. Re-run setup:
```bash
docker exec -i db-source psql -U postgres -d postgres < setup_cdc.sql
```

3. If CDC table has records but Producer doesn't see them, check offset:
```bash
cat cdc_offset.json
```

If offset is higher than max CDC ID, reset:
```bash
rm cdc_offset.json
# Restart Producer
```

---

### Issue 3: Batch INSERT Not Triggering

**Symptom:** Single INSERT works, but batch INSERT doesn't trigger CDC

**Cause:** Transaction not committed in SQL client

**Solution:**

Use command line instead of DBeaver:
```bash
docker exec -i db-source psql -U postgres -d postgres << 'EOF'
INSERT INTO employees (...) VALUES (...), (...), (...);
EOF
```

Or in DBeaver, explicitly commit:
```sql
BEGIN;
INSERT INTO employees (...) VALUES (...), (...), (...);
COMMIT;  -- Must have this!
```

---

### Issue 4: Database Connection Failed

**Symptom:**
```
connection to server at "localhost", port 5435 failed
```

**Solution:**

1. Check if containers are running:
```bash
docker ps
```

2. Restart Docker services:
```bash
docker-compose down
docker-compose up -d
```

---

### Issue 5: Data in Source but Not in Destination

**Diagnostic Checklist:**

1. ✅ Consumer is running?
2. ✅ Producer is running and processing messages?
3. ✅ Check Producer terminal for "Message delivered" confirmations
4. ✅ Check Consumer terminal for "INSERT/UPDATE/DELETE" logs
5. ✅ Verify in destination database:
```bash
docker exec -i db-destination psql -U postgres -d postgres -c \
  "SELECT COUNT(*) FROM employees;"
```

---

## 📊 Monitoring & Verification

### Check System Status

```bash
# All containers running?
docker ps

# Producer offset
cat cdc_offset.json

# CDC table size
docker exec -i db-source psql -U postgres -d postgres -c \
  "SELECT COUNT(*) FROM emp_cdc;"

# Source DB record count
docker exec -i db-source psql -U postgres -d postgres -c \
  "SELECT COUNT(*) FROM employees;"

# Destination DB record count
docker exec -i db-destination psql -U postgres -d postgres -c \
  "SELECT COUNT(*) FROM employees;"
```

### Verify Data Consistency

```bash
# Compare record counts
echo "Source DB:"
docker exec -i db-source psql -U postgres -d postgres -c \
  "SELECT COUNT(*) FROM employees;"

echo "Destination DB:"
docker exec -i db-destination psql -U postgres -d postgres -c \
  "SELECT COUNT(*) FROM employees;"

# Should be identical!
```

---

## 🎯 Quick Reference

### Daily Workflow

```bash
# 1. Start Docker (if not running)
docker-compose up -d

# 2. Start Consumer (Terminal 1)
python3 consumer.py

# 3. Start Producer (Terminal 2)
python3 producer.py

# 4. Test (Terminal 3)
docker exec -i db-source psql -U postgres -d postgres << 'EOF'
INSERT INTO employees (first_name, last_name, dob, city, salary)
VALUES ('Test', 'User', '1990-01-01', 'Boston', 50000);
EOF

# 5. Stop (when done)
# Ctrl+C in Producer and Consumer terminals
docker-compose down
```

### Reset Workflow

```bash
# Quick reset
./reset_all.sh
# Then restart Producer (Ctrl+C, python3 producer.py)

# OR manual reset
rm -f cdc_offset.json
docker exec -i db-source psql -U postgres -d postgres -c \
  "TRUNCATE employees RESTART IDENTITY; TRUNCATE emp_cdc RESTART IDENTITY;"
docker exec -i db-destination psql -U postgres -d postgres -c \
  "TRUNCATE employees RESTART IDENTITY;"
# Then restart Producer
```

---

## 💡 Tips & Best Practices

1. **Always start Consumer before Producer** to ensure no messages are missed

2. **Reset offset after truncating CDC table** to avoid sync issues

3. **Use command line for batch operations** instead of GUI tools (more reliable)

4. **Monitor both terminals** when testing to see real-time sync in action

5. **Check offset regularly** if you notice sync issues:
   ```bash
   cat cdc_offset.json
   ```

6. **Keep Consumer running** between tests - only Producer needs restart after reset

---

## 🆘 Getting Help

If you encounter issues not covered here:

1. Check Docker logs:
   ```bash
   docker logs kafka-1
   docker logs db-source
   docker logs db-destination
   ```

2. Check Python program output for error messages

3. Verify database state:
   ```bash
   docker exec -it db-source psql -U postgres -d postgres
   # Then run: SELECT * FROM emp_cdc ORDER BY cdc_id;
   ```

4. Try a complete reset (Method 3 above)

---

**That's it! You now have all the information needed to run, test, and reset the project successfully.** 🎉
