"""
Copyright (C) 2024 BeaconFire Staffing Solutions
Author: Ray Wang

Production-Ready CDC Consumer with:
- Database Connection Pool
- Manual Offset Commit
- Transaction Support
- Dead Letter Queue (DLQ)
- Idempotency (Exactly-Once Semantics)
- Retry Mechanism
- Error Handling
"""

import json
import psycopg2
from psycopg2 import pool
from confluent_kafka import Consumer, Producer, KafkaError, KafkaException
from employee import Employee
from producer import employee_topic_name

DLQ_TOPIC = "bf_employee_cdc_dlq"
MAX_RETRIES = 3


class ProductionCDCConsumer(Consumer):
    """
    Production-ready CDC Consumer with all enterprise features
    """

    def __init__(self, host: str = "localhost", port: str = "29092", group_id: str = '',
                 db_host: str = "localhost", db_port: str = "5433",
                 enable_dlq: bool = True, enable_idempotency: bool = True):

        self.conf = {
            'bootstrap.servers': f'{host}:{port}',
            'group.id': group_id,
            'enable.auto.commit': False,  # Manual commit for reliability
            'auto.offset.reset': 'earliest'
        }
        super().__init__(self.conf)
        self.keep_running = True
        self.enable_dlq = enable_dlq
        self.enable_idempotency = enable_idempotency

        # Statistics
        self.stats = {
            'processed': 0,
            'failed': 0,
            'duplicates_skipped': 0,
            'dlq_sent': 0
        }

        # Create DLQ producer if enabled
        if self.enable_dlq:
            self.dlq_producer = Producer({'bootstrap.servers': f'{host}:{port}'})
            print(f"✓ DLQ enabled: {DLQ_TOPIC}")

        # Create database connection pool
        try:
            self.db_pool = pool.SimpleConnectionPool(
                1, 10,  # min and max connections
                host=db_host,
                database="postgres",
                user="postgres",
                port=db_port,
                password="postgres"
            )
            print(f"✓ Database connection pool created ({db_host}:{db_port})")
            print(f"✓ Idempotency: {'Enabled' if enable_idempotency else 'Disabled'}")
        except Exception as err:
            print(f"✗ Error creating database connection pool: {err}")
            raise

    def send_to_dlq(self, msg, error_reason):
        """Send failed message to Dead Letter Queue"""
        if not self.enable_dlq:
            return False

        try:
            dlq_payload = {
                'original_topic': msg.topic(),
                'original_partition': msg.partition(),
                'original_offset': msg.offset(),
                'original_key': msg.key().decode() if msg.key() else None,
                'original_value': msg.value().decode(),
                'error_reason': str(error_reason),
                'timestamp': msg.timestamp()[1] if msg.timestamp()[0] else None
            }

            self.dlq_producer.produce(
                DLQ_TOPIC,
                key=msg.key(),
                value=json.dumps(dlq_payload)
            )
            self.dlq_producer.flush()
            self.stats['dlq_sent'] += 1
            return True
        except Exception as e:
            print(f"✗ Failed to send to DLQ: {e}")
            return False

    def is_already_processed(self, action_id, conn):
        """Check if event was already processed (idempotency)"""
        if not self.enable_idempotency:
            return False

        try:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM processed_events WHERE action_id = %s", (action_id,))
            result = cur.fetchone()
            cur.close()
            return result is not None
        except Exception as e:
            # If table doesn't exist, idempotency is disabled
            if "does not exist" in str(e):
                print(f"⚠ processed_events table not found, idempotency disabled")
                self.enable_idempotency = False
            return False

    def mark_as_processed(self, action_id, emp_id, action, partition, offset, conn):
        """Mark event as processed (idempotency)"""
        if not self.enable_idempotency:
            return

        cur = conn.cursor()
        cur.execute(
            "INSERT INTO processed_events (action_id, emp_id, action, kafka_partition, kafka_offset) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (action_id) DO NOTHING",
            (action_id, emp_id, action, partition, offset)
        )
        cur.close()

    def process_message(self, msg):
        """
        Process a CDC message with full error handling and idempotency
        Returns True if successful, False otherwise
        """
        conn = None
        try:
            e = Employee(**json.loads(msg.value().decode('utf-8')))
            conn = self.db_pool.getconn()
            conn.autocommit = False

            # Idempotency check
            if self.is_already_processed(e.action_id, conn):
                print(f"⏩ Skipping duplicate: action_id={e.action_id}, emp_id={e.emp_id}")
                self.stats['duplicates_skipped'] += 1
                conn.rollback()
                return True  # Return True to commit offset

            cur = conn.cursor()

            # Process the CDC event
            if e.action == "INSERT" or e.action == "UPDATE":
                cur.execute(
                    "INSERT INTO employees (emp_id, first_name, last_name, dob, city, salary) "
                    "VALUES (%s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (emp_id) DO UPDATE SET "
                    "first_name=EXCLUDED.first_name, last_name=EXCLUDED.last_name, "
                    "dob=EXCLUDED.dob, city=EXCLUDED.city, salary=EXCLUDED.salary",
                    (e.emp_id, e.emp_FN, e.emp_LN, e.emp_dob, e.emp_city, e.emp_salary)
                )
            elif e.action == "DELETE":
                cur.execute("DELETE FROM employees WHERE emp_id = %s", (e.emp_id,))
            else:
                print(f"✗ Unknown action: {e.action}")
                conn.rollback()
                cur.close()
                return False

            # Mark as processed (idempotency)
            self.mark_as_processed(e.action_id, e.emp_id, e.action,
                                  msg.partition(), msg.offset(), conn)

            # Commit transaction
            conn.commit()
            cur.close()
            self.stats['processed'] += 1

            if self.stats['processed'] % 10 == 0:
                self.print_stats()

            return True

        except Exception as err:
            print(f"✗ Error processing message: {err}")
            if conn:
                conn.rollback()
            self.stats['failed'] += 1
            return False
        finally:
            if conn:
                self.db_pool.putconn(conn)

    def consume(self, topics):
        """Main consumption loop with retry and DLQ support"""
        retry_count = {}  # Track retry attempts per offset

        try:
            self.subscribe(topics)
            print(f"🚀 Consumer started, subscribed to: {topics}")
            print("=" * 60)

            while self.keep_running:
                msg = self.poll(timeout=1.0)
                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        raise KafkaException(msg.error())

                # Track retries
                offset_key = f"{msg.partition()}:{msg.offset()}"
                current_retry = retry_count.get(offset_key, 0)

                # Process message
                success = self.process_message(msg)

                if success:
                    # Success - commit and clear retry counter
                    self.commit(msg)
                    retry_count.pop(offset_key, None)
                else:
                    # Failed - check retry limit
                    if current_retry >= MAX_RETRIES:
                        print(f"⚠ Max retries ({MAX_RETRIES}) exceeded for offset {msg.offset()}")
                        # Send to DLQ and commit to skip this message
                        self.send_to_dlq(msg, f"Max retries exceeded after {MAX_RETRIES} attempts")
                        self.commit(msg)
                        retry_count.pop(offset_key, None)
                    else:
                        # Increment retry counter but don't commit
                        retry_count[offset_key] = current_retry + 1
                        print(f"⟳ Retry {current_retry + 1}/{MAX_RETRIES} for offset {msg.offset()}")

        except KeyboardInterrupt:
            print("\n⚠ Consumer interrupted by user")
        finally:
            self.print_final_stats()
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'db_pool') and self.db_pool:
            self.db_pool.closeall()
            print("✓ Database connection pool closed")
        if hasattr(self, 'dlq_producer') and self.dlq_producer:
            self.dlq_producer.flush()
        self.close()

    def print_stats(self):
        """Print current statistics"""
        print(f"📊 Stats: Processed={self.stats['processed']}, "
              f"Failed={self.stats['failed']}, "
              f"Duplicates={self.stats['duplicates_skipped']}, "
              f"DLQ={self.stats['dlq_sent']}")

    def print_final_stats(self):
        """Print final statistics"""
        print("\n" + "=" * 60)
        print("📊 Final Statistics:")
        print(f"  ✓ Successfully processed: {self.stats['processed']}")
        print(f"  ✗ Failed: {self.stats['failed']}")
        print(f"  ⏩ Duplicates skipped: {self.stats['duplicates_skipped']}")
        print(f"  📮 Sent to DLQ: {self.stats['dlq_sent']}")
        print("=" * 60)


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Production CDC Consumer")
    print("=" * 60)
    print("Features:")
    print("  • Database connection pool (1-10 connections)")
    print("  • Manual offset commit (at-least-once delivery)")
    print("  • Transaction support (atomicity)")
    print("  • Dead Letter Queue (error isolation)")
    print("  • Idempotency (exactly-once semantics)")
    print("  • Retry mechanism (max 3 attempts)")
    print("=" * 60)

    consumer = ProductionCDCConsumer(
        group_id='production_cdc_consumer',
        enable_dlq=True,
        enable_idempotency=True
    )

    consumer.consume([employee_topic_name])
    print("✓ Consumer shutdown complete")
