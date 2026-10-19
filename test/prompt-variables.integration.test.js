import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { installCwdPromptVariable } from "../lib/prompt-variables.js";

// Point DSH_TEST_AI_BASE at an installed runtime's node_modules/@deepseek-ai.
test("renders the unchanged suffix with real host services and disposes registration", {
  skip: !process.env.DSH_TEST_AI_BASE && "set DSH_TEST_AI_BASE to run against an installed DSH runtime",
}, async () => {
  const load = (name) => import(pathToFileURL(path.join(process.env.DSH_TEST_AI_BASE, name, "lib/index.js")).href);
  const { Context } = await load("cordis");
  const { SystemPrompt, renderPrompt } = await load("dsh-system-prompt");
  const { WorkingDirectoryService } = await load("dsh-working-directory");
  const ctx = new Context();
  new SystemPrompt(ctx, { personaSuffix: "Your working directory is {{cwd}}." });
  const defaultDirectory = path.resolve("test-default");
  const directories = new Map();
  ctx.provide("sessionProjections", { register() {}, stateOf(session) { return directories.get(session) ?? null; } });
  ctx.provide("fs", { async resolve(p) { return p; }, async stat() { return { type: "directory" }; } });
  new WorkingDirectoryService(ctx, { defaultDirectory });
  assert.throws(() => renderPrompt({ sections: [{ name: "deployment:persona-suffix", text: "Your working directory is {{cwd}}." }], variables: {} }), /unknown prompt variable/);

  const fiber = installCwdPromptVariable(ctx);
  await fiber;
  try {
    const a = { session: { header: {}, append() {} }, ctx };
    const b = { session: { header: {}, append() {} }, ctx };
    directories.set(a.session, path.resolve("project-a"));
    directories.set(b.session, path.resolve("project-b"));
    for (const agent of [a, b]) {
      const assembly = await ctx.systemPrompt.assemble({ agent });
      assert.equal(assembly.variables.cwd, directories.get(agent.session));
      assert(renderPrompt(assembly).includes(directories.get(agent.session)));
    }
    directories.set(a.session, path.resolve("project-a/subdir"));
    assert.equal((await ctx.systemPrompt.assemble({ agent: a })).variables.cwd, directories.get(a.session));
    assert.equal((await ctx.systemPrompt.assemble({ agent: b })).variables.cwd, directories.get(b.session));
    assert.equal((await ctx.systemPrompt.assemble()).variables.cwd, defaultDirectory);
  } finally {
    await fiber.dispose();
  }
  assert.equal(Object.hasOwn((await ctx.systemPrompt.assemble()).variables, "cwd"), false);
  ctx.systemPrompt.variable("cwd", () => "host-owned");
  const reuse = installCwdPromptVariable(ctx);
  await reuse;
  assert.equal((await ctx.systemPrompt.assemble()).variables.cwd, "host-owned");
  await reuse.dispose();
  assert.equal((await ctx.systemPrompt.assemble()).variables.cwd, "host-owned");
});
