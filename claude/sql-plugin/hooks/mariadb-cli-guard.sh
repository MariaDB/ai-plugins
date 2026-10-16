#!/usr/bin/env bash
#
# Copyright (c) 2026, MariaDB plc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License, version 2.0,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See
# the GNU General Public License, version 2.0, for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#
# mariadb-cli-guard.sh — PreToolUse hook on the agent's shell tool (Claude Code
# and Codex use the same protocol).
#
# Denies a shell command that uses a MariaDB or MySQL command-line client for
# something the mariadb MCP server's tools do, and tells the model which tool
# to call instead. A client run from a shell needs the password on its command
# line or in its environment, where it lands in the process list, in logs and in
# the transcript the model provider sees. A connection opened through the MCP
# server reads its password from the operating system's secret store.
#
# Only five clients are looked at, and each only for what a tool covers:
#   mariadb, mysql          running SQL                    -> db.execute_sql(_script)
#   mariadb-shell, mysqlsh  SQL mode                       -> db.execute_sql(_script)
#                           `-- <object> <method>` calls   -> the matching tool
#   mariadb-dump            piped into another client      -> util.copy_*
# Everything else - --version and --help, Python or JavaScript mode, a dump
# written to a file, `-- mcp setup`, an API call no tool wraps - is let through,
# so the agent keeps every feature the tools do not have yet.
#
# Reads the hook payload (JSON) on stdin; prints a deny decision on stdout, or
# nothing to let the command run. Every failure lets the command run: a broken
# guard must never stop the agent's unrelated work.
#
# Opt-out, for an operator who wants the agent to run the clients:
#   MARIADB_PLUGIN_ALLOW_CLI=1   set in the environment the agent is started in.
#
# Pure bash 3.2 (no python, jq or node), so it runs wherever the harness runs
# hooks: macOS, Linux and Git Bash on Windows. Its rules are mirrored in the Pi
# and OpenCode extensions and the Hermes plugin; tests/cli-guard-cases.json
# holds the cases all of them must agree on.

[ "${MARIADB_PLUGIN_ALLOW_CLI:-}" = "1" ] && exit 0

# The `-- <object> <method>` calls of mariadb-shell / mysqlsh that an MCP tool
# wraps, as <object>.<method> in snake_case - the MCP tool's own name.
COVERED_API=" util.dump_instance util.dump_schemas util.dump_tables \
util.export_table util.load_dump util.import_table util.copy_instance \
util.copy_schemas util.copy_tables sandbox.deploy sandbox.start sandbox.stop \
sandbox.kill sandbox.delete msm.create_project msm.get_project_information \
msm.set_development_version msm.get_released_versions \
msm.get_last_released_version msm.get_last_deployment_version \
msm.prepare_release msm.get_sql_content_from_section \
msm.set_section_sql_content msm.generate_deployment_script \
msm.get_deployment_script_versions msm.deploy_schema mrs.dump_service \
mrs.load_service mrs.dump_service_project mrs.load_service_project \
mrs.load_content_set mrs.dump_audit_log mrs.dump_sdk_service_files "

payload=$(cat) || exit 0

