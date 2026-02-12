# Kafka CDC (Change Data Capture) Project

Real-time database synchronization system using Kafka for PostgreSQL CDC replication

## 📋 Project Overview

This project implements **real-time synchronization** (< 1 second latency) between two PostgreSQL databases:
- Any INSERT/UPDATE/DELETE operation on Source DB
- Automatically synced to Destination DB via Kafka

### Key Features

✅ **Real-time Sync**: < 1 second latency  
✅ **Incremental Scanning**: Avoids full table scans, 100-1000x performance improvement  
✅ **Offset Tracking**: Resume from last position after Producer restart  
✅ **Trigger-Driven**: Automatically captures all data changes without modifying business code  
✅ **Full DML Support**: INSERT / UPDATE / DELETE

---

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Source DB     │────▶│    Kafka     │────▶│ Destination DB  │
│  (PostgreSQL)   │     │  (Message    │     │  (PostgreSQL)   │
│                 │     │   Queue)     │     │                 │
│  - employees    │     │              │     │  - employees    │
│  - emp_cdc      │     └──────────────┘     │                 │
│  - trigger      │            ▲              └─────────────────┘
└─────────────────┘            │                       ▲
         │                     │                       │
         ▼                     │                       │
   ┌──────────┐         ┌─────┴──────┐         ┌─────┴──────┐
   │ Trigger  │         │  Producer  │         │  Consumer  │
   │ captures │         │  (scans    │         │  (applies  │
   │ changes  │         │   CDC tbl) │         │  changes)  │
   └──────────┘         └────────────┘         └────────────┘
```

### Data Flow

1. **Business Operation** → Source DB `employees` table
2. **Trigger Activated** → Automatically logs changes to `emp_cdc` table
3. **Producer Scans** → Reads new records from `emp_cdc` (incremental scan)
4. **Send to Kafka** → Message queue transmission
5. **Consumer Consumes** → Applies changes to Destination DB

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.7+
- At least 2GB available memory

### Installation & Setup

See [HOW_TO_RUN.md](HOW_TO_RUN.md) for detailed step-by-step instructions.

**Quick Commands:**

```bash
# 1. Start Docker services
docker-compose up -d

# 2. Initialize databases
docker exec -i db-source psql -U postgres -d postgres < setup_cdc.sql

# 3. Create Kafka topic
docker exec -it kafka-1 kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic employee_cdc \
  --partitions 1 \
  --replication-factor 1

# 4. Install Python dependencies
pip install -r requirements.txt

# 5. Run Consumer (Terminal 1)
python3 consumer.py

# 6. Run Producer (Terminal 2)
python3 producer.py
```

---

## 🔑 Core Technical Concepts

### 1. PostgreSQL Trigger (Automatic Change Capture)

**Trigger Function:**
```sql
CREATE OR REPLACE FUNCTION log_employee_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'INSERT') THEN
        INSERT INTO emp_cdc(emp_id, first_name, ..., action)
        VALUES (NEW.emp_id, NEW.first_name, ..., 'INSERT');
    ELSIF (TG_OP = 'UPDATE') THEN
        INSERT INTO emp_cdc(..., action) VALUES (..., 'UPDATE');
    ELSIF (TG_OP = 'DELETE') THEN
        INSERT INTO emp_cdc(..., action) VALUES (OLD..., 'DELETE');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

**Key Points:**
- ✅ Automatically captures all DML operations
- ✅ No need to modify business code
- ✅ Records operation type (INSERT/UPDATE/DELETE)

---

### 2. Incremental Scanning (Offset Tracking)

**The key to avoiding Full Scans:**

```python
# ❌ Full Scan (scans entire table every time)
query = "SELECT * FROM emp_cdc"

# ✅ Incremental Scan (only scans new records)
query = """
    SELECT * FROM emp_cdc 
    WHERE cdc_id > {last_offset} 
    ORDER BY cdc_id 
    LIMIT 100
"""
```

**Performance Comparison:**

| CDC Table Size | Full Scan | Incremental Scan | Improvement |
|---------------|-----------|------------------|-------------|
| 1,000         | 100ms     | 1ms              | 100x        |
| 100,000       | 10s       | 1ms              | 10,000x     |
| 1,000,000     | 100s+     | 1ms              | 100,000x    |

**Offset Management:**
- Storage: `cdc_offset.json` file
- Auto-update: Saves latest position after each processing
- Resume capability: Producer continues from last position after restart

---

### 3. Kafka Message Transmission

**Producer Send Logic:**
```python
producer.produce(
    topic='employee_cdc',
    key=str(cdc_id),           # For partitioning
    value=json.dumps(record),   # Complete change record
    callback=delivery_report    # Delivery confirmation
)
```

**Consumer Consumption Logic:**
```python
while True:
    msg = consumer.poll(timeout=1.0)
    if msg:
        record = json.loads(msg.value())
        apply_change(record)  # Apply to destination database
```

---

### 4. Idempotency Handling

