"""GitHub クライアントのテスト"""

import json
import socket
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.github_client import (
    AppInstaller,
    GitHubClient,
    GitHubClientError,
    Release,
    ReleaseAsset,
)


# --- テストデータ ---

RELEASE_JSON = {
    "tag_name": "v1.0.0",
    "name": "Release v1.0.0",
    "body": "Initial release",
    "published_at": "2025-01-01T00:00:00Z",
    "assets": [
        {
            "name": "app-v1.0.0.zip",
            "size": 1024,
            "browser_download_url": "https://github.com/owner/repo/releases/download/v1.0.0/app-v1.0.0.zip",
            "content_type": "application/zip",
        }
    ],
}

RELEASE_JSON_V2 = {
    "tag_name": "v2.0.0",
    "name": "Release v2.0.0",
    "body": "Major update",
    "published_at": "2025-06-01T00:00:00Z",
    "assets": [
        {
            "name": "app-v2.0.0.zip",
            "size": 2048,
            "browser_download_url": "https://github.com/owner/repo/releases/download/v2.0.0/app-v2.0.0.zip",
            "content_type": "application/zip",
        }
    ],
}


def _make_urlopen_response(data: dict | list) -> MagicMock:
    """urlopen のレスポンスモックを作成する。"""
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(data).encode("utf-8")
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


