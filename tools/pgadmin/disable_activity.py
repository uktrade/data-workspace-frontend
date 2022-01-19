import time
import sqlite3

# Quite a hacky way to stop the activity graphs from being shown by default.
# They are suspected to cause a lot of requests from the browser, through the
# proxy, and to Fargate's API requesting the state of the task, which cause
# throttling-related exceptions
#
# There doesn't seem to be a good way to hook into the preferences stored in
# the sqlite db: initially the file doesn't exist, then it's created without
# the preference rows, and only then do rows for the preferences get created
# once the user starts loading the front end
while True:
    try:
        with sqlite3.connect("/var/lib/pgadmin/pgadmin4.db") as con:
            cur = con.cursor()
            cur.execute("""BEGIN""")
            cur.execute(
                """
                SELECT id FROM preferences WHERE name IN (
                    'show_activity',
                    'show_graphs'
                )
            """
            )
            preference_ids = [row[0] for row in cur]
            bindings_delete = ",".join(["?"] * len(preference_ids))
            cur.execute(
                f"""
                DELETE FROM user_preferences WHERE pid IN ({bindings_delete})
            """,
                preference_ids,
            )
            bindings_create = ",".join(["(1,?,'False')"] * len(preference_ids))
            cur.execute(
                f"""
                INSERT INTO user_preferences(uid, pid, value) VALUES {bindings_create}
            """,
                preference_ids,
            )
            cur.execute("""COMMIT""")
    except sqlite3.OperationalError as e:
        print(e)

    time.sleep(1)
