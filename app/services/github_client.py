"""GitHub API クライアント

GitHub Releases からアプリケーションをダウンロードするための機能を提供する。
"""

import json
import shutil
import socket
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.services.log_manager import get_logger

logger = get_logger("app")


@dataclass
class Release:
    """GitHub Release 情報"""

    tag_name: str
    name: str
    body: str
    published_at: datetime
    assets: list["ReleaseAsset"]


@dataclass
class ReleaseAsset:
    """Release Asset 情報"""

    name: str
    size: int
    download_url: str
    content_type: str


class GitHubClientError(Exception):
    """GitHub API エラー"""

    pass


class GitHubClient:
    """GitHub API クライアント"""

    API_BASE_URL = "https://api.github.com"

    def __init__(self, token: str):
        """初期化

        Args:
            token: GitHub Personal Access Token
        """
        self.token = token

    def _request(self, endpoint: str) -> dict:
        """GitHub API にリクエストを送信する。

        Args:
            endpoint: APIエンドポイント（例: /repos/owner/repo/releases/latest）

        Returns:
            レスポンスのJSON

        Raises:
            GitHubClientError: APIリクエストに失敗した場合
        """
        url = f"{self.API_BASE_URL}{endpoint}"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        request = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise GitHubClientError(f"リソースが見つかりません: {endpoint}")
            elif e.code == 401:
                raise GitHubClientError("認証に失敗しました。GitHub Tokenを確認してください。")
            elif e.code == 403:
                raise GitHubClientError("アクセスが拒否されました。権限を確認してください。")
            else:
                raise GitHubClientError(f"GitHub API エラー: {e.code} {e.reason}")
        except urllib.error.URLError as e:
            raise GitHubClientError(f"ネットワークエラー: {e.reason}")
        except (TimeoutError, socket.timeout):
            raise GitHubClientError("リクエストがタイムアウトしました")

    def get_latest_release(self, owner: str, repo: str) -> Release | None:
        """最新のリリース情報を取得する。

        Args:
            owner: リポジトリオーナー
            repo: リポジトリ名

        Returns:
            Release 情報。リリースがない場合は None。
        """
        try:
            data = self._request(f"/repos/{owner}/{repo}/releases/latest")
            return self._parse_release(data)
        except GitHubClientError as e:
            if "見つかりません" in str(e):
                return None
            raise

    def get_releases(self, owner: str, repo: str, per_page: int = 10) -> list[Release]:
        """リリース一覧を取得する。

        Args:
            owner: リポジトリオーナー
            repo: リポジトリ名
            per_page: 取得件数

        Returns:
            Release のリスト
        """
        data = self._request(f"/repos/{owner}/{repo}/releases?per_page={per_page}")
        return [self._parse_release(release) for release in data]

    def _parse_release(self, data: dict) -> Release:
        """リリースデータをパースする。"""
        assets = [
            ReleaseAsset(
                name=asset["name"],
                size=asset["size"],
                download_url=asset["browser_download_url"],
                content_type=asset["content_type"],
            )
            for asset in data.get("assets", [])
        ]

        published_at = datetime.fromisoformat(
            data["published_at"].replace("Z", "+00:00")
        )

        return Release(
            tag_name=data["tag_name"],
            name=data.get("name") or data["tag_name"],
            body=data.get("body") or "",
            published_at=published_at,
            assets=assets,
        )

    def download_asset(self, asset: ReleaseAsset, dest_path: Path) -> None:
        """アセットをダウンロードする。

        Args:
            asset: ダウンロードするアセット
            dest_path: 保存先パス

        Raises:
            GitHubClientError: ダウンロードに失敗した場合
        """
        headers = {
            "Accept": "application/octet-stream",
            "Authorization": f"Bearer {self.token}",
        }

        request = urllib.request.Request(asset.download_url, headers=headers)

        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                with open(dest_path, "wb") as f:
                    shutil.copyfileobj(response, f)
        except urllib.error.URLError as e:
            raise GitHubClientError(f"ダウンロードエラー: {e.reason}")
        except (TimeoutError, socket.timeout):
            raise GitHubClientError("ダウンロードがタイムアウトしました")