# The command string: "command":"..." in tool_input. JSON escapes are undone
# just enough for the words to read as the shell would see them.
re='"command"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)"'
[[ $payload =~ $re ]] || exit 0
cmd=${BASH_REMATCH[1]}
cmd=${cmd//\\\"/\"}
cmd=${cmd//\\n/$'\n'}
cmd=${cmd//\\t/ }
cmd=${cmd//\\\\/\\}

blocked=""   # the client, once a command is denied
use=""       # what to do instead

# is_info_flag ARG — does ARG make a client only print something about itself?
is_info_flag() {
  case $1 in
    --version|-V|--help|--help=*|-\?|-I|--print-defaults) return 0 ;;
  esac
  return 1
}

# check_shell NAME ARG... — mariadb-shell or mysqlsh.
check_shell() {
  local name=$1 arg mode="" file="" api=0 object="" method="" next_is_file=0
  shift
  for arg in "$@"; do
    if [ $next_is_file = 1 ]; then file=$arg; next_is_file=0; continue; fi
    if [ $api = 1 ]; then
      case $arg in
        -*) ;;
        *) if [ -z "$object" ]; then object=$arg
           elif [ -z "$method" ]; then method=$arg; fi ;;
      esac
      continue
    fi
    is_info_flag "$arg" && return 0
    case $arg in
      --) api=1 ;;
      --sql|--sqlc|--sqlx) mode=sql ;;
      --py|--python) mode=py ;;
      --js|--javascript) mode=js ;;
      -f|--file) next_is_file=1 ;;
      --file=*) file=${arg#--file=} ;;
    esac
  done

  if [ $api = 1 ]; then
    [ -n "$method" ] || return 0
    # kebab-case and camelCase both name the same method.
    method=$(printf '%s' "$method" | sed -e 's/-/_/g' -e 's/\([A-Z]\)/_\1/g' | tr 'A-Z' 'a-z')
    case $COVERED_API in
      *" $object.$method "*)
        blocked=$name
        use="call the MCP tool $object.$method instead" ;;
    esac
    return 0
  fi

  if [ -z "$mode" ]; then
    case $file in
      *.sql) mode=sql ;;
      *.py) mode=py ;;
      *.js) mode=js ;;
    esac
  fi
  # MariaDB Shell starts in SQL mode, MySQL Shell in JavaScript.
  [ -n "$mode" ] || { [ "$name" = mariadb-shell ] && mode=sql || mode=js; }
  if [ $mode = sql ]; then
    blocked=$name
    use="run the SQL with db.connect and db.execute_sql, or db.execute_sql_script (it takes a file_path for a .sql file), instead"
  fi
}

# check_words WORD... — one simple command, already split into words. Sets
# $name to the command it runs, and $blocked and $use if it is denied. Reads
# $piped_from: the command whose output this one reads, if any.
check_words() {
  local words=("$@") i=0 word arg j
  name=""
  # Skip what runs a command rather than being one: VAR=value assignments,
  # wrappers and the options they take, and the shell's own keywords.
  while [ $i -lt ${#words[@]} ]; do
    word=${words[$i]}
    # `command -v NAME` looks a command up rather than running it.
    if [ "$word" = command ]; then
      case ${words[$((i + 1))]:-} in -v|-V) return 0 ;; esac
    fi
    case $word in
      *=*|sudo|doas|env|command|exec|nohup|time|nice|xargs|-*) ;;
      do|then|else|elif|if|while|until|'!') ;;
      *) break ;;
    esac
    i=$((i + 1))
  done
  [ $i -lt ${#words[@]} ] || return 0

  name=${words[$i]##*/}
  name=${name%.exe}

  case $name in
    # A command string handed to a shell is a command line of its own.
    sh|bash|zsh|dash|ksh|eval)
      for ((j = i + 1; j < ${#words[@]}; j++)); do
        case ${words[$j]} in
          -*) ;;
          *) check_line "${words[$j]}" ;;
        esac
      done ;;
    mariadb|mysql)
      for arg in "${words[@]:$((i + 1))}"; do
        is_info_flag "$arg" && return 0
      done
      blocked=$name
      if [ "$piped_from" = mariadb-dump ]; then
        blocked="mariadb-dump | $name"
        use="copy between servers with util.copy_instance, util.copy_schemas or util.copy_tables instead (a dump written to a file is fine)"
      else
        use="run the SQL with db.connect and db.execute_sql, or db.execute_sql_script (it takes a file_path for a .sql file), instead"
      fi ;;
    mariadb-shell|mysqlsh)
      check_shell "$name" "${words[@]:$((i + 1))}" ;;
  esac
  # mariadb-dump on its own is fine: no tool writes a .sql dump.
  return 0
}

