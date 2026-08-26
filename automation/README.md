# シカキン パートナー歯科医院 LP自動生成システム

## 目的
Googleスプレッドシートに医院情報を入力し、メニューから1回実行するだけで `https://shikakin.github.io/shikakin-partner-lp/<slug>/` に医院LPを生成する。

## 構成
1. Googleフォーム（任意）→ Googleスプレッドシート
2. Apps Script (`automation/Code.gs`)
3. GitHub Actions (`.github/workflows/generate-clinic-lp.yml`)
4. MASTER: `fukuoka-tdc/index.html`
5. GitHub Pagesで公開

## 初回設定
1. Googleスプレッドシートを1つ作成する。
2. 拡張機能 → Apps Script を開く。
3. `automation/Code.gs` の内容を貼り付けて保存する。
4. Apps Scriptのプロジェクト設定 → スクリプトプロパティに `GITHUB_TOKEN` を登録する。
5. トークンは `shikakin/shikakin-partner-lp` への Contents: Read and write / Actions: Read and write に限定する。
6. スプレッドシートを再読み込みし「シカキンLP → 入力シートを初期設定」を実行する。

## 日常運用
1. 「医院LP」シートに1医院1行で入力。
2. `slug` は英小文字・数字・ハイフン。例: `ginza-dental`。
3. 対象行を選択。
4. 「シカキンLP → 選択行のLPを作成」。
5. GitHub ActionsがMASTERからHTMLを生成しGitHub Pagesが公開する。

## 重要ルール
- MASTERのデザイン・固定文章を医院ごとに変更しない。
- 既存医院slugはgenerator側で保護する。
- 公開URLは `https://shikakin.github.io/shikakin-partner-lp/<slug>/` に統一する。
- 既存の旧URLは、相手先に配布済みの場合は削除しない。
- 写真は公開可能なHTTPS URLを使用する。Google Drive共有URLはそのままでは画像直リンクにならない場合があるため、将来の画像自動アップロード機能で対応する。

## 次期拡張
- Googleフォームから写真ファイルを受け取り、GitHubへ画像を自動アップロード。
- GitHub Pagesのデプロイ完了とHTTP 200を確認してからステータスを「公開済み」に変更。
- Notion「認定パートナー歯科医院 LP」へ正式URLを自動記録。
- MASTERを専用 `template/master.html` に独立させ、医院データと完全分離する。
