"""
Unified CLI runner for OpenCode + Browser-Use integration.

This runner:
1. Connects to the local OpenCode daemon (http://127.0.0.1:4096).
2. Spawns a new session and sends your high-level goal.
3. Streams OpenCode's real-time thoughts, todo lists, and Browser-Use tool invocations.
"""

import asyncio
import json
import sys
import httpx


async def check_opencode_server(base_url: str = 'http://127.0.0.1:4096') -> bool:
	try:
		async with httpx.AsyncClient(timeout=3.0) as client:
			res = await client.get(f'{base_url}/global/health')
			return res.status_code == 200
	except Exception:
		return False


async def run_opencode_task(prompt: str, base_url: str = 'http://127.0.0.1:4096'):
	is_online = await check_opencode_server(base_url)
	if not is_online:
		print(f"\n[ERROR] OpenCode daemon is not running on {base_url}.")
		print("Please start OpenCode in another terminal with:")
		print("    opencode serve --port 4096 --hostname 127.0.0.1\n")
		return

	print(f"\n========================================================")
	print(f"🚀 Starting OpenCode + Browser-Use Autonomous Agent")
	print(f"Goal: {prompt}")
	print(f"========================================================\n")

	async with httpx.AsyncClient(timeout=300.0) as client:
		# 1. Create session
		session_res = await client.post(f"{base_url}/session", json={"title": "CLI Task"})
		session_res.raise_for_status()
		session_id = session_res.json().get("id") or session_res.json().get("sessionID")
		print(f"[*] Created OpenCode Session: {session_id}")

		# 2. Start SSE listener in background
		async def sse_listener():
			try:
				async with client.stream("GET", f"{base_url}/event") as response:
					async for line in response.aiter_lines():
						if line.startswith("data:"):
							raw_json = line[5:].strip()
							if not raw_json:
								continue
							try:
								evt = json.loads(raw_json)
								evt_type = evt.get("type", "")
								props = evt.get("properties", {})

								# Token delta
								if evt_type == "message.part.delta" and "delta" in props:
									sys.stdout.write(props["delta"])
									sys.stdout.flush()

								# Tool update (Browser-Use MCP call)
								elif evt_type == "message.part.updated":
									part = props.get("part", {})
									tool_name = part.get("tool")
									state = part.get("state")
									if tool_name:
										print(f"\n[🔧 TOOL CALL] {tool_name} (State: {state})")
										if "args" in part:
											print(f"    Args: {json.dumps(part['args'])}")

								elif evt_type == "session.idle":
									print("\n\n[✓] OpenCode session completed turn.")
							except Exception:
								pass
			except asyncio.CancelledError:
				pass
			except Exception as e:
				print(f"\n[SSE Info]: Stream ended ({e})")

		listener_task = asyncio.create_task(sse_listener())

		# 3. Dispatch prompt
		print("[*] Dispatching prompt to OpenCode Brain...\n")
		msg_payload = {
			"parts": [{"type": "text", "text": prompt}],
		}
		try:
			msg_res = await client.post(f"{base_url}/session/{session_id}/message", json=msg_payload)
			msg_res.raise_for_status()
		except Exception as e:
			print(f"[ERROR] Failed to send message: {e}")
		finally:
			await asyncio.sleep(2)
			listener_task.cancel()

	print("\n========================================================")
	print("✨ Execution finished.")
	print("========================================================\n")


if __name__ == "__main__":
	if len(sys.argv) > 1:
		task_query = " ".join(sys.argv[1:])
	else:
		task_query = "Search for latest release features of Browser-Use and summarize them in bullet points."

	asyncio.run(run_opencode_task(task_query))
