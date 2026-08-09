/**
 * TEMPORARY: paste into Code.gs only to verify Chat replies.
 * Must use hostAppDataAction format for Workspace Add-ons Chat.
 */

function onMessage(event) {
  return {
    hostAppDataAction: {
      chatDataAction: {
        createMessageAction: {
          message: {
            text: 'pong — Apps Script reached (Add-on format OK).'
          }
        }
      }
    }
  };
}

function onAddToSpace() {
  return onMessage();
}

function onAddedToSpace() {
  return onMessage();
}

function onCardClick() {
  return onMessage();
}
