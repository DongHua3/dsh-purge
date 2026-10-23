// Placeholders are filled by official-update.js. Quit the official client, run the downloaded installer, then reopen.
var exe = __EXE_JSON__;
var installer = __INSTALLER_JSON__;
var resources = __RESOURCES_JSON__;
var installDir = __INSTALL_DIR_JSON__;
if (installDir.length > 3) installDir = installDir.replace(/[\\\/]+$/, '');
var logPath = __LOG_JSON__;
var fso = new ActiveXObject('Scripting.FileSystemObject');
var sh = new ActiveXObject('WScript.Shell');
var wmi = GetObject('winmgmts:\\\\.\\root\\cimv2');
function z(n) { return (n < 10 ? '0' : '') + n; }
function stamp() { var d = new Date(); return d.getFullYear() + '-' + z(d.getMonth() + 1) + '-' + z(d.getDate()) + 'T' + z(d.getHours()) + ':' + z(d.getMinutes()) + ':' + z(d.getSeconds()); }
function log(m) { var f = fso.OpenTextFile(logPath, 8, true); f.WriteLine(stamp() + ' ' + m); f.Close(); }
function samePath(a, b) { return String(a || '').replace(/\//g, '\\').toLowerCase() === String(b || '').replace(/\//g, '\\').toLowerCase(); }
function pids() { var out = []; var e = new Enumerator(wmi.ExecQuery("SELECT ProcessId, ExecutablePath FROM Win32_Process WHERE Name = 'DeepSeek Harness.exe'")); for (; !e.atEnd(); e.moveNext()) { var p = e.item(); if (samePath(p.ExecutablePath, exe)) out.push(p.ProcessId); } return out; }
function fileSize(fp) { if (!fso.FileExists(fp)) return -1; return fso.GetFile(fp).Size; }
function fileStamp(fp) { if (!fso.FileExists(fp)) return ''; return String(fso.GetFile(fp).DateLastModified); }
log('update-begin');
WScript.Sleep(800);
var list = pids();
log('pids ' + list.join(','));
for (var i = 0; i < list.length; i++) sh.Run('taskkill.exe /F /PID ' + list[i], 0, true);
var deadline = new Date().getTime() + 20000;
var left = list;
while (new Date().getTime() < deadline) { left = pids(); if (left.length === 0) break; WScript.Sleep(200); }
log('left ' + left.length);
var asar = resources + '\\app.asar';
var bak = asar + '.bak';
var appDir = resources + '\\app';
var movedApp = false;
var prev = '';
if (fso.FolderExists(appDir)) {
  prev = appDir + '.dshpurge-prev';
  if (fso.FolderExists(prev)) prev = appDir + '.dshpurge-prev-' + (new Date().getTime());
  for (var n = 0; n < 40; n++) {
    try { fso.MoveFolder(appDir, prev); movedApp = true; log('moved-app'); break; }
    catch (moveErr) { log('move-app ' + (moveErr && moveErr.message ? moveErr.message : moveErr)); WScript.Sleep(250); }
  }
}
var copiedAsar = false;
if (!fso.FileExists(asar) && fso.FileExists(bak)) {
  try { fso.CopyFile(bak, asar, true); copiedAsar = true; log('restored-asar'); }
  catch (restoreErr) { log('restore-asar ' + (restoreErr && restoreErr.message ? restoreErr.message : restoreErr)); }
}
var exeBeforeSize = fileSize(exe);
var exeBeforeStamp = fileStamp(exe);
var asarBeforeSize = fileSize(asar);
function runInstaller(updated) {
  var args = updated ? ' --updated /S /D=' : ' /S /D=';
  return sh.Run('"' + installer + '"' + args + installDir, 0, true);
}
function resourcesPresent() {
  // Required resources for a usable install: the packed archive or the unpacked app dir.
  return fso.FileExists(asar) || fso.FolderExists(appDir);
}
// Success is installer exit code AND required resources present. Size/timestamp drift is
// logged for diagnosis only: a real installer can produce byte-identical output, and the
// old "size changed" heuristic then triggered a second install plus a bogus rollback.
function decide(code, exeChanged, asarChanged, resourcesOk) {
  log('decide exit=' + code + ' resources=' + resourcesOk + ' exeChanged=' + exeChanged + ' asarChanged=' + asarChanged);
  return code === 0 && resourcesOk;
}
var code = runInstaller(true);
log('installer ' + code);
var exeChanged = fileSize(exe) !== exeBeforeSize || fileStamp(exe) !== exeBeforeStamp;
var asarChanged = fileSize(asar) !== asarBeforeSize;
log('observed exe=' + exeChanged + ' asar=' + asarChanged);
var resourcesOk = resourcesPresent();
var ok = decide(code, exeChanged, asarChanged, resourcesOk);
if (!ok && code === 0 && !resourcesOk) {
  // Retry only when the installer reported success but the required resources are missing.
  // A non-zero exit code is a real failure: retrying would start a bogus second install.
  code = runInstaller(false);
  log('installer-plain ' + code);
  exeChanged = fileSize(exe) !== exeBeforeSize || fileStamp(exe) !== exeBeforeStamp;
  asarChanged = fileSize(asar) !== asarBeforeSize;
  resourcesOk = resourcesPresent();
  log('observed-plain exe=' + exeChanged + ' asar=' + asarChanged);
  ok = decide(code, exeChanged, asarChanged, resourcesOk);
}
if (!ok) {
  if (copiedAsar && fso.FileExists(asar)) {
    try { fso.DeleteFile(asar, true); log('rehid-asar'); } catch (hideErr) { log('rehid-asar ' + hideErr); }
  }
  // A concurrent unpack helper may have recreated resources\app. On failure we must NOT
  // fso.DeleteFolder it: FSO deletes through an app\runtime -> resources\runtime junction and
  // wipes the real runtime (that is how office/SKILL.md disappeared). Rename it into a unique
  // app.dshpurge-failed-<ts> quarantine instead and let the Node side clean that up with
  // fs.rmSync after validating the path; if the rename fails, keep the scene and log it.
  var isolated = '';
  if (movedApp) {
    if (fso.FolderExists(appDir)) {
      for (var k = 0; k < 20; k++) {
        var quarantine = appDir + '.dshpurge-failed-' + (new Date().getTime());
        try { fso.MoveFolder(appDir, quarantine); isolated = quarantine; log('isolated-app ' + quarantine); break; }
        catch (isoErr) { log('isolate-app ' + (isoErr && isoErr.message ? isoErr.message : isoErr)); WScript.Sleep(250); }
      }
      if (fso.FolderExists(appDir)) log('isolate-app-kept ' + appDir);
    }
    // Restore the pre-update app: prefer the canonical app.dshpurge-prev (that is the one
    // moved out before the installer ran), otherwise the directory this run moved aside.
    // Never restore the app a concurrent helper just rebuilt - it is the quarantined one.
    var originalPrev = appDir + '.dshpurge-prev';
    var restoreFrom = fso.FolderExists(originalPrev) ? originalPrev : prev;
    if (!fso.FolderExists(appDir) && restoreFrom && fso.FolderExists(restoreFrom)) {
      try { fso.MoveFolder(restoreFrom, appDir); log('restored-app ' + restoreFrom); }
      catch (backErr) { log('restored-app ' + (backErr && backErr.message ? backErr.message : backErr)); }
    } else if (fso.FolderExists(appDir)) {
      log('restore-app-skipped ' + appDir);
    }
  }
  log('decide-final rollback isolated=' + isolated);
  try { sh.Environment('PROCESS').Remove('ELECTRON_RUN_AS_NODE'); } catch (ignore) {}
  sh.Run('"' + exe + '"', 1, false);
  log('started-old');
} else {
  if (!movedApp && fso.FolderExists(appDir)) log('move-app-failed');
  try {
    var marker = fso.CreateTextFile(resources + '\\dsh-purge-reapply-asar', true);
    marker.WriteLine('1');
    marker.Close();
    log('marker');
  } catch (markerErr) { log('marker ' + markerErr); }
  try { sh.Environment('PROCESS').Remove('ELECTRON_RUN_AS_NODE'); } catch (ignore2) {}
  sh.Run('"' + exe + '"', 1, false);
  log('started');
}
