/**
 * SINGLE-FILE Manual Attendance Chat app (Workspace Add-on format).
 *
 * IMPORTANT in Apps Script editor:
 * 1. Replace Code.gs with this entire file
 * 2. Open Cards.gs / Config.gs / Data.gs and delete ALL code
 *    (leave empty or delete the files) so old helpers cannot override this
 * 3. Keep appsscript.json from repo
 * 4. Deploy → Manage deployments → New version → Deploy
 */

// -------------------- Add-on reply wrappers --------------------

function addonCreate_(message) {
  return {
    hostAppDataAction: {
      chatDataAction: {
        createMessageAction: { message: message }
      }
    }
  };
}

function addonUpdate_(message) {
  return {
    hostAppDataAction: {
      chatDataAction: {
        updateMessageAction: { message: message }
      }
    }
  };
}

function replyText_(text, update) {
  var msg = { text: String(text) };
  return update ? addonUpdate_(msg) : addonCreate_(msg);
}

function replyCards_(cardsV2, update) {
  var msg = { cardsV2: cardsV2 };
  return update ? addonUpdate_(msg) : addonCreate_(msg);
}

function replyError_(text, update) {
  return replyCards_([{
    cardId: 'manualAttendanceError',
    card: {
      header: { title: 'Manual Attendance', subtitle: 'Something went wrong' },
      sections: [{ widgets: [{ textParagraph: { text: String(text) } }] }]
    }
  }], update);
}

// -------------------- Chat triggers --------------------

function onMessage(event) {
  try {
    var text = extractMessageText_(event);

    if (text === 'ping' || text === 'test') {
      return replyText_('Manual Attendance is online.');
    }

    if (
      text === 'hi' ||
      text === '/attendance' ||
      text === 'attendance' ||
      text === 'manual attendance' ||
      text.indexOf('/attendance') === 0
    ) {
      return startManualAttendance_();
    }

    return replyText_('Send `hi` or `/attendance` to start Manual Attendance.');
  } catch (err) {
    console.error(err);
    return replyText_('Error: ' + String(err && err.message ? err.message : err));
  }
}

function onAddToSpace() {
  return replyText_('Manual Attendance ready. Send `hi` or `/attendance` to begin.');
}

function onAddedToSpace() {
  return onAddToSpace();
}

function onRemoveFromSpace() {}
function onRemovedFromSpace() {}

function onCardClick(event) {
  var fn = extractFunctionName_(event);
  try {
    if (fn === 'select_program') return handleSelectProgram_(event);
    if (fn === 'load_learners') return handleLoadLearners_(event);
    if (fn === 'submit_attendance') return handleSubmitAttendance_(event);
    return replyError_('Unknown action: ' + (fn || '(none)'), true);
  } catch (err) {
    console.error(err);
    return replyError_(String(err && err.message ? err.message : err), true);
  }
}

// -------------------- Flow --------------------

function startManualAttendance_() {
  var cache = fetchAttendanceCache_();
  if (!cache.programs.length) {
    return replyError_(
      'No programs in cache yet. Run GitHub Action "Sync Manual Attendance Cache" first.'
    );
  }
  return programCard_(cache.programs, false);
}

function handleSelectProgram_(event) {
  var formInputs = extractFormInputs_(event);
  var programId = formString_(formInputs, 'program_id');
  if (!programId) return replyError_('Please select a program.', true);

  var cache = fetchAttendanceCache_();
  var programName = programId;
  cache.programs.forEach(function (p) {
    if (p.id === programId) programName = p.text;
  });
  return sessionCard_(programId, programName, true);
}

function handleLoadLearners_(event) {
  var formInputs = extractFormInputs_(event);
  var params = actionParams_(event);
  var programId = params.program_id || formString_(formInputs, 'program_id');
  var programName = params.program_name || programId || 'Program';
  if (!programId) return replyError_('Missing program. Restart with hi.', true);

  var sessionDate = formDate_(formInputs, 'session_date');
  if (!sessionDate) return replyError_('Please select an attendance date.', true);

  var startTime = formString_(formInputs, 'start_time');
  var endTime = formString_(formInputs, 'end_time');
  if (!startTime || !endTime) return replyError_('Select start and end times.', true);
  if (endTime <= startTime) return replyError_('End time must be after start time.', true);

  var topic = (formString_(formInputs, 'meeting_topic') || '').trim();
  var meetingTopic = topic || sessionDate;

  var cache = fetchAttendanceCache_();
  var learners = cache.learners_by_program[programId] || [];
  if (!learners.length) {
    return replyError_('No learners for ' + programName + '. Re-sync cache.', true);
  }

  return learnersCard_({
    programId: programId,
    programName: programName,
    sessionDate: sessionDate,
    meetingTopic: meetingTopic,
    startTime: startTime,
    endTime: endTime,
    learners: learners
  }, true);
}

