function textMessage_(text) {
  return { text: text };
}

function errorCard_(message) {
  return {
    cardsV2: [{
      cardId: 'manualAttendanceError',
      card: {
        header: {
          title: 'Manual Attendance',
          subtitle: 'Something went wrong'
        },
        sections: [{
          widgets: [{ textParagraph: { text: message } }]
        }]
      }
    }]
  };
}

function programSelectionCard_(programs) {
  var items = programs.map(function (p, i) {
    return {
      text: p.text,
      value: p.id,
      selected: i === 0
    };
  });

  return {
    cardsV2: [{
      cardId: 'manualAttendanceProgram',
      card: {
        header: {
          title: 'Manual Attendance',
          subtitle: 'Step 1 of 3 — Select program'
        },
        sections: [{
          widgets: [
            {
              textParagraph: {
                text:
                  'Select the program for this offline session. ' +
                  'Programs are synced hourly from the database.'
              }
            },
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
                  onClick: {
                    action: { function: 'select_program' }
                  }
                }]
              }
            }
          ]
        }]
      }
    }]
  };
}

function sessionDetailsCard_(programId, programName) {
  var slots = buildTimeSlots_();
  var startItems = slots.map(function (item) {
    return {
      text: item.text,
      value: item.value,
      selected: item.value === '09:00'
    };
  });
  var endItems = slots.map(function (item) {
    return {
      text: item.text,
      value: item.value,
      selected: item.value === '11:00'
    };
  });

  return {
    cardsV2: [{
      cardId: 'manualAttendanceSession',
      card: {
        header: {
          title: 'Manual Attendance',
          subtitle: 'Step 2 of 3 — Session details'
        },
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
                label: 'Session start time',
                type: 'DROP_DOWN',
                items: startItems
              }
            },
            {
              selectionInput: {
                name: 'end_time',
                label: 'Session end time',
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
    }]
  };
}

function learnerChecklistCard_(opts) {
  var items = opts.learners.map(function (learner) {
    return {
      text: learner.display_name,
      value: learner.id,
      selected: false
    };
  });

  var allIds = opts.learners.map(function (l) { return l.id; }).join(',');

  return {
    cardsV2: [{
      cardId: 'manualAttendanceLearners',
      card: {
        header: {
          title: 'Manual Attendance',
          subtitle: 'Step 3 of 3 — Mark absents'
        },
        sections: [{
          widgets: [
            {
              textParagraph: {
                text:
                  '<b>Program:</b> ' + opts.programName + '<br>' +
                  '<b>Date:</b> ' + opts.sessionDate + '<br>' +
                  '<b>Topic:</b> ' + opts.meetingTopic + '<br>' +
                  '<b>Time:</b> ' + opts.startTime + ' – ' + opts.endTime + '<br><br>' +
                  'Check learners who were <b>ABSENT</b>. ' +
                  'Everyone else will be marked present.'
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
    }]
  };
}

function successCard_(summary) {
  return {
    cardsV2: [{
      cardId: 'manualAttendanceSuccess',
      card: {
        header: {
          title: 'Manual Attendance submitted',
          subtitle: summary.programName || ''
        },
        sections: [{
          widgets: [{
            textParagraph: {
              text:
                '<b>Date:</b> ' + summary.sessionDate + '<br>' +
                '<b>Topic:</b> ' + summary.meetingTopic + '<br>' +
                '<b>Time:</b> ' + summary.startTime + ' – ' + summary.endTime + '<br>' +
                '<b>Present (to insert):</b> ' + summary.presentCount + '<br>' +
                '<b>Absent (not inserted):</b> ' + summary.absentCount + '<br>' +
                '<b>Account:</b> offline session<br><br>' +
                'GitHub Action is saving rows to the database now. ' +
                'Check the Actions tab if you need confirmation.'
            }
          }]
        }]
      }
    }]
  };
}
