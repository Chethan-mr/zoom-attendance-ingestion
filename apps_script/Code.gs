/**
 * Google Chat (Workspace Add-on) entrypoints for Manual Attendance.
 *
 * Responses MUST use hostAppDataAction / createMessageAction.
 * Plain { text: "..." } will show as "not responding" even when Executions = Completed.
 */

function onAddToSpace(event) {
  return textMessage_('Manual Attendance ready. Send `hi` or `/attendance` to begin.');
}

function onAddedToSpace(event) {
  return onAddToSpace(event);
}

function onRemoveFromSpace(event) {
  console.log('Removed from space');
}

function onRemovedFromSpace(event) {
  onRemoveFromSpace(event);
}

function onMessage(event) {
  try {
    var text = extractMessageText_(event);

    if (text === 'ping' || text === 'test') {
      return textMessage_('Manual Attendance is online.');
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

    return textMessage_('Send `hi` or `/attendance` to start Manual Attendance.');
  } catch (err) {
    console.error(err);
    return textMessage_('Error: ' + String(err && err.message ? err.message : err));
  }
}

function onCardClick(event) {
  var functionName = extractFunctionName_(event);

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
    return errorCard_('Unknown action: ' + (functionName || '(none)'), true);
  } catch (err) {
    console.error(err);
    return errorCard_(String(err && err.message ? err.message : err), true);
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
  var formInputs = extractFormInputs_(event);
  var programId = formString_(formInputs, 'program_id');
  if (!programId) {
    return errorCard_('Please select a program before continuing.', true);
  }

  var cache = fetchAttendanceCache_();
  var programName = programId;
  cache.programs.forEach(function (p) {
    if (p.id === programId) {
      programName = p.text;
    }
  });

  return sessionDetailsCard_(programId, programName, true);
}

function handleLoadLearners_(event) {
  var formInputs = extractFormInputs_(event);
  var params = actionParams_(event);

  var programId = params.program_id || formString_(formInputs, 'program_id');
  var programName = params.program_name || programId || 'Program';
  if (!programId) {
    return errorCard_('Missing program. Restart with `hi`.', true);
  }

  var sessionDay = formDate_(formInputs, 'session_date');
  if (!sessionDay) {
    return errorCard_('Please select an attendance date.', true);
  }

  var startTime = formString_(formInputs, 'start_time');
  var endTime = formString_(formInputs, 'end_time');
  if (!startTime || !endTime) {
    return errorCard_('Please select both start and end times.', true);
  }
  if (endTime <= startTime) {
    return errorCard_('End time must be after start time.', true);
  }

  var topic = (formString_(formInputs, 'meeting_topic') || '').trim();
  var sessionDate = sessionDay;
  var meetingTopic = topic || sessionDate;

  var cache = fetchAttendanceCache_();
  var learners = cache.learners_by_program[programId] || [];
  if (!learners.length) {
    return errorCard_(
      'No learners found for <b>' + programName + '</b> in the cache. ' +
      'Re-run "Sync Manual Attendance Cache".',
      true
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
    return errorCard_('Missing session details. Restart with `hi`.', true);
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
  }, true);
}

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
  if (event && event.commonEventObject && event.commonEventObject.parameters) {
    // some add-on payloads put function in common
  }
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
  if (!field) {
    return null;
  }
  // Add-on style: { stringInputs: { value: [...] } }
  if (field.stringInputs && field.stringInputs.value && field.stringInputs.value.length) {
    return String(field.stringInputs.value[0]);
  }
  // Sometimes nested differently
  if (field[""] && field[""].stringInputs) {
    var v = field[""].stringInputs.value;
    return v && v.length ? String(v[0]) : null;
  }
  return null;
}

function formStrings_(formInputs, name) {
  var field = formInputs[name];
  if (!field) {
    return [];
  }
  if (field.stringInputs && field.stringInputs.value) {
    return field.stringInputs.value.map(function (v) { return String(v); });
  }
  if (field[""] && field[""].stringInputs && field[""].stringInputs.value) {
    return field[""].stringInputs.value.map(function (v) { return String(v); });
  }
  return [];
}

function formDate_(formInputs, name) {
  var field = formInputs[name];
  if (!field) {
    return null;
  }
  var dateInput = field.dateInput || (field[""] && field[""].dateInput);
  if (!dateInput || dateInput.msSinceEpoch == null) {
    return null;
  }
  var ms = Number(dateInput.msSinceEpoch);
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
  if (event.commonEventObject && event.commonEventObject.parameters) {
    // object map form
    var obj = event.commonEventObject.parameters;
    Object.keys(obj).forEach(function (k) {
      params[k] = String(obj[k]);
    });
  }
  lists.forEach(function (list) {
    if (!list || !list.forEach) {
      return;
    }
    list.forEach(function (item) {
      if (item && item.key) {
        params[item.key] = String(item.value || '');
      }
    });
  });
  return params;
}
