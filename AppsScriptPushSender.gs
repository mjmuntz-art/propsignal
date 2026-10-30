/**
 * Stage-only Google Apps Script integration for nba_prop.
 *
 * Copy this file into the existing Google Apps Script project and invoke
 * pushNotifyPublished_() ONLY AFTER a successful published data build.
 * No automatic sending happens merely by adding this file.
 *
 * Script Properties:
 *  PUSH_NOTIFICATIONS_ENABLED  = true (after iPhone testing)
 *  ONESIGNAL_APP_ID            = public OneSignal app UUID
 *  ONESIGNAL_REST_API_KEY      = secret key (NEVER commit to GitHub)
 *
 * OneSignal targeting tags correspond to the GitHub Pages push-setup.js.
 */
const APP_PUSH_KEY_ = 'nba_prop';
const APP_PUSH_URL_ = 'https://mjmuntz-art.github.io/propsignal/';

/**
 * eventType: 'projections' | 'results' | 'locked'
 * publicationKey: date/week or slate ID e.g. '2026-10-30'
 * fingerprint: SHA-256 of the material published picks/results, stable over identical builds
 * title, message: user-facing notification copy
 *
 * Prefer to call this from the existing publishing function, NOT a new timer.
 * Example:
 * pushNotifyPublished_({
 *   eventType: 'projections',
 *   publicationKey: yyyyMMdd,
 *   fingerprint: pushFingerprint_({publishedPicks: publishedPicks}),
 *   title: 'NBA PropSignal — New slate',
 *   message: 'The latest published picks are ready.'
 * });
 */
function pushNotifyPublished_(event) {
  const allowed = ['projections', 'results', 'locked'];
  if (!event || allowed.indexOf(event.eventType) < 0 ||
      !event.publicationKey || !event.fingerprint ||
      !event.title || !event.message) {
    throw new Error('pushNotifyPublished_: missing/invalid publication event fields.');
  }
  const props = PropertiesService.getScriptProperties();
  if (props.getProperty('PUSH_NOTIFICATIONS_ENABLED') !== 'true') {
    return { status: 'disabled' };
  }
  const appId = props.getProperty('ONESIGNAL_APP_ID');
  const restKey = props.getProperty('ONESIGNAL_REST_API_KEY');
  if (!appId || !restKey) throw new Error('OneSignal app ID or REST API key not configured.');

  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const propertyKey = 'PUSH_SENT_' + APP_PUSH_KEY_ + '_' +
      event.eventType + '_' + String(event.publicationKey);
    const prev = props.getProperty(propertyKey);
    if (prev === String(event.fingerprint)) {
      return { status: 'unchanged' };
    }

    const filters = [
      {field: 'tag', key: 'push_' + APP_PUSH_KEY_ + '_enabled', relation: '=', value: '1'},
      {operator: 'AND'},
      {field: 'tag', key: 'push_' + APP_PUSH_KEY_ + '_' + event.eventType, relation: '=', value: '1'}
    ];
    const payload = {
      app_id: appId,
      target_channel: 'push',
      headings: {en: String(event.title)},
      contents: {en: String(event.message)},
      url: APP_PUSH_URL_,
      filters: filters
    };
    const response = UrlFetchApp.fetch('https://api.onesignal.com/notifications', {
      method: 'post',
      contentType: 'application/json',
      headers: {Authorization: 'Key ' + restKey},
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
    const code = response.getResponseCode();
    let result;
    try { result = JSON.parse(response.getContentText()); }
    catch (err) { throw new Error('OneSignal sent a non-JSON response (HTTP ' + code + ')'); }
    if (code < 200 || code >= 300 || !result.id) {
      throw new Error('OneSignal failed to accept message: HTTP ' + code + ' ' + response.getContentText());
    }
    props.setProperty(propertyKey, String(event.fingerprint));
    return {status: 'sent', notificationId: result.id};
  } finally {
    lock.releaseLock();
  }
}

/**
 * Input MUST be semantically stable: published picks/grades only.
 * Do not include refreshedAt, savedAt, updatedAt or other timer timestamps.
 * If your data source is an object, construct its keys in deterministic order.
 */
function pushFingerprint_(publishedContent) {
  const bytes = Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256,
    JSON.stringify(publishedContent),
    Utilities.Charset.UTF_8
  );
  return bytes.map(function (b) { return ('0' + (b & 255).toString(16)).slice(-2); }).join('');
}