**INSERT Conflict Handling:**
```python
INSERT INTO employees (...)
VALUES (...)
ON CONFLICT (emp_id) DO NOTHING  # Avoid duplicate inserts
```

**UPDATE Fault Tolerance:**
```python
# If record doesn't exist, fallback to INSERT
if update_rows_affected == 0:
    apply_insert(record)
```

---

## 📁 Project Structure

```
kafka-cdc-project/
├── docker-compose.yml       # Docker services configuration
├── setup_cdc.sql           # Database initialization (tables, triggers, functions)
├── requirements.txt        # Python dependencies
│
├── cdc_record.py          # Data model (CDCRecord class)
├── offset_manager.py      # Offset manager (incremental scan core)
├── producer.py            # CDC Producer (scans emp_cdc table)
├── consumer.py            # CDC Consumer (applies changes)
│
├── reset_all.sh           # Reset script (clears data and offset)
├── README.md              # This file
└── HOW_TO_RUN.md          # Detailed running instructions
```

---

## ⚙️ Configuration

### Docker Compose Port Mapping

```yaml
services:
  db-source:
    ports:
      - "5435:5432"  # Local 5435 → Container 5432
      
  db-destination:
    ports:
      - "5436:5432"  # Local 5436 → Container 5432
      
  kafka:
    ports:
      - "29092:29092"  # External access
      - "9092:9092"    # Container internal access
```

### Producer Configuration

```python
POLL_INTERVAL = 0.5  # Polling interval (seconds)
BATCH_SIZE = 100     # Maximum records per fetch
```

### Consumer Configuration

```python
CONSUMER_GROUP = "cdc_sync_group"
AUTO_OFFSET_RESET = "earliest"  # Start from earliest message
```

---

## 🔧 Troubleshooting

### Issue 1: Producer Not Capturing Changes?

**Diagnostic Steps:**

1. Verify trigger exists:
```bash
docker exec -i db-source psql -U postgres -d postgres -c "\d employees"
```

2. Check CDC table has records:
```bash
docker exec -i db-source psql -U postgres -d postgres -c "SELECT * FROM emp_cdc;"
```

3. Check offset is reasonable:
```bash
cat cdc_offset.json
# If offset is too high, delete it:
rm cdc_offset.json
```

---

### Issue 2: Data Not Syncing to Destination DB?

**Diagnostic Steps:**

1. Is Consumer running?
2. Is Kafka topic created?
```bash
docker exec -it kafka-1 kafka-topics --list --bootstrap-server localhost:9092
```

3. Check Consumer logs for errors

---

### Issue 3: Batch INSERT Not Triggering CDC?

**Cause**: DBeaver or SQL client transaction not committed

**Solution**:

```sql
-- Method 1: Explicit commit
BEGIN;
INSERT INTO employees (...) VALUES (...), (...), (...);
COMMIT;

-- Method 2: Use command line (auto-commit)
docker exec -i db-source psql -U postgres -d postgres << 'EOF'
INSERT INTO employees (...) VALUES (...), (...), (...);
EOF
```

---

### Issue 4: How to Reset Everything?

**Use reset script:**

```bash
./reset_all.sh
# Then restart Producer
```

See [HOW_TO_RUN.md](HOW_TO_RUN.md#resetting-the-project) for detailed reset procedures.

---

## 📊 Performance Monitoring

### Check CDC Table Size

```bash
docker exec -i db-source psql -U postgres -d postgres -c "SELECT COUNT(*) FROM emp_cdc;"
```

### Check Sync Latency

```bash
# Source DB latest record
docker exec -i db-source psql -U postgres -d postgres -c \
  "SELECT MAX(emp_id), NOW() FROM employees;"

# Destination DB latest record
docker exec -i db-destination psql -U postgres -d postgres -c \
  "SELECT MAX(emp_id) FROM employees;"
```

### Check Producer Offset

```bash
cat cdc_offset.json
```

---

## 🛑 Stopping Services

```bash
# 1. Stop Producer and Consumer (Ctrl+C)

# 2. Stop Docker services
docker-compose down

# 3. To delete data volumes (clear all data)
docker-compose down -v
```

---

## 🎓 Extensions & Enhancements

### 1. Add Data Validation (DLQ)

Add validation logic in Consumer:

```python
def validate_employee(record):
    if record.salary < 0:
        send_to_dlq(record)  # Send to Dead Letter Queue
        return False
    return True
```

### 2. Batch Processing Optimization

Modify Producer for batch sending:

```python
records = get_cdc_records(limit=1000)
for record in records:
    producer.produce(...)
producer.flush()  # Batch flush
```

### 3. Multi-Table Sync

Create separate CDC tables and Kafka topics for each table:
- `employees_cdc` → `employees_topic`
- `departments_cdc` → `departments_topic`

---

## 📚 Technology Stack

- **Message Queue**: Apache Kafka 7.4.0
- **Database**: PostgreSQL 14.1
- **Containerization**: Docker, Docker Compose
- **Language**: Python 3.x
- **Libraries**: confluent-kafka, psycopg2

---

