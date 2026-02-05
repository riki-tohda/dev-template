/**
 * POL Portal メインスクリプト
 */

// 共通ユーティリティ
const POL = {
    /**
     * APIリクエストを実行する
     * @param {string} url - リクエストURL
     * @param {object} options - fetchオプション
     * @returns {Promise<object>} レスポンスJSON
     */
    async fetchAPI(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };
        const response = await fetch(url, { ...defaultOptions, ...options });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    },

    /**
     * 状態に応じたラベルを取得する
     * @param {string} status - 状態
     * @returns {string} ラベル
     */
    getStatusLabel(status) {
        const labels = {
            'running': '実行中',
            'stopped': '停止',
            'error': 'エラー',
            'unknown': '不明',
            'not_installed': '未インストール'
        };
        return labels[status] || status;
    },

    /**
     * プログレスバーを更新する
     * @param {HTMLElement} element - progress要素
     * @param {number} value - 値（0-100）
     * @param {number} warningThreshold - 警告閾値
     */
    updateProgress(element, value, warningThreshold = 80) {
        element.value = value;
        if (value >= warningThreshold) {
            element.classList.add('warning');
        } else {
            element.classList.remove('warning');
        }
    },

    /**
     * 日時をフォーマットする
     * @param {string} isoString - ISO形式の日時文字列
     * @returns {string} フォーマット済み文字列
     */
    formatDateTime(isoString) {
        const date = new Date(isoString);
        return date.toLocaleString('ja-JP');
    }
};

// グローバルに公開
window.POL = POL;
