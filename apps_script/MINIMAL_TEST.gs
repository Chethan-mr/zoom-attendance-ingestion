/**
 * QUICK TEST — paste ONLY this into Code.gs and clear Cards/Config/Data.
 * Then redeploy Add-on and try: @Manual attendance ping
 */

function onMessage(event) {
  return {
    hostAppDataAction: {
      chatDataAction: {
        createMessageAction: {
          message: { text: 'pong — Add-on reply format works.' }
        }
      }
    }
  };
}

function onAddToSpace() { return onMessage(); }
function onAddedToSpace() { return onMessage(); }
function onCardClick() { return onMessage(); }