class TestGitHubClient:
    """GitHubClient のテスト"""

    def test_default_api_base_url(self):
        """デフォルトの API Base URL が設定される"""
        client = GitHubClient("test-token")
        assert client.api_base_url == "https://api.github.com"

    def test_custom_api_base_url(self):
        """カスタム API Base URL が設定される"""
        client = GitHubClient(
            "test-token", api_base_url="https://github.example.com/api/v3"
        )
        assert client.api_base_url == "https://github.example.com/api/v3"

    def test_custom_api_base_url_trailing_slash(self):
        """末尾スラッシュが除去される"""
        client = GitHubClient(
            "test-token", api_base_url="https://github.example.com/api/v3/"
        )
        assert client.api_base_url == "https://github.example.com/api/v3"

    def test_request_success(self):
        """API リクエストが成功する"""
        client = GitHubClient("test-token")
        mock_response = _make_urlopen_response(RELEASE_JSON)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client._request("/repos/owner/repo/releases/latest")

        assert result["tag_name"] == "v1.0.0"

    def test_request_404(self):
        """404 エラーが GitHubClientError になる"""
        client = GitHubClient("test-token")
        error = urllib.error.HTTPError(
            "https://api.github.com/repos/owner/repo/releases/latest",
            404,
            "Not Found",
            {},
            None,
        )

        with patch("urllib.request.urlopen", side_effect=error):
            with pytest.raises(GitHubClientError, match="見つかりません"):
                client._request("/repos/owner/repo/releases/latest")

    def test_request_401(self):
        """401 エラーが認証エラーになる"""
        client = GitHubClient("bad-token")
        error = urllib.error.HTTPError(
            "https://api.github.com/test", 401, "Unauthorized", {}, None
        )

        with patch("urllib.request.urlopen", side_effect=error):
            with pytest.raises(GitHubClientError, match="認証に失敗"):
                client._request("/test")

    def test_request_403(self):
        """403 エラーがアクセス拒否になる"""
        client = GitHubClient("test-token")
        error = urllib.error.HTTPError(
            "https://api.github.com/test", 403, "Forbidden", {}, None
        )

        with patch("urllib.request.urlopen", side_effect=error):
            with pytest.raises(GitHubClientError, match="アクセスが拒否"):
                client._request("/test")

    def test_request_other_http_error(self):
        """その他の HTTP エラー"""
        client = GitHubClient("test-token")
        error = urllib.error.HTTPError(
            "https://api.github.com/test", 500, "Internal Server Error", {}, None
        )

        with patch("urllib.request.urlopen", side_effect=error):
            with pytest.raises(GitHubClientError, match="500"):
                client._request("/test")

    def test_request_timeout(self):
        """タイムアウトが GitHubClientError になる"""
        client = GitHubClient("test-token")

        with patch("urllib.request.urlopen", side_effect=TimeoutError):
            with pytest.raises(GitHubClientError, match="タイムアウト"):
                client._request("/test")

    def test_request_socket_timeout(self):
        """socket.timeout が GitHubClientError になる（Python 3.9互換）"""
        client = GitHubClient("test-token")

        with patch("urllib.request.urlopen", side_effect=socket.timeout):
            with pytest.raises(GitHubClientError, match="タイムアウト"):
                client._request("/test")

    def test_request_network_error(self):
        """ネットワークエラーが GitHubClientError になる"""
        client = GitHubClient("test-token")
        error = urllib.error.URLError("Connection refused")

        with patch("urllib.request.urlopen", side_effect=error):
            with pytest.raises(GitHubClientError, match="ネットワークエラー"):
                client._request("/test")

    def test_get_latest_release(self):
        """最新リリースを取得できる"""
        client = GitHubClient("test-token")
        mock_response = _make_urlopen_response(RELEASE_JSON)

        with patch("urllib.request.urlopen", return_value=mock_response):
            release = client.get_latest_release("owner", "repo")

        assert release is not None
        assert release.tag_name == "v1.0.0"
        assert release.name == "Release v1.0.0"
        assert len(release.assets) == 1
        assert release.assets[0].name == "app-v1.0.0.zip"

    def test_get_latest_release_not_found(self):
        """リリースが存在しない場合 None を返す"""
        client = GitHubClient("test-token")
        error = urllib.error.HTTPError(
            "https://api.github.com/repos/owner/repo/releases/latest",
            404,
            "Not Found",
            {},
            None,
        )

        with patch("urllib.request.urlopen", side_effect=error):
            release = client.get_latest_release("owner", "repo")

        assert release is None

    def test_get_releases(self):
        """リリース一覧を取得できる"""
        client = GitHubClient("test-token")
        mock_response = _make_urlopen_response([RELEASE_JSON, RELEASE_JSON_V2])

        with patch("urllib.request.urlopen", return_value=mock_response):
            releases = client.get_releases("owner", "repo")

        assert len(releases) == 2
        assert releases[0].tag_name == "v1.0.0"
        assert releases[1].tag_name == "v2.0.0"

    def test_download_asset(self, tmp_path: Path):
        """アセットをダウンロードできる"""
        client = GitHubClient("test-token")
        asset = ReleaseAsset(
            name="test.zip",
            size=100,
            download_url="https://github.com/download/test.zip",
            content_type="application/zip",
        )
        dest = tmp_path / "test.zip"

        mock_response = MagicMock()
        mock_response.read.side_effect = [b"file content", b""]
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            with patch("shutil.copyfileobj") as mock_copy:
                client.download_asset(asset, dest)
                mock_copy.assert_called_once()

    def test_download_asset_timeout(self, tmp_path: Path):
        """ダウンロードタイムアウト"""
        client = GitHubClient("test-token")
        asset = ReleaseAsset(
            name="test.zip",
            size=100,
            download_url="https://github.com/download/test.zip",
            content_type="application/zip",
        )
        dest = tmp_path / "test.zip"

        with patch("urllib.request.urlopen", side_effect=socket.timeout):
            with pytest.raises(GitHubClientError, match="ダウンロード.*タイムアウト"):
                client.download_asset(asset, dest)

    def test_download_asset_url_error(self, tmp_path: Path):
        """ダウンロードネットワークエラー"""
        client = GitHubClient("test-token")
        asset = ReleaseAsset(
            name="test.zip",
            size=100,
            download_url="https://github.com/download/test.zip",
            content_type="application/zip",
        )
        dest = tmp_path / "test.zip"

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            with pytest.raises(GitHubClientError, match="ダウンロードエラー"):
                client.download_asset(asset, dest)


