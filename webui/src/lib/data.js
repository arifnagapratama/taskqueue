export function createDemoData() {
  var S = {
      in_progress: "In progress",
      todo: "Todo",
      finished: "Finished",
    },
    ORDER = ["in_progress", "todo", "finished"];
  function p2(n) {
    return (n < 10 ? "0" : "") + n;
  }
  function fmt(t, sec) {
    var d = new Date(t);
    return (
      d.getFullYear() +
      "-" +
      p2(d.getMonth() + 1) +
      "-" +
      p2(d.getDate()) +
      " " +
      p2(d.getHours()) +
      ":" +
      p2(d.getMinutes()) +
      (sec ? ":" + p2(d.getSeconds()) : "")
    );
  }
  function ago(h) {
    return Date.now() - h * 36e5;
  }
  function at(id, t, st, mode, ref, steps, run) {
    return {
      id: id,
      t: t,
      st: st,
      mode: mode,
      ref: ref,
      steps: steps,
      run: run,
    };
  }
  var T = [
    {
      id: "TASK-12",
      epic: "EPIC-03",
      adrs: ["ADR-004"],
      bl: [],
      t: "OIDC login with Keycloak",
      s: "in_progress",
      l: ["auth", "backend"],
      u: ago(1),
      ai: {
        agent: "ai-agent",
        since: ago(6),
        step: "Fixing silent token refresh",
      },
      d: "Users sign in through Keycloak. Tokens are kept in an httpOnly cookie and refreshed automatically.",
      ac: [
        at(
          "AT-1",
          "Sign-in redirect round trip",
          "pass",
          "auto",
          "tests/e2e/auth/login.spec.ts",
          [
            "Given an unauthenticated user",
            "When they open /app",
            "Then they are redirected to Keycloak",
            "And they return with an authorization code after login",
          ],
          ago(5),
        ),
        at(
          "AT-2",
          "Session cookie flags",
          "pass",
          "auto",
          "tests/api/auth/test_cookie.py::test_flags",
          [
            "Given a signed-in user",
            "When the session cookie is issued",
            "Then it is httpOnly and SameSite=Lax",
          ],
          ago(2),
        ),
        at(
          "AT-3",
          "Silent token refresh",
          "fail",
          "auto",
          "tests/e2e/auth/refresh.spec.ts",
          [
            "Given a session whose access token expires in 30s",
            "When the user keeps using the app",
            "Then the token is refreshed before expiry",
            "And no request returns 401",
          ],
          ago(1),
        ),
        at(
          "AT-4",
          "Logout revokes Keycloak session",
          "pending",
          "manual",
          "",
          [
            "Given a signed-in user",
            "When they click Logout",
            "Then the Keycloak session is revoked",
            "And the old refresh token is rejected",
          ],
          null,
        ),
      ],
      log: [
        [ago(1), "agent", "test AT-3 failed"],
        [ago(2), "agent", "test AT-2 passed"],
        [ago(5), "agent", "test AT-1 passed"],
        [ago(6), "arif", "ai assigned (ai-agent)"],
        [ago(26), "arif", "status → in_progress"],
        [ago(120), "arif", "priority raised"],
        [ago(168), "arif", "created"],
      ],
    },
    {
      id: "TASK-15",
      epic: "EPIC-04",
      adrs: ["ADR-007"],
      bl: [],
      t: "Cluster list endpoint with pagination",
      s: "in_progress",
      l: ["api"],
      u: ago(20),
      d: "GET /clusters supports cursor pagination and status filter.",
      ac: [
        at(
          "AT-1",
          "Cursor pagination",
          "pass",
          "auto",
          "tests/api/clusters/test_paging.py",
          [
            "Given 120 clusters exist",
            "When GET /clusters?limit=50 is called",
            "Then 50 items and a next_cursor are returned",
            "And following the cursor returns the remaining 70",
          ],
          ago(20),
        ),
        at(
          "AT-2",
          "Status filter",
          "pending",
          "auto",
          "",
          [
            "Given clusters in mixed states",
            "When GET /clusters?status=ready is called",
            "Then only ready clusters are returned",
          ],
          null,
        ),
      ],
      log: [
        [ago(20), "agent", "test AT-1 passed"],
        [ago(30), "agent", "status → in_progress"],
        [ago(100), "arif", "created"],
      ],
    },
    {
      id: "TASK-18",
      epic: "EPIC-04",
      adrs: ["ADR-008"],
      bl: ["ADR-008"],
      t: "Node detail panel (CPU, memory, conditions)",
      s: "todo",
      l: ["ui"],
      u: ago(72),
      d: "Show node metrics in the side dialog on the cluster page.",
      ac: [
        at(
          "AT-1",
          "Metrics window",
          "pending",
          "manual",
          "",
          [
            "Given a node with 1h of metrics",
            "When the node panel opens",
            "Then CPU and memory charts cover the last hour",
          ],
          null,
        ),
        at(
          "AT-2",
          "Condition badge",
          "pending",
          "auto",
          "tests/ui/node-badge.spec.ts",
          [
            "Given a NotReady node",
            "When the panel opens",
            "Then a red NotReady badge is shown",
          ],
          null,
        ),
      ],
      log: [[ago(72), "arif", "created"]],
    },
    {
      id: "TASK-19",
      epic: "EPIC-05",
      adrs: ["ADR-005"],
      bl: [],
      t: "Audit log for configuration changes",
      s: "todo",
      l: ["backend", "security"],
      u: ago(70),
      d: "Record who changed what and when, with old and new values.",
      ac: [
        at(
          "AT-1",
          "Append-only audit table",
          "pending",
          "auto",
          "",
          [
            "Given an existing audit row",
            "When an UPDATE or DELETE is attempted",
            "Then the database rejects it",
          ],
          null,
        ),
        at(
          "AT-2",
          "Read with user filter",
          "pending",
          "auto",
          "",
          [
            "Given changes by two users",
            "When GET /audit?user=a is called",
            "Then only changes by a are returned",
          ],
          null,
        ),
        at(
          "AT-3",
          "Configurable retention",
          "pending",
          "manual",
          "",
          [
            "Given retention set to 30 days",
            "When the cleanup job runs",
            "Then older rows are archived",
          ],
          null,
        ),
      ],
      log: [[ago(70), "arif", "created"]],
    },
    {
      id: "TASK-21",
      epic: "EPIC-04",
      adrs: [],
      bl: [],
      t: "Export configuration as YAML",
      s: "todo",
      l: ["api"],
      u: ago(96),
      d: "Export a cluster configuration as re-appliable YAML.",
      ac: [
        at(
          "AT-1",
          "Export a single cluster",
          "pending",
          "auto",
          "",
          [
            "Given a configured cluster",
            "When the export is requested",
            "Then valid YAML is returned",
          ],
          null,
        ),
        at(
          "AT-2",
          "Schema validation",
          "pending",
          "auto",
          "",
          [
            "Given an invalid configuration",
            "When the export is requested",
            "Then a validation error lists the fields",
          ],
          null,
        ),
      ],
      log: [[ago(96), "arif", "created"]],
    },
    {
      id: "TASK-22",
      epic: "",
      adrs: [],
      bl: [],
      t: "Dark mode",
      s: "todo",
      l: ["ui"],
      u: ago(120),
      d: "Follow the system preference; allow manual override.",
      ac: [
        at(
          "AT-1",
          "Theme follows system",
          "pending",
          "manual",
          "",
          [
            "Given the OS is set to dark",
            "When the app loads",
            "Then dark tokens are applied",
          ],
          null,
        ),
      ],
      log: [[ago(120), "arif", "created"]],
    },
    {
      id: "TASK-07",
      epic: "EPIC-01",
      adrs: ["ADR-001"],
      bl: [],
      t: "Initial database schema and migrations",
      s: "finished",
      l: ["backend"],
      u: ago(170),
      d: "Core schema managed with Alembic.",
      ac: [
        at(
          "AT-1",
          "Core tables exist",
          "pass",
          "auto",
          "tests/db/test_schema.py",
          [
            "Given a fresh database",
            "When migrations run",
            "Then cluster, node and user tables exist",
          ],
          ago(172),
        ),
        at(
          "AT-2",
          "Down migration",
          "pass",
          "auto",
          "tests/db/test_downgrade.py",
          [
            "Given a migrated database",
            "When migrations are reverted",
            "Then the schema returns to empty",
          ],
          ago(171),
        ),
      ],
      log: [
        [ago(170), "agent", "status → finished"],
        [ago(200), "arif", "created"],
      ],
    },
    {
      id: "TASK-09",
      epic: "EPIC-01",
      adrs: [],
      bl: [],
      t: "CI pipeline: lint, test, build image",
      s: "finished",
      l: ["devops"],
      u: ago(175),
      d: "Pipeline runs on every PR.",
      ac: [
        at(
          "AT-1",
          "Lint and type check",
          "pass",
          "auto",
          ".github/workflows/ci.yml#lint",
          [
            "Given a pull request",
            "When CI runs",
            "Then lint and type checks pass",
          ],
          ago(176),
        ),
        at(
          "AT-2",
          "Unit tests",
          "pass",
          "auto",
          ".github/workflows/ci.yml#test",
          ["Given a pull request", "When CI runs", "Then unit tests pass"],
          ago(176),
        ),
        at(
          "AT-3",
          "Image build and push",
          "pass",
          "auto",
          ".github/workflows/ci.yml#image",
          [
            "Given a merge to main",
            "When CI runs",
            "Then the image is pushed to the registry",
          ],
          ago(175),
        ),
      ],
      log: [
        [ago(175), "arif", "status → finished"],
        [ago(210), "arif", "created"],
      ],
    },
  ];

  function steps(a) {
    return a.steps
      .map(function (l) {
        var m = l.match(/^(Given|When|Then|And|But)\s+(.*)$/i),
          k = m ? m[1][0].toUpperCase() + m[1].slice(1).toLowerCase() : "And";
        return (
          '<li><b class="kw k-' +
          k.toLowerCase() +
          '">' +
          k +
          "</b> " +
          esc(m ? m[2] : l) +
          "</li>"
        );
      })
      .join("");
  }
  function atCard(a, i) {
    var o = a.open === undefined ? a.st === "fail" : a.open,
      ic = { pass: "✓", fail: "✕", pending: "○" }[a.st];
    return (
      '<div class="at at-' +
      a.st +
      '"><div class="ath" data-t="' +
      i +
      '" tabindex="0" role="button" aria-expanded="' +
      o +
      '"><i class="ico">' +
      ic +
      '</i><span class="mono lbl">' +
      a.id +
      '</span><span class="ti">' +
      esc(a.t) +
      '</span><span class="mode">' +
      a.mode +
      '</span></div><div class="atb"' +
      (o ? "" : " hidden") +
      '><ol class="gh">' +
      steps(a) +
      '</ol><div class="atm mono"><span>' +
      (a.ref ? esc(a.ref) : "no automation linked") +
      "</span><span>" +
      (a.run ? "last run " + fmt(a.run) : "never run") +
      '</span></div><div class="ata"><button class="btn" data-p="' +
      i +
      '">Pass</button><button class="btn" data-fl="' +
      i +
      '">Fail</button><button class="btn" data-z="' +
      i +
      '">Reset</button><button class="rm" data-r="' +
      i +
      '" aria-label="Remove test" title="Remove">✕</button></div></div></div>'
    );
  }
  var sel = null,
    view = "specs",
    grp = "stage",
    kf = "all",
    flt = "all",
    q = "",
    collapsed = {},
    n = 23,
    OP = { ac: true, hist: false },
    adding = false,
    lastId = null;
  var $ = function (i) {
    return document.getElementById(i);
  };
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  var E = [
    {
      id: "EPIC-01",
      t: "Platform foundation",
      s: "CLOSED",
      u: ago(168),
      d: "Database, migrations and CI so every later feature ships on a tested base.",
    },
    {
      id: "EPIC-03",
      t: "Authentication and access",
      s: "OPEN",
      u: ago(1),
      d: "Single sign-on through Keycloak with secure session handling.",
    },
    {
      id: "EPIC-04",
      t: "Cluster inventory and observability",
      s: "OPEN",
      u: ago(20),
      d: "List, inspect and export clusters and nodes.",
    },
    {
      id: "EPIC-05",
      t: "Security and audit",
      s: "OPEN",
      u: ago(70),
      d: "Traceability for every configuration change.",
    },
  ];
  var A = [
    {
      id: "ADR-001",
      t: "Use PostgreSQL as the primary store",
      s: "ACCEPTED",
      u: ago(400),
      ctx: "The platform needs relational integrity, transactional migrations and mature tooling.",
      dec: "Use PostgreSQL with Alembic migrations.",
      cons: "Operational dependency on Postgres; JSON columns cover semi-structured configuration.",
      sup: "",
    },
    {
      id: "ADR-002",
      t: "Server-side session store",
      s: "SUPERSEDED",
      u: ago(380),
      ctx: "Sessions were initially kept server-side in a shared cache.",
      dec: "Keep session state in Redis keyed by a random session id.",
      cons: "Adds a stateful dependency and complicates horizontal scaling.",
      sup: "",
    },
    {
      id: "ADR-004",
      t: "Use Keycloak as the OIDC provider",
      s: "ACCEPTED",
      u: ago(200),
      ctx: "Users already exist in Keycloak; a separate identity store duplicates operations.",
      dec: "Delegate authentication to Keycloak (authorization code flow) and keep tokens in httpOnly cookies.",
      cons: "Hard dependency on Keycloak availability; refresh and logout must be coordinated with it.",
      sup: "ADR-002",
    },
    {
      id: "ADR-005",
      t: "Append-only audit log in the primary database",
      s: "ACCEPTED",
      u: ago(150),
      ctx: "Auditors need a tamper-evident history of configuration changes.",
      dec: "Write audit rows to an append-only table enforced by database permissions.",
      cons: "Table growth needs a retention job; no cross-database tamper evidence.",
      sup: "",
    },
    {
      id: "ADR-007",
      t: "Cursor pagination for list endpoints",
      s: "ACCEPTED",
      u: ago(110),
      ctx: "Offset pagination degrades and drifts on large, changing lists.",
      dec: "All list endpoints use opaque cursors with a limit parameter.",
      cons: "No random page access; clients must follow cursors.",
      sup: "",
    },
    {
      id: "ADR-008",
      t: "Metrics source for the node panel",
      s: "PROPOSED",
      u: ago(30),
      ctx: "The node panel needs CPU and memory history. Options: metrics-server (no history) or Prometheus.",
      dec: "Pending. Leaning towards Prometheus queries through a backend proxy.",
      cons: "Prometheus adds a dependency but supplies history and conditions.",
      sup: "",
    },
  ];
  return { specs: T, epics: E, adrs: A };
}