class AppInstaller:
    """アプリケーションインストーラー"""

    def __init__(self, github_client: GitHubClient, install_dir: Path):
        """初期化

        Args:
            github_client: GitHubクライアント
            install_dir: インストール先ベースディレクトリ
        """
        self.github_client = github_client
        self.install_dir = install_dir

    def get_app_dir(self, app_id: str) -> Path:
        """アプリのインストールディレクトリを取得する。"""
        return self.install_dir / app_id

    def check_update(
        self, owner: str, repo: str, current_version: str | None
    ) -> Release | None:
        """アップデートを確認する。

        Args:
            owner: リポジトリオーナー
            repo: リポジトリ名
            current_version: 現在のバージョン（タグ名）

        Returns:
            新しいバージョンがあれば Release、なければ None
        """
        latest = self.github_client.get_latest_release(owner, repo)

        if latest is None:
            return None

        if current_version is None:
            return latest

        if latest.tag_name != current_version:
            return latest

        return None

    def install(
        self, owner: str, repo: str, app_id: str, release: Release | None = None
    ) -> str:
        """アプリケーションをインストールする。

        Args:
            owner: リポジトリオーナー
            repo: リポジトリ名
            app_id: アプリケーションID
            release: インストールするリリース（省略時は最新）

        Returns:
            インストールしたバージョン（タグ名）

        Raises:
            GitHubClientError: インストールに失敗した場合
        """
        if release is None:
            release = self.github_client.get_latest_release(owner, repo)
            if release is None:
                raise GitHubClientError(f"リリースが見つかりません: {owner}/{repo}")

        # zipアセットを探す
        zip_asset = self._find_zip_asset(release)
        if zip_asset is None:
            raise GitHubClientError("インストール可能なアセット（zip）が見つかりません")

        app_dir = self.get_app_dir(app_id)

        # 既存のインストールをバックアップ
        backup_dir = None
        if app_dir.exists():
            backup_dir = app_dir.with_suffix(".backup")
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            shutil.move(str(app_dir), str(backup_dir))

        try:
            # ダウンロードと展開
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                zip_path = tmp_path / zip_asset.name

                logger.info(
                    "アセットをダウンロード中 asset=%s size=%d",
                    zip_asset.name,
                    zip_asset.size,
                )
                self.github_client.download_asset(zip_asset, zip_path)

                logger.info("アセットを展開中 dest=%s", app_dir)
                self._extract_zip(zip_path, app_dir)

            # バックアップを削除
            if backup_dir and backup_dir.exists():
                shutil.rmtree(backup_dir)

            logger.info(
                "インストール完了 app=%s version=%s", app_id, release.tag_name
            )
            return release.tag_name

        except Exception as e:
            # エラー時はバックアップから復元
            if backup_dir and backup_dir.exists():
                if app_dir.exists():
                    shutil.rmtree(app_dir)
                shutil.move(str(backup_dir), str(app_dir))
            raise GitHubClientError(f"インストールに失敗しました: {e}")

    def uninstall(self, app_id: str) -> None:
        """アプリケーションをアンインストールする。

        Args:
            app_id: アプリケーションID

        Raises:
            GitHubClientError: アンインストールに失敗した場合
        """
        app_dir = self.get_app_dir(app_id)

        if not app_dir.exists():
            raise GitHubClientError(f"アプリがインストールされていません: {app_id}")

        try:
            shutil.rmtree(app_dir)
            logger.info("アンインストール完了 app=%s", app_id)
        except Exception as e:
            raise GitHubClientError(f"アンインストールに失敗しました: {e}")

    def _find_zip_asset(self, release: Release) -> ReleaseAsset | None:
        """zipアセットを探す。"""
        for asset in release.assets:
            if asset.name.endswith(".zip"):
                return asset
        return None

    def _extract_zip(self, zip_path: Path, dest_dir: Path) -> None:
        """zipファイルを展開する。"""
        dest_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            # zipの構造を確認（ルートに1つのディレクトリがある場合は中身を展開）
            names = zip_ref.namelist()
            if names and all(name.startswith(names[0].split("/")[0] + "/") for name in names):
                # ルートディレクトリがある
                root_dir = names[0].split("/")[0]
                for member in zip_ref.infolist():
                    if member.filename.startswith(root_dir + "/"):
                        # ルートディレクトリを除去して展開
                        member.filename = member.filename[len(root_dir) + 1 :]
                        if member.filename:
                            zip_ref.extract(member, dest_dir)
            else:
                # そのまま展開
                zip_ref.extractall(dest_dir)
