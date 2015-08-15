import sqlalchemy
from sqlalchemy.inspection import inspect
from sqlalchemy.ext.automap import automap_base

def get_database(db_type, username, password, server):
    if db_type != ('postgres' or 'mysql'):
        raise ValueError
    if db_type == DB_TYPE.postgres:
        return PostgresDatabase(username, password, server)
    elif db_type == DB_TYPE.mysql:
        return MysqlDatabase(username, password, server)

class Database:
    _engine = None
    _username = None
    _password = None
    _hostname = None
    _protocol = None
    _driver = None
    _database = None
    _session_factory = None
    _base = None

    def __init__(self, username, password, hostname):
        self._username = username
        self._password = password
        self._hostname = hostname

    def _create_db_string(self):
        """Helper function for creating and formatting a remote server/db string. Will have to be expanded to support MySQL."""
        return "{}+{}://{}:{}@{}/{}".format(self._protocol,self._driver, self._username, self._password,self._hostname,self._database)

    def execute(self, query):
        "This function returns the results of a query"
        return self._engine.execute(query)

    def setup(self):
        if self._engine:
            RuntimeError("Only call setup once!")
        self._engine = sqlalchemy.create_engine(self._create_db_string())
        self._connection = self._engine.connect()
        self._base = automap_base()
        self._session_factory = sqlalchemy.orm.sessionmaker(bind=self._engine)
        self._base.prepare(self._engine, reflect = True)

    def list_databases(self):
        "This function returns a list of databases on the host"
        raise Exception('Only use subclass of Database')


    def database_connect(self, db_name):
        "This function handles selecting a database"
        self._engine.dispose()
        self._engine = None
        self._database = db_name
        self.setup()
        # raise Exception('Only use subclass of Database')

    def list_table_names(self):
        return self._engine.table_names()

    def list_column_names(self, table_name):
        "Returns the column names in a table"
        table_object = self._base.classes[table_name]
        return [c.name for c in table_object.__table__.columns]

    def list_rows(self, table_name):
        "Returns the rows in a table"
        # automap REQUIRES a primary key to be in the table
        session = self._session_factory()
        table_object = self._base.classes[table_name]
        return [row.__dict__ for row in session.query(table_object)]


    def update_row(self, table_name, row):
        col_names = self.list_column_names(table_name)
        table_object = self._base.classes[table_name]
        prim_key = inspect(table_object).primary_key[0].name
        row_dict = {key: row[key] for key in col_names}
        stmt = table_object.__table__.update().where(table_object.__table__.c[prim_key] == row[prim_key]).values(row_dict)
        self._connection.execute(stmt)

    def delete_row(self, table_name, row):
        col_names = self.list_column_names(table_name)
        table_object = self._base.classes[table_name]
        prim_key = inspect(table_object).primary_key[0].name
        row_dict = {key: row[key] for key in col_names}
        stmt = table_object.__table__.delete().where(table_object.__table__.c[prim_key] == row[prim_key])
        self._connection.execute(stmt)

    def add_row(self, table_name, row):
        col_names = self.list_column_names(table_name)
        table_object = self._base.classes[table_name]
        prim_key = inspect(table_object).primary_key[0].name
        row_dict = {key: row[key] for key in col_names}
        stmt = table_object.__table__.insert().values(row_dict)
        self._connection.execute(stmt)

class PostgresDatabase(Database):
    _protocol = "postgresql"
    _driver = "psycopg2"
    _database = "postgres"


    def list_databases(self):
        result = self._engine.execute("SELECT datname AS name FROM pg_database WHERE datistemplate = false")
        name_rows = result.fetchall()
        return [row['name'] for row in name_rows]

    def delete_database(self, db_name):
        self._connection.connection.set_isolation_level(0)
        self._connection.execute('DROP DATABASE {}'.format(db_name))
        self._connection.connection.set_isolation_level(1)

    def delete_table(self, table_name):
        self._connection.connection.set_isolation_level(0)
        self._connection.execute('DROP TABLE {}'.format(table_name))
        self._connection.connection.set_isolation_level(1)

    def create_database(self, db_name):
        self._connection.connection.set_isolation_level(0)
        self._connection.execute('CREATE DATABASE {}'.format(db_name))
        self._connection.connection.set_isolation_level(1)

    def create_table(self, table_name):
        self._connection.connection.set_isolation_level(0)
        self._connection.execute('CREATE TABLE {}'.format(table_name))
        self._connection.connection.set_isolation_level(1)
    # def database_connect(self, db_name):
    #     # Postgres requires you to reconnect
    #     self._engine.dispose()
    #     self._engine = None
    #     self._database = db_name
    #     self.setup()

class MySQLDatabase(Database):
    _protocol = "mysql"
    _driver = "mysqldb"
    _database = "mysql"

    def list_databases(self):
        result = self._engine.execute("SHOW databases;")
        db_names = result.fetchall()
        # db_name is a list of half-empty tuples?
        return [name[0] for name in db_names]

    def delete_database(self, db_name):
        self._connection.execute('DROP DATABASE {}'.format(db_name))

    def delete_table(self, table_name):
        self._connection.execute('DROP TABLE {}'.format(table_name))

    def create_database(self, db_name):
        self._connection.execute('CREATE DATABASE {}'.format(db_name))

    def create_table(self, table_name):
        self._connection.execute('CREATE TABLE {}'.format(table_name))
    # def database_connect(self, db_name):
    #     # doing setup again is very slow
    #     # I would prefer to use the statement:
    #     # >> self._engine.execute("USE " + db_name);
    #     # >> self._database = db_name
    #     # but I do not fully understand the lifecycles of:
    #     # session_factory, session, and base.prepare()
    #



