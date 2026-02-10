"""SQLite データベース操作モジュール"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

import bcrypt

from app.services.models import AppScript, Application, InitialUser, ScriptExecution, User


class Database:
    """SQLiteデータベースクラス"""

    def __init__(self, db_path: Path) -> None:
        """初期化。

        Args:
            db_path: データベースファイルパス
        """
        self.db_path = db_path

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """データベース接続のコンテキストマネージャー。

        Yields:
            sqlite3.Connection: データベース接続
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        """データベースを初期化する（テーブル作成）。"""
        with self.connection() as conn:
            cursor = conn.cursor()

            # users テーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    enabled INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # settings テーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    category TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # applications テーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    github_owner TEXT NOT NULL,
                    github_repo TEXT NOT NULL,
                    service_name TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    health_check_path TEXT,
                    auto_restart INTEGER DEFAULT 0,
                    installed INTEGER DEFAULT 0,
                    installed_version TEXT,
                    installed_at DATETIME,
                    sort_order INTEGER DEFAULT 0,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    proxy_enabled INTEGER DEFAULT 1,
                    proxy_rewrite_urls INTEGER DEFAULT 1
                )
            """)

            # app_scripts テーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_scripts (
                    id TEXT NOT NULL,
                    app_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    script_path TEXT NOT NULL,
                    mode TEXT NOT NULL DEFAULT 'sync',
                    timeout INTEGER NOT NULL DEFAULT 60,
                    sort_order INTEGER DEFAULT 0,
                    enabled INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (id, app_id)
                )
            """)

            # script_executions テーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS script_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    script_id TEXT NOT NULL,
                    app_id TEXT NOT NULL,
                    executed_by TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    exit_code INTEGER,
                    stdout TEXT,
                    stderr TEXT,
                    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    finished_at DATETIME
                )
            """)

            # 既存テーブルへのカラム追加（マイグレーション）
            self._migrate_applications_table(cursor)

    def is_initialized(self) -> bool:
        """データベースが初期化済みかどうかを確認する。

        Returns:
            初期化済みならTrue
        """
        if not self.db_path.exists():
            return False

        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='table' AND name IN ("
                "'users', 'settings', 'applications', "
                "'app_scripts', 'script_executions')"
            )
            count = cursor.fetchone()[0]
            return count >= 3

    def has_users(self) -> bool:
        """ユーザーが存在するかどうかを確認する。

        Returns:
            ユーザーが存在すればTrue
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            return count > 0

    # ユーザー操作

    def create_user(self, user: InitialUser) -> int:
        """ユーザーを作成する。

        Args:
            user: 初期ユーザー情報

        Returns:
            作成されたユーザーのID
        """
        password_hash = bcrypt.hashpw(
            user.password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, role)
                VALUES (?, ?, ?)
                """,
                (user.username, password_hash, user.role),
            )
            return cursor.lastrowid or 0

    def get_user_by_username(self, username: str) -> User | None:
        """ユーザー名でユーザーを取得する。

        Args:
            username: ユーザー名

        Returns:
            ユーザー情報。見つからない場合はNone
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()

            if row is None:
                return None

            return self._row_to_user(row)

    def get_user_by_id(self, user_id: int) -> User | None:
        """IDでユーザーを取得する。

        Args:
            user_id: ユーザーID

        Returns:
            ユーザー情報。見つからない場合はNone
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            return self._row_to_user(row)

    def update_user(self, user: User) -> None:
        """ユーザー情報を更新する。

        Args:
            user: ユーザー情報
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users
                SET username = ?, password_hash = ?, role = ?, enabled = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (user.username, user.password_hash, user.role, user.enabled, user.id),
            )

    def get_all_users(self) -> list[User]:
        """全ユーザーを取得する。

        Returns:
            ユーザーリスト
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users ORDER BY id")
            rows = cursor.fetchall()
            return [self._row_to_user(row) for row in rows]

    def _row_to_user(self, row: sqlite3.Row) -> User:
        """SQLite行をUserオブジェクトに変換する。"""
        return User(
            id=row["id"],
            username=row["username"],
            password_hash=row["password_hash"],
            role=row["role"],
            enabled=bool(row["enabled"]),
            created_at=self._parse_datetime(row["created_at"]),
            updated_at=self._parse_datetime(row["updated_at"]),
        )

    # 設定操作

    def set_setting(self, key: str, value: Any, category: str) -> None:
        """設定を保存する。

        Args:
            key: 設定キー
            value: 設定値
            category: カテゴリ
        """
        json_value = json.dumps(value, ensure_ascii=False)

        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO settings (key, value, category, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, json_value, category),
            )

    def get_setting(self, key: str, default: Any = None) -> Any:
        """設定を取得する。

        Args:
            key: 設定キー
            default: デフォルト値

        Returns:
            設定値
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()

            if row is None:
                return default

            return json.loads(row["value"])

    def get_all_settings(self) -> dict[str, Any]:
        """全設定を取得する。

        Returns:
            設定の辞書
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings")
            rows = cursor.fetchall()
            return {row["key"]: json.loads(row["value"]) for row in rows}

    def get_settings_by_category(self, category: str) -> dict[str, Any]:
        """カテゴリ別に設定を取得する。

        Args:
            category: カテゴリ

        Returns:
            設定の辞書
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT key, value FROM settings WHERE category = ?", (category,)
            )
            rows = cursor.fetchall()
            return {row["key"]: json.loads(row["value"]) for row in rows}

    # アプリケーション操作

    def create_application(self, app: Application) -> None:
        """アプリケーションを作成する。

        Args:
            app: アプリケーション情報
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO applications (
                    id, name, description, github_owner, github_repo,
                    service_name, port, health_check_path, auto_restart,
                    installed, installed_version, installed_at, sort_order,
                    proxy_enabled, proxy_rewrite_urls
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    app.id,
                    app.name,
                    app.description,
                    app.github_owner,
                    app.github_repo,
                    app.service_name,
                    app.port,
                    app.health_check_path,
                    1 if app.auto_restart else 0,
                    1 if app.installed else 0,
                    app.installed_version,
                    app.installed_at,
                    app.sort_order,
                    1 if app.proxy_enabled else 0,
                    1 if app.proxy_rewrite_urls else 0,
                ),
            )

    def get_application(self, app_id: str) -> Application | None:
        """アプリケーションを取得する。

        Args:
            app_id: アプリケーションID

        Returns:
            アプリケーション情報。見つからない場合はNone
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM applications WHERE id = ?", (app_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            return self._row_to_application(row)

    def get_all_applications(self) -> list[Application]:
        """全アプリケーションを取得する。

        Returns:
            アプリケーションリスト
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM applications ORDER BY sort_order, id")
            rows = cursor.fetchall()
            return [self._row_to_application(row) for row in rows]

    def update_application(self, app: Application) -> None:
        """アプリケーション情報を更新する。

        Args:
            app: アプリケーション情報
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE applications
                SET name = ?, description = ?, github_owner = ?, github_repo = ?,
                    service_name = ?, port = ?, health_check_path = ?,
                    auto_restart = ?, installed = ?, installed_version = ?,
                    installed_at = ?, sort_order = ?, proxy_enabled = ?,
                    proxy_rewrite_urls = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    app.name,
                    app.description,
                    app.github_owner,
                    app.github_repo,
                    app.service_name,
                    app.port,
                    app.health_check_path,
                    1 if app.auto_restart else 0,
                    1 if app.installed else 0,
                    app.installed_version,
                    app.installed_at,
                    app.sort_order,
                    1 if app.proxy_enabled else 0,
                    1 if app.proxy_rewrite_urls else 0,
                    app.id,
                ),
            )

    def _row_to_application(self, row: sqlite3.Row) -> Application:
        """SQLite行をApplicationオブジェクトに変換する。"""
        # 新しいカラムはマイグレーション前は存在しない可能性があるため、
        # キーの存在確認を行う
        row_keys = row.keys()

        return Application(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            github_owner=row["github_owner"],
            github_repo=row["github_repo"],
            service_name=row["service_name"],
            port=row["port"],
            health_check_path=row["health_check_path"],
            auto_restart=bool(row["auto_restart"]),
            installed=bool(row["installed"]),
            installed_version=row["installed_version"],
            installed_at=self._parse_datetime(row["installed_at"]),
            sort_order=row["sort_order"],
            updated_at=self._parse_datetime(row["updated_at"]),
            proxy_enabled=bool(row["proxy_enabled"])
            if "proxy_enabled" in row_keys
            else True,
            proxy_rewrite_urls=bool(row["proxy_rewrite_urls"])
            if "proxy_rewrite_urls" in row_keys
            else True,
        )

    def _parse_datetime(self, value: str | None) -> datetime | None:
        """文字列をdatetimeに変換する。"""
        if value is None:
            return None
        try:
            return datetime.fromisoformat(value.replace(" ", "T"))
        except (ValueError, AttributeError):
            return None

    # スクリプト操作

    def create_app_script(self, script: AppScript) -> None:
        """アプリスクリプトを作成または更新する。

        Args:
            script: スクリプト情報
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO app_scripts (
                    id, app_id, name, description, script_path,
                    mode, timeout, sort_order, enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id, app_id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    script_path = excluded.script_path,
                    mode = excluded.mode,
                    timeout = excluded.timeout,
                    sort_order = excluded.sort_order,
                    enabled = excluded.enabled,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    script.id,
                    script.app_id,
                    script.name,
                    script.description,
                    script.script_path,
                    script.mode,
                    script.timeout,
                    script.sort_order,
                    1 if script.enabled else 0,
                ),
            )

    def get_app_scripts(self, app_id: str) -> list[AppScript]:
        """アプリのスクリプト一覧を取得する。

        Args:
            app_id: アプリケーションID

        Returns:
            スクリプトリスト
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM app_scripts WHERE app_id = ? ORDER BY sort_order, id",
                (app_id,),
            )
            rows = cursor.fetchall()
            return [self._row_to_app_script(row) for row in rows]

    def get_app_script(self, app_id: str, script_id: str) -> AppScript | None:
        """特定のアプリスクリプトを取得する。

        Args:
            app_id: アプリケーションID
            script_id: スクリプトID

        Returns:
            スクリプト情報。見つからない場合はNone
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM app_scripts WHERE app_id = ? AND id = ?",
                (app_id, script_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_app_script(row)

    def update_app_script(self, script: AppScript) -> None:
        """アプリスクリプトを更新する。

        Args:
            script: スクリプト情報
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE app_scripts
                SET name = ?, description = ?, script_path = ?,
                    mode = ?, timeout = ?, sort_order = ?, enabled = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND app_id = ?
                """,
                (
                    script.name,
                    script.description,
                    script.script_path,
                    script.mode,
                    script.timeout,
                    script.sort_order,
                    1 if script.enabled else 0,
                    script.id,
                    script.app_id,
                ),
            )

    def delete_app_script(self, app_id: str, script_id: str) -> None:
        """アプリスクリプトを削除する。

        Args:
            app_id: アプリケーションID
            script_id: スクリプトID
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM app_scripts WHERE app_id = ? AND id = ?",
                (app_id, script_id),
            )

    def _row_to_app_script(self, row: sqlite3.Row) -> AppScript:
        """SQLite行をAppScriptオブジェクトに変換する。"""
        return AppScript(
            id=row["id"],
            app_id=row["app_id"],
            name=row["name"],
            description=row["description"],
            script_path=row["script_path"],
            mode=row["mode"],
            timeout=row["timeout"],
            sort_order=row["sort_order"],
            enabled=bool(row["enabled"]),
        )

    # スクリプト実行履歴操作

    def create_script_execution(self, execution: ScriptExecution) -> int:
        """スクリプト実行レコードを作成する。

        Args:
            execution: 実行情報

        Returns:
            作成されたレコードのID
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO script_executions (
                    script_id, app_id, executed_by, mode, status,
                    exit_code, stdout, stderr, started_at, finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    execution.script_id,
                    execution.app_id,
                    execution.executed_by,
                    execution.mode,
                    execution.status,
                    execution.exit_code,
                    execution.stdout,
                    execution.stderr,
                    execution.started_at
                    or datetime.now().isoformat(),
                    execution.finished_at,
                ),
            )
            return cursor.lastrowid or 0

    def update_script_execution(self, execution: ScriptExecution) -> None:
        """スクリプト実行レコードを更新する。

        Args:
            execution: 実行情報
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE script_executions
                SET status = ?, exit_code = ?, stdout = ?,
                    stderr = ?, finished_at = ?
                WHERE id = ?
                """,
                (
                    execution.status,
                    execution.exit_code,
                    execution.stdout,
                    execution.stderr,
                    execution.finished_at,
                    execution.id,
                ),
            )

    def get_script_execution(self, execution_id: int) -> ScriptExecution | None:
        """スクリプト実行レコードを取得する。

        Args:
            execution_id: 実行ID

        Returns:
            実行情報。見つからない場合はNone
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM script_executions WHERE id = ?",
                (execution_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_script_execution(row)

    def get_script_executions(
        self,
        app_id: str,
        script_id: str | None = None,
        limit: int = 20,
    ) -> list[ScriptExecution]:
        """スクリプト実行履歴を取得する。

        Args:
            app_id: アプリケーションID
            script_id: スクリプトID（Noneなら全スクリプト）
            limit: 取得件数

        Returns:
            実行履歴リスト
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            if script_id:
                cursor.execute(
                    "SELECT * FROM script_executions "
                    "WHERE app_id = ? AND script_id = ? "
                    "ORDER BY id DESC LIMIT ?",
                    (app_id, script_id, limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM script_executions "
                    "WHERE app_id = ? "
                    "ORDER BY id DESC LIMIT ?",
                    (app_id, limit),
                )
            rows = cursor.fetchall()
            return [self._row_to_script_execution(row) for row in rows]

    def _row_to_script_execution(self, row: sqlite3.Row) -> ScriptExecution:
        """SQLite行をScriptExecutionオブジェクトに変換する。"""
        return ScriptExecution(
            id=row["id"],
            script_id=row["script_id"],
            app_id=row["app_id"],
            executed_by=row["executed_by"],
            mode=row["mode"],
            status=row["status"],
            exit_code=row["exit_code"],
            stdout=row["stdout"],
            stderr=row["stderr"],
            started_at=self._parse_datetime(row["started_at"]),
            finished_at=self._parse_datetime(row["finished_at"]),
        )

    def _migrate_applications_table(self, cursor: sqlite3.Cursor) -> None:
        """applicationsテーブルのマイグレーションを行う。"""
        # 既存カラムを取得
        cursor.execute("PRAGMA table_info(applications)")
        columns = {row[1] for row in cursor.fetchall()}

        # proxy_enabled カラムがなければ追加
        if "proxy_enabled" not in columns:
            cursor.execute(
                "ALTER TABLE applications ADD COLUMN proxy_enabled INTEGER DEFAULT 1"
            )

        # proxy_rewrite_urls カラムがなければ追加
        if "proxy_rewrite_urls" not in columns:
            cursor.execute(
                "ALTER TABLE applications ADD COLUMN proxy_rewrite_urls INTEGER DEFAULT 1"
            )
