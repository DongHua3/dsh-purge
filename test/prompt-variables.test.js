import test from "node:test";
import assert from "node:assert/strict";
import { installCwdPromptVariable } from "../lib/prompt-variables.js";

function fixture(existing = {}) {
  const variables = new Map(Object.entries(existing));
  const directories = new Map();
  let activate;
  const host = {
    systemPrompt: {
      variable(name, provider) {
        if (variables.has(name)) throw new Error(`prompt variable "${name}" is already registered (for a per-agent value, register through that agent's \`agent.ctx\` instead)`);
        variables.set(name, provider);
      },
    },
    workingDirectory: {
      defaultDirectory: "D:/default",
      get(session) { return directories.get(session) ?? this.defaultDirectory; },
    },
  };
  const ctx = {
    inject(dependencies, callback) {
      assert.deepEqual(dependencies, ["systemPrompt", "workingDirectory"]);
      activate = () => callback(host);
      return "injection-disposer";
    },
  };
  assert.equal(installCwdPromptVariable(ctx), "injection-disposer");
  return { host, variables, directories, activate: () => activate() };
}

test("waits for services, then resolves each session's current directory", () => {
  const f = fixture({ provider: () => "provider", model: () => "model" });
  assert.equal(f.variables.has("cwd"), false);
  f.activate();
  const a = { session: {} };
  const b = { session: {} };
  f.directories.set(a.session, "D:/project-a");
  f.directories.set(b.session, "D:/project-b");
  const cwd = f.variables.get("cwd");
  assert.equal(cwd({ agent: a }), "D:/project-a");
  assert.equal(cwd({ agent: b }), "D:/project-b");
  f.directories.set(a.session, "D:/project-a/subdir");
  assert.equal(cwd({ agent: a }), "D:/project-a/subdir");
  assert.equal(cwd({ agent: b }), "D:/project-b");
  assert.equal(f.variables.get("provider")(), "provider");
  assert.equal(f.variables.get("model")(), "model");
});

test("uses the host default for assemblies without an agent or committed directory", () => {
  const f = fixture();
  f.activate();
  assert.equal(f.variables.get("cwd")({}), "D:/default");
  assert.equal(f.variables.get("cwd")({ agent: { session: {} } }), "D:/default");
});

test("preserves an existing host registration", () => {
  const existing = () => "D:/host-owned";
  const f = fixture({ cwd: existing });
  assert.doesNotThrow(f.activate);
  assert.equal(f.variables.get("cwd"), existing);
});

test("does not swallow unrelated registration errors", () => {
  const f = fixture();
  const error = new Error("inactive context");
  f.host.systemPrompt.variable = () => { throw error; };
  assert.throws(f.activate, (actual) => actual === error);
});
