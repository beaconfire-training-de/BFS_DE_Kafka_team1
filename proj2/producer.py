"""
Copyright (C) 2024 BeaconFire Staffing Solutions
Author: Ray Wang

This file is part of Oct DE Batch Kafka Project 1 Assignment.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import json
import time
from confluent_kafka import Producer
from employee import Employee
import psycopg2
from psycopg2 import pool

employee_topic_name = "bf_employee_cdc"

class cdcProducer(Producer):
    #if running outside Docker (i.e. producer is NOT in the docer-compose file): host = localhost and port = 29092
    #if running inside Docker (i.e. producer IS IN the docer-compose file), host = 'kafka' or whatever name used for the kafka container, port = 9092
    def __init__(self, host="localhost", port="29092", db_host="localhost", db_port="5432"):
        self.host = host
        self.port = port
        producerConfig = {'bootstrap.servers':f"{self.host}:{self.port}",
                          'acks' : 'all'}
        super().__init__(producerConfig)
        self.running = True

        # Create database connection pool
        try:
            self.db_pool = pool.SimpleConnectionPool(
                1, 5,  # min and max connections
                host=db_host,
                database="postgres",
                user="postgres",
                port=db_port,
                password="postgres"
            )
            print(f"Database connection pool created for {db_host}:{db_port}")
        except Exception as err:
            print(f"Error creating database connection pool: {err}")
            raise

    def fetch_cdc(self, last_action_id=0):
        conn = None
        try:
            conn = self.db_pool.getconn()
            cur = conn.cursor()
            # Query emp_cdc table for records after last_action_id
            cur.execute(
                "SELECT action_id, emp_id, first_name, last_name, dob, city, salary, action FROM emp_cdc WHERE action_id > %s ORDER BY action_id ASC",
                (last_action_id,)
            )
            rows = cur.fetchall()
            cur.close()
            return rows
        except Exception as err:
            print(f"Error fetching CDC data: {err}")
            return []
        finally:
            if conn:
                self.db_pool.putconn(conn)

    def close(self):
        """Clean up resources"""
        if hasattr(self, 'db_pool') and self.db_pool:
            self.db_pool.closeall()
            print("Database connection pool closed")
    

if __name__ == '__main__':
    producer = cdcProducer()
    last_action_id = 0

    try:
        while producer.running:
            try:
                rows = producer.fetch_cdc(last_action_id)
                if rows:
                    for row in rows:
                        action_id, emp_id, first_name, last_name, dob, city, salary, action = row
                        # Create Employee object
                        employee = Employee(action_id, emp_id, first_name, last_name, str(dob), city, salary, action)
                        # Send to Kafka
                        producer.produce(
                            employee_topic_name,
                            key=str(emp_id),
                            value=employee.to_json(),
                            callback=lambda err, msg, aid=action_id: print(
                                f"Message sent: action_id={aid}, emp_id={msg.key().decode()} - {msg.topic()}[{msg.partition()}]@{msg.offset()}"
                                if err is None else f"Error sending action_id={aid}: {err}"
                            )
                        )
                        last_action_id = action_id
                    producer.flush()
                    print(f"Processed {len(rows)} CDC records, last action_id: {last_action_id}")
                else:
                    # No new records, wait a bit before polling again
                    time.sleep(1)
            except KeyboardInterrupt:
                print("Producer stopped by user")
                producer.running = False
            except Exception as e:
                print(f"Error in producer main loop: {e}")
                time.sleep(1)
    finally:
        producer.close()
        print("Producer shutdown complete")
