function fetchAttendanceCache_() {
  var config = getConfig_();
  var response = UrlFetchApp.fetch(config.cacheUrl, {
    method: 'get',
    muteHttpExceptions: true,
    headers: {
      Authorization: 'Bearer ' + config.githubToken,
      Accept: 'application/vnd.github.raw',
      'User-Agent': 'manual-attendance-apps-script'
    }
  });

  var code = response.getResponseCode();
  if (code < 200 || code >= 300) {
    // Fallback: try public raw URL without auth headers
    response = UrlFetchApp.fetch(config.cacheUrl, {
      method: 'get',
      muteHttpExceptions: true
    });
    code = response.getResponseCode();
  }

  if (code < 200 || code >= 300) {
    throw new Error('Failed to load attendance cache (HTTP ' + code + ')');
  }

  var cache = JSON.parse(response.getContentText());
  if (!cache.programs) {
    cache.programs = [];
  }
  if (!cache.learners_by_program) {
    cache.learners_by_program = {};
  }
  return cache;
}

function triggerManualAttendanceSubmit_(payload) {
  var config = getConfig_();
  var url = 'https://api.github.com/repos/' + config.githubRepo + '/dispatches';

  var response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    muteHttpExceptions: true,
    headers: {
      Authorization: 'Bearer ' + config.githubToken,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'manual-attendance-apps-script'
    },
    payload: JSON.stringify({
      event_type: 'manual_attendance_submit',
      client_payload: payload
    })
  });

  var code = response.getResponseCode();
  // GitHub returns 204 No Content on success
  if (code !== 204 && code !== 200) {
    throw new Error(
      'GitHub dispatch failed (HTTP ' + code + '): ' + response.getContentText()
    );
  }
}

function buildTimeSlots_() {
  var items = [];
  for (var minutes = 6 * 60; minutes <= 22 * 60; minutes += 15) {
    var hh = Math.floor(minutes / 60);
    var mm = minutes % 60;
    var value =
      (hh < 10 ? '0' : '') + hh + ':' + (mm < 10 ? '0' : '') + mm;
    items.push({ text: value, value: value });
  }
  return items;
}
