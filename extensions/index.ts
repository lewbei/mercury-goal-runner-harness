/**
 * Mercury Goal Runner — Pi Extension
 *
 * Registers a /goal-run slash command and tools that call the Python
 * deterministic certifier, orchestrator, and validators via subprocess.
 *
 * Pi orchestrates. Mercury executes. Policy decides. Certifier writes final status.
 */

import { spawnSync } from "node:child_process";
import * as path from "node:path";
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";

/** Repository root — where Python scripts live relative to this extension. */
function repoRoot(): string {
  // extension/index.ts → repo root (two levels up)
  return path.resolve(__dirname, "..", "..");
}

function python(cwd: string, script: string, args: string[]): { code: number; stdout: string } {
  const result = spawnSync("python", [script, ...args], {
    cwd,
    encoding: "utf-8",
    timeout: 30_000,
    maxBuffer: 1024 * 1024,
  });
  return { code: result.status ?? 1, stdout: (result.stdout || "") + (result.stderr || "") };
}

export default function (pi: ExtensionAPI) {
  const root = repoRoot();

  // ── Command: /goal-run ──────────────────────────────────────────
  pi.registerCommand("goal-run", {
    description: "Start the QRSPI goal execution pipeline",
    action: async (_args: string) => {
      return {
        content: [{
          type: "text",
          text: [
            "# QRSPI Goal Runner Pipeline",
            "",
            "To run a goal through the harness:",
            "",
            "1. Create a goal contract at `.agentic-runs/<run_id>/goal_contract.json`",
            "2. Spawn `planner-minimal` agent to design the solution",
            "3. Spawn `guarded-worker` agent to implement",
            "4. Spawn `verifier-generator` agent to produce evidence",
            "5. Run `harness_orchestrate` tool for deterministic phases",
            "6. Run `harness_certify` tool for final status",
            "",
            "Agents available: planner-minimal, planner-robust, guarded-worker, verifier-generator",
            "Skills loaded: question-contract, research-pack, design-options, structure-outline, root-plan",
          ].join("\n"),
        }],
      };
    },
  });

  // ── Tool: certify_run ──────────────────────────────────────────────
  pi.registerTool({
    name: "harness_certify",
    label: "Certify Run",
    description:
      "Run the deterministic certifier on a run folder. Returns CERTIFIED_DONE, PROVISIONAL_DONE, or NOT_DONE with confidence score.",
    parameters: Type.Object({
      run_id: Type.String({ description: "Run identifier (folder under .agentic-runs/)" }),
    }),
    async execute(_id, params) {
      const script = path.join(root, ".agentic-pi", "validators", "certify_run.py");
      const runDir = path.join(root, ".agentic-runs", params.run_id);
      const { code, stdout } = python(root, script, [runDir]);

      // Read final_status.json for structured result
      let status = "UNKNOWN";
      let confidence = 0;
      try {
        const fs = require("node:fs");
        const finalStatus = JSON.parse(
          fs.readFileSync(path.join(runDir, "final_status.json"), "utf-8")
        );
        status = finalStatus.status;
        confidence = finalStatus.confidence_score ?? 0;
      } catch {}

      return {
        content: [
          {
            type: "text",
            text: `${status} (confidence: ${confidence.toFixed(2)})\n${stdout.slice(-500)}`,
          },
        ],
        details: { status, confidence, run_id: params.run_id },
      };
    },
  });

  // ── Tool: orchestrate ──────────────────────────────────────────────
  pi.registerTool({
    name: "harness_orchestrate",
    label: "Orchestrate Pipeline",
    description:
      "Run deterministic pipeline phases: artifact routing, formal verification, signing, certification.",
    parameters: Type.Object({
      run_id: Type.String({ description: "Run identifier" }),
    }),
    async execute(_id, params) {
      const script = path.join(root, ".agentic-pi", "runtime", "orchestrate_pipeline.py");
      const { code, stdout } = python(root, script, ["--run-id", params.run_id]);

      const success = code === 0;
      return {
        content: [
          {
            type: "text",
            text: success
              ? `Pipeline completed.\n${stdout.slice(-1000)}`
              : `Pipeline failed (code ${code}).\n${stdout.slice(-1000)}`,
          },
        ],
        details: { success, run_id: params.run_id, exit_code: code },
        isError: !success,
      };
    },
  });

  // ── Tool: validate_schema ──────────────────────────────────────────
  pi.registerTool({
    name: "harness_validate_schema",
    label: "Validate Schema",
    description: "Validate a JSON file against a harness schema.",
    parameters: Type.Object({
      schema: Type.String({ description: "Schema file path (e.g., .agentic-pi/schemas/goal_contract.schema.json)" }),
      target: Type.String({ description: "Target JSON file to validate" }),
    }),
    async execute(_id, params) {
      const script = path.join(root, ".agentic-pi", "validators", "validate_schema.py");
      const schemaPath = path.join(root, params.schema);
      const targetPath = path.join(root, params.target);
      const { code, stdout } = python(root, script, [schemaPath, targetPath]);

      return {
        content: [
          { type: "text", text: stdout.slice(-1000) || "Validation passed" },
        ],
        details: { valid: code === 0 },
        isError: code !== 0,
      };
    },
  });

  console.log("[mercury-goal-runner] Extension loaded — /goal-run available");
}
