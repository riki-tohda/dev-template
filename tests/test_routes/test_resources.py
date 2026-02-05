"""リソースモニタルートのテスト"""

import json


class TestResourcesPage:
    """リソース画面のテスト"""

    def test_requires_login(self, client):
        """未ログイン状態でリダイレクトされる"""
        response = client.get("/resources/", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_page_display(self, admin_client):
        """リソースページが表示される"""
        response = admin_client.get("/resources/")
        assert response.status_code == 200
        assert "リソース" in response.data.decode("utf-8")

    def test_page_accessible_by_user(self, user_client):
        """一般ユーザーもアクセスできる"""
        response = user_client.get("/resources/")
        assert response.status_code == 200


class TestResourcesApi:
    """リソース API のテスト"""

    def test_api_requires_login(self, client):
        """未ログイン状態で API にアクセスできない"""
        response = client.get("/resources/api/status", follow_redirects=False)
        assert response.status_code == 302

    def test_api_status(self, admin_client):
        """API がリソース状態を返す"""
        response = admin_client.get("/resources/api/status")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert "cpu" in data
        assert "memory" in data
        assert "disks" in data
        assert "system" in data

    def test_api_cpu_fields(self, admin_client):
        """CPU 情報に必要なフィールドがある"""
        response = admin_client.get("/resources/api/status")
        data = json.loads(response.data)

        cpu = data["cpu"]
        assert "percent" in cpu
        assert "count" in cpu

    def test_api_memory_fields(self, admin_client):
        """メモリ情報に必要なフィールドがある"""
        response = admin_client.get("/resources/api/status")
        data = json.loads(response.data)

        memory = data["memory"]
        assert "percent" in memory
        assert "total_gb" in memory
        assert "used_gb" in memory
        assert "available_gb" in memory

    def test_api_system_fields(self, admin_client):
        """システム情報に必要なフィールドがある"""
        response = admin_client.get("/resources/api/status")
        data = json.loads(response.data)

        system = data["system"]
        assert "boot_time" in system
        assert "uptime" in system
