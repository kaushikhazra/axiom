# axiom

A terminal assistant that runs on a model on your own machine.

No account, no API key, no subscription. axiom talks to [Ollama](https://ollama.com), and
Ollama runs the model locally — your conversation does not leave the machine unless you
point it somewhere else on purpose.

It can read and write files, run commands, search and fetch the web, follow skills you
write for it, schedule a prompt for later, and use tools from any MCP server you configure.

## What you need

- **[Ollama](https://ollama.com/download)**, installed and running, with at least one model
  pulled.
- Nothing else. The install below brings its own Python.

If you have not pulled a model yet:

```
ollama pull qwen2.5:7b
```

Any model can hold a conversation. **Tools need a model that supports them** — axiom checks
which of yours do and lists those first.

## Install

**1. Install [uv](https://docs.astral.sh/uv/).** Skip this if you already have it.

Windows:

```
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS and Linux:

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**2. Install axiom.**

```
uv tool install --python 3.12 https://github.com/kaushikhazra/axiom/archive/refs/heads/master.zip
```

uv downloads a Python 3.12 for it if you do not have one. You do not need git.

**3. Put it on your PATH.** Only if step 2 warned you that it is not.

```
uv tool update-shell
```

Then **open a new terminal** — the change does not reach the one you are in.

**4. Check it.**

```
axiom --help
```

## Running it

Go to the folder you want to work in, then start it:

```
cd path/to/your/work
axiom
```

**The folder you start in is the folder it works in.** Files it creates land there, commands
run there, and its settings are kept there.

On the first run it lists the models Ollama has and asks which you want. It remembers the
answer for next time. With only one model installed it uses that one and tells you so. If
Ollama is not running, or has no models, axiom says so and exits with status 2 rather than
guessing.

Type a message and press enter. Four commands are handled by axiom itself:

| | |
|---|---|
| `/model` | switch model without losing the conversation |
| `/skills` | list the skills it can follow |
| `/skill <name> [text]` | run one |
| `/exit` or `/quit` | leave — `Ctrl-D` and `Ctrl-C` do the same |

## What it can do to your machine

Read this before pointing it at anything you care about.

axiom hands the model real tools, and **there is no approval prompt**. When the model decides
to run a command or change a file, it happens.

- **`run_command` runs whatever the model asks**, with your account's permissions. There is
  no list of allowed programs.
- **File tools create, change and delete.** A relative path lands in the working directory; an
  absolute path goes exactly where it says.
- axiom **tells you** when a path resolves outside the working directory, before the tool
  runs. It does not stop it.

Start it in a folder you would not mind it changing. `--no-tools` turns all of this off and
leaves you with plain chat.

## Configuration

Every setting is a command-line flag, or the same setting as an environment variable. The
flag wins.

| flag | variable | what it does |
|---|---|---|
| `--host` | `AXIOM_HOST` | Where Ollama is. Default `http://localhost:11434`. Point it at another machine to use a model you are not running yourself. |
| `--model` | `AXIOM_MODEL` | Use this model and skip the question. |
| `--working-directory` | `AXIOM_WORKING_DIRECTORY` | Where tools act, if not where you started. |
| `--no-tools` | `AXIOM_TOOLS=off` | Chat only. Takes the web, skills and MCP with it. |
| `--no-web` | `AXIOM_WEB=off` | Keep the other tools, drop search and fetch. |
| `--command-timeout` | `AXIOM_COMMAND_TIMEOUT` | Seconds a command may run before it is stopped. Default 30. |
| `--no-render` | `AXIOM_RENDER=off` | Show replies as the model wrote them, markdown and all. |

`axiom --help` lists the rest — search results, page size, fetch and MCP timeouts.

## Where its files live

Everything is under `.axiom/` in the folder you start from.

| | |
|---|---|
| `.axiom/model.json` | which model you picked, per host. Written by axiom. |
| `.axiom/mcp.json` | MCP servers to start. Written by you. |
| `.axiom/skills/` | one folder per skill, each holding a `SKILL.md`. |

Because these are relative to the working directory, **a different folder is a different
workspace** — its own model choice, its own servers, its own skills. That is deliberate, and
it means starting axiom somewhere new will ask you the model question again.

## Skills

A skill is a folder under `.axiom/skills/` holding a `SKILL.md`: markdown instructions behind
frontmatter carrying a name and a description.

```markdown
---
name: release-notes
description: Turn a list of merged pull requests into release notes.
---

Group the changes by what a reader would look for...
```

Only the name and description are sent with each request; the instructions are read from disk
at the moment the skill is invoked, so editing one mid-session takes effect without a restart.
A `SKILL.md` written for another agent loads unchanged — fields axiom does not use are
ignored.

## MCP servers

Put them in `.axiom/mcp.json` in your working directory:

```json
{
  "mcpServers": {
    "files": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
      "env": { "TOKEN": "${MY_TOKEN}" }
    }
  }
}
```

Their tools appear alongside the built-in ones as `files__read_file`. Add `"tools": [...]` to
declare only some of them.

`${NAME}` is replaced from the environment when axiom starts, so the file holds the *name* of
a secret and never its value — which is what makes it safe to commit. A server that fails to
start costs you that server and its tools, not the session.

`--no-mcp` ignores the file entirely.

## Updating and removing

`uv tool upgrade` will not re-fetch an install from a URL — it reports "nothing to upgrade".
Reinstall over the top instead:

```
uv tool install --force --python 3.12 https://github.com/kaushikhazra/axiom/archive/refs/heads/master.zip
```

To remove it:

```
uv tool uninstall axiom
```

Uninstalling leaves any `.axiom/` folders where they are.

## Working on axiom

```
git clone https://github.com/kaushikhazra/axiom.git
cd axiom
uv run axiom
uv run pytest
```

The live-model tests are excluded by default — they need Ollama and take minutes:

```
uv run pytest -m live
```
