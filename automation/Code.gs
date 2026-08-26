// シカキン認定パートナー歯科医院 LP自動生成
// Googleスプレッドシートの Apps Script に貼り付けて使用します。

const SHIKAKIN = {
  owner: 'shikakin',
  repo: 'shikakin-partner-lp',
  workflow: 'generate-clinic-lp.yml',
  branch: 'main',
  pagesBase: 'https://shikakin.github.io/shikakin-partner-lp/'
};

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('シカキンLP')
    .addItem('選択行のLPを作成', 'generateSelectedClinicLp')
    .addItem('入力シートを初期設定', 'setupClinicSheet')
    .addToUi();
}

function setupClinicSheet() {
  const ss = SpreadsheetApp.getActive();
  let sheet = ss.getSheetByName('医院LP');
  if (!sheet) sheet = ss.insertSheet('医院LP');
  const headers = [
    'ステータス','医院名','slug','医院HP','院長名','院長役職','院長写真URL',
    'セラピスト名','セラピスト職種','セラピスト写真URL','住所','TEL','アクセス',
    '予約URL','LINE URL','医院紹介文','公開URL','作成日時'
  ];
  sheet.getRange(1,1,1,headers.length).setValues([headers]);
  sheet.setFrozenRows(1);
  sheet.autoResizeColumns(1, headers.length);
  SpreadsheetApp.getUi().alert('「医院LP」シートを作成しました。');
}

function generateSelectedClinicLp() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const row = sheet.getActiveRange().getRow();
  if (row <= 1) throw new Error('医院データの行を選択してください。');
  const headers = sheet.getRange(1,1,1,sheet.getLastColumn()).getValues()[0];
  const values = sheet.getRange(row,1,1,sheet.getLastColumn()).getValues()[0];
  const data = {};
  headers.forEach((h,i) => data[h] = values[i]);

  const slug = normalizeSlug_(data['slug']);
  if (!data['医院名']) throw new Error('医院名が未入力です。');
  if (!slug) throw new Error('slugが未入力です。例: ginza-dental');

  const payload = {
    slug: slug,
    clinicName: String(data['医院名'] || ''),
    website: String(data['医院HP'] || ''),
    doctors: [{
      name: String(data['院長名'] || ''),
      role: String(data['院長役職'] || '院長'),
      photo: String(data['院長写真URL'] || '')
    }],
    therapists: [{
      name: String(data['セラピスト名'] || ''),
      role: String(data['セラピスト職種'] || 'シカキンセラピスト'),
      photo: String(data['セラピスト写真URL'] || '')
    }],
    address: String(data['住所'] || ''),
    tel: String(data['TEL'] || ''),
    access: String(data['アクセス'] || ''),
    reservationUrl: String(data['予約URL'] || ''),
    lineUrl: String(data['LINE URL'] || ''),
    clinicIntro: String(data['医院紹介文'] || '')
  };

  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('Apps Scriptのスクリプトプロパティに GITHUB_TOKEN を登録してください。');

  const endpoint = `https://api.github.com/repos/${SHIKAKIN.owner}/${SHIKAKIN.repo}/actions/workflows/${SHIKAKIN.workflow}/dispatches`;
  const response = UrlFetchApp.fetch(endpoint, {
    method: 'post',
    contentType: 'application/json',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28'
    },
    payload: JSON.stringify({ref: SHIKAKIN.branch, inputs: {payload: JSON.stringify(payload)}}),
    muteHttpExceptions: true
  });
  if (response.getResponseCode() !== 204) {
    throw new Error(`GitHub送信エラー ${response.getResponseCode()}: ${response.getContentText()}`);
  }

  const url = SHIKAKIN.pagesBase + slug + '/';
  writeByHeader_(sheet,row,'ステータス','公開処理中');
  writeByHeader_(sheet,row,'公開URL',url);
  writeByHeader_(sheet,row,'作成日時',new Date());
  SpreadsheetApp.getUi().alert(`LP生成を開始しました。\n公開URL: ${url}\n\nGitHub Pagesの公開完了後に表示されます。`);
}

function normalizeSlug_(value) {
  return String(value || '').toLowerCase().trim()
    .replace(/[^a-z0-9-]+/g,'-').replace(/^-+|-+$/g,'');
}

function writeByHeader_(sheet,row,header,value) {
  const headers = sheet.getRange(1,1,1,sheet.getLastColumn()).getValues()[0];
  const col = headers.indexOf(header) + 1;
  if (col > 0) sheet.getRange(row,col).setValue(value);
}
