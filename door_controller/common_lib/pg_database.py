import psycopg2
import datetime


class postgres:
    def __init__(self, str_connect):
        self.db_con = psycopg2.connect(str_connect)

    def get_maxid(self, query):
        max_id = 0
        # Add records tp SQLite database
        cur = self.db_con.cursor()
        cur.execute(query)
        row = cur.fetchone()
        if row:
            max_id = row[0]
        return max_id

    def gen_swipe_record(self, record, sql):
        str_query = F"""{sql} ({int(record[0])}, {int(record[1])}, '{record[2]}',{record[3]},'{record[4]}','{record[5]}')"""
        print (str_query)
        return str_query

    def insert_swipe_record(self, data, max_id):
        query = ('INSERT INTO dataload.t_keyswipes_slop '
                 '(record_id, fob_id,  status, door, swipe_timestamp, door_controller_ip) values')
        # Add records tp SQLite database
        cur = self.db_con.cursor()
        [cur.execute(self.gen_swipe_record(record, query)) for record in data if int(record[0])>max_id]
        self.db_con.commit()

    def insert_access_list_record(self, data):
        # db = sqlite3.connect(self.db_path)
        # Add records tp SQLite database
        dt_now = datetime.datetime.now()
        now = "'{}'".format(dt_now.strftime("%Y-%m-%d %H:%M:%S"))
        cidr = data[4][7:] + '/32'
        cidr = "'{}'".format(cidr)
        door_id = int(data[2][1:2])
        query = ('INSERT INTO dataload.access_list_from_controller_slop '
                 '(record_id, fob_id, status, door_id, controller_ip, record_time) values')
        cur = self.db_con.cursor()
        sql = F"""{query} ({int(data[0])}, {int(data[1])}, '{data[3]}',{door_id}, {cidr}, {now})"""
        print(sql)
        cur.execute(sql)
        self.db_con.commit()
        # db.close()

    def insert_swipe_start_record(self):
        cur = self.db_con.cursor()
        # Purge the slop table
        cur.execute('delete from dataload.t_keyswipes_slop')
        self.db_con.commit()
        # Add the starting records
        cur.execute('insert into dataload.t_keyswipes_slop (record_id, fob_id, status, door, swipe_timestamp, \
                    door_controller_ip) with max_recs as \
                    (select max(swipe_timestamp ) as swipe, door_controller_ip \
                    from door_controller.t_keyswipes tks \
                    group by door_controller_ip ) \
                    select tks.record_id, tks.fob_id, tks.status, tks.door, tks.swipe_timestamp, \
                    tks.door_controller_ip from door_controller.t_keyswipes tks \
                    inner join max_recs mr on mr.swipe = tks.swipe_timestamp')
        self.db_con.commit()

    def insert_access_list_start_record(self):
        cur = self.db_con.cursor()
        # Purge the slop table
        cur.execute('delete from dataload.access_list_slop')
        self.db_con.commit()
        # Add the starting records
        cur.execute('INSERT INTO dataload.access_list_from_controller_slop (record_id, fob_id, door_controller,'
                    ' status, door_id, controller_ip) '
                 'select max(record_id), fob_id, door_controller, status, door_id, controller_ip'
                 'group by fob_id, door_controller, status, door_id, controller_ip')
        self.db_con.commit()

    def add_new_swipess(self):
        cur = self.db_con.cursor()
        # Purge the slop table
        sql = "insert into door_controller.t_keyswipes (record_id, fob_id , status, swipe_timestamp, "
        sql += "door,door_controller_ip) "
        sql += "select distinct record_id, fob_id , status, swipe_timestamp, door,door_controller_ip "
        sql += "from dataload.t_keyswipes_slop tks "
        sql += "where concat(record_id, '-',substr(door_controller_ip, 18,3)) "
        sql += "not in (select distinct concat(record_id, '-',substr(door_controller_ip, 18,3)) "
        sql += "from door_controller.t_keyswipes )"
        print(sql)
        cur.execute(sql)
        self.db_con.commit()

    def get_fob_records(self):
        cur = self.db_con.cursor()
        cur.execute('select distinct controller_record_id '
                    'from door_controller.system_fobs '
                    'where date(record_time) = '
                    '(select max(date(record_time)) from door_controller.system_fobs) '
                    'order by controller_record_id asc;')
        rows = cur.fetchall()
        return rows

    def move_fob_records(self):
        cur = self.db_con.cursor()
        # Purge the slop table for the records by controller CIDR
        cur.execute(f"insert into door_controller.system_fobs (controller_record_id, record_time, fob_id, controller_ip) "
                    f"select record_id, record_time, fs2.fob_id , controller_ip "
                    f"from dataload.fobs_slop fs2")
        self.db_con.commit()
        cur.execute(f"delete from dataload.fobs_slop")
        self.db_con.commit()
        return

    def purge_fob_records(self, cidr):
        cur = self.db_con.cursor()
        # Purge the slop table for the records by controller CIDR
        cur.execute(f"delete from dataload.fobs_slop where controller_ip={cidr}")
        self.db_con.commit()
        return

    def write_db(self, data, sql_template):
        # db = sqlite3.connect(self.db_path)
        # Add records tp SQLite database
        cur = self.db_con.cursor()
        [cur.execute(self.generate_query_string(sql_template, token)) for token in data]
        self.db_con.commit()
        # Close the database
        return

    def generate_query_string(self, sql, token):
        # Convert list to a string of comma seperated values
        the_string = ','.join(token)
        the_query = f"""{sql}({the_string})"""
        print(the_query)
        return the_query

    def get_record_id(self, url, fob_id):
        cidr = url[7:] + '/32'
        cidr = "'{}'".format(cidr)
        cur = self.db_con.cursor()
        cur.execute(f"select controller_record_id "
                    f"from door_controller.access_list_from_controller alc "
                    f"where alc.fob_id = {fob_id} "
                    f"and date(record_time) = max(date(record_time) "
                    f"and controller_ip = {cidr}")
        rows = cur.fetchall()
        return rows

    def move_acl_records(self):
        cur = self.db_con.cursor()
        # Purge the slop table for the records by controller CIDR
        cur.execute(f"insert into door_controller.access_list_from_controller (record_id, fob_id, status, "
                    f"door_id, controller_ip, record_time) "
                    f"select record_id, fs2.fob_id, status, door_id, controller_ip, record_time "
                    f"from dataload.access_list_from_controller_slop fs2")
        self.db_con.commit()
        cur.execute(f"delete from dataload.access_list_from_controller_slop")
        self.db_con.commit()
        return

    def purge_acl_records(self):
        cur = self.db_con.cursor()
        # Purge the slop table for the records by controller CIDR
        cur.execute(f"delete from dataload.access_list_from_controller_slop")
        self.db_con.commit()
        return
