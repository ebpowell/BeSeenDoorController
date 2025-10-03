import sqlite3
import datetime


class cls_sqlite:
    def __init__(self, path):
        self.db_path = path

    def write_db(self, data, sql_template):
        db = sqlite3.connect(self.db_path)
        # Add records tp SQLite database
        cur = db.cursor()
        [cur.execute(self.generate_query_string(sql_template, token)) for token in data]
        db.commit()
        # Close the database
        db.close()

    def get_maxid(self, query):
        max_id = 0
        db = sqlite3.connect(self.db_path)
        # Add records tp SQLite database
        cur = db.cursor()
        cur.execute(query)
        row = cur.fetchone()
        if row:
            max_id = row[0]
        # Close the database
        db.close()
        return max_id

    def purge_db(self, table):
        db = sqlite3.connect(self.db_path)
        # Add records tp SQLite database
        cur = db.cursor()
        cur.execute(f"delete from {table}")
        db.commit()

    def generate_query_string(self, sql, token):
        # Convert list to a string of comma seperated values
        the_string = '","'.join(token)
        the_query = f"""{sql}("{the_string}")"""
        return the_query

    def get_fob_records(self):
        db = sqlite3.connect(self.db_path)
        cur = db.cursor()
        cur.execute('select distinct record_id from system_fobs order by record_id asc')
        rows = cur.fetchall()
        # Close the database
        db.close()
        return rows

    def insert_access_list_record(self, record):
        db = sqlite3.connect(self.db_path)
        # Add a timestamp tp the record
        record.append(str(datetime.datetime.now()))
        # Add records tp SQLite database
        query = 'INSERT INTO access_control (record_id, fob_id, door, status, controller, record_time) values'
        sql = self.generate_query_string(query, record)
        cur = db.cursor()
        cur.execute(sql)
        db.commit()
        db.close()

    def write_new(self, data, sql_template,  max_id):
        db = sqlite3.connect(self.db_path)
        # Add records tp SQLite database
        cur = db.cursor()
        [cur.execute(self.generate_query_string(sql_template, token)) for token in data if int(token[0])>max_id]
        db.commit()
        db.close()