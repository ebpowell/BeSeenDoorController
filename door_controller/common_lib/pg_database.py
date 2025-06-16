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

    def generate_query_string(self, sql, token):
        # Convert list to a string of comma seperated values
        the_string = '","'.join(token)
        the_query = f"""{sql}("{the_string}")"""
        return the_query

    def gen_swipe_record(self, record, sql):
        str_query = F"""{sql} ({int(record[0])}, {int(record[1])}, '{record[2]}',{record[3]},'{record[4]}','{record[5]}')"""
        print (str_query)
        return str_query

    def insert_swipe_record(self, data, max_id):
        query = 'INSERT INTO dataload.t_keyswipes_slop (record_id, fob_id,  status, door, swipe_timestamp, door_controller_ip) values'
        # Add records tp SQLite database
        cur = self.db_con.cursor()
        [cur.execute(self.gen_swipe_record(record, query)) for record in data if int(record[0])>max_id]
        self.db_con.commit()

    def insert_controller_fobs_slop(self, data):
        # data.append(str(datetime.datetime.now()))
        # data.append(str(run_time))
        query = ('INSERT INTO dataload.fobs_slop (record_id, fob_id, controller_ip, '
                 'record_time) values')
        cur = self.db_con.cursor()
        query = F"""{query} {data[0], data[1], data[2], data[3]}"""
        cur.execute(query)
        self.db_con.commit()

    def purge_controller_fobs_slop(self):
        cur = self.db_con.cursor()
        # Purge the slop table
        cur.execute('delete from dataload.fobs_slop')
        self.db_con.commit()

    def purge_acl_slop(self):
        cur = self.db_con.cursor()
        # Purge the slop table
        cur.execute('delete from dataload.access_list_from_controller_slop')
        self.db_con.commit()

    def insert_access_list_record(self, data):
        # data.append(str(datetime.datetime.now()))
        # data.append(str(run_time))
        query = ('INSERT INTO dataload.access_list_from_controller_slop (record_id, fob_id, status, '
                 'door_id, controller_ip, data_date) values')
        cur = self.db_con.cursor()
        query = F"""{query} {data[0], data[1], data[3], data[2], data[4], data[5]}"""
        cur.execute(query)
        self.db_con.commit()

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
        sql = "insert into door_controller.t_keyswipes (record_id, fob_id , status, swipe_timestamp, "
        sql += "door,door_controller_ip) "
        sql += "select distinct record_id, fob_id , status, swipe_timestamp, door,door_controller_ip "
        sql += "from dataload.t_keyswipes_slop tks "
        sql += "where concat(record_id, '-',substr(door_controller_ip, 18,3)) "
        sql += "not in (select distinct concat(record_id, '-',substr(door_controller_ip, 18,3)) "
        sql += "from door_controller.t_keyswipes )"
        # print(sql)
        cur.execute(sql)
        self.db_con.commit()

    # TO DO - Flesh out query
    def add_new_fobs(self):
        cur = self.db_con.cursor()
        sql = "insert into key_fobs.fobs (record_id, fob_id ,controller_ip, record_time) "
        sql += "select distinct record_id, fob_id, controller_ip, record_time"
        sql += "from dataload.fobs_slop fs "
        sql += "where concat(record_id::text, '-',substr(door_controller_ip, 18,3)) "
        sql += "not in (select distinct concat(record_id::text, '-',substr(door_controller_ip, 18,3)) "
        sql += "from door_controller.fobs)"
        # print(sql)
        cur.execute(sql)
        self.db_con.commit()

    def get_fob_records(self, url):
        cur = self.db_con.cursor()
        cur.execute(F"""select distinct record_id from dataload.fobs_slop where controller_ip ='{url[7:]}' order by record_id asc""")
        rows = cur.fetchall()
        return rows

    def get_max_fob_id(self, url):
        cur = self.db_con.cursor()
        sql = F"""select max(record_id) 
            from dataload.fobs_slop
            where controller_ip = '{url[7:]}/32'::cidr"""
            # WHERE record_time >= now()::date
            # AND record_time < (now()::date + INTERVAL '1 day')"""

        # print(sql)
        cur.execute(sql)
        rows = cur.fetchone()
        if rows[0]:
            return rows[0]
        else:
            return 1
