/**
 * Manual Attendance Web App (shareable link — no Google Chat required).
 *
 * Deploy: Deploy → New deployment → Web app
 *   Execute as: Me
 *   Who has access: Anyone within Mentorskool (or your domain)
 * Copy the /exec URL and share with ops.
 *
 * Script properties (same as Chat app):
 *   CACHE_URL, GITHUB_TOKEN, GITHUB_REPO
 */

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('Manual Attendance')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

/** Bootstrap data for the page: programs + recent sessions */
function getBootstrap() {
  var cache = fetchAttendanceCache_();
  return {
    updated_at: cache.updated_at || null,
    programs: cache.programs || [],
    recent_sessions: cache.recent_sessions || []
  };
}

function getLearners(programId) {
  if (!programId) return [];
  var cache = fetchAttendanceCache_();
  return cache.learners_by_program[programId] || [];
}

/**
 * Submit attendance. Payload from the HTML form:
 * {
 *   program_id, program_name, session_date, topic_suffix,
 *   start_time, end_time, all_present, absent_learner_ids[]
 * }
 */
function submitAttendance(form) {
  form = form || {};
  var programId = String(form.program_id || '').trim();
  var programName = String(form.program_name || programId).trim();
  if (!programId) throw new Error('Select a program.');

  var sessionDate = String(form.session_date || '').trim() || todayIso_();
  var startTime = normalizeTime_(form.start_time || '09:00');
  var endTime = normalizeTime_(form.end_time || '11:00');
  if (!startTime || !endTime) {
    throw new Error('Enter start and end times as HH:MM (e.g. 09:00).');
  }
  if (endTime <= startTime) throw new Error('End time must be after start time.');

  var topicSuffix = String(form.topic_suffix || '').trim();
  if (!topicSuffix) {
    throw new Error('Enter the topic name (saved as ' + programName + '-ILT-[topic]).');
  }
  var prefix = programName + '-ILT-';
  if (topicSuffix.indexOf(prefix) === 0) {
    topicSuffix = topicSuffix.substring(prefix.length).trim();
  }
  if (!topicSuffix) throw new Error('Enter the topic name after ILT-.');
  var meetingTopic = prefix + topicSuffix;

  var cache = fetchAttendanceCache_();
  var learners = cache.learners_by_program[programId] || [];
  if (!learners.length) {
    throw new Error('No learners for this program. Re-sync the cache.');
  }
  var allLearnerIds = learners.map(function (l) { return l.id; });

  var absentLearnerIds = Array.isArray(form.absent_learner_ids)
    ? form.absent_learner_ids.map(String)
    : [];
  var allPresent = !!form.all_present;
  if (absentLearnerIds.length > 0) {
    allPresent = false;
  } else if (allPresent) {
    absentLearnerIds = [];
  } else {
    absentLearnerIds = [];
  }

  var presentCount = allLearnerIds.filter(function (id) {
    return absentLearnerIds.indexOf(id) === -1;
  }).length;

  triggerManualAttendanceSubmit_({
    program_id: programId,
    program_name: programName,
    session_date: sessionDate,
    meeting_topic: meetingTopic,
    start_time: startTime,
    end_time: endTime,
    all_learner_ids: allLearnerIds,
    absent_learner_ids: absentLearnerIds
  });

  return {
    ok: true,
    meeting_topic: meetingTopic,
    session_date: sessionDate,
    start_time: startTime,
    end_time: endTime,
    present_count: presentCount,
    absent_count: absentLearnerIds.length
  };
}

// -------------------- Shared helpers --------------------

function getConfig_() {
  var props = PropertiesService.getScriptProperties();
  var cacheUrl = props.getProperty('CACHE_URL');
  var githubToken = props.getProperty('GITHUB_TOKEN');
  var githubRepo = props.getProperty('GITHUB_REPO') || 'Chethan-mr/zoom-attendance-ingestion';
  if (!cacheUrl) throw new Error('Missing Script Property CACHE_URL');
  if (!githubToken) throw new Error('Missing Script Property GITHUB_TOKEN');
  return { cacheUrl: cacheUrl, githubToken: githubToken, githubRepo: githubRepo };
}

function fetchAttendanceCache_() {
  var config = getConfig_();
  var apiUrl =
    'https://api.github.com/repos/' +
    config.githubRepo +
    '/contents/data/manual_attendance_cache.json?ref=main';

  var response = UrlFetchApp.fetch(apiUrl, {
    method: 'get',
    muteHttpExceptions: true,
    headers: {
      Authorization: 'Bearer ' + config.githubToken,
      Accept: 'application/vnd.github.raw',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'manual-attendance-webapp'
    }
  });

  var code = response.getResponseCode();
  if (code < 200 || code >= 300) {
    response = UrlFetchApp.fetch(config.cacheUrl, {
      method: 'get',
      muteHttpExceptions: true,
      headers: {
        Authorization: 'Bearer ' + config.githubToken,
        'User-Agent': 'manual-attendance-webapp'
      }
    });
    code = response.getResponseCode();
  }
  if (code < 200 || code >= 300) {
    response = UrlFetchApp.fetch(config.cacheUrl, { method: 'get', muteHttpExceptions: true });
    code = response.getResponseCode();
  }
  if (code < 200 || code >= 300) {
    throw new Error('Failed to load attendance cache (HTTP ' + code + ')');
  }

  var cache = JSON.parse(response.getContentText());
  cache.programs = cache.programs || [];
  cache.learners_by_program = cache.learners_by_program || {};
  cache.recent_sessions = cache.recent_sessions || [];
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
      'User-Agent': 'manual-attendance-webapp'
    },
    payload: JSON.stringify({
      event_type: 'manual_attendance_submit',
      client_payload: payload
    })
  });
  var code = response.getResponseCode();
  if (code !== 204 && code !== 200) {
    throw new Error('GitHub dispatch failed (HTTP ' + code + '): ' + response.getContentText());
  }
}

function normalizeTime_(value) {
  if (!value) return null;
  var text = String(value).trim();
  var match = text.match(/^(\d{1,2}):(\d{2})$/);
  if (!match) return null;
  var hh = Number(match[1]);
  var mm = Number(match[2]);
  if (hh < 0 || hh > 23 || mm < 0 || mm > 59) return null;
  return (hh < 10 ? '0' : '') + hh + ':' + (mm < 10 ? '0' : '') + mm;
}

function todayIso_() {
  var d = new Date();
  var yyyy = d.getFullYear();
  var mm = ('0' + (d.getMonth() + 1)).slice(-2);
  var dd = ('0' + d.getDate()).slice(-2);
  return yyyy + '-' + mm + '-' + dd;
}
