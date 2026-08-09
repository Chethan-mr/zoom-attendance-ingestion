# Minimal ping test

If Chat still says "not responding", temporarily replace **all** of `Code.gs` with:

```javascript
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
```

Clear `Cards.gs`, `Config.gs`, `Data.gs` completely.

Then use **Head deployment ID** (Deploy → Test deployments), paste into Chat API Configuration → Apps Script, Save.

Test in a **1:1 DM** with the app first: `ping`
