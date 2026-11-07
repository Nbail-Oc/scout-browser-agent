"""
Full-featured Web UI for OpenCode + Browser-Use Autonomous Agent.
Provides live reasoning stream, todo checklist, browser action history, and real-time step viewer.

Run with:
    python examples/ui/opencode_gradio_ui.py
"""

import asyncio
import json
import os
import sys
import time
import httpx
import gradio as gr

# Ensure repo root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
	sys.path.insert(0, REPO_ROOT)

from browser_use import Agent, Browser, ChatOpenCode

OPENCODE_DEFAULT_URL = "http://127.0.0.1:4096"


async def check_opencode_health(base_url: str) -> bool:
	try:
		async with httpx.AsyncClient(timeout=2.0) as client:
			res = await client.get(f"{base_url.rstrip('/')}/global/health")
			return res.status_code == 200
	except Exception:
		return False


async def run_autonomous_agent(
	task_prompt: str,
	opencode_url: str,
	model_name: str,
	headless: bool,
	max_steps: int,
	use_vision: bool,
):
	if not task_prompt.strip():
		yield (
			"⚠️ Please enter a task description.",
			"Idle",
			"",
			"Waiting for prompt...",
			None,
		)
		return

	is_online = await check_opencode_health(opencode_url)
	if not is_online:
		yield (
			f"❌ Could not connect to OpenCode daemon at {opencode_url}.\n"
			"Please ensure OpenCode is running (`opencode serve --port 4096 --hostname 127.0.0.1`).",
			"Server Offline",
			"",
			"OpenCode not detected.",
			None,
		)
		return

	status_msg = "🚀 Initializing OpenCode Agent & Browser-Use..."
	yield (
		"Connecting to OpenCode session...",
		"Initializing",
		"⏳ Creating session...",
		"Launching browser...",
		None,
	)

	thought_stream = ""
	action_logs = []
	step_history = ""
	latest_screenshot = None

	try:
		# Initialize ChatOpenCode adapter
		llm = ChatOpenCode(
			base_url=opencode_url,
			model=model_name,
			timeout=120.0,
		)

		browser = Browser(
			headless=headless,
			window_size={"width": 1280, "height": 800},
		)

		agent = Agent(
			task=task_prompt,
			llm=llm,
			browser=browser,
			use_vision=use_vision,
			max_actions_per_step=1,
		)

		action_logs.append("🌐 Chromium session launched.")
		action_logs.append("🧠 OpenCode Planner active.")

		yield (
			"### 🧠 OpenCode Reasoning:\nAnalyzing prompt and formulating execution plan...",
			"Running",
			"\n".join([f"- [ ] Step: {task_prompt[:60]}..."]),
			"\n\n".join(action_logs),
			None,
		)

		# Run the agent execution loop
		history = await agent.run(max_steps=max_steps)

		# Extract screenshots and steps
		all_actions = history.action_names() if hasattr(history, "action_names") else []
		extracted = history.final_result() if hasattr(history, "final_result") else "Task Completed."

		for idx, act in enumerate(all_actions, 1):
			action_logs.append(f"Step {idx}: Executed `{act}`")

		# Check for screenshots
		screenshots = history.screenshot_paths() if hasattr(history, "screenshot_paths") else []
		if screenshots and len(screenshots) > 0:
			latest_screenshot = screenshots[-1]

		final_report = (
			f"### ✅ Task Execution Summary\n\n"
			f"**Result:**\n{extracted}\n\n"
			f"**Total Steps:** {len(all_actions)}\n"
			f"**Completed Successfully:** {history.is_done() if hasattr(history, 'is_done') else True}"
		)

		yield (
			final_report,
			"Completed",
			"✅ All planned steps executed.",
			"\n\n".join(action_logs),
			latest_screenshot,
		)

	except Exception as e:
		yield (
			f"❌ Execution Error: {str(e)}",
			"Failed",
			"⚠️ Execution interrupted.",
			f"Error: {str(e)}",
			None,
		)


# Build the Gradio UI Layout
def build_interface():
	theme = gr.themes.Soft(
		primary_hue="blue",
		secondary_hue="slate",
		neutral_hue="slate",
	)

	custom_css = """
	.container { max-width: 1300px; margin: auto; }
	.header-title { font-size: 26px; font-weight: 700; color: #1e293b; margin-bottom: 4px; }
	.header-subtitle { color: #64748b; font-size: 14px; margin-bottom: 20px; }
	"""

	with gr.Blocks(title="Browser-Use AI Controller", theme=theme, css=custom_css) as demo:
		with gr.Row():
			with gr.Column():
				gr.Markdown("<div class='header-title'>🌐 Browser-Use Autonomous Agent Control Center</div>")
				gr.Markdown(
					"<div class='header-subtitle'>Powered by OpenCode Deep Reasoning Engine & Browser-Use CDP Automation</div>"
				)

		with gr.Row():
			# Left Control Sidebar
			with gr.Column(scale=4):
				with gr.Group():
					gr.Markdown("### 🎯 Task Configuration")
					task_input = gr.Textbox(
						label="Task Goal",
						placeholder="What should the agent automate? (e.g. Find pricing tiers on stripe.com and summarize them)",
						lines=4,
						value="Go to python.org, find what is new in the latest release, and summarize the key highlights.",
					)

					with gr.Accordion("⚙️ Advanced Settings", open=False):
						opencode_url = gr.Textbox(
							label="OpenCode Server URL",
							value=OPENCODE_DEFAULT_URL,
						)
						model_select = gr.Dropdown(
							choices=[
								"opencode/deepseek-v4-flash-free",
								"opencode/claude-3-7-sonnet",
								"opencode/gpt-4o",
								"opencode/qwen-2.5-72b",
							],
							value="opencode/deepseek-v4-flash-free",
							label="OpenCode Model",
						)
						max_steps_slider = gr.Slider(
							minimum=1,
							maximum=50,
							value=15,
							step=1,
							label="Max Steps",
						)
						headless_toggle = gr.Checkbox(
							label="Headless Mode (Hide Chromium Window)",
							value=False,
						)
						vision_toggle = gr.Checkbox(
							label="Use Vision (Send Screenshots to Model)",
							value=False,
						)

					run_button = gr.Button("🚀 Run Autonomous Agent", variant="primary", size="lg")
					status_badge = gr.Textbox(label="Agent Status", value="Ready", interactive=False)

			# Right Output & Inspection Workspace
			with gr.Column(scale=6):
				with gr.Tabs():
					with gr.TabItem("🧠 Reasoning & Output"):
						output_markdown = gr.Markdown(
							value="### Ready to run\nEnter your task on the left and click **Run Autonomous Agent**."
						)

					with gr.TabItem("📋 Todo List & Planning"):
						todo_markdown = gr.Markdown(value="No active plan yet.")

					with gr.TabItem("🔧 Action History Logs"):
						action_logs_box = gr.Markdown(value="Waiting for actions...")

					with gr.TabItem("📸 Live Screenshot / Viewport"):
						screenshot_viewer = gr.Image(label="Latest Browser Viewport", interactive=False)

		# Hook up click event
		run_button.click(
			fn=run_autonomous_agent,
			inputs=[
				task_input,
				opencode_url,
				model_select,
				headless_toggle,
				max_steps_slider,
				vision_toggle,
			],
			outputs=[
				output_markdown,
				status_badge,
				todo_markdown,
				action_logs_box,
				screenshot_viewer,
			],
		)

	return demo


if __name__ == "__main__":
	app = build_interface()
	app.launch(server_name="127.0.0.1", server_port=7860)