# check_line LINE — a whole command line. Splits it into simple commands at the
# shell's separators, outside quotes, and each of those into words, quotes
# removed. $(...) and `...` start a command of their own.
check_line() {
  local line=$1 n=${#1} k=0 c quote="" word="" have_word=0 name=""
  local piped_from="" next_piped_from=""
  local words=()
  while [ $k -lt "$n" ] && [ -z "$blocked" ]; do
    c=${line:$k:1}
    if [ -n "$quote" ]; then
      if [ "$c" = "$quote" ]; then
        quote=""
      elif [ "$quote" = '"' ] && [ "$c" = '\' ]; then
        k=$((k + 1)); word+=${line:$k:1}
      elif [[ $quote = '"' && ( ${line:$k:2} = '$(' || $c = '`' ) ]]; then
        # A substitution runs even inside double quotes: check what it runs.
        local end depth=1 start
        if [ "$c" = '`' ]; then
          start=$((k + 1)); end=$start
          while [ $end -lt "$n" ] && [ "${line:$end:1}" != '`' ]; do end=$((end + 1)); done
        else
          start=$((k + 2)); end=$start
          while [ $end -lt "$n" ] && [ $depth -gt 0 ]; do
            case ${line:$end:1} in
              '(') depth=$((depth + 1)) ;;
              ')') depth=$((depth - 1)) ;;
            esac
            [ $depth -gt 0 ] && end=$((end + 1))
          done
        fi
        check_line "${line:$start:$((end - start))}"
        k=$end
      else
        word+=$c
      fi
    else
      case $c in
        "'"|'"') quote=$c; have_word=1 ;;
        '\') k=$((k + 1)); word+=${line:$k:1}; have_word=1 ;;
        ' '|$'\t')
          [ $have_word = 1 ] && words+=("$word")
          word=""; have_word=0 ;;
        ';'|'&'|'|'|'('|')'|'{'|'}'|'`'|$'\n')
          [ $have_word = 1 ] && words+=("$word")
          if [ ${#words[@]} -gt 0 ]; then
            check_words "${words[@]}"
            next_piped_from=$name
          fi
          # A single | hands this command's output to the next one; || and
          # every other separator do not.
          if [ "$c" = '|' ] && [ "${line:$((k + 1)):1}" != '|' ] \
             && [ "${line:$((k - 1)):1}" != '|' ]; then
            piped_from=$next_piped_from
          else
            piped_from=""
          fi
          next_piped_from=""
          words=(); word=""; have_word=0 ;;
        '$')
          if [ "${line:$((k + 1)):1}" = "(" ]; then
            [ $have_word = 1 ] && words+=("$word")
            [ ${#words[@]} -gt 0 ] && check_words "${words[@]}"
            words=(); word=""; have_word=0; piped_from=""; k=$((k + 1))
          else
            word+=$c; have_word=1
          fi ;;
        *) word+=$c; have_word=1 ;;
      esac
    fi
    k=$((k + 1))
  done
  [ $have_word = 1 ] && words+=("$word")
  [ ${#words[@]} -gt 0 ] && [ -z "$blocked" ] && check_words "${words[@]}"
  return 0
}

check_line "$cmd"

[ -n "$blocked" ] || exit 0

reason="Blocked: \`${blocked}\` does something the mariadb MCP server's tools do, \
and a client run from a shell puts database credentials on a command line, in \
the process list, in logs and in this conversation. Use the MCP tools: ${use}. \
Never ask for or pass a database password: open a server with db.connect, and \
if it is not in db.list_connections, ask the user to add it with \
\`mariadb-shell -- mcp setup\`. What no MCP tool covers is not blocked. If the \
user wants you to run the clients anyway, they can start the agent with \
MARIADB_PLUGIN_ALLOW_CLI=1."

printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' \
  "$reason"
