name: gaussian
triggers: gaussian, gauss, g16, g09, gjf, com, b3lyp, 6-31g, opt, freq

# Gaussian Workflow

Use this skill when the user asks for a Gaussian calculation or gives Gaussian route keywords.

## Tool Model

- Do not use a Gaussian-specific function. Use only the base tools: `path_info`, `list_dir`, `read_file`, `write_file`, and `run_command`.
- Treat Settings -> Workspace as the task working directory. Put generated `.gjf`, `.com`, `.chk`, `.log`, and small helper files there unless the user gives another path.
- Do not use the application install directory or process cwd as the calculation directory.
- Always wait for tool results before saying a file exists, a command ran, or a calculation completed.

## Preflight

1. Check the current tool workspace with `system_info` if the workspace is unknown.
2. If the user gives a Gaussian executable path, verify it with `path_info`.
3. If the user does not give a path, inspect common executable names or paths with generic tools. Prefer direct executable paths over shell probing.
4. Before writing inputs, choose a short, explicit file name in the workspace.

## Running

- Write the Gaussian input with `write_file`.
- Ask for confirmation before `run_command`.
- Run Gaussian directly as an argv list, for example:
  - command: `/opt/Gaussian/g16/g16`
  - args: `["water.gjf"]`
- Use the workspace as `cwd` for the run unless the user specified another calculation directory.

## Follow-up

- After running, inspect the log with `read_file` or `search_text`.
- Report only what the log supports. For optimization, look for normal termination and final geometry or convergence text before claiming success.
