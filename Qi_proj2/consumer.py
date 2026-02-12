"""
CDC Consumer
Consumes CDC records from Kafka and applies changes to destination database
Handles INSERT, UPDATE, and DELETE operations
"""
import psycopg2
from confluent_kafka import Consumer, KafkaError, KafkaException
from cdc_record import CDCRecord


CDC_TOPIC = "employee_cdc"
CONSUMER_GROUP = "cdc_sync_group"


class CDCConsumer:
    """Consumer that applies CDC changes to destination database"""
    
    def __init__(self, db_host="localhost", db_port="5436", kafka_host="localhost", kafka_port="29092"):
        # Database configuration (Destination DB)
        self.db_config = {
            'host': db_host,
            'port': db_port,
            'database': 'postgres',
            'user': 'postgres',
            'password': 'postgres'
        }
        
        # Kafka configuration
        kafka_config = {
            'bootstrap.servers': f'{kafka_host}:{kafka_port}',
            'group.id': CONSUMER_GROUP,
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': True
        }
        self.consumer = Consumer(kafka_config)
        
        self.running = True
        self.processed_count = {'INSERT': 0, 'UPDATE': 0, 'DELETE': 0}
    
    def apply_insert(self, record):
        """Apply INSERT operation to destination database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            conn.autocommit = True
            cur = conn.cursor()
            
            query = """
                INSERT INTO employees (emp_id, first_name, last_name, dob, city, salary)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (emp_id) DO NOTHING
            """
            
            cur.execute(query, (
                record.emp_id,
                record.first_name,
                record.last_name,
                record.dob,
                record.city,
                record.salary
            ))
            
            cur.close()
            conn.close()
            
            print(f"✓ INSERT: emp_id={record.emp_id}, {record.first_name} {record.last_name}")
            self.processed_count['INSERT'] += 1
            
        except Exception as e:
            print(f"❌ Error applying INSERT: {e}")
    
    def apply_update(self, record):
        """Apply UPDATE operation to destination database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            conn.autocommit = True
            cur = conn.cursor()
            
            query = """
                UPDATE employees
                SET first_name = %s,
                    last_name = %s,
                    dob = %s,
                    city = %s,
                    salary = %s
                WHERE emp_id = %s
            """
            
            cur.execute(query, (
                record.first_name,
                record.last_name,
                record.dob,
                record.city,
                record.salary,
                record.emp_id
            ))
            
            rows_affected = cur.rowcount
            
            cur.close()
            conn.close()
            
            if rows_affected > 0:
                print(f"✓ UPDATE: emp_id={record.emp_id}, {record.first_name} {record.last_name}")
                self.processed_count['UPDATE'] += 1
            else:
                print(f"⚠️  UPDATE: emp_id={record.emp_id} not found (applying as INSERT)")
                self.apply_insert(record)
            
        except Exception as e:
            print(f"❌ Error applying UPDATE: {e}")
    
    def apply_delete(self, record):
        """Apply DELETE operation to destination database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            conn.autocommit = True
            cur = conn.cursor()
            
            query = "DELETE FROM employees WHERE emp_id = %s"
            
            cur.execute(query, (record.emp_id,))
            
            rows_affected = cur.rowcount
            
            cur.close()
            conn.close()
            
            if rows_affected > 0:
                print(f"✓ DELETE: emp_id={record.emp_id}")
                self.processed_count['DELETE'] += 1
            else:
                print(f"⚠️  DELETE: emp_id={record.emp_id} not found")
            
        except Exception as e:
            print(f"❌ Error applying DELETE: {e}")
    
    def process_message(self, msg):
        """Process a single CDC message"""
        try:
            # Deserialize CDC record
            record = CDCRecord.from_json(msg.value().decode('utf-8'))
            
            # Apply change based on action
            if record.action == 'INSERT':
                self.apply_insert(record)
            elif record.action == 'UPDATE':
                self.apply_update(record)
            elif record.action == 'DELETE':
                self.apply_delete(record)
            else:
                print(f"⚠️  Unknown action: {record.action}")
                
        except Exception as e:
            print(f"❌ Error processing message: {e}")
    
    def print_statistics(self):
        """Print processing statistics"""
        total = sum(self.processed_count.values())
        print("\n" + "=" * 60)
        print("Processing Statistics:")
        print("=" * 60)
        print(f"INSERT: {self.processed_count['INSERT']}")
        print(f"UPDATE: {self.processed_count['UPDATE']}")
        print(f"DELETE: {self.processed_count['DELETE']}")
        print(f"TOTAL:  {total}")
        print("=" * 60 + "\n")
    
    def run(self):
        """Main loop - consume messages from Kafka"""
        print("=" * 60)
        print("CDC Consumer Started")
        print("=" * 60)
        print(f"Database: {self.db_config['host']}:{self.db_config['port']}")
        print(f"Topic: {CDC_TOPIC}")
        print(f"Consumer Group: {CONSUMER_GROUP}")
        print("=" * 60)
        print("\nWaiting for CDC messages...\n")
        
        try:
            self.consumer.subscribe([CDC_TOPIC])
            
            while self.running:
                msg = self.consumer.poll(timeout=1.0)
                
                if msg is None:
                    continue
                
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        print(f"Reached end of partition {msg.partition()}")
                    else:
                        raise KafkaException(msg.error())
                else:
                    self.process_message(msg)
                    
        except KeyboardInterrupt:
            print("\n\n🛑 Consumer stopped by user")
        finally:
            self.print_statistics()
            self.consumer.close()
            print("Consumer shut down gracefully")


if __name__ == '__main__':
    consumer = CDCConsumer()
    consumer.run()
