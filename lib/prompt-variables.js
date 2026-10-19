/** Register the variable used by cordis.patch.yml without blocking other services. */
export function installCwdPromptVariable(ctx) {
  return ctx.inject(["systemPrompt", "workingDirectory"], (host) => {
    try {
      host.systemPrompt.variable("cwd", ({ agent }) => agent
        ? host.workingDirectory.get(agent.session)
        : host.workingDirectory.defaultDirectory);
    } catch (error) {
      // Older hosts (or another plugin) may already own this variable.
      if (!/^prompt variable "cwd" is already registered(?: \(| in this scope$|$)/.test(String(error?.message || ""))) {
        throw error;
      }
    }
  });
}
