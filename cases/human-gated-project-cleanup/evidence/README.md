# Evidence artifacts

These JSON files are sanitized extracts from real Claude Code MCP sessions. They retain only
the task prompt, Dolphin MCP calls, their returned values, and the final assistant response.
They omit system messages, credentials, addresses, request headers, and unrelated content.

- `two-phase-transcript.json` records the successful quarantine, separate approval, deletion,
  and read-back verification sequence.
- `exact-match-block.json` is a negative test. It intentionally asks for a name ending in
  `20260821` while the only project ends in `20260820`. The session made exactly one allowed
  read-only `ds_list_projects` call, then stopped; it made zero mutation calls.

The original evidence image (`../preview.png`) is a visual layout of the first transcript. Its
SHA-256 is `75705d6dd8c75b2c2b89d54a1e722e284b43b4432a15bf9da41cd2f01944e3ba`.

The negative-test image (`../exact-match-block.png`) is a visual layout of
`exact-match-block.json`. Its SHA-256 is
`8ac8d15e9ace655e7b91ced69f5c97672f08b6fdc17906be3a8aca714e1592e2`.