function handleSubmitAttendance_(event) {
  var formInputs = extractFormInputs_(event);
  var params = actionParams_(event);

  var programId = params.program_id;
  var programName = params.program_name || programId;
  var sessionDate = params.session_date;
  var meetingTopic = params.meeting_topic || sessionDate;
  var startTime = params.start_time;
  var endTime = params.end_time;
  var allIdsRaw = params.all_learner_ids || '';

  if (!programId || !sessionDate || !startTime || !endTime) {
    return replyError_('Missing session details. Restart with hi.', true);
  }

  var allLearnerIds = allIdsRaw.split(',').filter(function (x) { return !!x; });
  var absentLearnerIds = formStrings_(formInputs, 'absent_learners');
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

  return replyCards_([{
    cardId: 'manualAttendanceSuccess',
    card: {
      header: {
        title: 'Manual Attendance submitted',
        subtitle: programName
      },
      sections: [{
        widgets: [{
          textParagraph: {
            text:
              '<b>Date:</b> ' + sessionDate + '<br>' +
              '<b>Topic:</b> ' + meetingTopic + '<br>' +
              '<b>Time:</b> ' + startTime + ' – ' + endTime + '<br>' +
              '<b>Present:</b> ' + presentCount + '<br>' +
              '<b>Absent (not inserted):</b> ' + absentLearnerIds.length + '<br>' +
              '<b>Account:</b> offline session'
          }
        }]
      }]
    }
  }], true);
}

// -------------------- Cards --------------------

function programCard_(programs, update) {
  var items = programs.map(function (p, i) {
    return { text: p.text, value: p.id, selected: i === 0 };
  });
  return replyCards_([{
    cardId: 'manualAttendanceProgram',
    card: {
      header: { title: 'Manual Attendance', subtitle: 'Step 1 — Select program' },
      sections: [{
        widgets: [
          { textParagraph: { text: 'Select the program for this offline session.' } },
          {
            selectionInput: {
              name: 'program_id',
              label: 'Program',
              type: 'DROP_DOWN',
              items: items
            }
          },
          {
            buttonList: {
              buttons: [{
                text: 'Continue',
                onClick: { action: { function: 'select_program' } }
              }]
            }
          }
        ]
      }]
    }
  }], update);
}

function sessionCard_(programId, programName, update) {
  var slots = buildTimeSlots_();
  var startItems = slots.map(function (item) {
    return { text: item.text, value: item.value, selected: item.value === '09:00' };
  });
  var endItems = slots.map(function (item) {
    return { text: item.text, value: item.value, selected: item.value === '11:00' };
  });

  return replyCards_([{
    cardId: 'manualAttendanceSession',
    card: {
      header: { title: 'Manual Attendance', subtitle: 'Step 2 — Session details' },
      sections: [{
        widgets: [
          { textParagraph: { text: '<b>Program:</b> ' + programName } },
          {
            dateTimePicker: {
              name: 'session_date',
              label: 'Attendance date',
              type: 'DATE_ONLY'
            }
          },
          {
            textInput: {
              name: 'meeting_topic',
              label: 'Meeting topic (optional)',
              type: 'SINGLE_LINE',
              hintText: 'Leave blank to use the date'
            }
          },
          {
            selectionInput: {
              name: 'start_time',
              label: 'Start time',
              type: 'DROP_DOWN',
              items: startItems
            }
          },
          {
            selectionInput: {
              name: 'end_time',
              label: 'End time',
              type: 'DROP_DOWN',
              items: endItems
            }
          },
          {
            buttonList: {
              buttons: [{
                text: 'Load learners',
                onClick: {
                  action: {
                    function: 'load_learners',
                    parameters: [
                      { key: 'program_id', value: programId },
                      { key: 'program_name', value: programName }
                    ]
                  }
                }
              }]
            }
          }
        ]
      }]
    }
  }], update);
}

function learnersCard_(opts, update) {
  var items = opts.learners.map(function (l) {
    return { text: l.display_name, value: l.id, selected: false };
  });
  var allIds = opts.learners.map(function (l) { return l.id; }).join(',');

  return replyCards_([{
    cardId: 'manualAttendanceLearners',
    card: {
      header: { title: 'Manual Attendance', subtitle: 'Step 3 — Mark absents' },
      sections: [{
        widgets: [
          {
            textParagraph: {
              text:
                '<b>Program:</b> ' + opts.programName + '<br>' +
                '<b>Date:</b> ' + opts.sessionDate + '<br>' +
                '<b>Topic:</b> ' + opts.meetingTopic + '<br>' +
                '<b>Time:</b> ' + opts.startTime + ' – ' + opts.endTime + '<br><br>' +
                'Check learners who were <b>ABSENT</b>.'
            }
          },
          {
            selectionInput: {
              name: 'absent_learners',
              label: 'Absent learners',
              type: 'CHECK_BOX',
              items: items
            }
          },
          {
            buttonList: {
              buttons: [{
                text: 'Submit attendance',
                onClick: {
                  action: {
                    function: 'submit_attendance',
                    parameters: [
                      { key: 'program_id', value: opts.programId },
                      { key: 'program_name', value: opts.programName },
                      { key: 'session_date', value: opts.sessionDate },
                      { key: 'meeting_topic', value: opts.meetingTopic },
                      { key: 'start_time', value: opts.startTime },
                      { key: 'end_time', value: opts.endTime },
                      { key: 'all_learner_ids', value: allIds }
                    ]
                  }
                }
              }]
            }
          }
        ]
      }]
    }
  }], update);
}

