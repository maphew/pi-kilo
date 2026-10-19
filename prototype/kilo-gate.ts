/** Kilo-side permission gate: every tool call requires confirm().
 * Deny -> {block:true}; enforcement stays in Pi. Auto-responds over RPC
 * via extension_ui_request/extension_ui_response. Default DENY for
 * write/exec tools, ALLOW for read-only (configurable via env).
 */
export default function (pi) {
  const denyByDefault = (process.env.PI_GATE_DENY ?? "write,bash,edit").split(",");
  pi.on("tool_call", async (event, ctx) => {
    const name = event.toolName ?? "";
    const isWrite = denyByDefault.some((p) => name.includes(p.trim()));
    const ok = await ctx.ui.confirm(
      isWrite ? "Block tool call?" : "Allow tool call?",
      `${name}: ${JSON.stringify(event.input).slice(0, 300)}`,
    );
    // When Kilo drives us, the adapter auto-answers: deny writes, allow reads.
    // Interactive use still gets a real prompt.
    if (!ok) return { block: true, reason: `${name} denied by kilo-gate` };
  });
}
