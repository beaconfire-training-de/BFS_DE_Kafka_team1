# BFS_DE_Kafka_team1
# PostgreSQL CDC Pipeline with Debezium & Kafka

A production-grade Change Data Capture (CDC) implementation using Debezium, Kafka Connect, and PostgreSQL. This is an optimized version that replaces the original Python-based producer/consumer with trigger+function approach.

## Architecture Overview

```
PostgreSQL (Source)
    |
    | WAL (Write-Ahead Log)
    v
Debezium Source Connector
    |
    v
Kafka Broker (KRaft mode)
    |
    v
Debezium Sink Connector
    |
    v
PostgreSQL (Target)
```

## Key Technical Stack

### Kafka KRaft Mode
- **No Zookeeper dependency**: Kafka now runs in KRaft (Kafka Raft) mode, eliminating the need for Zookeeper
- Single-node configuration suitable for development and testing
- Simplified architecture with broker acting as both broker and controller
- Faster metadata propagation and cluster recovery

### Kafka Connect
- **Debezium PostgreSQL Source Connector**: Captures changes from source database using PostgreSQL's logical replication
- **Debezium JDBC Sink Connector**: Writes changes to target database with upsert capability
- Distributed, scalable architecture
- Native integration with Kafka ecosystem

### Log Compaction
- Topic cleanup policy: `compact,delete`
- Retains the latest state for each key while removing outdated records
- Configurable `min.cleanable.dirty.ratio` (0.1) for performance tuning
- Reduces storage footprint while maintaining data consistency
- Retention period: 7 days (604800000 ms)

### Dead Letter Queue (DLQ)
- Separate DLQ topics for source and sink connectors
- `dlq_source`: Handles errors from source connector
- `dlq_sink`: Handles errors from sink connector
- Full context headers for debugging
- Message logging enabled for troubleshooting
- Prevents pipeline failure due to individual message errors

### Error Handling & Resilience
- `errors.tolerance: all` - Continue processing despite errors
- DLQ with context headers for error analysis
- Comprehensive error logging
- Automatic retry mechanisms

### Schema Evolution
- `auto.create: true` - Automatically creates target tables
- `auto.evolve: true` - Handles schema changes dynamically
- `schema.evolution: basic` - Supports adding/removing columns

## Prerequisites

- Docker and Docker Compose
- PostgreSQL 16 (via Docker)
- Kafka 7.6.1 (Confluent Platform)
- Debezium Connect 2.5

## Configuration Highlights

### Source Connector Configuration

**Logical Replication Setup**
- Plugin: `pgoutput` (PostgreSQL native)
- Replication slot: `debezium_pgsource_slot`
- Publication: `debezium_pub` with filtered mode
- WAL level: `logical` (configured in PostgreSQL)

**Data Type Handling**
- Decimal: String representation (avoids precision loss)
- Time: Connect precision mode
- Tombstones disabled for delete events

**Topic Configuration**
- 3 partitions per topic for parallelism
- LZ4 compression for efficiency
- Replication factor: 1 (single-node)

### Sink Connector Configuration

**Write Mode**
- Insert mode: `upsert` (handles both inserts and updates)
- Primary key mode: `record_key`
- Delete support enabled
- Table auto-creation and schema evolution

**Resilience**
- Error tolerance: All
- Dead letter queue enabled
- Full context preservation

## Quick Start

### 1. Start Infrastructure

```bash
docker-compose up -d
```

Wait for all services to become healthy (approximately 60 seconds).

### 2. Verify Kafka Connect

```bash
curl http://localhost:8083/connector-plugins
```

### 3. Create Source Table

```bash
docker exec -it postgres-source psql -U cdc -d bf_source

CREATE TABLE employees (
    emp_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    department VARCHAR(50),
    salary DECIMAL(10,2),
    hire_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4. Deploy Source Connector

```bash
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d @postg-source-connector.json
```

### 5. Deploy Sink Connector

```bash
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d @postg-sink-connector.json
```

### 6. Test CDC Pipeline

Insert data into source:
```sql
INSERT INTO employees (name, email, department, salary, hire_date)
VALUES ('John Doe', 'john@example.com', 'Engineering', 75000.00, '2024-01-15');
```

Verify in target:
```bash
docker exec -it postgres-target psql -U cdc -d bf_target -c "SELECT * FROM employees;"
```

## Monitoring & Management

### Check Connector Status

```bash
# List all connectors
curl http://localhost:8083/connectors

