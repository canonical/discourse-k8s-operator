import logging

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import connection

logger = logging.getLogger(__name__)


class DatabaseClient:
    """A database client to connect to the Discourse PostgreSQL database."""

    def __init__(self, relation_data: dict[str, str]):
        """Initialize the DatabaseClient with relation data.

        Args:
            relation_data (dict): A dictionary containing database relation info.
        """
        self._relation_data = relation_data
        self._conn: connection = None

    def connect(self) -> None:
        """Establish a connection to the PostgreSQL database.

        Raises:
            psycopg2.Error: If the connection to the database fails.
        """
        if self._conn is None:
            logger.debug("Connecting to database")
            try:
                self._conn = psycopg2.connect(
                    database=self._relation_data["POSTGRES_DB"],
                    user=self._relation_data["POSTGRES_USER"],
                    password=self._relation_data["POSTGRES_PASSWORD"],
                    host=self._relation_data["POSTGRES_HOST"],
                    port=self._relation_data["POSTGRES_PORT"],
                )
                self._conn.autocommit = True
            except psycopg2.Error as exc:
                logger.error(f"Failed to connect to database: {exc}")
                raise

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            logger.debug("Closing database connection")
            self._conn.close()
            self._conn = None

    def change_pgvector_ownership(self) -> None:
        """Change the ownership of the pgvector extension.

        Args:
            query (str): The SQL query to execute.

        Returns:
            list[tuple]: The results of the query.
        """
        try:
            self.connect()
            with self._conn.cursor() as cursor:
                cursor.execute(
                    sql.SQL("ALTER EXTENSION pgvector OWNER TO {owner};").format(
                        owner=sql.Identifier(self._relation_data["POSTGRES_USER"])
                    )
                )
                logger.info("Changed pgvector extension ownership successfully.")
        except psycopg2.Error as exc:
            logger.error(f"Failed to change pgvector ownership: {exc}")
            raise
        finally:
            self.close()

    def check_pgvector_installed(self) -> bool:
        try:
            self.connect()
            with self._conn.cursor() as cursor:
                cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
                result = cursor.fetchone()
                return result is not None
        except psycopg2.Error as exc:
            logger.error(f"Failed to check pgvector installation: {exc}")
            raise
        finally:
            self.close()
