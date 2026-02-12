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


import os
import psycopg2
from time import sleep
from employee import Employee
from confluent_kafka import Producer
from confluent_kafka.serialization import StringSerializer


employee_topic_name = "bf_employee_cdc"

class cdcProducer(Producer):
    #if running outside Docker (i.e. producer is NOT in the docker-compose file): host = localhost and port = 29092
    #if running inside Docker (i.e. producer IS IN the docker-compose file), host = 'kafka' or whatever name used for the kafka container, port = 9092
    def __init__(self, host="localhost", port="29092"):
        self.host = host
        self.port = port
        producerConfig = {'bootstrap.servers':f"{self.host}:{self.port}",
                          'acks' : 'all'}
        super().__init__(producerConfig)
        self.running = True

    @staticmethod
    def fetch_cdc():
        try:
            conn = psycopg2.connect(
                host="localhost",
                database="bf_source",
                user="postgres",
                port = '5432',
                password="postgres")
            conn.autocommit = True
            cur = conn.cursor()
            #your logic should go here

            # Read last offset
            last_id = 0
            if os.path.exists('last_cdc.txt'):
                with open('last_cdc.txt','r') as f:
                    last_id = int(f.read())

            # SQL Clause to fetch new data
            query = """
            SELECT cdc_id, emp_id, first_name, last_name, dob, city, salary, action, changed_at
            FROM emp_cdc
            WHERE cdc_id > %s
            ORDER BY cdc_id;
            """
            cur.execute(query, (last_id,))
            rows = cur.fetchall()

            # Print
            for row in rows:
                print("CDC ROW:", row)

            # Update offset
            if rows:
                new_last_id = rows[-1][0]
                with open('last_cdc.txt','w') as f:
                    f.write(str(new_last_id))

            cur.close()
            conn.close()

            return rows

        except Exception as err:
            print("Error fetching CDC:",err)
            return []

        # return # if you need to return sth, modify here


if __name__ == '__main__':
    encoder = StringSerializer('utf-8')
    producer = cdcProducer()

    def delivery_report(err, msg):
        if err:
            print("Message delivery failed: {}".format(err))
        else:
            print("Send to {} [{}]".format(msg.topic(), msg.partition()))

    try:
        while producer.running:
            rows = producer.fetch_cdc()

            for row in rows:
                emp = Employee.from_line(row)

                producer.produce(
                    topic=employee_topic_name,
                    key=encoder(str(emp.emp_id), None),
                    value=encoder(emp.to_json(), None),
                    callback=delivery_report
                )

            if rows:
                producer.flush()

            sleep(1)
    except KeyboardInterrupt as err:
        print("\n Stopping Producer")
    
