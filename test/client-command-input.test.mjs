import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const clientPath = fileURLToPath(new URL("../client.js", import.meta.url));
const manifestPath = fileURLToPath(new URL("../package.json", import.meta.url));

// Exercise the shipped client factory without a DOM, a model, or network access.
function loadClient() {
	let client;
	const definitions = [];
	const slots = [];
	const react = {
		Component: class {},
		createElement: (type, props, ...children) => ({ type, props, children }),
	};
	const window = {
		__ModuleLoader__: {
			load: ({ factory }) => {
				client = factory((name) => {
					assert.equal(name, "react", `unexpected client import: ${name}`);
					return react;
				});
			},
		},
	};
	vm.runInNewContext(readFileSync(clientPath, "utf8"), {
		window, console, URL, AbortController,
		setTimeout, clearTimeout, setInterval, clearInterval,
		fetch: async () => ({
			ok: true,
			json: async () => ({ ok: true, granted: false }),
		}),
	}, { filename: "dsh-purge/client.js" });
	client.apply({
		effect() {},
		inject() {},
		locale: { bind: () => (key) => key },
		uiConversation: { events: { register: (definition) => definitions.push(definition) } },
		slots: {
			inject: (_name, install) => install(),
			register: (definition, render) => {
				slots.push({ definition, render });
				return () => {};
			},
		},
	});
	return { client, definitions, slots };
}

test("declares the conversation dependency and registers the input contribution", () => {
	const { client, definitions, slots } = loadClient();
	const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
	assert.ok(client.inject.includes("uiConversation"));
	assert.ok(manifest.dsh.client.inject.includes("@deepseek-ai/dsh-client-ui-conversation"));
	assert.ok(definitions.some((definition) => definition.kind === "dsh-purge-command-input"));
	assert.ok(slots.some(({ definition }) => definition.key === "dsh-purge-command-input"));
});

test("projects a purge run as visible chat activity before its result", () => {
	const { definitions } = loadClient();
	const definition = definitions.find((entry) => entry.kind === "dsh-purge-command-input");
	assert.ok(definition, "missing purge input projection");
	const event = {
		type: "command/run", seq: 14, time: 123456,
		data: { commandId: "command-1", name: "purge", args: " status ", source: { kind: "user" } },
	};
	const match = { event, ...definition.match(event) };
	assert.equal(match.id, "command-1");
	const state = definition.start({}, match);
	const node = definition.buildViewNode({
		key: "context-1", id: "command-1", state,
		start: { location: { kind: "unresolved" } },
	});
	assert.equal(node.target, "chat");
	assert.equal(node.visibility, "visible");
	assert.notEqual(node.kind, "command", "generic command rows do not activate an empty host chat");
	assert.equal(node.key, "context-1");
	assert.equal(node.data.text, "/purge status");
	assert.equal(node.data.commandId, "command-1");
	assert.equal(node.data.time, event.time);
	assert.ok(node.anchorSeq < event.seq);
	assert.equal(definition.buildViewNode({ state: undefined }), null);
	assert.equal(definition.match({ ...event, data: { ...event.data, name: "goal" } }), null);
	assert.equal(definition.match({ ...event, type: "command/done" }), null);
});

test("renders command input as literal text", () => {
	const { slots } = loadClient();
	const slot = slots.find(({ definition }) => definition.key === "dsh-purge-command-input");
	assert.ok(slot, "missing purge input renderer");
	const text = "/purge status <tag>";
	const tree = slot.render({ node: { data: { text } } });
	assert.equal(tree.props.role, "group");
	assert.equal(tree.children[0].children[0], text);
	assert.equal(JSON.stringify(tree).includes("dangerouslySetInnerHTML"), false);
});
