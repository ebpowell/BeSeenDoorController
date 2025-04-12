import psycopg2


class postgres:
    def __init__(self, str_connect):
        self.db_con = psycopg2.connect(str_connect)

    def write_db(self, data, sql_template):
        # Add records tp SQLite database
        cur = self.db_con.cursor()
        [cur.execute(self.generate_query_string(sql_template, token)) for token in data]
        self.db_con.commit()

    def generate_query_string(self, sql, token):
        # Convert list to a string of comma seperated values
        the_string = '","'.join(token)
        the_query = f"""{sql}("{the_string}")"""
        return the_query

    def get_maxid(self, query):
        max_id = 0
        # Add records tp SQLite database
        cur = self.db_con.cursor()
        cur.execute(query)
        row = cur.fetchone()
        if row:
            max_id = row[0]
        return max_id

    def write_new(self, data, sql_template,  max_id):
        # Add records tp SQLite database
        cur = self.db_con.cursor()
        [cur.execute(self.generate_query_string(sql_template, token)) for token in data if int(token[0])>max_id]
        self.db_con.commit()