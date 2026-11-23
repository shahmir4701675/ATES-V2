import { spawn } from "node:child_process";
import { randomBytes, randomUUID } from "node:crypto";
import { resolve } from "node:path";
import { createServer } from "node:net";
import { pathToFileURL } from "node:url";

const source = resolve(".ates/postgres/node_modules/embedded-postgres/dist/index.js");
const {default: EmbeddedPostgres} = await import(pathToFileURL(source).href);
const listener = createServer();
await new Promise((ready) => listener.listen(0, "127.0.0.1", ready));
const port = listener.address().port;
await new Promise((closed) => listener.close(closed));
const password = randomBytes(24).toString("hex");
const name = "ates_disposable_gate";
const pg = new EmbeddedPostgres({
  databaseDir: resolve(".ates/postgres/cluster-" + randomUUID()),
  port, user: "postgres", password, authMethod: "scram-sha-256",
  initdbFlags: ["--encoding=UTF8", "--no-sync"],
  postgresFlags: ["-c", "listen_addresses=127.0.0.1"],
  onLog: () => {},
});
await pg.initialise();
await pg.start();
try {
  await pg.createDatabase(name);
  const client = pg.getPgClient(name);
  await client.connect();
  const info = await client.query("SELECT version()");
  console.log(info.rows[0].version);
  await client.end();
  const interpreter = process.env.ATES_TEST_PYTHON ||
    resolve(process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python");
  const args = process.argv.includes("--reference-http") ?
    ["-c", "import runpy, sys; sys.path.insert(0, 'tests'); runpy.run_path('tests/reference_http.py', run_name='__main__')"] :
    ["-m", "pytest", "-q", "-s", "--tb=short", "tests/test_schema.py", "-k", "postgres"];
  const child = spawn(interpreter, args, {
    stdio: "inherit",
    env: {...process.env, ATES_TEST_DATABASE_URL: "postgresql+psycopg://postgres:" +
      password + "@127.0.0.1:" + port + "/" + name},
  });
  process.exitCode = await new Promise((finish, reject) => { child.on("exit", finish); child.on("error", reject); });
} finally {
  await pg.stop();
}

