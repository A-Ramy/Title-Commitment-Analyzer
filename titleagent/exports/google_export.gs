/**
 * Title Commitment Agent → Google Drive (Total Cash Home Buyers).
 *
 * Saves the app's Google Sheets / Docs exports into the folder set in the app
 * (Settings → Google Exports), as the Google account that deploys this script.
 * Nothing to edit: paste, add the Drive service, run setup, deploy.
 * Only the Title Commitment Agent can use it: every request must carry the key setup() prints.
 */

const SHEET = 'application/vnd.google-apps.spreadsheet';
const DOC = 'application/vnd.google-apps.document';
const SOURCE = {
  sheet: [SHEET, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
  doc: [DOC, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
};

/** Run once from the editor: makes the key and prints the two lines for the app's secrets. */
function setup() {
  const props = PropertiesService.getScriptProperties();
  let key = props.getProperty('KEY');
  if (!key) {
    key = (Utilities.getUuid() + Utilities.getUuid()).replace(/-/g, '');
    props.setProperty('KEY', key);
  }
  DriveApp.getRootFolder(); // asks for Drive access now, not on the first export
  Drive.About.get({fields: 'user'}); // fails here if the Drive service wasn't added
  Logger.log('Deploy as a web app, then add to the app secrets:\nGOOGLE_EXPORT_URL = "<the web app URL>"\n' +
             'GOOGLE_EXPORT_KEY = "' + key + '"');
}

function doPost(e) {
  try {
    const req = JSON.parse(e.postData.contents);
    const key = PropertiesService.getScriptProperties().getProperty('KEY');
    if (!key || req.key !== key) return reply({ok: false, error: 'wrong key'});
    const folder = Drive.Files.get(req.folder, {
      supportsAllDrives: true, fields: 'name, mimeType, capabilities(canAddChildren)',
    });
    if (folder.mimeType !== 'application/vnd.google-apps.folder') return reply({ok: false, error: 'not a folder'});
    if (!folder.capabilities.canAddChildren) return reply({ok: false, error: 'read only', folder: folder.name});
    if (req.action === 'ping') return reply({ok: true, folder: folder.name});

    const type = SOURCE[req.kind];
    if (!type) return reply({ok: false, error: 'unknown kind'});
    const blob = Utilities.newBlob(Utilities.base64Decode(req.data), type[1], req.name);
    const file = Drive.Files.create({name: req.name, mimeType: type[0], parents: [req.folder]}, blob, {
      supportsAllDrives: true, fields: 'id, webViewLink',
    });
    return reply({ok: true, link: file.webViewLink, folder: folder.name});
  } catch (err) {
    return reply({ok: false, error: String(err).slice(0, 300)});
  }
}

function reply(body) {
  return ContentService.createTextOutput(JSON.stringify(body)).setMimeType(ContentService.MimeType.JSON);
}
