import sqlite3


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