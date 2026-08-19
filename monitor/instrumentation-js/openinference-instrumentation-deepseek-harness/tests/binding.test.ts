import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import type { ToolDefinition } from "@deepseek-ai/dsh-tools";

import { installA2EBindingTools } from "../src/binding.js";

test("binding config registers a native Harness tool and forwards execution", async () => {
  const requests: unknown[] = [];
  const server = createServer((request, response) => {
    const chunks: Buffer[] = [];
    request.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
    request.on("end", () => {
      assert.equal(request.headers.authorization, "Bearer secret");
      requests.push(JSON.parse(Buffer.concat(chunks).toString("utf8")));
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ result: { answer: 5 } }));
    });
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  assert(address && typeof address !== "string");

  const directory = mkdtempSync(join(tmpdir(), "a2e-deepseek-binding-"));
  const configPath = join(directory, "binding.json");
  writeFileSync(configPath, JSON.stringify({
    endpoint: `http://127.0.0.1:${address.port}/tool`,
    token: "secret",
    tools: [{
      name: "add_offset",
      description: "Add an offset",
      parameters: {
        type: "object",
        properties: { value: { type: "integer" } },
        required: ["value"],
      },
    }],
  }));

  let definition: ToolDefinition | undefined;
  try {
    assert.equal(installA2EBindingTools({
      register(value) {
        definition = value;
        return () => undefined;
      },
    }, configPath), 1);
    assert.equal(definition?.name, "add_offset");
    const result = await definition!.execute(
      { value: 3 },
      { signal: new AbortController().signal } as never,
    );
    assert.deepEqual(result, { answer: 5 });
    assert.deepEqual(requests, [{ name: "add_offset", arguments: { value: 3 } }]);
  } finally {
    await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    rmSync(directory, { recursive: true, force: true });
  }
});

test("binding tools are disabled when no config path is present", () => {
  assert.equal(installA2EBindingTools({ register: () => { throw new Error("unexpected"); } }, undefined), 0);
});
