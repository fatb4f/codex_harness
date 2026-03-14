# App Server Runtime Baseline Review

## Runtime target
- command: `codex app-server --listen stdio://`
- version: `codex-cli 0.112.0`

## Selected scenario groups
- `bootstrap`
- `threads`
- `turns`
- `collaboration`
- `approvals`
- `persistence`

## Execution results
- `bootstrap`: **passed** (725 ms) — installed bootstrap passed. userAgent=codex_app_server_runtime_probe/0.112.0 (Arch Linux Unknown; x86_64) kitty (codex_app_server_runtime_probe; 0.1.0), configRead=yes, collaborationModes=2, threadId=019cedd2-57c8-78d1-b2db-d54b3293d843.
- `threads`: **passed** (9049 ms) — persistent thread lifecycle passed. threadId=019cedd2-5acb-78b3-b60b-d3825db93482, materializedTurnId=019cedd2-5cc7-72e3-83c9-181c12196810, forkedThreadId=019cedd2-7a46-7282-ac21-f682ee41bf9b, loadedCount=2, listedCount=20.
- `turns`: **passed** (4980 ms) — turn lifecycle and output shaping passed. threadId=019cedd2-7e4b-7170-b402-64ea687aab25, turnId=019cedd2-7e76-7003-9051-3c44ee0f7b55, turnStatus=completed, turnSteerErrorCode=-32600.
- `collaboration`: **passed** (2510 ms) — collaboration discovery passed. modes=['Plan', 'Default'], enabledFeatures=['shell_tool', 'unified_exec', 'shell_snapshot', 'sqlite', 'enable_request_compression', 'multi_agent', 'skill_mcp_dependency_install', 'steer', 'collaboration_modes', 'personality', 'fast_mode'], planTurnId=019cedd2-91b2-78c3-be15-eac0f52309db.
- `approvals`: **partial** (19148 ms) — approval and user-input surface discovery was partial. threadId=019cedd2-9b56-7c52-b6a5-c4091cfb7c24, turnId=019cedd2-9b6a-7653-bff9-9456469a1fd8, enabledFeatures=['shell_tool', 'unified_exec', 'shell_snapshot', 'sqlite', 'enable_request_compression', 'multi_agent', 'skill_mcp_dependency_install', 'steer', 'collaboration_modes', 'personality', 'fast_mode'], serverRequests=[], serverRequestResolved=no, configLayers=yes.
- `persistence`: **passed** (765 ms) — thread metadata persistence passed. threadId=019cedd2-e614-79f1-8aae-b16a1672d241, branch=runtime-probe/persistence.

## Notes
- This runtime baseline validates the installed `codex app-server` surface over stdio.
- Each pack uses the smallest installed-runtime path that is practical without compiling the workspace server from source.
- Approval and user-input coverage is only marked `passed` when a real server-initiated request/response roundtrip is observed.
- Partial results mean the runtime surface was discovered, but the deeper bidirectional flow was not fully exercised in the live run.
