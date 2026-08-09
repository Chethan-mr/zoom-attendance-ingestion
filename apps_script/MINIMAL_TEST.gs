/**
 * TEMPORARY test file — paste ONLY this into Code.gs (replace everything)
 * and remove/ignore Cards.gs, Config.gs, Data.gs for this test.
 *
 * Goal: prove Chat → Apps Script works.
 * Expected reply to "@Manual attendance ping": "pong"
 */

function onMessage(event) {
  var text = '';
  try {
    text = (event.message && (event.message.argumentText || event.message.text)) || '';
  } catch (e) {}
  return { text: 'pong — Apps Script reached. You said: ' + String(text) };
}

function onAddToSpace() {
  return { text: 'Manual Attendance added. Try: ping' };
}

function onCardClick() {
  return { text: 'card click ok' };
}
