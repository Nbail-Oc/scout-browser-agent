"""
Streamlit UI for OpenCode + Browser-Use Dual Harness.

Run with:
    streamlit run examples/ui/opencode_browser_ui.py
"""

import asyncio
import json
import os
import sys
import httpx
import streamlit as st

# Setup page layout
st.set_page_config(
	page_title="OpenCode + Browser-Use AI Agent",
	page_icon="🌐",
	layout="wide",
)

st.title("🌐 OpenCode + Browser-Use Autonomous Agent")
st.caption("Combining OpenCode's deep reasoning & planning harness with Browser-Use's web automation engine.")

OPENCODE_URL = st.sidebar.text_input("OpenCode Daemon URL", value="http://127.0.0.1:4096")


def check_health(url: str) -> bool:
	try:
		res = httpx.get(f"{url}/global/health", timeout=2.0)
		return res.status_code == 200
	except Exception:
		return False


is_healthy = check_health(OPENCODE_URL)
if is_healthy:
	st.sidebar.success("🟢 OpenCode Server Connected")
else:
	st.sidebar.error("🔴 OpenCode Server Disconnected")
	st.sidebar.info("Start daemon with:\n`opencode serve --port 4096 --hostname 127.0.0.1`")

# Main Interface
col_main, col_live = st.columns([1, 1])

with col_main:
	st.subheader("🎯 Agent Task")
	user_prompt = st.text_area(
		"What should the agent accomplish?",
		value="Research the top 3 trending GitHub Python repositories today, extract their features, and write a summary.",
		height=100,
	)
	run_btn = st.button("🚀 Run Autonomous Agent", disabled=not is_healthy, type="primary")

with col_live:
	st.subheader("📋 Planning & Live Execution")
	status_container = st.empty()
	todo_container = st.empty()
	tool_container = st.empty()

if run_btn:
	status_container.info("Starting OpenCode session...")

	async def run_flow():
		async with httpx.AsyncClient(timeout=300.0) as client:
			# 1. Create Session
			s_res = await client.post(f"{OPENCODE_URL}/session", json={"title": "Streamlit Task"})
			session_id = s_res.json().get("id") or s_res.json().get("sessionID")
			status_container.success(f"Session Active: `{session_id}`")

			# 2. Setup live output placeholders
			thought_box = st.expander("🧠 OpenCode Reasoning & Thoughts", expanded=True)
			thought_text_ph = thought_box.empty()
			tool_box = st.expander("🔧 Browser-Use Actions", expanded=True)
			tool_text_ph = tool_box.empty()

			accumulated_thoughts = ""
			tool_logs = []

			# Background SSE reader
			async def read_events():
				nonlocal accumulated_thoughts
				try:
					async with client.stream("GET", f"{OPENCODE_URL}/event") as stream:
						async for line in stream.aiter_lines():
							if line.startswith("data:"):
								raw = line[5:].strip()
								if not raw:
									continue
								try:
									data = json.loads(raw)
									t = data.get("type", "")
									p = data.get("properties", {})

									if t == "message.part.delta" and "delta" in p:
										accumulated_thoughts += p["delta"]
										thought_text_ph.markdown(accumulated_thoughts)

									elif t == "message.part.updated":
										part = p.get("part", {})
										tool = part.get("tool")
										if tool:
											tool_logs.append(f"**Tool:** `{tool}` | **State:** `{part.get('state')}`")
											tool_text_ph.markdown("\n\n".join(tool_logs))
								except Exception:
									pass
				except Exception:
					pass

			event_task = asyncio.create_task(read_events())

			# Send prompt
			await client.post(
				f"{OPENCODE_URL}/session/{session_id}/message",
				json={"parts": [{"type": "text", "text": user_prompt}]},
			)

			await asyncio.sleep(2)
			event_task.cancel()
			status_container.success("✨ Task Finished Successfully!")

	asyncio.run(run_flow())