class TestAppInstaller:
    """AppInstaller のテスト"""

    def _make_release(
        self, tag: str = "v1.0.0", zip_name: str = "app-v1.0.0.zip"
    ) -> Release:
        """テスト用 Release を作成する。"""
        return Release(
            tag_name=tag,
            name=f"Release {tag}",
            body="",
            published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            assets=[
                ReleaseAsset(
                    name=zip_name,
                    size=1024,
                    download_url=f"https://github.com/download/{zip_name}",
                    content_type="application/zip",
                )
            ],
        )

    def test_get_app_dir(self, tmp_path: Path):
        """アプリディレクトリが正しく取得できる"""
        client = MagicMock()
        installer = AppInstaller(client, tmp_path)
        assert installer.get_app_dir("my-app") == tmp_path / "my-app"

    def test_check_update_new_version(self, tmp_path: Path):
        """新しいバージョンがある場合"""
        client = MagicMock()
        release = self._make_release("v2.0.0")
        client.get_latest_release.return_value = release

        installer = AppInstaller(client, tmp_path)
        result = installer.check_update("owner", "repo", "v1.0.0")

        assert result is not None
        assert result.tag_name == "v2.0.0"

    def test_check_update_same_version(self, tmp_path: Path):
        """同じバージョンの場合 None"""
        client = MagicMock()
        release = self._make_release("v1.0.0")
        client.get_latest_release.return_value = release

        installer = AppInstaller(client, tmp_path)
        result = installer.check_update("owner", "repo", "v1.0.0")

        assert result is None

    def test_check_update_no_release(self, tmp_path: Path):
        """リリースがない場合 None"""
        client = MagicMock()
        client.get_latest_release.return_value = None

        installer = AppInstaller(client, tmp_path)
        result = installer.check_update("owner", "repo", "v1.0.0")

        assert result is None

    def test_check_update_no_current_version(self, tmp_path: Path):
        """現在バージョンが None の場合はリリースを返す"""
        client = MagicMock()
        release = self._make_release("v1.0.0")
        client.get_latest_release.return_value = release

        installer = AppInstaller(client, tmp_path)
        result = installer.check_update("owner", "repo", None)

        assert result is not None
        assert result.tag_name == "v1.0.0"

    def test_install_success(self, tmp_path: Path):
        """インストールが成功する"""
        client = MagicMock()
        release = self._make_release()

        installer = AppInstaller(client, tmp_path)

        with patch.object(installer, "_extract_zip"):
            version = installer.install("owner", "repo", "test-app", release)

        assert version == "v1.0.0"
        client.download_asset.assert_called_once()

    def test_install_no_release_fetches_latest(self, tmp_path: Path):
        """リリース未指定時は最新を取得する"""
        client = MagicMock()
        release = self._make_release()
        client.get_latest_release.return_value = release

        installer = AppInstaller(client, tmp_path)

        with patch.object(installer, "_extract_zip"):
            version = installer.install("owner", "repo", "test-app")

        assert version == "v1.0.0"
        client.get_latest_release.assert_called_once_with("owner", "repo")

    def test_install_no_release_found(self, tmp_path: Path):
        """リリースが見つからない場合"""
        client = MagicMock()
        client.get_latest_release.return_value = None

        installer = AppInstaller(client, tmp_path)

        with pytest.raises(GitHubClientError, match="リリースが見つかりません"):
            installer.install("owner", "repo", "test-app")

    def test_install_no_zip_asset(self, tmp_path: Path):
        """zip アセットがない場合"""
        client = MagicMock()
        release = Release(
            tag_name="v1.0.0",
            name="Release v1.0.0",
            body="",
            published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            assets=[
                ReleaseAsset(
                    name="readme.txt",
                    size=100,
                    download_url="https://example.com/readme.txt",
                    content_type="text/plain",
                )
            ],
        )

        installer = AppInstaller(client, tmp_path)

        with pytest.raises(GitHubClientError, match="zip"):
            installer.install("owner", "repo", "test-app", release)

    def test_install_backup_and_restore_on_failure(self, tmp_path: Path):
        """インストール失敗時にバックアップから復元する"""
        client = MagicMock()
        release = self._make_release()

        # 既存のインストールディレクトリを作成
        app_dir = tmp_path / "test-app"
        app_dir.mkdir()
        (app_dir / "existing.txt").write_text("existing data")

        client.download_asset.side_effect = GitHubClientError("download failed")

        installer = AppInstaller(client, tmp_path)

        with pytest.raises(GitHubClientError, match="インストールに失敗"):
            installer.install("owner", "repo", "test-app", release)

        # バックアップから復元されている
        assert app_dir.exists()
        assert (app_dir / "existing.txt").read_text() == "existing data"

    def test_uninstall_success(self, tmp_path: Path):
        """アンインストールが成功する"""
        client = MagicMock()
        app_dir = tmp_path / "test-app"
        app_dir.mkdir()
        (app_dir / "file.txt").write_text("data")

        installer = AppInstaller(client, tmp_path)
        installer.uninstall("test-app")

        assert not app_dir.exists()

    def test_uninstall_not_installed(self, tmp_path: Path):
        """未インストールのアプリをアンインストール"""
        client = MagicMock()
        installer = AppInstaller(client, tmp_path)

        with pytest.raises(GitHubClientError, match="インストールされていません"):
            installer.uninstall("nonexistent-app")
