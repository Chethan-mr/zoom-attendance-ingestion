/**
 * Google Chat app entrypoints for Manual Attendance.
 *
 * Preferred connection (more reliable):
 *   Deploy → Web app → Anyone
 *   Chat API Configuration → HTTP endpoint URL → paste Web app URL
 *
 * Alternate connection:
 *   Deploy → Add-on → paste Deployment ID under Apps Script
 */

function textReply_(text) {
  return { text: String(text) };
}

function onAddToSpace(event) {
  return textReply_('Manual Attendance ready. Send `hi` or `/attendance` to begin.');
}

function onRemoveFromSpace(event) {
  console.log('Removed from space', event && event.space && event.space.name);
}

/**
 * HTTP endpoint handler for Chat (Web app deployment).
 */
function doPost(e) {
  try {
    var event = JSON.parse(e.postData.contents);
    var body = routeChatEvent_(event) || {};
    return ContentService
      .createTextOutput(JSON.stringify(body))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    console.error(err);
    return ContentService
      .createTextOutput(JSON.stringify({
        text: 'Error: ' + String(err && err.message ? err.message : err)
      }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet() {
  return ContentService.createTextOutput('Manual Attendance Chat app is running.');
}

function routeChatEvent_(event) {
  var type = event && event.type;
  if (type === 'ADDED_TO_SPACE') {
    return onAddToSpace(event);
  }
  if (type === 'MESSAGE') {
    return onMessage(event);
  }
  if (type === 'CARD_CLICKED') {
    return onCardClick(event);
  }
  if (type === 'REMOVED_FROM_SPACE') {
    onRemoveFromSpace(event);
    return {};
  }
  return {};
}

function onMessage(event) {
  try {
    var message = (event && event.message) || {};
    var text = message.argumentText || message.text || '';
    text = String(text).replace(/@\S+/g, '').trim().toLowerCase();

    if (text === 'ping' || text === 'test') {
      return textReply_('Manual Attendance is online.');
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

    return textReply_('Send `hi` or `/attendance` to start Manual Attendance.');
  } catch (err) {
    console.error(err);
    return textReply_('Error: ' + String(err && err.message ? err.message : err));
  }
}

function onCardClick(event) {
  var functionName = '';
  if (event && event.common && event.common.invokedFunction) {
    functionName = event.common.invokedFunction;
  } else if (event && event.action && event.action.actionMethodName) {
    functionName = event.action.actionMethodName;
  } else if (event && event.action && event.action.function) {
    functionName = event.action.function;
  }

  try {
    if (functionName === 'select_program') {
      return handleSelectProgram_(event);
    }
    if (functionName === 'load_learners') {
      return handleLoadLearners_(event);
    }
    if (functionName === 'submit_attendance') {
      return handleSubmitAttendance_(event);
    }
    return errorCard_('Unknown action: ' + (functionName || '(none)'));
  } catch (err) {
    console.error(err);
    return errorCard_(String(err && err.message ? err.message : err));
  }
}

function startManualAttendance_() {
  try {
    var cache = fetchAttendanceCache_();
    if (!cache.programs.length) {
      return errorCard_(
        'No programs in cache yet. Run the GitHub Action ' +
        '"Sync Manual Attendance Cache" first.'
      );
    }
    return programSelectionCard_(cache.programs);
  } catch (err) {
    console.error(err);
    return errorCard_(
      'Could not load programs cache. Check CACHE_URL / GITHUB_TOKEN. ' +
      String(err && err.message ? err.message : err)
    );
  }
}

function handleSelectProgram_(event) {
  var formInputs = (event.common && event.common.formInputs) || {};
  var programId = formString_(formInputs, 'program_id');
  if (!programId) {
    return errorCard_('Please select a program before continuing.');
  }

  var cache = fetchAttendanceCache_();
  var programName = programId;
  cache.programs.forEach(function (p) {
    if (p.id === programId) {
      programName = p.text;
    }
  });

  return sessionDetailsCard_(programId, programName);
}

function handleLoadLearners_(event) {
  var formInputs = (event.common && event.common.formInputs) || {};
  var params = actionParams_(event);

  var programId = params.program_id || formString_(formInputs, 'program_id');
  var programName = params.program_name || programId || 'Program';
  if (!programId) {
    return errorCard_('Missing program. Restart with `hi`.');
  }

  var sessionDay = formDate_(formInputs, 'session_date');
  if (!sessionDay) {
    return errorCard_('Please select an attendance date.');
  }

  var startTime = formString_(formInputs, 'start_time');
  var endTime = formString_(formInputs, 'end_time');
  if (!startTime || !endTime) {
    return errorCard_('Please select both start and end times.');
  }
  if (endTime <= startTime) {
    return errorCard_('End time must be after start time.');
  }

  var topic = (formString_(formInputs, 'meeting_topic') || '').trim();
  var sessionDate = sessionDay;
  var meetingTopic = topic || sessionDate;

  var cache = fetchAttendanceCache_();
  var learners = cache.learners_by_program[programId] || [];
  if (!learners.length) {
    return errorCard_(
      'No learners found for <b>' + programName + '</b> in the cache. ' +
      'Re-run "Sync Manual Attendance Cache".'
    );
  }

  return learnerChecklistCard_({
    programId: programId,
    programName: programName,
    sessionDate: sessionDate,
    meetingTopic: meetingTopic,
    startTime: startTime,
    endTime: endTime,
    learners: learners
  });
}

function handleSubmitAttendance_(event) {
  var formInputs = (event.common && event.common.formInputs) || {};
  var params = actionParams_(event);

  var programId = params.program_id;
  var programName = params.program_name || programId;
  var sessionDate = params.session_date;
  var meetingTopic = params.meeting_topic || sessionDate;
  var startTime = params.start_time;
  var endTime = params.end_time;
  var allIdsRaw = params.all_learner_ids || '';

  if (!programId || !sessionDate || !startTime || !endTime) {
    return errorCard_('Missing session details. Restart with `hi`.');
  }

  var allLearnerIds = allIdsRaw.split(',').filter(function (x) { return !!x; });
  var absentLearnerIds = formStrings_(formInputs, 'absent_learners');
  var presentCount = allLearnerIds.filter(function (id) {
    return absentLearnerIds.indexOf(id) === -1;
  }).length;

  var payload = {
    program_id: programId,
    program_name: programName,
    session_date: sessionDate,
    meeting_topic: meetingTopic,
    start_time: startTime,
    end_time: endTime,
    all_learner_ids: allLearnerIds,
    absent_learner_ids: absentLearnerIds
  };

  triggerManualAttendanceSubmit_(payload);

  return successCard_({
    programName: programName,
    sessionDate: sessionDate,
    meetingTopic: meetingTopic,
    startTime: startTime,
    endTime: endTime,
    presentCount: presentCount,
    absentCount: absentLearnerIds.length
  });
}

function formString_(formInputs, name) {
  var field = formInputs[name];
  if (!field || !field.stringInputs || !field.stringInputs.value) {
    return null;
  }
  return String(field.stringInputs.value[0]);
}

function formStrings_(formInputs, name) {
  var field = formInputs[name];
  if (!field || !field.stringInputs || !field.stringInputs.value) {
    return [];
  }
  return field.stringInputs.value.map(function (v) { return String(v); });
}

function formDate_(formInputs, name) {
  var field = formInputs[name];
  if (!field || !field.dateInput || field.dateInput.msSinceEpoch == null) {
    return null;
  }
  var ms = Number(field.dateInput.msSinceEpoch);
  var d = new Date(ms);
  var yyyy = d.getUTCFullYear();
  var mm = ('0' + (d.getUTCMonth() + 1)).slice(-2);
  var dd = ('0' + d.getUTCDate()).slice(-2);
  return yyyy + '-' + mm + '-' + dd;
}

function actionParams_(event) {
  var params = {};
  var lists = [];
  if (event.common && event.common.parameters) {
    lists.push(event.common.parameters);
  }
  if (event.action && event.action.parameters) {
    lists.push(event.action.parameters);
  }
  lists.forEach(function (list) {
    list.forEach(function (item) {
      if (item && item.key) {
        params[item.key] = String(item.value || '');
      }
    });
  });
  return params;
}