function buildTimeSlots_() {
  var items = [];
  for (var minutes = 6 * 60; minutes <= 22 * 60; minutes += 15) {
    var hh = Math.floor(minutes / 60);
    var mm = minutes % 60;
    var value = (hh < 10 ? '0' : '') + hh + ':' + (mm < 10 ? '0' : '') + mm;
    items.push({ text: value, value: value });
  }
  return items;
}

// -------------------- Config / GitHub --------------------

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
      'User-Agent': 'manual-attendance-apps-script'
    }
  });

  var code = response.getResponseCode();
  if (code < 200 || code >= 300) {
    response = UrlFetchApp.fetch(config.cacheUrl, {
      method: 'get',
      muteHttpExceptions: true,
      headers: {
        Authorization: 'Bearer ' + config.githubToken,
        'User-Agent': 'manual-attendance-apps-script'
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
  if (code !== 204 && code !== 200) {
    throw new Error('GitHub dispatch failed (HTTP ' + code + '): ' + response.getContentText());
  }
}

// -------------------- Event helpers --------------------

function extractMessageText_(event) {
  var text = '';
  if (event && event.chat && event.chat.messagePayload && event.chat.messagePayload.message) {
    var msg = event.chat.messagePayload.message;
    text = msg.argumentText || msg.text || '';
  } else if (event && event.message) {
    text = event.message.argumentText || event.message.text || '';
  }
  return String(text).replace(/@\S+/g, '').trim().toLowerCase();
}

function extractFormInputs_(event) {
  if (event && event.commonEventObject && event.commonEventObject.formInputs) {
    return event.commonEventObject.formInputs;
  }
  if (event && event.common && event.common.formInputs) {
    return event.common.formInputs;
  }
  return {};
}

function extractFunctionName_(event) {
  if (event && event.common && event.common.invokedFunction) {
    return String(event.common.invokedFunction);
  }
  if (event && event.action && event.action.actionMethodName) {
    return String(event.action.actionMethodName);
  }
  if (event && event.action && event.action.function) {
    return String(event.action.function);
  }
  if (event && event.commonEventObject && event.commonEventObject.invokedFunction) {
    return String(event.commonEventObject.invokedFunction);
  }
  return '';
}

function formString_(formInputs, name) {
  var field = formInputs[name];
  if (!field) return null;
  if (field.stringInputs && field.stringInputs.value && field.stringInputs.value.length) {
    return String(field.stringInputs.value[0]);
  }
  if (field[''] && field[''].stringInputs && field[''].stringInputs.value) {
    return String(field[''].stringInputs.value[0]);
  }
  return null;
}

function formStrings_(formInputs, name) {
  var field = formInputs[name];
  if (!field) return [];
  if (field.stringInputs && field.stringInputs.value) {
    return field.stringInputs.value.map(function (v) { return String(v); });
  }
  if (field[''] && field[''].stringInputs && field[''].stringInputs.value) {
    return field[''].stringInputs.value.map(function (v) { return String(v); });
  }
  return [];
}

function formDate_(formInputs, name) {
  var field = formInputs[name];
  if (!field) return null;
  var dateInput = field.dateInput || (field[''] && field[''].dateInput);
  if (!dateInput || dateInput.msSinceEpoch == null) return null;
  var d = new Date(Number(dateInput.msSinceEpoch));
  var yyyy = d.getUTCFullYear();
  var mm = ('0' + (d.getUTCMonth() + 1)).slice(-2);
  var dd = ('0' + d.getUTCDate()).slice(-2);
  return yyyy + '-' + mm + '-' + dd;
}

function actionParams_(event) {
  var params = {};
  var lists = [];
  if (event.common && event.common.parameters) lists.push(event.common.parameters);
  if (event.action && event.action.parameters) lists.push(event.action.parameters);
  if (event.commonEventObject && event.commonEventObject.parameters) {
    var obj = event.commonEventObject.parameters;
    Object.keys(obj).forEach(function (k) { params[k] = String(obj[k]); });
  }
  lists.forEach(function (list) {
    if (!list || !list.forEach) return;
    list.forEach(function (item) {
      if (item && item.key) params[item.key] = String(item.value || '');
    });
  });
  return params;
}
