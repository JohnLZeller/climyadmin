import sqlalchemy

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

    def list_databases(self):
        "This function returns a list of databases on the host"
        raise Exception('Only use subclass of Database')


    def database_connect(self, db_name):
        "This function handles selecting a database"
        raise Exception('Only use subclass of Database')

    def list_table_names(self):
        return self._engine.table_names()

class PostgresDatabase(Database):
    _protocol = "postgresql"
    _driver = "pg8000"
    _database = "postgres"


    def list_databases(self):
        result = self._engine.execute("SELECT datname AS name FROM pg_database WHERE datistemplate = false")
        name_rows = result.fetchall()
        return [row['name'] for row in name_rows]

    def database_connect(self, db_name):
        # Postgres requires you to reconnect
        self._engine.dispose()
        self._engine = None
        self._database = db_name
        self.setup()

class MySQLDatabase(Database):
    _protocol = "mysql"
    _driver = "mysqldb"
    _database = "mysql"

    def list_databases(self):
        result = self._engine.execute("SHOW databases;")
        db_names = result.fetchall()
        # db_name is a list of half-empty tuples?
        return [name[0] for name in db_names]

    def database_connect(self, db_name):
        self._engine.execute("USE " + db_name)
        self._database = db_name




