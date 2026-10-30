/**
 * Title Commitment Agent → Google Drive (Total Cash Home Buyers).
 *
 * Saves the app's exports into the folder set in the app (Settings → Google Exports), as the Google account that
 * deploys this script, each in a folder for its type (PDF, Word, Excel, CSV, Google Sheets, Google Docs), made the
 * first time. Nothing to edit: paste, add the Drive service, run setup, deploy.
 * Only the Title Commitment Agent can use it: every request must carry the key setup() prints.
 * Updating: paste over the old script, Save, then Deploy → Manage deployments → edit → Version: New version.
 */

const VERSION = 2; // the engine asks for this: an older script can't make the folders
const FOLDER = 'application/vnd.google-apps.folder';

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
    if (folder.mimeType !== FOLDER) return reply({ok: false, error: 'not a folder'});
    if (!folder.capabilities.canAddChildren) return reply({ok: false, error: 'read only', folder: folder.name});
    if (req.action === 'ping') return reply({ok: true, folder: folder.name, version: VERSION});
    if (req.action !== 'save' || !req.type) return reply({ok: false, error: 'unknown kind'});

    // the file as it is (PDF, Word, Excel, CSV), or converted when convert names a Google type (Sheets, Docs)
    const blob = Utilities.newBlob(Utilities.base64Decode(req.data), req.type, req.name);
    const meta = {name: req.name, parents: [subfolder(req.folder, req.subfolder)]};
    if (req.convert) meta.mimeType = req.convert;
    const file = Drive.Files.create(meta, blob, {supportsAllDrives: true, fields: 'id, webViewLink'});
    return reply({ok: true, link: file.webViewLink, folder: folder.name, version: VERSION});
  } catch (err) {
    return reply({ok: false, error: String(err).slice(0, 300)});
  }
}

/** The folder for this type inside the chosen one, made the first time (one at a time, so never twice). */
function subfolder(parent, name) {
  if (!name) return parent;
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const q = "'" + parent + "' in parents and name = '" + name.replace(/'/g, "\\'") + "' and mimeType = '" +
              FOLDER + "' and trashed = false";
    const found = Drive.Files.list({
      q: q, corpora: 'allDrives', supportsAllDrives: true, includeItemsFromAllDrives: true, fields: 'files(id)',
    }).files;
    if (found && found.length) return found[0].id;
    return Drive.Files.create({name: name, mimeType: FOLDER, parents: [parent]}, null,
                              {supportsAllDrives: true, fields: 'id'}).id;
  } finally {
    lock.releaseLock();
  }
}

function reply(body) {
  return ContentService.createTextOutput(JSON.stringify(body)).setMimeType(ContentService.MimeType.JSON);
}
