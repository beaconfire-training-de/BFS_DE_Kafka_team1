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
import psycopg2
from employee import Employee
from producer import employee_topic_name
from confluent_kafka.serialization import StringDeserializer
from confluent_kafka import Producer, Consumer, KafkaError, KafkaException

class cdcConsumer(Consumer):
    #if running outside Docker (i.e. producer is NOT in the docker-compose file): host = localhost and port = 29092
    #if running inside Docker (i.e. producer IS IN the docker-compose file), host = 'kafka' or whatever name used for the kafka container, port = 9092
    def __init__(self, host: str = "localhost", port: str = "29092", group_id: str = '', decoder = None):
        self.conf = {'bootstrap.servers': f'{host}:{port}',
                     'group.id': group_id,
                     'enable.auto.commit': True,
                     'auto.offset.reset': 'earliest'}
        super().__init__(self.conf)
        self.keep_running = True
        self.group_id = group_id


        # DLQ Producer
        self.dlq_producer = Producer({'bootstrap.servers': f'{host}:{port}',})
        self.dlq_topic = "bf_employee_cdc_dlq"

        # Decoder
        self.decoder = decoder or StringDeserializer('utf-8')

    def update_dst(self, msg):
        try:
            value_str = self.decoder(msg.value(), None)
            emp = Employee(**(json.loads(value_str)))

            conn = psycopg2.connect(
                host="localhost",
                database="bf_destination",
                user="postgres",
                port='5433',  # change this port number to align with the docker compose file
                password="postgres")
            conn.autocommit = True
            cur = conn.cursor()

            # your logic goes here
            if emp.action == "INSERT":
                cur.execute(
                    """
                    INSERT INTO employees
                        (emp_id, first_name, last_name, dob, city, salary)
                    VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (emp_id) DO NOTHING
                    """,
                    (emp.emp_id, emp.first_name, emp.last_name, emp.dob, emp.city, emp.salary)
                )
                print("Insert employee id: ", emp.emp_id)

            elif emp.action == "UPDATE":
                cur.execute(
                    """
                    UPDATE employees
                    SET first_name=%s,
                        last_name=%s,
                        dob=%s,
                        city=%s,
                        salary=%s
                    WHERE emp_id = %s
                    """,
                    (emp.first_name, emp.last_name, emp.dob, emp.city, emp.salary, emp.emp_id)
                )
                print("Update employee id: ", emp.emp_id)

            elif emp.action == "DELETE":
                cur.execute(
                    "DELETE FROM employees WHERE emp_id=%s",
                    (emp.emp_id,)
                )
                print("Delete employee id: ", emp.emp_id)

            cur.close()
            conn.close()
        except Exception as err:
            print(err)
            dlq_payload = json.dumps({
                "error": str(err),
                "original": msg.value().decode("utf-8", errors="ignore")
            }).encode("utf-8")

            self.dlq_producer.produce(
                topic = self.dlq_topic,
                value = dlq_payload
            )
            self.dlq_producer.flush()

    def run(self, topics, processing_func):
        try:
            self.subscribe(topics)
            while self.keep_running:
                #implement your logic here

                msg = self.poll(1.0)

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        raise KafkaException(msg.error())

                processing_func(msg)

        except KeyboardInterrupt:
            print("\n Stopping consumer...")

        finally:
            self.close()





if __name__ == '__main__':
    consumer = cdcConsumer(group_id="bf_cdc_group")
    consumer.run([employee_topic_name], consumer.update_dst)