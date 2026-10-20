import test from "node:test";
import assert from "node:assert/strict";
import { ALL_PATCHES, applyReplacementsToText } from "../lib/core.js";
import { hostPromptKeepsInject } from "../lib/host-clean.js";

/** The exact 0.2.1-rc.2 assemble() tail (tab indented, as shipped). */
const HOST_021_TAIL = [
	"\t\tconst transformed = await this.ctx.waterfall(scopeTarget(this, scope), \"system-prompt/assemble\", assembly, context, () => Promise.resolve(assembly));",
	"\t\tif (completeSection === void 0 && !runtimeContextSuppressed) return transformed;",
	"\t\tconst requiredContexts = new Set([...contextByName.values()].filter((entry) => entry.required === true).map((entry) => entry.name));",
	"\t\treturn {",
	"\t\t\t...transformed,",
	"\t\t\tsections: completeSection === void 0 ? transformed.sections : [completeSection],",
	"\t\t\tcontexts: runtimeContextSuppressed ? transformed.contexts.filter((entry) => requiredContexts.has(entry.name)) : transformed.contexts",
	"\t\t};",
].join("\n");

function hostFile(tail, { identity = true } = {}) {
	return [
		"// @deepseek-ai/dsh-system-prompt 0.2.1-rc.2 (fixture)",
		`const PERSONA_SUFFIX_SECTION = "deployment:persona-suffix";`,
		identity ? "\tthis.section({ name: \"harness:identity\", text: \"You are an AI agent powered by DeepSeek Harness.\" });" : "",
		"async function assemble(assembly, context, scope) {",
		"\tconst contextByName = new Map();",
		tail,
		"}",
	].filter(Boolean).join("\n");
}

test("patch 40 matches the 0.2.1 assemble tail and keeps required contexts", () => {
	const patch = ALL_PATCHES.find((entry) => entry.id === 40);
	assert.ok(patch, "patch 40 must exist");
	const source = hostFile(HOST_021_TAIL);
	const out = applyReplacementsToText(source, patch, "/tmp/dsh-system-prompt/lib/index.js");
	assert.equal(out.changed, true, "#40 must match 0.2.1");
	assert.equal(out.text.includes("[dsh-purge] fold-complete inject first"), true);
	assert.equal(out.text.includes("requiredContexts"), true, "required-context filtering must survive");
	assert.equal(out.text.includes("transformed.contexts.filter((entry) => requiredContexts.has(entry.name))"), true);
	assert.equal(out.text.includes("You are an AI agent powered by DeepSeek Harness."), true);
});

test("patched host passes the host-clean marker check", () => {
	const source = hostFile(HOST_021_TAIL);
	assert.equal(hostPromptKeepsInject(source), false, "pristine 0.2.1 must be reported dirty");
	const file = "/tmp/dsh-system-prompt/lib/index.js";
	let patched = source;
	for (const id of [25, 40]) {
		patched = applyReplacementsToText(patched, ALL_PATCHES.find((entry) => entry.id === id), file).text;
	}
	assert.equal(patched.includes("[dsh-purge] identity stripped"), true);
	assert.equal(patched.includes("[dsh-purge] fold-complete inject first"), true);
	assert.equal(hostPromptKeepsInject(patched), true, `patched 0.2.1 must be clean: ${patched.slice(0, 240)}`);
});

test("patch 40 is idempotent — a second pass does not double-inject", () => {
	const patch = ALL_PATCHES.find((entry) => entry.id === 40);
	const once = applyReplacementsToText(hostFile(HOST_021_TAIL), patch, "/tmp/dsh-system-prompt/lib/index.js").text;
	const twice = applyReplacementsToText(once, patch, "/tmp/dsh-system-prompt/lib/index.js").text;
	assert.equal(twice, once);
	assert.equal(/\[dsh-purge\] fold-complete inject first/.test(once), true);
});

test("0.2.0-shaped tail still matches (no regression)", () => {
	const tail = [
		"\t\tconst transformed = await this.ctx.waterfall(scopeTarget(this, scope), \"system-prompt/assemble\", assembly, context, () => Promise.resolve(assembly));",
		"\t\tif (completeSection === void 0 && !runtimeContextSuppressed) return transformed;",
		"\t\treturn {",
		"\t\t\t...transformed,",
		"\t\t\tsections: completeSection === void 0 ? transformed.sections : [completeSection],",
		"\t\t\tcontexts: runtimeContextSuppressed ? [] : transformed.contexts",
		"\t\t};",
	].join("\n");
	const out = applyReplacementsToText(hostFile(tail), ALL_PATCHES.find((entry) => entry.id === 40), "/tmp/dsh-system-prompt/lib/index.js");
	assert.equal(out.changed, true);
	assert.equal(out.text.includes("[dsh-purge]"), true);
});
