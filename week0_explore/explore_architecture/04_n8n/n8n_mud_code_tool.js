// n8n AI Agent → "Code Tool" (Language: JavaScript)
// Tool name suggestion: mud
// Tool description (paste into the tool's description field so the LLM knows how to call it):
//
//   Interact with a live MUD (text adventure) session. Actions:
//   - "send": issue a MUD command (e.g. look, north, "kill rat") and get the new game output.
//   - "read": get any new output since last read, without sending a command.
//   - "status": check whether the session is connected.
//   - "start"/"stop": (re)connect or end the session.
//
// The AI Agent passes its arguments as `query`. Configure the tool's input schema
// (or let the agent send JSON) as: { "action": "send", "command": "look", "wait": 1.5 }
//
// Set the daemon URL + optional token below (or as workflow/n8n env vars).

const BASE_URL = $env.MUD_BRIDGE_URL || 'http://127.0.0.1:8765';
const TOKEN = $env.MUD_HTTP_TOKEN || '';

// The agent may hand us a JSON string or an already-parsed object.
let args = query;
if (typeof args === 'string') {
  try { args = JSON.parse(args); }
  catch { args = { action: 'send', command: query }; } // bare string => treat as a command
}
args = args || {};

const action = (args.action || 'send').toLowerCase();
const headers = TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {};

async function call(method, path, body) {
  const res = await this.helpers.httpRequest({
    method,
    url: `${BASE_URL}${path}`,
    headers: { ...headers, 'Content-Type': 'application/json' },
    body,
    json: true,
    timeout: 40000,
  });
  return res;
}

let out;
switch (action) {
  case 'send':
    out = await call.call(this, 'POST', '/send', {
      text: args.command ?? args.text ?? '',
      wait: args.wait ?? 1.5,
    });
    break;
  case 'read':
    out = await call.call(this, 'GET', '/read');
    break;
  case 'status':
    out = await call.call(this, 'GET', '/status');
    break;
  case 'start':
    out = await call.call(this, 'POST', '/start', {});
    break;
  case 'stop':
    out = await call.call(this, 'POST', '/stop', {});
    break;
  default:
    return `Unknown action "${action}". Use send | read | status | start | stop.`;
}

// Return a compact string — that is what the LLM will read as the tool result.
if (out && out.ok === false) return `MUD error: ${out.error}`;
if (out && typeof out.output === 'string') return out.output || '(no new output)';
return JSON.stringify(out);
