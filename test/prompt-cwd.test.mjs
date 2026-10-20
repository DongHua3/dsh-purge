import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { rewritePromptAssembly, cwdSuffixText, fillCwdPlaceholders } from "../lib/identity.js";

const root = fileURLToPath(new URL("../", import.meta.url));

/**
 * The judge: the exact interpolation contract of @deepseek-ai/dsh-system-prompt
 * (0.2.1-rc.2). It registers only `provider` and `model`; an unknown `{{name}}`
 * reference throws before any model request is sent. Anything the plugin leaves
 * in a section must survive this function.
 */
function renderPrompt(assembly, variables = { provider: "deepseek", model: "v4" }) {
	return assembly.sections
		.map((section) => (section.interpolate === false ? section.text : interpolate(section, variables)))
		.filter((text) => text.length > 0)
		.join("\n\n");
}

function interpolate(input, variables) {
	const text = String(input.text ?? "");
	let result = "";
	let last = 0;
	for (let open = text.indexOf("{{"); open >= 0; open = text.indexOf("{{", last)) {
		const close = text.indexOf("}}", open + 2);
		const name = close >= 0 ? text.slice(open + 2, close) : "";
		if (close < 0 || name.includes("{")) {
			result += text.slice(last, open + 2);
			last = open + 2;
			continue;
		}
		if (!Object.hasOwn(variables, name)) {
			throw new Error(`unknown prompt variable "{{${name}}}" in section "${input.name}"; registered variables: ${Object.keys(variables).join(", ")}`);
		}
		result += text.slice(last, open) + variables[name];
		last = close + 2;
	}
	return result + text.slice(last);
}

const context = { agent: { session: { header: { cwd: "/work/project" } } } };
const cwdContext = [{ name: "working-directory:current", text: "/work/project" }];

function assembly(sections, contexts = []) {
	return { sections, contexts, tools: [], variables: {} };
}

function rewrite(sections, contexts = [], opts = {}) {
	return rewritePromptAssembly(assembly(sections, contexts), "", { context, capabilityProtocol: true, ...opts });
}

test("legacy cwd-only suffix renders with the real path", () => {
	const out = rewrite([{ name: "deployment:persona-suffix", text: "Your working directory is {{cwd}}." }], cwdContext);
	const text = renderPrompt(out);
	assert.equal(text.includes("{{cwd}}"), false);
	assert.equal(text.startsWith("Your working directory is /work/project."), false, "host already supplies working-directory context, the suffix must not repeat it");
	assert.equal(text.includes("## Capability selection by task"), true, "capability protocol still renders");
});

test("long legacy identity line is neutralized without emitting {{cwd}}", () => {
	const out = rewrite([{
		name: "deployment:persona-prefix",
		text: "You are a coding agent powered by the {{model}} model, running on the DeepSeek Harness. Your working directory is {{cwd}}.",
	}], cwdContext);
	const text = renderPrompt(out);
	assert.equal(text.includes("{{cwd}}"), false);
	assert.equal(text.includes("DeepSeek Harness agent"), false);
});

test("empty and missing suffix both render without a duplicated cwd line", () => {
	for (const sections of [
		[{ name: "deployment:persona-prefix", text: "" }, { name: "deployment:persona-suffix", text: "" }],
		[{ name: "deployment:persona-prefix", text: "" }],
	]) {
		const text = renderPrompt(rewrite(sections, cwdContext));
		assert.equal(text.includes("{{cwd}}"), false);
		const cwdLines = text.split("\n").filter((line) => line.startsWith("Your working directory is"));
		assert.equal(cwdLines.length, 0);
	}
});

test("0.2.0 host without working-directory context still gets a cwd sentence", () => {
	const text = renderPrompt(rewrite([{ name: "deployment:persona-suffix", text: "" }], []));
	assert.equal(text.includes("{{cwd}}"), false);
	assert.equal(text.startsWith("Your working directory is /work/project."), true);
});

test("user-written multi-sentence suffix is preserved", () => {
	const suffix = "Be terse. Report findings in tables.";
	const text = renderPrompt(rewrite([{ name: "deployment:persona-suffix", text: suffix }], cwdContext));
	assert.equal(text.startsWith(suffix), true);
});

test("leftover {{cwd}} in plugin sections is filled with the real path", () => {
	const out = rewrite([{ name: "dsh-purge", text: "inject mentions {{cwd}} once", interpolate: false }], cwdContext);
	assert.equal(out.sections.some((section) => String(section.text).includes("{{cwd}}")), false);
	assert.equal(renderPrompt(out).includes("/work/project"), true);
});

test("unrelated unknown variables still throw — the judge is not neutered", () => {
	const out = rewrite([{ name: "dsh-purge:post", text: "leaked {{nope}} here" }], cwdContext);
	assert.throws(() => renderPrompt(out), /unknown prompt variable "\{\{nope\}\}"/);
});

test("helper units", () => {
	assert.equal(cwdSuffixText("/x"), "Your working directory is /x.");
	assert.equal(cwdSuffixText(""), "");
	assert.deepEqual(
		fillCwdPlaceholders([{ name: "a", text: "{{cwd}}/b" }], "/r"),
		[{ name: "a", text: "/r/b" }],
	);
});

test("shipped bundle patch never writes an interpolated persona suffix", () => {
	const yml = readFileSync(new URL("../cordis.patch.yml", import.meta.url), "utf8")
		.split("\n")
		.filter((line) => !line.trim().startsWith("#"))
		.join("\n");
	assert.equal(/personaSuffix\s*:.*\{\{cwd\}\}/.test(yml), false);
	assert.equal(/personaSuffix\s*:\s*Your working directory is \{\{cwd\}\}\./.test(yml), false);
});

test("only legacy fingerprints and pattern sources may mention {{cwd}}", () => {
	// The constant is kept for recognising old text; nothing may emit it.
	const identity = readFileSync(new URL("../lib/identity.js", import.meta.url), "utf8");
	assert.equal(identity.includes('LEGACY_CWD_ONLY_SUFFIX = "Your working directory is {{cwd}}."'), true);
	assert.equal(identity.includes('"Working directory: {{cwd}}. "'), false, "identity.js must not write {{cwd}} back into a section");
});
