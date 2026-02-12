"""
CDC Producer
Scans emp_cdc table and sends change records to Kafka
Uses offset tracking to avoid full table scans
"""
import time
import psycopg2
from confluent_kafka import Producer
from confluent_kafka.serialization import StringSerializer
from cdc_record import CDCRecord
from offset_manager import OffsetManager


CDC_TOPIC = "employee_cdc"
POLL_INTERVAL = 0.5  # Poll every 500ms for changes


class CDCProducer:
    """Producer that scans CDC table and publishes to Kafka"""
    
    def __init__(self, db_host="localhost", db_port="5435", kafka_host="localhost", kafka_port="29092"):
        # Database configuration (Source DB)
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
            'acks': 'all'
        }
        self.producer = Producer(kafka_config)
        self.encoder = StringSerializer('utf-8')
        
        # Offset manager
        self.offset_manager = OffsetManager()
        
        self.running = True
    
    def get_cdc_records(self):
        """Fetch new CDC records from database (incremental, not full scan)"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            last_cdc_id = self.offset_manager.get_last_cdc_id()
            
            # Query only NEW records (avoids full table scan!)
            query = """
                SELECT cdc_id, emp_id, first_name, last_name, dob, city, salary, action, created_at
                FROM emp_cdc
                WHERE cdc_id > %s
                ORDER BY cdc_id
                LIMIT 100
            """
            
            cur.execute(query, (last_cdc_id,))
            rows = cur.fetchall()
            
            cur.close()
            conn.close()
            
            return [CDCRecord.from_db_row(row) for row in rows]
            
        except Exception as e:
            print(f"Error fetching CDC records: {e}")
            return []
    
    def delivery_report(self, err, msg):
        """Callback for message delivery reports"""
        if err is not None:
            print(f'❌ Message delivery failed: {err}')
        else:
            print(f'✓ Message delivered: cdc_id={msg.key().decode()}, partition={msg.partition()}, offset={msg.offset()}')
    
    def send_to_kafka(self, record):
        """Send CDC record to Kafka"""
        try:
            self.producer.produce(
                CDC_TOPIC,
                key=self.encoder(str(record.cdc_id)),
                value=self.encoder(record.to_json()),
                callback=self.delivery_report
            )
            self.producer.poll(0)  # Trigger delivery callbacks
            return True
        except Exception as e:
            print(f"Error sending to Kafka: {e}")
            return False
    
    def process_cdc_records(self):
        """Process CDC records and send to Kafka"""
        records = self.get_cdc_records()
        
        if records:
            print(f"\n📦 Found {len(records)} new CDC record(s)")
            
            for record in records:
                print(f"Processing: {record.action} - emp_id={record.emp_id}, cdc_id={record.cdc_id}")
                
                if self.send_to_kafka(record):
                    # Update offset after successful send
                    self.offset_manager.save_offset(record.cdc_id)
            
            # Flush remaining messages
            self.producer.flush()
            print(f"✅ Processed {len(records)} record(s), offset updated to {self.offset_manager.get_last_cdc_id()}")
        
        return len(records)
    
    def run(self):
        """Main loop - continuously poll for CDC changes"""
        print("=" * 60)
        print("CDC Producer Started")
        print("=" * 60)
        print(f"Database: {self.db_config['host']}:{self.db_config['port']}")
        print(f"Topic: {CDC_TOPIC}")
        print(f"Poll Interval: {POLL_INTERVAL}s")
        print(f"Starting from CDC ID: {self.offset_manager.get_last_cdc_id()}")
        print("=" * 60)
        print("\nWaiting for changes in emp_cdc table...\n")
        
        try:
            while self.running:
                self.process_cdc_records()
                time.sleep(POLL_INTERVAL)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Producer stopped by user")
        finally:
            print(f"Final offset: {self.offset_manager.get_last_cdc_id()}")
            self.producer.flush()
            print("Producer shut down gracefully")


if __name__ == '__main__':
    producer = CDCProducer()
    producer.run()