# Source connector status
curl http://localhost:8083/connectors/pg-source-connector/status

# Sink connector status
curl http://localhost:8083/connectors/pg-sink-connector/status
```

### View Kafka Topics

```bash
docker exec cdc-kafka kafka-topics --list --bootstrap-server localhost:9092
```

### Consume Messages

```bash
docker exec cdc-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic pgsource.public.employees \
  --from-beginning
```

### Check Dead Letter Queue

```bash
# Source DLQ
docker exec cdc-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic dlq_source \
  --from-beginning

# Sink DLQ
docker exec cdc-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic dlq_sink \
  --from-beginning
```

### View Replication Slots

```bash
docker exec postgres-source psql -U cdc -d bf_source -c \
  "SELECT * FROM pg_replication_slots;"
```

## Performance Considerations

### Topic Partitioning
- 3 partitions allow parallel processing
- Partition key based on primary key ensures ordering per record
- Scalable to multiple consumer instances

### Compression
- LZ4 compression reduces network and storage overhead
- Lower latency compared to gzip
- Good balance between compression ratio and CPU usage

### Log Compaction
- Reduces storage by keeping only latest state
- Background compaction doesn't impact produce/consume performance
- Configurable dirty ratio (0.1) for tuning

### Resource Allocation
- Single-node Kafka suitable for development
- Production: Scale to 3+ brokers with replication factor 3
- Adjust partition count based on throughput requirements

## Comparison with Original Implementation

| Aspect | Original (Python) | Optimized (Debezium) |
|--------|------------------|----------------------|
| Architecture | Custom producer/consumer | Kafka Connect framework |
| Change Detection | PostgreSQL triggers | Native WAL parsing |
| Schema Changes | Manual migration | Automatic evolution |
| Error Handling | Application-level | DLQ + retry mechanisms |
| Scalability | Single-threaded | Distributed, multi-task |
| Maintenance | Custom code | Configuration-based |
| Monitoring | Custom logging | Built-in metrics |
| Dependencies | Python libraries | Debezium connectors |

## Troubleshooting

### Connector Failed to Start

```bash
# View connector logs
docker-compose logs connect

# Restart connector
curl -X POST http://localhost:8083/connectors/pg-source-connector/restart
```

### Replication Slot Not Advancing

```bash
# Check slot status
docker exec postgres-source psql -U cdc -d bf_source -c \
  "SELECT * FROM pg_replication_slots WHERE slot_name = 'debezium_pgsource_slot';"

# If inactive, restart connector
curl -X POST http://localhost:8083/connectors/pg-source-connector/restart
```

### Messages in DLQ

```bash
# Check DLQ messages with headers
docker exec cdc-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic dlq_sink \
  --property print.headers=true \
  --from-beginning
```

### Target Table Not Created

Verify sink connector configuration:
- `auto.create: true` must be set
- Database user must have CREATE TABLE permission
- Check connector logs for schema evolution errors

## Cleanup

```bash
# Stop all services
docker-compose down

# Remove volumes (deletes all data)
docker-compose down -v
```

## Production Recommendations

1. **Kafka Cluster**: Deploy 3+ brokers with replication factor 3
2. **Security**: Enable SSL/TLS and SASL authentication
3. **Monitoring**: Integrate Prometheus + Grafana
4. **Backup**: Regular PostgreSQL backups and Kafka topic snapshots
5. **Resource Limits**: Set memory and CPU limits in docker-compose
6. **Network**: Use dedicated VPC/network for database connectivity
7. **Replication Slots**: Monitor and clean up inactive slots
8. **Log Retention**: Adjust retention based on storage capacity
9. **Testing**: Implement chaos engineering for failure scenarios
10. **Documentation**: Maintain runbooks for common operations

## References

- Debezium Documentation: https://debezium.io/documentation/
- Kafka KRaft: https://kafka.apache.org/documentation/#kraft
- PostgreSQL Logical Replication: https://www.postgresql.org/docs/current/logical-replication.html
- Kafka Connect: https://docs.confluent.io/platform/current/connect/
