# 📊 Features & Tool Categories

## Feature Comparison

Comparison against the most prominent public DolphinScheduler MCP server: [ocean-zhc/dolphinscheduler-mcp](https://github.com/ocean-zhc/dolphinscheduler-mcp) (community-built, FastMCP-based, auto-generated from DS REST API).

| Capability | dolphin-mcp-pilot | ocean-zhc/dolphinscheduler-mcp |
|---|:---:|:---:|
| **Tool count** | **53+** (manually curated) | 30+ (auto-generated from REST API) |
| Create project | ✅ | ✅ |
| Create SQL workflow | ✅ | ❌ (no process_definition tools) |
| Create DAG workflow | ✅ | ❌ |
| Update workflow | ✅ | ❌ |
| Clone workflow | ✅ | ❌ |
| Workflow version rollback | ✅ | ❌ |
| **Schedule management** | ✅ 6 tools | ❌ (no schedule tools) |
| Pause/Resume/Rerun instances | ✅ | ❌ (no process_instance tools) |
| Task logs | ✅ | ❌ |
| Force success / skip task | ✅ | ❌ |
| Resource content update | ✅ | ❌ (no resource tools) |
| **Multi-tenant auth** | ✅ (per-request token/user) | ❌ (single `DOLPHINSCHEDULER_API_KEY`) |
| Raw API passthrough | ✅ (GET/POST/PUT/DELETE) | ❌ |
| Audit log access | ✅ | ✅ |
| Data lineage | ❌ | ✅ |
| K8s namespace management | ❌ | ✅ |

### Design differences

- **dolphin-mcp-pilot**: Manually curated tools focused on **operations workflows** (create, run, monitor, debug). Multi-tenant auth enables shared MCP server scenarios. Raw API passthrough as a safety valve for uncovered edge cases.
- **ocean-zhc/dolphinscheduler-mcp**: Auto-generated tools providing **broad REST API coverage**. Better for read-only exploration and administrative tasks (audit logs, lineage, K8s). Single-tenant by design.

## 🛠️ Tool Categories

### Project management (5 tools)
- Test connection
- List / create / rename / delete projects

### Datasource management (1 tool)
- List datasources

### Workflow management (8 tools)
- List / get / create (SQL) / release / run / status / delete / simple-list

### Advanced workflow management (7 tools)
- Update / clone / batch-delete / list-versions / rollback / create-dag / get-by-name

### Schedule management (6 tools)
- List / set / online / offline / list-in-project / delete

### Process instance management (13 tools)
- List / stop / pause / resume / rerun / rerun-from-failure / delete / complement-data
- Get instance tasks / task log / force-task-success / skip-task

### Resource management (5 tools)
- List / view / update-content / delete / get-by-name

### Monitoring (2 tools)
- Monitor masters / workers

### User / tenant (2 tools)
- List users / tenants

### Raw API passthrough (4 tools)
- GET / POST / PUT / DELETE for any DS API endpoint

### Help & navigation (1 tool)
- `ds_help` — tool navigation guide with categories and quick-start tips

---

← Back to [README](../README.md) | [Installation](INSTALLATION.md) | [Configuration](CONFIGURATION.md) | [Deployment](DEPLOYMENT.md)
