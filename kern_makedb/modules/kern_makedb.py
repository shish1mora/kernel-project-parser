import os
import re
import tomllib
import urllib3
import psycopg2
import sqlparse
from multiprocessing import cpu_count
from concurrent.futures import ThreadPoolExecutor
from dotenv import dotenv_values
from psycopg2 import sql, OperationalError
from helper_func import exec_bash

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

class KernelToDb:
    def __init__(self):
        self.script_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        self.__credentials = dotenv_values(f"{self.script_path}/.env")
        self.options = self.__get_options()
        self.db_connection = self.__connect_pgdb()
        self.cursor = self.db_connection.cursor()
        self.missed_hashes = set()
        self.fixes_re = re.compile(r"^Fixes:\s([a-z0-9]+)", re.MULTILINE)
        self.msg_commit_re = re.compile(r"(?=^.*(?:\b[Uu]pstream.*[Cc]ommit\b|\b[Cc]ommit.*[Uu]pstream\b).*$)"
                                   r".*\b([a-f0-9]{7,40})\b.*", re.MULTILINE)

    def __del__(self):
        self.db_connection.close()
        self.cursor.close()

    def __connect_pgdb(self):
        try:
            conn = psycopg2.connect(dbname=self.__credentials['PGDB_NAME'],
                                    user=self.__credentials['PGDB_USER'],
                                    password=self.__credentials['PGDB_PASSWORD'],
                                    port=self.__credentials['PGDB_PORT'],
                                    host=self.__credentials['PGDB_HOST'])
            conn.set_session(autocommit=True)
            return conn
        except OperationalError as err:
            print(f"Connection can't be established: {err}")
            exit(1)

    def __get_options(self):
        """
        Опции лежат в файле options.toml в папке со скриптом
        :return:
        """
        try:
            with open(os.path.join(self.script_path, "options.toml"), "rb") as f:
                return tomllib.load(f)
        except IOError:
            print("Error opening options.toml file")
            raise IOError

    def r_tables_exist(self) -> bool:
        result = True
        tables = ['KERNEL_MAIN', 'KERNEL_FIXES']

        for table_name in tables:
            self.cursor.execute(
                sql.SQL("""
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_catalog = %s
                        AND table_schema = 'public'
                        AND table_name = %s
                    );
                """), (self.__credentials['PGDB_NAME'], table_name)
            )

            cursor_resp = self.cursor.fetchone()
            result &= cursor_resp[0] if cursor_resp is not None else False
        return result

    def make_tables(self):
        with open(os.path.join(self.script_path, "sql/kernel-tables.sql"), "r") as f:
            self.cursor.execute(f.read())
        return self.r_tables_exist()

    @staticmethod
    def kern_query(kernel_data: dict) -> str:
        filtered_kernel_data = {k: v for k, v in kernel_data.items() if v}
        ref_values = f"""{", ".join(map(lambda x: f"{x}" if isinstance(x, int) else f"'{x}'" , [item for item in filtered_kernel_data.values()]))}"""
        ref_excluded_string = f"""{", ".join([f"{item} = EXCLUDED.{item}" for item in filtered_kernel_data.keys() if item != 'kern_hash'])}"""
        insert_query = f"""
            INSERT INTO public."KERNEL_MAIN" ({", ".join(filtered_kernel_data.keys())})
            VALUES ({ref_values})
            ON CONFLICT (kern_hash)
            DO UPDATE SET
                {ref_excluded_string};
            """

        return insert_query

    def process_hash(self, hash_str):
        git_message_str = f"git -C {self.options['KERNEL-PATH']['linux-ml']} log --format=%B -n 1 {hash_str}"
        git_describe_hash_str = f"git -C {self.options['KERNEL-PATH']['linux-ml']} describe --contains {hash_str}"
        describe_resp = exec_bash(git_describe_hash_str)
        if not describe_resp:
            print(f"{hash_str} missing version")
            self.missed_hashes.add(hash_str)
            return
        message_resp = exec_bash(git_message_str)
        if not message_resp:
            print(f"{hash_str} returns empty message")
            self.missed_hashes.add(hash_str)
            return

        kern_ver = describe_resp.strip()
        fixes_hashes = self.fixes_re.findall(message_resp) if message_resp else []
        fixes_hashes = [exec_bash(f"git -C {self.options['KERNEL-PATH']['linux-ml']} rev-parse {fix_hash}") for fix_hash in fixes_hashes]

        upstream_hash = self.msg_commit_re.findall(message_resp) if message_resp else None

        result = {
            'kern_hash': hash_str,
            'kern_ver': kern_ver,
            'message': message_resp.replace("'", "''"),
            'upstream_hash': upstream_hash[0].strip() if upstream_hash else None,
        }
        prepared_query = self.kern_query(result)
        try:
            self.cursor.execute(prepared_query)
        except Exception as e:
            print(f"Error processing hash {hash_str}: {e}")
            print(sqlparse.format(prepared_query, reindent=True, keyword_case='upper'))
            exit(1)

        for fix_hash in fixes_hashes:
            if fix_hash is not None and fix_hash.strip() != '':
                fix_query = f"""
                    INSERT INTO public."KERNEL_FIXES" (kern_hash, fixes_hash)
                    VALUES ('{hash_str}', '{fix_hash.strip()}')
                    ON CONFLICT (kern_hash, fixes_hash) DO NOTHING;
                """
                try:
                    self.cursor.execute(fix_query)
                except Exception as e:
                    print(f"Error inserting fix hash {fix_hash} for {hash_str}: {e}")
                    print(sqlparse.format(fix_query, reindent=True, keyword_case='upper'))
                    exit(1)

    def create_db(self):
        print("Getting hashlist")
        all_hashes_str = f"git -C {self.options['KERNEL-PATH']['linux-ml']} rev-list --all"
        result = exec_bash(all_hashes_str)
        if not result:
            exit(1)

        result = map(str.strip, result.split())
        print("Creating key value database")
        with ThreadPoolExecutor(max_workers=cpu_count()) as executor:
            executor.map(self.process_hash, result)

        print(len(self.missed_hashes))
        with open("missed_hashes.log", "w") as f:
            f.writelines(self.missed_hashes)

if __name__ == "__main__":
    kernel_to_db = KernelToDb()
    if not kernel_to_db.r_tables_exist():
        kernel_to_db.make_tables()
    kernel_to_db.create_db()